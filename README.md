# Frame — local face retrieval POC

Current software milestone: **C1 fixed-policy natural group-photo challenge**, including the accepted C0.1 hardening and C1 pair-delivery and gallery-observation corrections. Review branch: [`poc/c1-software-ready`](https://github.com/rakshitachopade2-del/face-recognise/tree/poc/c1-software-ready). See the [publication handoff](docs/C1_PUBLICATION.md) for verification provenance and scope. See [C1_IMPLEMENTATION_REPORT.md](docs/C1_IMPLEMENTATION_REPORT.md) and [C1 input checklist and commands](docs/C1_INPUTS.md). **Real C1 execution is BLOCKED ON DATA**: fresh natural photographs, independent references, documented permission and complete human labels are missing. The supplied FRLL studio portraits are historical evidence, not C1 inputs.

C1 gallery-observation verification: **195 backend tests passed** (77 focused C1 checks), plus Ruff and Python compilation. The previous four browser tests and TypeScript/Vite build are historical checks, not rerun for this backend-only correction. The runner now distinguishes unavailable galleries from successfully read empty galleries. All four A/B/C/D reads must succeed before pair, pilot, design or overall success. Unavailable counts are null, errors are exported, and an incomplete result consumes the attempt without automatic retry. Exact AB/AC/BC requirements, thresholds and all 24/96 rows are unchanged. All 3,879 inventoried historical evidence/artifact files and prior ZIPs were preserved. Real execution remains BLOCKED ON DATA; these software checks do not establish recognition accuracy.

The [C0.1 report](docs/C0_1_HARDENING_REPORT.md) and C0 results below are historical. Keep `var/c0-studio/` and `var/c0-1-hardening/` unchanged. Run the synthetic app in a separate runtime:

```sh
FACE_DATA_DIR=var/c1-demo FACE_CONFIG=configs/synthetic.json .venv/bin/python -m scripts.dev
```

Open http://127.0.0.1:5177. The historical C0 commands below are not instructions to execute current code against preserved experiments. Frozen preflight now refuses to rewrite evidence, including through partially completed `all` commands.

Phases A/B plus C0 and the supplied local studio experiment, implemented in this workspace. **Operator-controlled identity simulator: no real authentication, verified camera capture or liveness. Do not expose it publicly.**

The default provider accepts visibly synthetic colored rectangles only. The separate C0 experiment verified the permitted YuNet/AuraFace artifacts, passed independent non-person parity, and completed the supplied studio calibration/probe. Each cohort had 6 correct links, 0 wrong and 0 missed across 12 gallery photos; calibration released no guest links. These small, correlated studio results do not establish real-event accuracy. Shipped real configs remain disabled; SFace, production costs, scale, fairness and liveness remain unmeasured.

Repository: [rakshitachopade2-del/face-recognise](https://github.com/rakshitachopade2-del/face-recognise) · Published baseline: [`poc/phases-a-b`](https://github.com/rakshitachopade2-del/face-recognise/tree/poc/phases-a-b). C0 review branch: [`poc/c0-studio-study`](https://github.com/rakshitachopade2-del/face-recognise/tree/poc/c0-studio-study). The user subsequently authorized publishing this branch for review; no merge or deployment.

Verification on 1 November 2026: **63 backend tests and 3 Chromium browser tests passed**, including a populated two-event workflow. TypeScript checks (including browser test code), Vite build, Ruff and Python compilation passed. The populated checks exercised group-photo sharing, duplicate imports, late enrollment/photos, rejection after retry and worker/browser restart, withdrawal with queued work, and cross-event denial. These are synthetic pipeline results, not recognition accuracy.

## Supported setup

Verified on Apple Silicon macOS with Node 24.13.0, npm 11.6.2 and Python 3.12.16. A system Python 3.9+ is sufficient to bootstrap uv; uv installs the pinned Python 3.12 runtime. Internet is needed for open-source dependencies and the optional browser-test download. Default app startup never downloads models. The explicitly invoked study setup downloads only the two permitted pinned artifacts and reference code. HEIC support comes from the pinned pillow-heif wheel; unsupported HEIC variants fail per file. Other operating systems have not been verified.

Clone the C1 software review branch and install its locked dependencies. For current AI review, start with [C1_PUBLICATION.md](docs/C1_PUBLICATION.md); [AI_REVIEW_HANDOFF.md](docs/AI_REVIEW_HANDOFF.md) describes the historical C0 milestone. Private experiment inputs and runtime evidence are not included in the repository:

```sh
git clone --branch poc/c1-software-ready https://github.com/rakshitachopade2-del/face-recognise.git
cd face-recognise
python3 -m venv .bootstrap
.bootstrap/bin/python -m pip install uv==0.13.6
.bootstrap/bin/uv sync --locked
npm --prefix web ci
.venv/bin/python -m scripts.make_fixtures
```

Start the API, one worker and browser app together:

```sh
.venv/bin/python -m scripts.dev
```

Open **http://127.0.0.1:5177**. Ctrl-C stops this POC's processes. Ports 8017/5177 avoid an unrelated application found on 8000/5173. The app's database and queue survive restarts.

Alternatively use three terminals, each starting in the workspace root:

```sh
# Terminal 1 — API
.venv/bin/python -m server
```

```sh
# Terminal 2 — durable worker
.venv/bin/python -m server.worker
```

```sh
# Terminal 3 — web
npm --prefix web run dev
```

API docs are local at http://127.0.0.1:8017/docs. The supported entry point rejects public mode and non-loopback hosts. Mutations require an allowed browser Origin or the explicit `X-Local-Request: 1` CLI header. Cookie sessions separate operator diagnostics from a selected guest preview; anyone controlling this local computer can assume operator identity. This is deliberately not production authentication.

## Try the synthetic loop

1. Create an event and enter a synthetic dataset authorization record.
2. Import `var/fixtures/gallery-group.png`, `gallery-unknown.png` and optionally `corrupt.png`. The corrupt fixture fails independently. Importing the same file again reports a duplicate.
3. In Enrollment, record synthetic participant consent and upload `enroll-red.png`. The group photo should appear in that participant's preview; the unknown blue rectangle should not. A second participant using `enroll-green.png` can receive the same group photograph.
4. Try **Not me**. It removes and permanently suppresses that participant/photo link. Try **Withdraw consent & delete enrollment**. Matching and gallery access stop, and enrollment templates are purged.
5. Inspect the operator diagnostics and generate an aggregate report. Synthetic metrics are pipeline assertions, never evidence of face recognition accuracy.

The enrollment count is versioned in `configs/synthetic.json` (1, 3 or 5). Multiple references must be consistent. Reference photographs are processed in memory and not retained by the app. Gallery originals and oriented sRGB PNG derivatives are stored privately, with generated keys and no user filenames in records or application logs.

## Verify

```sh
.venv/bin/pytest -q --junitxml=var/test-results.xml
.venv/bin/ruff check server scripts tests
.venv/bin/python -m compileall -q server scripts
npm --prefix web run build
.venv/bin/python -m scripts.synthetic_run
```

For browser tests, stop `scripts.dev` first so the test runner can own its ports:

```sh
cd web
npx playwright install chromium
npm run test:browser
```

Tests use generated fixtures and isolated temporary/private databases. Browser artifacts go to `var/browser-results.json`, `var/populated-browser-outcomes.json` and `var/screenshots/`; the browser's synthetic database is `var/browser-tests/`. Synthetic run measurements go to `var/runs/synthetic-latest.json`. Use `FACE_DATA_DIR=var/verification-synthetic .venv/bin/python -m scripts.synthetic_run` to keep a verification run separate from your demo data. The populated browser test injects a failed match-job state only into its isolated synthetic database, retries it through the UI and restarts the real worker process; it does not add a fault-injection API to the app.

## Completed C0 studio study

Read [C0 readiness](docs/C0_READINESS_REPORT.md) and [actual studio results](docs/STUDIO_STUDY_REPORT.md). The kit is under `var/assistant-inputs/face-poc-kit/`; all weights, pictures, labels, mappings and detailed evidence remain ignored under `var/c0-studio/`.

```sh
.bootstrap/bin/uv sync --locked --group reference
.venv/bin/python -m scripts.studio_study preflight
.venv/bin/python -m scripts.studio_study all
```

On a fresh run, `all` automates permitted downloads, parity, import/enrollment, label mapping, calibration, freezing, the probe and reports. On this completed run it returns saved results without repeating probe inference. An interrupted stage is not silently replayed. Optional angle references were not used. Do not delete the saved freeze or retune from probe errors.

To inspect the completed probe locally:

```sh
FACE_DATA_DIR=var/c0-studio FACE_MODELS=var/c0-studio/registry.json \
  FACE_CONFIG=var/c0-studio/provisional-config.json .venv/bin/python -m scripts.dev
```

Open **http://127.0.0.1:5177** and select the probe event. Preserve its raw results; do not activate its provisional policy on the calibration event or correct the saved experiment. Stop any existing launcher first. The UI is still an operator simulator, with no production identity verification.

## Real-model setup and evaluation

See [docs/MODELS.md](docs/MODELS.md) for approval, exact artifacts, preprocessing and parity requirements; [docs/EVALUATION.md](docs/EVALUATION.md) for labels and metric semantics; and [docs/IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md) for verified outcomes and remaining work. Never use synthetic constants as a real-model threshold.

Use `FACE_DATA_DIR` for another private data directory, `FACE_CONFIG` for an operating-point JSON and `FACE_MODELS` for a registry. Keep all API/worker/evaluation processes on identical settings. Activating a new configuration for an existing event is explicit:

```sh
FACE_CONFIG=configs/your-approved-operating-point.json .venv/bin/python -m scripts.reindex --event EVENT_ID
```

Start all processes with that same `FACE_CONFIG`. Threshold-only changes reuse embeddings. Reference count/consistency changes invalidate enrollment templates and guest access while retaining reusable photo vectors. Decoder, detector, quality, alignment or model changes use a new namespace. Incompatible enrollment templates require new references and enrollment; they cannot be converted. Old workers cannot publish after configuration activation.

## Privacy and retention

`var/` is private and ignored; it contains originals, derivatives, SQLite/WAL, model binaries if supplied, run reports and parity receipts. Do not place it under `web/`, commit it, or upload it. Access is checked for every gallery request; responses are not cacheable. An already downloaded or in-flight image cannot be recalled.

Participant withdrawal immediately revokes consent, increments the generation, deletes its enrollment, proposals, releases and sessions, and retains only the suppression/audit records. Event photo-face observations are retained independently under the recorded dataset permission. The worker enforces the shorter recorded expiry or a 30-day POC maximum, measured from event creation (a conservative bound on run lifetime). It purges event vectors, links, originals and normalized media at expiry, with tombstones preventing regeneration. Access fails immediately at expiry even if the worker is stopped; physical cleanup occurs at worker restart or its next one-minute maintenance pass. Orphans from interrupted imports are swept after an hour or at event expiry.

The app creates no backups. SQLite secure deletion and WAL truncation are used, but filesystem snapshots, swap and external backups are outside the application's erasure guarantee. Do not back up real POC data without a separate approved destruction policy. Old database copies must not be restored without replaying all subsequent deletion/expiry tombstones; automatic restore is unsupported. OS-level encryption and appropriately restricted local accounts are prerequisites for real data. No claim of forensic erasure is made.
