# C1 input handoff and local commands

Real execution is **BLOCKED ON DATA**. The supplied FRLL portraits are historical studio inputs, not fresh natural group photographs. Existing C0/C0.1 results and freezes must remain untouched. C1 uses a new run directory and a predeclared policy; it has no calibration or threshold search command.

Generate the incomplete scaffold once from the project root:

```sh
.venv/bin/python -m scripts.make_c1_template --output var/assistant-inputs/c1-natural-group-pairs
```

It refuses an existing destination. It creates draft JSON using `c1-natural-group-pairs-v2`, machine-readable schemas, a `pair-protocol.json` requirements document, empty directories and an `INCOMPLETE.txt` notice. It does not create photographs, consent records, capture evidence or truth. Fill the drafts using documented inputs; save completed versions as `study.json` and `qualification.json`.

```text
var/assistant-inputs/c1-natural-group-pairs/
  study.json                         # finalized study.draft.json
  qualification.json                 # finalized qualification.draft.json
  photos/
    references/{A,B,C,D}.jpg          # one independent capture for each enrollee
    gallery/
      group/G01.jpg ... G12.jpg       # >=2 depicted identities, >=1 enrolled
      solo/S01.jpg ... S06.jpg        # one present enrolled person
      unknown-only/U01.jpg ... U06.jpg # U and/or V; no enrolled person
  controls/
    corrupt.bin                      # deliberately invalid non-person file
    no-face.png                      # independently confirmed no-face image
  provenance/
    permitted-use.md
    annotation.md
    reference-independence.md
    fresh-captures.md
    people/{A,B,C,D,U,V}.md
    captures/{A,B,C,D,G01,...,G12,S01,...,S06,U01,...,U06}.md
```

Names/extensions may be changed in the manifest. All file paths must stay inside this input directory. The duplicate control points to an existing gallery asset, default `G01`; it is an extra import of the exact bytes, not a 25th challenge photo. Corrupt and no-face controls are separate files and excluded from the 24-photo/96-label denominators.

The missing input checklist is:

- Six documented identities: A/B/C enrolled and present, D enrolled and absent from all 24 photos, U/V unenrolled and both present somewhere. Pseudonyms are sufficient. Use protocol pseudonyms A/B/C/D/U/V. Every present enrollee needs pair-specific group-photo opportunities as described below.
- Four single-person reference photographs, one per enrollee. Document capture session/occasion and provenance. No reference may share a file hash or capture group with **any** gallery photo, including another person's photo. Capture IDs must describe the real capture relationship; renaming a file or inventing a new ID does not establish independence.
- Twenty-four distinct fresh natural photographs: 12 group, six solo and six unknown-only, with complete `depicted_person_ids` lists covering everyone depicted. Studio portraits, collages, generated images and the historical FRLL inputs cannot fill this requirement.
- Among the 12 group photographs, require **three distinct natural photographs** whose human-verified enrolled-person presence subsets are exactly **{A,B}**, **{A,C}** and **{B,C}**. U and/or V may also appear. D is absent throughout. ABC photographs may be additional coverage but cannot satisfy any required pair. Do not assign labels simply to meet this design: collect qualifying photographs and independently verify the actual identities.
- Permitted-use evidence covering local biometric enrollment/retrieval, all six people (including unenrolled people), every photograph and controls. Include scope, source, reviewer/date and applicable retention/use limitations. Use `participant_consent` only with actual consent records; use `published_dataset_study_use_basis` only with a documented applicable study-use basis. A previous dataset's permission does not authorize new photographs.
- Human-verified identity mapping, annotation method/reviewer and all 4 × 24 presence labels. `present` must be a JSON boolean; `recognisable` may be null if not adjudicated. Complete all negative rows, including D's 24 absences. Never derive identity or presence from model predictions. Labels must agree with independently documented depicted identities.
- Capture/freshness records establishing reference independence and no prior use of the challenge for calibration, development or probe tuning. Permission and capture records must be nonempty files with SHA-256 hashes.
- `qualification.json`: a human's explicit documented review of permission coverage, reference independence, fresh natural photographs and prediction-independent labels. Set its `study_sha256` to the final `study.json` byte hash. All four review assertions must literally be `true`, after review. This is an operator record, not a cryptographic attestation or automatic legal approval.

Use `shasum -a 256 <file>` for exact byte hashes. Populate every `sha256` in `study.json`, finalize that file, then hash it for `qualification.json`. Editing labels, documentation or photographs invalidates the freeze. Keep private photographs, labels, permissions, mappings, runtime databases and embeddings under ignored `var/`, never in source control.

Run the read-only qualification check:

```sh
.venv/bin/python -m scripts.group_challenge preflight \
  --inputs var/assistant-inputs/c1-natural-group-pairs
```

