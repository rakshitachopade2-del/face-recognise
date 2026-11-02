"""One local C1 fixed-policy challenge. No calibration, tuning or automatic replay."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Literal

from pydantic import model_validator

from scripts.studio_study import code_identity, drain, load, save, stage_start
from server.challenge import ID, PAIR_PROTOCOL, SHA, Challenge, StrictModel, compare_galleries, safe_input
from server.config import ROOT, OperatingPoint, Settings, digest_json
from server.identity import pipeline_identity, sha_file
from server.providers import RealProvider
from server.service import DomainError, Service

POLICY = {'version': 'c1-predeclared-exploratory-v1', 'provider': 'auraface', 'state': 'provisional',
          'acceptance': .6, 'margin': .3, 'consistency': 1.0, 'enrollment_count': 1,
          'detector_score': .8, 'detector_max_side': 1600, 'min_face_px': 40, 'min_blur': 0,
          'note': 'Predeclared C1 exploratory baseline; no challenge-driven calibration or production claim.',
          'release_enabled': False, 'freeze_id': None}


class Qualification(StrictModel):
    study_sha256: SHA
    reviewed_by: ID
    reviewed_at: ID
    permitted_use_for_all_six_people_and_all_inputs: Literal[True]
    independent_reference_captures: Literal[True]
    fresh_natural_photographs_not_studio_collage_or_generated: Literal[True]
    complete_labels_verified_without_recognition_predictions: Literal[True]
    scope: Literal['one_private_local_c1_challenge']

    @model_validator(mode='before')
    @classmethod
    def explicit_review(cls, values):
        for field in ('permitted_use_for_all_six_people_and_all_inputs', 'independent_reference_captures',
                      'fresh_natural_photographs_not_studio_collage_or_generated',
                      'complete_labels_verified_without_recognition_predictions'):
            if values.get(field) is not True:
                raise ValueError('explicit_boolean_qualification_required:' + field)
        return values


def preflight(inputs):
    study = Challenge.model_validate(load(inputs / 'study.json'))
    if study.input_kind != 'natural_photographs':
        raise ValueError('real_challenge_rejects_synthetic_inputs')
    inventory = study.verify_files(inputs)
    review = Qualification.model_validate(load(inputs / 'qualification.json'))
    if review.study_sha256 != sha_file(inputs / 'study.json'):
        raise ValueError('qualification_not_bound_to_current_study')
    inventory.update({'study.json': sha_file(inputs / 'study.json'),
                      'qualification.json': sha_file(inputs / 'qualification.json')})
    return study, inventory


def artifact_inventory(root):
    # A dedicated, prepared artifact directory: no historical DB or photographs.
    paths = [root/'registry.json', root/'artifact-evidence.json']
    for folder in ('models', 'terms', 'reference-code', 'reference-corpus', 'parity'):
        paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {str(p.relative_to(root)): sha_file(p) for p in sorted(paths)}


def source_inventory():
    result = code_identity()
    for folder, pattern in [('tests', '*.py'), ('web/src', '*'), ('web/tests', '*.ts'), ('configs', '*.json')]:
        for p in (ROOT/folder).rglob(pattern):
            if p.is_file():
                result[str(p.relative_to(ROOT))] = sha_file(p)
    for name in ('web/package.json', 'web/package-lock.json', 'web/playwright.config.ts'):
        result[name] = sha_file(ROOT/name)
    return result


def provider(artifacts, policy):
    return RealProvider(Settings(data_dir=artifacts, registry_path=artifacts/'registry.json'),
                        OperatingPoint.model_validate(policy))


def freeze(inputs, artifacts, root):
    if root.exists():
        raise ValueError('new_empty_run_path_required_existing_evidence_preserved')
    if any(root.is_relative_to(p) or p.is_relative_to(root) for p in (inputs, artifacts)):
        raise ValueError('run_inputs_artifacts_must_be_separate_directories')
    study, inventory = preflight(inputs)
    real = provider(artifacts, POLICY)  # Validates permitted artifacts and independent parity; no photo inference.
    manifest = {'schema': 'c1-fixed-pair-challenge-freeze-v2', 'study_id': study.study_id,
                'inputs_root': str(inputs), 'artifacts_root': str(artifacts), 'inputs': inventory,
                'artifacts': artifact_inventory(artifacts), 'code': source_inventory(), 'pipeline': pipeline_identity(),
                'policy_without_freeze_id': POLICY, 'provider_namespace': real.namespace,
                'parity_receipt_sha256': sha_file(real.parity_path),
                'pair_protocol': PAIR_PROTOCOL, 'pair_opportunities': study.pair_opportunities(),
                'pilot_targets': {'wrong_deliveries': 0, 'presence_recall_minimum': .8,
                                  'shared_photo_retrieval_for_every_present_enrollee': True,
                                  'exact_pair_delivery_for_AB_AC_BC': True, 'no_duplicate_deliveries': True},
                'calibration': 'NONE; predeclared exploratory baseline; no tuning on challenge results'}
    frozen = {'freeze_id': digest_json(manifest), 'manifest': manifest}
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    save(root, 'freeze.json', frozen)
    save(root, 'policy.json', {**POLICY, 'release_enabled': True, 'freeze_id': frozen['freeze_id']})
    return frozen


def verify_freeze(root):
    frozen = load(root/'freeze.json')
    m = frozen['manifest']
    if m.get('schema') != 'c1-fixed-pair-challenge-freeze-v2' or digest_json(m) != frozen['freeze_id']:
        raise ValueError('not_a_valid_c1_freeze')
    if m['code'] != source_inventory() or m['pipeline'] != pipeline_identity() or m['policy_without_freeze_id'] != POLICY:
        raise ValueError('frozen_code_pipeline_or_policy_changed')
    expected_policy = {**POLICY, 'release_enabled': True, 'freeze_id': frozen['freeze_id']}
    if load(root/'policy.json') != expected_policy:
        raise ValueError('frozen_runtime_policy_changed')
    inputs, artifacts = Path(m['inputs_root']), Path(m['artifacts_root'])
    study, inventory = preflight(inputs)
    if inventory != m['inputs'] or artifact_inventory(artifacts) != m['artifacts']:
        raise ValueError('frozen_inputs_or_artifacts_changed')
    if m.get('pair_protocol') != PAIR_PROTOCOL or m.get('pair_opportunities') != study.pair_opportunities():
        raise ValueError('frozen_pair_protocol_or_presence_coverage_changed')
    return frozen, study, inputs, artifacts, expected_policy


def execute(study, inputs, root, service):
    """Shared production import/enroll/worker/gallery paths. Also used by explicitly synthetic tests."""
    if service.provider.synthetic != (study.input_kind == 'synthetic_test_only'):
        raise ValueError('study_provider_kind_mismatch')
    basis = 'C1 documented study basis: ' + study.permitted_use.path
    event = service.create_event('C1 ' + study.study_id, basis, authorization_kind=study.authorization_kind)
    mapping = {'event_id': event, 'people': {}, 'photos': {}, 'enrollments': [], 'imports': []}
    failures = []
    def read_input(asset):
        content = safe_input(inputs, asset.path).read_bytes()
        if hashlib.sha256(content).hexdigest() != asset.sha256:
            raise ValueError('input_changed_before_inference:' + asset.path)
        return content
    def checkpoint():
        save(root, 'mapping.json', mapping)
    checkpoint()
    for source in study.enrolled:
        person = next(p for p in study.people if p.person_id == source)
        pid = service.consent(event, source, 'Documented basis: '+person.permitted_use.path,
                              basis_kind=study.authorization_kind)['participant_id']
        mapping['people'][source] = pid
        ref = next(a for a in study.assets if a.kind == 'reference' and a.depicted_person_ids == [source])
        content = read_input(ref)
        try:
            outcome = service.enroll(event, pid, [content])
        except (DomainError, ValueError) as exc:
            outcome = {'state': 'failed', 'reason': str(exc)}
            failures.append({'stage': 'enrollment', 'person_id': source, **outcome})
        mapping['enrollments'].append({'person_id': source, **outcome})
        checkpoint()
    for i, asset in enumerate(study.gallery):
        outcome = service.import_one(event, read_input(asset), 'c1-challenge', i)
        mapping['imports'].append({'asset_id': asset.asset_id, **outcome})
        if outcome['state'] == 'imported':
            mapping['photos'][asset.asset_id] = outcome['photo_id']
        else:
            failures.append({'stage': 'import', 'asset_id': asset.asset_id, **outcome})
        checkpoint()
    drain_error = None
    try:
        drain(service)
    except TimeoutError:
        drain_error = 'worker_drain_timeout_no_automatic_replay'
        failures.append({'stage': 'worker', 'reason': drain_error})
    with service.db.connect() as db:
        raw = {table: [dict(r) for r in db.execute(f'SELECT * FROM {table} WHERE event_id=?', (event,))]
               for table in ('jobs', 'proposed_matches', 'released_associations')}
        raw['photos'] = [dict(r) for r in db.execute('SELECT id,state FROM photos WHERE event_id=?', (event,))]
        revision = uncorrected_revision(db, event)
    save(root, 'raw-before-corrections.json', raw)
    reverse_photos = {v: k for k, v in mapping['photos'].items()}
    for job in raw['jobs']:
        if job['status'] not in {'complete', 'superseded'}:
            failures.append({'stage': 'processing', 'photo_id': job['photo_id'],
                             'asset_id': reverse_photos.get(job['photo_id']), 'kind': job['kind'],
                             'status': job['status'], 'reason': job['error']})
    actual = []
    observations = {}
    for source, pid in mapping['people'].items():
        try:
            rows = [(source, reverse_photos[r['id']]) for r in service.gallery(event, pid)]
        except DomainError as exc:
            observations[source] = {'status': 'unavailable', 'error': str(exc)}
            failures.append({'stage': 'gallery_access', 'person_id': source, 'reason': str(exc)})
        else:
            actual.extend(rows)
            observations[source] = {'status': 'observed', 'error': None}
    with service.db.connect() as db:
        if uncorrected_revision(db, event) != revision:
            raise ValueError('event_changed_during_guest_gallery_snapshot')
    save(root, 'actual-guest-galleries-before-corrections.json', {
        'source': 'Service.gallery', 'event_id': event, 'revision': revision,
        'gallery_observations': observations,
        'gallery_observation_complete': all(r['status'] == 'observed' for r in observations.values()),
        'deliveries': [{'person_id': p, 'asset_id': a} for p, a in actual]})
    comparison = compare_galleries(study, actual, failures, observations=observations)
    complete = comparison['gallery_observation_complete']
    comparison['status'] = ('incomplete_worker_timeout' if drain_error else
                            'incomplete_gallery_observation' if not complete else 'completed_once')
    comparison['design_executed'] = complete and not drain_error and not any(f['stage'] == 'enrollment' for f in failures)
    comparison['challenge_succeeded'] = False  # Finalized only after controls; metric targets alone are insufficient.
    save(root, 'gallery-comparison.json', comparison)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=['person_id', 'asset_id', 'expected', 'actual', 'actual_count',
                                               'observation_status', 'observation_error'])
    writer.writeheader()
    writer.writerows(comparison['matrix'])
    from server.media import atomic_write
    atomic_write(root, 'gallery-comparison.csv', stream.getvalue().encode())
    if drain_error:
        return comparison  # Do not continue after unsettled challenge work.
    # Operational controls are separate from the 24 photos and 96 labels.
    control_event = service.create_event('C1 non-person controls', 'Supplied non-person control fixtures')
    controls = {}
    for i, name in enumerate(('corrupt', 'no_face')):
        controls[name] = service.import_one(control_event, read_input(getattr(study.controls, name)), 'controls', i)
    duplicate = next(a for a in study.gallery if a.asset_id == study.controls.duplicate_asset_id)
    controls['duplicate'] = service.import_one(event, read_input(duplicate), 'duplicate-control', 0)
    drain(service)
    with service.db.connect() as db:
        controls['detected_faces'] = db.execute('SELECT COUNT(*) FROM faces WHERE event_id=?', (control_event,)).fetchone()[0]
        controls['jobs'] = [dict(r) for r in db.execute('SELECT kind,status,error FROM jobs WHERE event_id=?', (control_event,))]
    controls['passed'] = (controls['corrupt']['state'] == 'terminal_failure' and
                          controls['no_face']['state'] == 'imported' and controls['detected_faces'] == 0 and
                          controls['duplicate']['state'] == 'duplicate' and
                          all(j['status'] in {'complete', 'superseded'} for j in controls['jobs']))
    controls['excluded_from_challenge_denominators'] = True
    save(root, 'controls-result.json', controls)
    comparison['controls'] = controls
    comparison['challenge_succeeded'] = comparison['design_executed'] and comparison['passed_pilot_targets'] and controls['passed']
    save(root, 'gallery-comparison.json', comparison)
    return comparison


def uncorrected_revision(db, event):
    if (db.execute('SELECT 1 FROM rejections WHERE event_id=? LIMIT 1', (event,)).fetchone()
            or db.execute('SELECT 1 FROM participants WHERE event_id=? AND active=0 LIMIT 1', (event,)).fetchone()
            or db.execute("SELECT 1 FROM released_associations WHERE event_id=? AND outcome!='automatic' LIMIT 1", (event,)).fetchone()):
        raise ValueError('operator_corrected_event_cannot_be_scored_as_automatic_delivery')
    return db.execute('SELECT revision FROM events WHERE id=?', (event,)).fetchone()[0]


def run(root):
    if (root/'result.json').exists():
        return load(root/'result.json')  # Read only; no provider, writes or repeated inference.
    if (root/'challenge.started.json').exists():
        raise ValueError('challenge_already_started_partial_evidence_preserved_no_replay')
    frozen, study, inputs, artifacts, policy = verify_freeze(root)
    stage_start(root, 'challenge')  # Exclusive claim, before any challenge inference; crash consumes the run.
    try:
        real = provider(artifacts, policy)
        if real.namespace != frozen['manifest']['provider_namespace'] or sha_file(real.parity_path) != frozen['manifest']['parity_receipt_sha256']:
            raise ValueError('provider_or_parity_changed')
        service = Service(Settings(data_dir=root/'runtime', config_path=root/'policy.json'), provider=real)
        result = execute(study, inputs, root, service)
        result['freeze_id'] = frozen['freeze_id']
        save(root, 'result.json', result)
        return result
    except Exception as exc:
        save(root, 'failure.json', {'status': 'failed_no_automatic_replay', 'exception_type': type(exc).__name__,
                                  'reason': str(exc), 'freeze_id': frozen['freeze_id']})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['preflight', 'freeze', 'run'])
    parser.add_argument('--inputs', type=Path, default=ROOT/'var/assistant-inputs/c1-natural-group-pairs')
    parser.add_argument('--artifacts', type=Path, default=ROOT/'var/c1-artifacts')
    parser.add_argument('--root', type=Path, default=ROOT/'var/c1-challenge')
    args = parser.parse_args()
    inputs, artifacts, root = args.inputs.resolve(), args.artifacts.resolve(), args.root.resolve()
    if args.stage == 'preflight':
        try:
            study, _ = preflight(inputs)
        except (OSError, ValueError) as exc:
            print(json.dumps({'status': 'BLOCKED ON DATA', 'reason': str(exc)}))
            raise SystemExit(2) from exc
        print(json.dumps({'status': 'documented_inputs_qualified', 'photos': len(study.gallery), 'labels': len(study.labels)}))
    elif args.stage == 'freeze':
        print(json.dumps({'status': 'frozen_not_executed', 'freeze_id': freeze(inputs, artifacts, root)['freeze_id']}))
    else:
        result = run(root)
        print(json.dumps({k: result[k] for k in ('status', 'freeze_id', 'evidence_kind', 'passed_pilot_targets')}))


if __name__ == '__main__':
    main()
