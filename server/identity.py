"""Code-bound representation and numerical-evidence identities (not tamper-proof attestation)."""
import hashlib
import importlib.metadata
from pathlib import Path

from server.config import ROOT, digest_json

CASE_NAMES = ('identity', 'asymmetric', 'grid', 'translation', 'rotation', 'scale', 'combined', 'border')
PARITY_SCHEMA = 'independent-nonperson-v2'


def sha_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pipeline_identity():
    return {'code': {name: sha_file(ROOT / 'server' / name) for name in
                     ('providers.py', 'media.py', 'identity.py', 'parity.py')},
            'runtime': {name: importlib.metadata.version(name) for name in
                        ('numpy', 'opencv-python-headless', 'onnxruntime', 'pillow', 'pillow-heif')}}


def checker_identity():
    return digest_json({'schema': PARITY_SCHEMA,
                        'checker': sha_file(ROOT / 'scripts/check_parity.py'),
                        'generator': sha_file(ROOT / 'scripts/reference_runner.py'),
                        'reference_runtime': {p: importlib.metadata.version(p) for p in ('scikit-image', 'onnx')}})
