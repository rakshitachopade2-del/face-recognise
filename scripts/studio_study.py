"""Bounded kit study. Immutable stages, shared app paths, no probe-driven tuning."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from scripts.evaluate import evaluate
from scripts.prepare_c0 import prepare
from server.config import ROOT, Settings, digest_json
from server.evaluation import Asset, Evaluation, validate_split_assets
from server.identity import pipeline_identity, sha_file
from server.matching import decide
from server.media import atomic_write
from server.metrics import score
from server.reporting import hardware
from server.service import DomainError, Service, eligible
from server.worker import Worker

BASIS = 'published_dataset_study_use_basis'
CITATION = 'FRLL-V5-PUBLISHED-STUDY-USE; DeBruine & Jones (2017), Face Research Lab London Set v5; DOI 10.6084/m9.figshare.5047666.v5; CC BY 4.0; published research basis, not a new app signature'
PROCEDURE = {'acceptance': [.2, .3, .4, .5, .6, .7, .8, .9], 'margin': [0, .05, .1, .15, .2, .3],
             'selection': 'zero observed wrong links; highest correct count; highest threshold; highest margin. Require >=1 correct. Otherwise no useful policy, skip probe.',
             'fixed': {'enrollment_count': 1, 'consistency': 1.0, 'detector_score': .8, 'detector_max_side': 1600, 'min_face_px': 40, 'min_blur': 0}}


def save(root, name, payload):
    atomic_write(root, name, json.dumps(payload, indent=2, allow_nan=False).encode())


def load(path):
    return json.loads(path.read_text())


def code_identity():
    paths = list((ROOT / 'server').glob('*.py')) + list((ROOT / 'scripts').glob('*.py'))
    paths += [ROOT / 'server/schema.sql', ROOT / 'pyproject.toml', ROOT / 'uv.lock', ROOT / 'configs/reference-sources.json']
    return {str(p.relative_to(ROOT)): sha_file(p) for p in sorted(paths)}


def stage_start(root, stage):
    path = root / (stage + '.started.json')
    with path.open('x') as out:
        json.dump({'started_unix': time.time(), 'code': code_identity()}, out)
    path.chmod(0o600)


def preflight(kit, root):
    # Includes incomplete `all` invocations. Never refresh historical evidence.
    if (root / 'freeze.json').exists():
        raise ValueError('frozen_experiment_preflight_is_read_only_use_a_new_directory')
    result = subprocess.run([sys.executable, str(kit / 'tools/verify_bundle.py')], check=True, capture_output=True, text=True)
    study = load(kit / 'dataset/study.json')
    assets = []
    for a in study['assets']:
        if a['kind'] == 'optional_reference':
            continue
        assets.append(Asset(asset_id=a['asset_id'], path=a['path'], sha256=a['sha256'], person_id=a['person_id'],
                            capture_group_id=a['capture_group_id'], wedding_id=a['cohort'], split=a['cohort'],
                            split_version=study['dataset_version'], kind=a['kind']))
    validate_split_assets(assets, study['protocol'])
    evidence = {'bundle_verifier': json.loads(result.stdout), 'protocol': study['protocol'],
                'selected_assets': len(assets), 'optional_references_used': 0, 'sealed_test': False,
                'permission_basis_sha256': sha_file(kit / 'provenance/permission-basis.json'),
                'study_sha256': sha_file(kit / 'dataset/study.json')}
    save(root, 'preflight.json', evidence)
    return study


def settings(root, config):
    return Settings(data_dir=root, config_path=root / config, registry_path=root / 'registry.json')


def drain(service):
    worker = Worker(service)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if worker.run_once():
            continue
        with service.db.connect() as db:
            pending = db.execute("SELECT 1 FROM jobs WHERE config_id=? AND status IN ('pending','running','retryable_failure') LIMIT 1", (service.config_id,)).fetchone()
        if not pending:
            return
        time.sleep(.1)
    raise TimeoutError('worker_drain_timeout_evidence_preserved')


def cohort_run(kit, root, study, cohort_name, service):
    cohort = next(c for c in study['cohorts'] if c['cohort'] == cohort_name)
    all_assets = {a['asset_id']: a for a in study['assets']}
    selected = cohort['default_reference_asset_ids'] + cohort['gallery_asset_ids']
    e = service.create_event('FRLL exploratory ' + cohort_name, CITATION, authorization_kind=BASIS)
    mapping = {'event_id': e, 'people': {}, 'photos': {}, 'imports': [], 'enrollments': []}
    for source in cohort['enrolled_person_ids']:
        p = service.consent(e, source, CITATION, basis_kind=BASIS)['participant_id']
        mapping['people'][source] = p
        refs = [all_assets[a] for a in cohort['default_reference_asset_ids'] if all_assets[a]['person_id'] == source]
        try:
            outcome = service.enroll(e, p, [(kit / a['path']).read_bytes() for a in refs])
        except (DomainError, ValueError) as exc:
            outcome = {'state': 'failed', 'reason': str(exc)}
        mapping['enrollments'].append({'person_id': source, 'references': [a['asset_id'] for a in refs], **outcome})
        save(root, cohort_name + '-mapping.json', mapping)
    for i, asset_id in enumerate(cohort['gallery_asset_ids']):
        outcome = service.import_one(e, (kit / all_assets[asset_id]['path']).read_bytes(), cohort_name, i)
        mapping['imports'].append({'asset_id': asset_id, **outcome})
        if 'photo_id' not in outcome:
            save(root, cohort_name + '-mapping.json', mapping)
            raise ValueError('verified_portrait_import_failed_run_blocked_not_filtered')
        mapping['photos'][asset_id] = outcome['photo_id']
        save(root, cohort_name + '-mapping.json', mapping)
    drain(service)
    # Probe labels are loaded only here, after frozen policy and inference.
    truth = load(kit / cohort['label_file'])
    if truth['dataset_version'] != study['dataset_version'] or set(truth['evaluated_roster']) != set(mapping['people']):
        raise ValueError('label_version_or_roster_mismatch')
    rows = [{'wedding_id': e, 'person_id': mapping['people'][r['person_id']],
             'canonical_photo_id': mapping['photos'][r['asset_id']], **{k: r[k] for k in ('present', 'recognisable', 'annotation_status', 'label_basis')}} for r in truth['labels']]
    assets = []
    for key in selected:
        a = all_assets[key]
        assets.append({'asset_id': key, 'path': a['path'], 'sha256': a['sha256'], 'person_id': a['person_id'],
                       'capture_group_id': a['capture_group_id'], 'wedding_id': e, 'split': cohort_name,
                       'split_version': study['dataset_version'], 'kind': a['kind'], 'canonical_photo_id': mapping['photos'].get(key)})
    manifest = {'dataset_version': study['dataset_version'], 'split_version': study['dataset_version'],
                'protocol': study['protocol'], 'event_id': e, 'canonical_photo_ids': list(mapping['photos'].values()),
                'enrolled': [{'wedding_id': e, 'person_id': p} for p in mapping['people'].values()], 'labels': rows,
                'person_mapping': mapping['people'], 'photo_mapping': mapping['photos'], 'assets': assets, 'sealed_test': False}
    Evaluation.model_validate(manifest).verify(service, kit)
    save(root, cohort_name + '-evaluation.json', manifest)
    with service.db.connect() as db:
        raw = {table: [dict(r) for r in db.execute(f'SELECT * FROM {table} WHERE event_id=?', (e,))]
               for table in ('proposed_matches', 'released_associations', 'jobs')}
        raw['faces'] = [dict(r) for r in db.execute('SELECT photo_id,ordinal,bbox,quality,status FROM faces WHERE event_id=? AND namespace=?', (e, service.namespace))]
    save(root, cohort_name + '-raw-before-corrections.json', raw)
    return e, mapping, manifest, cohort


def extras(metrics, deliveries, mapping, study, cohort):
    unknown_assets = {a['asset_id'] for a in study['assets'] if a['cohort'] == cohort['cohort'] and a['kind'] == 'gallery' and a['person_id'] in cohort['unknown_person_ids']}
    unknown_photos = {mapping['photos'][a] for a in unknown_assets}
    wrong_unknown = [d for d in deliveries if d['canonical_photo_id'] in unknown_photos]
    absent = {mapping['people'][p] for p in cohort['absent_enrolled_person_ids']}
    return {'metrics': metrics, 'unknown_only_photos': len(unknown_photos), 'unknown_only_false_links': len(wrong_unknown),
            'unknown_only_photos_with_false_release': len({d['canonical_photo_id'] for d in wrong_unknown}),
            'unknown_only_photo_false_release_rate': len({d['canonical_photo_id'] for d in wrong_unknown}) / len(unknown_photos) if unknown_photos else None,
            'absent_C_false_links': sum(d['person_id'] in absent for d in deliveries),
            'gallery_capture_groups': len({a['capture_group_id'] for a in study['assets'] if a['cohort'] == cohort['cohort'] and a['kind'] == 'gallery'}),
            'enrollments': mapping['enrollments'], 'photo_denominator': len(mapping['photos']),
            'label_denominator': len(mapping['photos']) * len(mapping['people'])}


def calibrate(kit, root, study):
    if (root / 'calibration-result.json').exists():
        return load(root / 'calibration-result.json')
    stage_start(root, 'calibration')
    started = time.perf_counter()
    save(root, 'calibration-procedure.json', PROCEDURE)  # Before inference or score access.
    config = load(ROOT / 'configs/auraface.uncalibrated.json')
    save(root, 'diagnostic-config.json', config)
    s = Service(settings(root, 'diagnostic-config.json'))
    if s.op.can_release:
        raise ValueError('calibration_requires_release_disabled')
    e, mapping, manifest, cohort = cohort_run(kit, root, study, 'calibration', s)
    with s.db.connect() as db:
        if db.execute('SELECT COUNT(*) FROM released_associations WHERE event_id=?', (e,)).fetchone()[0] != 0:
            raise ValueError('calibration_published_guest_links')
        templates = eligible(db, e, policy_id=s.op.enrollment_policy)
        for t in templates:
            t['vector'] = np.frombuffer(t['vector'], dtype='float32')
        faces = [dict(r) for r in db.execute('SELECT * FROM faces WHERE event_id=? AND namespace=?', (e, s.namespace))]
    candidates, scores = [], []
    for threshold in PROCEDURE['acceptance']:
        for margin in PROCEDURE['margin']:
            op = s.op.model_copy(update={'acceptance': threshold, 'margin': margin})
            links = set()
            for face in faces:
                decision = decide(np.frombuffer(face['vector'], dtype='float32') if face['vector'] else None, s.namespace, templates, op)
                scores.append({'threshold': threshold, 'margin_policy': margin, 'photo_id': face['photo_id'],
                               'face_id': face['id'], **decision.__dict__})
                if decision.accepted:
                    links.add((decision.candidate, face['photo_id']))
            delivered = [{'wedding_id': e, 'person_id': p, 'canonical_photo_id': f} for p, f in sorted(links)]
            metrics = score(manifest['labels'], delivered, manifest['enrolled'])
            candidates.append({'acceptance': threshold, 'margin': margin, **extras(metrics, delivered, mapping, study, cohort)})
    useful = [c for c in candidates if c['metrics']['micro']['wrong'] == 0 and c['metrics']['micro']['correct'] > 0]
    chosen = max(useful, key=lambda c: (c['metrics']['micro']['correct'], c['acceptance'], c['margin'])) if useful else None
    result = {'status': 'useful_provisional_policy' if chosen else 'no_useful_policy_probe_skipped',
              'procedure': PROCEDURE, 'candidates': candidates, 'chosen': chosen, 'event_id': e,
              'wall_seconds': time.perf_counter()-started, 'provider_namespace': s.namespace,
              'processed': evaluate(s, e, manifest, kit, rematch=False), 'hardware': hardware()}
    save(root, 'calibration-private-scores.json', scores)
    save(root, 'calibration-result.json', result)
    if chosen:
        policy = {**config, 'version': 'frll-studio-exploratory-frozen-v1', 'state': 'provisional',
                  'acceptance': chosen['acceptance'], 'margin': chosen['margin'], 'release_enabled': True,
                  'note': 'Provisional closed studio study only; calibration selected; not production validated'}
        freeze = {'protocol': study['protocol'], 'sealed_test': False, 'created_unix': time.time(),
                  'policy_without_freeze_id': policy, 'procedure': PROCEDURE, 'code': code_identity(),
                  'pipeline': pipeline_identity(), 'registry_sha256': sha_file(root / 'registry.json'),
                  'parity_receipt_sha256': sha_file(s.provider.parity_path), 'provider_namespace': s.namespace,
                  'reference_corpus_sha256': sha_file(root / 'reference-corpus/manifest.json'),
                  'calibration_result_sha256': sha_file(root / 'calibration-result.json'),
                  'study_sha256': sha_file(kit / 'dataset/study.json'),
                  'input_hashes': {a['asset_id']: a['sha256'] for a in study['assets'] if a['kind'] != 'optional_reference'},
                  'label_file_hashes': {c['cohort']: sha_file(kit / c['label_file']) for c in study['cohorts']},
                  'permission_basis_sha256': sha_file(kit / 'provenance/permission-basis.json'),
                  'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  'source_diff_sha256': hashlib.sha256(subprocess.check_output(['git', 'diff', 'HEAD'])).hexdigest()}
        freeze_id = digest_json(freeze)
        # Freeze probe input/label BYTES by hash only; optimizer never opens probe labels or vectors.
        save(root, 'freeze.json', {'freeze_id': freeze_id, 'manifest': freeze})
        save(root, 'provisional-config.json', {**policy, 'freeze_id': freeze_id})
    return result


def probe(kit, root, study):
    if (root / 'probe-result.json').exists():
        return load(root / 'probe-result.json')  # No repeated probe inference.
    if not (root / 'freeze.json').exists():
        return {'status': 'skipped_no_frozen_useful_policy'}
    freeze = load(root / 'freeze.json')
    m = freeze['manifest']
    if digest_json(m) != freeze['freeze_id'] or m['code'] != code_identity():
        raise ValueError('freeze_or_executed_code_changed_probe_blocked')
    if sha_file(root / 'registry.json') != m['registry_sha256'] or sha_file(kit / 'dataset/study.json') != m['study_sha256']:
        raise ValueError('frozen_inputs_changed')
    config = load(root / 'provisional-config.json')
    if {**config, 'freeze_id': None} != m['policy_without_freeze_id'] or config['freeze_id'] != freeze['freeze_id']:
        raise ValueError('frozen_policy_changed')
    for c in study['cohorts']:
        if sha_file(kit / c['label_file']) != m['label_file_hashes'][c['cohort']]:
            raise ValueError('frozen_label_bytes_changed')
    # Verify actual frozen bytes before constructing a provider or running inference.
    if study != load(kit / 'dataset/study.json') or m['pipeline'] != pipeline_identity():
        raise ValueError('frozen_study_or_pipeline_changed')
    selected = {a['asset_id']: a for a in study['assets'] if a['kind'] != 'optional_reference'}
    if set(selected) != set(m['input_hashes']):
        raise ValueError('frozen_asset_inventory_changed')
    for asset_id, a in selected.items():
        path = (kit / a['path']).resolve()
        if (not path.is_relative_to(kit.resolve()) or a['sha256'] != m['input_hashes'][asset_id]
                or sha_file(path) != m['input_hashes'][asset_id]):
            raise ValueError('frozen_input_bytes_changed')
    for path, key in ((kit / 'provenance/permission-basis.json', 'permission_basis_sha256'),
                      (root / 'reference-corpus/manifest.json', 'reference_corpus_sha256'),
                      (root / 'calibration-result.json', 'calibration_result_sha256')):
        if sha_file(path) != m[key]:
            raise ValueError('frozen_evidence_changed')
    stage_start(root, 'probe')  # Refuse automatic retries after partial inference.
    started = time.perf_counter()
    s = Service(settings(root, 'provisional-config.json'))
    if sha_file(s.provider.parity_path) != m['parity_receipt_sha256'] or s.namespace != m['provider_namespace']:
        raise ValueError('frozen_parity_or_representation_changed')
    e, mapping, manifest, cohort = cohort_run(kit, root, study, 'probe', s)
    evaluated = evaluate(s, e, manifest, kit, rematch=False)
    result = {'status': 'completed_once_frozen', 'freeze_id': freeze['freeze_id'],
              'wall_seconds': time.perf_counter()-started, 'evaluation': evaluated,
              **extras(evaluated['metrics'], evaluated['raw_deliveries'], mapping, study, cohort)}
    save(root, 'probe-result.json', result)
    return result


def controls(kit, root, study):
    if (root / 'controls-result.json').exists():
        return load(root / 'controls-result.json')
    s = Service(settings(root, 'diagnostic-config.json'))
    e = s.create_event('Non-person operational controls', 'Non-person generated kit patterns')
    cases = load(kit / 'dataset/controls/control-cases.json')['cases']
    results = [s.import_one(e, (kit / c['path']).read_bytes(), 'controls', i) for i, c in enumerate(cases) if 'path' in c]
    drain(s)
    with s.db.connect() as db:
        face_count = db.execute('SELECT COUNT(*) FROM faces WHERE event_id=?', (e,)).fetchone()[0]
    mapping = load(root / 'calibration-mapping.json')
    a = next(a for a in study['assets'] if a['asset_id'] == cases[-1]['asset_id'])
    # Duplicate belongs to calibration event and must queue no new work.
    duplicates = [s.import_one(mapping['event_id'], (kit / a['path']).read_bytes(), 'duplicate-control', i) for i in range(2)]
    result = {'nonperson_imports': results, 'nonperson_detected_faces': face_count, 'duplicate_imports': duplicates,
              'excluded_from_portrait_denominator': True}
    save(root, 'controls-result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['preflight', 'calibrate', 'probe', 'controls', 'all'])
    parser.add_argument('--kit', type=Path, default=ROOT / 'var/assistant-inputs/face-poc-kit')
    parser.add_argument('--root', type=Path, default=ROOT / 'var/c0-studio')
    args = parser.parse_args()
    root, kit = args.root.resolve(), args.kit.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stages = ['calibration', 'probe', 'controls'] if args.stage == 'all' else [
        'calibration' if args.stage == 'calibrate' else args.stage]
    if args.stage != 'preflight' and all((root / (s + '-result.json')).exists() for s in stages):
        print(json.dumps({s: load(root / (s + '-result.json')).get('status', 'recorded') for s in stages}))
        return  # Historical completed results are read-only, including their preflight evidence.
    study = preflight(kit, root)
    if args.stage == 'preflight':
        print(json.dumps({'status': 'preflight_passed', 'selected_portraits': 30, 'gallery_photos': 24}))
        return
    if args.stage == 'all' and not (root / 'calibration.started.json').exists():
        prepare(kit, root)
        env = {**os.environ, 'FACE_DATA_DIR': str(root), 'FACE_MODELS': str(root / 'registry.json'),
               'FACE_CONFIG': str(ROOT / 'configs/auraface.uncalibrated.json')}
        subprocess.run([sys.executable, '-m', 'scripts.check_parity'], env=env, check=True)
    result = {}
    if args.stage in {'all', 'calibrate'}:
        result['calibration'] = calibrate(kit, root, study)['status']
    if args.stage in {'all', 'probe'}:
        result['probe'] = probe(kit, root, study)['status']
    if args.stage in {'all', 'controls'}:
        controls(kit, root, study)
        result['controls'] = 'recorded'
    print(json.dumps(result))


if __name__ == '__main__':
    main()
