# C1 implementation report — complete gallery observation

**2 November 2026. Software verification passed; real execution remains BLOCKED ON DATA.** This bounded revision fixes only the incomplete-gallery-observation defect. Synthetic tests are not natural-photo recognition results.

## Defect and correction

Previously, `execute()` recorded a `Service.gallery` `DomainError` but supplied no rows for that person to the scorer. The scorer interpreted no rows as zero occurrences. If D's gallery was unavailable while A/B/C delivery was perfect, the pair, execution and overall success flags could incorrectly pass.

Every A/B/C/D gallery now has an explicit observation record: `observed` with no error, or `unavailable` with its error. `execute()` collects each gallery once and adds its rows only after the read completes successfully. An observed empty D gallery is valid; an unavailable D gallery is not verified empty. Available deliveries from other people remain preserved.

`compare_galleries()` requires observation metadata for all four enrollees. It rejects missing/invalid records and deliveries attributed to an unavailable gallery. Complete successful observation of all four is necessary for pair-delivery success and every pilot target. `execute()` also requires it for `design_executed`; consequently `challenge_succeeded` cannot pass on incomplete observations. The status is explicitly `incomplete_gallery_observation`, unless the existing worker-timeout status also applies. Gallery failures remain in `processing_failures` as `gallery_access` records.

`actual-guest-galleries-before-corrections.json`, `gallery-comparison.json` and `result.json` export `gallery_observations` and `gallery_observation_complete` alongside available raw deliveries. Results also list `unobserved_people` and `metrics_scope`. Pair occurrence counts and `matrix.actual`/`actual_count` are **null** for unavailable people, not zero/false. CSV contains blank actual/count cells plus `observation_status` and `observation_error`. Successfully read empty galleries still have verified zero counts.

All **24 photographs and 96 label rows** remain in the universe. Whole-study recall is null when observation is incomplete. Available correct/wrong links remain known evidence; `missed_links` includes only confirmed misses in successfully observed galleries. Expected positive links with unknown delivery are explicitly listed as `unobserved_expected_links`; they are not filtered from expected truth or misrepresented as confirmed misses. Per-person actual/wrong/missed lists and recall are null for unavailable people. This preserves uncertainty without changing thresholds or reducing the declared universe.

The original attempt remains consumed. The runner saves an incomplete `result.json` under the already-created start marker. Reinvoking the production command returns that saved result without another provider startup, gallery read, inference or evidence write. No automatic challenge retry was added. Existing partial-crash refusal, duplicate checks, controls, correction guards, freeze binding and historical read-only behavior remain.

## Unchanged requirements and scope

Pair requirements are unchanged: distinct natural photographs with exact enrolled presence {A,B}, {A,C}, {B,C}; U/V may appear, D remains absent and ABC cannot substitute. Each qualifying photo must appear exactly once in both intended guest galleries and zero times in every absent enrolled gallery. The new completeness gate establishes whether those counts were actually observed; it does not alter pair eligibility or numeric criteria.

The entire `POLICY`, `PAIR_REQUIREMENTS` and `PAIR_PROTOCOL` match the preceding pair-coverage ZIP. Acceptance remains **0.6**, margin **0.3**; YuNet/AuraFace, direct matching, one reference, consistency 1.0, detector score 0.8, maximum side 1600, minimum face 40px and blur minimum 0 are unchanged. Input/freeze schemas, models, preprocessing, qualification, references, labels and dependency versions are unchanged. Permissions, capture independence, fixed inputs and all prior integrity checks remain mandatory.

Production flow remains `main → run → verify_freeze → preflight → execute → Service.gallery → compare_galleries`. The scorer now requires explicit observation metadata; the runner is the production caller and supplies it. New source hashes bind this correction to any future authorized freeze. Historical recorded results are preserved, not rewritten using new scoring.

Work remains local on `poc/c0-1-hardening`, HEAD `c281bd8fe4d713509f9136776ff708cae8707882`. No commit, push, deployment, paid service, human qualification, real challenge freeze/run, historical probe rerun or retuning occurred.

## Actual verification

| Check | Outcome |
| --- | --- |
| Full backend suite | **195 passed**, 39.42 seconds |
| Focused C1 suite | **77 passed**, 27.56 seconds |
| New observation regressions | **11 passed**, included above |
| Ruff | Passed |
| Python compilation | Passed |
| Updated tested source | **60 files**, current bytes match the tested inventory |
| Historical evidence | **3,879 files unchanged** by SHA-256, size and modification time |
| Policy, pair requirements and model metadata | Unchanged versus prior pair-coverage packet |
| Browser/build | Not rerun for this backend-only correction; prior four browser tests and TypeScript/Vite build remain historical evidence, with web/API/service hashes unchanged |

