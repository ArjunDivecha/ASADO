#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: regime/calib/jst_calib.py
=============================================================================

DESCRIPTION:
Read-only accessor for the JST bear-bottom conditional-return tables produced
by scripts/calibrate_jst_bearbottom.py. This is the thin API the live layer
uses so it never touches the raw 150-year JST panel — only the distilled
distributions.

Given a (real) equity drawdown, it returns the JST-calibrated forward 1/3/5-year
return distribution for that bear-bottom state (median, p10/p90, P(neg), …),
estimated over 1870-2020 across the 13 in-universe developed markets. This is
the once-in-a-century tail context the modern ~2000+ sample cannot provide.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/calib/jst_bearbottom_conditional_returns.json
    Nested distributions: state -> asset -> horizon -> stats.

OUTPUT FILES:
- None (library module).

VERSION: 1.0
LAST UPDATED: 2026-06-15
AUTHOR: Claude Code for Arjun Divecha

DEPENDENCIES: pandas (only for country_drawdowns helper); json/pathlib stdlib.

USAGE:
  from regime.calib.jst_calib import forward_distribution, bucket_for_drawdown
  dist = forward_distribution("equity", bucket_for_drawdown(-0.28), horizon=3)
  # -> {'n_obs':145,'median':0.045,'p10':-0.111,'prob_neg':0.33, ...}

NOTES:
- Returns None when the calibration file is absent or a cell is missing — the
  caller decides what missing tail context means; it is never fabricated.
=============================================================================
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

CALIB_JSON = Path(__file__).resolve().parent / "jst_bearbottom_conditional_returns.json"

# The 13 in-universe developed markets JST actually calibrates (T2 names) —
# i.e. scripts/collect_jst_macrohistory.JST_TO_T2.values(). Defined here in the
# live accessor layer so every consumer can split an in-scope DM (a same-market
# estimate) from any other T2 country, for which the JST distribution is only a
# DM ANALOGY. Static by design: JST R6 is a static historical release.
JST_DM_COUNTRIES = frozenset({
    "Australia", "Canada", "Denmark", "France", "Germany", "Italy", "Japan",
    "Netherlands", "Spain", "Sweden", "Switzerland", "U.K.", "U.S.",
})


def is_jst_dm(country: str) -> bool:
    """True if `country` is one of the 13 DMs JST calibrates directly (in-scope).

    For any other T2 country (the EMs, plus the NASDAQ / US SmallCap sleeves)
    the JST conditional distribution is a developed-market ANALOGY, not a
    same-market estimate — callers should label such rows accordingly.
    """
    return country in JST_DM_COUNTRIES


@lru_cache(maxsize=1)
def _tables() -> dict:
    if not CALIB_JSON.exists():
        return {}
    return json.loads(CALIB_JSON.read_text()).get("tables", {})


def bucket_for_drawdown(drawdown: float) -> str:
    """Map a (negative) equity drawdown to its JST drawdown-bucket state name.

    Buckets must match calibrate_jst_bearbottom.py: (0,-10] / (-10,-20] /
    (-20,-35] / (<=-35]%.
    """
    dd = min(drawdown, 0.0)
    if dd <= -0.35:
        return "dd_35_plus"
    if dd <= -0.20:
        return "dd_20_35"
    if dd <= -0.10:
        return "dd_10_20"
    return "dd_0_10"


def forward_distribution(asset: str, state: str, horizon: int) -> Optional[dict]:
    """Return the JST conditional forward-return stats for (asset, state, horizon).

    asset in {equity, bond, bill}; horizon in {1,3,5}. Returns None if missing.
    """
    return _tables().get(state, {}).get(asset, {}).get(str(horizon))


def lookup_by_drawdown(asset: str, drawdown: float, horizon: int = 3) -> Optional[dict]:
    """Convenience: distribution for the bucket implied by `drawdown`."""
    dist = forward_distribution(asset, bucket_for_drawdown(drawdown), horizon)
    if dist is not None:
        return {**dist, "state": bucket_for_drawdown(drawdown)}
    return None


def country_drawdowns(returns_piv, lookback_days: int = 1260) -> dict[str, float]:
    """Current cyclical drawdown per country from a (dates x countries) daily-return panel.

    drawdown = cumulative-return index / its running peak - 1, at the last date,
    with the peak taken over a TRAILING window (default ~5y = 1260 trading days)
    rather than the full history. A trailing peak captures the *current* bear
    cycle; a full-history peak would report a permanent large drawdown for any
    market that never reclaimed an old high (e.g. a 2007 peak), which is not a
    tradable bottom signal.

    NOMINAL over the modern window (no CPI deflation live) — used only to bucket
    a country into the JST state; in the low-inflation modern regime nominal and
    real drawdowns coincide closely enough for bucketing.
    """
    out: dict[str, float] = {}
    for country in returns_piv.columns:
        s = returns_piv[country].dropna()
        if len(s) < 60:
            continue
        s = s.iloc[-lookback_days:]
        idx = (1.0 + s).cumprod()
        dd = float(idx.iloc[-1] / idx.cummax().iloc[-1] - 1.0)
        out[country] = dd
    return out
