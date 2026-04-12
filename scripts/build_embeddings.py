#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_embeddings.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb    (unified_panel view — all factor values by country/date)

OUTPUT FILES:
- Neo4j: state_embedding property on each Country node
- Neo4j: countryStateIndex vector index for cosine similarity search

VERSION: 1.0
LAST UPDATED: 2026-04-12
AUTHOR: Arjun Divecha

DESCRIPTION:
Builds country-state embedding vectors from the DuckDB unified_panel and
stores them as vector properties on Country nodes in Neo4j, with a vector
index for nearest-neighbor (cosine similarity) search.

Pipeline:
  1. Query DuckDB for the latest available date per variable per country
  2. Pivot to wide format: 1 row per country, 1 column per variable
  3. Drop variables with >50% missing (per country fill is meaningless)
  4. Impute remaining missing values with column median
  5. Standardize (z-score) each variable
  6. PCA-compress to 128 dimensions (or fewer if <128 variables remain)
  7. Write embedding vectors to Country.state_embedding in Neo4j
  8. Create (or recreate) a vector index for cosine similarity search

Queries enabled:
  - "Find the 5 countries most similar to Turkey"
      MATCH (c:Country {t2_name: 'Turkey'})
      CALL db.index.vector.queryNodes('countryStateIndex', 6, c.state_embedding)
      YIELD node, score
      WHERE node <> c
      RETURN node.t2_name, score

  - Country-pair similarity:
      MATCH (a:Country {t2_name: 'Brazil'}), (b:Country {t2_name: 'India'})
      RETURN gds.similarity.cosine(a.state_embedding, b.state_embedding)

DEPENDENCIES:
- duckdb, pandas, numpy, scikit-learn, neo4j

USAGE:
  python scripts/build_embeddings.py
  python scripts/build_embeddings.py --dims 64       # use 64-d instead of 128
  python scripts/build_embeddings.py --no-pca        # skip PCA, use raw z-scores

