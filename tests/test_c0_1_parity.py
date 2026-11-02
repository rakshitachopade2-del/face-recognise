"""Test-only synthetic evidence; never construct a real provider or load model weights."""
import copy
import hashlib
import io
import json

import numpy as np
import pytest

from scripts import prepare_c0, reference_runner
from server import reference_pins
from server.identity import CASE_NAMES, PARITY_SCHEMA, checker_identity, sha_file
from server.parity import (
    CONTROL_NAMES,
    TOLERANCES,
    WRAPPER_SIZES,
    Receipt,
    validate_corpus,
    validate_payload,
    validate_receipt,
)


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    # Pin substitution is scoped to this test. No real model registry/artifacts exist here.
    root = tmp_path
    (root/'reference-code').mkdir()
    (root/'reference-corpus').mkdir()
    pins, sources, cases, detectors = {}, {}, {}, {}
    for name in reference_pins.SOURCE_NAMES:
        path = root/'reference-code'/name
        path.write_text('SYNTHETIC TEST SOURCE ONLY: '+name)
        pin = {'sha256': sha_file(path), 'size_bytes': path.stat().st_size}
        pins[name] = pin
        sources[name] = {'path': 'reference-code/'+name, 'sha256': pin['sha256']}
    monkeypatch.setattr(reference_pins, 'source_pins', lambda: pins)
    for name in CASE_NAMES:
        path = root/'reference-corpus'/(name+'.npz')
        np.savez(path, case_id=np.array(name), rgb=np.zeros((112,112,3),dtype='uint8'),
                 landmarks=np.zeros((5,2),dtype='float32'), crop=np.zeros((112,112,3),dtype='uint8'),
                 tensor=np.zeros((1,3,112,112),dtype='float32'),
                 raw_embedding=np.ones(512,dtype='float32'),
                 embedding=np.ones(512,dtype='float32')/np.sqrt(np.float32(512)))
        cases[name] = {'case_id': name, 'path': 'reference-corpus/'+name+'.npz', 'sha256': sha_file(path)}
    for name, (w,h) in WRAPPER_SIZES.items():
        path = root/'reference-corpus'/f'detector-{w}-{h}.npz'
        np.savez(path, case_id=np.array(name), bgr=np.zeros((h,w,3),dtype='uint8'), rows=np.empty((0,5),dtype='float32'))
        detectors[name] = {'case_id': name, 'path': str(path.relative_to(root)), 'sha256': sha_file(path)}
    manifest = {'schema_version': PARITY_SCHEMA, 'provider': 'auraface', 'checker_identity': checker_identity(),
                'cases': cases, 'sources': sources, 'detector_cases': detectors, 'scope': 'SYNTHETIC CONTRACT TEST ONLY'}
    corpus_digest = validate_corpus(root, manifest)
    results = {name: {**v, 'passed': True, 'tensor_max_abs_error': 0.0, 'tensor_scaled_error': 0.0,
                      'embedding_cosine': 1.0, 'pixel_max_abs_error': 0, 'pixel_elements_different': 0,
                      'app_raw_norm': 1.0, 'reference_raw_norm': 1.0} for name,v in cases.items()}
    wrappers = {name: {**v, 'passed': True, 'actual_shape': [0,5], 'reference_shape': [0,5],
                       'max_abs_error': 0.0} for name,v in detectors.items()}
    receipt = {'schema_version': PARITY_SCHEMA, 'provider': 'auraface', 'status': 'passed',
               'model_identity': 'a'*64, 'checker_identity': checker_identity(), 'corpus_digest': corpus_digest,
               'cases': results, 'negative_controls': dict.fromkeys(CONTROL_NAMES, True),
               'negative_controls_passed': True, 'detector_wrappers': wrappers,
               'detector_wrapper_passed': True, 'tolerances': TOLERANCES, 'scope': 'SYNTHETIC CONTRACT TEST ONLY'}
    (root/'reference-corpus/manifest.json').write_text(json.dumps(manifest))
    (root/'receipt.json').write_text(json.dumps(receipt))
    return root, manifest, receipt, corpus_digest


def test_complete_synthetic_evidence_passes(evidence):
    root, manifest, receipt, digest = evidence
    assert validate_payload(receipt, manifest, 'a'*64, digest)['status'] == 'passed'
    assert validate_receipt(root, root/'receipt.json', 'a'*64)['status'] == 'passed'


