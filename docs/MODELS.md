# Model boundary and enabling checklist

No model binary was found, downloaded or executed. All real registry entries are **disabled**, and production clearance is **blocked/unresolved**. The checked-in entries are candidate manifests, not approvals. Null revisions and hashes deliberately prevent execution. `docs/dependency-manifest.json` records installed package license declarations; these declarations are not a rights audit.

## Implementation audit for this milestone

| Component | Actual code | Remaining verification/input |
|---|---|---|
| YuNet detector | `RealProvider.__init__` constructs `cv2.FaceDetectorYN`; `_analyze` resizes BGR images, calls detection and maps boxes/landmarks back to oriented images. This is executable integration code, not a dummy detector | Approved exact detector bytes/revision/hash; real landmark-order/coordinate checks, detector recall and difficult-frame experiments |
| AuraFace recognition | The shared `RealProvider` constructs `onnxruntime.InferenceSession`, validates input shape, performs five-point alignment/RGB/NCHW preprocessing, runs the graph and normalizes a 512-dimensional result | Approved recognition-only bytes; exact graph-contract confirmation and independent preprocessing/embedding parity. No inference with AuraFace weights has been run |
| SFace comparison | The same real ONNX adapter selects SFace's registry contract, embedded-normalization path and 128-dimensional output; it does not return fake embeddings | Approved SFace bytes and independent OpenCV reference parity. The ONNX equivalent of the upstream runtime is still unverified |
| Artifact gate | Explicit approval fields, local-only safe paths, allowed artifact names and actual-byte SHA-256 verification are implemented | The manifest revision/hash/permission values are intentionally missing. Startup was rechecked for both recognizers and refused with `model_disabled_missing_approval_or_manifest` |
| Parity checker | `scripts/check_parity.py` compares independent NPZ tensors/embeddings and stores a keyed pass/fail receipt | No independent reference NPZ or passing receipt exists. The current checker is a single-reference comparison, not a broad reference corpus or detector-parity harness |
| Operating point | Acceptance, distinct-person margin, consistency and quality checks are implemented in versioned configuration | Real configurations contain blocking exploratory placeholders; no real calibration or held-out evidence exists |
| Dataset | Import, authorization, enrollment and private-manifest validation code is implemented | Authorized adult photographs, separate references, active consent records, adjudicated labels and split provenance |

There is no missing replacement for a stub in the baseline adapter path. There is also no evidence yet that these candidate contracts execute correctly for the eventual approved artifacts. Graph-specific fixes, if parity or integration fails, remain implementation work after those artifacts arrive. Selective tiled detection, detector-parity automation, calibration sweeps and sealed/load evaluation orchestration are separate unimplemented extensions. Neither source inspection nor synthetic test success grants model approval or establishes recognition accuracy.

| Provider | Selected artifact | Official source | Current status |
|---|---|---|---|
| YuNet | `face_detection_yunet_2023mar.onnx` | [OpenCV Zoo detector](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) | No approved pinned bytes/hash |
| AuraFace v1 | `glintr100.onnx` recognition file only | [fal/AuraFace-v1](https://huggingface.co/fal/AuraFace-v1) | No approved pinned bytes/hash; candidate contract requires parity |
| SFace comparison | `face_recognition_sface_2021dec.onnx` | [OpenCV Zoo recognizer](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) | No approved pinned bytes/hash; candidate contract requires parity |

The [AuraFace publisher card](https://huggingface.co/fal/AuraFace-v1/blob/main/README.md) declares Apache-2.0 and describes commercial intent, but it does not enumerate all training datasets. This is evidence for a review, not this implementation's approval for specific artifact bytes or a production rights conclusion. OpenCV's model-directory terms and upstream provenance also need separate recording. No age, gender, emotion, ethnicity, other auxiliary model or alternate checkpoint is loaded.

To enable a real experiment:

1. Record the approval basis for the intended product-development POC, exact publisher/repository revision, code and weight terms, unresolved training provenance, evaluation status and separate production status. Approval must apply to the detector and recognizer independently. Keep production blocked until its own clearance is resolved.
2. Obtain only the approved detector and one approved recognizer from their explicit pinned official sources, outside this application. Place them under `var/models/` (or `models/` beneath your chosen `FACE_DATA_DIR`). Compute SHA-256 from the actual bytes with `shasum -a 256`. Populate `configs/models.json` or a private copied registry. `artifact` paths are relative to `FACE_DATA_DIR`, cannot escape it, and filenames are restricted to the selected candidates. Do not download the AuraFace bundle.
3. Verify the graph input/output contract and normalization. The adapter implements a five-landmark non-reflecting similarity transform to the 112×112 reference. Candidate AuraFace input is NCHW RGB with external `(x−127.5)/127.5`, unless the approved graph/reference establishes embedded normalization. Candidate SFace input is NCHW RGB with graph-embedded normalization. Invalid, zero or non-finite output fails; valid vectors are unit-normalized float32. Output dimension must match the manifest. These are candidate contracts, not measured parity results.
4. Generate a private independent reference NPZ from the exact upstream reference code, using a consented test image or non-person synthetic color pattern and a valid five-landmark array. Save `rgb` (uint8 HWC), `landmarks` (5×2), `tensor` (1×3×112×112) and unit-normalized `embedding` (D). Do not use this adapter to generate the expected values. Record the upstream revision, graph behavior, command and image authorization.
5. Set both entries' `evaluation_use_status` to `approved` only after the approval record exists. Run the parity command below. It verifies artifact hashes, compares tensors (atol 1e-4 / rtol 1e-5) and embedding cosine (minimum .99999), and persists a pass/fail receipt keyed by artifact/contract/runtime identity. These tolerances check implementation parity, not identity acceptance. A failed check must be investigated, never relabeled as passing.
6. Record an explicitly exploratory acceptance threshold, distinct-person margin, reference consistency rule and quality settings in a versioned config. Real config examples intentionally contain blocking placeholder operating points, not calibrated thresholds. Gather calibration evidence before selecting a provisional or validated operating point. Keep services local regardless of state.
7. Supply adult-authorized event photographs, separate enrollment references, permission records and adjudicated labels. Then run a small end-to-end experiment and inspect errors before considering a larger study.

```sh
FACE_CONFIG=configs/auraface.uncalibrated.json \
  .venv/bin/python -m scripts.check_parity \
  --reference var/parity-reference/independent-reference.npz \
  --reference-source 'exact upstream revision and reference-generation command' \
  --authorization 'permission record or non-person synthetic pattern'

FACE_CONFIG=configs/your-approved-operating-point.json .venv/bin/python -m scripts.dev
```

Runtime uses OpenCV detection and ONNX Runtime CPU recognition with two intra-op threads. That is a reproducible local starting point, not a CPU-only product decision or GPU comparison. Inference is serialized within the API provider; the durable worker is a separate single process. No quantization is applied.

Reference implementation sources inspected: [YuNet wrapper](https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/yunet.py), [OpenCV SFace preprocessing](https://github.com/opencv/opencv/blob/4.x/modules/objdetect/src/face_recognize.cpp), [ArcFace ONNX reference preprocessing](https://github.com/deepinsight/insightface/blob/master/python-package/insightface/model_zoo/arcface_onnx.py), and [ONNX Runtime Python API](https://onnxruntime.ai/docs/api/python/api_summary.html). Reading reference code did not download any InsightFace checkpoint or establish its experimental-use permission.

Real detection, full-frame recall, graph inference, preprocessing parity and wedding-photo accuracy remain **NOT RUN** until these inputs exist. The synthetic alignment unit test only checks the geometric implementation on a non-person image.
