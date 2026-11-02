# Evaluation contract and commands

C0.1 hardening is documented in [C0_1_HARDENING_REPORT.md](C0_1_HARDENING_REPORT.md). The completed C0 study remains historical evidence for its original code. Do not rerun or retune it using this revision. Freeze checks now also verify actual selected input bytes and permission/corpus/calibration hashes before creating a probe provider. Completed-stage reads do not rewrite preflight artifacts.

`server.evaluation.Evaluation` is the authoritative typed run contract. Its generated schema is [evaluation.schema.json](evaluation.schema.json). The supplied studio runner builds, saves and verifies this contract automatically; no new photographs or manual labels are needed for that completed study.

A run declares dataset/split versions, protocol, actual app event ID, exact canonical-photo universe, full enrolled roster (including absent participants), source-to-app person/photo mappings, input assets with paths/hashes/capture groups/splits, and one truth row for every photo × enrolled person. Duplicate or missing rows, dangling mappings, wrong event/version, empty real input inventories, changed source bytes, reference/gallery hash or capture reuse, and inconsistent app photo/reference hashes fail validation. Enrollment failures remain roster members; processing failures remain in the photo denominator. Counts are calculated after processing. Predictions outside the declared universe are excluded explicitly and returned for audit.

JSON `present` and `recognisable` accept only actual `true`, `false`, or `null`, never strings or numeric booleans. IDs must be nonempty. `adjudicated` and explicitly supported `source_verified` truth require a known boolean; `unknown` requires null truth. Recognisable=true requires present=true. Source-verified rows require provenance and the studio protocol; they are not silently relabeled human-adjudicated. For this single-person publisher-coded protocol, each source-verified presence value must agree with the gallery asset’s source identity and source-to-app mapping. An unenrolled source identity requires all evaluated participants to be absent. This constraint does not apply to adjudicated multi-person photographs.

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

The unit is a unique event/person/canonical-photo link. Precision is correct/all delivered links, undefined at no deliveries, and withheld for unresolved deliveries. Recall uses all true links, including missed detections, rejected faces and processing failures. Unknown truth withholds whole-set recall; known-truth-only recall is explicitly separate. Whole-set recognisable recall is null if any presence truth is unknown, or a known positive has unannotated recognisability; a known recognisable subset cannot establish whole-set recall. Missing release-batch evidence makes maximum wrong-release burst null when deliveries exist; event totals are not substituted.

Absent-C errors and the fraction of the six unknown-only photos receiving any false link are separate study outputs. That photo-level rate is not independent face FMR. No face boxes/evidence identities were supplied, so detector recall and evidence-face correctness remain unmeasured. No population confidence intervals, real-event performance, scale, fairness, liveness, cost or production clearance follows from these small correlated studio results.

## C1 exact-pair challenge scoring

C1 uses `server.challenge.Challenge` (schema `c1-natural-group-pairs-v2`) and `scripts.group_challenge`, separate from the historical studio contract above. See [C1_INPUTS.md](C1_INPUTS.md) and [C1_IMPLEMENTATION_REPORT.md](C1_IMPLEMENTATION_REPORT.md). Nothing in this section authorizes rerunning the completed studio probe.

Complete human-verified 4 × 24 presence labels determine eligibility: among 12 group photographs, there must be distinct photos with enrolled presence exactly {A,B}, {A,C}, {B,C}. U/V may also appear, D must remain absent, and ABC does not satisfy a pair-specific requirement. All 96 labels must agree with documented depicted identities. Reference independence, permitted-use/qualification records, input hashes and one-attempt freezes remain mandatory. Preflight validates this contract; freeze records the protocol and exact label-derived candidate photo IDs; run validates them again before inference.

After the existing worker settles, the runner calls `Service.gallery` once for each enrollee, before any operator corrections. It preserves the actual returned rows, including multiplicity, in `actual-guest-galleries-before-corrections.json`. Detected faces, accepted proposals or raw release records alone cannot satisfy the delivery gate. Rejections, withdrawal, nonautomatic release outcomes or event changes during the snapshot block automatic scoring.

For each pair, `pair_delivery` reports qualifying IDs, all four gallery occurrence counts per photo, successful IDs and a pass/fail flag. A photo qualifies for success only when both intended recipients have exactly one occurrence and every absent enrolled recipient has zero. At least one such photo per pair is required. The `pair_delivery_success` conjunction is necessary for `passed_pilot_targets`, which also retains zero wrong links, >=80% recall and per-person group retrieval and now rejects any duplicate delivery. `challenge_succeeded` additionally requires the existing execution and controls gates.

Unique-link recall still uses every human-positive person/photo link. The denominator is always the declared 24 photographs and 96 label rows, even for failed enrollment/import/processing. Duplicate occurrences are reported separately and never inflate unique-link recall. `matrix.actual_count` and the CSV retain occurrence counts; `actual` remains a boolean for compatibility. An additional ABC photo never repairs missing exact-pair delivery. No threshold, detector, quality or model change is part of this protocol fix.

Synthetic regression tests cover the four reported counterexamples, ABC-only/missing-pair input rejection, optional ABC and U/V, partial/wrong/duplicate delivery, candidates without gallery delivery, failures, correction refusal and real CLI orchestration with explicit synthetic provider/preflight substitutes. These checks establish software behavior, not natural-photo recognition accuracy.

### Incomplete gallery observation

All four A/B/C/D guest galleries must be successfully read before any pair-delivery, pilot-target or overall success. `Service.gallery` returning an empty list is an observed empty gallery; `DomainError` is `unavailable` with an error, never an implicit empty list. The scorer requires an explicit observation record for every enrollee and refuses deliveries attributed to an unavailable gallery.

`gallery_observations`, `gallery_observation_complete` and `unobserved_people` are exported with available raw deliveries. An unavailable person's per-photo counts and `matrix.actual`/`actual_count` are null; CSV cells are blank with `observation_status=unavailable` and `observation_error`. Verified zeros remain zeros for successfully read galleries. No row is removed: 24 photographs and 96 presence labels remain the universe.

On incomplete observation, whole-study `presence_recall` is null and `metrics_scope` is `partial_gallery_observation`. Available correct/wrong links remain evidence; `missed_links` contains confirmed misses only from observed galleries. Human-positive links whose galleries could not be read are exported separately as `unobserved_expected_links`, not silently counted as confirmed misses or successes. Per-person actual/wrong/missed lists are null for unavailable people. All success gates are false, including `design_executed`; the outcome is `incomplete_gallery_observation` (or the existing worker-timeout status if that also occurred).

Incomplete outcomes consume the original attempt and are persisted as results. Reinvoking the production command returns the saved incomplete outcome without rereading galleries, starting a provider or rewriting evidence. This correction does not change pair eligibility, numeric thresholds, models, controls or correction/replay protections.
