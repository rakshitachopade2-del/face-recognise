import copy

import numpy as np
import pytest

from scripts.evaluate import evaluate
from scripts.make_fixtures import fixture
from server.config import Settings
from server.evaluation import Asset, Evaluation, Label, labels_from_csv, validate_split_assets
from server.metrics import score
from server.parity import validate_case
from server.providers import RealProvider, SyntheticProvider
from server.service import DomainError, Service
from server.worker import Worker
from tests.conftest import drain
from tests.test_pipeline import count, event, person, photo


def change(service, tmp_path, **changes):
    op = service.op.model_copy(update=changes)
    path = tmp_path / 'changed.json'
    path.write_text(op.model_dump_json())
    return Service(Settings(data_dir=service.settings.data_dir, config_path=path), provider=service.provider)


@pytest.mark.parametrize('changes', [{'enrollment_count': 3}, {'consistency': .75}])
def test_enrollment_policy_invalidates_without_reprocessing(service, worker, tmp_path, changes):
    e = event(service)
    p = person(service, e)
    photo(service, e)
    drain(worker)
    token = service.session('guest', e, p)
    new = change(service, tmp_path, **changes)
    new.activate_configuration(e)
    drain(Worker(new))
    assert count(new, 'faces') == 1
    assert count(new, 'released_associations') == 0
    for call in (lambda: new.session('guest', e, p), lambda: new.gallery(e, p), lambda: new.authorize(token, 'guest', e, p)):
        with pytest.raises(DomainError):
            call()
    new.enroll(e, p, [fixture(['red'])] * new.op.enrollment_count)
    drain(Worker(new))
    assert len(new.gallery(e, p)) == 1


def test_real_release_gate_identical_single_template_direct_publication(service, worker, tmp_path):
    e = event(service)
    p = person(service, e)
    photo(service, e)
    drain(worker)
    # Synthetic vectors test the real policy boundary, not real recognition.
    blocked = change(service, tmp_path, provider='auraface', acceptance=1.0, margin=2.0,
                     release_enabled=False, state='uncalibrated')
    blocked.activate_configuration(e)
    w = Worker(blocked)
    job = w.claim()
    snapshot = w.compute_matches(job)
    assert snapshot[1][0][1].accepted  # Numeric placeholders are not a gate.
    w.publish_matches(job, snapshot)
    assert count(blocked, 'proposed_matches') == 1
    assert count(blocked, 'released_associations') == 0
    with pytest.raises(DomainError, match='release_disabled'):
        blocked.gallery(e, p)
    with pytest.raises(DomainError, match='release_disabled'):
        blocked.session('guest', e, p)


def test_coalesces_twenty_enrollments_five_photos(service, worker):
    e = event(service)
    for i in range(5):
        photo(service, e, variant=i+1)
    drain(worker)
    for _ in range(20):
        person(service, e)
    with service.db.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs WHERE kind='match' AND status='pending'").fetchone()[0] == 5
        assert db.execute("SELECT COUNT(*) FROM jobs WHERE status='superseded'").fetchone()[0] == 95
    assert drain(worker) == 5


def test_pending_process_survives_enrollment_and_stale_match_cannot_delete_new(service, worker):
    e = event(service)
    pic = photo(service, e)
    p = person(service, e)
    assert worker.run_once()
    old = worker.claim()
    snapshot = worker.compute_matches(old)
    person(service, e, 'green')
    drain(worker)
    assert [r['id'] for r in service.gallery(e, p)] == [pic]
    worker.publish_matches(old, snapshot)
    assert [r['id'] for r in service.gallery(e, p)] == [pic]


def test_whole_event_expiry_creates_no_rematches(service, worker):
    e = event(service)
    for i in range(5):
        photo(service, e, variant=i+1)
        person(service, e)
    drain(worker)
    before = count(service, 'jobs')
    with service.db.connect(write=True) as db:
        db.execute('UPDATE events SET expires=0')
        db.execute('UPDATE consents SET expires=0')
    service.maintenance()
    assert count(service, 'jobs') == before
    assert count(service, 'enrollments') == 0


@pytest.mark.parametrize('shape', [(101, 1001), (1, 10000), (10000, 1)])
def test_rounded_resize_geometry_and_extreme_inputs(shape):
    op = Settings().operating_point().model_copy(update={'detector_max_side': 320, 'min_face_px': 99999})
    provider = RealProvider.__new__(RealProvider)
    provider.op = op

    class Detector:
        def setInputSize(self, size):
            self.size = size
        def detect(self, bgr):
            assert min(bgr.shape[:2]) >= 1
            return None, np.array([[1, 2, 3, 4] + [1, 2] * 5 + [.99]], dtype='float32')
    provider.detector = Detector()
    face = provider._analyze(np.zeros((*shape, 3), dtype='uint8'))[0]
    w, h = provider.detector.size
    np.testing.assert_allclose(face.bbox, [shape[1]/w, 2*shape[0]/h, 3*shape[1]/w, 4*shape[0]/h])
    np.testing.assert_allclose(face.quality['landmarks'][0], [shape[1]/w, 2*shape[0]/h])


