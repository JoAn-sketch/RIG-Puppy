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
from migration_checks import verify_runtime

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
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


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
    snapshot = verify_runtime(containers)
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


def rollback(run, snapshot, replacements, current, suffix, journal):
    """Restore retained IDs only. Caller holds lock and supplies fresh inspect-all.

    replacements is the exact name->ID mapping recorded when the failed release
    was created. Unknown occupants or missing originals abort before mutation.
    This does not restore bind-mounted data or claim application health.
    """
    if Path(journal).exists() or Path(journal).with_suffix('.pending').exists():
        raise RuntimeError('Existing rollback journal requires inspection')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', suffix):
        raise ValueError('Invalid rollback suffix')
    if set(snapshot) != set(ORDER) or not set(replacements).issubset(ORDER):
        raise RuntimeError('Unexpected container scope')
    by_id = {c['Id']: c for c in current}
    by_name = {c['Name'].lstrip('/'): c['Id'] for c in current}
    old_ids = {v['id'] for v in snapshot.values()}
    if len(old_ids) != 3 or old_ids.intersection(replacements.values()):
        raise RuntimeError('Conflicting container IDs')
    if len(set(replacements.values())) != len(replacements):
        raise RuntimeError('Duplicate failed container IDs')
    for name in ORDER:
        old = by_id.get(snapshot[name]['id'])
        if not old:
            raise RuntimeError('Original container missing: ' + name)
        if old['State'].get('Running') or old['State'].get('Restarting'):
            raise RuntimeError('Original must be stopped before rollback: ' + name)
        occupant = by_name.get(name)
        if occupant and occupant not in {snapshot[name]['id'], replacements.get(name)}:
            raise RuntimeError('Unknown name occupant: ' + name)
        if name in replacements:
            failed = by_id.get(replacements[name])
            if not failed or failed['Name'].lstrip('/') != name:
                raise RuntimeError('Failed release identity mismatch: ' + name)
            if name + '-failed-' + suffix in by_name:
                raise RuntimeError('Failed backup name occupied')
        policy = snapshot[name]['restart']
        if policy['Name'] not in {'always', 'unless-stopped', 'no', 'on-failure'}:
            raise RuntimeError('Unknown restart policy')
    main_id = snapshot['xiaozhi-esp32-server']['id']
    for name in ORDER[:2]:
        if by_id[snapshot[name]['id']]['HostConfig']['NetworkMode'] != 'container:' + main_id:
            raise RuntimeError('Original network reference changed')
    state = {'status': 'restoring', 'containers': snapshot,
             'replacements': replacements, 'steps': []}
    persist(journal, state)
    def action(command):
        step = {'command': command, 'status': 'pending'}
        state['steps'].append(step)
        persist(journal, state)
        run(command)
        step['status'] = 'complete'
        persist(journal, state)
    for name in ORDER:
        if name in replacements:
            cid = replacements[name]
            action(['docker', 'update', '--restart=no', cid])
            action(['docker', 'stop', '--time', '30', cid])
            action(['docker', 'rename', cid, name + '-failed-' + suffix])
    for name in reversed(ORDER):
        cid = snapshot[name]['id']
        if by_id[cid]['Name'].lstrip('/') != name:
            action(['docker', 'rename', cid, name])
        policy = snapshot[name]['restart']
        restart = policy['Name']
        if restart == 'on-failure' and policy.get('MaximumRetryCount', 0):
            restart += ':' + str(int(policy['MaximumRetryCount']))
        action(['docker', 'update', '--restart=' + restart, cid])
        action(['docker', 'start', cid])
    state['status'] = 'containers_restored_health_not_verified'
    persist(journal, state)
    return state


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
