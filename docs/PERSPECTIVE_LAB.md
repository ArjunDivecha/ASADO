# ASADO Perspective Lab

Perspective Lab is an embedded ASADO research workbench for inspecting curated DuckDB surfaces with Perspective's pivotable datagrid UI.

It intentionally lives inside the ASADO repo because it depends on local ASADO paths, `Data/asado.duckdb`, and strategy artifacts under `Data/strategy/`.

## Run Locally

Start the read-only DuckDB API:

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
./venv/bin/python scripts/perspective_lab_server.py
```

Start the Vite frontend in a second terminal:

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/frontend/perspective_lab"
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5174
```

## Build And Serve From Python

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/frontend/perspective_lab"
npm run build

cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
./venv/bin/python scripts/perspective_lab_server.py
```

Open:

```text
http://127.0.0.1:7832
```

## Data Contract

The server exposes focused read-only datasets instead of the entire warehouse:

- Daily country returns from `t2_factors_daily`.
- Daily optimizer factor returns from `factor_returns_daily`.
- Monthly factor payoff diagnostics from `factor_returns`.
- Latest country-factor attribution from `country_factor_attribution`.
- Latest prediction-market signals from `predmkt_signals_daily`.
- Latest World Bank commodity momentum features from `wb_commodity_features`.
- Warehouse freshness from `unified_panel`.
- Strategy #1 analog artifacts from `Data/strategy/analogs/v1/`.

The lab is an analyst/operator UI layer. It is not an alpha engine, backtester, order router, or replacement for the MCP/query assistant.

## Dependency Note

v1 intentionally uses `@perspective-dev/viewer` plus `@perspective-dev/viewer-datagrid` only. The optional D3FC chart plugin was left out because its current transitive dependency chain raised high-severity `npm audit` findings during implementation. Add chart plugins only after accepting or resolving that dependency risk.
