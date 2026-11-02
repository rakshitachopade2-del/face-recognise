# C0.1 hardening report — 1 November 2026

**Completed locally. No new recognition-accuracy result was measured.** The completed FRLL calibration/probe was not run, retuned, rematched, corrected or upgraded. All six review findings are fixed and covered by regressions; fresh non-person numerical parity passed separately.

Branch: `poc/c0-1-hardening`, created from reviewed `poc/c0-studio-study` at `c281bd8fe4d713509f9136776ff708cae8707882`. The C0.1 changes are **uncommitted local working-tree changes**, not a new published commit. No push, merge, deployment, paid service, new photograph collection, threshold change or recognizer change occurred. The prior branch/history were preserved.

The supplied already-extracted `Def Ref/C0-Review/` was copied to `var/assistant-inputs/C0-Review/`. All 16 entries matched CONTENTS.json SHA-256 and byte counts. The separate review/prompt copies matched the same instructions. No review ZIP was needed because the requested extracted folder was available. The packet and reviewer logs remain ignored; they are not repository source.

## Completion matrix

| Requirement | Result | Evidence |
|---|---|---|
| F1: rematch after stale-Service withdrawal and cross-configuration expiry | PASS | Remaining gallery recovers through the event's active worker; no extra PROCESS jobs; old worker remains fenced. |
| F2: official byte-pinned reference sources | PASS | All five URLs/revisions/sizes/hashes recorded in an uncommitted pin manifest; cached/downloaded mismatch and pre-import rejection regressions. |
| F3: complete strict parity contracts | PASS | Positive synthetic contract fixture passes; malformed Booleans, missing/failed results, duplicate cases, invalid sources, stale identities, contradictory/nonfinite measurements rejected. |
| F4: recognisable recall with unknown presence | PASS | Whole recall and whole-set recognisable recall both null; known-truth-only recall remains explicitly separate. |
| F5: publisher-coded studio presence consistency | PASS | A-source portrait labeled A absent/B present rejected; enrolled and unenrolled source cases accepted; adjudicated group truth unaffected. |
| F6: API/UI readiness | PASS | Invalid policy/namespace/consent/generation/expiry excluded from eligible count; incompatible participant hidden from preview and shown re-enrollment reason; re-enrollment restores access. |
| Runner freeze/stage guarantees | PASS | Synthetic tests reject changed frozen code/policy/registry/input/label/evidence before provider creation; started incomplete stages refuse retry; completed stages return saved output; raw snapshot precedes scoring. |
| Backend / frontend / browser | PASS | 118 backend tests, 4 Chromium tests, Ruff, compilation and TypeScript/Vite build. |
| Fresh non-person parity and startup | PASS | Eight cases, seven negative controls, three wrapper sizes; new v3 receipt accepted; guest release remains disabled. |
| Historical evidence integrity | PASS | 109 files unchanged in paths, SHA-256, sizes and modification times; zero additions/removals. |

## Findings, fixes and reproductions

### F1 — event-active rematch routing

Before the fix, the supplied reproduction showed a remaining participant's gallery dropping from one photo to zero after a stale Service withdrew someone else. The active worker executed zero jobs, and the pending job used an inactive configuration.

`Service.rematch_event` now reads the event's persisted active configuration and namespace inside the existing transaction and passes them to job creation. It does not instantiate another model, reject withdrawal, weaken access checks or bypass worker fences. Revocation/deletion still occurs immediately. Existing compatible photo observations are reused.

After the fix, the same reproduction shows one active-worker match, the remaining gallery restored to one photo, and no pending jobs. Regressions additionally exercise two events with different active configurations during individual-consent expiry, stale snapshot publication refusal, no added PROCESS work and existing whole-event expiry/coalescing guarantees. Five photos plus twenty enrollments still yield five effective matches and 95 superseded entries; whole-event expiry adds zero jobs.

### F2 — reference source pins before execution

The original gate reproduction accepted a 38-byte stale cache file and attributed it to a requested URL. `configs/reference-sources.json` now records the exact five official source pins already independently confirmed by the review. `server/reference_pins.py` verifies inventory, bytes and sizes. Preparation validates cached files and newly downloaded temporary bytes; mismatches leave existing cached evidence untouched and do not publish a downloaded target.

The isolated reference runner checks every source pin before loading upstream code. It compiles the verified source bytes rather than loading potentially stale Python bytecode. Expected preprocessing still does not import application alignment/preprocessing. Tests cover stale cache, mismatched download, a valid download, missing/changed source and rejection before the import hook. No new source revision or model artifact was introduced.

Pin-manifest SHA-256: `744f29e37afd3d32cbd249e3b0be746de703cd9703ead958aad6b3d4f7ff34da`.

### F3 — strict, complete v3 evidence

The original reproduction accepted a receipt with string `"false"` summary flags and empty result inventories, and accepted an empty source map with one archive reused for eight names. New shared Corpus, CaseResult, WrapperResult and Receipt models reject those shapes.

