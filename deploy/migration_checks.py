"""Read-only checks for a future first-adoption operation."""
NAMES = {'xiaozhi-esp32-server', 'funasr-runtime', 'kokoro-runtime'}
NETWORK = 'xiaozhi-server_default'
MOUNTS = {
    'xiaozhi-esp32-server': {
        '/opt/xiaozhi-esp32-server/data': '/home/ubuntu/xiaozhi-esp32-server-main/main/xiaozhi-server/data',
        '/opt/xiaozhi-esp32-server/models/SenseVoiceSmall': '/home/ubuntu/xiaozhi-esp32-server-main/main/xiaozhi-server/models/SenseVoiceSmall'},
    'funasr-runtime': {'/workspace/models': '/home/ubuntu/funasr-runtime-resources/models'},
    'kokoro-runtime': {}}


def verify_runtime(containers):
    snapshot = verify_snapshot(containers)
    for c in containers:
        name = c['Name'].lstrip('/')
        if name not in NAMES:
            continue
        if not c['State'].get('Running') or c['State'].get('Restarting'):
            raise RuntimeError('Container is not stable: ' + name)
        if c['State'].get('Health', {}).get('Status', 'healthy') != 'healthy':
            raise RuntimeError('Container health is not ready: ' + name)
        mounts = c.get('Mounts', [])
        if any(m.get('Type') != 'bind' or not m.get('RW') for m in mounts):
            raise RuntimeError('Unexpected mount type or mode: ' + name)
        actual = {m['Destination']: m['Source'] for m in mounts}
        if len(actual) != len(mounts) or actual != MOUNTS[name]:
            raise RuntimeError('Production mounts changed: ' + name)
    return snapshot


def verify_snapshot(containers):
    by_name = {c['Name'].lstrip('/'): c for c in containers}
    if not NAMES.issubset(by_name):
        raise RuntimeError('Missing one or more core containers')
    main = by_name['xiaozhi-esp32-server']
    if set(main['NetworkSettings']['Networks']) != {NETWORK}:
        raise RuntimeError('Production network changed; review required')
    aliases = main['NetworkSettings']['Networks'][NETWORK].get('Aliases') or []
    if 'xiaozhi-esp32-server' not in aliases:
        raise RuntimeError('Main service DNS alias missing')
    expected = {'xiaozhi-esp32-server': 'always', 'funasr-runtime': 'unless-stopped',
                'kokoro-runtime': 'unless-stopped'}
    for name in NAMES:
        c = by_name[name]
        if c['HostConfig']['RestartPolicy']['Name'] != expected[name]:
            raise RuntimeError('Restart policy changed: ' + name)
        if name != 'xiaozhi-esp32-server':
            if c['HostConfig']['NetworkMode'] != 'container:' + main['Id']:
                raise RuntimeError('Voice namespace changed: ' + name)
    return {name: {'id': by_name[name]['Id'],
                   'restart': by_name[name]['HostConfig']['RestartPolicy'].copy()}
            for name in sorted(NAMES)}