@pytest.mark.parametrize('flag', ['false', 'true', 0, 1])
def test_summary_and_result_flags_are_actual_booleans(evidence, flag):
    _, manifest, receipt, digest = evidence
    for field in ('negative_controls_passed', 'detector_wrapper_passed'):
        with pytest.raises(ValueError):
            validate_payload({**receipt, field: flag}, manifest, 'a'*64, digest)
    for group, name in [('cases', 'identity'), ('detector_wrappers', '320x320')]:
        bad = copy.deepcopy(receipt)
        bad[group][name]['passed'] = flag
        with pytest.raises(ValueError):
            Receipt.model_validate(bad)
    bad = copy.deepcopy(receipt)
    bad['negative_controls']['channel_swap'] = flag
    with pytest.raises(ValueError):
        Receipt.model_validate(bad)


@pytest.mark.parametrize('group,key', [('cases', n) for n in CASE_NAMES] +
                         [('negative_controls', n) for n in CONTROL_NAMES] +
                         [('detector_wrappers', n) for n in WRAPPER_SIZES])
def test_every_required_result_is_required(evidence, group, key):
    _, manifest, receipt, digest = evidence
    del receipt[group][key]
    with pytest.raises(ValueError):
        validate_payload(receipt, manifest, 'a'*64, digest)


