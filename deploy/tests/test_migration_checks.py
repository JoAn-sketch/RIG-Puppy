import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).parents[1]))
import migration_checks as m


class MigrationChecks(unittest.TestCase):
    def fixture(self):
        return [{'Name': '/' + name, 'Id': name,
                 'NetworkSettings': {'Networks': {m.NETWORK: {'Aliases': [name]}} if name == 'xiaozhi-esp32-server' else {}},
                 'HostConfig': {'RestartPolicy': {'Name': 'always' if name == 'xiaozhi-esp32-server' else 'unless-stopped', 'MaximumRetryCount': 0},
                                'NetworkMode': m.NETWORK if name == 'xiaozhi-esp32-server' else 'container:xiaozhi-esp32-server'}} for name in sorted(m.NAMES)]

    def test_verified_state_returns_original_restart_policy(self):
        x = self.fixture()
        before = copy.deepcopy(x)
        self.assertEqual(m.verify_snapshot(x)['kokoro-runtime']['restart']['Name'], 'unless-stopped')
        self.assertEqual(x, before)

    def test_network_drift_rejected(self):
        x = self.fixture()
        next(c for c in x if c['Name'] == '/xiaozhi-esp32-server')['NetworkSettings']['Networks'] = {}
        with self.assertRaises(RuntimeError): m.verify_snapshot(x)

    def test_restart_drift_rejected(self):
        x = self.fixture()
        x[0]['HostConfig']['RestartPolicy']['Name'] = 'no'
        with self.assertRaises(RuntimeError): m.verify_snapshot(x)
