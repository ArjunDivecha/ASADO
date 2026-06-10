# ASADO Regime Conditioning Value Test

Research package to test whether deterministic macro regimes improve T2 factor IC and portfolio Sharpe (see `PRD.md`).

## Quick run

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
source venv/bin/activate
pip install -r regime/requirements.txt
python regime/run_regime_test.py
```

Outputs land in `regime/results/`; verdict in `regime/regime.md`.

## Layout

- `src/` — data loading, regime tagging, IC analysis, backtest
- `data/raw/` — FRED macro cache
- `data/processed/` — intermediate panels
- `results/` — parquet, figures, summary
- `tests/` — unit tests for tagger and alignment
- `notebooks/regime_test_analysis.ipynb` — notebook mirror of the pipeline

## Data

- T2 factors & country returns: `Data/asado.duckdb` (`t2_master`)
- Macro indicators: FRED API (`FRED_API_KEY` in env or `AAA Backup/.env.txt`)
- Supplement: ASADO `extended_factors` / `bloomberg_factors` where noted in logs
