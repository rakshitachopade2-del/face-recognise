"""Independent pinned-code non-person parity gate; never reads portrait fixtures."""
import copy
import json
import subprocess
import sys
import time

import numpy as np
import onnx

from server.config import ROOT, Settings
from server.identity import PARITY_SCHEMA, checker_identity
from server.media import atomic_write
from server.parity import TOLERANCES, Receipt, validate_case, validate_corpus, validate_payload
from server.providers import RealProvider, align
from server.reference_pins import verify_sources


def compare(provider, case):
    validate_case(case)
    crop = align(case['rgb'], case['landmarks'])
    tensor = provider.preprocess(case['rgb'], case['landmarks'])
    raw = provider.session.run(None, {provider.input_name: tensor})[0].reshape(512)
    embedding = provider.embed(tensor)
    cosine = float(embedding @ case['embedding'])
    scaled_error = float(np.max(np.abs(tensor - case['tensor']) / (1e-4 + 1e-5 * np.abs(case['tensor']))))
    passed = bool(scaled_error <= 1 and cosine >= .99999)
    return {'passed': passed, 'tensor_scaled_error': scaled_error, 'tensor_max_abs_error': float(np.max(np.abs(tensor - case['tensor']))),
            'embedding_cosine': cosine, 'pixel_max_abs_error': int(np.abs(crop.astype(int)-case['crop']).max()),
            'pixel_elements_different': int(np.count_nonzero(crop != case['crop'])),
            'app_raw_norm': float(np.linalg.norm(raw)), 'reference_raw_norm': float(np.linalg.norm(case['raw_embedding']))}


def run(settings):
    root = settings.data_dir
    if (root / 'freeze.json').exists():
        raise ValueError('historical_freeze_present_use_separate_parity_directory')
    if settings.operating_point().provider != 'auraface':
        raise ValueError('this_reference_suite_is_auraface_only')
    pins = verify_sources(root)
    subprocess.run([sys.executable, '-I', str(ROOT / 'scripts/reference_runner.py'), '--root', str(root)], check=True)
    metadata = json.loads((root / 'reference-corpus/reference-metadata.json').read_text())
    sources = {name: {'path': 'reference-code/' + name, 'sha256': pin['sha256']}
               for name, pin in pins.items()}
    manifest = {'schema_version': PARITY_SCHEMA, 'provider': 'auraface', 'checker_identity': checker_identity(),
                'cases': metadata['cases'], 'sources': sources,
                'detector_cases': {v['case_id']: v for v in metadata['detector_cases']},
                'scope': 'Deterministic non-person numerical patterns'}
    atomic_write(root, 'reference-corpus/manifest.json', json.dumps(manifest, indent=2).encode())
    corpus_digest = validate_corpus(root, manifest)
    provider = RealProvider(settings, settings.operating_point(), require_parity=False)
    cases = {}
    for name, entry in manifest['cases'].items():
        with np.load(root / entry['path'], allow_pickle=False) as data:
            cases[name] = {k: data[k] for k in data.files}
    results = {name: {**manifest['cases'][name], **compare(provider, case)} for name, case in cases.items()}
    controls = {}
    for name in ('channel_swap', 'landmark_swap', 'omitted_normalization', 'broadcastable_tensor', 'nonfinite_embedding'):
        bad = copy.deepcopy(cases['asymmetric'])
        if name == 'channel_swap':
            bad['tensor'] = bad['tensor'][:, ::-1].copy()
        elif name == 'landmark_swap':
            bad['landmarks'][[0, 1]] = bad['landmarks'][[1, 0]]
        elif name == 'omitted_normalization':
            bad['tensor'] = (bad['tensor'] * 127.5 + 127.5).astype('float32')
        elif name == 'broadcastable_tensor':
            bad['tensor'] = bad['tensor'][:, :1]
        else:
            bad['embedding'][0] = np.nan
        try:
            controls[name] = not compare(provider, bad)['passed']
        except ValueError:
            controls[name] = True
    missing = copy.deepcopy(manifest)
    del missing['cases']['border']
    try:
        validate_corpus(root, missing)
        controls['missing_case'] = False
    except ValueError:
        controls['missing_case'] = True
    wrappers = {}
    for entry in metadata['detector_cases']:
        with np.load(root / entry['path'], allow_pickle=False) as data:
            height, width = data['bgr'].shape[:2]
            provider.detector.setInputSize((width, height))
            _, rows = provider.detector.detect(data['bgr'])
            actual = np.empty((0, 5)) if rows is None else rows
            same_shape = actual.shape == data['rows'].shape
            error = float(np.max(np.abs(actual-data['rows']))) if same_shape and actual.size else 0.0
            wrappers[entry['case_id']] = {**entry, 'actual_shape': list(actual.shape),
                                          'reference_shape': list(data['rows'].shape), 'max_abs_error': error,
                                          'passed': same_shape and error == 0}
    detector_graph = onnx.load(str(root / 'models/face_detection_yunet_2023mar.onnx'))
    metadata['detector_graph_shape'] = [d.dim_value for d in detector_graph.graph.input[0].type.tensor_type.shape.dim]
    # The final identity control uses a complete in-memory positive candidate.
    # No receipt is published until the real control result replaces this placeholder.
    controls['stale_implementation_digest'] = True
    receipt = {'schema_version': PARITY_SCHEMA, 'provider': 'auraface',
               'status': 'passed', 'model_identity': provider.model_identity,
               'checker_identity': checker_identity(), 'corpus_digest': corpus_digest, 'cases': results,
               'negative_controls': controls, 'negative_controls_passed': all(controls.values()),
               'detector_wrapper_passed': all(x['passed'] for x in wrappers.values()),
               'detector_wrappers': wrappers, 'tolerances': TOLERANCES,
               'scope': 'Non-person preprocessing and same-engine detector wrapping, not recognition accuracy'}
    receipt['status'] = ('passed' if all(x['passed'] for x in results.values())
                         and receipt['negative_controls_passed'] and receipt['detector_wrapper_passed'] else 'failed')
    # Identity rejection is meaningful only after the exact positive payload validates.
    if receipt['status'] == 'passed':
        validate_payload(receipt, manifest, provider.model_identity, corpus_digest)
        try:
            validate_payload(receipt, manifest, '0' * 64, corpus_digest)
            controls['stale_implementation_digest'] = False
        except ValueError:
            controls['stale_implementation_digest'] = True
    else:
        controls['stale_implementation_digest'] = False  # Not established under failing prerequisites.
    receipt['negative_controls_passed'] = all(controls.values())
    if not receipt['negative_controls_passed']:
        receipt['status'] = 'failed'
    Receipt.model_validate(receipt)
    if receipt['status'] == 'passed':
        validate_payload(receipt, manifest, provider.model_identity, corpus_digest)
    key = str(provider.parity_path.relative_to(root))
    atomic_write(root, key, json.dumps(receipt, indent=2).encode())
    atomic_write(root, f'parity/history/{time.time_ns()}.json', json.dumps(receipt, indent=2).encode())
    atomic_write(root, 'reference-corpus/runtime-metadata.json', json.dumps(metadata, indent=2).encode())
    return receipt


def main():
    receipt = run(Settings.environment())
    print(json.dumps({'status': receipt['status'], 'cases': receipt['cases'],
                      'negative_controls': receipt['negative_controls'], 'wrappers': receipt['detector_wrappers']}))
    raise SystemExit(0 if receipt['status'] == 'passed' else 1)


if __name__ == '__main__':
    main()
