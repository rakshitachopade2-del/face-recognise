"""C1 contract, freeze and actual app workflow checks. All inputs are SYNTHETIC, not faces."""
import copy
import hashlib
import json
from unittest.mock import Mock

import pytest

from scripts import group_challenge as runner
from scripts import studio_study
from scripts.make_fixtures import fixture
from server.challenge import Challenge, compare_galleries
from server.config import digest_json
from server.identity import sha_file


def write(root, name, content):
    p = root/name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return {'path': name, 'sha256': sha_file(p)}


def observed_galleries(study):
    """Explicit observation metadata for pure scorer fixtures, including successfully empty galleries."""
    return {p: {'status': 'observed', 'error': None} for p in study.enrolled}


@pytest.fixture
def study_input(tmp_path):
    root = tmp_path/'inputs'
    evidence = write(root, 'SYNTHETIC.txt', b'SYNTHETIC test documentation only; NO human permission or natural photographs.')
    people = [{'person_id': p, 'role': r, 'permitted_use': evidence} for p, r in
              zip('ABCDUV', ['enrolled_present']*3+['enrolled_absent']+['unenrolled']*2)]
    assets = []
    for i, p in enumerate('ABCD'):
        # D intentionally cannot enroll. The failure must remain visible, with D in all 24 label rows.
        raw = fixture([['red', 'green', 'blue'][i]] if i < 3 else [], variant=100+i)
        assets.append({**write(root, f'ref-{p}.png', raw), 'asset_id': f'ref-{p}', 'kind': 'reference',
                       'depicted_person_ids': [p], 'capture_group_id': f'ref-session-{p}', 'capture_record': evidence})
    for i in range(24):
        kind = 'group' if i < 12 else 'solo' if i < 18 else 'unknown_only'
        depicted = list(('AB', 'AC', 'BC')[i % 3]) if kind == 'group' else ['ABC'[i%3]] if kind == 'solo' else ['UV'[i%2]]
        colors = [{'A': 'red', 'B': 'green', 'C': 'blue'}[p] for p in depicted if p in 'ABC']
        assets.append({**write(root, f'photo-{i}.png', fixture(colors, variant=i)), 'asset_id': f'p{i}',
                       'kind': kind, 'depicted_person_ids': depicted, 'capture_group_id': 'gallery-session',
                       'capture_record': evidence})
    data = {'schema_version': 'c1-natural-group-pairs-v2', 'study_id': 'SYNTHETIC-ONLY',
            'input_kind': 'synthetic_test_only', 'authorization_kind': 'participant_consent',
            'permitted_use': evidence, 'annotation_record': evidence, 'capture_independence_record': evidence,
            'fresh_capture_record': evidence, 'people': people, 'assets': assets,
            'labels': [{'person_id': p, 'asset_id': a['asset_id'], 'present': p in a['depicted_person_ids'],
                        'recognisable': p in a['depicted_person_ids']} for p in 'ABCD' for a in assets[4:]],
            'controls': {'duplicate_asset_id': 'p0', 'corrupt': write(root, 'corrupt.bin', b'SYNTHETIC CORRUPT'),
                         'no_face': write(root, 'blank.png', fixture([], variant=1000))}}
    (root/'study.json').write_text(json.dumps(data))
    return root, data


def test_full_synthetic_app_workflow(service, study_input, tmp_path):
    inputs, data = study_input
    study = Challenge.model_validate(data)
    study.verify_files(inputs)
    out = tmp_path/'output'
    result = runner.execute(study, inputs, out, service)
    assert result['evidence_kind'] == 'synthetic_test_only'
    assert result['photo_denominator'] == 24 and result['label_denominator'] == 96
    assert len(result['actual_links']) == result['correct_links'] == 30
    assert not result['wrong_links'] and not result['missed_links']
    assert result['shared_photo_retrieval'] == dict.fromkeys('ABC', True)
    assert result['per_person'][3]['presence_recall'] is None
    assert any(f['stage'] == 'enrollment' and f['person_id'] == 'D' for f in result['processing_failures'])
    assert result['controls']['passed']
    assert not result['design_executed'] and not result['challenge_succeeded']
    assert len((out/'gallery-comparison.csv').read_text().splitlines()) == 97
    assert len(runner.load(out/'raw-before-corrections.json')['photos']) == 24


