# Codex implementation prompt — Face POC, phases A and B

Copy the prompt below into Codex in the local checkout of `https://github.com/rakshitachopade2-del/face-recognise`. Place this handoff folder inside that checkout first. Supply real evaluation photographs separately; never commit them.

---

You are implementing a local proof of concept for finding a consenting wedding guest's photographs from their enrollment selfies. Build the working experiment, not the full wedding application. Implement **phases A and B only**, validate them, and return a structured handoff. Do not proceed to cloud deployment or public guest access.

Read these documents before implementation:

1. `01-Architecture-and-Decisions.md`
2. `02-Evaluation-and-Acceptance.md`
3. This prompt

The architecture and evaluation documents define the decisions and metric semantics. Resolve differences explicitly in your report; never silently choose a convenient interpretation. Earlier supplied product documents are background. Their Expo frontend rules, mock-only restriction, CPU-only mandate, AdaFace choice, and mandatory cluster-first premise do not govern this new POC.

## 1. Inspect and preserve

Inspect the repository, applicable `AGENTS.md` files, git status, installed runtimes, and available hardware first. This repository was observed empty, with no commits, on 31 October 2026; verify its current state rather than assuming it is still empty. Preserve unrelated local changes. Do not overwrite an existing application without reconciling its structure.

Do not commit, push, deploy, purchase services, create cloud resources, send messages, or upload biometric data. Do not run paid APIs. Use official documentation when resolving implementation details. Record assumptions and proceed with reversible local work; ask only for genuinely blocking information.

## 2. Stack and structure

Use React, TypeScript, Vite, and CSS modules for a plain browser interface. Keep components and styles in separate files. Use Python FastAPI, SQLite in WAL mode, a private local data directory, and one worker initially. Use OpenCV for detection and ONNX Runtime for recognition through replaceable provider interfaces. Use exact, event-scoped vector comparisons. Do not add a vector database, Redis, Celery, Kubernetes, native mobile app, or model training.

Suggested structure: `web/`, `server/`, `configs/`, `scripts/`, `tests/`, `docs/`, and an ignored `var/` directory for uploaded media, embeddings, databases, and private run artifacts. Adapt names if the repository already establishes conventions. Pin resolved dependencies in lockfiles. Document one supported clean setup, operating-system prerequisites, and actual runtime versions.

Bind all services to loopback by default. Keep FastAPI documentation, files, and diagnostic endpoints local. Configure a narrow browser origin allowlist and validate origins for mutating requests; do not expose unrestricted CORS or LAN listeners. This is an operator-controlled identity simulator, not real authentication or liveness. Put that limitation visibly in the interface and README. Fail closed if a production/public-access mode is requested without the later security gates.

## 3. Model and data boundaries

Default candidate: **YuNet detection plus AuraFace recognition only**. Keep **SFace** as a comparison provider. Never download or load a bundled age/gender model. Do not substitute InsightFace checkpoints, AdaFace, another model, or a managed API silently.

Before enabling a real provider, create its manifest: official source, exact artifact, SHA-256, code and weights terms, training-data provenance or unresolved questions, permitted experimental use status, production-clearance status, input shape, channel order, normalization, alignment reference, output dimension, and provider version. Follow the architecture document's licensing gates. A permissive repository license is not evidence that every artifact and training dataset is cleared. An unresolved production question does not authorize a prohibited experiment; if POC use is not established, keep that provider disabled and explain precisely what is missing.

Obtain only approved artifacts from explicit sources and verify hashes. Keep model binaries out of git. No implicit first-run network downloads. Implement a preprocessing/parity check against the provider's documented reference behavior and persist its result. Never compare vectors across model or preprocessing versions. Do not quantize in these phases.

Real photographs must be user-supplied and authorized for this experiment, using consenting adults. Do not scrape people, substitute celebrity datasets, or infer age, gender, ethnicity, or emotion. Record dataset processing authorization before analyzing gallery images, and separately require active enrollment consent before creating or using a guest template. Authorized evaluation subjects can deliberately remain unenrolled for open-set testing. Test fixtures and fake embeddings must be visibly synthetic; they cannot establish recognition accuracy. Keep identifying filenames, crops, templates, signed URLs, and per-person results out of public logs and git.

## 4. Phase A — reproducible foundation

Create the repository skeleton, configuration validation, provider interfaces, durable schema, worker entry point, API, and minimal interface shell. Add a deterministic fake provider solely for pipeline and metric tests. Clearly label fake-provider runs and prevent their inclusion in real-model benchmark summaries.

