"""Explicit steps for already-adopted Compose voice services, not initial adoption."""
VOICES = ['funasr-runtime', 'kokoro-runtime']


def validate_adoption(containers, project):
    for c in containers:
        labels = c.get('Config', {}).get('Labels') or {}
        name = c['Name'].lstrip('/')
        if labels.get('com.docker.compose.project') != project or labels.get('com.docker.compose.service') != name:
            raise RuntimeError('Initial Compose adoption is not complete: ' + name)


def update(run, command, service):
    # Caller must have completed build and retained recovery artifacts.
    run(command + ['stop', *VOICES])
    run(command + ['up', '-d', '--no-build', '--pull', 'never', '--no-deps', service])
    run(command + ['up', '-d', '--no-build', '--pull', 'never', '--no-deps', '--force-recreate', *VOICES])


def validate_network(containers):
    main = next(c for c in containers if c['Name'] == '/xiaozhi-esp32-server')
    for c in containers:
        if c['Name'].lstrip('/') in VOICES:
            if c.get('HostConfig', {}).get('NetworkMode') != 'container:' + main['Id']:
                raise RuntimeError('Voice container still references old network: ' + c['Name'])
