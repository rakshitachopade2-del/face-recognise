# Model boundary and verified local artifacts

C0.1 adds a new `independent-nonperson-v3` evidence contract. [C0_1_HARDENING_REPORT.md](C0_1_HARDENING_REPORT.md) records fresh non-person parity in separate storage. Historical C0 receipts are preserved, rejected for the changed code, and never upgraded in place. No C0.1 portrait experiment was performed.

C0 executed **YuNet + AuraFace** on 1 November 2026. These adapters are implemented and now have independent non-person preprocessing evidence and the bounded studio experiment described in [STUDIO_STUDY_REPORT.md](STUDIO_STUDY_REPORT.md). The checked-in registry remains disabled; only the ignored study registry enables the exact user-authorized artifacts. Production clearance remains unresolved. No SFace weights, auxiliary models, demographic models or model bundles were downloaded.

| Artifact | Pinned revision | Actual bytes | SHA-256 |
|---|---|---:|---|
| YuNet `face_detection_yunet_2023mar.onnx` | `48b10fa505aeb51fbd127fc60a5c660040e823b7` | 232589 | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` |
| AuraFace `glintr100.onnx` | `af6d057c9b0ec4071d4c49c80e3539258798b609` | 260694151 | `a7933ea5330113b01c9b60351d8f4c33003f145d8470ac5f0e52ee2effe25c60` |

Sources: [pinned YuNet model](https://media.githubusercontent.com/media/opencv/opencv_zoo/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet/face_detection_yunet_2023mar.onnx), [YuNet MIT terms](https://raw.githubusercontent.com/opencv/opencv_zoo/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet/LICENSE), [pinned AuraFace model](https://huggingface.co/fal/AuraFace-v1/resolve/af6d057c9b0ec4071d4c49c80e3539258798b609/glintr100.onnx), [AuraFace Apache-2.0 terms](https://huggingface.co/fal/AuraFace-v1/raw/af6d057c9b0ec4071d4c49c80e3539258798b609/LICENSE.md). Copies of terms/cards and their hashes are retained privately in `var/c0-studio/terms/` and `artifact-evidence.json`.

The user explicitly authorized these published artifacts for this closed local experiment. That authorization is not a bespoke vendor letter, a completed training-provenance review or production approval. The publisher card does not resolve all training-data provenance or possible overlap with the evaluation dataset.

## Contracts and parity

Actual AuraFace metadata: `data`, float32 `['None',3,112,112]`; output `1333`, float32 `[1,512]`. Upstream graph inspection selected external mean/std 127.5. App preparation is oriented sRGB → five-point similarity alignment → RGB float32 NCHW `(x−127.5)/127.5` → CPU ONNX Runtime → unit-normalized 512-vector. Inference uses two intra-op threads.

The YuNet graph declares `[1,3,640,640]`. OpenCV `FaceDetectorYN` executes variable input sizes; this distinction is explicit in the registry. Detector coordinates map back with the actual rounded horizontal/vertical scales. No detector-recall ground truth was supplied.

Expected crops/tensors/embeddings come from original pinned InsightFace **code**, in a separate isolated Python process, without importing app preprocessing. Revision: `c6c3af7bd2d0a0bf4b78c78437357f3521aa5d52`. See [original alignment](https://raw.githubusercontent.com/deepinsight/insightface/c6c3af7bd2d0a0bf4b78c78437357f3521aa5d52/python-package/insightface/utils/face_align.py), [original ArcFace ONNX code](https://raw.githubusercontent.com/deepinsight/insightface/c6c3af7bd2d0a0bf4b78c78437357f3521aa5d52/python-package/insightface/model_zoo/arcface_onnx.py) and [pinned code-license declaration](https://raw.githubusercontent.com/deepinsight/insightface/c6c3af7bd2d0a0bf4b78c78437357f3521aa5d52/README.md). No InsightFace pretrained checkpoint is used.

Eight deterministic non-person cases pass tensor atol `1e-4` / rtol `1e-5` and embedding cosine ≥ `.99999`. Every aligned pixel matches. Seven negative controls reject channel/landmark swaps, omitted normalization, malformed tensor shape, nonfinite embedding, missing case and stale implementation identity. Original YuNet wrapper comparisons pass on three non-person input sizes. Those same-engine, zero-detection comparisons are wrapping checks, not detection accuracy. Initial failed parity results are retained and explained in [C0_READINESS_REPORT.md](C0_READINESS_REPORT.md).

Representation identity includes inference/preparation code hashes, artifact hashes, contract and runtime dependencies. Parity also binds checker/generator/schema, pinned source hashes and complete corpus hashes. Reference arrays must have exact dtype/shape and finite, nonzero embeddings; malformed arrays cannot pass by broadcasting. This is local reproducibility evidence, not protection against an administrator deliberately forging files.

## Commands

For a new numerical parity directory, from the repository root with the supplied kit in ignored storage (no portrait inference):

```sh
.bootstrap/bin/uv sync --locked --group reference
.venv/bin/python -m scripts.prepare_c0 --root var/c0-1-fresh-parity
FACE_DATA_DIR=var/c0-1-fresh-parity FACE_MODELS=var/c0-1-fresh-parity/registry.json \
  FACE_CONFIG=configs/auraface.uncalibrated.json .venv/bin/python -m scripts.check_parity
```

`all` prepares artifacts and parity for a new run, then calibrates, freezes, probes once and records controls. A completed run returns saved results without repeating probe inference. Preserve its runtime directory; do not regenerate or edit frozen evidence to make a later run appear identical. An interrupted stage remains marked and is not silently replayed. New code or new experiments need separate run storage and an honestly declared new exploratory protocol.

Real shipped configs have `release_enabled=false`. Raw diagnostics can run with no guest releases. Only an explicitly enabled provisional/validated policy with a freeze identity permits release; the studio runner verifies the full frozen manifest before the probe. Default startup remains synthetic. SFace has shared adapter code, but its graph-specific contract and parity are unverified and its model remains disabled; comparison is out of scope.

## C0.1 evidence validation

`configs/reference-sources.json` commits the exact five original source URLs, revisions, sizes and SHA-256 pins. Preparation verifies both cached and downloaded bytes; a mismatch is refused without replacing a cached source. The isolated runner checks every pin before importing reference code and compiles the verified source bytes rather than trusting cached bytecode.

Shared strict schemas require exactly eight named preprocessing cases, seven negative controls, three declared wrapper sizes and all five pinned sources. Each archive has a bound case ID, path and hash. Numeric metrics must be finite; Boolean fields cannot be strings or integers. Fixed-tolerance case decisions and aggregate summaries must agree with complete measurements; a summary flag alone cannot enable a provider. Case norm/shape/dtype checks also run at startup. A final receipt is atomically written only after the stale-identity control completes. Pin-manifest, schema, generator/checker and reference-runtime changes invalidate prior evidence.

This remains a local correctness/reproducibility gate, not signed tamper-proof attestation. The suite is AuraFace-specific and does not establish SFace parity. Preparation and parity commands refuse a directory containing a historical freeze. Never use the old C0 runtime as new-run storage.
