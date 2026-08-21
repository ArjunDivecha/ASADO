# GMD Ingest Review - 2026-07-03

## Summary

Global Macro Database `2026_06` was ingested in the separate worktree:

`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-gmd-ingest`

Branch:

`codex/gmd-ingest-20260703`

This first pass treats GMD as an isolated annual structural macro reference corpus. It is loaded into `external_reference_gmd_*` tables and is intentionally not part of `unified_panel` or `feature_panel`.

## Artifacts

Processed outputs:

- `Data/processed/gmd_annual_panel.parquet`
- `Data/processed/gmd_raw_source_panel.parquet`
- `Data/processed/gmd_variable_meta.parquet`
- `Data/processed/gmd_country_meta.parquet`
- `Data/processed/gmd_release_manifest.parquet`

Raw-source cache:

- `Data/raw/gmd/2026_06/raw_sources/*.parquet`

New/modified code:

- `scripts/collect_gmd_annual.py`
- `scripts/setup_duckdb.py`
- `scripts/monthly_update.py`
- `scripts/build_schema_registry.py`
- `requirements.txt`

## Ingest Counts

Final collector check:

- GMD version: `2026_06`
- Package version: `global-macro-data==2.0.0`
- Harmonized rows: `355,695`
- Raw-source rows: `189,584`
- ASADO countries: `34`
- Unique sovereign ISO3s: `31`
- Official GMD variables ingested: `79`
- Years: `1086-2030`
- Forecast-like harmonized rows: `7,354`
- Raw-source variables with provider rows: `11`
- Raw-source providers: `54`

The 34-to-31 ISO3 collapse is expected:

- `CHN`: `ChinaA`, `ChinaH`
- `USA`: `NASDAQ`, `U.S.`, `US SmallCap`

Rows carry `graph_role` and `is_market_sleeve` so downstream code can distinguish sovereign macro states from equity sleeves.

## Verification

Commands run from the GMD worktree:

```bash
../ASADO/venv/bin/python -m py_compile \
  scripts/collect_gmd_annual.py \
  scripts/setup_duckdb.py \
  scripts/monthly_update.py \
  scripts/build_schema_registry.py

../ASADO/venv/bin/python scripts/collect_gmd_annual.py --dry-run --raw-sources
../ASADO/venv/bin/python scripts/collect_gmd_annual.py --raw-sources
../ASADO/venv/bin/python scripts/collect_gmd_annual.py --check
```

Isolated loader smoke test:

```python
import duckdb, tempfile
from pathlib import Path
import scripts.setup_duckdb as setup

path = Path(tempfile.gettempdir()) / "asado_gmd_loader_test.duckdb"
if path.exists():
    path.unlink()
con = duckdb.connect(str(path))
setup.load_gmd_reference(con)
```

Loader output:

- `external_reference_gmd_annual`: `355,695` rows, 34 countries, 79 variables, `1086-2030`
- `external_reference_gmd_raw_sources`: `189,584` rows, 11 variables, 54 raw sources
- `external_reference_gmd_variable_meta`: `79` rows
- `external_reference_gmd_country_meta`: `34` rows
- `external_reference_gmd_manifest`: `1` row

## First Look

Best coverage:

- `59` variables have full 34-country non-forecast coverage with latest year at least 2024.
- Strong current structural candidates include `CA_GDP`, `govdebt_GDP`, `govdef_GDP`, `infl`, `REER`, `USDfx`, `rGDP_pc`, `unemp`, government revenue/expense/tax/debt ratios, consumption, investment, exports, imports, GDP, population.

Long-history spine:

- `nGDP`: starts `1086`, 34 countries
- `CPI`: starts `1209`, 34 countries
- `infl`: starts `1210`, 34 countries
- `rGDP`: starts `1270`, 34 countries
- `pop`: starts `1277`, 34 countries
- `exports`: starts `1280`, 34 countries
- `imports`: starts `1560`, 34 countries
- `govdebt_GDP`: starts `1670`, 34 countries

Thin or caveated variables:

- `M4`: only 3 countries.
- `ltrate`: 29 countries.
- `cgovdef` / `cgovdef_GDP`: 29 countries.
- Crisis flags are valuable for analogs but not current-state variables:
  - `BankingCrisis` last non-forecast year `2020`
  - `SovDebtCrisis` last non-forecast year `2017`
  - `CurrencyCrisis` last non-forecast year `2018`

Raw-source evidence:

- Priority raw-source variables requested: 13.
- Provider-level rows materialized for 11. The two fiscal raw files `govdebt_GDP` and `govdef_GDP` do not expose provider-value columns in this package beyond the harmonized value. The crisis files expose effectively one source-like column each, so they are not rich provenance panels.
- Largest chosen-source families in the raw evidence: `Derived`, `BIS`, `OECD_EO`, `JST`, `WDI`, `IMF_WEO`, `CS1/CS2`, `WB_infl`, `EUS`.

## Incorporation Recommendation

Keep the current isolated table design.

Do next:

1. Build `scripts/loop/build_gmd_structural_priors.py`.
2. Output `Data/work/loop/gmd_structural_priors.parquet`.
3. Load loop table `gmd_structural_priors` with tidy columns: `date, country, value, variable, source`.
4. Start with a small derived prior set:
   - `GMD_DEBT_STRESS_PRIOR`
   - `GMD_EXTERNAL_IMBALANCE_PRIOR`
   - `GMD_INFLATION_MEMORY_PRIOR`
   - `GMD_GROWTH_SCAR_PRIOR`
   - `GMD_CRISIS_MEMORY_PRIOR`
5. Add a reconciliation report comparing GMD annual values against existing ASADO IMF/WB/Bloomberg/T2 annualized values.
6. Use priors in briefs/cockpit as context only until a registered harness test says otherwise.

Do not do yet:

- Do not union GMD into `unified_panel`.
- Do not forward-fill annual rows to monthly.
- Do not let 2026-2030 forecast rows enter live evidence.
- Do not use raw annual variables as direct alpha signals.

## Verdict

GMD is worth keeping. The right use is structural macro memory, cross-source QA, and crisis analog retrieval. It should become a small prior layer only after derived features and PIT/use gates are explicit.