Required inventory is exactly eight named preprocessing cases, seven named negative controls, three declared detector sizes and five pinned sources. Archives contain case IDs, with exact expected paths and unique hashes; startup verifies identities, hashes, source pins and array shapes/dtypes/finiteness/norms. Result records bind back to their corpus entries. Boolean fields reject strings and numeric coercion. Finite numerical measurements must agree with fixed tolerance decisions and aggregate summaries; absolute/scaled tensor-error contradictions are rejected. A caller-supplied summary cannot substitute for complete results.

The checker completes all controls, including the stale-identity control, before atomically writing its final receipt. A regression watches publication order and verifies one final receipt plus one history copy, with all seven controls complete. Passing synthetic fixtures exist only in temporary test directories with mocked pins/providers; they are never used to enable a real provider.

Schema version is `independent-nonperson-v3`. Representation/checker identities include the pin manifest and relevant validation code; reference identity additionally includes SciPy. Old v2 evidence was directly checked and rejected without rewriting it. The suite remains AuraFace-specific; SFace stays disabled/unvalidated. These are local evidence-consistency checks, not signed or adversarial attestation.

### F4 — unresolved recognisable denominator

Before: one delivered known recognisable positive plus one unknown-presence row yielded whole recall null but recognisable recall 1.0. After: both whole-set metrics are null. Known positives with unannotated recognisability still withhold recognisable recall; known negative rows do not falsely make that denominator unresolved. Existing known-truth-only recall and coverage/support fields remain separate. The historical studio result is unchanged because its positive recognisability was already null.

### F5 — source-verified presence semantics

For `studio_identity_split_exploratory` only, each source-verified label now agrees with the gallery asset's source person and source-to-app mapping. The supplied A/B swap reproduction is rejected. An enrolled source yields the matching positive and other negatives; an unenrolled source yields all negatives. Manually adjudicated group-photo labels are not forced into a single-person rule. Reference/gallery reuse checks remain intact. Generated JSON schema was regenerated and is byte-identical: this is a semantic validator change, documented in EVALUATION.md.

### F6 — enrollment readiness

Status derives eligible enrollment from the event-active policy and namespace using the same consent/generation/expiry predicate used for matching. `enrolled` is a Boolean eligibility result; `gallery_ready` additionally accounts for the serving configuration and release gate. `readiness_reason` explains policy/representation changes, expired authorization or unavailable preview.

The original API reproduction reported enrolled=1 while preview denied access. It now reports enrolled=false with a re-enrollment reason. Backend tests cover actual 1→3 invalidation, successful re-enrollment and permission expiry. The added browser test starts with a previous three-reference template, switches to the active one-reference policy, checks the message/hidden preview choice, then re-enrolls and retrieves the generated photo. There is no UI redesign.

## Runner protection without replay

All new runner tests use temporary literal files, generated colored rectangles, dependency injection or mocks. They never reference the preserved study runtime.

Freeze checks now verify actual selected input bytes (not just manifest declarations), the passed study object, permission/corpus/calibration hashes and pipeline identity before constructing a probe provider. The pin manifest is included in code identity. Changed code, policy, registry, input, labels, study, permission, corpus, calibration or runtime are rejected before inference. Started incomplete stages retain their exclusive marker. Completed CLI calls return saved results without rewriting preflight artifacts. Calibration explicitly refuses a release-enabled service and checks that no guest links were published; raw outcomes are asserted to exist before scoring. Probe scoring is explicitly invoked with `rematch=False`.

No `studio_study all`, calibration or probe command was run on `var/c0-studio/`. Preparation/parity now refuse directories containing a historical freeze. No old receipt was copied into a new provider's gate.

## Actual verification

Environment: existing locked Python 3.12 environment with the `reference` group; no dependency or lockfile changes. Chromium was already available here; the reviewer's browser installation failure did not recur.

| Command/check | Actual outcome |
|---|---|
| `.bootstrap/bin/uv sync --locked --group reference` | Passed, 41 resolved / 39 installed packages checked. |
| Supplied backend/evaluation reproduction scripts, before and after fixes | Before/after results preserved under `var/c0-1-hardening/`; lifecycle and metric defects corrected. |
| `.venv/bin/pytest -q --junitxml=var/c0-1-hardening/backend-tests.xml` | **118 passed**, one Starlette/httpx deprecation warning, 12.93 s. |
| `.venv/bin/ruff check server scripts tests` | Passed. |
| `.venv/bin/python -m compileall -q server scripts tests` | Passed. |
| `npm --prefix web run build` | TypeScript and Vite build passed, 30 modules. |
| Browser command below | **4 passed**, 21.0 s; populated lifecycle, readiness/re-enrollment, operator loop, mobile layout. |
| `FACE_DATA_DIR=var/c0-1-hardening/synthetic .venv/bin/python -m scripts.synthetic_run` | Passed; explicitly synthetic pipeline metrics only. |
| Fresh non-person parity, final command below | Eight positive cases, seven negative controls, three wrapper cases passed with unchanged tolerances. |
| RealProvider construction using the fresh final receipt | Passed; no portrait analyze call; `can_release=False`. |

