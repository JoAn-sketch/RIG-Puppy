import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deployment', Path(__file__).parents[1] / 'deploy.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class Guards(unittest.TestCase):
    def test_shared_network_blocks_recreation(self):
        containers = [{'Name': '/xiaozhi-esp32-server', 'Id': 'abc123'},
                      {'Name': '/funasr-runtime', 'HostConfig': {'NetworkMode': 'container:abc123'}}]
        with self.assertRaisesRegex(RuntimeError, 'shares its network'):
            d.check_network_dependencies(containers)

    def test_dirty_worktree_stops(self):
        with patch.object(d, 'run', return_value=' M app.py\n?? new.py'):
            with self.assertRaisesRegex(RuntimeError, 'Dirty worktree'):
                d.clean()

    def test_disabled_template_never_runs_commands(self):
        with patch.object(d, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'disabled'):
                d.deploy({'enabled': False}, {})
            run.assert_not_called()

    def test_protected_paths(self):
        for p in ['app/.env', 'app/.env.production', 'app/data/db.sqlite', 'app/models/m.pt']:
            self.assertTrue(d.protected(p, []))
        self.assertFalse(d.protected('app/.env.example', []))

    def test_health_is_not_merely_running(self):
        self.assertFalse(d.ready([{'State': {'Running': True, 'Health': {'Status': 'starting'}}}]))
        self.assertFalse(d.ready([{'State': {'Running': True, 'Restarting': True}}]))
        self.assertTrue(d.ready([{'State': {'Running': True, 'Health': {'Status': 'healthy'}}}]))

    def test_command_failure_raises(self):
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            d.run(['sh', '-c', 'exit 7'], cwd=Path('/tmp'))


if __name__ == '__main__':
    unittest.main()
