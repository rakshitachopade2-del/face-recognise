import json

import numpy as np

from server.config import digest_json
from server.identity import CASE_NAMES, PARITY_SCHEMA, checker_identity, sha_file
from server.media import safe_path


def validate_case(case):
    expected = {'landmarks': ((5, 2), np.dtype('float32')),
                'crop': ((112, 112, 3), np.dtype('uint8')),
                'tensor': ((1, 3, 112, 112), np.dtype('float32')),
                'embedding': ((512,), np.dtype('float32')),
                'raw_embedding': ((512,), np.dtype('float32'))}
    rgb = case['rgb']
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 1:
        raise ValueError('invalid_reference_rgb')
    for name, (shape, dtype) in expected.items():
        value = case[name]
        if value.shape != shape or value.dtype != dtype or not np.isfinite(value).all():
            raise ValueError('invalid_reference_' + name)
    if np.linalg.norm(case['raw_embedding']) <= 1e-8 or not np.isclose(np.linalg.norm(case['embedding']), 1, atol=1e-5):
        raise ValueError('invalid_reference_norm')


def validate_corpus(root, manifest):
    if manifest['schema'] != PARITY_SCHEMA or manifest['case_names'] != list(CASE_NAMES):
        raise ValueError('incomplete_reference_case_inventory')
    if manifest['checker_identity'] != checker_identity():
        raise ValueError('stale_reference_generator_or_checker')
    if set(manifest['cases']) != set(CASE_NAMES):
        raise ValueError('missing_reference_case')
    for records in (manifest['cases'], manifest['sources']):
        for entry in records.values():
            if sha_file(safe_path(root, entry['path'])) != entry['sha256']:
                raise ValueError('reference_corpus_or_source_changed')
    return digest_json(manifest)


def validate_receipt(root, path, model_identity):
    if not path.is_file():
        raise ValueError('preprocessing_parity_not_run')
    receipt = json.loads(path.read_text())
    manifest = json.loads(safe_path(root, 'reference-corpus/manifest.json').read_text())
    corpus_digest = validate_corpus(root, manifest)
    if (receipt.get('model_identity') != model_identity or receipt.get('status') != 'passed'
            or receipt.get('corpus_digest') != corpus_digest or receipt.get('checker_identity') != checker_identity()
            or not receipt.get('negative_controls_passed') or not receipt.get('detector_wrapper_passed')):
        raise ValueError('stale_or_failed_parity_receipt')
    return receipt
