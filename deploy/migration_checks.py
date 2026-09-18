"""Read-only checks for a future first-adoption operation."""
NAMES = {'xiaozhi-esp32-server', 'funasr-runtime', 'kokoro-runtime'}
NETWORK = 'xiaozhi-server_default'


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
