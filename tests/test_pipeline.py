import sqlite3
import time

import pytest

from scripts.make_fixtures import fixture
from server.service import DomainError, Service, uid
from server.worker import LeaseLost, Worker
from tests.conftest import drain


def event(s, name="Synthetic event"):
    return s.create_event(name, "Synthetic fixtures only")


def person(s, e, color="red"):
    p = s.consent(e, color, "synthetic test consent")["participant_id"]
    s.enroll(e, p, [fixture([color])])
    return p


def photo(s, e, colors=("red",), variant=1):
    return s.import_one(e, fixture(colors, variant=variant), uid(), 0)["photo_id"]


def count(s, table):
    with s.db.connect() as db:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_late_enrollment_late_photo_group_and_unknown(service, worker):
    e = event(service)
    group = photo(service, e, ["red", "green"])
    unknown = photo(service, e, ["blue"])
    drain(worker)
    before = count(service, "faces")
    red, green = person(service, e), person(service, e, "green")
    drain(worker)
    assert [p["id"] for p in service.gallery(e, red)] == [group]
    assert [p["id"] for p in service.gallery(e, green)] == [group]
    assert count(service, "faces") == before  # Late enrollment reuses vectors.
    late = photo(service, e, variant=2)
    drain(worker)
    assert {p["id"] for p in service.gallery(e, red)} == {group, late}
    assert unknown not in {p["id"] for p in service.gallery(e, red)}


def test_duplicate_import_and_batch_corruption(service, worker):
    e = event(service)
    first = service.import_one(e, fixture(), "batch", 0)
    second = service.import_one(e, fixture(), "batch", 1)
    bad = service.import_one(e, b"bad file", "batch", 2)
    assert first["photo_id"] == second["photo_id"]
    assert second["state"] == "duplicate"
    assert bad["state"] == "terminal_failure"
    drain(worker)
    assert count(service, "photos") == 1
    assert count(service, "faces") == 1
    assert len([p for p in (service.settings.data_dir / "media").rglob('*') if p.is_file()]) == 2


def test_two_event_isolation_and_foreign_keys(service, worker):
    a, b = event(service, "A"), event(service, "B")
    p = person(service, a)
    pb = photo(service, b)
    pa = photo(service, a)
    drain(worker)
    assert {p["id"] for p in service.gallery(a, p)} == {pa}
    assert pb != pa
    with pytest.raises(DomainError):
        service.gallery(b, p)
    with pytest.raises(sqlite3.IntegrityError), service.db.connect(write=True) as db:
        db.execute("INSERT INTO rejections VALUES (?,?,?,?)", (b, p, pb, time.time()))


def test_active_consent_before_and_after_inference(service, monkeypatch):
    e = event(service)
    with pytest.raises(DomainError, match="active_purpose"):
        service.enroll(e, "no-consent", [fixture()])
    p = service.consent(e, "red", "synthetic consent")["participant_id"]
    analyze = service.provider.analyze
    def revoke(rgb):
        value = analyze(rgb)
        service.withdraw(e, p)
        return value
    monkeypatch.setattr(service.provider, "analyze", revoke)
    with pytest.raises(DomainError, match="consent_changed"):
        service.enroll(e, p, [fixture()])
    assert count(service, "enrollments") == 0


@pytest.mark.parametrize("contents,error", [([fixture([])], "exactly_one_face"),
    ([fixture(["red", "green"])], "exactly_one_face"), ([fixture(size=5)], "quality"), ([], "exactly_1")])
def test_enrollment_quality(service, contents, error):
    e = event(service)
    p = service.consent(e, "red", "synthetic consent")["participant_id"]
    with pytest.raises(DomainError, match=error):
        service.enroll(e, p, contents)
    assert count(service, "enrollments") == 0


def test_withdrawal_during_matching_cannot_publish(service, worker):
    e = event(service)
    p = person(service, e)
    photo(service, e)
    assert worker.run_once()  # Process; matching is still pending.
    job = worker.claim()
    snapshot = worker.compute_matches(job)
    token = service.session("guest", e, p)
    service.withdraw(e, p)
    worker.publish_matches(job, snapshot)  # Paused stale work resumes after revocation.
    assert count(service, "released_associations") == 0
    assert count(service, "enrollments") == 0
    assert count(service, "proposed_matches") == 0
    assert count(service, "faces") == 1  # Separate event-level face retention.
    with pytest.raises(DomainError):
        service.authorize(token, "guest", e, p)
    with pytest.raises(DomainError):
        service.gallery(e, p)


def test_not_me_suppression_survives_pending_worker_and_restart(service, worker):
    e = event(service)
    p = person(service, e)
    first, second = photo(service, e), photo(service, e, variant=3)
    drain(worker)
    # Capture a fresh decision before a correction. Final publication must consult suppression.
    with service.db.connect(write=True) as db:
        service.queue(db, e, first, "match", 99)
    job = worker.claim()
    snapshot = worker.compute_matches(job)
    service.reject(e, p, first)
    worker.publish_matches(job, snapshot)
    restarted = Service(service.settings)
    assert [r["id"] for r in restarted.gallery(e, p)] == [second]
    assert count(service, "rejections") == 1


