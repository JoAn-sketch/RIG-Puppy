import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import first_deploy


class FirstDeploy(unittest.TestCase):
    def test_execution_gate_precedes_every_operation(self):
        runner = Mock()
        release = first_deploy.Release('/tmp/not-created-by-test', 'a' * 40, runner)
        with patch.object(first_deploy.deployment, 'RECOVERY_IMPLEMENTATION_VERIFIED', False):
            with self.assertRaisesRegex(RuntimeError, 'blocked'):
                release.execute()
        runner.assert_not_called()
