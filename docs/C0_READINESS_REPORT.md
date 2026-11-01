# C0 readiness report — 1 November 2026

C0 engineering and numerical gates passed; the supplied bounded studio experiment also completed. The default app remains synthetic and shipped real-model registries/releases remain disabled. See [STUDIO_STUDY_REPORT.md](STUDIO_STUDY_REPORT.md) for separate real-photo results.

Local branch: `poc/c0-studio-study`. Executed source/test commit: `888e79db463d977e48c9bb2e8a14d5d5ae16795f`, based on inspected `b895af6a9e22101a5e9b5ab6e1c3aad32e007847`. Every server/script/runtime-lock file in the freeze matches this source commit. Documentation is committed separately after measurement. No push, merge, deployment, paid service or reset of prior app data was performed.

## Engineering changes and focused verification

| Reviewed defect | Implemented behavior / regression evidence |
|---|---|
| Numeric placeholder was not a release gate | Explicit real `release_enabled=false`; worker final publication, guest sessions, authorization and gallery access enforce it. Single identical-vector enrollment still accepts numerically but publishes nothing under the blocked real policy. Raw diagnostics remain available. |
| Weak labels and incomplete denominators | Strict shared Evaluation/Label models; actual JSON booleans/null, status consistency, exact full matrix, source/app mappings, asset/reference hashes, split/capture rules. Unknown truth withholds whole recall; malformed/missing matrix is refused; failed processing stays in denominator. Counts occur after work; excluded predictions are exposed. CSV conversion uses the same Label model. |
| Stale enrollment templates | Separate count/consistency/aggregation policy identity and actual reference-byte hashes. Tests cover 1→3 and consistency changes, blocked old sessions/releases, re-enrollment and reused gallery vectors. |
| N×roster obsolete matches / expiry amplification | Latest per-photo MATCH supersedes pending/retry/running older revisions. PROCESS survives roster changes. Twenty enrollments over five processed photos leave five runnable matches and 95 superseded entries. Whole-event expiry precedes participant expiry; no added jobs. Stale publication cannot erase a newer gallery. UI/report/evaluator understand superseded work. |
| Rounded coordinates / stale synthetic cache | Separate actual x/y scales; minimum resize dimension one; deterministic odd/1×10000/10000×1 geometry tests. Synthetic namespace binds observation settings and code. Existing orientation tests remain passing. |
| Weak parity provenance / broadcasting | Code/model/contract/runtime-bound representations; independent pinned reference process; strict arrays, corpus/source hashes and checker/generator/schema identity. Missing/stale/malformed evidence fails closed. |
| Dataset basis indistinguishable from new consent | Narrow `published_dataset_study_use_basis` event and authorization-record types; explicit publisher citation. Ordinary flows keep their existing participant-consent default. No new signatures claimed. Legacy table/purpose names remain for migration compatibility; explicit basis fields carry the distinction. |

## Actual checks

| Command | Outcome |
|---|---|
| `.bootstrap/bin/uv sync --group reference` | Installed locked numerical-reference dependencies; uv.lock updated. |
| `.venv/bin/pytest -q --junitxml=var/c0-test-results.xml` | 63 passed in 4.80 s, one Starlette/httpx deprecation warning. |
| `.venv/bin/ruff check server scripts tests` | Passed. |
| `.venv/bin/python -m compileall -q server scripts tests` | Passed. |
| `npm --prefix web run build` | TypeScript and Vite build passed (30 modules). |
| `npm --prefix web run test:browser` | 3 Chromium tests passed in 17.5 s; populated lifecycle, basic workflow and mobile layout. |
| `FACE_DATA_DIR=var/c0-synthetic .venv/bin/python -m scripts.synthetic_run` | Passed, explicitly synthetic; separate private DB. |
| `.venv/bin/python -m scripts.studio_study preflight` | Kit inventory verified: 42 real JPEGs, 10 people, 2 cohorts, 72 presence rows; 30 portraits selected, 12 optional references unused. |
| Independent parity command below | 8/8 positive cases; 7/7 negative controls; 3/3 same-engine wrapper cases. |
| `.venv/bin/python -m scripts.studio_study all` | Real calibration/freeze/one probe/operational controls completed. |

Browser tests explicitly exercise a shared group photo, duplicates, late enrollment/photos, Not me after retry/restart, withdrawal with queued work and two-event isolation. These remain synthetic assertions. The studio kit has no real group photographs. Tests used their own runtime folders; the prior demo launcher was stopped to free only ports 8017/5177. Unrelated applications on other ports were not touched.

## Independent numerical evidence

The original pinned InsightFace routines execute in `scripts/reference_runner.py` through an isolated subprocess. A supplied CPU session captures the upstream input tensor; expected crops/tensors/embeddings never call application alignment/preprocessing. Source notices and the pinned MIT declaration are retained privately. The two permitted models and actual metadata are listed in [MODELS.md](MODELS.md). No reference model auto-download or FaceAnalysis is used.

| Case | Pixel elements differing | Tensor max absolute error | Embedding cosine | Pass |
|---|---:|---:|---:|---|
| identity | 0 | 5.96046448e-08 | 1.000000000 | True |
| asymmetric | 0 | 5.96046448e-08 | 1.000000000 | True |
| grid | 0 | 5.96046448e-08 | 1.000000000 | True |
| translation | 0 | 5.96046448e-08 | 0.999999940 | True |
| rotation | 0 | 5.96046448e-08 | 0.999999940 | True |
| scale | 0 | 5.96046448e-08 | 1.000000000 | True |
| combined | 0 | 5.96046448e-08 | 1.000000000 | True |
| border | 0 | 5.96046448e-08 | 1.000000000 | True |

