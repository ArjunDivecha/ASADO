#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: db_bridge.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb                  (DuckDB analytical store)
- Neo4j graph at bolt://localhost:7687

OUTPUT FILES:
- None (this is a library module, not a standalone script)

VERSION: 1.0
LAST UPDATED: 2026-04-11
AUTHOR: Arjun Divecha

DESCRIPTION:
Unified Python query interface bridging DuckDB (time-series analytics) and
Neo4j (knowledge graph). Provides the AsadoDB class with methods for panel
queries, graph queries, country profiles, factor snapshots, and factor edge
refresh.

Import this module from other scripts:
    from db_bridge import AsadoDB
    db = AsadoDB()
    df = db.query_panel("SELECT * FROM t2_master LIMIT 10")
    records = db.query_graph("MATCH (c:Country) RETURN c.t2_name LIMIT 5")
    profile = db.country_profile("Turkey")
    snapshot = db.factor_snapshot("BIS_Credit_GDP_Gap")
    db.close()

DEPENDENCIES:
- duckdb, neo4j, pandas

USAGE:
  # As a module:
  from scripts.db_bridge import AsadoDB

  # As a standalone test:
  python scripts/db_bridge.py
=============================================================================
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import duckdb
import pandas as pd
from neo4j import GraphDatabase

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "Data" / "asado.duckdb"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "mythos2026"


