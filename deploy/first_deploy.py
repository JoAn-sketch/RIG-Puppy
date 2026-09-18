#!/usr/bin/env python3
"""Explicit first adoption. Default is read-only; no automatic rollback."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import time
import uuid
import adoption
import coordinated
import migration_flow
import preflight
from deploy import ROOT, run, ready
from migration_checks import NAMES, verify_runtime

MAIN = 'xiaozhi-esp32-server'
PROJECT = 'puppy-git-runtime'
STATE_ROOT = Path('/home/ubuntu/puppy-deployment-records')


class Release:
    def __init__(self, directory, target, runner=run):
        self.directory, self.target, self.run = Path(directory), target, runner
        self.suffix = self.directory.name
        self.command = ['docker', 'compose', '-p', PROJECT]
        for filename in preflight.FILES:
            self.command += ['-f', str(ROOT / filename)]
        self.command += ['-f', str(self.directory / 'release.json')]
        self.original = None

    def inspect(self, ids=None):
        return json.loads(self.run(['docker', 'inspect', *(ids or sorted(NAMES))]))

    def preflight(self):
        report = preflight.check(self.run)
        if report['blockers']:
            raise RuntimeError('Preflight failed: ' + '; '.join(report['blockers']))
        # Tool updates are installed through Git before this entrypoint is run.
        # Never replace the code of a running migration tool by resetting itself.
        if report['server_HEAD'] != self.target or report['github_commit'] != self.target:
            raise RuntimeError('Install reviewed target through Git before first adoption; HEAD/remote mismatch')
        if self.run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT]):
            raise RuntimeError('Destination project already exists; not a first adoption')
        self.original = self.inspect()
        self.snapshot = verify_runtime(self.original)
        # No source mounts in any running container; reject before any reset/up.
        running = self.run(['docker', 'ps', '-q']).split()
        for c in self.inspect(running) if running else []:
            for mount in c.get('Mounts', []):
                source = Path(mount['Source']).resolve()
                if source == ROOT or source in ROOT.parents:
                    raise RuntimeError('Running container mounts repository root')
                if ROOT in source.parents and not any(
                    source == ROOT / p or ROOT / p in source.parents
                    for p in ('main/xiaozhi-server/data', 'main/xiaozhi-server/models')):
                    raise RuntimeError('Running container mounts business source')
        adoption.persist(self.directory / 'original-inspect.json', self.original)

    def sync(self):
        self.run(['git', 'fetch', 'origin', 'refs/heads/clean-server:refs/remotes/origin/clean-server'])
        if self.run(['git', 'rev-parse', 'origin/clean-server']) != self.target:
            raise RuntimeError('Remote advanced; review new commit first')
        if self.run(['git', 'status', '--porcelain', '--untracked-files=all']):
            raise RuntimeError('Worktree changed')
        # HEAD already equals target; reset intentionally unnecessary.
        if self.run(['git', 'rev-parse', 'HEAD']) != self.target:
            raise RuntimeError('HEAD changed')

    def build(self):
        adoption.persist(self.directory / 'release.json', {'services': {MAIN: {
            'image': 'puppy-server:' + self.target,
            'build': {'labels': {'org.opencontainers.image.revision': self.target}}}}})
        self.run(self.command + ['config', '--quiet'])
        self.run(self.command + ['build', MAIN], timeout=3600)
        self.image = self.run(['docker', 'image', 'inspect', 'puppy-server:' + self.target, '--format', '{{.Id}}'])
        spec = json.loads(self.run(self.command + ['config', '--format', 'json']))
        for voice in coordinated.VOICES:
            # Resolve before downtime; never pull during cutover.
            self.run(['docker', 'image', 'inspect', spec['services'][voice]['image']])

    def recheck(self):
        current = self.inspect()
        if current != self.original:
            # Runtime counters may change; compare identity and critical config only.
            for before, now in zip(sorted(self.original, key=lambda c:c['Name']), sorted(current, key=lambda c:c['Name'])):
                if any(before[k] != now[k] for k in ('Id', 'Config', 'HostConfig', 'Mounts')):
                    raise RuntimeError('Container configuration changed during build')
        verify_runtime(current)
        self.sync()

    def backup(self):
        adoption.persist(self.directory / 'release-record.json', {
            'target': self.target, 'image': self.image, 'snapshot': self.snapshot,
            'project': PROJECT, 'suffix': self.suffix})

    def retain(self):
        adoption.retain(self.run, self.snapshot, self.suffix, self.directory / 'retain.json')

    def create(self, services):
        try:
            self.run(self.command + ['up', '-d', '--no-build', '--pull', 'never', '--no-deps', *services])
        finally:
            # Capture partially created containers even when compose up fails.
            ids = self.run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT]).split()
            values = self.inspect(ids) if ids else []
            adoption.persist(self.directory / 'new-inspect.json', values)

    def verify(self):
        deadline = time.monotonic() + 180
        while True:
            current = self.inspect()
            coordinated.validate_adoption(current, PROJECT)
            coordinated.validate_network(current)
            main = next(c for c in current if c['Name'] == '/' + MAIN)
            if main['Image'] != self.image:
                raise RuntimeError('Unexpected main image')
            if ready(current):
                try:
                    checks = json.loads(self.run(['docker', 'exec', MAIN, 'python', '/opt/puppy-deploy/health.py'], timeout=25))
                    if all(checks.get(k) is True for k in ('server_http', 'kokoro_http', 'funasr_tcp')):
                        adoption.persist(self.directory / 'health.json', checks)
                        return
                except RuntimeError:
                    pass
            if time.monotonic() >= deadline:
                raise RuntimeError('Health timeout; use explicit rollback after inspecting journal')
            time.sleep(3)

    def execute(self):
        phases = {p: getattr(self, p) for p in ('preflight','sync','build','recheck','backup','retain','verify')}
        phases.update(create_main=lambda:self.create([MAIN]), create_voices=lambda:self.create(coordinated.VOICES))
        return migration_flow.execute(phases, self.directory / 'flow.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--target', help='Reviewed full commit SHA')
    args = parser.parse_args()
    if not args.execute:
        report = preflight.check(run)
        print(json.dumps(report, indent=2))
        return int(bool(report['blockers']))
    if not args.target or not __import__('re').fullmatch('[0-9a-f]{40}', args.target):
        parser.error('--execute requires full --target SHA')
    # No invocation in this change: maintenance window authorization is separate.
    with open('/home/ubuntu/.puppy-deploy.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        STATE_ROOT.mkdir(mode=0o700, exist_ok=True)
        if STATE_ROOT.is_symlink() or STATE_ROOT.stat().st_mode & 0o077:
            raise RuntimeError('Deployment record directory must be private and not a symlink')
        directory = STATE_ROOT / (time.strftime('%Y%m%d_%H%M%S') + '-' + uuid.uuid4().hex[:8])
        directory.mkdir(mode=0o700)
        print('Private recovery record: ' + str(directory), flush=True)
        release = Release(directory, args.target)
        result = release.execute()
        print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
