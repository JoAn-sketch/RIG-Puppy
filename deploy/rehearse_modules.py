#!/usr/bin/env python3
"""Run the real retention/rollback functions on isolated local containers."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
import adoption


def main():
    def docker(args):
        return subprocess.check_output(args, text=True, timeout=60).strip()
    if os.environ.get('DOCKER_HOST') or docker(['docker', 'context', 'show']) != 'colima':
        raise RuntimeError('Local Colima only')
    prefix = 'puppy-modules-' + uuid.uuid4().hex[:10] + '-'
    directory = Path(tempfile.mkdtemp(prefix='puppy-module-report-'))
    ids = []
    result = {'result': 'failed', 'production_validation': False, 'prefix': prefix}

    def run(command):
        command = list(command)
        if command[1] == 'rename':
            command[-1] = prefix + command[-1]
        return docker(command)

    def inspect():
        values = json.loads(docker(['docker', 'inspect', *ids]))
        for item in values:
            item['Name'] = '/' + item['Name'].lstrip('/').removeprefix(prefix)
        return values

    def create(name, network, restart):
        cid = docker(['docker', 'create', '--platform', 'linux/amd64', '--network', network,
                      '--name', prefix + name, '--restart', restart,
                      '--label', 'puppy.rehearsal=' + prefix,
                      '--entrypoint', 'python', 'puppy-build-check:local', '-c',
                      'import signal,time; signal.signal(signal.SIGTERM,lambda *a:exit(0)); time.sleep(3600)'])
        ids.append(cid)
        docker(['docker', 'start', cid])
        return cid

    try:
        main_name = 'xiaozhi-esp32-server'
        original = create(main_name, 'none', 'always')
        for name in adoption.ORDER[:2]:
            create(name, 'container:' + original, 'unless-stopped')
        snapshot = {x['Name'].lstrip('/'): {'id': x['Id'], 'restart': x['HostConfig']['RestartPolicy']}
                    for x in inspect()}
        adoption.retain(run, snapshot, 'exercise', directory/'retain.json')
        new_main = create(main_name, 'none', 'always')
        replacements = {main_name: new_main}
        for name in adoption.ORDER[:2]:
            replacements[name] = create(name, 'container:' + new_main, 'unless-stopped')
        adoption.rollback(run, snapshot, replacements, inspect(), 'exercise', directory/'rollback.json')
        actual = {x['Id']: x for x in inspect()}
        for name, saved in snapshot.items():
            item = actual[saved['id']]
            if item['Name'] != '/' + name or not item['State']['Running']:
                raise RuntimeError('Original name/running state not restored')
            if item['HostConfig']['RestartPolicy'] != saved['restart']:
                raise RuntimeError('Restart policy mismatch')
            if name != main_name and item['HostConfig']['NetworkMode'] != 'container:' + original:
                raise RuntimeError('Old namespace not restored')
        for cid in replacements.values():
            if actual[cid]['State']['Running'] or actual[cid]['HostConfig']['RestartPolicy']['Name'] != 'no':
                raise RuntimeError('Failed version not safely retained')
        result['result'] = 'passed'
        result['checks'] = ['real retain and rollback modules', 'old IDs and names',
                            'restart policies', 'shared namespace', 'failed version retained']
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        for cid in reversed(ids):
            try:
                docker(['docker', 'update', '--restart=no', cid])
                docker(['docker', 'stop', '--time', '2', cid])
            except Exception as exc:
                result.setdefault('cleanup_errors', []).append(str(exc))
        result['container_ids'] = ids
        adoption.persist(directory/'result.json', result)
        print(json.dumps({'report': str(directory), **result}, indent=2))
    return 0 if result['result'] == 'passed' and not result.get('cleanup_errors') else 1


if __name__ == '__main__':
    raise SystemExit(main())
