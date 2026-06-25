#!/usr/bin/env python3
"""Insert the Price-Discovery Gap pilot section into the latest dislocation brief."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.gap_engine_common import load_gap_config  # noqa: E402
from scripts.loop.loopdb import BRIEF_DIR, loop_connection  # noqa: E402

START = "<!-- GAP_ENGINE_TOP_START -->"
END = "<!-- GAP_ENGINE_TOP_END -->"


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [gap-render] {msg}", flush=True)


def latest_gap_date(con, explicit: str | None = None) -> pd.Timestamp:
    if explicit:
        return pd.Timestamp(explicit)
    d = con.execute("SELECT max(date) FROM gap_episode_marks").fetchone()[0]
    if d:
        return pd.Timestamp(d)
    d = con.execute("SELECT max(date) FROM dislocation_daily").fetchone()[0]
    if not d:
        raise RuntimeError("no dislocation_daily date")
    return pd.Timestamp(d)


def brief_path(date: pd.Timestamp) -> Path:
    return BRIEF_DIR / f"brief_{date.strftime('%Y_%m_%d')}.md"


def strip_existing(text: str) -> str:
    if START not in text or END not in text:
        return text
    pre = text.split(START, 1)[0].rstrip()
    post = text.split(END, 1)[1].lstrip()
    return pre + "\n\n" + post


def load_top_gaps(con, as_of: pd.Timestamp, limit: int) -> pd.DataFrame:
    return con.execute(
        """
        WITH latest_marks AS (
          SELECT *
          FROM gap_episode_marks
          WHERE CAST(date AS DATE) = CAST(? AS DATE)
          QUALIFY row_number() OVER (PARTITION BY gap_id ORDER BY mark_window) = 1
        )
        SELECT e.gap_id, e.entity, e.direction, e.gap_class, e.horizon_bucket,
               e.mechanism_text, e.preferred_ticker, e.currency_basis,
               e.invalidation_rule, e.tension_score_at_open,
               m.tension_score_current, m.absorption_state, m.days_active,
               m.expected_move_source, m.price_absorption_index,
               e.world_state_json, e.price_state_json
        FROM gap_episodes e
        JOIN latest_marks m USING (gap_id)
        WHERE e.status = 'open' AND e.research_only = false
        ORDER BY COALESCE(m.tension_score_current, e.tension_score_at_open) DESC
        """,
        [str(as_of.date())],
    ).fetchdf().head(limit * 4)


def dedupe_entity_direction(df: pd.DataFrame, limit: int) -> list[dict]:
    selected: list[dict] = []
    seen: set[tuple[str, str]] = set()
    related: dict[tuple[str, str], list[dict]] = {}
    for row in df.to_dict("records"):
        key = (row["entity"], row["direction"])
        if key in seen:
            related.setdefault(key, []).append(row)
            continue
        selected.append(row)
        seen.add(key)
        if len(selected) >= limit:
            break
    for row in selected:
        row["_related"] = related.get((row["entity"], row["direction"]), [])
    return selected


def select_diversified_gaps(df: pd.DataFrame, limit: int) -> list[dict]:
    """Headline list: strongest first, then first available rows from other classes."""
    rows = dedupe_entity_direction(df, max(limit * 4, limit))
    if not rows or limit <= 0:
        return []
    selected: list[dict] = []
    selected_ids: set[str] = set()
    seen_classes: set[str] = set()

    def add(row: dict) -> bool:
        gid = row.get("gap_id")
        if not gid or gid in selected_ids or len(selected) >= limit:
            return False
        selected.append(row)
        selected_ids.add(gid)
        seen_classes.add(row.get("gap_class"))
        return True

    add(rows[0])
    for row in rows[1:]:
        if row.get("gap_class") not in seen_classes:
            add(row)
        if len(selected) >= limit:
            return selected
    for row in rows:
        add(row)
        if len(selected) >= limit:
            return selected
    return selected


def compact_json(raw: str | None, max_items: int = 3) -> str:
    if not raw:
        return ""
    try:
        obj = json.loads(raw)
    except Exception:
        return str(raw)[:160]
    if not isinstance(obj, dict):
        return str(obj)[:160]
    bits = []
    for k, v in obj.items():
        if k in {"reading", "note"}:
            continue
        if isinstance(v, float):
            bits.append(f"{k}={v:.2f}")
        elif isinstance(v, (int, str)):
            bits.append(f"{k}={v}")
        if len(bits) >= max_items:
            break
    reading = obj.get("reading") or obj.get("note")
    if reading:
        bits.append(str(reading))
    return "; ".join(bits)[:260]


def render_section(con, as_of: pd.Timestamp) -> str:
    cfg, cfg_hash = load_gap_config()
    max_top = int(cfg.get("promotion", {}).get("max_top_gaps", 5))
    df = load_top_gaps(con, as_of, max_top)
    lines = [
        START,
        "",
        "## Top Price-Discovery Gaps (pilot)",
        "",
        "Read me: this section is an enhancement layer over the raw dislocation table below. "
        "Absorption is **provisional** while expected moves are severity-mapped; it is not yet validated ranking skill.",
        f"Config: `{cfg.get('config_version')}` `{cfg_hash[:12]}`.",
        "",
    ]
    if df.empty:
        lines.append("No open non-research price-discovery gap episodes for this as-of date.")
        lines.append("")
        lines.append(END)
        return "\n".join(lines)

    top = select_diversified_gaps(df, max_top)
    for i, r in enumerate(top, start=1):
        score = r.get("tension_score_current") or r.get("tension_score_at_open")
        provisional = "provisional " if r.get("expected_move_source") in {"severity_mapping", "neutral_default"} else ""
        lines.append(f"{i}. **{r['entity']} {r['direction']}** — {r['mechanism_text']}")
        lines.append(f"   - FACT price expression: `{r.get('preferred_ticker') or 'none'}`; currency basis `{r.get('currency_basis') or 'unknown'}`; horizon `{r.get('horizon_bucket')}`.")
        lines.append(f"   - INFERENCE tension: {score:.2f}; class `{r.get('gap_class')}`.")
        lines.append(f"   - Absorption: **{r.get('absorption_state')}** ({provisional}{r.get('expected_move_source')}); days active {r.get('days_active')}; index {r.get('price_absorption_index')}.")
        lines.append(f"   - World-state evidence: {compact_json(r.get('world_state_json'))}")
        lines.append(f"   - What would prove this wrong: {r.get('invalidation_rule')}")
        if r.get("_related"):
            rel = ", ".join(f"{x['gap_class']} {x['gap_id'][:8]}" for x in r["_related"][:3])
            lines.append(f"   - Related same-country gap episodes nested, not headline slots: {rel}")
        lines.append("")
    lines.append(END)
    return "\n".join(lines)


def insert_section(original: str, section: str) -> str:
    clean = strip_existing(original)
    if "<!-- GOVERNANCE_SCORECARD_END -->" in clean:
        pre, post = clean.split("<!-- GOVERNANCE_SCORECARD_END -->", 1)
        return (
            pre.rstrip()
            + "\n<!-- GOVERNANCE_SCORECARD_END -->\n\n"
            + section
            + "\n\n"
            + post.lstrip()
        ).rstrip() + "\n"
    lines = clean.splitlines()
    if not lines:
        return section + "\n"
    insert_at = 1
    for i, line in enumerate(lines[:12]):
        if line.strip() == "":
            insert_at = i + 1
            break
    out = lines[:insert_at] + ["", section, ""] + lines[insert_at:]
    return "\n".join(out).rstrip() + "\n"


def render(as_of: str | None = None, dry_run: bool = False) -> Path:
    con = loop_connection()
    try:
        cfg, _ = load_gap_config()
        date = latest_gap_date(con, as_of)
        path = brief_path(date)
        if not path.exists():
            raise FileNotFoundError(f"brief not found for {date.date()}: {path}")
        if not cfg.get("feature_flags", {}).get("render_top_gaps", True):
            cleaned = strip_existing(path.read_text())
            if not dry_run:
                path.write_text(cleaned)
                log(f"render_top_gaps=false; removed gap section if present: {path}")
            else:
                print(cleaned)
            return path
        section = render_section(con, date)
        rendered = insert_section(path.read_text(), section)
        if not dry_run:
            path.write_text(rendered)
            log(f"brief updated: {path}")
        else:
            print(rendered)
        return path
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Price-Discovery Gap section into the daily brief.")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    render(args.as_of, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
