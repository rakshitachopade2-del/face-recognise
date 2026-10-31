# Face POC handoff

Prepared 31 October 2026 for https://github.com/rakshitachopade2-del/face-recognise.

**Decision:** build the local experiment now. Start with YuNet + AuraFace and compare SFace. Begin with direct matching and require evidence before adding grouping. No claim of production accuracy or cost has been made.

## Files

| File | Purpose |
|---|---|
| [01-Architecture-and-Decisions.md](01-Architecture-and-Decisions.md) | Product behavior, stack, model shortlist, matching, production direction and twelve-stage evidence register |
| [02-Evaluation-and-Acceptance.md](02-Evaluation-and-Acceptance.md) | Data manifests, held-out tests, metrics, security and release gates |
| [03-Codex-Build-Prompt.md](03-Codex-Build-Prompt.md) | Copy into local Codex to implement the foundation and usable local photo loop |
| [04-Cost-and-Provider-Comparison.md](04-Cost-and-Provider-Comparison.md) | Cost boundaries, managed API correctness, illustrative scenarios and measurement rules |
| [tools/cost_scenarios.py](tools/cost_scenarios.py) | Reproduces the illustrative cost arithmetic with Python's standard library |
| [05-Illustrative-Cost-Scenarios.json](05-Illustrative-Cost-Scenarios.json) | Script output; hypothetical rates/FX, not a benchmark or quote |

## Use with Codex

1. Open the repository in VS Code and copy this folder into it, for example under `docs/face-poc/`.
2. Give Codex the contents of `03-Codex-Build-Prompt.md`. Its document filenames refer to this handoff directory. Tell it the directory path if you used a different location.
3. Let it implement phases A and B locally and produce `docs/IMPLEMENTATION_REPORT.md`. No cloud account is needed for the foundation. Approved model artifacts and authorized test images are needed to run real recognition.
4. Return that implementation report plus changed code or a repository commit link for review. If code is to be reviewed from GitHub, it needs to be pushed from your own coding environment; this handoff does not grant automatic push or deployment instructions.
5. Run the evaluation chapter before selecting a production model. Failed experiments and missing data are useful results; fabricated success metrics are not.

## What to prepare when testing starts

- A small authorized starter photo set: roughly 200–500 images of 20–40 consenting adults, including group photos and difficult conditions.
- Separate enrollment references from those adults; include some consented evaluation participants who are deliberately not enrolled, and some enrolled people absent from the gallery.
- The machine on which Codex will run; it records actual CPU, memory, operating system and runtime versions.

These are practical first inputs, not proof of quality at 300–1,000 guests. Neither paying for cloud infrastructure nor assembling the complete validation corpus is necessary to begin the local implementation.

## Evidence status

Reviewed all eleven supplied planning documents across architecture, requirements, model selection and evaluation workstreams. The initial files remain unchanged. Git clone/status inspection found no repository commits on `main`. Primary publisher documentation was checked for model licensing and managed-provider behavior. No participant photographs, model inference, enrollment attacks, or cloud benchmarks were run.

The source files are the user's context; this package is the revised POC plan. Runtime measurements and license approval records must be produced during implementation/evaluation. The original claims of ₹31 compute, guaranteed cluster gains, or ready commercial clearance are not adopted.