@pytest.mark.parametrize('mutation,reason', [
    ('missing_label', 'complete_unique'), ('duplicate_label', 'complete_unique'),
    ('string_bool', 'boolean'), ('wrong_presence', 'contradicts_documented'),
    ('unknown_identity', 'outside_roster'), ('capture_reuse', 'capture_reuse'),
    ('duplicate_bytes', 'duplicate_study_bytes'), ('missing_reference', 'four_references'),
    ('unknown_enrolled', 'unknown_only'), ('absent_present', 'declared_role'),
    ('one_person_group', 'group_requires'), ('control_in_gallery', 'controls_must_be_distinct')])
def test_input_contract_rejects(study_input, mutation, reason):
    _, original = study_input
    d = copy.deepcopy(original)
    if mutation == 'missing_label': d['labels'].pop()
    elif mutation == 'duplicate_label': d['labels'][-1] = d['labels'][0]
    elif mutation == 'string_bool': d['labels'][0]['present'] = 'true'
    elif mutation == 'wrong_presence': d['labels'][0]['present'] = False
    elif mutation == 'unknown_identity': d['assets'][4]['depicted_person_ids'].append('OUTSIDER')
    elif mutation == 'capture_reuse': d['assets'][4]['capture_group_id'] = d['assets'][3]['capture_group_id']
    elif mutation == 'duplicate_bytes': d['assets'][4]['sha256'] = d['assets'][0]['sha256']
    elif mutation == 'missing_reference': d['assets'].pop(0)
    elif mutation == 'unknown_enrolled': d['assets'][-1]['depicted_person_ids'] = ['A']
    elif mutation == 'one_person_group': d['assets'][4]['depicted_person_ids'] = ['A']
    elif mutation == 'control_in_gallery': d['controls']['no_face'] = {k: d['assets'][4][k] for k in ('path', 'sha256')}
    elif mutation == 'absent_present':
        d['assets'][4]['depicted_person_ids'].append('D')
        next(r for r in d['labels'] if r['person_id'] == 'D' and r['asset_id'] == 'p0')['present'] = True
    with pytest.raises(ValueError, match=reason): Challenge.model_validate(d)


def test_wrong_missed_links_and_denominators(study_input):
    _, d = study_input
    s = Challenge.model_validate(d)
    result = compare_galleries(s, [('A', 'p0'), ('D', 'p0'), ('A', 'p18')], [{'stage': 'import', 'asset_id': 'p1'}], observations=observed_galleries(s))
    assert len(result['wrong_links']) == 2 and len(result['missed_links']) == 29
    assert result['presence_recall'] == 1/30
    assert result['photo_denominator'] == 24 and result['label_denominator'] == 96
    assert not result['passed_pilot_targets']
    assert result['per_person'][0]['presence_recall'] == 1/10
    assert result['processing_failures'] == [{'stage': 'import', 'asset_id': 'p1'}]
    with pytest.raises(ValueError, match='outside_frozen'): compare_galleries(s, [('A', 'alien')], [], observations=observed_galleries(s))


def test_import_failure_stays_in_denominator(six_color_service, study_input, tmp_path):
    service = six_color_service
    inputs, d = study_input
    target = inputs/d['assets'][4]['path']
    target.write_bytes(b'INTENTIONALLY CORRUPT SYNTHETIC PHOTO')
    d['assets'][4]['sha256'] = sha_file(target)
    result = runner.execute(Challenge.model_validate(d), inputs, tmp_path/'out', service)
    assert result['photo_denominator'] == 24 and result['label_denominator'] == 96
    assert len(result['missed_links']) == 2 and result['presence_recall'] == 28/30
    assert any(f.get('asset_id') == 'p0' and f['stage'] == 'import' for f in result['processing_failures'])
    assert not result['controls']['passed']  # Duplicate of corrupt input also fails; never invented pass.


