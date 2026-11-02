"""C1 input/label contract and source-ID gallery comparison; no recognition inference here."""
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import StrictBool, model_validator

from server.evaluation import ID, SHA, StrictModel
from server.identity import sha_file

PAIR_REQUIREMENTS = (('A', 'B'), ('A', 'C'), ('B', 'C'))
PAIR_PROTOCOL = {
    'version': 'exact-enrolled-pairs-v2',
    'required_pairs': [list(pair) for pair in PAIR_REQUIREMENTS],
    'distinct_photographs': True,
    'exact_enrolled_presence_subset': True,
    'unenrolled_U_V_allowed': True,
    'ABC_qualifies': False,
    'delivery': 'same_photo_exactly_once_in_both_intended_guest_galleries_and_zero_in_absent_enrolled_galleries',
    'source': 'guest_galleries_before_operator_corrections',
}


class Evidence(StrictModel):
    path: ID
    sha256: SHA


class StudyPerson(StrictModel):
    person_id: ID
    role: Literal['enrolled_present', 'enrolled_absent', 'unenrolled']
    permitted_use: Evidence


class StudyPhoto(Evidence):
    asset_id: ID
    kind: Literal['reference', 'group', 'solo', 'unknown_only']
    depicted_person_ids: list[ID]
    capture_group_id: ID
    capture_record: Evidence

    @model_validator(mode='after')
    def identities(self):
        if not self.depicted_person_ids or len(set(self.depicted_person_ids)) != len(self.depicted_person_ids):
            raise ValueError('unique_nonempty_depicted_identities_required')
        return self


class Presence(StrictModel):
    person_id: ID
    asset_id: ID
    present: StrictBool
    recognisable: StrictBool | None


class Controls(StrictModel):
    duplicate_asset_id: ID
    corrupt: Evidence
    no_face: Evidence


