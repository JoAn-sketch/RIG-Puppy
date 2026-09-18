import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).parents[1]))
import adoption


class RetentionTests(unittest.TestCase):
    def test_every_failure_is_journalled_and_halts(self):
        snapshot = {name: {'id': name + '-id'} for name in adoption.ORDER}
        for failure in range(9):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                journal = Path(temp) / 'journal.json'
                calls = []
                def run(command):
                    self.assertEqual(json.loads(journal.read_text())['steps'][-1]['status'], 'pending')
                    calls.append(command)
                    if len(calls) == failure + 1:
                        raise RuntimeError('injected')
                with self.assertRaisesRegex(RuntimeError, 'injected'):
                    adoption.retain(run, snapshot, 'test', journal)
                self.assertEqual(len(calls), failure + 1)
                self.assertEqual(journal.stat().st_mode & 0o777, 0o600)
                self.assertFalse(any('rm' in c or 'down' in c for c in calls))

    def test_success_preserves_ids_and_dependency_order(self):
        snapshot = {name: {'id': name + '-id'} for name in adoption.ORDER}
        with tempfile.TemporaryDirectory() as temp:
            calls = []
            result = adoption.retain(calls.append, snapshot, 'test', Path(temp) / 'journal.json')
            self.assertEqual(result['status'], 'retained')
            self.assertEqual(len(calls), 9)
            self.assertEqual(calls[0][-1], 'funasr-runtime-id')
            self.assertEqual(calls[-1][-2], 'xiaozhi-esp32-server-id')