def test_synthetic_rejected_by_real_preflight(study_input):
    with pytest.raises(ValueError, match='rejects_synthetic'): runner.preflight(study_input[0])


@pytest.mark.parametrize('change', ['bytes', 'traversal', 'empty_evidence'])
def test_actual_input_verification(study_input, change):
    root, d = study_input
    if change == 'bytes': (root/d['assets'][4]['path']).write_bytes(b'changed')
    elif change == 'traversal': d['assets'][4]['path'] = '../escape'
    else:
        (root/'SYNTHETIC.txt').write_bytes(b'')
        empty_hash = hashlib.sha256(b'').hexdigest()
        for key in ('permitted_use', 'annotation_record', 'capture_independence_record', 'fresh_capture_record'):
            d[key]['sha256'] = empty_hash
    with pytest.raises(ValueError): Challenge.model_validate(d).verify_files(root)


def tree(root):
    return {str(p.relative_to(root)): (sha_file(p), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('command', ['direct', 'preflight', 'all'])
def test_frozen_preflight_and_partial_all_preserve_every_file(tmp_path, monkeypatch, command):
    root = tmp_path/'historical'
    root.mkdir()
    for name in ('freeze.json', 'preflight.json', 'calibration-result.json', 'probe.started.json'):
        (root/name).write_text('{"sentinel":"temporary synthetic historical evidence"}')
    before = tree(root)
    monkeypatch.setattr(studio_study.subprocess, 'run', Mock(side_effect=AssertionError('no subprocess allowed')))
    if command == 'direct':
        call = lambda: studio_study.preflight(tmp_path/'missing-kit', root)
    else:
        monkeypatch.setattr(studio_study.sys, 'argv', ['study', command, '--root', str(root), '--kit', str(tmp_path/'missing-kit')])
        call = studio_study.main
    with pytest.raises(ValueError, match='frozen_experiment_preflight'): call()
    assert tree(root) == before
    studio_study.subprocess.run.assert_not_called()


@pytest.fixture
def frozen_challenge(study_input, tmp_path, monkeypatch):
    inputs, d = study_input
    s = Challenge.model_validate(d)
    artifacts = tmp_path/'artifacts'
    artifacts.mkdir()
    receipt = artifacts/'receipt.json'; receipt.write_text('SYNTHETIC TEST DOUBLE, NOT PARITY')
    fake = Mock(namespace='TEST-ONLY', parity_path=receipt)
    monkeypatch.setattr(runner, 'provider', Mock(return_value=fake))
    monkeypatch.setattr(runner, 'preflight', lambda path: (s, {'study.json': sha_file(inputs/'study.json')}))
    monkeypatch.setattr(runner, 'artifact_inventory', lambda path: {'receipt.json': sha_file(receipt)})
    root = tmp_path/'challenge'
    runner.freeze(inputs, artifacts, root)
    runner.provider.reset_mock()
    return root, inputs, artifacts


@pytest.mark.parametrize('change', ['code', 'policy', 'labels', 'artifact', 'schema', 'freeze'])
def test_freeze_changes_block_before_inference(frozen_challenge, monkeypatch, change):
    root, inputs, artifacts = frozen_challenge
    if change == 'code': monkeypatch.setattr(runner, 'source_inventory', lambda: {'changed': 'code'})
    elif change == 'policy':
        p = runner.load(root/'policy.json'); p['margin'] = .1; runner.save(root, 'policy.json', p)
    elif change == 'labels': (inputs/'study.json').write_text('changed')
    elif change == 'artifact': (artifacts/'receipt.json').write_text('changed')
    else:
        f = runner.load(root/'freeze.json')
        if change == 'schema':
            f['manifest']['schema'] = 'historical-c0'; f['freeze_id'] = digest_json(f['manifest'])
        else: f['freeze_id'] = '0'*64
        runner.save(root, 'freeze.json', f)
    with pytest.raises(ValueError): runner.run(root)
    runner.provider.assert_not_called()
    assert not (root/'challenge.started.json').exists()


def test_partial_run_refuses_replay_and_completed_run_read_only(frozen_challenge):
    root, _, _ = frozen_challenge
    runner.stage_start(root, 'challenge')
    before = tree(root)
    with pytest.raises(ValueError, match='partial_evidence_preserved'): runner.run(root)
    assert tree(root) == before
    runner.save(root, 'result.json', {'status': 'SYNTHETIC saved output'})
    before = tree(root)
    assert runner.run(root)['status'] == 'SYNTHETIC saved output'
    assert tree(root) == before
    runner.provider.assert_not_called()


def test_no_overwrite_existing_run(frozen_challenge):
    root, inputs, artifacts = frozen_challenge
    before = tree(root)
    with pytest.raises(ValueError, match='existing_evidence_preserved'): runner.freeze(inputs, artifacts, root)
    assert tree(root) == before
    runner.provider.assert_not_called()


@pytest.fixture
def six_color_service(study_input, tmp_path, monkeypatch):
    """Six orthogonal test-only color vectors exercise 4-enrolled/2-unknown fixed-policy logic."""
    import numpy as np

    from scripts import make_fixtures
    from server.config import OperatingPoint, Settings
    from server.providers import SyntheticProvider, unit
    from server.service import Service

    extra = {'yellow': (240, 240, 0), 'magenta': (240, 0, 240), 'cyan': (0, 240, 240)}
    monkeypatch.setattr(make_fixtures, 'COLORS', {**make_fixtures.COLORS, **extra})
    colors = list(make_fixtures.COLORS.values())
    class SixColorProvider(SyntheticProvider):
        def analyze(self, rgb):
            observations = super().analyze(rgb)
            for obs in observations:
                if obs.vector is not None:
                    index = min(range(6), key=lambda i: np.linalg.norm(obs.vector-unit(colors[i])))
                    obs.vector = np.eye(6, dtype=np.float32)[index]
            return observations
    inputs, data = study_input
    for a in data['assets']:
        if a['asset_id'] == 'ref-D' or a['kind'] == 'unknown_only':
            color = 'yellow' if a['asset_id'] == 'ref-D' else 'magenta' if a['depicted_person_ids'] == ['U'] else 'cyan'
            info = write(inputs, a['path'], fixture([color], variant=200+data['assets'].index(a)))
            a.update(info)
    op = OperatingPoint.model_validate({**runner.POLICY, 'provider': 'synthetic',
                                       'note': 'SYNTHETIC SIX COLOR TEST DOUBLE. No natural photographs.'})
    policy = tmp_path/'synthetic-policy.json'; policy.write_text(op.model_dump_json())
    provider = SixColorProvider(op)
    provider.namespace = 'SYNTHETIC-six-orthogonal-colors-test-only'
    service = Service(Settings(data_dir=tmp_path/'six-color-runtime', config_path=policy), provider=provider)
    return service


def test_six_identity_fixed_policy_success(study_input, tmp_path, six_color_service):
    inputs, data = study_input
    result = runner.execute(Challenge.model_validate(data), inputs, tmp_path/'out', six_color_service)
    assert result['pair_delivery_success']
    assert all(result['pair_delivery'][p]['passed'] for p in ('A+B', 'A+C', 'B+C'))
    assert result['challenge_succeeded'] and result['design_executed']
    assert not result['processing_failures']
    assert result['correct_links'] == 30 and not result['wrong_links'] and not result['missed_links']
    assert result['evidence_kind'] == 'synthetic_test_only'
    assert result['shared_photo_retrieval'] == dict.fromkeys('ABC', True)


def test_terminal_processing_failure_is_reported(six_color_service, study_input, tmp_path, monkeypatch):
    from server.providers import ProviderError

    service = six_color_service
    inputs, data = study_input
    analyze = service.provider.analyze
    def fail_groups(rgb):
        # All synthetic group fixtures contain two colored rectangles.
        observations = analyze(rgb)
        if len(observations) >= 2:
            raise ProviderError('synthetic_injected_group_processing_failure')
        return observations
    monkeypatch.setattr(service.provider, 'analyze', fail_groups)
    result = runner.execute(Challenge.model_validate(data), inputs, tmp_path/'out', service)
    assert len(result['missed_links']) == 24
    assert len([f for f in result['processing_failures'] if f['stage'] == 'processing']) == 12
    assert result['presence_recall'] == 6/30
    assert not result['passed_pilot_targets']
    assert result['photo_denominator'] == 24 and result['label_denominator'] == 96


@pytest.mark.parametrize('value', [None, False, 1, 'true'])
def test_qualification_requires_explicit_review(study_input, value):
    root, d = study_input
    # Schema gate test only: all payload photographs remain labelled synthetic fixture bytes.
    d['input_kind'] = 'natural_photographs'
    (root/'study.json').write_text(json.dumps(d))
    review = {key: True for key in runner.Qualification.model_fields}
    review.update(study_sha256=sha_file(root/'study.json'), reviewed_by='SYNTHETIC TEST REVIEWER',
                  reviewed_at='SYNTHETIC TEST DATE', scope='one_private_local_c1_challenge')
    review['independent_reference_captures'] = value
    (root/'qualification.json').write_text(json.dumps(review))
    with pytest.raises(ValueError, match='explicit_boolean'): runner.preflight(root)


def test_dynamic_studio_extras_no_12_36_dependency():
    mapping = {'people': {'A': 'app-A'}, 'photos': {'p': 'app-p'}, 'enrollments': []}
    study = {'assets': [{'asset_id': 'p', 'person_id': 'A', 'cohort': 'probe', 'kind': 'gallery', 'capture_group_id': 'g'}]}
    cohort = {'cohort': 'probe', 'unknown_person_ids': [], 'absent_enrolled_person_ids': []}
    result = studio_study.extras({}, [], mapping, study, cohort)
    assert result['photo_denominator'] == result['label_denominator'] == 1
    assert result['unknown_only_photo_false_release_rate'] is None


def test_startup_failure_consumes_attempt_and_records_failure(frozen_challenge):
    root, _, _ = frozen_challenge
    runner.provider.side_effect = RuntimeError('SYNTHETIC injected startup failure')
    with pytest.raises(RuntimeError, match='injected startup'): runner.run(root)
    assert (root/'challenge.started.json').exists()
    assert runner.load(root/'failure.json')['status'] == 'failed_no_automatic_replay'
    before = tree(root)
    runner.provider.reset_mock()
    with pytest.raises(ValueError, match='partial_evidence_preserved'): runner.run(root)
    runner.provider.assert_not_called()
    assert tree(root) == before


def test_worker_timeout_exports_incomplete_without_controls(service, study_input, tmp_path, monkeypatch):
    inputs, data = study_input
    monkeypatch.setattr(runner, 'drain', Mock(side_effect=TimeoutError('SYNTHETIC timeout')))
    result = runner.execute(Challenge.model_validate(data), inputs, tmp_path/'out', service)
    assert result['status'] == 'incomplete_worker_timeout'
    assert not result['challenge_succeeded'] and not result['design_executed']
    assert not result['actual_links'] and len(result['missed_links']) == 30
    assert result['photo_denominator'] == 24 and result['label_denominator'] == 96
    assert not (tmp_path/'out/controls-result.json').exists()
    assert any(f.get('asset_id') == 'p0' and f['stage'] == 'processing' for f in result['processing_failures'])


def test_scaffold_is_incomplete_and_never_overwrites(tmp_path):
    from scripts.make_c1_template import template
    root = tmp_path/'scaffold'
    template(root)
    d = runner.load(root/'study.draft.json')
    assert len(d['assets']) == 28 and len(d['labels']) == 96
    assert all(r['present'] is None for r in d['labels'])
    assert not (root/'study.json').exists()
    with pytest.raises(ValueError): Challenge.model_validate(d)
    before = tree(root)
    with pytest.raises(FileExistsError): template(root)
    assert tree(root) == before
