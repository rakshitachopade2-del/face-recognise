"""No downloads. Real inference requires explicit artifact approval and a parity receipt."""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np
import onnxruntime as ort

from server.config import digest_json
from server.media import PREPARATION_VERSION, safe_path

MAGIC = np.array([[70, 65, 67], [69, 80, 79], [67, 83, 89], [78, 84, 72]], dtype=np.uint8)
REFERENCE = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                      [41.5493, 92.3655], [70.7299, 92.2041]], dtype=np.float64)


class ProviderError(ValueError):
    pass


def unit(vector):
    value = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = np.linalg.norm(value)
    if not np.isfinite(value).all() or not np.isfinite(norm) or norm < 1e-8:
        raise ProviderError("invalid_embedding")
    return value / norm


@dataclass
class Observation:
    bbox: list[float]
    quality: dict
    vector: np.ndarray | None
    status: str


class Provider(Protocol):
    namespace: str
    synthetic: bool

    def analyze(self, rgb: np.ndarray) -> list[Observation]: ...


class SyntheticProvider:
    synthetic = True

    def __init__(self, op):
        self.op = op
        self.namespace = "SYNTHETIC-rectangles-v1:" + PREPARATION_VERSION

    def analyze(self, rgb):
        if rgb.shape[1] < 4 or not np.array_equal(rgb[0, :4], MAGIC):
            raise ProviderError("synthetic_fixture_required_use_scripts_make_fixtures")
        mask = ((rgb.max(axis=2) > 50) & (rgb.min(axis=2) < 50)).astype(np.uint8)
        mask[:8] = 0
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        observations = []
        for x, y, w, h, area in stats[1:count]:
            if area < 4:
                continue
            usable = min(w, h) >= self.op.min_face_px
            vector = unit(rgb[y + h // 2, x + w // 2]) if usable else None
            observations.append(Observation([int(x), int(y), int(w), int(h)],
                                            {"synthetic": True, "score": 1.0}, vector,
                                            "usable" if usable else "face_too_small"))
        return observations


def align(rgb, landmarks):
    """Least-squares non-reflecting similarity transform, five landmarks to 112x112."""
    source = np.asarray(landmarks, dtype=np.float64)
    if source.shape != (5, 2) or not np.isfinite(source).all():
        raise ProviderError("invalid_landmarks")
    src_mean, dst_mean = source.mean(0), REFERENCE.mean(0)
    src, dst = source - src_mean, REFERENCE - dst_mean
    variance = (src ** 2).sum() / 5
    if variance < 1e-8:
        raise ProviderError("degenerate_landmarks")
    u, singular, vt = np.linalg.svd(dst.T @ src / 5)
    sign = np.ones(2)
    if np.linalg.det(u @ vt) < 0:
        sign[-1] = -1
    rotation = u @ np.diag(sign) @ vt
    scale = (singular * sign).sum() / variance
    transform = np.column_stack((scale * rotation, dst_mean - scale * rotation @ src_mean))
    return cv2.warpAffine(rgb, transform, (112, 112), flags=cv2.INTER_LINEAR, borderValue=0)


def verified_artifact(entry, root):
    required = ["source", "revision", "artifact", "sha256", "code_terms", "weights_terms",
                "permission_basis", "training_provenance", "production_use_status", "contract"]
    if entry.get("evaluation_use_status") != "approved" or any(not entry.get(k) for k in required):
        raise ProviderError("model_disabled_missing_approval_or_manifest")
    path = safe_path(root, entry["artifact"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise ProviderError("model_artifact_missing_or_hash_mismatch")
    return path


class RealProvider:
    synthetic = False

    def __init__(self, settings, op, require_parity=True):
        registry = json.loads(settings.registry_path.read_text())
        self.op = op
        self.detector_entry = registry["yunet"]
        self.entry = registry[op.provider]
        root = settings.data_dir.resolve()
        for name, entry, expected in (("yunet", self.detector_entry, "face_detection_yunet_2023mar.onnx"),
                                      (op.provider, self.entry, "glintr100.onnx" if op.provider == "auraface"
                                       else "face_recognition_sface_2021dec.onnx")):
            if entry.get("artifact", "").split("/")[-1] != expected:
                raise ProviderError("only_selected_detector_and_recognizer_artifacts_allowed")
        detector_path = verified_artifact(self.detector_entry, root)
        model_path = verified_artifact(self.entry, root)
        contract = self.entry["contract"]
        if (contract.get("input_shape") != [1, 3, 112, 112]
                or contract.get("channel_order") != "RGB"
                or contract.get("alignment") != "five-point-similarity-112-v1"
                or contract.get("normalization") not in {"external-127.5/127.5", "embedded"}):
            raise ProviderError("unsupported_preprocessing_contract")
        self.contract = contract
        self._inference_lock = threading.Lock()
        self.model_identity = digest_json({"detector": self.detector_entry, "recognizer": self.entry,
                                          "preparation": PREPARATION_VERSION,
                                          "opencv": cv2.__version__, "ort": ort.__version__})
        self.namespace = op.provider + ":" + self.model_identity + ":" + digest_json({
            k: getattr(op, k) for k in ("detector_score", "detector_max_side", "min_face_px", "min_blur")})
        self.parity_path = settings.data_dir / "parity" / (self.model_identity + ".json")
        if require_parity:
            if not self.parity_path.is_file():
                raise ProviderError("model_disabled_preprocessing_parity_not_run")
            receipt = json.loads(self.parity_path.read_text())
            if receipt.get("model_identity") != self.model_identity or receipt.get("status") != "passed":
                raise ProviderError("model_disabled_preprocessing_parity_failed")
        self.detector = cv2.FaceDetectorYN.create(str(detector_path), "", (320, 320),
                                                op.detector_score, 0.3, 5000)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(model_path), sess_options=options,
                                            providers=["CPUExecutionProvider"])
        input_node = self.session.get_inputs()[0]
        if len(self.session.get_inputs()) != 1 or input_node.shape[1:] != [3, 112, 112]:
            raise ProviderError("onnx_input_contract_mismatch")
        self.input_name = input_node.name

    def preprocess(self, rgb, landmarks):
        crop = align(rgb, landmarks).astype(np.float32)
        if self.contract["normalization"] == "external-127.5/127.5":
            crop = (crop - 127.5) / 127.5
        return np.ascontiguousarray(crop.transpose(2, 0, 1)[None])

    def embed(self, tensor):
        vector = unit(self.session.run(None, {self.input_name: tensor})[0])
        if vector.size != self.contract["output_dimension"]:
            raise ProviderError("onnx_output_contract_mismatch")
        return vector

    def analyze(self, rgb):
        with self._inference_lock:
            return self._analyze(rgb)

    def _analyze(self, rgb):
        height, width = rgb.shape[:2]
        scale = min(1, self.op.detector_max_side / max(height, width))
        resized = cv2.resize(rgb[:, :, ::-1], (round(width * scale), round(height * scale)))
        self.detector.setInputSize((resized.shape[1], resized.shape[0]))
        _, rows = self.detector.detect(resized)
        result = []
        for row in [] if rows is None else rows:
            bbox = row[:4].astype(float) / scale
            landmarks = row[4:14].reshape(5, 2).astype(float) / scale
            quality = {"score": float(row[14]), "detector_size": list(resized.shape[:2][::-1]),
                       "landmarks": landmarks.tolist(), "blur": None}
            status, vector = "usable", None
            if min(bbox[2:]) < self.op.min_face_px:
                status = "face_too_small"
            elif ((landmarks < 0).any() or (landmarks[:, 0] >= width).any()
                  or (landmarks[:, 1] >= height).any()):
                status = "invalid_landmarks"
            else:
                try:
                    crop = align(rgb, landmarks)
                    quality["blur"] = float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY),
                                                         cv2.CV_64F).var())
                    if quality["blur"] < self.op.min_blur:
                        status = "blur_rejected"
                    else:
                        vector = self.embed(self.preprocess(rgb, landmarks))
                except ProviderError:
                    status = "invalid_alignment_or_embedding"
            result.append(Observation(bbox.tolist(), quality, vector, status))
        return result


def create_provider(settings, op):
    return SyntheticProvider(op) if op.provider == "synthetic" else RealProvider(settings, op)