Missing or invalid inputs produce `BLOCKED ON DATA` with exit code 2. A qualified result means the schema, documented review and byte inventory are consistent. The operator remains responsible for the truth of the evidence. Preflight does not infer faces or modify experiment files.

The local C1 artifact directory is `var/c1-artifacts/`. It contains copies of the permitted YuNet/AuraFace models, terms, pinned reference source, non-person corpus and accepted C0.1 parity receipt. The receipt is validated against the current pipeline/checker identity on provider startup. This is reuse of compatible numerical evidence, **not** reuse of the C0 experiment freeze or a new recognition experiment. If preprocessing or its dependencies change, obtain fresh parity in a separate preparation directory before freezing; never rewrite historical evidence. For a clean machine without these private local artifacts, the existing setup commands are:

```sh
.bootstrap/bin/uv sync --locked --group reference
.venv/bin/python -m scripts.prepare_c0 \
  --kit var/assistant-inputs/face-poc-kit --root var/c1-artifacts
FACE_DATA_DIR=var/c1-artifacts FACE_MODELS=var/c1-artifacts/registry.json \
  FACE_CONFIG=configs/auraface.uncalibrated.json \
  .venv/bin/python -m scripts.check_parity
```

These commands require the existing user-authorized model-pin kit. Do not rerun preparation or parity in a directory bound to a C1 freeze. Once inputs qualify and final code is ready:

```sh
.venv/bin/python -m scripts.group_challenge freeze \
  --inputs var/assistant-inputs/c1-natural-group-pairs \
  --artifacts var/c1-artifacts --root var/c1-challenge
.venv/bin/python -m scripts.group_challenge run --root var/c1-challenge
```

`freeze` requires a nonexistent run directory and performs no photograph inference. It binds C1 source (including untracked source/tests), pipeline identity, exact input and label bytes, permission/capture/qualification records, model/reference/parity artifact inventory, the exact-pair protocol, label-derived qualifying photo IDs and the fixed policy. The new freeze schema is `c1-fixed-pair-challenge-freeze-v2`; earlier C1/C0 freezes are not accepted for execution. The policy is YuNet/AuraFace, direct matching, acceptance 0.6, margin 0.3, enrollment count 1, consistency 1.0, detector score 0.8, maximum side 1600, minimum face 40px and minimum blur 0. No historical operating point is loaded.

`run` validates the freeze before inference and exclusively creates `challenge.started.json`. A partial or failed run cannot be automatically retried, including after a process restart. Preserve its failure and partial evidence; do not delete the marker or switch output directories to get another attempt on the same challenge. A completed invocation only returns saved results. Operational worker retries remain bounded by the existing queue policy; there is no new experiment attempt or policy tuning.

Private outputs include `mapping.json`, `raw-before-corrections.json` (no vectors), `actual-guest-galleries-before-corrections.json`, `gallery-comparison.json`, the complete 96-row `gallery-comparison.csv`, `controls-result.json`, and `result.json` or `failure.json`. Exports retain every declared photo, including import/processing failures, and list expected/actual/wrong/missed links, per-person presence recall, per-pair common-photo delivery and processing failures. `pair_delivery` lists each qualifying photo, occurrence counts in all four guest galleries, successful photo IDs and pair pass/fail. The CSV includes `actual_count` so duplicates are visible. An absent person's recall is undefined (`null`), not 100%. A failed enrollment prevents `design_executed` and `challenge_succeeded`, even if the three metric targets happen to pass. Targets retain zero wrong deliveries and at least 80% presence recall. In addition, for **each** of AB/AC/BC, at least one qualifying photo must appear **exactly once in both intended guest galleries**, and **zero times in every enrolled gallery whose person is absent from that photo** (including the third present enrollee and D). At least one valid photo per pair suffices; additional ABC deliveries cannot substitute. Any duplicate delivery is exposed and fails the no-duplicate gate. Candidate matches, detections and proposed associations do not count as guest delivery. The runner snapshots `Service.gallery` before corrections and refuses correction/withdrawal-contaminated scoring. Pair delivery is necessary for overall success alongside execution, controls and existing metrics; failures never remove photos or label rows. Passing a tiny exploratory challenge is not production validation.


Observation completeness is also mandatory: all four A/B/C/D galleries must be read successfully. A successful empty D gallery is valid; an unavailable D gallery cannot prove zero wrong delivery. `gallery_observations` records status/errors alongside the available raw deliveries. Unavailable counts are null in JSON and blank in CSV with explicit status/error columns. Such a run is incomplete and cannot pass pair, pilot or overall success, even if A/B/C have otherwise perfect delivery. All 24/96 rows remain. Preserve the consumed attempt and incomplete result; do not retry the challenge to replace it.
