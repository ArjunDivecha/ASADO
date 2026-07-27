# ASADO

A hybrid data-collection and research platform for a 34-country macro universe. A DuckDB +
Neo4j warehouse ingests 26+ free sources, World Bank commodities, and ~28 Bloomberg
variables; on top of it runs the **Alpha-Hunting Loop**, a nightly engine that finds
cross-subsystem dislocations, forms hypotheses, and puts them through a skeptic harness.

Its actual product is *trustworthy falsification*. Most candidate signals are expected to
die, and the discipline that kills them honestly is the asset. Country and factor returns
are the **outcome source of truth**; commodities, GDELT, Bloomberg, graph edges, and
prediction markets are explanatory and must be joined back to returns before any
performance claim.

## Start with the skills, not this file

This repo carries eight `asado-*` skills that hold the real detail and are maintained more
carefully than any prose here. **Route to `asado-start-here` on any zero-context session**;
it hands off to the right sibling:

| Need | Skill |
|---|---|
| Oriented from zero; which docs are current | `asado-start-here` |
| Run a stage, check health, tail a log, run tests | `asado-operations` |
| Something is broken right now | `asado-debugging-playbook` |
| Why is it built this way; what breaks if I change it | `asado-architecture-contract` |
| May I change this, and how is it gated | `asado-change-control` |
| Design and run an experiment | `asado-research-protocol` |
| Has this idea already been killed | `asado-graveyard` |

`AGENTS.md` carries the most current operational gotchas and is updated more often than
this file. `docs/factor_reference.md` is the auto-regenerated catalog of everything in the
warehouse. `llmchat.md` runs behind — use `git log` plus `AGENTS.md` for true current state.

## The rules you need before you touch anything

These live here rather than in a skill because a session can destroy something before it
finishes reading a skill.

**The main checkout is production.** launchd runs whatever is in this tree. Never switch
branches here — use `git worktree add "../ASADO-exp-<name>"`. `A Complete/Fable Daily
Trading` reads the loop DB read-only at 12:20 PT.

**Never hold a DuckDB connection**, even an idle read-only one, to either database. DuckDB
is one-writer/many-readers and a stray holder blocks the nightly writers — this caused the
2026-07-02/03 pipeline failures. Pipeline opens go through
`duckdb_lock_guard.guarded_connect()`; snapshot inputs with `snapshot_for_experiment.py`
before experimenting.

**`setup_duckdb.py` deletes and recreates `Data/asado.duckdb`.** Never create a persistent
table there. Durable loop state belongs in `Data/loop/asado_loop.duckdb`, which attaches the
main DB read-only as schema `asado`.

**Forward-return variables are hard-blacklisted as signals.** T2 `NMRet`/`NDRet`
(`1MRet/3MRet/6MRet/9MRet/12MRet` and daily `1DRet/5DRet/20DRet/60DRet/120DRet`) are
optimizer *targets*, not trailing momentum. Registering one as a predictor is look-ahead.
Canonical set: `scripts/harness/evaluate_signal.py`.

**Never union the isolated tables into `feature_panel` / `unified_panel`:** `ff_factors`
(regional, 8 series), the JST Macrohistory corpus, and optimizer outputs (`factor_returns`,
`factor_top20_membership`, `country_factor_attribution`). The optimizer exclusion guards
against the input/output cycle; the FF/JST exclusion stops region-level series being tiled
across 34 countries, which is a leakage class.

**Do not fix monthly-collector or T2-feed bugs without approval** — append to
`docs/USER_FIX_LIST.md` instead.

**Experiments write only** to `experiments/<name>/` or `Data/work/experiments/<name>/`.
Never touch `Data/processed/`, `Data/loop/`, shared `Data/work/`, `config/`, or `ledgers/`.
New packages go in a per-experiment `uv venv`, never the project `venv/` the nightly
pipeline depends on. Avoid long-held resources 06:00–08:30 PT.

**Cost gating is retired.** The 25bp one-way cost law was retracted 2026-07-13. The
harness's breakeven-bps output is informational — never use it to kill a signal, and ignore
cost-based verdicts in older records.

## Data conventions

First-of-month dates. Exact T2 country names (`Brazil`, `ChinaA`, `U.S.`). Tidy/long schema
`(date, country, value, variable, source)`. China broadcasts to **both** ChinaA and ChinaH;
United States to U.S., NASDAQ, and US SmallCap. `config/country_mapping.json` is the
Rosetta Stone for source codes.

Bloomberg runs under the OpusBloomberg conda env (Terminal logged in on Parallels);
`collect_*_bbg.py` write parquet only, paired `load_*.py` run in the project venv. Invoke
conda by absolute path in anything launchd runs — its PATH has no `/opt/homebrew/bin`.
Confirm every new ticker's country: `GSAB10YR` is South Africa's 10Y, not Saudi Arabia's.
