#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/write_graph_discoveries.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `similarity_twins`   — latest month's top-5 fundamental twins
    Table `leadlag_edges`      — latest month's lead-lag network edges
    Table `combiner_scores_daily` — latest daily composite country scores

OUTPUT FILES (Neo4j graph at bolt://localhost:7687, not files):
- SIMILAR_TO edges     Country -> Country, props: sim, as_of
    (replaced wholesale each run; fundamental-twins cosine similarity)
- LEADS edges          Country -> Country, props: corr, as_of
    (replaced wholesale each run; lag-1 return cross-correlation >= 0.15)
- Country.combiner_score / combiner_rank / combiner_as_of properties
    (latest daily walk-forward ridge composite, rank 1 = best)

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, graph machine build-out)

DESCRIPTION:
Closes the loop between the discovery machinery and the knowledge graph:
the fundamental-twins map, the lead-lag network, and the latest combiner
ranking — all discovered from data, none previously representable in
Neo4j — become first-class edges/properties that Claude Desktop (via the
MCP's run_neo4j_cypher) and the Neo4j browser can traverse. A 10th
grader's version: we taught the map new kinds of roads and pinned today's
leaderboard to it.

DEPENDENCIES:
- duckdb, pandas, neo4j (project venv)

USAGE:
 python scripts/loop/write_graph_discoveries.py          # write latest state
 python scripts/loop/write_graph_discoveries.py --check  # count edges

NOTES:
- Only the LATEST month's edges are kept in Neo4j (the graph is a "now"
  surface; history lives in DuckDB tables similarity_twins / leadlag_edges).
- FAIL-IS-FAIL: empty source tables abort (exit 1). Neo4j down → PARTIAL (exit 2)
  because this step is optional=true in the governance contract; the graph is a
  query surface, not a data source — DuckDB holds the canonical history.
=============================================================================
"""

from __future__ import annotations

import argparse
import socket
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import loop_connection  # noqa: E402

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "mythos2026")


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [graph_write] {msg}", flush=True)


def _neo4j_reachable(host: str = "localhost", port: int = 7687, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def write() -> int:
    if not _neo4j_reachable():
        log("WARNING: Neo4j bolt port unreachable — skipping graph write (PARTIAL)")
        return 2

    from neo4j import GraphDatabase

    con = loop_connection(read_only=True)
    try:
        twins = con.execute("""
            SELECT focal, neighbor, sim, month FROM similarity_twins
            WHERE month = (SELECT MAX(month) FROM similarity_twins)
        """).fetchdf()
        leads = con.execute("""
            SELECT leader, follower, corr, month FROM leadlag_edges
            WHERE month = (SELECT MAX(month) FROM leadlag_edges)
        """).fetchdf()
        scores = con.execute("""
            SELECT country, value,
                   RANK() OVER (ORDER BY value DESC) AS rnk,
                   date
            FROM combiner_scores_daily
            WHERE date = (SELECT MAX(date) FROM combiner_scores_daily)
        """).fetchdf()
    finally:
        con.close()
    if twins.empty or leads.empty or scores.empty:
        raise RuntimeError("a source table is empty — run the builders first (FAIL-IS-FAIL)")

    twins["month"] = twins["month"].astype(str)
    leads["month"] = leads["month"].astype(str)
    scores["date"] = scores["date"].astype(str)

    drv = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        with drv.session() as s:
            s.run("MATCH ()-[r:SIMILAR_TO]->() DELETE r")
            s.run("""
                UNWIND $rows AS row
                MATCH (a:Country {t2_name: row.focal})
                MATCH (b:Country {t2_name: row.neighbor})
                MERGE (a)-[e:SIMILAR_TO]->(b)
                SET e.sim = row.sim, e.as_of = row.month
            """, rows=twins.to_dict("records"))

            s.run("MATCH ()-[r:LEADS]->() DELETE r")
            s.run("""
                UNWIND $rows AS row
                MATCH (a:Country {t2_name: row.leader})
                MATCH (b:Country {t2_name: row.follower})
                MERGE (a)-[e:LEADS]->(b)
                SET e.corr = row.corr, e.as_of = row.month
            """, rows=leads.to_dict("records"))

            s.run("""
                UNWIND $rows AS row
                MATCH (c:Country {t2_name: row.country})
                SET c.combiner_score = row.value,
                    c.combiner_rank = row.rnk,
                    c.combiner_as_of = row.date
            """, rows=scores.to_dict("records"))

            n_sim = s.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS n").single()["n"]
            n_lead = s.run("MATCH ()-[r:LEADS]->() RETURN count(r) AS n").single()["n"]
            n_scored = s.run("MATCH (c:Country) WHERE c.combiner_score IS NOT NULL "
                             "RETURN count(c) AS n").single()["n"]
    finally:
        drv.close()
    if not (n_sim and n_lead and n_scored):
        raise RuntimeError(f"write-back incomplete: sim={n_sim} leads={n_lead} scored={n_scored}")
    log(f"SIMILAR_TO={n_sim} (as of {twins['month'].iloc[0]}), "
        f"LEADS={n_lead} (as of {leads['month'].iloc[0]}), "
        f"combiner scores on {n_scored} countries (as of {scores['date'].iloc[0]})")
    return 0


def check() -> int:
    if not _neo4j_reachable():
        log("WARNING: Neo4j bolt port unreachable — cannot run check (PARTIAL)")
        return 2

    from neo4j import GraphDatabase

    drv = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        with drv.session() as s:
            n_sim = s.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS n").single()["n"]
            n_lead = s.run("MATCH ()-[r:LEADS]->() RETURN count(r) AS n").single()["n"]
            top = s.run("MATCH (c:Country) WHERE c.combiner_rank <= 5 "
                        "RETURN c.t2_name AS t2, c.combiner_rank AS r ORDER BY r").data()
    finally:
        drv.close()
    print(f"SIMILAR_TO: {n_sim}, LEADS: {n_lead}, top-5 combiner: "
          + ", ".join(f"{r['t2']}({r['r']})" for r in top))
    ok = bool(n_sim and n_lead and top)
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Write discovered edges/scores into Neo4j.")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    return check() if args.check else write()


if __name__ == "__main__":
    sys.exit(main())