Browser command (new DB/results/screenshots, preserving earlier browser artifacts):

```sh
FACE_BROWSER_DATA_DIR=var/c0-1-hardening/browser-data \
FACE_BROWSER_RESULTS_DIR=var/c0-1-hardening \
  npm --prefix web run test:browser
```

Fresh parity used copies of only the already-permitted models, terms and pinned reference code, followed by normal verification; it copied no photographs, labels, DBs, embeddings or old receipts. Final evidence directory: `var/c0-1-hardening/parity-final/`.

```sh
.venv/bin/python -m scripts.prepare_c0 --root var/c0-1-hardening/parity-final
FACE_DATA_DIR=var/c0-1-hardening/parity-final \
FACE_MODELS=var/c0-1-hardening/parity-final/registry.json \
FACE_CONFIG=configs/auraface.uncalibrated.json \
  .venv/bin/python -m scripts.check_parity
```

These record the commands actually executed; preserve the resulting evidence. Use a separate unused directory for another numerical run. A preliminary v3 numerical run is retained separately in `var/c0-1-hardening/parity/`; the final run follows an additional check that absolute/scaled error measurements cannot contradict each other. Neither run used person photographs.

Final numerical results: zero differing aligned pixels in all eight cases; maximum tensor absolute error 5.96046448e-08; minimum embedding cosine 0.999999940. Tolerances remain atol 1e-4 / rtol 1e-5, cosine ≥0.99999. The three wrapper inputs are 320×320, 479×321 and 176×160; each returns zero detections in both same-engine paths. This is not detector recall or recognition accuracy.

- Final model/pipeline identity: `2ca49f09383c2779a2107348817e7d9d9861c57920cf2297bc7191396658dc49`.
- Checker identity: `52b280151d5a12c7a3ef6ca3a3d4c2ce90a8f5fe94a3b1f013b210d2ad16cea0`.
- Final corpus digest: `3b5b661bf4df78e59539cf0fa410686d6a374a02511a3ed79f2df7f30fd1e565`.
- Final receipt SHA-256: `bf6aedc3675f0df03ef27a7818b968090eeda5a797928f2130ca68eb07b4ee6c`.
- Executed backend/frontend/test source inventory digest: `7a74a2331e2ed8e95b33ac997dfe6a21ecf98c5504ec18af1ce4a0e68ad96df8`; detailed hashes are in ignored `source-inventory.json`.

Intermediate failures were not hidden: one new stage-retry test initially failed because its fixture had supplied a completed calibration result while expecting an incomplete-stage error. The fixture was corrected to remove that completed result for that assertion; application completed-stage behavior was retained. Ruff flagged unused imports and deliberate pinned-source execution; imports were corrected and the verified-source execution was documented locally. Remaining warnings are the existing Starlette/httpx deprecation, upstream scikit-image `estimate` deprecation and Playwright color-environment warning. There is no unresolved environment blocker.

## Historical integrity

Before changes, every file under `var/c0-studio/` was inventoried without opening a DB or displaying biometric contents. After all checks, all **109 files** have identical paths, SHA-256, byte lengths and modification times. Access times were deliberately excluded. There are zero added, removed or modified historical files. The comparison includes old models/code, corpus/receipts, freeze/configuration, inputs/results, media and SQLite artifacts as bytes.

Inventory digest: `8b64e745c45b7ec32b41d8ec1b07cd706cc8c6e5db95c2aa07f965e826e4cc8f`. Ignored evidence: `historical-before.json`, `historical-after.json`, `historical-integrity-result.json`. The original C0 readiness/studio reports are unchanged. New numerical and engineering results are stored separately and do not revalidate the old recognition experiment for this revision.

## Changed files and remaining limits

- Lifecycle/readiness: `server/service.py`, `server/api.py`, `web/src/App.tsx`.
- Source/evidence gates: `configs/reference-sources.json`, `server/reference_pins.py`, `server/parity.py`, `server/identity.py`, `scripts/prepare_c0.py`, `scripts/reference_runner.py`, `scripts/check_parity.py`.
- Evaluation/runner: `server/metrics.py`, `server/evaluation.py`, `scripts/studio_study.py`.
- Regressions: four `tests/test_c0_1_*.py` files, browser lifecycle/readiness coverage and isolated browser artifact configuration.
- Documentation: this report, README.md, MODELS.md and EVALUATION.md. Generated evaluation schema has no field-shape change.

All real providers remain disabled in checked-in defaults; the private fresh parity registry uses only the previously authorized artifacts. No thresholds, model choice, matching architecture or completed probe outcome changed. General group-photo identity-set/split representation, new authorized natural captures, larger cohorts, production authentication/liveness, deployment, scale/cost benchmarks and production-rights conclusions remain outside this milestone. No further photograph or consent collection is needed for these completed engineering fixes.
