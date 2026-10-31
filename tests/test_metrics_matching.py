import numpy as np
import pytest

from server.config import Settings
from server.matching import aggregate, decide
from server.metrics import score, validate_splits
from server.providers import REFERENCE, ProviderError, align, unit
from server.reporting import real_benchmark_summary


def row(person, photo, present=True, recognisable=True, **extra):
    return dict(wedding_id='event', person_id=person, canonical_photo_id=photo,
                present=present, recognisable=recognisable, annotation_status='adjudicated', **extra)


def roster(*people):
    return [{'wedding_id': 'event', 'person_id': p} for p in people]


def test_hand_verifiable_group_wrong_unknown_empty_and_rejection():
    labels = [row('a','group'), row('b','group'), row('a','solo'), row('a','unknown',False),
              row('b','unknown',False), row('c','absent-from-results')]
    delivered = [row('a','group'), row('a','group'), row('b','group'), row('a','unknown')]
    result = score(labels, delivered, roster('a','b','c'), previews=[row('b','unknown')],
                   evidence=[{'correct': False}, {'correct': True}], rejections=[row('a','unknown')])
    assert result['micro']['correct'] == 2
    assert result['micro']['wrong'] == 1
    assert result['micro']['precision'] == pytest.approx(2/3)
    assert result['micro']['recall'] == .5
    assert result['macro_precision']['mean'] == .75
    assert result['macro_recall']['mean'] == .5
    assert result['macro_recall']['worst'] == 0
    assert result['empty_gallery_coverage'] == pytest.approx(1/3)
    assert result['previews']['wrong_known_links'] == 1
    assert result['evidence']['wrong'] == 1
    assert result['operator_corrected']['wrong_known_links'] == 0
    assert result['affected_guests'] == result['events_with_wrong_links'] == 1


def test_no_results_is_undefined_precision_and_zero_recall():
    result = score([row('a','one')], [], roster('a'))
    assert result['micro']['precision'] is None
    assert result['micro']['recall'] == 0
    assert result['macro_precision']['mean'] is None
    result = score([], [], roster('absent'))
    assert result['micro']['recall'] is None
    assert result['micro']['precision'] is None


def test_recognisable_denominator_unknowns_wrong_evidence_and_bursts():
    labels = [row('a','one'), row('a','hard',recognisable=False), row('a','wrong',False)]
    result = score(labels, [row('a','one'), row('a','wrong'), row('a','unlabelled')], roster('a'), evidence=[{'correct':False}])
    assert result['micro']['recall'] == .5
    assert result['micro']['recognisable_recall'] == 1
    assert result['unresolved_deliveries'] == 1
    assert result['maximum_wrong_release_burst'] == 1
    assert result['evidence']['wrong'] == 1


def test_split_leakage_and_synthetic_benchmark_refusal():
    for key in ('person_id','capture_group_id'):
        with pytest.raises(ValueError, match='split_leakage'):
            validate_splits([{key:'shared','split':'development'}, {key:'shared','split':'test'}])
    with pytest.raises(ValueError, match='synthetic'):
        real_benchmark_summary([{'synthetic':True}])


def test_exact_policy_threshold_margin_namespace_single_guest():
    op = Settings().operating_point()
    a = {'participant_id':'a','generation':1,'namespace':'v1','vector':np.array([1,0,0])}
    assert decide([1,0,0], 'v1', [a], op).accepted
    assert not decide([0,1,0], 'v1', [a], op).accepted
    assert not decide([1,0,0], 'v2', [a], op).accepted
    assert decide([1,0,0], 'v1', [a,{**a,'participant_id':'b'}], op).reason == 'ambiguous'
    assert decide(None, 'v1', [a], op).reason == 'unusable_face'
    with pytest.raises(ProviderError):
        unit([float('nan'),1])
    with pytest.raises(ProviderError):
        unit([0,0])


def test_three_frame_consistency_and_normalized_average():
    op = Settings().operating_point().model_copy(update={'enrollment_count':3})
    np.testing.assert_allclose(aggregate([[1,0],[1,0],[1,0]],op),[1,0])
    with pytest.raises(ProviderError, match='inconsistent'):
        aggregate([[1,0],[1,0],[0,1]],op)


def test_alignment_identity_and_invalid_landmarks():
    image = np.random.default_rng(7).integers(0,255,(112,112,3),dtype=np.uint8)
    np.testing.assert_array_equal(align(image,REFERENCE),image)
    with pytest.raises(ProviderError,match='degenerate'):
        align(image,np.zeros((5,2)))


def test_real_provider_cannot_start_with_unapproved_manifest(tmp_path):
    from server.providers import create_provider
    s = Settings(data_dir=tmp_path, config_path=Settings().config_path.with_name('auraface.uncalibrated.json'))
    with pytest.raises(ProviderError, match='model_disabled'):
        create_provider(s,s.operating_point())


def test_artifact_hash_and_path_gates_without_loading_a_model(tmp_path):
    import hashlib

    from server.media import MediaError
    from server.providers import verified_artifact
    artifact = tmp_path / 'synthetic-artifact.bin'
    artifact.write_bytes(b'SYNTHETIC HASH TEST - NOT MODEL WEIGHTS')
    entry = {key: 'synthetic test only' for key in ('source','revision','code_terms','weights_terms',
             'permission_basis','training_provenance','production_use_status','contract')}
    entry.update(evaluation_use_status='approved', artifact=artifact.name, sha256='0' * 64)
    with pytest.raises(ProviderError,match='hash_mismatch'):
        verified_artifact(entry,tmp_path)
    entry['sha256'] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert verified_artifact(entry,tmp_path) == artifact
    entry['artifact'] = '../escape.bin'
    with pytest.raises(MediaError,match='unsafe_path'):
        verified_artifact(entry,tmp_path)


def test_unresolved_deliveries_do_not_inflate_precision():
    result = score([row('a','known')],[row('a','known'),row('a','unknown')],roster('a'))
    assert result['micro']['precision'] is None
    assert result['micro']['adjudicated_only_precision'] == 1
    assert result['macro_precision']['defined_guests'] == 0