Implement event, photo, detected-face, consent, enrollment, processing-job, proposed-match, released-association, rejection, and run/configuration records. Store event IDs throughout and enforce event-scoped relationships. Separate provisional matches from gallery release. Maintain model/preprocessing/configuration versions and enrollment generations. Require an active, purpose-specific consent record for enrollment creation and use.

Jobs need unique idempotency keys, status, attempts, lease owner, lease expiry, heartbeat, and bounded retry behavior. Recover expired leases after a crash. Use database transactions and atomic file writes so interrupted processing cannot produce duplicate faces or half-published results. Configure SQLite busy timeout and short transactions; keep expensive decoding/inference outside write transactions.

Implement evaluation primitives first. Test person–photo precision/recall, no-result behavior, multiple people in one photo, wrong assignments of unenrolled people, macro/micro aggregation, and rejection handling using small hand-verifiable fixtures. Follow document 02 exactly; do not conflate face accuracy with photograph delivery. Produce machine-readable run metadata and report generation that explicitly marks unavailable measurements.

## 5. Phase B — working real-photo loop

Build these flows end to end:

1. **Create event and import.** Select an event and import JPEG, PNG, and supported HEIC photographs. Preserve originals; normalize EXIF orientation for analysis and derivatives. Validate actual file types and decode limits. Use randomized internal storage keys, safe paths, and event-scoped content hashes. Record corrupt/unsupported files individually without failing the batch. Exact duplicate imports reuse prior work. Do not silently discard visually similar photographs or claim automatic wrong-event detection.
2. **Process and inspect.** Show pending, running, complete, retryable-failure, and terminal-failure states with progress and recovery actions. Detect, align, quality-check, and embed using the active provider version. Preserve unusable-face status without forcing an identity. Operator diagnostics may show boxes and scores; simulated guest galleries must not.
3. **Enroll a test participant.** Select the event, record consent, and supply authorized enrollment images. Reject zero-face, multiple-face, or inadequate inputs with a retry explanation. Support configurable enrollment counts for later 1/3/5-frame comparison. Store no enrollment template without the active consent. Treat image selection as operator enrollment, explicitly not verified camera capture or anti-spoofing.
4. **Retrieve photographs.** Perform exact comparisons only against the event's eligible enrollments. Implement the architecture's direct-matching baseline, ambiguity handling, and abstention. Read thresholds from a versioned operating-point configuration; never invent a universal similarity threshold or probability interpretation. An uncalibrated run must be conspicuously experimental. Keep automatic results, operator-reviewed outcomes, and candidate previews distinct in reports. De-duplicate gallery photographs while permitting legitimate multi-person ownership.
5. **Handle late work.** A new enrollment searches already processed event photographs. Later photographs reach existing eligible participants. Reopening the application or restarting the worker preserves progress. Neither path reprocesses the whole event unnecessarily.
6. **Correct and withdraw.** “Not me” immediately removes the association and records an explicit suppression that retries cannot resurrect. Do not train the model or automatically change global thresholds. Withdrawal immediately disables matching and gallery authorization, invalidates pending work through enrollment generation checks, and performs deletion of enrollment data and links. Apply the documented photo-face retention policy separately. A stale worker may finish computation but cannot publish after revocation. Test this race.

Do not implement automatic cluster expansion, contextual rescue, facial account merging, cloud sync, video, billing, or production notifications. A simple polling UI is sufficient. Keep private storage outside a static public directory; serve gallery content through the API's event/session checks even though the simulator is not production authentication.

## 6. Verification and reporting

Run focused unit/integration tests, backend checks, frontend type checking/build, and a browser smoke test. Verify two-event isolation, consent enforcement, duplicate import, worker crash/restart, late enrollment, late photos, rejected-association persistence, model-version mismatch, and withdrawal during processing. Test public-mode refusal and private-file access paths.

Measure elapsed time, actual hardware, provider versions, processed counts, retry counts, and configured settings. Clearly separate measured values, estimates, and targets. Never manufacture accuracy, liveness, cost, or fairness results. If real images or approved weights are absent, finish the runnable paths and synthetic integration verification, then state which real-model checks remain unrun. Do not claim the feature works on wedding photographs from fake-provider tests.

Finish with `docs/IMPLEMENTATION_REPORT.md` containing: repository state and existing commit SHA if any; files changed; exact setup/run commands; completed phase A/B capabilities; test commands and outcomes; model provenance/clearance status; measurements with artifact paths; known limitations; and the smallest next experiment. List missing user inputs separately from implementation defects. Include a concise terminal summary and stop at this handoff. No automatic commit or push.
