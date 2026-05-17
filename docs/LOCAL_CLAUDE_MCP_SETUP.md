# ASADO Local MCP Setup for Claude Desktop

This repo now includes a local MCP server at:

`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/asado_mcp_server.py`

Run it through the repo venv:

```bash
cd '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO'
./venv/bin/python scripts/asado_mcp_server.py
```

## Claude Desktop config

Add an `asado` entry to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "asado": {
      "command": "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python",
      "args": [
        "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/asado_mcp_server.py"
      ],
      "env": {
        "ANTHROPIC_API_KEY": "YOUR_ANTHROPIC_API_KEY"
      }
    }
  }
}
```

## Exposed tools

- `ask_asado`
  - Natural-language query assistant over ASADO.
  - Uses the existing planner + executor + interpreter.
  - Requires `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in the MCP server environment.
- `get_schema_summary`
  - Returns a compact schema snapshot for DuckDB + Neo4j.
- `run_duckdb_sql`
  - Executes validated read-only SQL.
- `run_neo4j_cypher`
  - Executes validated read-only Cypher.
- `get_country_profile`
  - Returns a combined DuckDB + Neo4j profile for one country.
- `event_window`, `events_in_window`, `daily_factor_series`
  - Daily/event workflows over T2, GDELT, factor returns, event log, and trading calendar.
- `country_returns`, `factor_return_series`, `country_factor_attribution`, `return_leaders`
  - Deterministic return surfaces. Use these first for performance, winner/loser, attribution, and event-reaction questions.
- `commodity_price_series`
  - World Bank Pink Sheet commodity/index series and derived monthly features. Commodity data is explanatory context; use return tools before claiming country/factor impact.
- `predmkt_snapshot`, `country_signal_now`, `event_market_set`
  - Curated prediction-market probabilities, country spillovers, and market search.

## Practical usage pattern

Best default inside Claude Desktop:

1. Ask Claude to use `get_schema_summary` if it needs to inspect the schema.
2. Ask Claude to use `ask_asado` for natural-language database questions.
3. Fall back to `run_duckdb_sql` or `run_neo4j_cypher` for explicit read-only queries.

## Important caveats

- `ChinaA` is the sovereign proxy for China in graph-network questions.
- `ChinaH`, `NASDAQ`, and `US SmallCap` are market sleeves, not sovereign countries.
- The sanctions layer reflects OFAC/SDN-linked country associations, not a clean sovereign target-country registry.
- Country and factor returns are ASADO's outcome source of truth. Explanatory surfaces such as commodities, prediction markets, Bloomberg, GDELT, and macrostructure should usually be tied back to returns before making performance claims.
- If you omit API keys from the MCP server `env`, the direct query tools still work, but `ask_asado` will not.
