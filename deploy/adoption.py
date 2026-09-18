#!/usr/bin/env python3
"""First-adoption planner and journalled container-retention primitives.

CLI is read-only. Production execution stays blocked until full preflight and
failure recovery have been verified; these primitives never delete containers.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import re
from migration_checks import verify_snapshot

ORDER = ['funasr-runtime', 'kokoro-runtime', 'xiaozhi-esp32-server']


def persist(path, value):
    path = Path(path)
    temporary = path.with_suffix('.pending')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def retain(run, snapshot, suffix, journal):
    """Called only after verified build, durable snapshot and exclusive lock.

Journal intent BEFORE each operation; interrupted calls require inspection,
never blindly replay. Caller must verify current names still match recorded IDs.
"""
    if Path(journal).exists() or Path(journal).with_suffix('.pending').exists():
        raise RuntimeError('Existing journal requires inspection; refusing replay')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', suffix):
        raise ValueError('Invalid backup suffix')
    state = {'status': 'retaining', 'containers': snapshot, 'steps': []}
    persist(journal, state)
    for name in ORDER:
        cid = snapshot[name]['id']
        operations = [(['docker', 'update', '--restart=no', cid], 'disable_restart'),
                      (['docker', 'stop', '--time', '30', cid], 'stop'),
                      (['docker', 'rename', cid, name + '-backup-' + suffix], 'rename')]
        for command, action in operations:
            step = {'id': cid, 'action': action, 'status': 'pending'}
            state['steps'].append(step)
            persist(journal, state)
            run(command)
            step['status'] = 'complete'
            persist(journal, state)
    state['status'] = 'retained'
    persist(journal, state)
    return state


def make_plan(containers):
    snapshot = verify_snapshot(containers)
    return {'mode': 'read-only', 'execution_enabled': False,
            'directory': '/home/ubuntu/xiaozhi-esp32-server-main',
            'candidate_project': 'puppy-git-runtime',
            'original_containers': snapshot,
            'stop_order': ORDER, 'restore_order': list(reversed(ORDER)),
            'requirements': ['verified Git SHA and successful build',
                             'exclusive deployment lock and private durable inspect backup',
                             'retain original IDs; no deletion or compose down',
                             'external xiaozhi-server_default network with original aliases',
                             'check static IP dependencies and actual data mount identities',
                             'journal partial failures before every mutation',
                             'production-equivalent recovery validation']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect-json', help='Private existing docker inspect JSON; otherwise read Docker')
    args = parser.parse_args()
    if args.inspect_json:
        containers = json.loads(Path(args.inspect_json).read_text())
    else:
        containers = json.loads(subprocess.check_output(
            ['docker', 'inspect', *ORDER], text=True, timeout=30))
    print(json.dumps(make_plan(containers), indent=2))


if __name__ == '__main__':
    main()
