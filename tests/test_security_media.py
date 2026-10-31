import io

import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from scripts.make_fixtures import fixture
from server.config import Settings
from server.media import MediaError, decode, safe_path
from tests.conftest import drain
from tests.test_pipeline import event, person, photo


def test_private_storage_cannot_be_the_web_root():
    from server.config import ROOT

    with pytest.raises(ValidationError, match='Private data must be outside'):
        Settings(data_dir=ROOT / 'web')


@pytest.mark.parametrize("overrides", [{"mode": "production"}, {"mode": "public"}, {"host": "0.0.0.0"}, {"host": "192.168.1.1"}])
def test_public_mode_refused(overrides):
    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_origins_sessions_and_private_paths(client, service):
    assert client.post('/api/events', headers={"Origin": "https://evil.example"}, json={"name": "bad", "authorization": "none"}).status_code == 403
    client.headers.pop("Origin")
    assert client.post('/api/session').status_code == 403
    assert client.post('/api/session', headers={"X-Local-Request": "1"}).status_code == 200
    assert client.get('/api/events', headers={"Host": "evil.example"}).status_code == 400
    for path in ('/var/metadata.db', '/media/test.png', '/api/../var/metadata.db'):
        assert client.get(path).status_code == 404
    client.cookies.clear()
    assert client.get('/api/events').status_code == 401
    with pytest.raises(MediaError):
        safe_path(service.settings.data_dir, '../metadata.db')


def test_gallery_sessions_cross_event_not_me_and_withdraw(client, service, worker):
    a, b = event(service), event(service)
    p = person(service, a)
    pic = photo(service, a)
    drain(worker)
    base = f'/api/events/{a}/participants/{p}'
    assert client.get(base + '/gallery').status_code == 401
    assert client.post(base + '/preview').status_code == 200
    response = client.get(base + '/gallery')
    assert response.status_code == 200
    assert 'score' not in response.text and 'bbox' not in response.text
    media = f'{base}/gallery/{pic}/media'
    assert client.get(media).status_code == 200
    assert client.get(media).headers['cache-control'] == 'no-store, private'
    assert client.get(media.replace(a, b)).status_code == 403
    assert client.post(base + f'/gallery/{pic}/reject').status_code == 200
    assert client.get(media).status_code == 403
    assert client.post(base + '/withdraw').status_code == 200
    assert client.get(base + '/gallery').status_code in (401, 403)


def test_diagnostics_require_operator_even_with_guest_session(client, service, worker):
    e = event(service)
    p = person(service, e)
    pic = photo(service, e)
    drain(worker)
    client.post(f'/api/events/{e}/participants/{p}/preview')
    client.cookies.delete('operator_session')
    assert client.get(f'/api/events/{e}/diagnostics').status_code == 401
    assert client.get(f'/api/events/{e}/photos/{pic}/operator-media').status_code == 401
    assert client.get(f'/api/events/{e}/participants/{p}/gallery').status_code == 200


def test_actual_format_orientation_limits_and_heic():
    rgb = np.zeros((20, 40, 3), dtype=np.uint8)
    rgb[:, :20] = (230, 20, 20)
    image = Image.fromarray(rgb)
    out = io.BytesIO()
    exif = image.getexif(); exif[274] = 6
    image.save(out, 'JPEG', exif=exif)
    array, _, fmt, orientation = decode(out.getvalue(), 100000, 10000)
    assert fmt == 'JPEG' and orientation == 6 and array.shape[:2] == (40, 20)
    with pytest.raises(MediaError, match='pixel_limit'):
        decode(out.getvalue(), 100000, 10)
    with pytest.raises(MediaError, match='file_too_large'):
        decode(out.getvalue(), 2, 10000)
    out = io.BytesIO(); image.save(out, 'GIF')
    with pytest.raises(MediaError, match='unsupported_format'):
        decode(out.getvalue(), 100000, 10000)
    out = io.BytesIO(); image.save(out, 'HEIF')
    array, _, fmt, _ = decode(out.getvalue(), 100000, 10000)
    assert fmt == 'HEIF' and array.shape == (40, 20, 3)  # Same orientation=6 EXIF was retained.


def test_upload_batch_api_does_not_trust_name_or_mime(client, service):
    e = event(service)
    response = client.post(f'/api/events/{e}/photos', files=[
        ('files', ('../../evil.jpg', fixture(), 'text/plain')),
        ('files', ('looks-valid.png', b'no image', 'image/png'))])
    assert response.status_code == 200
    assert [r['state'] for r in response.json()['files']] == ['imported', 'terminal_failure']
    assert '../../evil' not in response.text


def test_normal_photo_rejected_by_synthetic_provider(service, worker):
    e = event(service)
    out = io.BytesIO(); Image.new('RGB', (100, 100), 'white').save(out, 'PNG')
    service.import_one(e, out.getvalue(), 'batch', 0)
    drain(worker)
    with service.db.connect() as db:
        assert db.execute('SELECT status,error FROM jobs').fetchone()[:] == (
            'terminal_failure', 'synthetic_fixture_required_use_scripts_make_fixtures')


def test_withdrawal_during_media_read_denies_bytes(client, service, worker, monkeypatch):
    from pathlib import Path

    e = event(service)
    p = person(service, e)
    pic = photo(service, e)
    drain(worker)
    base = f'/api/events/{e}/participants/{p}'
    client.post(base + '/preview')
    original = Path.read_bytes
    def revoke_after_read(path):
        content = original(path)
        if path.suffix == '.png':
            service.withdraw(e, p)
        return content
    monkeypatch.setattr(Path, 'read_bytes', revoke_after_read)
    response = client.get(base + f'/gallery/{pic}/media')
    assert response.status_code in (401, 403)
    assert response.headers['content-type'] == 'application/json'
