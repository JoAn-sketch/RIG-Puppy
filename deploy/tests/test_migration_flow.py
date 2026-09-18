import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).parents[1]))
import migration_flow as f


class MigrationFlow(unittest.TestCase):
    def test_each_failure_prevents_all_later_phases(self):
        for index, failed in enumerate(f.PHASES):
            with self.subTest(phase=failed), tempfile.TemporaryDirectory() as temp:
                calls = []
                def adapter(phase):
                    def call():
                        calls.append(phase)
                        if phase == failed: raise RuntimeError('injected')
                    return call
                path = Path(temp)/'flow.json'
                with self.assertRaises(RuntimeError):
                    f.execute({p: adapter(p) for p in f.PHASES}, path)
                self.assertEqual(calls, list(f.PHASES[:index+1]))
                state = json.loads(path.read_text())
                self.assertEqual(state['result'], 'failed')
                self.assertEqual(state['phase'], failed)
                self.assertEqual(state['completed'], list(f.PHASES[:index]))

    def test_success_requires_health_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            result = f.execute({p: lambda: None for p in f.PHASES}, Path(temp)/'flow.json')
            self.assertEqual(result['completed'][-1], 'verify')
            self.assertEqual(result['result'], 'passed')
            self.assertFalse(result['production_ready'])

    def test_missing_phase_rejected_without_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'flow.json'
            with self.assertRaises(ValueError): f.execute({}, path)
            self.assertFalse(path.exists())
