"""ASADO Discovery Triage V1.

JSONL/YAML-first scaffolding for quarantined discovery, provenance routing,
minimal triage, blind rulings, and forward tracking. This package deliberately
keeps state outside Data/asado.duckdb; durable records live under journal/ until
workflow stability justifies folded DuckDB tables.
"""

from .paths import BASE_DIR, JOURNAL_DIR

__all__ = ["BASE_DIR", "JOURNAL_DIR"]
