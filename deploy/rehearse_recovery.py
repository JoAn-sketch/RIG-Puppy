#!/usr/bin/env python3
"""Local synthetic recovery exercise, no production names, ports or mounts.

Does not validate production configuration fidelity. Leaves all artifacts in
place so failure evidence and snapshot images are recoverable.
"""
import argparse
import json
import subprocess
import uuid
import os
from pathlib import Path


def exercise(image, report_path):
    prefix = 'puppy-rehearsal-' + uuid.uuid4().hex[:10]
    report = {'prefix': prefix, 'production_validation': False, 'result': 'failed',
              'containers': [], 'snapshots': []}

    def run(*args):
        return subprocess.check_output(['docker', *args], text=True, timeout=120).strip()

    def create(name, source, network='none'):
        run('create', '--platform', 'linux/amd64', '--name', name,
            '--network', network, '--label', 'puppy.rehearsal=' + prefix,
            '--entrypoint', 'python', source, '-c', 'import time; time.sleep(3600)')
        report['containers'].append(name)
        run('start', name)

    try:
        context = run('context', 'show')
        if context != 'colima' or os.environ.get('DOCKER_HOST'):
            raise RuntimeError('Rehearsal requires local colima context without DOCKER_HOST override')
        old = [prefix + '-old-' + role for role in ('main', 'asr', 'tts')]
        create(old[0], image)
        for name in old[1:]:
            create(name, image, 'container:' + old[0])
        for name in old:
            run('exec', name, 'python', '-c',
                'from pathlib import Path; Path("/tmp/recovery-marker").write_text("old-state")')
        # Snapshot stopped containers in dependent-first order, retaining originals.
        for name in reversed(old):
            run('stop', '--time', '2', name)
        for name in old:
            snapshot = name + ':snapshot'
            run('commit', name, snapshot)
            report['snapshots'].append(snapshot)
        new = [prefix + '-new-' + role for role in ('main', 'asr', 'tts')]
        create(new[0], image)
        for name in new[1:]:
            create(name, image, 'container:' + new[0])
        # Simulate a failed release. Retain failed containers, then restore old state.
        for name in reversed(new):
            run('stop', '--time', '2', name)
        restored = [prefix + '-restored-' + role for role in ('main', 'asr', 'tts')]
        create(restored[0], report['snapshots'][0])
        for name, snapshot in zip(restored[1:], report['snapshots'][1:]):
            create(name, snapshot, 'container:' + restored[0])
        main_id = run('inspect', '--format', '{{.Id}}', restored[0])
        for name in restored:
            marker = run('exec', name, 'python', '-c',
                         'from pathlib import Path; print(Path("/tmp/recovery-marker").read_text())')
            if marker != 'old-state':
                raise RuntimeError('Writable layer was not recovered')
        for name in restored[1:]:
            mode = run('inspect', '--format', '{{.HostConfig.NetworkMode}}', name)
            if mode != 'container:' + main_id:
                raise RuntimeError('Restored network namespace is wrong')
        report['result'] = 'passed'
        report['checks'] = ['old writable layers restored', 'new shared network references verified',
                            'original and failed containers retained']
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        for name in reversed(report['containers']):
            try:
                run('stop', '--time', '2', name)
            except Exception:
                report.setdefault('stop_failures', []).append(name)
        Path(report_path).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['result'] == 'passed' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='puppy-build-check:local')
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    raise SystemExit(exercise(args.image, args.report))
