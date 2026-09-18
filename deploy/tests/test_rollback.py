import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).parents[1]))
import adoption as a


class Rollback(unittest.TestCase):
    def fixture(self):
        snapshot = {n: {'id': 'old-' + n, 'restart': {'Name': 'always', 'MaximumRetryCount': 0}} for n in a.ORDER}
        replacements = {n: 'new-' + n for n in a.ORDER}
        current = []
        for n in a.ORDER:
            current += [{'Id': snapshot[n]['id'], 'Name': '/' + n + '-backup',
                         'State': {'Running': False}, 'HostConfig': {'NetworkMode': 'container:old-xiaozhi-esp32-server'}},
                        {'Id': replacements[n], 'Name': '/' + n}]
        return snapshot, replacements, current

    def test_restore_dependency_order_without_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            calls = []
            result = a.rollback(calls.append, *self.fixture(), 'test', Path(temp)/'log.json')
            starts = [c[-1] for c in calls if c[1] == 'start']
            self.assertEqual(starts, ['old-' + n for n in reversed(a.ORDER)])
            self.assertFalse(any(c[1] in {'rm', 'remove'} for c in calls))
            self.assertIn('health_not_verified', result['status'])

    def test_all_operation_failures_stop_with_pending_journal(self):
        for fail in range(18):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as temp:
                calls = []
                path = Path(temp)/'log.json'
                def run(c):
                    calls.append(c)
                    if len(calls) == fail+1: raise RuntimeError('injected')
                with self.assertRaisesRegex(RuntimeError, 'injected'):
                    a.rollback(run, *self.fixture(), 'test', path)
                self.assertEqual(len(calls), fail+1)
                self.assertEqual(json.loads(path.read_text())['steps'][-1]['status'], 'pending')

    def test_unknown_occupant_aborts_before_mutation(self):
        snapshot, replacements, current = self.fixture()
        current[-1]['Id'] = 'unrelated'
        calls = []
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(RuntimeError):
            a.rollback(calls.append, snapshot, replacements, current, 'test', Path(temp)/'log.json')
        self.assertEqual(calls, [])
