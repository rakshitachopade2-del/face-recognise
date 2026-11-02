"""Pair protocol regressions. Synthetic metadata/rectangles only; no human qualification or real run."""
import copy
import json
import sys
from unittest.mock import Mock

import pytest

from scripts import group_challenge as runner
from server.challenge import PAIR_PROTOCOL, Challenge, compare_galleries
from server.config import digest_json
from server.identity import sha_file
from tests import test_c1 as fixtures

study_input = fixtures.study_input
six_color_service = fixtures.six_color_service


def relabel(data, groups):
    d = copy.deepcopy(data)
    for asset, people in zip(d['assets'][4:16], groups, strict=True):
        asset['depicted_person_ids'] = list(people)
    depicted = {a['asset_id']: a['depicted_person_ids'] for a in d['assets']}
    for row in d['labels']:
        row['present'] = row['person_id'] in depicted[row['asset_id']]
        row['recognisable'] = row['present']
    return d


def truth(s):
    return [(r.person_id, r.asset_id) for r in s.labels if r.present]


@pytest.mark.parametrize('groups', [
    ['AU']*4+['BU']*4+['CV']*4,  # Reported counterexample 1: no enrolled pair opportunities.
    ['ABC']*12,
    ['AB']*6+['AC']*6,
    ['AB']*6+['BC']*6,
    ['AC']*6+['BC']*6,
])
def test_missing_exact_pair_coverage_rejected(study_input, groups):
    with pytest.raises(ValueError, match='missing_exact_enrolled_pair_group_photographs'):
        Challenge.model_validate(relabel(study_input[1], groups))


@pytest.mark.parametrize('pair', ['AB', 'AC', 'BC'])
def test_reported_partial_recipient_counterexamples_fail(study_input, pair):
    s = Challenge.model_validate(relabel(study_input[1], ['AB']*4+['AC']*4+['BC']*4))
    photos = set(s.pair_opportunities()['+'.join(pair)])
    actual = [(p, a) for p, a in truth(s) if not (p == pair[1] and a in photos)]
    result = compare_galleries(s, actual, [], observations=fixtures.observed_galleries(s))
    assert result['presence_recall'] == 26/30  # Aggregate recall still clears 80%; pair gate must fail.
    assert not result['wrong_links'] and len(result['missed_links']) == 4
    assert all(result['shared_photo_retrieval'].values())
    assert not result['pair_delivery']['+'.join(pair)]['passed']
    assert not result['pair_delivery_success'] and not result['passed_pilot_targets']
    assert result['photo_denominator'] == 24 and result['label_denominator'] == 96


@pytest.mark.parametrize('absent', ['C', 'D'])
def test_wrong_recipient_invalidates_qualifying_photo(study_input, absent):
    s = Challenge.model_validate(study_input[1])
    photos = s.pair_opportunities()['A+B']
    result = compare_galleries(s, truth(s)+[(absent, a) for a in photos], [], observations=fixtures.observed_galleries(s))
    assert result['presence_recall'] == 1 and len(result['wrong_links']) == len(photos)
    assert not result['pair_delivery']['A+B']['passed']
    assert not result['passed_pilot_targets']
    assert all(p['guest_gallery_occurrences'][absent] == 1 for p in result['pair_delivery']['A+B']['photos'])


def test_duplicate_delivery_is_not_silently_deduplicated(study_input):
    s = Challenge.model_validate(study_input[1])
    extras = [('A', a) for a in s.pair_opportunities()['A+B']]
    result = compare_galleries(s, truth(s)+extras, [], observations=fixtures.observed_galleries(s))
    assert result['presence_recall'] == 1 and not result['wrong_links']
    assert result['delivery_observation_count'] == 34 and len(result['actual_links']) == 30
    assert len(result['duplicate_deliveries']) == 4
    assert not result['pair_delivery']['A+B']['passed'] and not result['passed_pilot_targets']
    assert any(r['actual_count'] == 2 for r in result['matrix'])


