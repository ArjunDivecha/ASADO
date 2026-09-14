# REPRODUCE — ASADO Nonlinear Country-Return Study

All commands run from the experiment worktree
(`ASADO-exp-Nonlinear/`, branch `exp/Nonlinear`) with the main checkout's
venv: `ASADO=/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO;
PY=$ASADO/venv/bin/python`.

Frozen input snapshot (read-only, in the main checkout):
`$ASADO/Data/work/experiments/nonlinear_country_returns/snapshot_2026_09_13/`
(manifest `audit/snapshot_manifest.json`, sha256-pinned).

## Registration + integrity

```bash
$PY experiments/2026_09_nonlinear_country_returns/src/validate_registration.py
# expected: VALIDATE-REGISTRATION: PASS ...
```

Registration receipt: `governance/registration_receipt.json`
(experiment `M_20260913_001`); locked protocol: `governance/protocol.lock.json`.

## Phase drivers (in order)

```bash
$PY experiments/.../src/p01_audit.py          # field audit (done; artifacts in audit/)
$PY experiments/.../src/p02_calendars_labels.py
$PY experiments/.../src/p03_features.py
$PY experiments/.../src/p04_panel_splits.py
$PY -m pytest experiments/.../tests -q        # 27 synthetic tests
$PY experiments/.../src/p06_freeze.py         # dev-window-only generator params
$PY experiments/.../src/register_p06.py       # methodology-ledger registration
$PY experiments/.../src/p07_calibrate.py      # inference-size calibration
$PY experiments/.../src/p07_replay.py         # frozen historical replay (~25 min)
$PY experiments/.../src/p07_controls.py --reps 100 --workers 12   # ~15h
$PY experiments/.../src/p08_evaluate.py       # primary comparison + verdict
$PY experiments/.../src/p09_mechanism.py
$PY experiments/.../src/p09_sensitivity.py
$PY experiments/.../src/p10_portfolio.py
```

## Independent reproduction (PRD 15.3)

`origin_metrics.parquet` regenerates from stored forecasts alone:

```python
from metrics import load_scored, collect_forecasts, origin_metric_table
from runner import STREAMS
tab = origin_metric_table(load_scored(), collect_forecasts(REPLAY_DIR, STREAMS), STREAMS)
# == results/origin_metrics.parquet
```

Re-run of two fit segments reproduces selected configs and forecasts
within 1e-10 (tree leaf-parity verified at P05).

## Safety invariants

- No DuckDB connection is ever held open; all data access is parquet
  snapshot + open-query-close.
- Nothing under `Data/processed/`, `Data/loop/`, shared `Data/work/`,
  `config/`, or `ledgers/` is written by experiment code; the only ledger
  write was `register_methodology_experiment` (authorized API).
- No scheduler, broker, or collector change; P12 shadow operation is
  disabled by default and not authorized.
