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

from .lab_session import DEFAULT_MODEL, _searches, run_lab_session
from .paths import DOCKETS_DIR, loop_db_path


def all_searches() -> list[str]:
    return list(_searches().keys())

MIN_CARDS, MAX_CARDS = 3, 10


def _score_card(d: dict[str, Any]) -> tuple[int, str]:
    """Rank a canonical draft: reward richer relationship sets + clearer falsification +
    deeper cited evidence; penalize single-relationship dependency (FR4)."""
    members = d.get("members") or []
    fal = d.get("falsification") or {}
    fatal = fal.get("fatal_if") or []
    must = fal.get("must_check") or []
    summary = str(d.get("summary", ""))
    score = (min(len(members), 3) + min(len(fatal), 2) + min(len(must), 2)
             + min(len(summary) // 220, 3))
    if len(members) <= 1:
        score -= 1
    why = (f"{len(members)} member(s) · {len(fatal)} fatal_if · {len(must)} must_check "
           f"· {len(summary)} chars evidence")
    return score, why


def curate(results: list[dict[str, Any]]) -> tuple[list[tuple[int, str, dict[str, Any]]], dict[str, int]]:
    """Dedupe by entity (keep highest-scored), rank, cap. Returns (shown, meta).
    NEVER pads to the minimum with low-quality cards."""
    raw = [d for r in results for d in r.get("drafts", [])]
    best: dict[Any, tuple[int, str, dict[str, Any]]] = {}
    for d in raw:
        score, why = _score_card(d)
        fam = d.get("family_name")
        if fam not in best or score > best[fam][0]:
            best[fam] = (score, why, d)
    ranked = sorted(best.values(), key=lambda x: x[0], reverse=True)
    shown = ranked[:MAX_CARDS]
    meta = {
        "raw": len(raw),
        "collapsed": len(raw) - len(best),
        "shown": len(shown),
        "dropped_validation": sum(len(r.get("dropped", [])) for r in results),
        "searches": len([r for r in results if not r.get("error")]),
    }
    return shown, meta


def _render(as_of: str, results: list[dict[str, Any]]) -> str:
    shown, meta = curate(results)
    lines = [
        f"# Discovery Docket — {as_of}",
        "",
        "> **UNVALIDATED · TOOL-OUTCOME-BLIND drafts.** Nothing here is validated alpha or a "
        "trade. Each card carries its certification route; with a null model cutoff, ideas route "
        "prospective-only until forward evidence accrues.",
        "",
        (f"Cards: {meta['shown']} shown (ranked, cap {MAX_CARDS}) · {meta['raw']} raw candidates "
         f"· {meta['collapsed']} collapsed by entity · {meta['dropped_validation']} dropped by strict "
         f"validation · {meta['searches']} searches."),
        "",
    ]
    for i, (score, why, c) in enumerate(shown, 1):
        fal = c.get("falsification") or {}
        sf = c.get("mythos_self_falsification") or {}
        lines += [
            f"## {i}. {c.get('family_name')}  ·  rank {score}",
            f"**Epistemic status:** {' · '.join(c.get('epistemic_status', []))}",
            f"*Why ranked:* {why}",
            "",
            c.get("summary", ""),
            "",
            "**Proposed relationships:** " + "; ".join(map(str, c.get("members", []))),
            "**Fatal if:** " + "; ".join(fal.get("fatal_if", [])),
            "**Must check:** " + "; ".join(fal.get("must_check", [])),
            "**Strongest counterargument:** " + str(sf.get("strongest_counterargument", "")),
            "**What would change my mind:** " + "; ".join(sf.get("what_would_change_my_mind", [])),
            "",
            "---",
            "",
        ]
    if meta["shown"] < MIN_CARDS:
        lines.append(f"> NOTE: only {meta['shown']} card(s) cleared strict validation — below the "
                     f"{MIN_CARDS} floor. NOT padded with low-quality cards.")
    skipped = [r for r in results if r.get("error")]
    if skipped:
        lines += ["", "### Skipped searches"]
        lines += [f"- `{r.get('search')}` — {str(r.get('error'))[:160]}" for r in skipped]
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
        try:
            results.append(run_lab_session(s, as_of, client=client, con=con, model_id=model_id))
        except Exception as e:  # noqa: BLE001 — one failing search must not kill the docket
            results.append({"search": s, "error": str(e), "drafts": [], "dropped": [], "usage": None})
    dockets_dir.mkdir(parents=True, exist_ok=True)
    out = dockets_dir / f"discovery_docket_{as_of.replace('-', '_')}.md"
    out.write_text(_render(as_of, results), encoding="utf-8")
    return out, results


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build the daily discovery docket (real Claude model).")
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--search", action="append", dest="searches",
                    default=None, help="repeatable; default = all 5 discovery searches")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--loop-db", default=None,
                    help="loop DB path; default = $ASADO_DATA_ROOT/loop/asado_loop.duckdb")
    ap.add_argument("--nightly", action="store_true",
                    help="nightly mode: no-op unless ASADO_RUN_DISCOVERY_LAB=1 (cost guard)")
    args = ap.parse_args(argv)
    searches = args.searches or all_searches()

    # Cost guard: the nightly job must NOT auto-spend on the Anthropic API unless
    # explicitly opted in. A manual run (no --nightly) always proceeds.
    if args.nightly and not os.environ.get("ASADO_RUN_DISCOVERY_LAB"):
        print("[docket] nightly Discovery Lab disabled — set ASADO_RUN_DISCOVERY_LAB=1 "
              "to enable live LLM runs. (no spend)")
        return 0

    import duckdb
    loop_db = args.loop_db or str(loop_db_path())
    if not Path(loop_db).exists():
        print(f"ERROR: loop DB not found at {loop_db} "
              "(set ASADO_DATA_ROOT to the checkout that holds Data/loop/)", file=sys.stderr)
        return 1
    con = duckdb.connect(loop_db, read_only=True)
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
