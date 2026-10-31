"""Reproducible synthetic end-to-end exercise, with private JSON measurements."""
import json
import time

from scripts.evaluate import evaluate
from scripts.make_fixtures import fixture
from server.config import Settings
from server.media import atomic_write
from server.service import Service, uid
from server.worker import Worker


def main():
    started = time.perf_counter()
    s = Service(Settings.environment())
    if not s.provider.synthetic:
        raise ValueError("This command is synthetic-only")
    event = s.create_event("Synthetic pipeline demonstration", "Generated rectangles; no human subjects")
    group = s.import_one(event, fixture(["red", "green"], variant=1), uid(), 0)["photo_id"]
    unknown = s.import_one(event, fixture(["blue"]), uid(), 1)["photo_id"]
    worker = Worker(s)
    while worker.run_once():
        pass
    people = []
    for color in ("red", "green"):
        person = s.consent(event, "Synthetic " + color, "Generated fixture; synthetic consent for pipeline test")["participant_id"]
        s.enroll(event, person, [fixture([color])] * s.op.enrollment_count)
        people.append(person)
    result = evaluate(s, event, {"dataset_version": "synthetic-rectangles-v1", "split_version": "synthetic-debug-v1",
        "split_memberships": [], "enrolled": [{"wedding_id": event, "person_id": p} for p in people],
        "labels": [{"wedding_id": event, "person_id": p, "canonical_photo_id": photo, "present": photo == group,
                    "recognisable": photo == group, "annotation_status": "adjudicated"}
                   for p in people for photo in (group, unknown)]})
    result["measured"]["exercise_wall_seconds"] = time.perf_counter() - started
    atomic_write(s.settings.data_dir, "runs/synthetic-latest.json", json.dumps(result, indent=2).encode())
    print(json.dumps({"status": "SYNTHETIC ONLY", "event_id": event,
                      "artifact": str(s.settings.data_dir / "runs/synthetic-latest.json"),
                      "exercise_wall_seconds": result["measured"]["exercise_wall_seconds"]}))


if __name__ == "__main__":
    main()
