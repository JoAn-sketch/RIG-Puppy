#!/usr/bin/env python3
"""Server-only, fail-closed Git deployment. No file upload or automatic rollback."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordinated

ROOT = Path('/home/ubuntu/xiaozhi-esp32-server-main')
ORIGINS = {'git@github.com:JoAn-sketch/RIG-Puppy.git',
           'https://github.com/JoAn-sketch/RIG-Puppy.git'}


def run(args, cwd=ROOT, timeout=300):
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        # Raw build/config output can contain credentials. Keep it on the server.
        with tempfile.NamedTemporaryFile(mode='w', prefix='puppy-deploy-error-',
                                         suffix='.log', delete=False) as log:
            log.write(result.stdout + result.stderr)
        raise RuntimeError(f'{args[0]} failed ({result.returncode}); private log: {log.name}')
    return result.stdout.strip()


def clean():
    changes = run(['git', 'status', '--porcelain', '--untracked-files=all'])
    if changes:
        raise RuntimeError('Dirty worktree; no overwrite permitted:\n' + changes)


def protected(path, configured):
    parts = Path(path).parts
    return (any(p in {'.env', 'data', 'models', 'mysql', 'redis', 'uploadfile'}
                or (p.startswith('.env.') and p not in {'.env.example', '.env.sample'})
                for p in parts)
            or any(path == p or path.startswith(p.rstrip('/') + '/') for p in configured))


def inspect(names):
    return json.loads(run(['docker', 'inspect', *names]))


def ready(containers):
    return all(c['State'].get('Running') and not c['State'].get('Restarting')
               and c['State'].get('Health', {}).get('Status', 'healthy') == 'healthy'
               for c in containers)


def check_network_dependencies(containers):
    main = next(c for c in containers if c['Name'] == '/xiaozhi-esp32-server')
    for c in containers:
        mode = c.get('HostConfig', {}).get('NetworkMode', '')
        if mode.startswith('container:'):
            owner = mode.split(':', 1)[1].lstrip('/')
            if owner == 'xiaozhi-esp32-server' or main['Id'].startswith(owner):
                raise RuntimeError('Cannot recreate main server: ' + c['Name'] +
                                   ' shares its network namespace; coordinated migration required')


def compose(config):
    command = ['docker', 'compose', '-p', config['project']]
    for filename in config['compose_files']:
        p = Path(filename)
        if not p.is_absolute() or not p.is_file():
            raise RuntimeError('Compose files must be existing absolute paths')
        command += ['-f', str(p)]
    return command


def deploy(config, report):
    if not config.get('enabled'):
        raise RuntimeError('Deployment disabled: production configuration not verified')
    if not config.get('project') or not config.get('compose_files') or not config.get('health_command'):
        raise RuntimeError('Verified Compose project/files and health command required')
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError('Fixed production directory missing or is a symlink')
    if Path(run(['git', 'rev-parse', '--show-toplevel'])).resolve() != ROOT:
        raise RuntimeError('Unexpected Git root')
    if run(['git', 'remote', 'get-url', 'origin']) not in ORIGINS:
        raise RuntimeError('Unexpected origin; expected JoAn-sketch/RIG-Puppy')
    report['before_HEAD'] = run(['git', 'rev-parse', 'HEAD'])
    clean()
    cmd = compose(config)
    report['compose'] = {'project': config['project'], 'files': config['compose_files']}
    resolved = json.loads(run(cmd + ['config', '--format', 'json']))
    service = config['service']
    spec = resolved['services'][service]
    build = spec.get('build')
    if not isinstance(build, dict) or Path(build.get('context', '')).resolve() != ROOT:
        raise RuntimeError('Main service must build from the fixed Git root')
    if spec.get('pull_policy') == 'always':
        raise RuntimeError('Main service must not force remote image pulls')
    names = config['containers']
    if len(names) != 3 or set(names) != {'xiaozhi-esp32-server', 'funasr-runtime', 'kokoro-runtime'}:
        raise RuntimeError('All three core containers must be checked')
    before = inspect(names)
    coordinated_mode = config.get('coordinated', False)
    if coordinated_mode:
        coordinated.validate_adoption(before, config['project'])
        for voice in coordinated.VOICES:
            voice_spec = resolved['services'].get(voice, {})
            if voice_spec.get('network_mode') != 'service:' + service:
                raise RuntimeError('Voice service must share main service network: ' + voice)
            if '@sha256:' not in voice_spec.get('image', ''):
                raise RuntimeError('Voice image must be pinned: ' + voice)
        if not config.get('recovery_rehearsed', False):
            raise RuntimeError('Coordinated recovery rehearsal not confirmed')
    else:
        check_network_dependencies(before)
    report['before_containers'] = {c['Name']: {'id': c['Id'], 'image': c['Image']} for c in before}
    # All running containers, not just the main service, can mount source.
    ids = run(['docker', 'ps', '-q']).split()
    for container in inspect(ids) if ids else []:
        for mount in container.get('Mounts', []):
            src = Path(mount['Source']).resolve()
            if src == ROOT or src in ROOT.parents:
                raise RuntimeError('Running container mounts production source root')
            if ROOT in src.parents and not protected(str(src.relative_to(ROOT)), config['protected_paths']):
                raise RuntimeError('Running container mounts code: ' + str(src))
    report['phase'] = 'fetch'
    run(['git', 'fetch', 'origin', 'refs/heads/clean-server:refs/remotes/origin/clean-server'])
    target = run(['git', 'rev-parse', '--verify', 'origin/clean-server^{commit}'])
    report['target_commit'] = target
    target_paths = run(['git', 'ls-tree', '-r', '--name-only', target]).splitlines()
    if config['source'] not in target_paths:
        raise RuntimeError('Target missing required server source: ' + config['source'])
    bad = [p for p in target_paths if protected(p, config['protected_paths'])]
    if bad:
        raise RuntimeError('Target tracks protected runtime paths: ' + ', '.join(bad[:20]))
    # Ignored files can be overwritten by reset despite a clean worktree.
    ignored = run(['git', 'ls-files', '--others', '--ignored', '--exclude-standard']).splitlines()
    for p in ignored:
        if any(p == q or p.startswith(q + '/') or q.startswith(p + '/') for q in target_paths):
            raise RuntimeError('Target would overwrite ignored file: ' + p)
    # Fail closed if target changes deployment configuration; review separately.
    dockerfile = Path(build.get('dockerfile', 'Dockerfile'))
    if not dockerfile.is_absolute():
        dockerfile = ROOT / dockerfile
    if ROOT not in dockerfile.resolve().parents or not dockerfile.is_file():
        raise RuntimeError('Dockerfile must exist within the production Git root')
    critical = [str(dockerfile.relative_to(ROOT)), '.dockerignore', 'deploy']
    if '.dockerignore' not in target_paths:
        raise RuntimeError('Target missing Docker build exclusions')
    for filename in config['compose_files']:
        p = Path(filename)
        if ROOT in p.parents:
            critical.append(str(p.relative_to(ROOT)))
    if run(['git', 'diff', '--name-only', 'HEAD', target, '--', *critical]):
        raise RuntimeError('Deployment configuration changed; review required before activation')
    clean()
    report['phase'] = 'sync'
    run(['git', 'reset', '--hard', target])
    report['after_HEAD'] = run(['git', 'rev-parse', 'HEAD'])
    if report['after_HEAD'] != target:
        raise RuntimeError('HEAD mismatch')
    # Override only image identity. Preserve production mounts, ports and data.
    with tempfile.TemporaryDirectory(prefix='puppy-compose-') as temp:
        override = Path(temp) / 'revision.json'
        override.write_text(json.dumps({'services': {service: {
            'image': 'puppy-server:' + target,
            'build': {'labels': {'org.opencontainers.image.revision': target}}
        }}}))
        release = cmd + ['-f', str(override)]
        run(release + ['config', '--quiet'])
        report['phase'] = 'build'
        run(release + ['build', service], timeout=3600)
        report['build'] = 'passed'
        expected_image = run(['docker', 'image', 'inspect', 'puppy-server:' + target,
                              '--format', '{{.Id}}'])
        report['phase'] = 'update'
        if coordinated_mode:
            coordinated.update(run, release, service)
        else:
            run(release + ['up', '-d', '--no-build', '--pull', 'never', '--no-deps', service])
        report['phase'] = 'health'
        deadline = time.monotonic() + min(int(config.get('timeout_seconds', 120)), 600)
        while True:
            after = inspect(names)
            report['containers'] = {c['Name']: c['State']['Status'] for c in after}
            if ready(after):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Core containers failed readiness timeout')
            time.sleep(3)
        main = next(c for c in after if c['Name'] == '/xiaozhi-esp32-server')
        report['after_containers'] = {c['Name']: {'id': c['Id'], 'image': c['Image']} for c in after}
        if main['Image'] != expected_image:
            raise RuntimeError('Main container does not use built image')
        if main['Config'].get('Labels', {}).get('org.opencontainers.image.revision') != target:
            raise RuntimeError('Main container revision mismatch')
        if coordinated_mode:
            coordinated.validate_network(after)
        # Ports are private to the main container's namespace, not host listeners.
        while True:
            try:
                checks = json.loads(run(config['health_command'], timeout=30))
                if not all(checks.get(k) is True for k in ('server_http', 'kokoro_http', 'funasr_tcp')):
                    raise RuntimeError('Application readiness failed')
                report['10095'] = checks['funasr_tcp']
                report['8880'] = checks['kokoro_http']
                break
            except (RuntimeError, ValueError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(3)
        report['health'] = 'passed'
        run(release + ['ps'])
    report['result'] = 'passed'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    report = {'directory': str(ROOT), 'repository': 'JoAn-sketch/RIG-Puppy',
              'branch': 'clean-server', 'phase': 'preflight', 'result': 'failed',
              'build': 'not executed', 'health': 'not executed'}
    try:
        with open('/home/ubuntu/.puppy-deploy.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            deploy(json.loads(Path(args.config).read_text()), report)
    except Exception as exc:
        report['error'] = str(exc)
        report['impact'] = 'No automatic rollback; consult phase, HEAD and previous image IDs'
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['result'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
