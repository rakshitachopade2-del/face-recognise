"""Download only the two user-authorized pinned models and pinned reference CODE/terms."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from server.media import atomic_write

REFERENCE_REV = "c6c3af7bd2d0a0bf4b78c78437357f3521aa5d52"


def download(url, target, expected=None, size=None):
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = target.with_suffix('.download')
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temporary.replace(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if expected and digest != expected or size and target.stat().st_size != size:
        raise ValueError('artifact_hash_or_size_mismatch:' + target.name)
    return {'url': url, 'sha256': digest, 'size_bytes': target.stat().st_size}


def prepare(kit, root):
    pins = json.loads((kit / 'docs/prior-review/03-Model-Pins.json').read_text())
    registry = json.loads(Path('configs/models.json').read_text())
    evidence = {'models': {}, 'reference_sources': {}, 'project_authorization':
                'User-invoked kit: closed local evaluation under published terms; no vendor letter or production clearance'}
    for model in pins['models']:
        name = model['id']
        evidence['models'][name] = download(model['download_url'], root / 'models' / model['filename'],
                                            model['sha256'], model['size_bytes'])
        for kind in ('license', 'model_card'):
            evidence['models'][name][kind] = download(model[kind + '_url'], root / 'terms' / (name + '-' + kind + '.txt'))
        registry[name].update(revision=model['revision'], sha256=model['sha256'], evaluation_use_status='approved',
                             permission_basis='User-authorized local experiment under pinned published ' + model['published_license'] +
                             ' terms; notices retained in terms/. No bespoke approval or production clearance claimed.',
                             weights_terms=model['license_url'])
    registry['yunet']['contract'].update(input_shape=[1, 3, 640, 640],
                                        runtime_shape='OpenCV 4.x variable input; verified separately')
    paths = {'face_align.py': 'python-package/insightface/utils/face_align.py',
             'arcface_onnx.py': 'python-package/insightface/model_zoo/arcface_onnx.py',
             'onnxruntime_utils.py': 'python-package/insightface/model_zoo/onnxruntime_utils.py',
             'UPSTREAM-README.md': 'README.md'}
    for filename, upstream in paths.items():
        url = f'https://raw.githubusercontent.com/deepinsight/insightface/{REFERENCE_REV}/{upstream}'
        evidence['reference_sources'][filename] = download(url, root / 'reference-code' / filename)
    rev = pins['models'][0]['revision']
    evidence['reference_sources']['yunet.py'] = download(
        f'https://raw.githubusercontent.com/opencv/opencv_zoo/{rev}/models/face_detection_yunet/yunet.py',
        root / 'reference-code/yunet.py')
    for name, payload in (('registry.json', registry), ('artifact-evidence.json', evidence)):
        atomic_write(root, name, json.dumps(payload, indent=2).encode())
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kit', type=Path, default=Path('var/assistant-inputs/face-poc-kit'))
    parser.add_argument('--root', type=Path, default=Path('var/c0-studio'))
    args = parser.parse_args()
    result = prepare(args.kit, args.root)
    print(json.dumps({'status': 'verified', 'models': {k: v['sha256'] for k, v in result['models'].items()}}))