class Challenge(StrictModel):
    """24 photos/96 human-verified labels; distinct exact AB, AC, BC group captures required; ABC cannot substitute."""

    schema_version: Literal['c1-natural-group-pairs-v2']
    study_id: ID
    input_kind: Literal['natural_photographs', 'synthetic_test_only']
    authorization_kind: Literal['participant_consent', 'published_dataset_study_use_basis']
    permitted_use: Evidence
    # This record must describe human annotation, identity mapping, and capture independence.
    annotation_record: Evidence
    capture_independence_record: Evidence
    fresh_capture_record: Evidence
    people: list[StudyPerson]
    assets: list[StudyPhoto]
    labels: list[Presence]
    controls: Controls

    @property
    def enrolled(self):
        return [p.person_id for p in self.people if p.role != 'unenrolled']

    @property
    def gallery(self):
        return [a for a in self.assets if a.kind != 'reference']

    def pair_opportunities(self):
        # Derive eligible photographs from complete presence truth, never recognizer predictions.
        presence = {a.asset_id: {r.person_id for r in self.labels if r.asset_id == a.asset_id and r.present}
                    for a in self.gallery if a.kind == 'group'}
        return {'+'.join(pair): sorted(a for a, people in presence.items() if people == set(pair))
                for pair in PAIR_REQUIREMENTS}

    @model_validator(mode='after')
    def complete(self):
        people = {p.person_id for p in self.people}
        if len(people) != len(self.people) or Counter(p.role for p in self.people) != {
                'enrolled_present': 3, 'enrolled_absent': 1, 'unenrolled': 2}:
            raise ValueError('six_person_3_present_1_absent_2_unenrolled_design_required')
        if {p.person_id: p.role for p in self.people} != {
                'A': 'enrolled_present', 'B': 'enrolled_present', 'C': 'enrolled_present',
                'D': 'enrolled_absent', 'U': 'unenrolled', 'V': 'unenrolled'}:
            raise ValueError('protocol_pseudonyms_A_B_C_present_D_absent_U_V_unenrolled_required')
        if Counter(a.kind for a in self.assets) != {'reference': 4, 'group': 12, 'solo': 6, 'unknown_only': 6}:
            raise ValueError('four_references_12_group_6_solo_6_unknown_required')
        if len({a.asset_id for a in self.assets}) != len(self.assets):
            raise ValueError('duplicate_asset_id')
        if len({a.sha256 for a in self.assets}) != len(self.assets):
            raise ValueError('duplicate_study_bytes_controls_must_be_separate')
        if len({a.path for a in self.assets}) != len(self.assets):
            raise ValueError('duplicate_asset_path')
        refs = [a for a in self.assets if a.kind == 'reference']
        if any(len(a.depicted_person_ids) != 1 for a in refs) or {
                a.depicted_person_ids[0] for a in refs} != set(self.enrolled):
            raise ValueError('one_single_identity_reference_per_enrollee_required')
        # Across the ENTIRE study, even reuse by a different identity is forbidden.
        if {a.capture_group_id for a in refs} & {a.capture_group_id for a in self.gallery}:
            raise ValueError('study_reference_gallery_capture_reuse')
        for a in self.assets:
            if not set(a.depicted_person_ids) <= people:
                raise ValueError('depicted_identity_outside_roster')
            if a.kind == 'group' and (len(a.depicted_person_ids) < 2 or not set(a.depicted_person_ids) & set(self.enrolled)):
                raise ValueError('group_requires_multiple_identities_and_enrolled_presence')
            if a.kind == 'solo' and (len(a.depicted_person_ids) != 1 or a.depicted_person_ids[0] not in self.enrolled):
                raise ValueError('solo_requires_one_enrolled_identity')
            if a.kind == 'unknown_only' and set(a.depicted_person_ids) & set(self.enrolled):
                raise ValueError('unknown_only_cannot_contain_enrolled_identity')
        expected = {(p, a.asset_id) for p in self.enrolled for a in self.gallery}
        actual = [(r.person_id, r.asset_id) for r in self.labels]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError('complete_unique_person_photo_presence_matrix_required')
        photos = {a.asset_id: a for a in self.gallery}
        for row in self.labels:
            if row.present != (row.person_id in photos[row.asset_id].depicted_person_ids):
                raise ValueError('label_contradicts_documented_depicted_identities')
            if row.recognisable is True and not row.present:
                raise ValueError('recognisable_requires_present')
        for p in self.people:
            present = any(p.person_id in a.depicted_person_ids for a in self.gallery)
            if (p.role == 'enrolled_absent' and present) or (p.role != 'enrolled_absent' and not present):
                raise ValueError('declared_role_contradicts_presence')
            if p.role == 'enrolled_present' and not any(
                    a.kind == 'group' and p.person_id in a.depicted_person_ids for a in self.gallery):
                raise ValueError('each_present_enrollee_requires_group_photo_opportunity')
        if self.controls.duplicate_asset_id not in photos:
            raise ValueError('duplicate_control_must_reference_gallery_asset')
        controls = [self.controls.corrupt, self.controls.no_face]
        if len({c.sha256 for c in controls}) != 2 or {c.sha256 for c in controls} & {a.sha256 for a in self.assets}:
            raise ValueError('controls_must_be_distinct_from_challenge_assets')
        missing = [pair for pair, photos in self.pair_opportunities().items() if not photos]
        if missing:
            raise ValueError('missing_exact_enrolled_pair_group_photographs:' + ','.join(missing))
        return self

    def verify_files(self, root):
        """Read only; documentation is required evidence, not an invented approval."""
        evidence = [self.permitted_use, self.annotation_record, self.capture_independence_record,
                    self.fresh_capture_record, *(p.permitted_use for p in self.people),
                    *(a.capture_record for a in self.assets)]
        files = [*evidence, *self.assets, self.controls.corrupt, self.controls.no_face]
        inventory = {}
        for item in files:
            path = safe_input(root, item.path)
            if not path.is_file() or sha_file(path) != item.sha256:
                raise ValueError('missing_or_changed_input:' + item.path)
            if item in evidence and not path.read_bytes().strip():
                raise ValueError('empty_documentation:' + item.path)
            if item.path in inventory and inventory[item.path] != item.sha256:
                raise ValueError('conflicting_file_hash')
            inventory[item.path] = item.sha256
        return inventory


def safe_input(root, relative):
    name = Path(relative)
    resolved = (Path(root) / name).resolve()
    if name.is_absolute() or '..' in name.parts or not resolved.is_relative_to(Path(root).resolve()):
        raise ValueError('unsafe_input_path')
    return resolved


