"""Journalled first-adoption phase orchestration, without a production CLI.

Adapters must enforce Git identity/lock, validated build and fresh inspect.
No phase is optional and no rollback runs implicitly.
"""
from pathlib import Path
from adoption import persist

PHASES = ('preflight', 'sync', 'build', 'recheck', 'backup', 'retain',
          'create_main', 'create_voices', 'verify')


def execute(steps, journal):
    if set(steps) != set(PHASES) or any(not callable(steps[p]) for p in PHASES):
        raise ValueError('All migration phase adapters are required')
    path = Path(journal)
    if path.exists() or path.with_suffix('.pending').exists():
        raise RuntimeError('Existing migration journal requires inspection; no replay')
    state = {'result': 'in_progress', 'phase': 'preflight', 'completed': [],
             'rollback': 'explicit only', 'production_ready': False}
    persist(path, state)
    for phase in PHASES:
        state['phase'] = phase
        persist(path, state)
        try:
            # Adapters keep secrets in private artifacts, not return values.
            steps[phase]()
        except Exception:
            state['result'] = 'failed'
            state['impact'] = ('Old containers may be stopped or renamed; inspect retention journal'
                               if phase in PHASES[5:] else 'No container cutover attempted')
            persist(path, state)
            raise
        state['completed'].append(phase)
        persist(path, state)
    state['result'] = 'passed'
    persist(path, state)
    return state
