import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).parents[1]))
import coordinated


class CoordinatedTests(unittest.TestCase):
    def test_unmanaged_containers_rejected(self):
        with self.assertRaises(RuntimeError):
            coordinated.validate_adoption([{'Name': '/funasr-runtime'}], 'xiaozhi-server')

    def test_stop_failure_prevents_update(self):
        calls = []
        def run(cmd):
            calls.append(cmd)
            raise RuntimeError('stop failed')
        with self.assertRaises(RuntimeError):
            coordinated.update(run, ['docker', 'compose'], 'xiaozhi-esp32-server')
        self.assertEqual(len(calls), 1)

    def test_main_failure_prevents_voice_start(self):
        calls = []
        def run(cmd):
            calls.append(cmd)
            if 'up' in cmd: raise RuntimeError('up failed')
        with self.assertRaises(RuntimeError):
            coordinated.update(run, ['docker', 'compose'], 'xiaozhi-esp32-server')
        self.assertEqual(len(calls), 2)

    def test_old_namespace_rejected(self):
        with self.assertRaises(RuntimeError):
            coordinated.validate_network([{'Name': '/xiaozhi-esp32-server', 'Id': 'new'},
                {'Name': '/funasr-runtime', 'HostConfig': {'NetworkMode': 'container:old'}}])

    def test_update_order(self):
        calls = []
        coordinated.update(calls.append, ['docker', 'compose'], 'xiaozhi-esp32-server')
        self.assertIn('stop', calls[0])
        self.assertEqual(calls[1][-1], 'xiaozhi-esp32-server')
        self.assertIn('--force-recreate', calls[2])
