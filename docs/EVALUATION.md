# Evaluation contract and commands

`server.evaluation.Evaluation` is the authoritative typed run contract. Its generated schema is [evaluation.schema.json](evaluation.schema.json). The supplied studio runner builds, saves and verifies this contract automatically; no new photographs or manual labels are needed for that completed study.

A run declares dataset/split versions, protocol, actual app event ID, exact canonical-photo universe, full enrolled roster (including absent participants), source-to-app person/photo mappings, input assets with paths/hashes/capture groups/splits, and one truth row for every photo × enrolled person. Duplicate or missing rows, dangling mappings, wrong event/version, empty real input inventories, changed source bytes, reference/gallery hash or capture reuse, and inconsistent app photo/reference hashes fail validation. Enrollment failures remain roster members; processing failures remain in the photo denominator. Counts are calculated after processing. Predictions outside the declared universe are excluded explicitly and returned for audit.

JSON `present` and `recognisable` accept only actual `true`, `false`, or `null`, never strings or numeric booleans. IDs must be nonempty. `adjudicated` and explicitly supported `source_verified` truth require a known boolean; `unknown` requires null truth. Recognisable=true requires present=true. Source-verified rows require provenance and the studio protocol; they are not silently relabeled human-adjudicated.

CSV conversion is explicit, using the same Label model. Fields are `wedding_id,person_id,canonical_photo_id,present,recognisable,annotation_status`, plus optional `label_basis`. Boolean CSV values are exactly `true`, `false`, `unknown`, `null`, or empty for null:

```sh
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from server.evaluation import labels_from_csv
from server.media import atomic_write
root = Path('var/dataset')
atomic_write(root, 'labels.json', json.dumps(labels_from_csv(root / 'labels.csv'), indent=2).encode())
PY
```

This yields label rows, not a complete evaluation manifest. The older five-CSV `scripts.validate_dataset` utility is an inventory helper, not the authoritative experiment preflight. It cannot establish run completeness, permission or recognition accuracy.

## Protocols

- `synthetic`: visibly synthetic pipeline fixtures, never recognition evidence.
- `capture_holdout_exploratory`: the same global people may recur across splits, but capture groups and file hashes must not.
- `event_identity_holdout`: events, global identities, capture groups and hashes must be split-disjoint.
- `studio_identity_split_exploratory`: fixed kit subjects are calibration/probe disjoint; neutral/smiling capture groups differ but sessions do not. Source-verified presence is deliberately supported. Two app events are not two independent real events.

The kit preflight validates the complete cross-cohort asset inventory; per-cohort manifests bind actual app IDs. Hash/capture-ID checks cannot prove visual independence or training-data non-overlap. No sealed-test claim is made.

## Supplied study

```sh
.venv/bin/python -m scripts.studio_study preflight
.venv/bin/python -m scripts.studio_study all
# Optional individual stages, in order, using the same private root:
.venv/bin/python -m scripts.studio_study calibrate
.venv/bin/python -m scripts.studio_study probe
.venv/bin/python -m scripts.studio_study controls
```

Use `--kit PATH --root PATH` for explicitly separate private input/run storage. `all` performs model setup/parity on a fresh run. For individually invoked stages, first run the model/parity commands in [MODELS.md](MODELS.md). Calibration itself is the operator-only diagnostic: all 12 calibration gallery photos and three references, no guest releases. It declares 48 candidates before inference, uses `server.matching.decide`, and chooses zero wrong links, maximum correct links, then higher acceptance and margin. If none is useful, the probe is skipped with releases disabled.

The optimizer reads only calibration labels/vectors. Preflight verifies both kit cohorts; freezing hashes probe bytes without using their content to select policy. The frozen policy, code/model/reference/runtime identities, source/input/label hashes and permission basis are saved before any probe inference. The probe calls actual Service import/enrollment and Worker publication paths once; raw outcomes are saved before any corrections. Started-stage markers prevent silent retries after partial execution. Completed stages return their saved evidence. Keep the run directory intact.

Private artifacts include `preflight.json`, `calibration-procedure.json`, per-cohort mappings/manifests/raw outcomes, all candidate scores/results, `freeze.json`, `provisional-config.json`, `probe-result.json` and `controls-result.json`. The complete private files contain sensitive per-image evidence and stay out of Git. [STUDIO_STUDY_REPORT.md](STUDIO_STUDY_REPORT.md) contains sanitized aggregates.

For a separate generic, fully specified evaluation, use:

```sh
FACE_DATA_DIR=var/your-run FACE_CONFIG=var/your-run/policy.json \
  FACE_MODELS=var/your-run/registry.json .venv/bin/python -m scripts.evaluate \
  --event APP_EVENT_ID --labels var/your-run/evaluation.json --input-root var/your-inputs
```

That generic command rematches through the worker. Do not use it to silently repeat or retune the completed frozen probe. Corrected events are refused as raw automatic evaluation; preserve pre-correction results instead.

## Metric meanings

The unit is a unique event/person/canonical-photo link. Precision is correct/all delivered links, undefined at no deliveries, and withheld for unresolved deliveries. Recall uses all true links, including missed detections, rejected faces and processing failures. Unknown truth withholds whole-set recall; known-truth-only recall is explicitly separate. Recognisable recall is null when recognisability has not been annotated. Missing release-batch evidence makes maximum wrong-release burst null when deliveries exist; event totals are not substituted.

Absent-C errors and the fraction of the six unknown-only photos receiving any false link are separate study outputs. That photo-level rate is not independent face FMR. No face boxes/evidence identities were supplied, so detector recall and evidence-face correctness remain unmeasured. No population confidence intervals, real-event performance, scale, fairness, liveness, cost or production clearance follows from these small correlated studio results.
