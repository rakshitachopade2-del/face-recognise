"""Independent pinned-code non-person parity gate; never reads portrait fixtures."""
import copy
import json
import subprocess
import sys
import time

import numpy as np
import onnx

from server.config import ROOT, Settings
from server.identity import CASE_NAMES, PARITY_SCHEMA, checker_identity, sha_file
from server.media import atomic_write
from server.parity import validate_case, validate_corpus, validate_receipt
from server.providers import RealProvider, align


def compare(provider, case):
    validate_case(case)
    crop = align(case['rgb'], case['landmarks'])
    tensor = provider.preprocess(case['rgb'], case['landmarks'])
    raw = provider.session.run(None, {provider.input_name: tensor})[0].reshape(512)
    embedding = provider.embed(tensor)
    cosine = float(embedding @ case['embedding'])
    passed = bool(np.allclose(tensor, case['tensor'], atol=1e-4, rtol=1e-5) and cosine >= .99999)
    return {'passed': passed, 'tensor_max_abs_error': float(np.max(np.abs(tensor - case['tensor']))),
            'embedding_cosine': cosine, 'pixel_max_abs_error': int(np.abs(crop.astype(int)-case['crop']).max()),
            'pixel_elements_different': int(np.count_nonzero(crop != case['crop'])),
            'app_raw_norm': float(np.linalg.norm(raw)), 'reference_raw_norm': float(np.linalg.norm(case['raw_embedding']))}


def main():
    settings = Settings.environment()
    root = settings.data_dir
    subprocess.run([sys.executable, '-I', str(ROOT / 'scripts/reference_runner.py'), '--root', str(root)], check=True)
    metadata = json.loads((root / 'reference-corpus/reference-metadata.json').read_text())
    sources = {p.name: {'path': str(p.relative_to(root)), 'sha256': sha_file(p)}
               for p in (root / 'reference-code').iterdir() if p.is_file()}
    sources.update({f'detector-{i}': value for i, value in enumerate(metadata['detector_cases'])})
    manifest = {'schema': PARITY_SCHEMA, 'case_names': list(CASE_NAMES), 'checker_identity': checker_identity(),
                'cases': metadata['cases'], 'sources': sources, 'scope': 'Deterministic non-person numerical patterns'}
    atomic_write(root, 'reference-corpus/manifest.json', json.dumps(manifest, indent=2).encode())
    corpus_digest = validate_corpus(root, manifest)
    provider = RealProvider(settings, settings.operating_point(), require_parity=False)
    cases = {}
    for name, entry in manifest['cases'].items():
        with np.load(root / entry['path'], allow_pickle=False) as data:
            cases[name] = {k: data[k] for k in data.files}
    results = {name: compare(provider, case) for name, case in cases.items()}
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
    wrappers = []
    for entry in metadata['detector_cases']:
        with np.load(root / entry['path'], allow_pickle=False) as data:
            height, width = data['bgr'].shape[:2]
            provider.detector.setInputSize((width, height))
            _, rows = provider.detector.detect(data['bgr'])
            actual = np.empty((0, 5)) if rows is None else rows
            wrappers.append({'size': [width, height], 'rows': len(actual),
                             'passed': actual.shape == data['rows'].shape and bool(np.array_equal(actual, data['rows']))})
    detector_graph = onnx.load(str(root / 'models/face_detection_yunet_2023mar.onnx'))
    metadata['detector_graph_shape'] = [d.dim_value for d in detector_graph.graph.input[0].type.tensor_type.shape.dim]
    receipt = {'status': 'passed' if all(x['passed'] for x in results.values()) else 'failed',
               'model_identity': provider.model_identity, 'checker_identity': checker_identity(),
               'corpus_digest': corpus_digest, 'cases': results, 'metadata': metadata,
               'negative_controls': controls, 'negative_controls_passed': all(controls.values()),
               'detector_wrapper_passed': all(x['passed'] for x in wrappers), 'detector_wrappers': wrappers,
               'tolerances': {'tensor_atol': 1e-4, 'tensor_rtol': 1e-5, 'cosine_min': .99999},
               'scope': 'Non-person preprocessing parity and same-engine detector wrapping; not detection or recognition accuracy'}
    key = str(provider.parity_path.relative_to(root))
    atomic_write(root, key, json.dumps(receipt, indent=2).encode())
    try:
        validate_receipt(root, provider.parity_path, 'stale-implementation-digest')
        controls['stale_implementation_digest'] = False
    except ValueError:
        controls['stale_implementation_digest'] = True
    receipt['negative_controls_passed'] = all(controls.values())
    if not receipt['negative_controls_passed'] or not receipt['detector_wrapper_passed']:
        receipt['status'] = 'failed'
    atomic_write(root, key, json.dumps(receipt, indent=2).encode())
    atomic_write(root, f'parity/history/{time.time_ns()}.json', json.dumps(receipt, indent=2).encode())
    print(json.dumps({'status': receipt['status'], 'cases': results, 'negative_controls': controls, 'wrappers': wrappers}))
    raise SystemExit(0 if receipt['status'] == 'passed' else 1)


if __name__ == '__main__':
    main()