NOTES:
- Neo4j must be running: brew services start neo4j
- DuckDB must be built first: python scripts/setup_duckdb.py
- M4 Max will handle PCA on ~315 variables x 34 countries instantly
=============================================================================
"""

import argparse
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from neo4j import GraphDatabase
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "asado.duckdb"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "mythos2026"

EMBEDDING_DIMS = 128
MIN_COVERAGE_PCT = 50


def build_state_vectors(n_dims: int = EMBEDDING_DIMS, use_pca: bool = True) -> dict:
    """
    Build country-state embedding vectors from DuckDB.

    Returns dict mapping t2_name -> (embedding_list, embedding_date).
    """
    print("=" * 60)
    print("Building country-state embeddings")
    print("=" * 60)

    con = duckdb.connect(str(DB_PATH), read_only=True)

    print("\n  Querying latest values per country-variable ...")
    latest_df = con.execute("""
        WITH ranked AS (
            SELECT country, variable, value, date,
                   ROW_NUMBER() OVER (
                       PARTITION BY country, variable
                       ORDER BY date DESC
                   ) AS rn
            FROM unified_panel
            WHERE value IS NOT NULL
        )
        SELECT country, variable, value, date
        FROM ranked
        WHERE rn = 1
    """).fetchdf()
    con.close()

    print(f"  Raw: {len(latest_df)} country-variable pairs")
    print(f"  Countries: {latest_df['country'].nunique()}")
    print(f"  Variables: {latest_df['variable'].nunique()}")

    raw_date = latest_df["date"].max()
    embedding_date = pd.Timestamp(raw_date).strftime("%Y-%m-%d")

    print("\n  Pivoting to wide format ...")
    wide = latest_df.pivot_table(index="country", columns="variable", values="value")
    print(f"  Wide shape: {wide.shape}")

    n_countries, n_vars_raw = wide.shape
    missing_pct = wide.isnull().mean() * 100
    good_vars = missing_pct[missing_pct <= MIN_COVERAGE_PCT].index
    wide = wide[good_vars]
    n_vars = wide.shape[1]
    print(f"  After dropping >{MIN_COVERAGE_PCT}% missing: {n_vars} variables (dropped {n_vars_raw - n_vars})")

    print("  Imputing remaining missing values with column median ...")
    wide = wide.fillna(wide.median())

    remaining_nulls = wide.isnull().sum().sum()
    if remaining_nulls > 0:
        wide = wide.fillna(0)

    print("  Standardizing (z-score) ...")
    scaler = StandardScaler()
    scaled = scaler.fit_transform(wide.values)

    if use_pca:
        actual_dims = min(n_dims, n_vars, n_countries)
        print(f"  PCA: {n_vars} -> {actual_dims} dimensions ...")
        pca = PCA(n_components=actual_dims, random_state=42)
        embedded = pca.fit_transform(scaled)
        explained = pca.explained_variance_ratio_.sum() * 100
        print(f"  Explained variance: {explained:.1f}%")
    else:
        embedded = scaled
        actual_dims = n_vars
        print(f"  No PCA — using raw z-scores ({actual_dims} dims)")

    result = {}
    for i, country in enumerate(wide.index):
        vec = embedded[i].tolist()
        result[country] = (vec, embedding_date)

    print(f"\n  Built {len(result)} embeddings of dimension {actual_dims}")
    return result, actual_dims


def write_to_neo4j(embeddings: dict, n_dims: int):
    """Write embedding vectors to Country nodes and create vector index."""
    print("\n" + "=" * 60)
    print("Writing embeddings to Neo4j")
    print("=" * 60)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    driver.verify_connectivity()

    with driver.session() as session:
        session.run("DROP INDEX countryStateIndex IF EXISTS")

        count = 0
        for t2_name, (vec, emb_date) in embeddings.items():
            session.run("""
                MATCH (c:Country {t2_name: $name})
                SET c.state_embedding = $vector,
                    c.embedding_date = date($date),
                    c.embedding_dims = $dims
            """, name=t2_name, vector=vec, date=emb_date, dims=n_dims)
            count += 1

        print(f"  Updated {count} Country nodes with embeddings")

        session.run(f"""
            CREATE VECTOR INDEX countryStateIndex
            FOR (c:Country) ON (c.state_embedding)
            OPTIONS {{indexConfig: {{
                `vector.dimensions`: {n_dims},
                `vector.similarity_function`: 'cosine'
            }}}}
        """)
        print(f"  Created vector index: countryStateIndex ({n_dims}d, cosine)")

        import time as _t
        _t.sleep(2)

        idx_info = session.run("""
            SHOW INDEXES YIELD name, type, state
            WHERE name = 'countryStateIndex'
            RETURN name, type, state
        """).single()
        if idx_info:
            print(f"  Index status: {idx_info['state']}")

        print("\n  Testing similarity search (top 5 similar to first country) ...")
        test_name = list(embeddings.keys())[0]
        results = session.run("""
            MATCH (c:Country {t2_name: $name})
            CALL db.index.vector.queryNodes('countryStateIndex', 6, c.state_embedding)
            YIELD node, score
            WHERE node <> c
            RETURN node.t2_name AS country, score
            ORDER BY score DESC
            LIMIT 5
        """, name=test_name)
        print(f"  Countries most similar to {test_name}:")
        for r in results:
            print(f"    {r['country']}: {r['score']:.4f}")

    driver.close()
    print("\n  Done.")


def main():
    parser = argparse.ArgumentParser(description="ASADO Country-State Embeddings")
    parser.add_argument("--dims", type=int, default=EMBEDDING_DIMS,
                        help=f"PCA dimensions (default: {EMBEDDING_DIMS})")
    parser.add_argument("--no-pca", action="store_true",
                        help="Skip PCA, use raw standardized features")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"DuckDB not found at {DB_PATH} — run setup_duckdb.py first")
        sys.exit(1)

    start = time.time()
    embeddings, n_dims = build_state_vectors(
        n_dims=args.dims, use_pca=not args.no_pca
    )

    write_to_neo4j(embeddings, n_dims)

    elapsed = time.time() - start
    print(f"\nTotal time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