class AsadoDB:
    """Unified query interface across DuckDB and Neo4j."""

    def __init__(self, duckdb_path: Optional[Path] = None,
                 neo4j_uri: str = NEO4J_URI,
                 neo4j_user: str = NEO4J_USER,
                 neo4j_pass: str = NEO4J_PASS):
        """
        Initialize connections to both databases.

        Args:
            duckdb_path: Path to asado.duckdb file. Defaults to Data/asado.duckdb.
            neo4j_uri: Neo4j bolt URI. Defaults to bolt://localhost:7687.
            neo4j_user: Neo4j username.
            neo4j_pass: Neo4j password.
        """
        self._duckdb_path = duckdb_path or DB_PATH
        self._duck = duckdb.connect(str(self._duckdb_path), read_only=True)

        self._neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))
        self._neo4j_driver.verify_connectivity()
        self._factor_surface_name: Optional[str] = None

    def _factor_surface(self) -> str:
        """Return the default factor-query surface, preferring feature_panel when present."""
        if self._factor_surface_name is None:
            tables = {row[0] for row in self._duck.execute("SHOW TABLES").fetchall()}
            self._factor_surface_name = "feature_panel" if "feature_panel" in tables else "unified_panel"
        return self._factor_surface_name

    def query_panel(self, sql: str, params: Optional[list] = None) -> pd.DataFrame:
        """
        Execute a DuckDB SQL query and return results as a DataFrame.

        Args:
            sql: SQL query string (can reference t2_master, external_factors,
                 extended_factors, gdelt_panel, unified_panel, normalized_panel,
                 or feature_panel when present).
            params: Optional list of bind parameters.

        Returns:
            pandas DataFrame with query results.
        """
        if params:
            return self._duck.execute(sql, params).fetchdf()
        return self._duck.execute(sql).fetchdf()

    def query_graph(self, cypher: str, **params) -> List[Dict[str, Any]]:
        """
        Execute a Neo4j Cypher query and return results as a list of dicts.

        Args:
            cypher: Cypher query string.
            **params: Named parameters for the Cypher query.

        Returns:
            List of dicts, one per result record.
        """
        with self._neo4j_driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def country_profile(self, country: str,
                        date: Optional[str] = None) -> Dict[str, Any]:
        """
        Pull a comprehensive profile for a country: all factor values from DuckDB
        plus all graph relationships from Neo4j.

        Args:
            country: T2 country name (e.g., "Turkey", "U.S.", "ChinaA").
            date: Optional date string (YYYY-MM-DD). Defaults to latest available.

        Returns:
            Dict with keys: country, date, factors (DataFrame), graph (dict of
            relationship types and connected entities).
        """
        surface = self._factor_surface()
        if date:
            date_filter = f"AND date = '{date}'"
            actual_date = date
        else:
            date_filter = f"AND date = (SELECT MAX(date) FROM {surface} WHERE country = '{country}')"
            actual_date = self._duck.execute(f"""
                SELECT MAX(date) FROM {surface}
                WHERE country = '{country}'
            """).fetchone()[0]

        factors_df = self._duck.execute(f"""
            SELECT variable, value, source
            FROM {surface}
            WHERE country = '{country}'
            {date_filter}
            ORDER BY source, variable
        """).fetchdf()

        graph = {}
        with self._neo4j_driver.session() as session:
            cb = session.run("""
                MATCH (c:Country {t2_name: $name})-[:HAS_CENTRAL_BANK]->(cb)
                RETURN cb.name AS central_bank
            """, name=country).values()
            graph["central_bank"] = cb[0][0] if cb else None

            commodities = session.run("""
                MATCH (c:Country {t2_name: $name})-[:EXPORT_EXPOSED_TO]->(com)
                RETURN com.name AS commodity
            """, name=country).values()
            graph["commodity_exports"] = [r[0] for r in commodities]

            sanctions = session.run("""
                MATCH (c:Country {t2_name: $name})-[:SUBJECT_TO]->(s)
                RETURN s.name AS program
            """, name=country).values()
            graph["sanctions"] = [r[0] for r in sanctions]

            crises = session.run("""
                MATCH (c:Country {t2_name: $name})-[:HAS_CRISIS_HISTORY]->(ce)
                RETURN ce.name AS crisis, ce.type AS type
                ORDER BY ce.start_date
            """, name=country).values()
            graph["crisis_history"] = [{"name": r[0], "type": r[1]} for r in crises]

            sources = session.run("""
                MATCH (c:Country {t2_name: $name})-[:DATA_AVAILABLE_FROM]->(ds)
                RETURN ds.name AS source
                ORDER BY ds.name
            """, name=country).values()
            graph["data_sources"] = [r[0] for r in sources]

            meta = session.run("""
                MATCH (c:Country {t2_name: $name})
                RETURN c.iso3, c.dm_em, c.region, c.currency_code
            """, name=country).single()
            if meta:
                graph["iso3"] = meta[0]
                graph["dm_em"] = meta[1]
                graph["region"] = meta[2]
                graph["currency"] = meta[3]

        return {
            "country": country,
            "date": str(actual_date) if actual_date else None,
            "factors": factors_df,
            "graph": graph,
        }

    def factor_snapshot(self, variable: str,
                        date: Optional[str] = None) -> pd.DataFrame:
        """
        Cross-sectional view of one factor across all countries at a given date.

        Args:
            variable: Factor variable name (e.g., "BIS_Credit_GDP_Gap", "1MRet").
            date: Optional date string (YYYY-MM-DD). Defaults to latest available
                  for that variable.

        Returns:
            DataFrame with columns: country, value, date, sorted by value descending.
        """
        surface = self._factor_surface()
        if date:
            date_clause = f"= '{date}'"
        else:
            date_clause = f"= (SELECT MAX(date) FROM {surface} WHERE variable = '{variable}')"

        return self._duck.execute(f"""
            SELECT country, value, date
            FROM {surface}
            WHERE variable = '{variable}'
            AND date {date_clause}
            AND value IS NOT NULL
            ORDER BY value DESC
        """).fetchdf()

    def refresh_factor_edges(self):
        """
        Update Neo4j HAS_FACTOR_EXPOSURE edges from the latest DuckDB data.
        Deletes existing edges and recreates from the most recent date.
        """
        latest_date = self._duck.execute(
            "SELECT MAX(date) FROM unified_panel WHERE variable = '1MRet'"
        ).fetchone()[0]

        latest = self._duck.execute("""
            SELECT country, variable, value
            FROM unified_panel
            WHERE date = ?
            AND value IS NOT NULL
        """, [latest_date]).fetchdf()

        with self._neo4j_driver.session() as session:
            session.run("MATCH ()-[r:HAS_FACTOR_EXPOSURE]->() DELETE r")

            rows = latest.to_dict("records")
            batch_size = 500
            total = 0
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                session.run("""
                    UNWIND $batch AS row
                    MATCH (c:Country {t2_name: row.country})
                    MATCH (f:Factor {name: row.variable})
                    MERGE (c)-[r:HAS_FACTOR_EXPOSURE]->(f)
                    SET r.value = row.value, r.date = date($date)
                """, batch=batch, date=str(latest_date))
                total += len(batch)

        print(f"Refreshed {total} HAS_FACTOR_EXPOSURE edges (as of {latest_date})")

    def tables(self) -> List[str]:
        """List all DuckDB tables."""
        return [r[0] for r in self._duck.execute("SHOW TABLES").fetchall()]

    def graph_stats(self) -> Dict[str, int]:
        """Get node and edge counts from Neo4j."""
        stats = {}
        with self._neo4j_driver.session() as session:
            labels = session.run(
                "CALL db.labels() YIELD label RETURN label"
            ).values()
            for (label,) in labels:
                count = session.run(
                    f"MATCH (n:{label}) RETURN COUNT(n)"
                ).single()[0]
                stats[f"node:{label}"] = count

            rels = session.run(
                "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
            ).values()
            for (rt,) in rels:
                count = session.run(
                    f"MATCH ()-[r:{rt}]->() RETURN COUNT(r)"
                ).single()[0]
                stats[f"edge:{rt}"] = count
        return stats

    def close(self):
        """Clean shutdown of both database connections."""
        self._duck.close()
        self._neo4j_driver.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == "__main__":
    print("=" * 60)
    print("AsadoDB Bridge — Quick Test")
    print("=" * 60)

    with AsadoDB() as db:
        print("\n1. DuckDB tables:")
        for t in db.tables():
            print(f"   {t}")

        print("\n2. Neo4j graph stats:")
        for k, v in db.graph_stats().items():
            print(f"   {k}: {v}")

        print("\n3. DuckDB query — latest BIS_Credit_GDP_Gap (top 10):")
        df = db.factor_snapshot("BIS_Credit_GDP_Gap")
        print(df.head(10).to_string(index=False))

        print("\n4. Neo4j query — countries under sanctions:")
        sanctions = db.query_graph("""
            MATCH (c:Country)-[:SUBJECT_TO]->(s:SanctionsProgram)
            RETURN c.t2_name AS country, s.name AS program
            ORDER BY c.t2_name
        """)
        for r in sanctions[:10]:
            print(f"   {r['country']} → {r['program']}")

        print("\n5. Country profile — Turkey:")
        profile = db.country_profile("Turkey")
        g = profile["graph"]
        print(f"   ISO3: {g['iso3']}, Region: {g['region']}, DM/EM: {g['dm_em']}")
        print(f"   Central Bank: {g['central_bank']}")
        print(f"   Commodity exports: {g['commodity_exports']}")
        print(f"   Crisis history: {[c['name'] for c in g['crisis_history']]}")
        print(f"   Data sources: {len(g['data_sources'])}")
        print(f"   Factor values at {profile['date']}: {len(profile['factors'])} variables")

    print("\n" + "=" * 60)
    print("All tests passed.")
    print("=" * 60)
