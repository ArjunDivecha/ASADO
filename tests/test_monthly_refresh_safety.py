"""Offline regressions for the October monthly refresh repair."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import types
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from collect_t2_bloomberg import minimum_history_rows
from pipeline_lock import pipeline_lock
import collect_t2_bloomberg as collector


def test_monthly_floor_preserves_sparse_and_long_history():
    assert minimum_history_rows(True, 17) == 1000
    assert minimum_history_rows(False, 17) == 17
    assert minimum_history_rows(False, 320) == 320


def test_setup_does_not_retry_refusal():
    called = []
    def stop():
        called.append(1)
        raise RuntimeError('refused')
    with patch.dict(sys.modules, {'bbg': types.SimpleNamespace(bloomberg_setup=stop)}):
        with pytest.raises(RuntimeError):
            collector._setup_with_retry()
    assert len(called) == 1


@pytest.mark.parametrize('local', [False, True])
@pytest.mark.parametrize('kind', ['BloombergQuotaError', 'BloombergBudgetRefused', 'BloombergHardStop'])
def test_stop_aborts_batches_before_publication(local, kind, tmp_path):
    errors = {n: type(n, (RuntimeError,), {}) for n in
              ['BloombergQuotaError', 'BloombergBudgetRefused', 'BloombergHardStop']}
    calls = []
    class BBG:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def ref(self, *args): return 1
        def hist_batch(self, *args, **kwargs):
            calls.append(1)
            raise errors[kind]('stop')
    mods = {'bbg': types.SimpleNamespace(BBG=BBG, BloombergQuotaError=errors['BloombergQuotaError']),
            'budget_gate': types.SimpleNamespace(BloombergBudgetRefused=errors['BloombergBudgetRefused']),
            'quota_guard': types.SimpleNamespace(BloombergHardStop=errors['BloombergHardStop'])}
    output = tmp_path / 'master.xlsx'
    with patch.dict(sys.modules, mods), patch.object(collector, '_setup_with_retry'), patch.object(
            sys, 'argv', ['collect', '--sheets', '10Yr Bond' if local else 'Gold', '--out', str(output)]):
        with pytest.raises(errors[kind]): collector.main()
    assert calls == [1]
    assert not output.exists()


def test_competing_lock_refused_inheritance_and_release_work(tmp_path):
    path = tmp_path / 'pipeline.lock'
    code = ("import sys; from pathlib import Path; "
            f"sys.path.insert(0,{str(ROOT / 'scripts')!r}); "
            "from pipeline_lock import pipeline_lock;\n"
            "with pipeline_lock(Path(sys.argv[1])): print('acquired')")
    env = {k: v for k, v in os.environ.items() if k != 'ASADO_PIPELINE_LOCK_FD'}
    with pipeline_lock(path) as fd:
        blocked = subprocess.run([sys.executable, '-c', code, str(path)], env=env, capture_output=True)
        assert blocked.returncode != 0 and b'Another ASADO' in blocked.stderr
        allowed = subprocess.run([sys.executable, '-c', code, str(path)], pass_fds=(fd,),
                                 env=dict(env, ASADO_PIPELINE_LOCK_FD=str(fd)), capture_output=True)
        assert allowed.returncode == 0, allowed.stderr
    assert subprocess.run([sys.executable, '-c', code, str(path)], env=env, capture_output=True).returncode == 0


def test_completed_month_excludes_partial_observations():
    sys.path.insert(0, str(ROOT / 'scripts/gdelt_ingest'))
    from build_fullhistory_workbook import completed_observation_months
    frame = pd.DataFrame({'date': pd.to_datetime(['2026-09-30', '2026-10-02']),
                          'signal_month_end_date': pd.to_datetime(['2026-09-30', '2026-10-31'])})
    result = completed_observation_months(frame)
    assert len(result) == 1 and result.iloc[0]['date'] == pd.Timestamp('2026-09-30')
