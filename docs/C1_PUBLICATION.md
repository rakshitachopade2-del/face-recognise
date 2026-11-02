# C1 software publication handoff

Publication preparation: 2 November 2026. Branch: [`poc/c1-software-ready`](https://github.com/rakshitachopade2-del/face-recognise/tree/poc/c1-software-ready), based on `c281bd8fe4d713509f9136776ff708cae8707882`. This milestone includes the accepted C0.1 hardening and C1 source, including exact-pair delivery and incomplete-gallery-observation fixes. Real C1 execution remains **BLOCKED ON DATA**.

## Review and verification provenance

Before publication documentation changes, all 32 changed/new files matched the accepted `C1-Gallery-Observation-Source-Review.zip`. Its SHA-256 is `ea8a71702f7750041fa1b204ee6f63230de3ae97bfbe472054465bf7d7170970`. All 60 tested source/configuration/lockfile/test hashes matched the working tree. [C1_TESTED_SOURCE.json](C1_TESTED_SOURCE.json) preserves that exact inventory; its SHA-256 is `ffdf3006c479079fbdd4b951749408ab53d858665d070a24bea085d936b0fc4e`. Publication changes only the README and adds this handoff and inventory. No implementation was changed for publication.

The recorded backend run passed **195 tests**, with zero failures, errors or skips. This includes **77 focused C1 checks**. Ruff and Python compilation passed. The prior **four browser tests and TypeScript/Vite build passed**; these frontend checks were not rerun for the backend-only observation correction or publication. Verification here checks source identity against those recorded results; it does not claim a fresh test run.

Read [C1_IMPLEMENTATION_REPORT.md](C1_IMPLEMENTATION_REPORT.md) for detailed outcomes, [EVALUATION.md](EVALUATION.md) for scoring and [C1_INPUTS.md](C1_INPUTS.md) for the input contract. Original reports retain their historical descriptions of the then-uncommitted state. This publication handoff supersedes their GitHub availability statements; it does not revise experiment evidence. Private XML, browser artifacts and original review packets remain local.

## What the software verifies

Three distinct group photographs must have exact enrolled presence AB, AC and BC; U/V may appear, D must remain absent and ABC cannot substitute. At least one eligible photograph for each pair must appear exactly once in both intended guest galleries and in no absent enrollee's gallery. Candidate matches alone cannot satisfy this gate.

All four A/B/C/D galleries must be successfully observed. A successful empty D gallery is valid; an unavailable gallery is explicitly incomplete, with unknown counts and errors. Pair, pilot, execution and overall success cannot pass on incomplete observations. All 24 photographs and 96 presence-label rows remain in the evaluation universe. The consumed-attempt and no-replay protections remain intact.

These are synthetic/software results, not natural group-photo recognition accuracy. Models, policy thresholds and historical probe results are unchanged. The historical reports record preservation of all 3,879 inventoried evidence/artifact files; publication does not regenerate or edit them.

## Remaining data blocker

The current scaffold contains none of the required 28 C1 photographs: four independently captured references plus 24 fresh natural gallery photographs (12 group, six solo, six unknown-only). It also needs actual permitted-use records, human-confirmed identities and capture provenance, exact AB/AC/BC coverage, complete human-reviewed labels, separate controls and human qualification bound to the final study hash. Historical FRLL portraits are not substitutes.

The recorded read-only preflight returned exit code 2, `BLOCKED ON DATA`, because finalized `study.json` is absent. Neither `study.json` nor `qualification.json` has been finalized. No real C1 freeze or challenge has been run. Do not infer human qualification from synthetic tests or model predictions.

## Local synthetic app

After the locked dependency setup in the [README](../README.md), run from the repository root:

```sh
FACE_DATA_DIR=var/c1-demo FACE_CONFIG=configs/synthetic.json .venv/bin/python -m scripts.dev
```

Open http://127.0.0.1:5177 while that command is running. The API uses http://127.0.0.1:8017. Keep services private. Missing real inputs do not prevent this synthetic app from running.

For the prepared input scaffold, the permitted read-only check is:

```sh
.venv/bin/python -m scripts.group_challenge preflight \
  --inputs var/assistant-inputs/c1-natural-group-pairs
```

Publication includes source, tests, lockfiles, safe configuration and sanitized documentation. It excludes photographs, private labels, embeddings, databases, model binaries, credentials, identifying logs, review ZIPs, dependency directories and private runtime evidence. Publication does not authorize deployment or execution of the real challenge.
