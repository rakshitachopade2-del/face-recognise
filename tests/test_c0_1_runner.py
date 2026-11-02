"""Freeze/stage regressions: temporary literal files, generated rectangles and mocks only."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import studio_study as runner
from scripts.make_fixtures import fixture
from server.config import Settings, digest_json
from server.identity import sha_file
from server.providers import SyntheticProvider
from server.service import Service


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    root, kit = tmp_path/'run', tmp_path/'kit'
    root.mkdir()
    (kit/'dataset').mkdir(parents=True)
    (kit/'provenance').mkdir()
    (root/'reference-corpus').mkdir()
    for p in (root/'registry.json', root/'calibration-result.json', root/'reference-corpus/manifest.json',
              kit/'provenance/permission-basis.json', kit/'labels.json'):
        p.write_text('{}')
    (kit/'photo.txt').write_text('NONPERSON LITERAL INPUT; NO REAL PHOTOGRAPH')
    asset = {'asset_id': 'photo', 'path': 'photo.txt', 'kind': 'gallery', 'sha256': sha_file(kit/'photo.txt')}
    study = {'assets': [asset], 'cohorts': [{'cohort': 'probe', 'label_file': 'labels.json'}]}
    runner.save(kit, 'dataset/study.json', study)
    policy = {'freeze_id': None, 'acceptance': .6, 'margin': .3}
    monkeypatch.setattr(runner, 'code_identity', lambda: {'test-only-code': 'v1'})
    monkeypatch.setattr(runner, 'pipeline_identity', lambda: {'test-only-runtime': 'v1'})
    manifest = {'policy_without_freeze_id': policy, 'code': runner.code_identity(), 'pipeline': runner.pipeline_identity(),
                'registry_sha256': sha_file(root/'registry.json'), 'study_sha256': sha_file(kit/'dataset/study.json'),
                'input_hashes': {'photo': asset['sha256']}, 'label_file_hashes': {'probe': sha_file(kit/'labels.json')},
                'permission_basis_sha256': sha_file(kit/'provenance/permission-basis.json'),
                'reference_corpus_sha256': sha_file(root/'reference-corpus/manifest.json'),
                'calibration_result_sha256': sha_file(root/'calibration-result.json'),
                'parity_receipt_sha256': 'test', 'provider_namespace': 'test'}
    freeze_id = digest_json(manifest)
    runner.save(root, 'freeze.json', {'freeze_id': freeze_id, 'manifest': manifest})
    runner.save(root, 'provisional-config.json', {**policy, 'freeze_id': freeze_id})
    monkeypatch.setattr(runner, 'Service', Mock(side_effect=AssertionError('provider/inference must not start')))
    return root, kit, study


@pytest.mark.parametrize('change', ['code', 'policy', 'registry', 'input', 'labels', 'study', 'permission', 'corpus', 'calibration', 'pipeline'])
def test_changed_frozen_inputs_rejected_before_provider(frozen, monkeypatch, change):
    root, kit, study = frozen
    if change == 'code':
        monkeypatch.setattr(runner, 'code_identity', lambda: {'test-only-code': 'v2'})
    elif change == 'pipeline':
        monkeypatch.setattr(runner, 'pipeline_identity', lambda: {'test-only-runtime': 'v2'})
    else:
        paths = {'policy': root/'provisional-config.json', 'registry': root/'registry.json',
                 'input': kit/'photo.txt', 'labels': kit/'labels.json', 'study': kit/'dataset/study.json',
                 'permission': kit/'provenance/permission-basis.json', 'corpus': root/'reference-corpus/manifest.json',
                 'calibration': root/'calibration-result.json'}
        if change == 'policy':
            config = runner.load(paths[change]); config['margin'] = .1
            paths[change].write_text(json.dumps(config))
        else:
            paths[change].write_text('changed bytes')
    with pytest.raises(ValueError):
        runner.probe(kit, root, study)
    runner.Service.assert_not_called()
    assert not (root/'probe.started.json').exists()


def test_started_incomplete_probe_and_calibration_are_not_replayed(frozen):
    root, kit, study = frozen
    runner.stage_start(root, 'probe')
    runner.stage_start(root, 'calibration')
    with pytest.raises(FileExistsError):
        runner.probe(kit, root, study)
    (root/'calibration-result.json').unlink()  # Fixture supplied a completed calibration for freeze binding.
    with pytest.raises(FileExistsError):
        runner.calibrate(kit, root, study)
    runner.Service.assert_not_called()


@pytest.mark.parametrize('stage', ['probe', 'calibration', 'controls'])
def test_completed_stage_returns_saved_output_without_inference(frozen, stage):
    root, kit, study = frozen
    saved = {'status': 'SYNTHETIC SAVED RESULT ONLY', 'sentinel': 123}
    runner.save(root, stage+'-result.json', saved)
    call = {'probe': runner.probe, 'calibration': runner.calibrate, 'controls': runner.controls}[stage]
    assert call(kit, root, study) == saved
    runner.Service.assert_not_called()


def test_completed_cli_does_not_rewrite_historical_preflight(frozen, monkeypatch):
    root, kit, _ = frozen
    for stage in ('calibration', 'probe', 'controls'):
        runner.save(root, stage+'-result.json', {'status': 'saved synthetic evidence'})
    monkeypatch.setattr(runner, 'preflight', Mock(side_effect=AssertionError('historical preflight rewritten')))
    monkeypatch.setattr(runner.sys, 'argv', ['studio_study', 'all', '--root', str(root), '--kit', str(kit)])
    runner.main()
    runner.preflight.assert_not_called()
    runner.Service.assert_not_called()


def test_calibration_refuses_release_enabled_service_before_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'Service', lambda *a: SimpleNamespace(op=SimpleNamespace(can_release=True)))
    monkeypatch.setattr(runner, 'cohort_run', Mock(side_effect=AssertionError('inference started')))
    with pytest.raises(ValueError, match='release_disabled'):
        runner.calibrate(tmp_path, tmp_path, {})
    runner.cohort_run.assert_not_called()


def test_synthetic_calibration_publishes_nothing_and_raw_precedes_score(tmp_path, monkeypatch):
    root, kit = tmp_path/'run', tmp_path/'kit'
    root.mkdir(); kit.mkdir()
    protocol = 'studio_identity_split_exploratory'
    people = ['A', 'B', 'C']
    assets, references, gallery, labels = [], [], [], []
    for i, (name, color, kind) in enumerate([('A','red','reference'), ('B','green','reference'),
                                            ('C','blue','reference'), ('A','red','gallery'),
                                            ('B','green','gallery'), ('U','blue','gallery')]):
        asset_id = f'{kind}-{name}'
        path = kit/(asset_id+'.png')
        path.write_bytes(fixture([color], variant=i+1))
        assets.append({'asset_id': asset_id, 'path': path.name, 'sha256': sha_file(path), 'person_id': name,
                       'cohort': 'calibration', 'kind': kind, 'capture_group_id': asset_id})
        (references if kind == 'reference' else gallery).append(asset_id)
    for asset in gallery:
        for p in people:
            labels.append({'person_id': p, 'asset_id': asset, 'present': asset == 'gallery-'+p,
                           'recognisable': None, 'annotation_status': 'source_verified', 'label_basis': 'SYNTHETIC literal labels'})
    runner.save(kit, 'labels.json', {'dataset_version': 'synthetic-runner-test', 'evaluated_roster': people, 'labels': labels})
    study = {'dataset_version': 'synthetic-runner-test', 'protocol': protocol, 'assets': assets,
             'cohorts': [{'cohort': 'calibration', 'enrolled_person_ids': people, 'unknown_person_ids': ['U'],
                          'absent_enrolled_person_ids': ['C'], 'default_reference_asset_ids': references,
                          'gallery_asset_ids': gallery, 'label_file': 'labels.json'}]}
    # Real release policy exercised on rectangle vectors, never model/portrait inference.
    provider = SyntheticProvider(Settings().operating_point())
    provider.synthetic = False  # Test-only protocol injection; provider still only accepts MAGIC rectangles.
    actual_service = Service
    services = []
    def service(settings):
        value = actual_service(settings, provider=provider)
        services.append(value)
        return value
    monkeypatch.setattr(runner, 'Service', service)
    # Keep this diagnostic all-abstain so no real freeze is manufactured by the synthetic test.
    monkeypatch.setattr(runner, 'PROCEDURE', {**runner.PROCEDURE, 'acceptance': [1.0], 'margin': [2.0]})
    original_score, original_evaluate = runner.score, runner.evaluate
    calls = []
    def assert_raw():
        raw = runner.load(root/'calibration-raw-before-corrections.json')
        assert raw['released_associations'] == []
        assert len(raw['faces']) == 3
        calls.append('raw exists before scoring')
    def score(*args, **kwargs):
        assert_raw(); return original_score(*args, **kwargs)
    def evaluate(*args, **kwargs):
        assert_raw(); return original_evaluate(*args, **kwargs)
    monkeypatch.setattr(runner, 'score', score)
    monkeypatch.setattr(runner, 'evaluate', evaluate)
    result = runner.calibrate(kit, root, study)
    assert result['status'] == 'no_useful_policy_probe_skipped'
    assert calls and not (root/'freeze.json').exists()
    with services[0].db.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM released_associations').fetchone()[0] == 0


def test_probe_scores_after_raw_snapshot_and_never_rematches(frozen, monkeypatch):
    root, kit, study = frozen
    receipt = root/'test-parity.json'; receipt.write_text('test-only')
    freeze = runner.load(root/'freeze.json')
    freeze['manifest']['parity_receipt_sha256'] = sha_file(receipt)
    freeze['freeze_id'] = digest_json(freeze['manifest'])
    runner.save(root, 'freeze.json', freeze)
    runner.save(root, 'provisional-config.json', {**freeze['manifest']['policy_without_freeze_id'], 'freeze_id': freeze['freeze_id']})
    service = SimpleNamespace(provider=SimpleNamespace(parity_path=receipt), namespace='test')
    monkeypatch.setattr(runner, 'Service', lambda *a: service)
    def cohort(*args):
        runner.save(root, 'probe-raw-before-corrections.json', {'synthetic': True, 'raw': 'frozen'})
        return 'e', {}, {}, {}
    monkeypatch.setattr(runner, 'cohort_run', cohort)
    def evaluate(*args, **kwargs):
        assert runner.load(root/'probe-raw-before-corrections.json')['raw'] == 'frozen'
        assert kwargs['rematch'] is False
        return {'metrics': {}, 'raw_deliveries': []}
    monkeypatch.setattr(runner, 'evaluate', evaluate)
    monkeypatch.setattr(runner, 'extras', lambda *a: {})
    assert runner.probe(kit, root, study)['status'] == 'completed_once_frozen'