@pytest.mark.parametrize('bad_number', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_numeric_evidence_rejected(evidence, bad_number):
    _, manifest, receipt, digest = evidence
    for field in ('tensor_scaled_error', 'tensor_max_abs_error', 'embedding_cosine', 'app_raw_norm', 'reference_raw_norm'):
        bad = copy.deepcopy(receipt)
        bad['cases']['identity'][field] = bad_number
        with pytest.raises(ValueError):
            validate_payload(bad, manifest, 'a'*64, digest)


def test_failures_contradictions_and_stale_identities_rejected(evidence):
    _, manifest, receipt, digest = evidence
    for mutate in (
        lambda r: r['cases']['identity'].update(embedding_cosine=.5),
        lambda r: r['cases']['identity'].update(tensor_scaled_error=.5),
        lambda r: r['cases']['identity'].update(passed=False, embedding_cosine=.5),
        lambda r: r['negative_controls'].update(channel_swap=False),
        lambda r: r['detector_wrappers']['320x320'].update(max_abs_error=1.0),
        lambda r: r.update(checker_identity='0'*64),
        lambda r: r.update(model_identity='0'*64),
        lambda r: r.update(corpus_digest='0'*64),
        lambda r: r['cases']['identity'].update(path='reference-corpus/grid.npz'),
        lambda r: r.update(schema_version='independent-nonperson-v2'),
        lambda r: r.update(provider='sface'),
        lambda r: r.update(tolerances={**TOLERANCES, 'tensor_atol': .1}),
    ):
        bad = copy.deepcopy(receipt)
        mutate(bad)
        with pytest.raises(ValueError):
            validate_payload(bad, manifest, 'a'*64, digest)


def test_corpus_requires_sources_and_unique_bound_cases(evidence):
    root, manifest, _, _ = evidence
    for mutate in (
        lambda m: m.update(sources={}),
        lambda m: m['cases'].update(asymmetric=m['cases']['identity']),
        lambda m: m['cases']['asymmetric'].update(sha256=m['cases']['identity']['sha256']),
        lambda m: m['cases']['identity'].update(case_id='grid'),
        lambda m: m['detector_cases'].pop('320x320'),
        lambda m: m.update(checker_identity='0'*64),
    ):
        bad = copy.deepcopy(manifest)
        mutate(bad)
        with pytest.raises(ValueError):
            validate_corpus(root, bad)
    # Even separate paths cannot make the same archive pose as two named cases.
    path = root/'reference-corpus/asymmetric.npz'
    path.write_bytes((root/'reference-corpus/identity.npz').read_bytes())
    manifest['cases']['asymmetric']['sha256'] = sha_file(path)
    with pytest.raises(ValueError):
        validate_corpus(root, manifest)


def test_sources_missing_changed_or_misattributed_fail(evidence):
    root, manifest, _, _ = evidence
    bad = copy.deepcopy(manifest)
    bad['sources']['face_align.py']['sha256'] = '0'*64
    with pytest.raises(ValueError, match='pin_mismatch'):
        validate_corpus(root, bad)
    path = root/'reference-code/face_align.py'
    path.write_text('modified local debugging code')
    with pytest.raises(ValueError, match='pin_mismatch'):
        validate_corpus(root, manifest)
    path.unlink()
    with pytest.raises(ValueError, match='pin_mismatch'):
        validate_corpus(root, manifest)


def test_cached_and_downloaded_source_bytes_are_pinned(tmp_path, monkeypatch):
    expected = b'SYNTHETIC EXPECTED SOURCE'
    digest = hashlib.sha256(expected).hexdigest()
    path = tmp_path/'source.py'
    path.write_bytes(b'SYNTHETIC STALE CACHE')
    monkeypatch.setattr(prepare_c0.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('must not overwrite stale cache'))
    with pytest.raises(ValueError, match='hash_or_size_mismatch'):
        prepare_c0.download('https://example.invalid/pin', path, digest, len(expected))
    assert path.read_bytes() == b'SYNTHETIC STALE CACHE'
    new = tmp_path/'new.py'
    monkeypatch.setattr(prepare_c0.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(b'wrong download'))
    with pytest.raises(ValueError, match='download_hash_or_size_mismatch'):
        prepare_c0.download('https://example.invalid/pin', new, digest, len(expected))
    assert not new.exists()
    monkeypatch.setattr(prepare_c0.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(expected))
    assert prepare_c0.download('https://example.invalid/pin', new, digest, len(expected))['sha256'] == digest


def test_reference_runner_rejects_stale_source_before_import(tmp_path, monkeypatch):
    (tmp_path/'reference-code').mkdir()
    (tmp_path/'reference-code/face_align.py').write_text('SYNTHETIC STALE CACHE')
    monkeypatch.setattr(reference_runner, 'module', lambda *a: pytest.fail('unverified reference executed'))
    with pytest.raises(ValueError, match='pin_mismatch'):
        reference_runner.run(tmp_path)


def test_checker_publishes_only_after_complete_identity_control(evidence, monkeypatch):
    from types import SimpleNamespace

    from scripts import check_parity
    root, manifest, receipt, _ = evidence
    metadata = {'cases': manifest['cases'], 'detector_cases': list(manifest['detector_cases'].values())}
    (root/'reference-corpus/reference-metadata.json').write_text(json.dumps(metadata))
    monkeypatch.setattr(check_parity.subprocess, 'run', lambda *a, **k: None)
    fake = SimpleNamespace(model_identity='a'*64, parity_path=root/'parity/final.json',
                           detector=SimpleNamespace(setInputSize=lambda size: None, detect=lambda bgr: (None, None)))
    monkeypatch.setattr(check_parity, 'RealProvider', lambda *a, **k: fake)
    counter = 0
    fields = {'case_id', 'path', 'sha256'}
    def compare(*args):
        nonlocal counter
        counter += 1
        if counter > 8:
            raise ValueError('synthetic negative rejected')
        return {k:v for k,v in receipt['cases'][CASE_NAMES[counter-1]].items() if k not in fields}
    monkeypatch.setattr(check_parity, 'compare', compare)
    tensor = SimpleNamespace(shape=SimpleNamespace(dim=[SimpleNamespace(dim_value=n) for n in (1,3,640,640)]))
    graph = SimpleNamespace(input=[SimpleNamespace(type=SimpleNamespace(tensor_type=tensor))])
    monkeypatch.setattr(check_parity.onnx, 'load', lambda *a: SimpleNamespace(graph=graph))
    identity_control_ran = False
    actual_validate = check_parity.validate_payload
    def validate(payload, corpus, model_id, digest):
        nonlocal identity_control_ran
        if model_id == '0'*64:
            identity_control_ran = True
        return actual_validate(payload, corpus, model_id, digest)
    monkeypatch.setattr(check_parity, 'validate_payload', validate)
    writes = []
    actual_write = check_parity.atomic_write
    def write(root, key, value):
        if key.startswith('parity/'):
            assert identity_control_ran
            validated = Receipt.model_validate_json(value)
            assert set(validated.negative_controls) == set(CONTROL_NAMES)
            assert all(validated.negative_controls.values())
            writes.append(key)
        return actual_write(root, key, value)
    monkeypatch.setattr(check_parity, 'atomic_write', write)
    settings = SimpleNamespace(data_dir=root, operating_point=lambda: SimpleNamespace(provider='auraface'))
    assert check_parity.run(settings)['status'] == 'passed'
    assert writes[0] == 'parity/final.json'
    assert len(writes) == 2  # Exactly one final write and one immutable history copy.
