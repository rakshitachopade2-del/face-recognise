"""Evaluate the application's automatic outcomes against private, adjudicated link labels."""
import argparse
import json
from pathlib import Path

from server.config import Settings
from server.media import atomic_write
from server.metrics import score, validate_splits
from server.reporting import report
from server.service import Service, event_access
from server.worker import Worker


def evaluate(service, event_id, data):
    validate_splits(data["split_memberships"])
    with service.db.connect() as db:
        event_access(db, event_id)
        if any(r["wedding_id"] != event_id for r in data["labels"] + data["enrolled"]):
            raise ValueError("evaluation_event_mismatch")
        if db.execute("SELECT 1 FROM rejections WHERE event_id=? LIMIT 1", (event_id,)).fetchone():
            raise ValueError("corrected_event_cannot_be_scored_as_raw_automatic_use_frozen_pre_correction_snapshot")
        photos = db.execute("SELECT id FROM photos WHERE event_id=? AND state='complete' AND namespace=?",
                            (event_id, service.namespace)).fetchall()
    # Same policy and transactional publisher as the app. No separate evaluation-only matcher.
    with service.db.connect(write=True) as db:
        service.rematch_event(db, event_id)
    worker = Worker(service)
    while worker.run_once():
        pass
    with service.db.connect() as db:
        pending = db.execute("SELECT 1 FROM jobs WHERE event_id=? AND status!='complete' AND config_id=? LIMIT 1",
                             (event_id, service.config_id)).fetchone()
        if pending:
            raise ValueError("evaluation_requires_all_current_jobs_complete")
        delivered = [{"wedding_id": event_id, "person_id": r["participant_id"], "canonical_photo_id": r["photo_id"]}
                     for r in db.execute("SELECT * FROM released_associations WHERE event_id=? AND config_id=?",
                                         (event_id, service.config_id))]
    result = report(service, event_id)
    result["metrics"] = score(data["labels"], delivered, data["enrolled"], evidence=data.get("evidence", []))
    result["dataset_version"] = data["dataset_version"]
    result["split_version"] = data["split_version"]
    result["evaluated_processed_photos"] = len(photos)
    result["label"] = "SYNTHETIC METRIC CHECK — NOT RECOGNITION ACCURACY" if service.provider.synthetic else "EXPLORATORY EVALUATION — NO RELEASE CLAIM"
    result["sealed_test"] = False
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--labels", type=Path, required=True, help="Private JSON; see docs/EVALUATION.md")
    args = parser.parse_args()
    service = Service(Settings.environment())
    result = evaluate(service, args.event, json.loads(args.labels.read_text()))
    key = "runs/evaluation-" + result["run_id"] + ".json"
    atomic_write(service.settings.data_dir, key, json.dumps(result, indent=2).encode())
    print(json.dumps({"label": result["label"], "artifact": key}))


if __name__ == "__main__":
    main()
