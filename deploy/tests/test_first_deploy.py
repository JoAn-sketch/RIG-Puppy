import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import tempfile
import json
sys.path.insert(0, str(Path(__file__).parents[1]))
import first_deploy


class FirstDeploy(unittest.TestCase):
    def test_entrypoint_all_phases_and_each_failure(self):
        phases = list(first_deploy.migration_flow.PHASES)
        for failure in [None] + phases:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                calls = []
                release = first_deploy.Release(temp, 'a' * 40, Mock())
                def step(name):
                    def invoke(*args):
                        calls.append(name)
                        if name == failure:
                            raise RuntimeError('injected failure')
                    return invoke
                for name in phases:
                    if not name.startswith('create_'):
                        setattr(release, name, step(name))
                def create(services):
                    return step('create_main' if services == [first_deploy.MAIN] else 'create_voices')()
                release.create = create
                with patch.object(first_deploy.deployment, 'RECOVERY_IMPLEMENTATION_VERIFIED', True):
                    if failure:
                        with self.assertRaisesRegex(RuntimeError, 'injected'):
                            release.execute()
                    else:
                        self.assertEqual(release.execute()['result'], 'passed')
                expected = phases if failure is None else phases[:phases.index(failure)+1]
                self.assertEqual(calls, expected)
                journal = json.loads((Path(temp)/'flow.json').read_text())
                self.assertEqual(journal['result'], 'failed' if failure else 'passed')

    def test_execution_gate_precedes_every_operation(self):
        runner = Mock()
        release = first_deploy.Release('/tmp/not-created-by-test', 'a' * 40, runner)
        with patch.object(first_deploy.deployment, 'RECOVERY_IMPLEMENTATION_VERIFIED', False):
            with self.assertRaisesRegex(RuntimeError, 'blocked'):
                release.execute()
        runner.assert_not_called()
