"""Create an explicitly incomplete C1 input scaffold; never invent truth or permissions."""
import argparse
import json
from pathlib import Path

from scripts.group_challenge import Qualification
from server.challenge import PAIR_PROTOCOL, Challenge


def template(root):
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    for directory in ('photos/references', 'photos/gallery/group', 'photos/gallery/solo',
                      'photos/gallery/unknown-only', 'controls', 'provenance/people', 'provenance/captures'):
        (root/directory).mkdir(parents=True, mode=0o700)
    def evidence(path):
        return {'path': path, 'sha256': ''}
    people = [{'person_id': p, 'role': role, 'permitted_use': evidence(f'provenance/people/{p}.md')}
              for p, role in zip('ABCDUV', ['enrolled_present']*3 + ['enrolled_absent'] + ['unenrolled']*2)]
    assets = []
    for kind, names, folder in [('reference', list('ABCD'), 'photos/references'),
                                ('group', [f'G{i:02}' for i in range(1, 13)], 'photos/gallery/group'),
                                ('solo', [f'S{i:02}' for i in range(1, 7)], 'photos/gallery/solo'),
                                ('unknown_only', [f'U{i:02}' for i in range(1, 7)], 'photos/gallery/unknown-only')]:
        for name in names:
            assets.append({**evidence(f'{folder}/{name}.jpg'), 'asset_id': name, 'kind': kind,
                           'depicted_person_ids': [name] if kind == 'reference' else [], 'capture_group_id': '',
                           'capture_record': evidence(f'provenance/captures/{name}.md')})
    draft = {'schema_version': 'c1-natural-group-pairs-v2', 'study_id': '', 'input_kind': 'natural_photographs',
             'authorization_kind': 'participant_consent', 'permitted_use': evidence('provenance/permitted-use.md'),
             'annotation_record': evidence('provenance/annotation.md'),
             'capture_independence_record': evidence('provenance/reference-independence.md'),
             'fresh_capture_record': evidence('provenance/fresh-captures.md'), 'people': people, 'assets': assets,
             'labels': [{'person_id': p, 'asset_id': a['asset_id'], 'present': None, 'recognisable': None}
                        for p in 'ABCD' for a in assets if a['kind'] != 'reference'],
             'controls': {'duplicate_asset_id': 'G01', 'corrupt': evidence('controls/corrupt.bin'),
                          'no_face': evidence('controls/no-face.png')}}
    review = {k: None for k in Qualification.model_fields}
    review['scope'] = 'one_private_local_c1_challenge'
    for name, obj in [('study.draft.json', draft), ('qualification.draft.json', review),
                      ('study.schema.json', Challenge.model_json_schema()),
                      ('qualification.schema.json', Qualification.model_json_schema()),
                      ('pair-protocol.json', PAIR_PROTOCOL)]:
        (root/name).write_text(json.dumps(obj, indent=2)+'\n')
    (root/'INCOMPLETE.txt').write_text('BLOCKED ON DATA. Drafts deliberately lack photographs, hashes, permissions and truth.\n'
                                     'Require distinct exact-enrolled AB, AC, BC natural group photographs. U/V allowed; ABC does not substitute.\n'
                                     'Determine presence from human verification; draft labels intentionally remain null.\n'
                                     'See docs/C1_INPUTS.md. Do not label these drafts as qualified inputs.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('var/assistant-inputs/c1-natural-group-pairs'))
    template(parser.parse_args().output)