def test_at_least_one_qualifying_photo_per_pair_is_sufficient(study_input):
    s = Challenge.model_validate(study_input[1])
    # One AB photo is only partially delivered; other exact AB photos satisfy the pair.
    first = s.pair_opportunities()['A+B'][0]
    result = compare_galleries(s, [(p, a) for p, a in truth(s) if (p, a) != ('B', first)], [], observations=fixtures.observed_galleries(s))
    assert result['pair_delivery_success'] and result['passed_pilot_targets']
    assert len(result['pair_delivery']['A+B']['successful_photo_ids']) == 3
    assert result['presence_recall'] == 29/30


def test_optional_ABC_does_not_substitute_for_failed_exact_pair_delivery(study_input):
    s = Challenge.model_validate(relabel(study_input[1], ['AB', 'AC', 'BC']+['ABC']*9))
    ab = s.pair_opportunities()['A+B'][0]
    result = compare_galleries(s, [(p, a) for p, a in truth(s) if (p, a) != ('B', ab)], [], observations=fixtures.observed_galleries(s))
    assert result['presence_recall'] > .8 and all(result['shared_photo_retrieval'].values())
    assert not result['pair_delivery_success'] and not result['passed_pilot_targets']
    assert len(result['pair_delivery']['A+B']['qualifying_photo_ids']) == 1


def test_U_V_allowed_and_distinct_pair_photos_derive_from_labels(study_input):
    s = Challenge.model_validate(relabel(study_input[1], ['ABUV', 'ACU', 'BCV']+['ABC']*9))
    pairs = s.pair_opportunities()
    assert pairs == {'A+B': ['p0'], 'A+C': ['p1'], 'B+C': ['p2']}
    result = compare_galleries(s, truth(s), [], observations=fixtures.observed_galleries(s))
    assert result['pair_delivery_success'] and result['passed_pilot_targets']
    assert len(result['matrix']) == 96


def test_labels_cannot_claim_a_pair_absent_from_identity_annotations(study_input):
    d = relabel(study_input[1], ['ABC']*12)
    next(r for r in d['labels'] if r['person_id'] == 'C' and r['asset_id'] == 'p0').update(present=False, recognisable=False)
    with pytest.raises(ValueError, match='label_contradicts_documented'):
        Challenge.model_validate(d)


@pytest.mark.parametrize('stage', ['preflight', 'freeze'])
def test_real_CLI_rejects_missing_pairs_before_permissions_or_provider(study_input, tmp_path, monkeypatch, stage):
    inputs, data = study_input
    (inputs/'study.json').write_text(json.dumps(relabel(data, ['ABC']*12)))
    provider = Mock(side_effect=AssertionError('No real provider may start'))
    monkeypatch.setattr(runner, 'provider', provider)
    out = tmp_path/'no-run'
    monkeypatch.setattr(sys, 'argv',
                        ['group_challenge', stage, '--inputs', str(inputs), '--root', str(out)])
    if stage == 'preflight':
        with pytest.raises(SystemExit) as exc: runner.main()
        assert exc.value.code == 2
    else:
        with pytest.raises(ValueError, match='missing_exact_enrolled_pair'): runner.main()
    provider.assert_not_called()
    assert not out.exists() and not (inputs/'qualification.json').exists()


@pytest.fixture
def synthetic_cli(study_input, six_color_service, tmp_path, monkeypatch):
    """Use real CLI/freeze/worker/gallery code with ONLY a synthetic provider and explicit test preflight."""
    inputs, data = study_input
    (inputs/'study.json').write_text(json.dumps(data))
    def synthetic_preflight(path):
        s = Challenge.model_validate(runner.load(path/'study.json'))
        assert s.input_kind == 'synthetic_test_only'
        return s, {**s.verify_files(path), 'study.json': sha_file(path/'study.json')}
    monkeypatch.setattr(runner, 'preflight', synthetic_preflight)
    artifacts = tmp_path/'test-artifacts'; artifacts.mkdir()
    receipt = artifacts/'test-receipt'; receipt.write_text('SYNTHETIC ONLY; not parity evidence or human qualification')
    provider = six_color_service.provider
    provider.parity_path = receipt
    monkeypatch.setattr(runner, 'provider', Mock(return_value=provider))
    monkeypatch.setattr(runner, 'artifact_inventory', lambda path: {'test-receipt': sha_file(receipt)})
    out = tmp_path/'synthetic-challenge'
    def command(stage):
        monkeypatch.setattr(sys, 'argv', ['group_challenge', stage, '--inputs', str(inputs), '--artifacts', str(artifacts), '--root', str(out)])
        runner.main()
    command('freeze')  # Temporary SYNTHETIC harness only; never a real freeze.
    frozen = runner.load(out/'freeze.json')
    assert frozen['manifest']['pair_protocol'] == PAIR_PROTOCOL
    assert set(frozen['manifest']['pair_opportunities']) == {'A+B', 'A+C', 'B+C'}
    assert not (inputs/'qualification.json').exists()
    return command, out, inputs


