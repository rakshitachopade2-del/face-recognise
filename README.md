# Frame — local face retrieval POC

Phases A and B of the supplied handoff, implemented in this workspace. **Operator-controlled identity simulator: no real authentication, verified camera capture or liveness. Do not expose it publicly.**

The default provider accepts generated, visibly synthetic colored rectangles only. It does not recognize people. No model weights or authorized photographs were supplied. Real YuNet + AuraFace and YuNet + SFace adapters are disabled pending exact artifact approval, hash checks and reference preprocessing parity. Real recognition accuracy, cost, throughput and fairness are **NOT MEASURED**.

Repository: [rakshitachopade2-del/face-recognise](https://github.com/rakshitachopade2-del/face-recognise) · Milestone branch: [`poc/phases-a-b`](https://github.com/rakshitachopade2-del/face-recognise/tree/poc/phases-a-b).

Verification on 31 October 2026: **39 backend tests and 3 Chromium browser tests passed**, including a populated two-event workflow. TypeScript checks (including browser test code), Vite build, Ruff and Python compilation passed. The populated checks exercised group-photo sharing, duplicate imports, late enrollment/photos, rejection after retry and worker/browser restart, withdrawal with queued work, and cross-event denial. These are synthetic pipeline results, not recognition accuracy.

## Supported setup

Verified on Apple Silicon macOS with Node 24.13.0, npm 11.6.2 and Python 3.12.16. A system Python 3.9+ is sufficient to bootstrap uv; uv installs the pinned Python 3.12 runtime. Internet is needed for open-source dependencies and the optional browser-test download. No model is downloaded automatically. HEIC support comes from the pinned pillow-heif wheel; unsupported HEIC variants fail per file. Other operating systems have not been verified.

Clone the milestone, then install the locked dependencies:

```sh
git clone --branch poc/phases-a-b https://github.com/rakshitachopade2-del/face-recognise.git
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

## Real-model setup and evaluation

See [docs/MODELS.md](docs/MODELS.md) for approval, exact artifacts, preprocessing and parity requirements; [docs/EVALUATION.md](docs/EVALUATION.md) for labels and metric semantics; and [docs/IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md) for verified outcomes and remaining work. Never use synthetic constants as a real-model threshold.

Use `FACE_DATA_DIR` for another private data directory, `FACE_CONFIG` for an operating-point JSON and `FACE_MODELS` for a registry. Keep all API/worker/evaluation processes on identical settings. Activating a new configuration for an existing event is explicit:

```sh
FACE_CONFIG=configs/your-approved-operating-point.json .venv/bin/python -m scripts.reindex --event EVENT_ID
```

Start all processes with that same `FACE_CONFIG`. Threshold-only changes reuse embeddings. Decoder, detector, quality, alignment or model changes use a new namespace. Incompatible enrollment templates require new references and enrollment; they cannot be converted. Old workers cannot publish after configuration activation.

## Privacy and retention

`var/` is private and ignored; it contains originals, derivatives, SQLite/WAL, model binaries if supplied, run reports and parity receipts. Do not place it under `web/`, commit it, or upload it. Access is checked for every gallery request; responses are not cacheable. An already downloaded or in-flight image cannot be recalled.

Participant withdrawal immediately revokes consent, increments the generation, deletes its enrollment, proposals, releases and sessions, and retains only the suppression/audit records. Event photo-face observations are retained independently under the recorded dataset permission. The worker enforces the shorter recorded expiry or a 30-day POC maximum, measured from event creation (a conservative bound on run lifetime). It purges event vectors, links, originals and normalized media at expiry, with tombstones preventing regeneration. Access fails immediately at expiry even if the worker is stopped; physical cleanup occurs at worker restart or its next one-minute maintenance pass. Orphans from interrupted imports are swept after an hour or at event expiry.

The app creates no backups. SQLite secure deletion and WAL truncation are used, but filesystem snapshots, swap and external backups are outside the application's erasure guarantee. Do not back up real POC data without a separate approved destruction policy. Old database copies must not be restored without replaying all subsequent deletion/expiry tombstones; automatic restore is unsupported. OS-level encryption and appropriately restricted local accounts are prerequisites for real data. No claim of forensic erasure is made.
