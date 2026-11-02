import pytest
from fastapi.testclient import TestClient

from scripts.make_fixtures import fixture
from server.api import create_app
from server.service import DomainError
from server.worker import LeaseLost, Worker
from tests.conftest import drain
from tests.test_c0 import change
from tests.test_pipeline import count, event, person, photo


def test_old_service_withdrawal_uses_active_worker(service, worker, tmp_path):
    e = event(service)
    red, green = person(service, e), person(service, e, 'green')
    image = photo(service, e, ['red', 'green'])
    drain(worker)
    with service.db.connect(write=True) as db:
        service.rematch_event(db, e)
    stale_job = worker.claim()
    stale_snapshot = worker.compute_matches(stale_job)
    current = change(service, tmp_path, version='B', acceptance=.98)
    current.activate_configuration(e)
    drain(Worker(current))
    assert len(current.gallery(e, green)) == 1
    jobs_before = count(current, 'faces')
    service.withdraw(e, red)
    with pytest.raises(DomainError):
        current.session('guest', e, red)
    assert drain(Worker(current)) == 1
    assert [r['id'] for r in current.gallery(e, green)] == [image]
    assert count(current, 'faces') == jobs_before
    with pytest.raises(LeaseLost):
        worker.publish_matches(stale_job, stale_snapshot)
    assert [r['id'] for r in current.gallery(e, green)] == [image]
    with current.db.connect() as db:
        assert not db.execute("SELECT 1 FROM jobs WHERE status='pending'").fetchone()
        assert db.execute("SELECT COUNT(*) FROM jobs WHERE kind='process'").fetchone()[0] == 1


def test_maintenance_routes_two_event_configs_without_inference(service, worker, tmp_path):
    a, b = event(service, 'A'), event(service, 'B')
    withdrawing, remaining = {}, {}
    for e in (a, b):
        withdrawing[e], remaining[e] = person(service, e), person(service, e, 'green')
        photo(service, e, ['red', 'green'])
    drain(worker)
    current = change(service, tmp_path, version='B')
    current.activate_configuration(b)
    drain(Worker(current))
    with service.db.connect(write=True) as db:
        for e in (a, b):
            db.execute('UPDATE consents SET expires=0 WHERE participant_id=?', (withdrawing[e],))
    service.maintenance()
    assert drain(worker) == 1
    assert drain(Worker(current)) == 1
    for e, s in ((a, service), (b, current)):
        assert len(s.gallery(e, remaining[e])) == 1
        with pytest.raises(DomainError):
            s.gallery(e, withdrawing[e])
    with service.db.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs WHERE kind='process'").fetchone()[0] == 2
        assert not db.execute("SELECT 1 FROM jobs WHERE status='pending'").fetchone()


def test_api_readiness_policy_invalidation_reenrollment_and_expiry(service, worker, tmp_path):
    e = event(service)
    p = person(service, e)
    photo(service, e)
    drain(worker)
    current = change(service, tmp_path, enrollment_count=3)
    current.activate_configuration(e)
    drain(Worker(current))
    with TestClient(create_app(current.settings, current), base_url='http://127.0.0.1:8017') as client:
        client.headers['Origin'] = 'http://127.0.0.1:5177'
        client.post('/api/session')
        status = client.get(f'/api/events/{e}/status').json()['participants'][0]
        assert status['enrolled'] is False and status['gallery_ready'] is False
        assert 'reference policy changed' in status['readiness_reason']
        assert client.post(f'/api/events/{e}/participants/{p}/preview').status_code == 403
        current.enroll(e, p, [fixture(['red'])] * 3)
        drain(Worker(current))
        status = client.get(f'/api/events/{e}/status').json()['participants'][0]
        assert status['enrolled'] is True and status['gallery_ready'] is True
        assert status['readiness_reason'] is None
        assert client.post(f'/api/events/{e}/participants/{p}/preview').status_code == 200
        with current.db.connect(write=True) as db:
            db.execute('UPDATE consents SET expires=0 WHERE participant_id=?', (p,))
        status = client.get(f'/api/events/{e}/status').json()['participants'][0]
        assert status['enrolled'] is False and status['gallery_ready'] is False
        assert 'permission expired' in status['readiness_reason']
        assert client.post(f'/api/events/{e}/participants/{p}/preview').status_code == 403
