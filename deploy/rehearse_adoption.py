#!/usr/bin/env python3
"""Local-only Compose project isolation rehearsal. Retains all containers."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid


def run(*args):
    return subprocess.check_output(args, text=True, timeout=120).strip()


def main():
    if os.environ.get('DOCKER_HOST') or run('docker', 'context', 'show') != 'colima':
        raise RuntimeError('Local colima only')
    compose = '/private/tmp/puppy-docker-compose'
    prefix = 'puppy-adoption-' + uuid.uuid4().hex[:8]
    old_project, new_project = prefix + '-old', prefix + '-new'
    names = [prefix + '-' + role for role in ('main', 'asr', 'tts')]
    report = {'result': 'failed', 'prefix': prefix, 'production': False}
    tracked = []
    with tempfile.TemporaryDirectory(prefix='puppy-adoption-') as temp:
        config = Path(temp) / 'compose.json'
        services = {}
        for role, name in zip(('main', 'asr', 'tts'), names):
            services[role] = {'image': 'puppy-build-check:local', 'platform': 'linux/amd64',
                'container_name': name, 'entrypoint': ['python', '-c', 'import time; time.sleep(3600)'],
                'network_mode': 'none' if role == 'main' else 'service:main'}
        config.write_text(json.dumps({'services': services}))
        def command(project, *args):
            return run(compose, '-p', project, '-f', str(config), *args)
        try:
            command(old_project, 'up', '-d', '--pull', 'never')
            tracked.extend(names)
            old_ids = {n: run('docker', 'inspect', '--format', '{{.Id}}', n) for n in names}
            command(old_project, 'stop')
            for name in names:
                run('docker', 'rename', name, name + '-retained')
                tracked.append(name + '-retained')
            # Different project avoids matching the old immutable Compose labels.
            command(new_project, 'up', '-d', '--pull', 'never')
            for name in names:
                assert run('docker', 'inspect', '--format', '{{.Id}}', name + '-retained') == old_ids[name]
            command(new_project, 'stop')
            for name in names:
                run('docker', 'rename', name, name + '-failed')
                tracked.append(name + '-failed')
                run('docker', 'rename', name + '-retained', name)
            # Restore the original containers, preserving the original namespace ID.
            for name in names:
                run('docker', 'start', name)
                assert run('docker', 'inspect', '--format', '{{.Id}}', name) == old_ids[name]
            for name in names[1:]:
                assert run('docker', 'inspect', '--format', '{{.HostConfig.NetworkMode}}', name) == 'container:' + old_ids[names[0]]
            report.update(result='passed', old_ids_retained=True, old_network_restored=True,
                          change_required='New Compose project identity; production directory unchanged')
        finally:
            for name in tracked:
                subprocess.run(['docker', 'stop', '--time', '1', name], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=30)
            report['artifacts'] = tracked
            Path('/private/tmp/puppy-adoption-result.json').write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
