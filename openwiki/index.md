---
okf_version: "0.1"
---

# Files

- [Architecture overview](architecture.md) - ASADO's layered architecture: source collection, DuckDB warehouse, Neo4j graph, daily/monthly cadences, the separate loop database, and the cockpit/MCP query surface.
- [Frontend and cockpit](frontend-and-cockpit.md) - ASADO's Chief-of-Staff cockpit: the cockpit_data.json payload contract, producer logic, Phase 2 frontend binding, and the distinction between verified signals and conjecture.
- [Loop and research workflows](loop-and-research.md) - ASADO's nightly alpha-hunting loop: dislocation engine, ledgers, harness verdicts, calibration reports, Triptych priors, graph features, and the canonical nightly brief.
- [Operations and runbooks](operations.md) - How to run ASADO's monthly, daily, and nightly pipelines safely — prerequisites, commands, resume/lock discipline, failure modes, and the automated OpenWiki documentation workflow.
- [Prediction markets and Brier Gate](prediction-markets.md) - ASADO's prediction-market surfaces: the general predmkt pipeline and the Brier Gate experiment that tests whether the warehouse adds incremental forecasting value over market prices.
- [OpenWiki quickstart](quickstart.md) - Entry point for ASADO's OpenWiki knowledge base — a hybrid macro/research/trading platform for a 34-country universe with DuckDB, Neo4j, daily/monthly pipelines, an alpha-hunting loop, prediction-market experiments, and a Chief-of-Staff cockpit.
