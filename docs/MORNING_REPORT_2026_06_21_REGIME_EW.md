# Morning Report: Per-Country Regime Early-Warning PRD

Date: 2026-06-21

## Executive Verdict

Built and ran the new `regime_ew/` research module end to end. The PRD test **failed at Gate 3** under the strict walk-forward rules, so this should **not** be productionized as a return-timing overlay.

The important result is not "HMM regimes are useless." The narrower result is: these per-country monthly HMM adverse-state probabilities are persistent and not merely volatility states, but they do **not** lead each country's own forward returns strongly enough out of sample.

## Gate Results

| Gate | Result | Headline |
|---|---:|---|
| Gate 1: persistence | PASS | Median weighted 1-month persistence = 0.926; 100.0% of countries have adverse-state mean duration >= 3 months |
| Gate 2: volatility disguise | CLEAR | Median absolute correlation with trailing 6-month realized volatility = 0.152 |
| Gate 3: own-country forward-return lead | FAIL | Best signal was `dP_adverse`: 17/34 countries negative, median Spearman = -0.003, spread = -0.682%/month |
| Gate 4: artifact robustness | NOT RUN | The PRD says to stop at the first hard failed gate; Gate 3 failed |

Gate 3 failed all three required conditions:

- Required >= 23/34 countries with expected negative 1M lead; got 17/34 for `dP_adverse` and 11/34 for `P_adverse`.
- Required median Spearman <= -0.10; got -0.003 for `dP_adverse` and +0.040 for `P_adverse`.
- Required bottom-minus-top adverse-probability spread >= +0.50%/month; got -0.682%/month.

## Implementation Notes

- New module: `regime_ew/`
- Runner: `regime_ew/run_ew_test.py`
- Unit test: `regime_ew/tests/test_alignment.py`
- HMM library: `hmmlearn>=0.3.3`, installed in the repo venv and added to `regime_ew/requirements.txt`
- Features used: `12-1MTR_CS`, `REER_CS`, `RSI14_CS`, `Best PE _CS`, `Inflation_CS`, `Best ROE_CS`
- `Best ROE_CS` was used because there is no monthly-usable `GDELT*_CS` feature in `t2_master`
- Rows with more than two raw feature gaps are dropped. Remaining one- or two-feature standardized gaps are neutral-imputed to zero after the one-month forward-fill attempt.
- Walk-forward HMMs are refit annually using only data before the prediction year.
- Adverse-state labels are ranked using training-window forward `1MRet` only.
- Gate metrics use only walk-forward OOS posteriors.

## v1-Trap Diagnostic

The leaked full-sample diagnostic looked more flattering, which is exactly why the PRD's discipline matters:

- Full-sample `P_adverse`: 28/34 countries negative, p = 0.000098, but median Spearman only -0.028.
- Full-sample `dP_adverse`: 23/34 countries negative, p = 0.029, but median Spearman only -0.050.
- Full-sample spread was +0.667%/month.

Even the leaked diagnostic did not clear the median-Spearman threshold, and the clean walk-forward result flipped the economic spread negative.

## Verification

Commands run:

```bash
./venv/bin/python -m py_compile regime_ew/run_ew_test.py regime_ew/src/ew_model.py regime_ew/tests/test_alignment.py
./venv/bin/python -m pytest regime_ew/tests/test_alignment.py -q
./venv/bin/python regime_ew/run_ew_test.py
```

Validation checks:

- Syntax check passed.
- Alignment unit test passed.
- Full PRD runner completed.
- Artifact audit found 34 countries, 7,128 walk-forward signal rows, 34 HMM parameter JSON files, 611 walk-forward fits, and zero recorded fit failures.
- The accidental legacy `regime/data/processed/t2_factors_cs.parquet` cache modification from the old loader path was restored.

## Artifacts

- Main results: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/RESULTS.md>
- Manifest: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/manifest.json>
- Walk-forward signals: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/ew_signals.parquet>
- Gate 1 metrics: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/gate1_persistence.parquet>
- Gate 2 metrics: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/gate2_volatility.parquet>
- Gate 3 metrics: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/gate3_lead.parquet>
- HMM params: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/hmm_params/>
- Figures: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/figures/>

Raw paths:

- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/RESULTS.md`
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/manifest.json`
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/MORNING_REPORT_2026_06_21_REGIME_EW.md`

