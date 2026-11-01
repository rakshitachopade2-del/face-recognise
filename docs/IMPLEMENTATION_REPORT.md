# Current milestone: C0 and supplied studio study (1 November 2026)

C0 source/test commit: `888e79db463d977e48c9bb2e8a14d5d5ae16795f`, local branch `poc/c0-studio-study`. No push, merge, deployment or paid services. The original A/B report below is historical; its “no weights/no photographs/no parity” statements no longer describe the separate C0 study.

- **63 backend tests**, **3 Chromium tests**, Ruff, Python compilation and TypeScript/Vite build passed.
- Explicit release controls, strict complete evaluation schema, enrollment-policy compatibility, coalesced matching/expiry behavior, geometry/cache corrections and code-bound parity are implemented and tested.
- Both permitted pinned models were downloaded and byte-hash verified. Eight independent non-person parity cases, seven negative controls and three same-engine detector-wrapper checks passed. Initial parity failures were retained and corrected without relaxing tolerances.
- Fixed studio calibration and probe each contain all 12 gallery photos and 36 truth rows, with one reference for each of three enrolled adults. Chosen threshold 0.6 / margin 0.3 produced 6 correct, 0 wrong and 0 missed links per cohort. Calibration published nothing; the frozen probe published six links. Unknown-person photos and absent C received no links. No subjects or failures were filtered out.
- These are correlated, same-session studio results with source-verified presence labels. Real-event accuracy, recognisable/detector recall, fairness, liveness, scale, production rights and cost remain unestablished. No additional inputs are needed for this specific supplied study.

Full evidence, limitations and exact commands: [C0_READINESS_REPORT.md](C0_READINESS_REPORT.md), [STUDIO_STUDY_REPORT.md](STUDIO_STUDY_REPORT.md), [MODELS.md](MODELS.md), [EVALUATION.md](EVALUATION.md).

```sh
.bootstrap/bin/uv sync --locked --group reference
npm --prefix web ci
.venv/bin/python -m scripts.studio_study preflight
.venv/bin/python -m scripts.studio_study all
# Local synthetic app:
.venv/bin/python -m scripts.dev
# Or inspect the completed real probe (stop the other launcher first):
FACE_DATA_DIR=var/c0-studio FACE_MODELS=var/c0-studio/registry.json \
  FACE_CONFIG=var/c0-studio/provisional-config.json .venv/bin/python -m scripts.dev
```

UI: http://127.0.0.1:5177. Completed study stages return their saved evidence without repeating the probe. The runtime directory is private and ignored. Detailed labels, scores, embeddings, DBs, model binaries and photographs are excluded from Git. The documentation follow-up commit can be identified with `git log -2 --oneline`.

---

# Implementation report — phases A and B

