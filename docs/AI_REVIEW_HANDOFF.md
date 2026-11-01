# AI review handoff

Review branch: [poc/c0-studio-study](https://github.com/rakshitachopade2-del/face-recognise/tree/poc/c0-studio-study).

The user authorized publishing this branch so another AI can assess the implemented milestone and recommend the next step. No merge, deployment or paid services are authorized.

## Read first

1. [C0_READINESS_REPORT.md](C0_READINESS_REPORT.md): fixes, test results, independent parity and recorded failures.
2. [STUDIO_STUDY_REPORT.md](STUDIO_STUDY_REPORT.md): calibration candidates, frozen policy, probe outcomes and limitations.
3. [MODELS.md](MODELS.md) and [EVALUATION.md](EVALUATION.md): model gates and evaluation contract.
4. Actual source and tests, especially `server/evaluation.py`, `server/providers.py`, `server/parity.py`, `server/service.py`, `server/worker.py`, `scripts/check_parity.py`, `scripts/reference_runner.py`, `scripts/studio_study.py` and `tests/test_c0.py`.

Executed source/test commit: `888e79db463d977e48c9bb2e8a14d5d5ae16795f`. Measurement-report commit: `216d10ccb5d56a2cfc3e1f11f6f517c50c1443d0`. Later publication documentation does not change the frozen inference/evaluation code.

Reported checks: 63 backend tests, 3 browser tests, lint, compilation and frontend build passed; eight non-person parity cases, seven negative controls and three same-engine detector-wrapper checks passed. Initial parity failures were preserved and fixed without relaxed tolerances.

Calibration and probe each included 12 gallery photographs, 36 full presence labels and six true links. Selected acceptance 0.6 / margin 0.3 yielded six correct links, zero wrong and zero missed in each cohort. Calibration published no guest links; the frozen probe published six. These are small, correlated studio results with `sealed_test=false`, not real-event validation or production approval.

Photographs, private labels/mappings, per-image scores, embeddings, databases, weights and detailed runtime evidence remain excluded from Git. A source review can check implementation, but must not claim independently reproduced private experimental results without the inputs. Do not retune or rerun the exposed probe as a new held-out test.

## Request for the reviewing AI

Assess what the evidence supports, identify any implementation/evaluation gaps, and recommend ONE bounded next milestone with required inputs and measurable acceptance/failure criteria. Return a copy-and-paste implementation prompt that preserves existing work and private evidence. Distinguish reported test/results evidence from checks you independently perform. If additional evidence is essential, specify exactly what is needed rather than requesting private photographs or embeddings unnecessarily.
