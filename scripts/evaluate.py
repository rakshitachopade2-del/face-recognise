"""Evaluate declared complete truth using the application's automatic publisher."""
import argparse
import json
from pathlib import Path

from server.config import Settings
from server.evaluation import Evaluation
from server.media import atomic_write
from server.metrics import score
from server.reporting import report
from server.service import Service, event_access
from server.worker import Worker


def evaluate(service, event_id, data, input_root=None, rematch=True):
    manifest = Evaluation.model_validate(data).verify(service, input_root)
    if manifest.event_id != event_id:
        raise ValueError('evaluation_event_mismatch')
    with service.db.connect() as db:
        event_access(db, event_id)
        if db.execute('SELECT 1 FROM rejections WHERE event_id=? LIMIT 1', (event_id,)).fetchone():
            raise ValueError('corrected_event_cannot_be_scored_as_raw_automatic_use_frozen_pre_correction_snapshot')
    if rematch:
        with service.db.connect(write=True) as db:
            service.rematch_event(db, event_id)
        worker = Worker(service)
        while worker.run_once():
            pass
    with service.db.connect() as db:
        jobs = [dict(r) for r in db.execute('SELECT photo_id,status,error FROM jobs WHERE event_id=? AND config_id=?',
                                           (event_id, service.config_id))]
        if any(j['status'] not in {'complete', 'superseded', 'terminal_failure'} for j in jobs):
            raise ValueError('evaluation_requires_current_jobs_settled')
        photos = {r['id']: dict(r) for r in db.execute('SELECT id,state,namespace FROM photos WHERE event_id=?', (event_id,))}
        raw = [{'wedding_id': event_id, 'person_id': r['participant_id'], 'canonical_photo_id': r['photo_id']}
               for r in db.execute('SELECT * FROM released_associations WHERE event_id=? AND config_id=?', (event_id, service.config_id))]
    universe, people = set(manifest.canonical_photo_ids), {p.person_id for p in manifest.enrolled}
    delivered = [d for d in raw if d['canonical_photo_id'] in universe and d['person_id'] in people]
    result = report(service, event_id)
    result['metrics'] = score([r.model_dump() for r in manifest.labels], delivered, [p.model_dump() for p in manifest.enrolled])
    result.update(dataset_version=manifest.dataset_version, split_version=manifest.split_version,
                  protocol=manifest.protocol, sealed_test=False, declared_photos=len(universe),
                  evaluated_processed_photos=sum(photos[p]['state'] == 'complete' and photos[p]['namespace'] == service.namespace for p in universe),
                  failures=[j for j in jobs if j['photo_id'] in universe and j['status'] == 'terminal_failure'],
                  excluded_predictions=[d for d in raw if d not in delivered],
                  excluded_app_photos=sorted(set(photos) - universe), raw_deliveries=delivered)
    result['label'] = 'SYNTHETIC METRIC CHECK — NOT RECOGNITION ACCURACY' if service.provider.synthetic else 'EXPLORATORY REAL PHOTO EVALUATION — NO PRODUCTION CLAIM'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--input-root', type=Path)
    args = parser.parse_args()
    service = Service(Settings.environment())
    result = evaluate(service, args.event, json.loads(args.labels.read_text()), args.input_root)
    key = 'runs/evaluation-' + result['run_id'] + '.json'
    atomic_write(service.settings.data_dir, key, json.dumps(result, indent=2).encode())
    print(json.dumps({'label': result['label'], 'artifact': key}))


if __name__ == '__main__':
    main()
