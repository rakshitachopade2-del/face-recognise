"""Validate private CSV manifests without loading any photographs or model weights."""
import argparse
import csv
import json
from pathlib import Path

from server.metrics import validate_splits

HEADERS = {
    "media.csv": "wedding_id asset_id path canonical_photo_id capture_group_id stage_id permission_record_id",
    "face_annotations.csv": "wedding_id asset_id annotation_face_id person_id_or_unknown bbox_xywh recognisable original_interocular_px depiction_type annotation_status",
    "person_photo_labels.csv": "wedding_id person_id canonical_photo_id present recognisable annotation_status",
    "enrollments.csv": "wedding_id person_id enrollment_id capture_session_id path consent_record_id consent_version",
    "split_memberships.csv": "wedding_id person_id capture_group_id split split_version",
}


def validate(directory):
    tables = {}
    for filename, required in HEADERS.items():
        with (directory / filename).open(newline="") as stream:
            reader = csv.DictReader(stream)
            if not set(required.split()).issubset(reader.fieldnames or []):
                raise ValueError(f"missing_columns:{filename}")
            tables[filename] = list(reader)
    validate_splits(tables['split_memberships.csv'])
    assets, canonical = set(), set()
    for row in tables['media.csv']:
        if not row['permission_record_id']:
            raise ValueError('media_permission_record_required')
        path = Path(row['path'])
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('relative_safe_media_paths_required')
        key = row['wedding_id'], row['asset_id']
        if key in assets:
            raise ValueError('duplicate_asset_id')
        assets.add(key)
        canonical.add((row['wedding_id'], row['canonical_photo_id']))
    for row in tables['face_annotations.csv']:
        if (row['wedding_id'], row['asset_id']) not in assets:
            raise ValueError('unknown_annotated_asset')
        bbox = json.loads(row['bbox_xywh'])
        if len(bbox) != 4 or any(float(v) < 0 for v in bbox) or float(row['original_interocular_px']) < 0:
            raise ValueError('invalid_face_annotation_coordinates')
    labels = {}
    for row in tables['person_photo_labels.csv']:
        if (row['wedding_id'], row['canonical_photo_id']) not in canonical:
            raise ValueError('unknown_labeled_photo')
        if row['present'] not in {'true', 'false', 'unknown'} or row['recognisable'] not in {'true', 'false', 'unknown'}:
            raise ValueError('label_boolean_must_be_true_false_or_unknown')
        key = row['wedding_id'], row['person_id'], row['canonical_photo_id']
        if key in labels and labels[key] != row:
            raise ValueError('conflicting_person_photo_labels')
        labels[key] = row
    for row in tables['enrollments.csv']:
        if not row['consent_record_id'] or not row['consent_version']:
            raise ValueError('enrollment_consent_required')
        if Path(row['path']).is_absolute() or '..' in Path(row['path']).parts:
            raise ValueError('relative_safe_enrollment_paths_required')
    return {"status": "schema_checks_passed", "counts": {k: len(v) for k, v in tables.items()},
            "limit": "Checks structure and declared split identifiers, not legal permission or annotation truth."}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    print(json.dumps(validate(parser.parse_args().directory)))