def test_synthetic_quality_setting_in_namespace():
    op = Settings().operating_point()
    assert SyntheticProvider(op).namespace != SyntheticProvider(op.model_copy(update={'min_face_px': 99})).namespace


def label(**changes):
    return dict(wedding_id='e', person_id='p', canonical_photo_id='f', present=True,
                recognisable=None, annotation_status='adjudicated', **changes)


@pytest.mark.parametrize('bad', ['false', 0, 1, 'true', float('nan')])
def test_strict_json_boolean(bad):
    data = label()
    data['present'] = bad
    with pytest.raises(ValueError):
        Label.model_validate(data)


def test_unknown_recall_and_csv_conversion(tmp_path):
    data = label()
    data.update(present=None, annotation_status='unknown')
    result = score([data], [], [{'wedding_id': 'e', 'person_id': 'p'}])
    assert result['micro']['recall'] is None
    p = tmp_path / 'labels.csv'
    p.write_text('wedding_id,person_id,canonical_photo_id,present,recognisable,annotation_status\ne,p,f,false,null,adjudicated\n')
    assert labels_from_csv(p)[0]['present'] is False
    data.update(present=False, recognisable=True, annotation_status='adjudicated')
    with pytest.raises(ValueError):
        Label.model_validate(data)


def manifest_for(service, e, p, f):
    return {'dataset_version': 'synthetic-v1', 'split_version': 'v1', 'protocol': 'synthetic', 'event_id': e,
                'canonical_photo_ids': [f], 'enrolled': [{'wedding_id': e, 'person_id': p}],
                'person_mapping': {'source-person': p}, 'photo_mapping': {'source-photo': f}, 'assets': [],
                'labels': [{'wedding_id': e, 'person_id': p, 'canonical_photo_id': f, 'present': True,
                             'recognisable': True, 'annotation_status': 'adjudicated'}]}


def test_manifest_completeness_and_failed_photo_denominator(service, worker, monkeypatch):
    e = event(service)
    p = person(service, e)
    f = photo(service, e)
    data = manifest_for(service, e, p, f)
    for field, value in [('labels', []), ('person_mapping', {}), ('canonical_photo_ids', [f, f]), ('assets', []), ('photo_mapping', {})]:
        bad = copy.deepcopy(data)
        bad[field] = value
        if field == 'assets':
            bad['protocol'] = 'capture_holdout_exploratory'
        with pytest.raises(ValueError):
            Evaluation.model_validate(bad)
    def fail(rgb):
        from server.providers import ProviderError
        raise ProviderError('intentional_test_failure')
    monkeypatch.setattr(service.provider, 'analyze', fail)
    result = evaluate(service, e, data)
    assert result['declared_photos'] == 1
    assert result['evaluated_processed_photos'] == 0
    assert result['metrics']['micro']['recall'] == 0
    assert len(result['failures']) == 1


def test_split_protocols_enforce_real_files_and_identities():
    base = {'asset_id': 'one', 'path': 'one.jpg', 'sha256': 'a'*64, 'person_id': 'global-person',
                'capture_group_id': 'capture-one', 'wedding_id': 'e1', 'split': 'calibration', 'split_version': 'v1', 'kind': 'reference'}
    a = Asset(**base)
    b = Asset(**{**base, 'asset_id': 'two', 'path': 'two.jpg', 'sha256': 'b'*64,
                 'capture_group_id': 'capture-two', 'wedding_id': 'e2', 'split': 'test'})
    validate_split_assets([a, b], 'capture_holdout_exploratory')
    with pytest.raises(ValueError, match='person_id'):
        validate_split_assets([a, b], 'event_identity_holdout')
    with pytest.raises(ValueError, match='capture_group'):
        validate_split_assets([a, b.model_copy(update={'capture_group_id': a.capture_group_id})], 'capture_holdout_exploratory')


def test_reference_validation_forbids_broadcasting_and_nonfinite():
    case = {'rgb': np.zeros((112,112,3), dtype='uint8'), 'landmarks': np.ones((5,2), dtype='float32'),
                'crop': np.zeros((112,112,3), dtype='uint8'), 'tensor': np.zeros((1,3,112,112), dtype='float32'),
                'embedding': np.ones(512, dtype='float32')/np.sqrt(np.float32(512)), 'raw_embedding': np.ones(512, dtype='float32')}
    validate_case(case)
    for key, bad in [('tensor', np.zeros((1,1,112,112), dtype='float32')),
                     ('embedding', np.full(512, np.nan, dtype='float32')),
                     ('raw_embedding', np.zeros(512, dtype='float32'))]:
        with pytest.raises(ValueError):
            validate_case({**case, key: bad})


