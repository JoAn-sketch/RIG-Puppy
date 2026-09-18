#!/usr/bin/env python3
"""Read-only production preflight: no fetch, reset, build or container mutation."""
import json
import subprocess
from pathlib import Path
from deploy import ROOT, ORIGINS
from migration_checks import NAMES, verify_runtime, NETWORK

FILES = ['main/xiaozhi-server/docker-compose.yml', 'deploy/compose.build.yml',
         'deploy/compose.voice.yml', 'deploy/compose.network.yml']


def check(run):
    report = {'directory': str(ROOT), 'mode': 'read-only', 'checks': {}, 'blockers': []}
    def attempt(name, action):
        try:
            report['checks'][name] = action()
        except Exception as exc:
            report['blockers'].append(name + ': ' + str(exc))
    def git():
        if run(['git', 'rev-parse', '--show-toplevel']) != str(ROOT):
            raise RuntimeError('unexpected repository root')
        if run(['git', 'remote', 'get-url', 'origin']) not in ORIGINS:
            raise RuntimeError('unexpected origin')
        head = run(['git', 'rev-parse', 'HEAD'])
        report['server_HEAD'] = head
        dirty = run(['git', 'status', '--porcelain', '--untracked-files=all'])
        if dirty:
            report['worktree_changes'] = dirty.splitlines()
            raise RuntimeError('worktree is dirty; no overwrite permitted')
        return 'clean'
    attempt('git', git)
    def remote():
        # Explicit public SSH URL: no accidental query to an unverified origin.
        output = run(['git', 'ls-remote', '--exit-code',
                      'https://github.com/JoAn-sketch/RIG-Puppy.git', 'refs/heads/clean-server'])
        fields = output.split()
        if len(fields) != 2 or fields[1] != 'refs/heads/clean-server':
            raise RuntimeError('remote branch not resolved')
        report['github_commit'] = fields[0]
        return 'resolved; not fetched'
    attempt('github', remote)
    attempt('runtime', lambda: {'verified': list(verify_runtime(json.loads(
        run(['docker', 'inspect', *sorted(NAMES)]))))})
    def compose():
        cmd = ['docker', 'compose', '-p', 'puppy-git-runtime']
        for p in FILES:
            cmd += ['-f', str(ROOT/p)]
        spec = json.loads(run(cmd + ['config', '--format', 'json']))
        main = spec['services']['xiaozhi-esp32-server']
        if Path(main.get('build', {}).get('context', '')).resolve() != ROOT:
            raise RuntimeError('build context is not production Git root')
        network = spec.get('networks', {}).get('default', {})
        if network.get('name') != NETWORK or not network.get('external'):
            raise RuntimeError('existing production network not preserved')
        for n in ('funasr-runtime', 'kokoro-runtime'):
            voice = spec['services'][n]
            if voice.get('network_mode') != 'service:xiaozhi-esp32-server':
                raise RuntimeError('voice namespace mismatch')
            if '@sha256:' not in voice.get('image', ''):
                raise RuntimeError('voice image not pinned')
        return 'validated'
    attempt('compose', compose)
    report['production_execution_enabled'] = False
    report['result'] = 'blocked' if report['blockers'] else 'preflight_passed_not_deployed'
    return report


def main():
    def run(args):
        result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=30)
        if result.returncode:
            # Do not print raw compose/SSH output which may contain credentials.
            raise RuntimeError(f'{args[0]} returned {result.returncode}')
        return result.stdout.strip()
    report = check(run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['blockers'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
