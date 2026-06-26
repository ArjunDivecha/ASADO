"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/forward_track.py
=============================================================================

DESCRIPTION:
The readout engine for the Prospective Incubator and the Graveyard Control Arm
(FuguPRD §17/§18). On each run it reads the incubator/graveyard rosters, and for
every matured (claim, horizon) that has not been scored yet, appends a `readout`
record with the forward RELATIVE return over that horizon. It is idempotent per
(claim_id, horizon_days, measurement_shape) and reads returns ONLY through a
whitelist of return surfaces (Invariant C — never an optimizer surface).

PR-2B implements the `single_country_event` shape end to end. The other shapes
(cross_sectional_rank_ic / long_short_bucket / analog_set_forward_readout) need the
entry-time signal cross-section, which is not on the roster; they are skipped (not
faked) until that snapshot is captured.

INPUT FILES (read):
- .../journal/prospective_queue/prospective_queue.jsonl
- .../journal/graveyard/graveyard_forward_tracking.jsonl
- Data/loop/asado_loop.duckdb (read-only) for returns, when run as a script.
OUTPUT FILES (append-only): readout records appended to the two roster files above.

VERSION: 1.0 (PR-2B)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: pandas; duckdb only when run as a script.
=============================================================================
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

from . import schemas
from .jsonl_store import append_jsonl, read_jsonl
from .paths import GRAVEYARD_TRACKING, PROSPECTIVE_QUEUE

# Invariant C: returns may be read ONLY from these surfaces. country_returns_daily
# is a LOGICAL name resolved to the daily_country_returns() helper (not a table).
RETURN_SURFACES = frozenset({"country_returns_daily", "country_returns_monthly"})


def resolve_return_surface(con: Any, surface: str) -> "Any":
    """Return a tidy (date, country, ret) DataFrame for a whitelisted surface.
    Raises PermissionError for anything else (an optimizer surface can never leak in)."""
    s = str(surface).strip().lower()
    if s not in RETURN_SURFACES:
        raise PermissionError(f"return surface {surface!r} is not whitelisted")
    from scripts.loop.loopdb import daily_country_returns  # lazy
    if s == "country_returns_daily":
        return daily_country_returns(con)
    return con.execute(
        "SELECT date, country, return_1m AS ret FROM country_returns_monthly"
    ).df()


def horizon_steps(h: Any) -> int:
    return int(str(h).lower().rstrip("d"))


def compute_single_country_readout(
    returns_df: Any, target_country: str, start_date: str, horizon: int
) -> dict[str, Any] | None:
    """Forward relative return for one country over `horizon` post-start observations.
    Returns None (immature) if fewer than `horizon` observations exist after start."""
    import pandas as pd

    df = returns_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    start = pd.to_datetime(start_date)
    fwd = df[df["date"] > start].sort_values("date")
    cum: dict[str, float] = {}
    first_date = None
    for country, g in fwd.groupby("country"):
        g = g.head(horizon)
        if len(g) < horizon:
            continue
        cum[country] = float((1.0 + g["ret"]).prod() - 1.0)
        if country == target_country:
            first_date = str(g["date"].iloc[0].date())
    if target_country not in cum:
        return None  # immature for the target country
    country_cum = cum[target_country]
    xs_mean = sum(cum.values()) / len(cum)
    return {
        "country_cum_return": round(country_cum, 6),
        "xs_mean_return": round(xs_mean, 6),
        "relative_return": round(country_cum - xs_mean, 6),
        "n_countries_in_xs": len(cum),
        "first_forward_date": first_date,
    }


def run_forward_track(
    roster_path: Path,
    arm: str,
    returns_for: Callable[[str], Any],
) -> list[dict[str, Any]]:
    """Append matured, not-yet-scored readouts for one roster arm. Idempotent."""
    rows = read_jsonl(roster_path)
    entries = [r for r in rows if r.get("record_kind") in ("incubator_entry", "graveyard_entry")]
    scored = {
        (r.get("claim_id"), r.get("horizon_days"), r.get("measurement_shape"))
        for r in rows if r.get("record_kind") == "readout"
    }
    appended: list[dict[str, Any]] = []
    for e in entries:
        shape = e.get("measurement_shape")
        surface = e.get("return_surface")
        start = e.get("start_date")
        target_country = e.get("target_country")
        for hz in e.get("expected_readouts", []) or []:
            horizon = horizon_steps(hz)
            key = (e.get("claim_id"), horizon, shape)
            if key in scored:
                continue
            if shape != "single_country_event":
                continue  # needs entry-time signal snapshot (not yet captured)
            if not target_country:
                continue
            metrics = compute_single_country_readout(
                returns_for(surface), target_country, start, horizon
            )
            if metrics is None:
                continue  # immature; retried next run
            readout = {
                "record_kind": "readout",
                "claim_id": e.get("claim_id"),
                "hypothesis_id": e.get("hypothesis_id"),
                "arm": arm,
                "measurement_shape": shape,
                "observation_date": date.today().isoformat(),
                "horizon_days": horizon,
                **metrics,
            }
            schemas.Readout.model_validate(readout)
            append_jsonl(roster_path, readout)
            appended.append(readout)
            scored.add(key)
    return appended


def open_loop_with_warehouse(read_only: bool = True) -> Any:
    """H5 (red-team 2026-06-26): open the loop DB AND attach the main warehouse
    read-only as `asado`. `resolve_return_surface('country_returns_daily')` resolves
    via `asado.t2_factors_daily`, so without this ATTACH the daily readout path raises
    CatalogException. Honors ASADO_DATA_ROOT (FR9) — NOT loopdb's hardcoded constants."""
    import duckdb
    from .paths import data_root, loop_db_path
    con = duckdb.connect(str(loop_db_path()), read_only=read_only)
    main_db = data_root() / "asado.duckdb"
    if main_db.exists():
        con.execute(f"ATTACH '{main_db}' AS asado (READ_ONLY)")
    return con


def main(argv: list[str] | None = None) -> int:
    from .paths import data_root, loop_db_path
    db = loop_db_path()  # honors ASADO_DATA_ROOT (FR9)
    if not db.exists():
        print(f"[forward_track] loop DB not found at {db} (set ASADO_DATA_ROOT); nothing to do.")
        return 0  # optional nightly step — a missing DB is a no-op, not a failure
    main_db = data_root() / "asado.duckdb"
    if not main_db.exists():
        print(f"[forward_track] main warehouse not found at {main_db}; the daily return "
              "surface needs asado.t2_factors_daily — nothing to do.")
        return 0
    con = open_loop_with_warehouse(read_only=True)
    try:
        returns_for = lambda surface: resolve_return_surface(con, surface)  # noqa: E731
        total: list[dict[str, Any]] = []
        total += run_forward_track(PROSPECTIVE_QUEUE, "incubator", returns_for)
        total += run_forward_track(GRAVEYARD_TRACKING, "graveyard", returns_for)
        print(f"[forward_track] appended {len(total)} readouts")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