def compare_galleries(study, delivered, failures, *, observations):
    """Use every declared link, including photos that could not import/process."""
    if set(observations) != set(study.enrolled):
        raise ValueError('explicit_observation_status_required_for_every_enrollee')
    for record in observations.values():
        if (set(record) != {'status', 'error'} or record['status'] not in {'observed', 'unavailable'}
                or (record['status'] == 'observed' and record['error'] is not None)
                or (record['status'] == 'unavailable' and not isinstance(record['error'], str))):
            raise ValueError('invalid_gallery_observation_record')
    observed = {p for p, record in observations.items() if record['status'] == 'observed'}
    complete = observed == set(study.enrolled)
    universe = {(p, a.asset_id) for p in study.enrolled for a in study.gallery}
    expected = {(r.person_id, r.asset_id) for r in study.labels if r.present}
    counts = Counter(delivered)  # Keep multiplicity; duplicate delivery must not disappear into a set.
    actual = set(counts)
    if not actual <= universe:
        raise ValueError('delivery_outside_frozen_universe')
    if any(p not in observed for p, _ in actual):
        raise ValueError('delivery_without_successful_gallery_observation')
    observable = {(p, a) for p, a in universe if p in observed}
    correct, wrong, missed = actual & expected, actual - expected, (expected & observable) - actual
    def rows(links):
        return [{'person_id': p, 'asset_id': a} for p, a in sorted(links)]
    per_person = []
    for p in study.enrolled:
        truth = {a for person, a in expected if person == p}
        got = {a for person, a in actual if person == p}
        per_person.append({'person_id': p, 'expected': sorted(truth), 'observation': observations[p],
                           'actual': sorted(got) if p in observed else None,
                           'wrong': sorted(got-truth) if p in observed else None,
                           'missed': sorted(truth-got) if p in observed else None,
                           'presence_recall': len(truth & got)/len(truth) if truth and p in observed else None})
    shared = {p.person_id: (any((p.person_id, a.asset_id) in correct for a in study.gallery if a.kind == 'group')
                           if p.person_id in observed else None)
              for p in study.people if p.role == 'enrolled_present'}
    pairs = {}
    for pair in PAIR_REQUIREMENTS:
        key = '+'.join(pair)
        opportunities = study.pair_opportunities()[key]
        photos = []
        for a in opportunities:
            recipient_counts = {p: counts[p, a] if p in observed else None for p in study.enrolled}
            passed = complete and all(recipient_counts[p] == 1 for p in pair) and all(
                recipient_counts[p] == 0 for p in study.enrolled if p not in pair)
            photos.append({'asset_id': a, 'guest_gallery_occurrences': recipient_counts,
                           'observation_complete': complete, 'passed': passed})
        successful = [a['asset_id'] for a in photos if a['passed']]
        pairs[key] = {'qualifying_photo_ids': opportunities, 'successful_photo_ids': successful,
                      'passed': bool(successful), 'photos': photos}
    pair_success = all(p['passed'] for p in pairs.values())
    duplicates = [{'person_id': p, 'asset_id': a, 'occurrences': n}
                  for (p, a), n in sorted(counts.items()) if n > 1]
    recall = len(correct)/len(expected) if expected and complete else None
    return {'evidence_kind': study.input_kind, 'recognition_accuracy_claim': False,
            'gallery_observations': observations, 'gallery_observation_complete': complete,
            'unobserved_people': sorted(set(study.enrolled) - observed),
            'metrics_scope': 'complete_gallery_observation' if complete else 'partial_gallery_observation',
            'unobserved_expected_links': rows(expected - observable),
            'photo_denominator': len(study.gallery), 'label_denominator': len(study.labels),
            'expected_links': rows(expected), 'actual_links': rows(actual), 'wrong_links': rows(wrong),
            'missed_links': rows(missed), 'correct_links': len(correct), 'presence_recall': recall,
            'per_person': per_person, 'shared_photo_retrieval': shared, 'processing_failures': failures,
            'pair_protocol': PAIR_PROTOCOL, 'pair_delivery': pairs, 'pair_delivery_success': pair_success,
            'duplicate_deliveries': duplicates, 'delivery_observation_count': sum(counts.values()),
            'pilot_targets': {'complete_gallery_observation': complete,
                              'zero_wrong_deliveries': complete and not wrong, 'presence_recall_at_least_80_percent':
                              recall is not None and recall >= .8, 'shared_photo_for_every_present_enrollee': complete and all(shared.values()),
                              'exact_pair_delivery_for_AB_AC_BC': pair_success, 'no_duplicate_deliveries': complete and not duplicates},
            'passed_pilot_targets': complete and not wrong and recall is not None and recall >= .8 and all(shared.values()) and pair_success and not duplicates,
            'matrix': [{'person_id': p, 'asset_id': a, 'expected': (p, a) in expected,
                        'observation_status': observations[p]['status'], 'observation_error': observations[p]['error'],
                        'actual': (p, a) in actual if p in observed else None,
                        'actual_count': counts[p, a] if p in observed else None} for p, a in sorted(universe)]}
