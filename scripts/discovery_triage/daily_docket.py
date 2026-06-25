"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/daily_docket.py
=============================================================================

DESCRIPTION:
The Daily Discovery Docket (FuguPRD §9.3). Runs one or more outcome-blind
discovery searches through the Lab and renders ONE markdown artifact with 3-10
unvalidated draft cards, each screaming its epistemic status + certification
route. The docket never claims validation — it is a reading list, not a book.

INPUT FILES: config/discovery_triage.yaml, config/model_registry.yaml,
             Data/loop/asado_loop.duckdb (read-only) for the real run.
OUTPUT FILES (write):
- .../journal/dockets/discovery_docket_YYYY_MM_DD.md
- (plus the looks/drafts written by lab_session)

VERSION: 1.0 (PR-5)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

USAGE:
  python -m scripts.discovery_triage.daily_docket --as-of 2026-06-24 \
      --search cross_surface_contradiction
=============================================================================
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

from .lab_session import DEFAULT_MODEL, run_lab_session
from .paths import DOCKETS_DIR

MIN_CARDS, MAX_CARDS = 3, 10
# Resolve the loop DB: worktrees don't carry the 119 MB data file, so allow an
# override to the main checkout's copy.
_DEFAULT_LOOP_DB = "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb"


def _render(as_of: str, results: list[dict[str, Any]]) -> str:
    cards: list[dict[str, Any]] = []
    for r in results:
        for d in r.get("drafts", []):
            cards.append(d)
    lines = [
        f"# Discovery Docket — {as_of}",
        "",
        "> **UNVALIDATED · TOOL-OUTCOME-BLIND drafts.** Nothing here is validated alpha or a "
        "trade. Each card carries its certification route; with a null model cutoff, ideas route "
        "prospective-only until forward evidence accrues.",
        "",
        f"Cards: {len(cards)} (cap {MIN_CARDS}-{MAX_CARDS}).",
        "",
    ]
    for i, c in enumerate(cards[:MAX_CARDS], 1):
        card = c.get("card", {})
        lines += [
            f"## {i}. [{c.get('object_type')}] {c.get('family_name')}",
            f"**Epistemic status:** {' · '.join(c.get('epistemic_status', []))}",
            "",
            card.get("summary", ""),
            "",
            "**Falsification (near-term):** " + "; ".join(card.get("falsification", {}).get("near_term", [])),
            "",
            "**Self-falsification — strongest objection:** "
            + str(card.get("mythos_self_falsification", {}).get("strongest_objection", "")),
            "**First probe to run:** "
            + str(card.get("mythos_self_falsification", {}).get("first_probe_to_run", "")),
            "",
            "---",
            "",
        ]
    if len(cards) < MIN_CARDS:
        lines.append(f"> NOTE: only {len(cards)} card(s) emitted — below the {MIN_CARDS} floor "
                     "(thin run; not padded).")
    return "\n".join(lines)


def build_docket(
    as_of: str,
    searches: list[str],
    *,
    client: Any = None,
    con: Any = None,
    model_id: str = DEFAULT_MODEL,
    dockets_dir: Path = DOCKETS_DIR,
) -> tuple[Path, list[dict[str, Any]]]:
    results = []
    for s in searches:
        results.append(run_lab_session(s, as_of, client=client, con=con, model_id=model_id))
    dockets_dir.mkdir(parents=True, exist_ok=True)
    out = dockets_dir / f"discovery_docket_{as_of.replace('-', '_')}.md"
    out.write_text(_render(as_of, results), encoding="utf-8")
    return out, results


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build the daily discovery docket (real Claude model).")
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--search", action="append", dest="searches",
                    default=None, help="repeatable; default cross_surface_contradiction")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--loop-db", default=os.environ.get("ASADO_LOOP_DB", _DEFAULT_LOOP_DB))
    args = ap.parse_args(argv)
    searches = args.searches or ["cross_surface_contradiction"]

    import duckdb
    if not Path(args.loop_db).exists():
        print(f"ERROR: loop DB not found at {args.loop_db}", file=sys.stderr)
        return 1
    con = duckdb.connect(args.loop_db, read_only=True)
    try:
        out, results = build_docket(args.as_of, searches, con=con, model_id=args.model)
    finally:
        con.close()
    total = sum(len(r.get("drafts", [])) for r in results)
    dropped = sum(len(r.get("dropped", [])) for r in results)
    in_tok = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in results)
    out_tok = sum((r.get("usage") or {}).get("output_tokens") or 0 for r in results)
    print(f"[docket] {out}")
    print(f"[docket] searches={searches} cards={total} dropped={dropped} "
          f"route={results[0].get('route') if results else None}")
    print(f"[docket] LIVE Anthropic usage ({args.model}): input={in_tok:,} output={out_tok:,} tokens")
    link = "file://" + str(out).replace(" ", "%20")
    print(f"[docket] {link}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
