#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: triptych_tool_link.py
=============================================================================

INPUT FILES:
- None (pure URL construction from CLI arguments / function parameters).

OUTPUT FILES:
- None (prints a Triptych URL, or a Markdown link with --markdown).

VERSION: 1.0
LAST UPDATED: 2026-07-02
AUTHOR: Arjun Divecha (salvaged from the codex/triptych worktree, Phase 0 of
        PRD_Triptych_Prediction_Prior_Layer.md)

DESCRIPTION:
Build shareable Triptych URLs for ASADO country/factor review. This is
deliberately a tool launcher, not a data loader. ASADO uses it to send
candidate country/factor pairs into the Triptych visual workbench
(https://triptych-one.vercel.app) for point-in-time diagnostics before
deciding whether to register a formal harness hypothesis. Also imported by
scripts/loop/build_triptych_scan.py to stamp deep-links onto scan rows.

DEPENDENCIES:
- Standard library only.

USAGE:
 python scripts/triptych_tool_link.py --factor REER --country India
 python scripts/triptych_tool_link.py --factor REER --country India --markdown
=============================================================================
"""

from __future__ import annotations

import argparse
from urllib.parse import urlencode

DEFAULT_BASE_URL = "https://triptych-one.vercel.app/triptych.html"

NORMALIZATIONS = {
    "raw",
    "history_z",
    "cross_var_pct",
}
RETURN_MODES = {
    "absolute",
    "relative",
}
RANGES = {
    "all",
    "10y",
    "5y",
    "3y",
    "1y",
}
THRESHOLDS = {
    "pit",
    "full",
}
HORIZONS = {1, 3, 6, 12, 24, 36}
BUCKETS = {10, 5, 3}


def build_triptych_url(
    *,
    factor: str,
    country: str,
    normalization: str = "history_z",
    return_mode: str = "relative",
    horizon: int = 12,
    history_range: str = "10y",
    thresholds: str = "pit",
    buckets: int = 10,
    base_url: str = DEFAULT_BASE_URL,
) -> str:
    if normalization not in NORMALIZATIONS:
        raise ValueError(f"normalization must be one of {sorted(NORMALIZATIONS)}")
    if return_mode not in RETURN_MODES:
        raise ValueError(f"return_mode must be one of {sorted(RETURN_MODES)}")
    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {sorted(HORIZONS)}")
    if history_range not in RANGES:
        raise ValueError(f"history_range must be one of {sorted(RANGES)}")
    if thresholds not in THRESHOLDS:
        raise ValueError(f"thresholds must be one of {sorted(THRESHOLDS)}")
    if buckets not in BUCKETS:
        raise ValueError(f"buckets must be one of {sorted(BUCKETS)}")

    params = {
        "tab": "triptych",
        "tf": factor,
        "tc": country,
        "tn": normalization,
        "tm": return_mode,
        "th": str(horizon),
        "tr": history_range,
        "td": thresholds,
        "tb": str(buckets),
    }
    return f"{base_url}?{urlencode(params)}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Triptych tool URL for an ASADO country/factor pair."
    )
    parser.add_argument("--factor", required=True, help="Triptych factor/sheet name.")
    parser.add_argument("--country", required=True, help="Triptych country/market name.")
    parser.add_argument("--normalization", default="history_z", choices=sorted(NORMALIZATIONS))
    parser.add_argument("--return-mode", default="relative", choices=sorted(RETURN_MODES))
    parser.add_argument("--horizon", default=12, type=int, choices=sorted(HORIZONS))
    parser.add_argument("--range", default="10y", choices=sorted(RANGES), dest="history_range")
    parser.add_argument("--thresholds", default="pit", choices=sorted(THRESHOLDS))
    parser.add_argument("--buckets", default=10, type=int, choices=sorted(BUCKETS))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--markdown", action="store_true", help="Print a Markdown link.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    url = build_triptych_url(
        factor=args.factor,
        country=args.country,
        normalization=args.normalization,
        return_mode=args.return_mode,
        horizon=args.horizon,
        history_range=args.history_range,
        thresholds=args.thresholds,
        buckets=args.buckets,
        base_url=args.base_url,
    )
    if args.markdown:
        print(f"[Triptych: {args.country} / {args.factor}]({url})")
    else:
        print(url)


if __name__ == "__main__":
    main()
