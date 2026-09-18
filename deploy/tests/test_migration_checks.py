import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).parents[1]))
import migration_checks as m


class MigrationChecks(unittest.TestCase):
    def runtime_fixture(self):
        values = self.fixture()
        for c in values:
            c['State'] = {'Running': True}
            c['Mounts'] = [{'Type': 'bind', 'RW': True, 'Destination': d, 'Source': s}
                           for d, s in m.MOUNTS[c['Name'].lstrip('/')].items()]
        return values

    def test_runtime_mounts_match(self):
        self.assertEqual(len(m.verify_runtime(self.runtime_fixture())), 3)

    def test_wrong_mount_rejected(self):
        values = self.runtime_fixture()
        values[0]['Mounts'][0]['Source'] = '/wrong/models'
        with self.assertRaisesRegex(RuntimeError, 'mounts changed'):
            m.verify_runtime(values)

    def test_unhealthy_rejected(self):
        values = self.runtime_fixture()
        values[0]['State']['Health'] = {'Status': 'unhealthy'}
        with self.assertRaisesRegex(RuntimeError, 'health'):
            m.verify_runtime(values)
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
