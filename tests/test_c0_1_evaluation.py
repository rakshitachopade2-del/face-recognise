import pytest

from server.evaluation import Evaluation
from server.metrics import score


def test_unknown_presence_withholds_both_whole_recalls():
    labels = [{'wedding_id': 'e', 'person_id': 'p', 'canonical_photo_id': 'known', 'present': True,
               'recognisable': True, 'annotation_status': 'adjudicated'},
              {'wedding_id': 'e', 'person_id': 'p', 'canonical_photo_id': 'unknown', 'present': None,
               'recognisable': None, 'annotation_status': 'unknown'}]
    micro = score(labels, [labels[0]], [{'wedding_id': 'e', 'person_id': 'p'}])['micro']
    assert micro['recall'] is None and micro['recognisable_recall'] is None
    assert micro['known_truth_only_recall'] == 1
    labels[1].update(present=False, annotation_status='adjudicated')
    assert score(labels, [labels[0]], [{'wedding_id': 'e', 'person_id': 'p'}])['micro']['recognisable_recall'] == 1


def studio_manifest(source='A', truth='A', status='source_verified'):
    base = {'wedding_id': 'e', 'split': 'probe', 'split_version': 'v1'}
    return {'dataset_version': 'synthetic-contract-test', 'split_version': 'v1',
            'protocol': 'studio_identity_split_exploratory', 'event_id': 'e', 'canonical_photo_ids': ['photo'],
            'enrolled': [{'wedding_id': 'e', 'person_id': p} for p in ('app-A', 'app-B')],
            'person_mapping': {'A': 'app-A', 'B': 'app-B'}, 'photo_mapping': {'src-photo': 'photo'},
            'assets': [{**base, 'asset_id': 'ref-'+p, 'path': p+'.png', 'sha256': h*64,
                        'person_id': p, 'capture_group_id': 'ref-'+p, 'kind': 'reference'} for p,h in [('A','a'),('B','b')]] +
                      [{**base, 'asset_id': 'src-photo', 'path': 'gallery.png', 'sha256': 'c'*64,
                        'person_id': source, 'capture_group_id': 'gallery', 'kind': 'gallery', 'canonical_photo_id': 'photo'}],
            'labels': [{'wedding_id': 'e', 'person_id': 'app-'+p, 'canonical_photo_id': 'photo',
                        'present': p == truth, 'recognisable': None, 'annotation_status': status,
                        'label_basis': 'literal synthetic publisher-ID example'} for p in ('A','B')]}


def test_single_person_source_truth_rejects_swapped_identity():
    with pytest.raises(ValueError, match='contradicts_gallery_identity'):
        Evaluation.model_validate(studio_manifest(truth='B'))
    Evaluation.model_validate(studio_manifest())
    Evaluation.model_validate(studio_manifest(source='unknown-U', truth=None))
    group = studio_manifest(status='adjudicated')
    for r in group['labels']:
        r['present'] = True
    group['protocol'] = 'capture_holdout_exploratory'
    Evaluation.model_validate(group)  # No scalar-source rule for human-adjudicated group truth.