def test_expired_lease_recovery_fences_old_owner(service, worker):
    e = event(service)
    photo(service, e)
    first = worker.claim()
    with service.db.connect(write=True) as db:
        db.execute("UPDATE jobs SET lease_expiry=0 WHERE id=?", (first["id"],))
    replacement = Worker(Service(service.settings))
    second = replacement.claim()
    assert second["id"] == first["id"] and second["attempts"] == 2
    with pytest.raises(LeaseLost):
        worker.process(first)
    replacement.process(second)
    replacement.process(second)  # Idempotent replay under the current lease.
    assert count(service, "faces") == 1
    assert worker.heartbeat(first) == 0
    assert replacement.heartbeat(second) == 1


def test_worker_crash_after_publish_does_not_duplicate(service, worker):
    e = event(service)
    photo(service, e)
    job = worker.claim()
    worker.process(job)  # Simulate process death before marking the job complete.
    with service.db.connect(write=True) as db:
        db.execute("UPDATE jobs SET lease_expiry=0 WHERE id=?", (job["id"],))
    drain(Worker(Service(service.settings)))
    assert count(service, "faces") == 1
    with service.db.connect() as db:
        assert db.execute("SELECT attempts FROM jobs WHERE id=?", (job["id"],)).fetchone()[0] == 2


def test_bounded_retry_and_recovery_action(service, worker, monkeypatch):
    e = event(service)
    photo(service, e)
    def fail(rgb):
        raise RuntimeError("PRIVATE filename must not enter logs")
    monkeypatch.setattr(service.provider, "analyze", fail)
    for _ in range(service.settings.max_attempts):
        assert worker.run_once()
        with service.db.connect(write=True) as db:
            db.execute("UPDATE jobs SET available=0")
    assert not worker.run_once()
    with service.db.connect() as db:
        job = db.execute("SELECT * FROM jobs").fetchone()
        assert job["status"] == "terminal_failure"
        assert job["error"] == "processing_error"
    service.retry(e, job["id"])
    with service.db.connect() as db:
        assert db.execute("SELECT attempts FROM jobs").fetchone()[0] == 0


def test_model_version_mismatch_and_new_ambiguous_enrollment(service, worker):
    e = event(service)
    p = person(service, e)
    photo(service, e)
    drain(worker)
    assert len(service.gallery(e, p)) == 1
    person(service, e, "red")  # Same synthetic identity enrolled twice makes the margin ambiguous.
    assert service.gallery(e, p) == []
    drain(worker)
    assert service.gallery(e, p) == []
    with service.db.connect(write=True) as db:
        db.execute("UPDATE enrollments SET namespace='incompatible-v2'")
        service.rematch_event(db, e)
    drain(worker)
    assert count(service, "released_associations") == 0
    with service.db.connect() as db:
        assert db.execute("SELECT reason FROM proposed_matches").fetchone()[0] == "no_compatible_enrollment"


def test_expiry_purges_vectors_and_cannot_reprocess(service, worker):
    e = event(service)
    p = person(service, e)
    photo(service, e)
    drain(worker)
    with service.db.connect(write=True) as db:
        db.execute("UPDATE events SET expires=0 WHERE id=?", (e,))
    with pytest.raises(DomainError):
        service.gallery(e, p)
    service.maintenance()
    assert count(service, "faces") == count(service, "enrollments") == 0
    assert count(service, "deletions") >= 1
    with pytest.raises(DomainError):
        photo(service, e)
    assert not worker.run_once()
    assert not [p for p in (service.settings.data_dir / "media").rglob('*') if p.is_file()]


def test_configuration_change_fences_stale_worker_and_reuses_vectors(service, worker, tmp_path):
    import json

    from server.config import Settings
    e = event(service)
    p = person(service, e)
    photo(service, e)
    worker.run_once()
    stale = worker.claim()
    snapshot = worker.compute_matches(stale)
    config = service.op.model_dump()
    config['version'] = 'new-threshold-policy'
    config_path = tmp_path / 'policy.json'
    config_path.write_text(json.dumps(config))
    updated = Service(Settings(data_dir=service.settings.data_dir, config_path=config_path))
    updated.activate_configuration(e)
    with pytest.raises(LeaseLost):
        worker.publish_matches(stale, snapshot)
    assert count(service, 'faces') == 1
    drain(Worker(updated))
    assert len(updated.gallery(e, p)) == 1
    with pytest.raises(DomainError, match='configuration_changed'):
        service.gallery(e, p)


def test_model_namespace_change_and_return_reuses_valid_cached_faces(service, worker):
    from server.providers import SyntheticProvider

    e = event(service)
    p = person(service, e)
    pic = photo(service, e)
    drain(worker)
    replacement = SyntheticProvider(service.op)
    replacement.namespace += ':different-test-version'
    updated = Service(service.settings, provider=replacement)
    updated.activate_configuration(e)
    drain(Worker(updated))
    assert count(service, 'released_associations') == 0  # Old enrollment is incompatible.
    assert count(service, 'faces') == 2
    service.activate_configuration(e)
    drain(worker)
    assert [r['id'] for r in service.gallery(e, p)] == [pic]
    assert count(service, 'faces') == 2  # Restoring a valid namespace reuses its retained cache.
