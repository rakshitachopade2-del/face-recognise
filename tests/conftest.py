import pytest
from fastapi.testclient import TestClient

from server.api import create_app
from server.config import Settings
from server.service import Service
from server.worker import Worker


@pytest.fixture
def service(tmp_path):
    return Service(Settings(data_dir=tmp_path / "private"))


@pytest.fixture
def worker(service):
    return Worker(service)


@pytest.fixture
def client(service):
    with TestClient(create_app(service.settings, service), base_url="http://127.0.0.1:8017") as client:
        client.headers["Origin"] = "http://127.0.0.1:5177"
        assert client.post("/api/session").status_code == 200
        yield client


def drain(worker):
    count = 0
    while worker.run_once():
        count += 1
        assert count < 200
    return count
