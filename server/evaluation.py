"""Strict run contract shared by JSON, CSV conversion and real/synthetic evaluators."""
import csv
import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints, model_validator

ID = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
SHA = Annotated[str, StringConstraints(pattern=r'^[a-f0-9]{64}$')]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Link(StrictModel):
    wedding_id: ID
    person_id: ID
    canonical_photo_id: ID


class Label(Link):
    present: StrictBool | None
    recognisable: StrictBool | None
    annotation_status: Literal['adjudicated', 'source_verified', 'unknown']
    label_basis: str | None = None

    @model_validator(mode='after')
    def consistent(self):
        if self.annotation_status == 'unknown' and (self.present is not None or self.recognisable is not None):
            raise ValueError('unknown_status_requires_null_truth')
        if self.annotation_status != 'unknown' and self.present is None:
            raise ValueError('known_status_requires_boolean_truth')
        if self.recognisable is True and self.present is not True:
            raise ValueError('recognisable_requires_present')
        if self.annotation_status == 'source_verified' and not self.label_basis:
            raise ValueError('source_verified_requires_provenance')
        return self


class Person(StrictModel):
    wedding_id: ID
    person_id: ID


class Asset(StrictModel):
    asset_id: ID
    path: ID
    sha256: SHA
    person_id: ID
    capture_group_id: ID
    wedding_id: ID
    split: Literal['development', 'calibration', 'test', 'probe']
    split_version: ID
    kind: Literal['reference', 'gallery']
    canonical_photo_id: ID | None = None


class Evaluation(StrictModel):
    dataset_version: ID
    split_version: ID
    protocol: Literal['synthetic', 'capture_holdout_exploratory', 'event_identity_holdout', 'studio_identity_split_exploratory']
    event_id: ID
    canonical_photo_ids: list[ID]
    enrolled: list[Person]
    labels: list[Label]
    person_mapping: dict[ID, ID]
    photo_mapping: dict[ID, ID]
    assets: list[Asset]
    sealed_test: Literal[False] = False

    @model_validator(mode='after')
    def complete(self):
        photos = set(self.canonical_photo_ids)
        people = {p.person_id for p in self.enrolled}
        if not photos or not people or len(photos) != len(self.canonical_photo_ids) or len(people) != len(self.enrolled):
            raise ValueError('nonempty_unique_photo_universe_and_roster_required')
        if any(p.wedding_id != self.event_id for p in self.enrolled):
            raise ValueError('evaluation_event_mismatch')
        expected = {(self.event_id, p, f) for p in people for f in photos}
        actual = [(r.wedding_id, r.person_id, r.canonical_photo_id) for r in self.labels]
        if len(set(actual)) != len(actual) or set(actual) != expected:
            raise ValueError('complete_unique_photo_person_matrix_required')
        if set(self.person_mapping.values()) != people or len(self.person_mapping) != len(people):
            raise ValueError('person_mapping_mismatch')
        if set(self.photo_mapping.values()) != photos or len(self.photo_mapping) != len(photos):
            raise ValueError('photo_mapping_mismatch')
        if any(r.annotation_status == 'source_verified' for r in self.labels) and self.protocol != 'studio_identity_split_exploratory':
            raise ValueError('source_verified_requires_explicit_studio_protocol')
        if self.protocol != 'synthetic' and not self.assets:
            raise ValueError('nonempty_real_input_split_required')
        if self.assets:
            if len({a.asset_id for a in self.assets}) != len(self.assets):
                raise ValueError('duplicate_asset')
            gallery = [a for a in self.assets if a.kind == 'gallery']
            if {a.canonical_photo_id for a in gallery} != photos or len(gallery) != len(photos):
                raise ValueError('asset_photo_universe_mismatch')
            if any(self.photo_mapping.get(a.asset_id) != a.canonical_photo_id for a in gallery):
                raise ValueError('asset_mapping_mismatch')
            if any(a.wedding_id != self.event_id or a.split_version != self.split_version for a in self.assets):
                raise ValueError('asset_event_or_version_mismatch')
            references = [a for a in self.assets if a.kind == 'reference']
            if {a.person_id for a in references} != set(self.person_mapping):
                raise ValueError('reference_roster_mismatch')
            for key in ('sha256', 'capture_group_id'):
                if {getattr(a, key) for a in references} & {getattr(a, key) for a in gallery}:
                    raise ValueError('reference_gallery_reuse_' + key)
            validate_split_assets(self.assets, self.protocol)
        return self

    def verify(self, service, input_root=None):
        if (self.protocol == 'synthetic') != service.provider.synthetic:
            raise ValueError('provider_protocol_mismatch')
        for a in self.assets:
            path = Path(a.path)
            if input_root is None or path.is_absolute() or '..' in path.parts:
                raise ValueError('safe_input_root_required')
            resolved = (Path(input_root) / path).resolve()
            if not resolved.is_relative_to(Path(input_root).resolve()) or hashlib.sha256(resolved.read_bytes()).hexdigest() != a.sha256:
                raise ValueError('input_hash_mismatch')
        with service.db.connect() as db:
            event = db.execute('SELECT * FROM events WHERE id=?', (self.event_id,)).fetchone()
            if not event:
                raise ValueError('missing_app_event')
            if self.protocol == 'studio_identity_split_exploratory' and event['authorization_kind'] != 'published_dataset_study_use_basis':
                raise ValueError('study_authorization_type_required')
            roster = {r[0] for r in db.execute('SELECT id FROM participants WHERE event_id=? AND active=1', (self.event_id,))}
            if roster != {p.person_id for p in self.enrolled}:
                raise ValueError('app_roster_mismatch')
            photos = {r['id']: r for r in db.execute('SELECT * FROM photos WHERE event_id=?', (self.event_id,))}
            if not set(self.canonical_photo_ids).issubset(photos):
                raise ValueError('missing_app_photo')
            for a in self.assets:
                if a.kind == 'gallery' and photos[a.canonical_photo_id]['hash'] != a.sha256:
                    raise ValueError('app_photo_hash_mismatch')
            for source, app in self.person_mapping.items():
                enrollment = db.execute('SELECT * FROM enrollments WHERE event_id=? AND participant_id=?', (self.event_id, app)).fetchone()
                refs = [a.sha256 for a in self.assets if a.kind == 'reference' and a.person_id == source]
                if enrollment and refs and sorted(json.loads(enrollment['reference_hashes'])) != sorted(refs):
                    raise ValueError('app_reference_hash_mismatch')
        return self


def validate_split_assets(assets, protocol):
    seen = {}
    keys = ['capture_group_id', 'sha256']
    if protocol in {'event_identity_holdout', 'studio_identity_split_exploratory'}:
        keys.append('person_id')
    if protocol == 'event_identity_holdout':
        keys.append('wedding_id')
    for a in assets:
        for key in keys:
            identity = (key, getattr(a, key))
            if identity in seen and seen[identity] != a.split:
                raise ValueError('split_leakage_' + key)
            seen[identity] = a.split


def labels_from_csv(path):
    """Explicit conversion; JSON validation never coerces string/integer booleans."""
    values = {'true': True, 'false': False, 'unknown': None, 'null': None, '': None}
    result = []
    with Path(path).open(newline='') as stream:
        for row in csv.DictReader(stream):
            for field in ('present', 'recognisable'):
                if row[field] not in values:
                    raise ValueError('invalid_csv_boolean')
                row[field] = values[row[field]]
            result.append(Label.model_validate(row).model_dump())
    return result