31 October 2026 · Milestone branch: [`poc/phases-a-b`](https://github.com/rakshitachopade2-del/face-recognise/tree/poc/phases-a-b) · [Repository](https://github.com/rakshitachopade2-del/face-recognise)

**Result:** runnable local foundation and synthetic end-to-end retrieval loop implemented and verified. Real-model inference, preprocessing parity and recognition on authorized wedding photographs remain **NOT RUN** because no approved model bytes or authorized photographs were supplied. This is not production readiness or measured face-recognition accuracy.

## Repository inspection and decisions

- This directory initially contained the six handoff files and `tools/cost_scenarios.py`. It was **not a Git repository** during implementation. For this publication, `git ls-remote --symref` succeeded with no refs: the remote had no existing branches or commits to integrate. Git was initialized in the implementation folder itself on `poc/phases-a-b`, and `origin` was set to the user-specified repository. The existing Git identity and credential configuration were preserved. The user explicitly authorized this milestone commit/push; cloud deployment, paid APIs, cloud resources, messages and biometric uploads remain out of scope. No force-push or deletion of existing work is part of this publication. Obtain the exact milestone SHA with `git rev-parse HEAD` in this checkout; the publication handoff supplies the remote-verified SHA.
- No applicable `AGENTS.md` was found in the workspace or ancestor directories. The absolute `01` and `03` files named by the user were byte-identical to the workspace copies. `02-Evaluation-and-Acceptance.md` was available in this workspace, not beside those absolute paths. All original handoff files and the cost calculator were preserved.
- The user's request authorizes phases A/B here, so the prompt's suggestion to use a separate GitHub checkout was treated as background. Existing unrelated services occupied 8000/5173; this POC uses loopback **8017/5177** and did not stop those services.
- The Sites skill's local-only path was used for the browser implementation; no hosted Site was created. The requested React/TypeScript/Vite/CSS modules and FastAPI/SQLite stack was retained.
- Default mode is synthetic and refuses normal photographs at provider inference. Real candidate manifests are disabled rather than populated with guessed hashes or silently substituted checkpoints.
- POC expiry is bounded to 30 days from event creation, or a shorter permission. This is deliberately stricter than 30 days after an eventual evaluation run and cannot be extended by late uploads. Participant withdrawal has separate retention semantics from event-level photo-face processing permission.

## Completed capabilities

| Area | Implemented behavior / evidence |
|---|---|
| Foundation | Python package, validated local settings, provider protocol, explicit operating points, locked dependencies, durable SQLite schema, WAL/busy timeout, private storage, CLI entry points |
| Records | Events and dataset authorization, photos/import outcomes, observations, purpose-specific consent, participants, enrollment generations, jobs, config snapshots, proposals, released associations, rejections, deletion audits, local sessions and run records |
| Import | JPEG/PNG/HEIC decoding by actual bytes, EXIF orientation, ICC-to-sRGB conversion, byte/pixel limits, preserved originals, opaque keys, event-scoped exact hashes, duplicate reuse and independent corrupt-file failures |
| Worker | One worker, durable idempotency keys, per-claim fencing token, lease expiry/heartbeat, bounded attempts, retry/dead-letter states, explicit recovery action, transactional publication, atomic file writes, event scheduling and restart recovery |
| Providers | Deterministic visibly synthetic rectangle provider; OpenCV YuNet + ONNX Runtime AuraFace/SFace adapters behind approval/hash/parity gates; no implicit downloads or auxiliary demographic models |
| Enrollment | Separate active consent before and after inference, exactly 1/3/5 configurable references, one-face and quality checks, reference consistency, normalized mean template, no stored raw references, generation invalidation |
| Matching | Shared exact chunked direct baseline, version isolation, distinct-participant margin, acceptance threshold, abstention, one identity per face and many guests per photo, transactional consent/suppression checks |
| Late work | Late enrollment searches compatible stored vectors; new photos match current enrollments; new identities invalidate old margin decisions without repeating detection/embedding |
| Corrections | Not me removes and durably suppresses only that guest/photo association; retries and late work cannot restore it; no training or global threshold changes |
| Withdrawal | Immediate enrollment/session/gallery revocation, generation increment, synchronous template/link/proposal deletion, stale-worker publication refusal, media authorization rechecked after file IO |
| Retention | Worker expires permissions, deletes event vectors and media, records tombstones, sweeps import orphans and truncates WAL; authorization fails at expiry even while worker is stopped |
| Config changes | Explicit activation, stale-worker fencing, threshold-only embedding reuse, incompatible namespace isolation, reuse of valid retained cache when returning to an earlier namespace |
| UI | Event/import/progress view, enrollment and withdrawal, guest gallery/no-result/Not me, separate box/score diagnostics, aggregate JSON report/export; responsive layout and visible simulator/synthetic warnings |
| Evaluation | Unique person-photo metrics, supports/micro/macro/worst/median/p10, recognisable recall, empty-gallery coverage, wrong-link severity, separate previews/evidence/corrections, split validation, private CSV structure validator and shared-worker exploratory evaluation CLI |

Automatic releases in this local simulator are labeled experimental; configuration state is not public-release authorization. Operator-reviewed release automation is not implemented and its reported count is zero. Guest low-confidence candidate previews are not implemented and their count is zero. Ordinary released-gallery viewing is not a candidate-confirmation flow.

## Setup and exact local commands

Prerequisites: Node 24/npm 11, a system Python able to create a venv, and internet for open-source dependency installation. Supported and verified OS is Apple Silicon macOS. No separate libheif installation was necessary with the resolved wheel. Other operating systems remain unverified.

```sh
git clone --branch poc/phases-a-b https://github.com/rakshitachopade2-del/face-recognise.git
cd face-recognise
python3 -m venv .bootstrap
.bootstrap/bin/python -m pip install uv==0.13.6
.bootstrap/bin/uv sync --locked
npm --prefix web ci
.venv/bin/python -m scripts.make_fixtures
.venv/bin/python -m scripts.dev
```

Open **http://127.0.0.1:5177**. API/docs: **http://127.0.0.1:8017/docs**. Ctrl-C stops this POC's API, worker and Vite processes. The existing implementation-folder installation is already prepared; run `.venv/bin/python -m scripts.dev` from that folder. Browser-test servers shut down automatically after verification. Their database is separate from the operator demo data.

Separate-terminal equivalents:

```sh
# Each command in a separate terminal, from the workspace root:
.venv/bin/python -m server
.venv/bin/python -m server.worker
npm --prefix web run dev
```

For a non-UI synthetic exercise:

```sh
.venv/bin/python -m scripts.synthetic_run
```

Use the fixture walkthrough in [README.md](../README.md). Approved real experiments require the additional steps in [MODELS.md](MODELS.md); running the commands above does not perform real recognition.

## Verification outcomes

| Command | Outcome |
|---|---|
| `.venv/bin/pytest -q --junitxml=var/test-results.xml` | **39 passed**; one dependency deprecation warning about Starlette's httpx TestClient adapter, no test failures |
| `.venv/bin/ruff check server scripts tests` | Passed |
| `.venv/bin/python -m compileall -q server scripts` | Passed |
| `.bootstrap/bin/uv sync --locked` | Passed against existing lock; 33 resolved entries / 31 installed dependency packages |
| `npm --prefix web run build` | TypeScript check and Vite build passed; 30 transformed modules |
| `cd web && npx playwright install chromium && npm run test:browser` | **3 passed**, populated two-event lifecycle, original desktop workflow and mobile layout smoke, 16.0 seconds total |
| `.venv/bin/python -m scripts.synthetic_run` | Completed, private JSON includes measured elapsed/config/hardware/counts and explicit synthetic status |
| `scripts.dev` startup/shutdown smoke | API health and UI both HTTP 200; Ctrl-C launcher exit 0 |

Backend coverage includes two-event isolation and SQL relationship enforcement, consent before/after inference, corrupt/oversize/rotated/HEIC inputs, exact duplicates, ordinary-image refusal in synthetic mode, enrollment failure explanations, late enrollment/photos, multi-guest ownership, unknown abstention, ambiguous identities, model/namespace changes, active-config changes, persisted suppression, expired leases, heartbeat fencing, crash after publication, bounded retries, restart, withdrawal during matching and file reading, expiry/deletion, private paths, origin/host/session controls, public-mode refusal, artifact hash/path gates and hand-verifiable metric cases.

Browser checks used generated rectangles only; no human photographs were displayed. Screenshots are supplementary local artifacts; assertions below verify actual populated state and HTTP access outcomes. User-facing navigation, loaded images, diagnostic overlays, correction, withdrawal and report output passed without uncaught page errors.

Artifacts (private, ignored):

- `var/test-results.xml` — backend test cases/counts/duration.
- `var/browser-results.json` — Playwright outcomes and timings.
- `var/populated-browser-outcomes.json` — asserted populated workflow outcomes without subject IDs or session values.
- `var/provider-readiness.json` — both real-provider startup attempts correctly refused for missing approval/manifest.
- `var/screenshots/workspace.png`, `gallery.png`, `mobile.png` — synthetic screenshots.
- `var/verification-synthetic/runs/synthetic-latest.json` — isolated publication verification exercise metadata and toy metric assertions. Reproduced with `FACE_DATA_DIR=var/verification-synthetic .venv/bin/python -m scripts.synthetic_run`.
- `var/launcher-smoke.json`, `var/launcher-smoke.log` — combined launcher check.
- `docs/verification-summary.json` — sanitized measurements and artifact hashes; no per-person results.

## Populated browser verification — actual outcomes

The added `web/tests/populated.spec.ts` uses visibly labelled generated rectangles, two new events and three synthetic enrollment records. Browser actions create/import/enroll/preview/correct/withdraw; authenticated HTTP requests assert exact photo IDs and denial status. Private test IDs, cookie values, images and database contents are excluded from this published report.

| Scenario | Observed and asserted result |
|---|---|
| Initial import | Event A accepted 3 fixtures: red/green group, red-only and unenrolled blue; all jobs completed |
| Late enrollment | Red enrolled after processing received 2 photos; green enrolled later received the group photo. Detection-job count stayed at 3 |
| Shared group photo | The same canonical photo was present in both red and green galleries, with loaded browser images |
| Unknown fixture | Blue fixture was in neither gallery; attempted red guest media access returned HTTP 403 |
| Exact duplicate | Re-import reused the group photo ID, adding 0 photos and 0 jobs |
| Late photo | A later distinct red fixture increased red's gallery to 3; green remained at 1 |
| Not me + retry/restart | Red rejected the group. With the worker stopped, the test marked its completed match job retryable in the isolated test DB, clicked the UI Retry action, restarted the worker, waited for completion, and reloaded the browser. Red retained only the 2 unrelated photos; green still retained the group |
| Two-event isolation | Identical group bytes in event B produced a distinct event-scoped asset. B's red participant received only B's group. B's guest session accessing A's gallery/media returned 403; a wrong-event operator asset request returned 404 |
| Withdrawal with queued work | Another group fixture was queued with the worker stopped. Red withdrew before restart. After processing, red had 0 enrollment templates and 0 released associations; green had both group photos |
| Stale access after withdrawal | Saved pre-withdrawal session could no longer retrieve gallery/media (401); requesting a new red preview returned 403 |
| Unrelated event preserved | Event B's participant still had its single correct synthetic group photo after A's withdrawal |

The test restarts the actual worker process and reloads the browser. API service process restart is not claimed by this browser case; persistence/recovery is additionally covered by the backend service-recreation and lease/crash tests. Full anti-spoofing, authentication and recognition accuracy remain untested.

The only browser-verification failure encountered was an ambiguous accessible label for the participant selector in the new test. The selector now has explicit `aria-label="Participant"`; the complete suite passed afterward. Frontend type checking now includes both browser test files. Source audit also found and fixed the private-directory validator allowing `web/` itself (while rejecting its descendants); a regression test now refuses that path before any storage initialization.

## Actual measurements, and what they do not establish

Hardware: **Apple M4 Pro, arm64, 25,769,803,776 bytes RAM (24 GiB), macOS 27.0**. Runtime: **Python 3.12.16, Node 24.13.0, npm 11.6.2, uv 0.13.6**. Selected installed packages: FastAPI 0.162.0, NumPy 2.5.4, OpenCV headless 4.14.0.94, ONNX Runtime 1.31.1, Pillow 12.3.0 and pillow-heif 1.8.1. Full versions/declared licenses are in [dependency-manifest.json](dependency-manifest.json), `uv.lock` and `web/package-lock.json`.

The recorded synthetic exercise processed **2 generated images, 3 rectangle observations and 2 synthetic enrollments**, produced **2 deduplicated gallery associations**, completed **10 jobs with zero retries**, and took **0.288127 seconds** inside its measured exercise window on this machine. This does not include interpreter startup or dependency installation. Latest-attempt job elapsed values are recorded separately and are not billed seconds or total retry-inclusive CPU time. See the JSON artifact for exact namespace and operating-point settings.

The toy link assertions are correct for these hand-constructed rectangles; they do not estimate recognition precision or recall. No real-image detector recall, preprocessing parity, face recognition accuracy, subgroup/fairness performance, anti-spoofing/liveness, N=300/1,000 quality, 5,000/15,000-photo throughput, ten-event burst behavior, delivery p95, CPU/GPU comparison, cloud bills or cost were measured. The handoff's accuracy, latency and rupee figures remain targets, not results.

## Model provenance and clearance

`configs/models.json` records official candidate sources, selected filenames, candidate preprocessing and explicit disabled evaluation / blocked production status. Revision/hash/permission fields remain unset because no approved bytes or approval records were supplied. No artifact SHA is invented. Candidate artifact names are restricted to YuNet's selected detector, AuraFace's recognition-only file and the SFace comparison file.

Real-provider startup requires both artifacts' evaluation approval and manifest fields, actual-byte hash verification, a supported contract and a passing locally persisted reference-parity receipt tied to the artifacts/contract/runtime. Source review and the exact enablement steps are in [MODELS.md](MODELS.md). All real inference and parity checks remain **NOT RUN**. Unresolved production rights do not override the separate POC approval requirement.

## Remaining inputs versus implementation limits

**Missing external inputs for real testing:**

1. Approved YuNet and AuraFace recognition artifacts (SFace optional comparison), exact official revisions and actual SHA-256 values; experiment-use permission basis and separate production-clearance/provenance status.
2. Independent reference preprocessing/runtime output for those exact bytes, and its provenance/authorization, to run `scripts.check_parity`.
3. User-supplied authorized adult gallery images and independently captured enrollment references; event processing permission and active participant retrieval consent. Include permitted unenrolled people and enrolled participants absent from the gallery.
4. Independently adjudicated person-photo truth, evidence-face truth where available, capture/split identifiers and a documented exploratory operating point. No threshold transfer from synthetic mode.

**Known implementation/verification limits:**

- Real adapters are implemented but not exercised with weights. Exact graph preprocessing/shape incompatibilities can only be resolved after approved bytes and independent reference outputs exist.
- Full-frame YuNet detection is implemented; selective overlapping tiles, zero-detection second-pass experiments and detector recall analysis are unimplemented E1 challengers, not silently claimed coverage. No clustering/rescue is implemented, as requested for the baseline.
- The evaluation CLI is exploratory. CSV-to-app-ID label mapping is manual; immutable sealed-run registration, event/identity bootstrap intervals, annotation UI, comprehensive detector/open-set attribution and benchmark/load orchestration are not implemented. These are evaluation-harness extensions before launch evidence, not missing user permissions.
- One worker and local CPU execution were exercised. Multi-worker operation, GPU inference, large memory bounds, fairness at ten-event bursts and sustained throughput are unverified.
- The UI/API are a local operator simulator. No real membership authentication, liveness, public enrollment, transport deployment, notification, cloud storage or production access controls are implemented. Public mode fails closed. Never publish this as a guest service.
- Physical deletion needs the worker to run; logical authorization denial does not. No backups are created by the app; external backups/snapshots/swap, already downloaded files and bytes already in flight are not recallable. Restore requires a separately controlled tombstone replay procedure and is not automated. No forensic erasure guarantee is made.
- SQLite schema initialization supports this POC and its active-configuration column migration; this is not a general production migration/backup framework. Filesystem limits are per decoded file; this local operator service is not hardened against hostile large multipart traffic.
- A dependency deprecation warning remains for the test client's httpx adapter; it does not affect the passing runtime/API/browser checks.

No known failing synthetic functional test remains. The POC is ready for local synthetic demonstration and for supplying the inputs needed to begin real-provider verification; it is not yet “engineering ready on authorized real fixtures” under document 02.

## Publication file audit

The milestone includes application/test/tool source, dependency lockfiles, disabled safe configuration examples, the original non-biometric handoff documents and sanitized aggregate documentation. `.gitignore` covers private data, raw media, embeddings/arrays, model binaries, SQLite files, logs, credentials/key files, environment files, virtual environments, browser artifacts and dependency/build directories. The staged-file audit checks both paths and content before the commit; no private run artifacts or photographs are included. The report intentionally omits local account paths and participant/session identifiers.

## Files added

- `.gitignore`, `.python-version`, `pyproject.toml`, `uv.lock`, `README.md`.
- `server/`: `__init__.py`, `__main__.py`, `config.py`, `schema.sql`, `db.py`, `media.py`, `providers.py`, `matching.py`, `service.py`, `worker.py`, `api.py`, `metrics.py`, `reporting.py`.
- `configs/`: `synthetic.json`, `models.json`, `auraface.uncalibrated.json`, `sface.uncalibrated.json`.
- `scripts/`: package marker, `make_fixtures.py`, `dev.py`, `synthetic_run.py`, `evaluate.py`, `validate_dataset.py`, `check_parity.py`, `reindex.py`.
- `tests/`: package marker, `conftest.py`, `test_pipeline.py`, `test_security_media.py`, `test_metrics_matching.py`.
- `web/`: package/lock, HTML entry, TypeScript/Vite/Playwright configs, `src/main.tsx`, `src/App.tsx`, `src/App.module.css`, `src/api.ts`, `tests/smoke.spec.ts`, `tests/populated.spec.ts`.
- `docs/`: this report, `MODELS.md`, `EVALUATION.md`, `dependency-manifest.json`, `verification-summary.json`.
- Ignored local artifacts: `.bootstrap/`, `.venv/`, `web/node_modules/`, `web/dist/`, test/build caches and `var/`. The browser test installed Chromium in Playwright's normal user cache.

## Smallest next experiment

Approve and hash one YuNet/AuraFace pair, pass independent preprocessing parity, then process a few authorized full photographs with two consented enrolled adults plus one authorized unenrolled subject and separate references. Inspect missed faces, wrong evidence and abstentions; retain both successful and failed examples privately. Only then grow toward the 200–500-photo debug set and independent calibration/held-out events. No purchase or deployment is necessary for that next step.
