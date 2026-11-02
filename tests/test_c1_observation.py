"""Incomplete gallery observations are not empty galleries. All inputs/provider overrides are synthetic."""
import csv
from unittest.mock import Mock

import pytest

from scripts import group_challenge as runner
from server.challenge import Challenge, compare_galleries
from server.service import DomainError
from tests import test_c1 as fixtures
from tests import test_c1_pairs as pair_fixtures

study_input = fixtures.study_input
six_color_service = fixtures.six_color_service
synthetic_cli = pair_fixtures.synthetic_cli


@pytest.mark.parametrize('failed_person', list('ABCD'))
def test_scorer_marks_unobserved_gallery_unknown(study_input, failed_person):
    study = Challenge.model_validate(study_input[1])
    observed = fixtures.observed_galleries(study)
    observed[failed_person] = {'status': 'unavailable', 'error': 'SYNTHETIC gallery unavailable'}
    actual = [(r.person_id, r.asset_id) for r in study.labels if r.present and r.person_id != failed_person]
    result = compare_galleries(study, actual, [], observations=observed)
    assert not result['gallery_observation_complete']
    assert not result['pair_delivery_success'] and not result['passed_pilot_targets']
    assert not any(result['pilot_targets'].values())
    assert result['presence_recall'] is None
    assert result['photo_denominator'] == 24 and result['label_denominator'] == len(result['matrix']) == 96
    unknown = [r for r in result['matrix'] if r['person_id'] == failed_person]
    assert len(unknown) == 24 and all(r['actual'] is None and r['actual_count'] is None for r in unknown)
    assert all(r['observation_status'] == 'unavailable' and r['observation_error'] for r in unknown)
    for pair in result['pair_delivery'].values():
        assert not pair['passed']
        assert all(p['guest_gallery_occurrences'][failed_person] is None for p in pair['photos'])
    person = next(p for p in result['per_person'] if p['person_id'] == failed_person)
    assert person['actual'] is person['missed'] is person['wrong'] is None
    assert len(result['unobserved_expected_links']) == (0 if failed_person == 'D' else 10)
    assert not result['missed_links']  # Unavailable observations are unknown, not confirmed missed deliveries.


def test_scorer_successful_empty_D_is_verified_empty(study_input):
    study = Challenge.model_validate(study_input[1])
    actual = [(r.person_id, r.asset_id) for r in study.labels if r.present]
    result = compare_galleries(study, actual, [], observations=fixtures.observed_galleries(study))
    assert result['gallery_observation_complete'] and result['pair_delivery_success'] and result['passed_pilot_targets']
    assert result['gallery_observations']['D'] == {'status': 'observed', 'error': None}
    assert all(r['actual_count'] == 0 and r['actual'] is False for r in result['matrix'] if r['person_id'] == 'D')


@pytest.mark.parametrize('failed_person', [None, 'D', 'A', 'B', 'C'])
def test_CLI_exports_observation_and_consumes_attempt(synthetic_cli, monkeypatch, failed_person):
    command, out, _ = synthetic_cli
    original = runner.Service.gallery
    reads = []
    def observed_gallery(service, event, participant):
        people = runner.load(out/'mapping.json')['people']
        source = next(p for p, app in people.items() if app == participant)
        reads.append(source)
        if source == failed_person:
            raise DomainError('SYNTHETIC_gallery_access_failure_' + source, 503)
        return original(service, event, participant)
    monkeypatch.setattr(runner.Service, 'gallery', observed_gallery)
    command('run')
    result = runner.load(out/'result.json')
    raw = runner.load(out/'actual-guest-galleries-before-corrections.json')
    comparison = runner.load(out/'gallery-comparison.json')
    assert reads == list('ABCD')  # Exactly one observation attempt, including unavailable galleries.
    complete = failed_person is None
    assert result['gallery_observation_complete'] is complete
    assert result['pair_delivery_success'] is complete
    assert result['design_executed'] is complete
    assert result['passed_pilot_targets'] is complete
    assert result['challenge_succeeded'] is complete
    assert result['status'] == ('completed_once' if complete else 'incomplete_gallery_observation')
    assert raw['gallery_observations'] == comparison['gallery_observations'] == result['gallery_observations']
    assert raw['gallery_observation_complete'] is complete
    assert result['photo_denominator'] == 24 and result['label_denominator'] == 96
    assert len(raw['deliveries']) == (20 if failed_person in ('A', 'B', 'C') else 30)
    with (out/'gallery-comparison.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 96
    if complete:
        assert result['gallery_observations']['D'] == {'status': 'observed', 'error': None}
        assert all(r['actual_count'] == '0' for r in rows if r['person_id'] == 'D')
    else:
        assert result['gallery_observations'][failed_person]['status'] == 'unavailable'
        assert all(r['actual_count'] == r['actual'] == '' and r['observation_status'] == 'unavailable'
                   and r['observation_error'] for r in rows if r['person_id'] == failed_person)
        assert any(f['stage'] == 'gallery_access' and f['person_id'] == failed_person for f in result['processing_failures'])
        assert result['presence_recall'] is None
        assert not any(result['pilot_targets'].values())
    assert (out/'challenge.started.json').exists()
    before = fixtures.tree(out)
    # Restart semantics: cached incomplete result is returned with no provider, gallery retry or writes.
    monkeypatch.setattr(runner, 'provider', Mock(side_effect=AssertionError('Attempt must not replay')))
    command('run')
    runner.provider.assert_not_called()
    assert reads == list('ABCD') and fixtures.tree(out) == before
    assert runner.load(out/'result.json') == result


def test_observation_metadata_cannot_be_omitted_or_contradict_deliveries(study_input):
    study = Challenge.model_validate(study_input[1])
    with pytest.raises(ValueError, match='explicit_observation_status_required'):
        compare_galleries(study, [], [], observations={})
    with pytest.raises(TypeError):
        compare_galleries(study, [], [])
    observed = fixtures.observed_galleries(study)
    observed['D'] = {'status': 'unavailable', 'error': 'SYNTHETIC unavailable'}
    with pytest.raises(ValueError, match='without_successful_gallery_observation'):
        compare_galleries(study, [('D', 'p0')], [], observations=observed)
