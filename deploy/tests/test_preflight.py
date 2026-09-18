import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).parents[1]))
import preflight


class Preflight(unittest.TestCase):
    def test_failures_are_aggregated_without_mutations(self):
        calls = []
        def run(args):
            calls.append(args)
            raise RuntimeError('unavailable')
        report = preflight.check(run)
        self.assertEqual(len(report['blockers']), 4)
        self.assertEqual(report['result'], 'blocked')
        self.assertFalse(report['production_execution_enabled'])
        self.assertFalse(any(set(c) & {'fetch', 'reset', 'build', 'up', 'stop', 'rm'} for c in calls))
