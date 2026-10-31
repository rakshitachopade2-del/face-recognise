# Evaluation workflow and boundaries

`server.matching` is the direct baseline shared by the worker and evaluation CLI. It compares one aggregated template per distinct event participant, enforces acceptance and runner-up separation, and abstains. No clustering, rescue, template self-training or probability interpretation is implemented. A face has at most one assigned identity; a photograph can belong to multiple guests. Releases deduplicate `(event, participant, photo)`.

The application records aggregate snapshots separately from evaluation metrics. An app report without independent labels never manufactures accuracy. Synthetic reports have an explicit synthetic flag and cannot enter `real_benchmark_summary`.

## Private dataset manifests

Keep the five CSV manifests specified by document 02 under `var/dataset/`. Required columns are enforced by `scripts/validate_dataset.py`: `media.csv`, `face_annotations.csv`, `person_photo_labels.csv`, `enrollments.csv` and `split_memberships.csv`. Use JSON text for `bbox_xywh`, `true/false/unknown` for truth values, and `development/calibration/test` split names. Identity pseudonyms must be consistent across events to detect cross-event identity leakage. This validator checks declared identifiers, not visual duplicate detection or legal permission.

```sh
.venv/bin/python -m scripts.validate_dataset var/dataset
```

The scoring CLI accepts a private JSON export using app event, participant and canonical photo IDs. Export/convert your independently adjudicated labels to this shape; there is no automatic image-labeling tool. The required CSV files remain the source of dataset provenance and detection truth.

```json
{
  "dataset_version": "authorized-debug-v1",
  "split_version": "debug-split-v1",
  "split_memberships": [{"wedding_id":"EVENT_ID", "person_id":"PERSON_ID", "capture_group_id":"capture-1", "split":"development", "split_version":"debug-split-v1"}],
  "enrolled": [{"wedding_id":"EVENT_ID", "person_id":"PERSON_ID"}],
  "labels": [{"wedding_id":"EVENT_ID", "person_id":"PERSON_ID", "canonical_photo_id":"PHOTO_ID", "present":true, "recognisable":true, "annotation_status":"adjudicated"}],
  "evidence": [{"correct":true}]
}
```

Label all selected frames for each evaluated enrolled identity, including absent participants and images containing authorized unenrolled people. An unlisted pair is not an implicit negative. Mark unknown truth as `present: null`; recognisability must be defined before prediction review. Include missed detections in the person-photo denominator. `evidence` contains separately adjudicated correctness of supporting face observations; omit it when unavailable, rather than implying the evidence face was correct.

```sh
.venv/bin/python -m scripts.evaluate --event EVENT_ID --labels var/dataset/evaluation.json
```

This exploratory command queues a current-configuration rematch through the same worker code and writes `var/runs/evaluation-<run>.json`. It refuses a dataset with cross-event labels, split identifier leakage, unfinished/failed current work, or an event containing Not me corrections; raw automatic evaluation must be frozen before human correction. Use separate private snapshots for assisted outcomes. This CLI is not a sealed-test registry: immutable split freezing, event-aware confidence intervals and sealed-release decision automation are future evaluation work.

## Implemented metric semantics

- Unique person-photo links define truth and deliveries. Duplicated detections/deliveries cannot inflate counts. Co-present unknown bystanders do not make a correct group photo an error.
- Precision is correct delivered links / all delivered links when all deliveries are adjudicated. It is undefined for no deliveries and withheld if any delivery is unresolved; adjudicated-only precision is reported separately. Recall is correct delivered links / all adjudicated true links. No results with true appearances gives zero recall.
- Recognisable recall uses the predefined recognisable true-link denominator. Micro totals, per-person supports, macro means, median, p10, worst supported guest, empty-gallery coverage, wrong links, affected guests, events and wrong-release burst counts are available.
- Preview exposures, evidence-face errors and operator-corrected counts remain separate. Rejections do not improve the raw automatic metric retroactively. The live UI exposes no low-confidence candidate previews to guests.
- Detector recall, open-set evidence-face attribution, condition/subgroup gaps, confidence intervals, full-pipeline miss attribution, real N=300/1,000 quality, scale, billed cost and liveness remain unavailable without the respective measurements. Zero observed synthetic errors is not a release gate.

The smallest real experiment is a few authorized full photographs, including a multi-person frame and an authorized unenrolled participant, plus independently captured enrollment references. Then progress toward the document's 200–500-photo / 20–40-adult debug set. Larger held-out events and genuine distinct N=300/1,000 identities are required for those claims; synthetic identities cannot fill the gap.