The existing Starlette/httpx deprecation warning remains; it did not fail tests. No dependencies were upgraded. Fresh evidence is under `var/c1-observation-verification/`: backend XML/log, lint, source inventory verification, observation regression outcomes, policy/artifact metadata and historical before/after/comparison files. Previous browser/build evidence is explicitly identified as prior in the corrected packet.

Tested-source digest: `49ad16da936a6ad01b8adb6ccc8dd7ed6a167421fa775d3c0a05f0c20120cfac`. The inventory grows from 59 to 60 because `tests/test_c1_observation.py` is new. Existing scorer unit tests now explicitly declare successful observations; failure tests retain prior import/processing assertions with successfully enrolled synthetic participants so that gallery-unavailability is tested independently.

## Production CLI regression outcomes — synthetic only

Tests use the actual CLI orchestration, service, worker, guest-gallery collection, scorer and result exports with the existing explicit synthetic provider/preflight harness. No real qualification is created. Temporary test freezes contain synthetic fixtures only, never real data. `tests/test_c1_observation.py` injects gallery-access errors and verifies:

| Scenario | Available raw delivery rows | Rows with unknown counts | Observation complete | Pair / pilot / design / overall success |
| --- | --- | --- | --- | --- |
| D successfully read and genuinely empty | 30 | 0 | Yes | All true |
| D gallery unavailable; otherwise perfect delivery | 30 | 24 | No | All false |
| A gallery unavailable | 20 | 24 | No | All false |
| B gallery unavailable | 20 | 24 | No | All false |
| C gallery unavailable | 20 | 24 | No | All false |

All five export 24 photographs/96 labels. Failed-person counts are null in pair/JSON rows and blank in CSV with the explicit error. In each failure case, whole-study recall is null and the status is `incomplete_gallery_observation`. A genuinely empty, observed D gallery has zero counts and still passes. Pure scorer regressions additionally check the missing-metadata and contradictory-delivery guards.

For all five CLI scenarios, the test invokes `run` again after recording the result. The exact saved result returns, the provider is not called, gallery read counts remain one per A/B/C/D and every output file hash/modification time is unchanged. Thus incomplete outcomes consume the attempt and cannot silently replay.

Existing exact-pair, ABC/missing-pair, duplicate, wrong/partial recipient, correction, timeout, enrollment, import/processing failure, qualification and freeze-integrity regressions remain passing. These are software outcomes only, not evidence of natural-photo recognition accuracy.

## Preservation and readiness

The preservation inventory includes C0/C0.1 runs, original C1 and pair-correction verification (including their temporary synthetic evidence), permitted C1 artifacts, both incomplete scaffolds and all three previous source-review ZIPs. All **3,879** files retain their hashes, sizes and modification times, with no additions/removals inside those protected roots. Access times are excluded. Both inventory digests are `daecae608f9992beddf0efb6523248be1bf7a8445b4ecfea3ea60861b48537d8`.

Existing artifact hashes and pipeline identity remain compatible with the accepted non-person parity evidence. Only metadata/hashes were checked; no model was initialized or numerical parity rerun for this revision. No new approval is asserted.

Default real preflight remains **BLOCKED ON DATA**, exit code 2, because the scaffold has no finalized `study.json`. There is no real `var/c1-challenge/` directory. The documented real inputs, independent references, permissions, human labels and qualification are still missing. See [C1_INPUTS.md](C1_INPUTS.md); the incomplete-observation semantics are also documented in [EVALUATION.md](EVALUATION.md). No real accuracy or cost result is claimed.

## Commands and review handoff

From the repository root, the fresh checks were:

```sh
.venv/bin/pytest -q --basetemp=var/c1-observation-verification/pytest-tmp \
  --junitxml=var/c1-observation-verification/backend-tests.xml
.venv/bin/ruff check server scripts tests
.venv/bin/python -m compileall -q server scripts tests
```

Use a new output directory for future checks to preserve this evidence. The unchanged local synthetic app command is:

```sh
FACE_DATA_DIR=var/c1-demo FACE_CONFIG=configs/synthetic.json .venv/bin/python -m scripts.dev
# http://127.0.0.1:5177
```

The corrected source-review ZIP includes this report, full changed/new source and tests, baseline and C1-only reconstruction patches, updated tested hashes, schemas and sanitized evidence. The previous ZIPs remain historical. GitHub does not contain this uncommitted snapshot; attach the corrected ZIP for review. Do not rerun the challenge to replace an incomplete result.