Tolerances stayed tensor atol 1e-4 / rtol 1e-5 and embedding cosine ≥0.99999. Raw embedding norms and individual comparisons are retained in the private receipt. Negative controls passed: channel_swap, landmark_swap, omitted_normalization, broadcastable_tensor, nonfinite_embedding, missing_case, stale_implementation_digest.

Official pinned YuNet wrapper vs app detector: 320×320, 479×321 and 176×160 deterministic non-person BGR inputs, zero detections in both paths, exact same-engine output agreement. Geometry injection tests separately exercise coordinate mapping. This is not independent detection accuracy.

### Identities

- Model/pipeline identity: `1e9f8af3b3453432e007c8fd1f9fe98e449074d1ae0ffddc411b29d34ca763b1`.
- Checker identity: `36adfaac874c1311badf695cd035d32117b18552ce0dbc5aaeab71ca882414bb`.
- Corpus manifest SHA-256: `14924e5b32535493bb1584eff3ac9abed17072aa332b0f69422864bc303dc408`.
- Parity receipt SHA-256: `838270ff6c5a284dc64d50969db859e32e9aada5ae3381307f3824b12963b0f4`.
- Aggregate executed code inventory digest: `6516f65cf77df7171baffca02fd17dc3ce44170637c5b476aac4f0d3bed622ca`.
- Pre-commit tracked diff SHA-256: `60148ea23676cc6378c8436e761f4e08ab1213d80d33fe527d8b4752c07e5652`. New files are independently covered by the complete code inventory.

| Pinned reference source | SHA-256 |
|---|---|
| face_align.py | `a8b34ddd06716f5ca7e7501415cbd3789ccbce18db9e557b35e537695290d922` |
| arcface_onnx.py | `2df3524243b8e807b0e4756d98bd3f8fd7456feaf6d04da7502a24a54d74e2bc` |
| onnxruntime_utils.py | `0b5482f03f5f1a37db89569880268b6da090a00263134680f94a8b9eb87bd87f` |
| UPSTREAM-README.md | `1846967d19f2b19845b967e14715c162881e7598360e23ab6646a47c88667758` |
| yunet.py | `8115b70ce52f514958d9df23fded86729880aec02ee38f0ea18feebce360099a` |

Executed pipeline runtime versions: numpy 2.5.4, opencv-python-headless 4.14.0.94, onnxruntime 1.31.1, pillow 12.3.0, pillow-heif 1.8.1. Reference packages are locked in uv.lock, including scikit-image 0.26.0 and ONNX 1.23.2.

## Failures preserved and resolved

- Initial bundle verification failed because extraction added `.DS_Store` and `docs/.DS_Store`. No declared data was missing or altered. Only these metadata files were quarantined from the private copy; original Def Ref stayed untouched. The rerun verified all declared hashes. Evidence: `var/kit-extraction-check.json`.
- Guessed root `LICENSE` and `LICENSE.txt` URLs for the pinned InsightFace revision returned HTTP 404. Repository contents confirmed neither file exists there. The actual pinned README contains the MIT code declaration; it was downloaded and hashed with the original source notices. This does not change the separately sourced fal model terms.
- First independent parity run failed rotation (one pixel element, max difference 1; tensor error 0.00784314) and combined transform (three elements, max difference 8; tensor error 0.0627451). NumPy float64 landmarks/target and expression evaluation differed from upstream float32 mean/variance and warp transform conventions. Matching those conventions resolved the differences with unchanged tolerances. Failed receipt remains in `var/c0-studio/parity/history/`.
- An intermediate test run caught an indentation error introduced during metrics editing; it was fixed before the successful suite. Ruff found and fixed unused imports/style issues. No failed result is counted as a pass.
- Runtime warnings remain: Starlette TestClient/httpx deprecation; upstream scikit-image `estimate` deprecation; Playwright color-environment warning. They did not prevent execution. Upstream code was not silently rewritten to remove the warning.

## Reproduce and limits

```sh
.bootstrap/bin/uv sync --locked --group reference
npm --prefix web ci
.venv/bin/python -m scripts.prepare_c0
FACE_DATA_DIR=var/c0-studio FACE_MODELS=var/c0-studio/registry.json \
  FACE_CONFIG=configs/auraface.uncalibrated.json .venv/bin/python -m scripts.check_parity
.venv/bin/python -m scripts.studio_study preflight
.venv/bin/python -m scripts.studio_study all
```

These are new-run setup commands; keep completed freeze/corpus files intact. Repeating `studio_study all` on the completed directory reads saved stage results rather than repeating probe inference. For only viewing the frozen probe, use the local run command in the studio report. For generic typed label conversion/evaluation see [EVALUATION.md](EVALUATION.md).

No inputs are missing for this supplied study. Remaining claims require other evidence: independent real-event/session captures, authorized group photos and difficult conditions, face-level detection/evidence annotations, predeclared recognisability, larger independent calibration/holdout cohorts, relevant scale/latency/cost measurements, liveness/authentication and production rights review. SFace remains unexecuted and out of scope. No cloud cost, fairness, liveness or wedding/event accuracy is claimed.

Only source, tests, safe configuration examples, lockfiles and sanitized documentation were staged. Photographs, labels/mappings, per-image scores, embeddings, DB/WAL, weights, terms copies, detailed receipts/logs, node_modules and virtual environments stay ignored. The local source commit above contains the exact inference/evaluation code executed; use `git log -2 --oneline` for the documentation follow-up.
