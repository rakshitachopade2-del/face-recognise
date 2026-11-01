# Supplied studio study — actual results, 1 November 2026

**Completed once with a frozen provisional policy.** Both calibration and probe contain all 12 selected gallery photographs and all 36 presence labels. Calibration selected six correct candidate links with zero wrong links; it published zero guest links. The probe actually published six correct links, zero wrong links and zero misses. This is a small correlated studio retrieval experiment, not real-event validation.

Protocol: `studio_identity_split_exploratory`; `sealed_test=false`. Branch: `poc/c0-studio-study` (local only). Executed source commit: `888e79db463d977e48c9bb2e8a14d5d5ae16795f`. Baseline: `b895af6a9e22101a5e9b5ab6e1c3aad32e007847`. Documentation follows in a separate local commit; nothing was pushed.

## Data and permission

Dataset version `frll-v5-studio-10adults-v1`, from DeBruine, Lisa and Jones, Benedict (2017), [Face Research Lab London Set v5](https://doi.org/10.6084/m9.figshare.5047666.v5), CC BY 4.0. The supplied publisher-derived adult eligibility and research-use basis are preserved as `FRLL-V5-PUBLISHED-STUDY-USE`. The user authorized this bounded local use. No new app-specific signatures, customer enrollments or vendor letters are claimed. App event/authorization records explicitly use `published_dataset_study_use_basis` and the source citation.

Fixed calibration IDs: A=001, B=002, C=003, U=004, V=005. Fixed probe IDs: A=006, B=007, C=008, U=009, V=010 (global source prefix `frll-v5-`). These are publisher pseudonyms. Actual app UUID mappings stay private. Three people per cohort were enrolled, each with exactly one designated neutral-front reference. U/V were never enrolled. C references were never gallery imports. Twelve optional neutral-angle references remained unused.

All 42 supplied JPEGs and 72 presence rows passed the bundle verifier. Exactly 30 portraits were used: six references and 24 smiling gallery photographs. Each cohort has four gallery identities × three views, with four expression capture groups. Camera angles are simultaneous/correlated. Reference and gallery expression groups/files differ, but they come from the same studio visit; sessions are not disjoint. Cohort subjects are disjoint. Two app events are not independent real events. Selection was fixed by the kit, not by observed recognition scores. Training overlap and demographic representativeness remain unknown/unassessed.

Presence labels retain `annotation_status=source_verified` and publisher subject/archive-member provenance. `recognisable=null` is intentional. No recognisable recall, detector recall, face-box accuracy or evidence-face correctness was inferred from recognition outputs.

## Calibration and freeze

Before calibration inference, the runner recorded thresholds `[0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9]` × margins `[0,0.05,0.1,0.15,0.2,0.3]`, 48 candidates. Selection rule: zero observed wrong links, then most correct links, then highest threshold and highest margin. At least one correct link is required; otherwise the probe is skipped. Detector/quality choices were fixed in advance: score .8, maximum side 1600, minimum face 40 px, blur minimum 0. Enrollment count 1; consistency 1.0 is vacuous for one reference; normalized-mean aggregation.

The shared app matcher produced the following candidate results. Every cell is **correct / wrong / missed**, out of six true links. No candidate was published to guests during calibration.

| Acceptance | Margin 0 | .05 | .10 | .15 | .20 | .30 |
|---:|---|---|---|---|---|---|
| 0.2 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 |
| 0.3 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 |
| 0.4 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 |
| 0.5 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 |
| 0.6 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 |
| 0.7 | 2 / 0 / 4 | 2 / 0 / 4 | 2 / 0 / 4 | 2 / 0 / 4 | 2 / 0 / 4 | 2 / 0 / 4 |
| 0.8 | 1 / 0 / 5 | 1 / 0 / 5 | 1 / 0 / 5 | 1 / 0 / 5 | 1 / 0 / 5 | 1 / 0 / 5 |
| 0.9 | 0 / 0 / 6 | 0 / 0 / 6 | 0 / 0 / 6 | 0 / 0 / 6 | 0 / 0 / 6 | 0 / 0 / 6 |

Chosen acceptance **0.6**, distinct-identity margin **0.3**. The candidate reports also include precision/recall, per-person supports and unknown/absent counts. The numeric placeholder diagnostic worker abstained on all 12 calibration observations; offline candidates use the same `decide` function with releases disabled.

Freeze ID: `770b73c354b1dbbdb45a8c350c9e7bae66452ec7a7972b4ea1ea2177c23bf5a8`. Saved in `var/c0-studio/freeze.json` before any probe inference. The manifest binds complete executed code and lockfiles, actual model registry, passing parity receipt/reference corpus, input/label byte hashes, protocol, permission basis and selected policy. The optimizer never loaded probe labels or vectors. Preflight checked the full bundle; hashing probe files for integrity is not secure blinding.

## Separate outcomes

| Measure | Calibration selected candidate | Probe actual worker/publisher |
|---|---:|---:|
| Gallery photographs / complete truth rows | 12 / 36 | 12 / 36 |
| Successfully enrolled people / references | 3 / 3 | 3 / 3 |
| Processed photographs / usable observations | 12 / 12 | 12 / 12 |
| Enrollment / import / processing failures | 0 / 0 / 0 | 0 / 0 / 0 |
| True links | 6 | 6 |
| Accepted candidate links / actual released links | 6 / 0 | 6 / 6 |
| Correct / wrong / missed links | 6 / 0 / 0 | 6 / 0 / 0 |
| Observed link precision / presence recall | 1.0 / 1.0 | 1.0 / 1.0 |
| Absent C false links | 0 | 0 |
| Unknown-only photos with false links / total | 0 / 6 | 0 / 6 |
| Unknown-only photo false-release rate | 0 | 0 |
| Gallery photos with no accepted identity | 6 | 6 |
| Recognisable recall / detector recall | Not measured | Not measured |
| Maximum wrong-release burst | Not measured: no batch evidence | Not measured: no batch evidence |

Per enrolled person in each cohort: A has 3 true, 3 correct, 0 wrong and 0 missed; B has the same; C has 0 true, 0 delivered, undefined precision/recall and an empty gallery. Unknown U/V supply six photos; no links were assigned to enrolled people. The probe guest-session/gallery boundary was additionally exercised: gallery sizes 3, 3, 0. All 12 gallery images per cohort produced one usable observation; six unknown observations abstained under the chosen policy. No rejected face, detection miss, failed photo or subject was discarded or replaced. No threshold/quality/reference choice changed after probe results.

Raw probe associations, proposals, job outcomes and face diagnostics were saved before scoring and before any Not me/manual correction. The probe was not re-inferred or rematched. A later read-only gallery check did not alter predictions. The six unknown photos represent only two unknown people/capture groups; the measured rate is photo-level, not independent face-level FMR. No population confidence or zero-error guarantee follows.

## Separate operational controls and engineering checks

Both non-person control PNGs imported successfully, with zero detected faces. The deliberately corrupt JPEG was rejected as `corrupt_or_unsupported_image`. Two additional imports of the same designated calibration gallery bytes both returned `duplicate` and reused its canonical photo. These controls are excluded from the 24-gallery-photo recognition denominator. Synthetic group/lifecycle tests remain separate because there are no real group photographs in this kit.

63 backend tests, Ruff, Python compilation, TypeScript/Vite build and 3 Chromium tests passed. Independent non-person parity: eight cases, seven negative controls and three detector-wrapper comparisons passed. Initial extraction/parity/URL failures and their fixes are documented in [C0_READINESS_REPORT.md](C0_READINESS_REPORT.md); no failing trial was relabeled as passing.

## Runtime and evidence locations

Hardware: Apple M4 Pro, 24 GiB RAM, macOS-27.0-arm64-arm-64bit, Python 3.12.16; CPU ONNX Runtime, two intra-op threads, single worker. Observed calibration stage wall time **4.912 s**; probe stage **4.989 s**. These local measurements include their model setup/cohort processing/scoring boundaries and exclude prior downloads/parity; they are not queue-inclusive p95 service latency, a large-gallery throughput benchmark or billed cost. No paid services were used; production costs were not measured.

Private ignored evidence: `var/c0-studio/` contains registry/terms/models, complete parity corpus/history, per-cohort mappings, full labels, private score/candidate JSON, raw snapshots, freezes, SQLite/embeddings and controls. `var/c0-test-results.xml`, `var/browser-results.json`, `var/populated-browser-outcomes.json` and `var/c0-synthetic/runs/synthetic-latest.json` record engineering checks. Sanitized aggregate reports are tracked; photographs, labels/maps and per-image evidence are not.

## Run commands

```sh
.bootstrap/bin/uv sync --locked --group reference
npm --prefix web ci
.venv/bin/python -m scripts.studio_study preflight
.venv/bin/python -m scripts.studio_study all
```

On this completed directory, `all` returns recorded stage results without repeating the probe. Preserve frozen evidence; a partially started stage is not automatically retried. A new experiment needs separate storage and declared evaluation scope, not silent retuning of this probe.

To start the local UI with the completed provisional study:

```sh
FACE_DATA_DIR=var/c0-studio FACE_MODELS=var/c0-studio/registry.json \
  FACE_CONFIG=var/c0-studio/provisional-config.json .venv/bin/python -m scripts.dev
```

Open http://127.0.0.1:5177 and select the probe event. Calibration remains on its diagnostic configuration; do not activate the provisional policy on it to rewrite historical evidence. Do not perform corrections on the preserved study when inspecting it. Default synthetic demo: `.venv/bin/python -m scripts.dev`. Only one launcher may own ports 8017/5177. All services bind loopback; there is no deployment.

## Remaining work

Nothing is missing to run or audit this specific supplied study. Real-event readiness still needs authorized independent sessions/events and group photos, difficult capture conditions, larger distinct-identity support, independently annotated detection/evidence/recognisability truth, and relevant privacy/authentication/liveness, scale and production rights evaluation. SFace comparison, fairness and cloud/production cost remain unmeasured. This studio result must not be presented as wedding/event accuracy or release approval.
