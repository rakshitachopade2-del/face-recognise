"""Isolated upstream execution. Deliberately imports no application modules.

Only pinned reference CODE is loaded, with an explicitly supplied CPU session.
No model package, FaceAnalysis, automatic model downloads or person fixtures.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def run(root):
    sources = root / 'reference-code'
    for name in ('upstream', 'upstream.utils', 'upstream.model_zoo'):
        package = types.ModuleType(name)
        package.__path__ = []
        sys.modules[name] = package
    alignment = module('upstream.utils.face_align', sources / 'face_align.py')
    module('upstream.model_zoo.onnxruntime_utils', sources / 'onnxruntime_utils.py')
    arcface = module('upstream.model_zoo.arcface_onnx', sources / 'arcface_onnx.py')
    yunet = module('upstream_yunet', sources / 'yunet.py')
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(root / 'models/glintr100.onnx'), sess_options=options,
                                   providers=['CPUExecutionProvider'])

    class Capture:
        def __getattr__(self, key):
            return getattr(session, key)

        def run(self, names, values):
            self.tensor = next(iter(values.values())).copy()
            return session.run(names, values)

    capture = Capture()
    recognizer = arcface.ArcFaceONNX(str(root / 'models/glintr100.onnx'), session=capture)
    corpus = root / 'reference-corpus'
    corpus.mkdir(exist_ok=True)
    cases = {}
    names = ('identity', 'asymmetric', 'grid', 'translation', 'rotation', 'scale', 'combined', 'border')
    y, x = np.indices((160, 176))
    pattern = np.stack(((x * 7 + y * 3) % 256, (x * 2 + 71) % 256, (y * 5 + 17) % 256), -1).astype('uint8')
    for name in names:
        rgb = pattern.copy()
        landmarks = alignment.arcface_dst.copy()
        if name == 'identity':
            rgb = rgb[:112, :112].copy()
        elif name == 'grid':
            rgb[((x % 11) < 2) | ((y % 13) < 2)] = (255, 15, 60)
        if name in {'translation', 'combined'}:
            landmarks += np.array([23.3, 11.8], dtype='float32')
        if name in {'rotation', 'combined'}:
            angle = np.float32(.23)
            matrix = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]], dtype='float32')
            landmarks = (landmarks - 56) @ matrix.T + 56
        if name in {'scale', 'combined'}:
            landmarks = (landmarks - 56) * np.float32(1.27) + 56
        if name == 'border':
            landmarks -= np.array([34, 43], dtype='float32')
        landmarks = landmarks.astype('float32')
        crop_bgr = alignment.norm_crop(rgb[:, :, ::-1].copy(), landmarks, image_size=112)
        raw = recognizer.get_feat(crop_bgr).reshape(512).astype('float32')
        embedding = (raw / np.linalg.norm(raw)).astype('float32')
        path = corpus / (name + '.npz')
        np.savez(path, rgb=rgb, landmarks=landmarks, crop=crop_bgr[:, :, ::-1], tensor=capture.tensor,
                 raw_embedding=raw, embedding=embedding)
        cases[name] = {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    detector_cases = []
    for width, height in ((320, 320), (479, 321), (176, 160)):
        bgr = cv2.resize(pattern[:, :, ::-1], (width, height))
        detector = yunet.YuNet(modelPath=str(root / 'models/face_detection_yunet_2023mar.onnx'),
                               inputSize=[width, height], confThreshold=.8, nmsThreshold=.3, topK=5000)
        rows = detector.infer(bgr)
        path = corpus / f'detector-{width}-{height}.npz'
        np.savez(path, bgr=bgr, rows=rows)
        detector_cases.append({'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    metadata = {'cases': cases, 'detector_cases': detector_cases, 'normalization':
                {'mean': recognizer.input_mean, 'std': recognizer.input_std},
                'inputs': [{'name': v.name, 'shape': v.shape, 'type': v.type} for v in session.get_inputs()],
                'outputs': [{'name': v.name, 'shape': v.shape, 'type': v.type} for v in session.get_outputs()]}
    (corpus / 'reference-metadata.json').write_text(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root.resolve())
