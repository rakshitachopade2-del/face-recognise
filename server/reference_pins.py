"""Official byte pins, shared by preparation and numerical-evidence validation."""
import json
from pathlib import Path

from server.config import ROOT
from server.identity import sha_file

PIN_PATH = ROOT / 'configs/reference-sources.json'
SOURCE_NAMES = {'face_align.py', 'arcface_onnx.py', 'onnxruntime_utils.py', 'UPSTREAM-README.md', 'yunet.py'}


def source_pins():
    manifest = json.loads(PIN_PATH.read_text())
    if manifest['version'] != 'c0-1-official-sources-v1' or set(manifest['sources']) != SOURCE_NAMES:
        raise ValueError('invalid_reference_pin_inventory')
    return manifest['sources']


def verify_sources(root):
    pins = source_pins()
    for name, entry in pins.items():
        path = Path(root) / 'reference-code' / name
        if not path.is_file() or sha_file(path) != entry['sha256'] or path.stat().st_size != entry['size_bytes']:
            raise ValueError('reference_source_pin_mismatch:' + name)
    return pins