@pytest.mark.parametrize('fault', ['none', 'partial', 'wrong', 'duplicate', 'candidates_only'])
def test_CLI_run_scores_guest_galleries_not_candidates(synthetic_cli, monkeypatch, fault):
    command, out, _ = synthetic_cli
    original = runner.Service.gallery
    def observed_gallery(service, event, participant):
        rows = original(service, event, participant)
        mapping = runner.load(out/'mapping.json')
        source = next(p for p, app in mapping['people'].items() if app == participant)
        ab = {mapping['photos']['p'+str(i)] for i in (0, 3, 6, 9)}
        if fault == 'candidates_only':
            return []  # Processing and accepted proposals still exist; no guest-visible delivery.
        if fault == 'partial' and source == 'B':
            return [r for r in rows if r['id'] not in ab]
        if fault == 'duplicate' and source == 'A':
            return rows + [r for r in rows if r['id'] in ab]
        if fault == 'wrong' and source == 'D':
            return rows + [{'id': p} for p in ab]
        return rows
    monkeypatch.setattr(runner.Service, 'gallery', observed_gallery)
    command('run')
    result = runner.load(out/'result.json')
    assert result['challenge_succeeded'] is (fault == 'none')
    assert result['pair_delivery_success'] is (fault == 'none')
    assert result['photo_denominator'] == 24 and result['label_denominator'] == 96
    observations = runner.load(out/'actual-guest-galleries-before-corrections.json')
    assert observations['source'] == 'Service.gallery'
    raw = runner.load(out/'raw-before-corrections.json')
    assert len(raw['released_associations']) == 30
    if fault == 'candidates_only':
        assert raw['proposed_matches'] and not result['actual_links'] and not observations['deliveries']
    if fault == 'duplicate':
        assert result['duplicate_deliveries'] and len(observations['deliveries']) == 34
    assert runner.load(out/'gallery-comparison.json')['pair_delivery'] == result['pair_delivery']


@pytest.mark.parametrize('change', ['protocol', 'coverage', 'presence_bytes'])
def test_frozen_pair_changes_rejected_before_provider(synthetic_cli, monkeypatch, change):
    _, out, inputs = synthetic_cli
    if change == 'presence_bytes':
        d = runner.load(inputs/'study.json')
        d = relabel(d, ['ABC']*12)
        runner.save(inputs, 'study.json', d)
    else:
        f = runner.load(out/'freeze.json')
        f['manifest']['pair_protocol' if change == 'protocol' else 'pair_opportunities'] = {}
        f['freeze_id'] = digest_json(f['manifest'])
        runner.save(out, 'freeze.json', f)
        policy = runner.load(out/'policy.json'); policy['freeze_id'] = f['freeze_id']; runner.save(out, 'policy.json', policy)
    monkeypatch.setattr(runner, 'provider', Mock(side_effect=AssertionError('No inference')))
    with pytest.raises(ValueError): runner.run(out)
    runner.provider.assert_not_called()
    assert not (out/'challenge.started.json').exists()


def test_operator_correction_cannot_hide_missing_or_wrong_delivery(study_input, six_color_service, tmp_path, monkeypatch):
    service = six_color_service
    original = service.gallery
    corrected = False
    def corrected_gallery(event, participant):
        nonlocal corrected
        rows = original(event, participant)
        if not corrected and rows:
            service.reject(event, participant, rows[0]['id'])
            corrected = True
            rows = original(event, participant)
        return rows
    monkeypatch.setattr(service, 'gallery', corrected_gallery)
    with pytest.raises(ValueError, match='operator_corrected_event'):
        runner.execute(Challenge.model_validate(study_input[1]), study_input[0], tmp_path/'out', service)
    assert not (tmp_path/'out/gallery-comparison.json').exists()
