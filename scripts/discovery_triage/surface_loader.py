"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/surface_loader.py
=============================================================================

DESCRIPTION:
Code-level enforcement of outcome blindness at the DATA-ACCESS layer (Invariant E).
Only PIT-safe, outcome-blind surfaces may be loaded for a Discovery Lab context;
everything else is refused in code (default-deny), regardless of what config or a
model requests. Enforcement is two-tier:
  - TABLE allowlist: `ALLOWED_SURFACES` (8 families). Anything else (especially
    `combiner_scores_daily`, which is a Ridge fit on FORWARD returns, and the
    non-PIT `graph_features_daily`, and the optimizer outputs) raises PermissionError.
  - COLUMN allowlist/denylist: `price_state_daily` carries raw realized return
    columns (`country_return_5d/21d`, `etf_return_5d/21d`, `basis_gap_*`) that are
    trailing/PIT-safe but are still raw returns — the per-table column allowlist
    exposes ONLY the `*_state_json` descriptors + `price_state_summary`. Tables with
    no explicit allowlist fall back to `FORBIDDEN_COLUMN_PATTERNS` (belt-and-suspenders).

The pure check (`check_surface`) has NO database dependency and is unit-tested
offline. `load_surface` / `load_country_snapshot` lazily open the loop DB
read-only and apply a `date <= as_of` PIT cut.

INPUT FILES (read, at load time only):
- Data/loop/asado_loop.duckdb (read-only), via scripts/loop/loopdb.loop_connection
OUTPUT FILES: none.

VERSION: 1.0 (PR-2A)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: duckdb (only when actually loading); pure checks need stdlib only.
=============================================================================
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

# 8 outcome-blind input families (FuguPRD §9.2 allowed_surfaces).
ALLOWED_SURFACES = frozenset({
    "price_state_daily",
    "valuation_monthly",
    "sovereign_signals",
    "market_implied_signals",
    "etf_flow_signals",
    "graph_features_pit_daily",
    "leadlag_features_daily",
    "similarity_features_daily",
})

# Explicitly-named forbidden outcome surfaces (clearer errors than plain default-deny).
FORBIDDEN_SURFACES = frozenset({
    "combiner_scores_daily", "combiner_scores", "combiner_weights",  # trained on forward returns
    "graph_features_daily",                                          # non-PIT sibling
    "factor_returns", "factor_returns_daily", "factor_top20_membership",
    "country_factor_attribution", "country_returns_monthly", "country_returns_daily",
    "harness_results", "harness_ic_series", "hypothesis_ledger",
    "dislocation_daily", "gap_holdout_daily",
})

# Per-table column allowlist. A table listed here exposes ONLY these columns
# (plus the date/country keys); everything else is dropped.
COLUMN_ALLOWLIST: dict[str, frozenset[str]] = {
    "price_state_daily": frozenset({
        "date", "country",
        "equity_state_json", "fx_options_state_json", "sovereign_state_json",
        "flow_state_json", "valuation_state_json", "predmkt_state_json",
        "price_state_summary", "source_freshness_json",
    }),
}

# Belt-and-suspenders denylist for tables WITHOUT an explicit column allowlist.
FORBIDDEN_COLUMN_PATTERNS = re.compile(
    r"(^|_)(forward|future|pnl|profit|realized_return|outcome|verdict|promoted)(_|$)"
    r"|country_return|etf_return|basis_gap|combiner|_ret_lead|fwd_ret"
)

# Forward optimizer TARGETS — never valid as a signal variable (CLAUDE.md).
FORWARD_RETURN_VARIABLES = frozenset({
    "1dret", "1mret", "3mret", "6mret", "12mret", "fwdret", "forward_return",
})

ALWAYS_KEEP = {"date", "country"}


class SurfaceNotAllowed(PermissionError):
    """Raised when a non-whitelisted table or column is requested."""


def check_surface(table: str, column: Optional[str] = None) -> bool:
    """Pure, DB-free gate. Raises SurfaceNotAllowed for a forbidden/non-whitelisted
    table, or (when `column` is given) for a column not permitted on that table."""
    t = str(table).strip().lower()
    if t in FORBIDDEN_SURFACES:
        raise SurfaceNotAllowed(f"{table!r} is a forbidden outcome surface")
    if t not in ALLOWED_SURFACES:
        raise SurfaceNotAllowed(f"{table!r} is not in ALLOWED_SURFACES (default-deny)")
    if column is not None:
        c = str(column).strip().lower()
        if c in ALWAYS_KEEP:
            return True
        allow = COLUMN_ALLOWLIST.get(t)
        if allow is not None:
            if c not in allow:
                raise SurfaceNotAllowed(
                    f"{table}.{column} is not on the per-table column allowlist"
                )
        elif FORBIDDEN_COLUMN_PATTERNS.search(c):
            raise SurfaceNotAllowed(
                f"{table}.{column} matches a forbidden column pattern"
            )
    return True


# Alias matching the plan's `surface_loader._check` reference.
_check = check_surface


def allowed_columns(table: str, available: Iterable[str]) -> list[str]:
    """Filter `available` columns down to those permitted for `table`."""
    keep: list[str] = []
    for col in available:
        try:
            check_surface(table, col)
        except SurfaceNotAllowed:
            continue
        keep.append(col)
    return keep


def load_surface(con: Any, table: str, as_of: str, *, latest_per_country: bool = True) -> list[dict[str, Any]]:
    """Load a single allowed surface as-of a date, with the column allowlist applied
    and a `date <= as_of` PIT cut. `con` is a DuckDB connection (real or in-memory)."""
    check_surface(table)
    available = [r[0] for r in con.execute(f'DESCRIBE "{table}"').fetchall()]
    cols = allowed_columns(table, available)
    if not cols:
        return []
    col_sql = ", ".join(f'"{c}"' for c in cols)
    where = 'CAST("date" AS DATE) <= CAST(? AS DATE)' if "date" in available else "TRUE"
    qual = ""
    if latest_per_country and "country" in available and "date" in available:
        # tidy (date,country,variable,value) tables must keep the latest per
        # (country, variable); wide tables keep the latest per country.
        parts = '"country"' + (', "variable"' if "variable" in available else "")
        qual = f'QUALIFY row_number() OVER (PARTITION BY {parts} ORDER BY "date" DESC) = 1'
    sql = f'SELECT {col_sql} FROM "{table}" WHERE {where} {qual}'
    params = [as_of] if "date" in available else []
    rows = con.execute(sql, params).fetchall()
    names = [d[0] for d in con.description]
    return [dict(zip(names, r)) for r in rows]


def load_country_snapshot(
    as_of: str,
    surfaces: Optional[list[str]] = None,
    *,
    con: Any = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build a PIT-safe per-country snapshot across `surfaces` (default: all allowed).
    Opens the loop DB read-only if `con` is not supplied. Every table+column is gated
    by `check_surface`, so a forbidden surface can never enter the snapshot."""
    surfaces = surfaces or sorted(ALLOWED_SURFACES)
    owned = False
    if con is None:
        import duckdb  # lazy: keeps the pure checks DB-free
        from .paths import loop_db_path
        con = duckdb.connect(str(loop_db_path()), read_only=True)  # honors ASADO_DATA_ROOT (FR9)
        owned = True
    try:
        out: dict[str, list[dict[str, Any]]] = {}
        for table in surfaces:
            out[table] = load_surface(con, table, as_of)
        return out
    finally:
        if owned:
            con.close()