def test_dataset_authorization_is_not_new_participant_consent(service):
    e = service.create_event('dataset study', 'publisher citation', authorization_kind='published_dataset_study_use_basis')
    with pytest.raises(DomainError, match='basis_kind'):
        service.consent(e, 'pseudonym', 'new app signature')
    service.consent(e, 'pseudonym', 'publisher citation', basis_kind='published_dataset_study_use_basis')
    with service.db.connect() as db:
        assert db.execute('SELECT basis_kind FROM consents').fetchone()[0] == 'published_dataset_study_use_basis'


def test_source_verified_is_explicit_and_never_infers_recognisability():
    data = label()
    data.update(annotation_status='source_verified', label_basis='publisher member identity')
    metrics = score([data], [data], [{'wedding_id': 'e', 'person_id': 'p'}])
    assert metrics['micro']['correct'] == 1
    assert metrics['micro']['recall'] == 1
    assert metrics['micro']['recognisable_recall'] is None
    data['label_basis'] = None
    with pytest.raises(ValueError):
        Label.model_validate(data)


def test_mapping_hashes_references_and_complete_processing(service, tmp_path):
    import hashlib

    e = event(service)
    p = person(service, e)
    f = photo(service, e)
    ref, gallery = fixture(['red']), fixture(['red'], variant=1)
    (tmp_path / 'reference.png').write_bytes(ref)
    (tmp_path / 'gallery.png').write_bytes(gallery)
    data = manifest_for(service, e, p, f)
    base = {'person_id': 'source-person', 'wedding_id': e, 'split': 'calibration', 'split_version': 'v1'}
    data['assets'] = [{**base, 'asset_id': 'ref', 'path': 'reference.png', 'sha256': hashlib.sha256(ref).hexdigest(),
                       'capture_group_id': 'reference-capture', 'kind': 'reference'},
                      {**base, 'asset_id': 'source-photo', 'path': 'gallery.png', 'sha256': hashlib.sha256(gallery).hexdigest(),
                       'capture_group_id': 'gallery-capture', 'kind': 'gallery', 'canonical_photo_id': f}]
    Evaluation.model_validate(data).verify(service, tmp_path)
    before = evaluate(service, e, data, tmp_path)
    assert before['evaluated_processed_photos'] == 1  # Counted after the worker ran.
    assert before['metrics']['micro']['recall'] == 1
    for field in ('sha256', 'capture_group_id'):
        bad = copy.deepcopy(data)
        bad['assets'][0][field] = bad['assets'][1][field]
        with pytest.raises(ValueError, match='reference_gallery_reuse'):
            Evaluation.model_validate(bad)
    bad = copy.deepcopy(data)
    bad['assets'][0]['split_version'] = 'different'
    with pytest.raises(ValueError, match='version'):
        Evaluation.model_validate(bad)
    (tmp_path / 'gallery.png').write_bytes(b'changed')
    with pytest.raises(ValueError, match='input_hash_mismatch'):
        Evaluation.model_validate(data).verify(service, tmp_path)
    (tmp_path / 'gallery.png').write_bytes(gallery)
    with service.db.connect(write=True) as db:
        db.execute("UPDATE photos SET hash=? WHERE id=?", ('0'*64, f))
    with pytest.raises(ValueError, match='app_photo_hash_mismatch'):
        Evaluation.model_validate(data).verify(service, tmp_path)


def test_predictions_outside_declared_universe_are_exposed(service, worker):
    e = event(service)
    p = person(service, e)
    first, second = photo(service, e), photo(service, e, variant=2)
    drain(worker)
    data = manifest_for(service, e, p, first)
    result = evaluate(service, e, data, rematch=False)
    assert result['metrics']['micro']['delivered_links'] == 1
    assert result['excluded_app_photos'] == [second]
    assert len(result['excluded_predictions']) == 1


def test_changed_inference_code_invalidates_representation(monkeypatch):
    from server import identity
    old = identity.pipeline_identity()
    old_namespace = SyntheticProvider(Settings().operating_point()).namespace
    real_sha = identity.sha_file
    monkeypatch.setattr(identity, 'sha_file', lambda p: '0'*64 if p.name == 'providers.py' else real_sha(p))
    assert identity.pipeline_identity() != old
    assert SyntheticProvider(Settings().operating_point()).namespace != old_namespace
