"""
=============================================================================
SCRIPT NAME: run_forecasts.py (Brier Gate step 3)
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/brier_gate/corpus.parquet
  (from build_corpus.py)
- /Users/arjundivecha/Dropbox/AAA Backup/.env.txt (ANTHROPIC_API_KEY,
  OPENROUTER_API_KEY — first occurrence of each)
- ASADO DuckDBs via context_packs.py (read-only, PIT-embargoed)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/brier_gate/packs.jsonl
  Cached context packs, one per (market_id, horizon): text + sha.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/brier_gate/forecasts.jsonl
  One line per completed forecast call (append-only, written immediately —
  resumable): key fields + probability + rationale + model + arm + sample.

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Runs the Brier Gate forecast fleet (docs/PRD_BRIER_GATE.md §4): for each
corpus row (market × horizon), three arms × K samples per model:
  A0 baseline   — question + resolution rules only
  A1 +warehouse — A0 + the point-in-time ASADO context pack
  A2 +market    — A1 + the market price at forecast time
Models: claude-sonnet-5 (Anthropic API) and deepseek/deepseek-v4-pro
(OpenRouter, OpenAI-compatible endpoint) on the full corpus;
claude-fable-5 on a deterministic subsample (--fable-markets N).
NO web/tool access anywhere — the anti-contamination requirement.

Resumable: existing (market_id, horizon, arm, model, sample) keys in
forecasts.jsonl are skipped on restart.

DEPENDENCIES:
- anthropic, openai, duckdb, pandas (project venv)

USAGE:
  python scripts/brier_gate/run_forecasts.py                 [full fleet]
  python scripts/brier_gate/run_forecasts.py --limit 5       [smoke test]
  python scripts/brier_gate/run_forecasts.py --models sonnet [one model only]
  python scripts/brier_gate/run_forecasts.py --samples 5 --workers 12

NOTES:
- Prompt forces JSON {"probability": float, "rationale": str}; a regex
  fallback extracts a bare probability if JSON parsing fails.
- Costs: see PRD §4 (~$50-120 total).
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts" / "brier_gate"))

WORK_DIR = BASE_DIR / "Data" / "work" / "brier_gate"
CORPUS_PATH = WORK_DIR / "corpus.parquet"
PACKS_PATH = WORK_DIR / "packs.jsonl"
FORECASTS_PATH = WORK_DIR / "forecasts.jsonl"
ENV_PATH = Path("/Users/arjundivecha/Dropbox/AAA Backup/.env.txt")

MODELS = {
    "sonnet": {"provider": "anthropic", "id": "claude-sonnet-5"},
    "deepseek": {"provider": "openrouter", "id": "deepseek/deepseek-v4-pro"},
    "fable": {"provider": "anthropic", "id": "claude-fable-5"},
}
ARMS = ["A0", "A1", "A2"]
MAX_TOKENS = 300
TEMPERATURE = 1.0

_write_lock = threading.Lock()


def _load_keys() -> dict[str, str]:
    keys: dict[str, str] = {}
    for line in ENV_PATH.read_text().splitlines():
        m = re.match(r"^([A-Z_]+)=(.+)$", line.strip())
        if m and m.group(1) not in keys:
            keys[m.group(1)] = m.group(2).strip()
    return keys


def _system_prompt(forecast_date: str) -> str:
    return (
        "You are a careful probabilistic forecaster evaluating a prediction-market "
        f"question. Today's date is {forecast_date}. You must forecast using ONLY "
        "your general knowledge up to your training cutoff plus any data explicitly "
        "provided in the prompt. Do not assume knowledge of any event after "
        f"{forecast_date}. Think briefly, then respond with ONLY a JSON object: "
        '{"probability": <float 0-1, the probability the market resolves YES>, '
        '"rationale": "<one sentence>"}'
    )


def _user_prompt(row, arm: str, pack_text: str | None) -> str:
    parts = [
        f"QUESTION: {row.question}",
        f"RESOLUTION RULES: {row.rules_text or '(none provided)'}",
        f"RESOLUTION DEADLINE: {pd.Timestamp(row.resolve_ts):%Y-%m-%d}",
    ]
    if arm in ("A1", "A2") and pack_text:
        parts.append(f"\nDATA:\n{pack_text}")
    if arm == "A2":
        parts.append(f"\nCURRENT MARKET PRICE (probability of YES): {row.p_mkt:.3f}")
    parts.append("\nYour probability that this resolves YES?")
    return "\n".join(parts)


def _parse_probability(text: str):
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            obj = json.loads(m.group(0))
            p = float(obj.get("probability"))
            if 0.0 <= p <= 1.0:
                return p, str(obj.get("rationale", ""))[:300]
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    m = re.search(r"(?:0?\.\d+|[01](?:\.0+)?)", text)
    if m:
        p = float(m.group(0))
        if 0.0 <= p <= 1.0:
            return p, text[:200]
    return None, text[:200]


class Caller:
    def __init__(self, keys: dict[str, str]):
        import anthropic
        from openai import OpenAI

        self.anthropic = anthropic.Anthropic(api_key=keys["ANTHROPIC_API_KEY"])
        self.openrouter = OpenAI(
            base_url="https://openrouter.ai/api/v1", api_key=keys["OPENROUTER_API_KEY"]
        )

    def call(self, provider: str, model_id: str, system: str, user: str) -> str:
        if provider == "anthropic":
            if "fable" in model_id:
                # Fable 5 uses adaptive thinking controlled by output_config.effort;
                # xhigh per Arjun — the frontier-effort arm.
                kwargs = {
                    "thinking": {"type": "adaptive"},
                    "output_config": {"effort": "xhigh"},
                    "max_tokens": 16000,
                }
            else:
                kwargs = {"thinking": {"type": "disabled"}, "max_tokens": MAX_TOKENS}
            resp = self.anthropic.messages.create(
                model=model_id,
                temperature=TEMPERATURE,
                system=system,
                messages=[{"role": "user", "content": user}],
                **kwargs,
            )
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        resp = self.openrouter.chat.completions.create(
            model=model_id,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            extra_body={"reasoning": {"enabled": False}},
        )
        return resp.choices[0].message.content or ""


def load_or_build_packs(corpus: pd.DataFrame) -> dict[tuple, dict]:
    packs: dict[tuple, dict] = {}
    if PACKS_PATH.exists():
        for line in PACKS_PATH.read_text().splitlines():
            try:
                rec = json.loads(line)
                packs[(rec["market_id"], rec["horizon_days"])] = rec
            except json.JSONDecodeError:
                continue
    todo = [
        row
        for row in corpus.itertuples()
        if (row.market_id, row.horizon_days) not in packs
    ]
    if todo:
        from context_packs import ContextPackBuilder

        print(f"Building {len(todo)} context packs...")
        cpb = ContextPackBuilder()
        with open(PACKS_PATH, "a") as fh:
            for i, row in enumerate(todo):
                try:
                    text, sha = cpb.build(row.question, row.event_title, row.tag, row.forecast_ts)
                except Exception as exc:
                    print(f"  ❌ pack failed for {row.market_id[:14]}/{row.horizon_days}d: {exc}")
                    continue
                rec = {
                    "market_id": row.market_id,
                    "horizon_days": int(row.horizon_days),
                    "text": text,
                    "sha": sha,
                }
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                packs[(row.market_id, row.horizon_days)] = rec
                if (i + 1) % 200 == 0:
                    print(f"  packs: {i + 1}/{len(todo)}", flush=True)
        cpb.close()
    return packs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="corpus rows (smoke test)")
    parser.add_argument("--models", default="sonnet,deepseek,fable")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--fable-markets", type=int, default=50)
    args = parser.parse_args()

    corpus = pd.read_parquet(CORPUS_PATH)
    if args.limit:
        corpus = corpus.head(args.limit)
    print(f"Corpus: {len(corpus)} rows, {corpus['market_id'].nunique()} markets")

    packs = load_or_build_packs(corpus)

    # deterministic fable subsample: first N market_ids sorted
    fable_ids = set(sorted(corpus["market_id"].unique())[: args.fable_markets])

    done: set[tuple] = set()
    if FORECASTS_PATH.exists():
        for line in FORECASTS_PATH.read_text().splitlines():
            try:
                r = json.loads(line)
                done.add((r["market_id"], r["horizon_days"], r["arm"], r["model"], r["sample"]))
            except json.JSONDecodeError:
                continue
    print(f"Already completed: {len(done)} calls")

    jobs = []
    for model_key in [m.strip() for m in args.models.split(",")]:
        spec = MODELS[model_key]
        for row in corpus.itertuples():
            if model_key == "fable" and row.market_id not in fable_ids:
                continue
            pack = packs.get((row.market_id, row.horizon_days))
            for arm in ARMS:
                if arm in ("A1", "A2") and pack is None:
                    continue
                for sample in range(args.samples):
                    key = (row.market_id, int(row.horizon_days), arm, model_key, sample)
                    if key in done:
                        continue
                    jobs.append((row, arm, model_key, spec, sample, pack))
    print(f"Jobs to run: {len(jobs)}")
    if not jobs:
        print("Nothing to do.")
        return 0

    caller = Caller(_load_keys())
    out_fh = open(FORECASTS_PATH, "a")
    n_ok = n_fail = 0

    def run_job(job):
        row, arm, model_key, spec, sample, pack = job
        fdate = f"{pd.Timestamp(row.forecast_ts):%Y-%m-%d}"
        system = _system_prompt(fdate)
        user = _user_prompt(row, arm, pack["text"] if pack else None)
        for attempt in range(3):
            try:
                text = caller.call(spec["provider"], spec["id"], system, user)
                break
            except Exception as exc:
                if attempt == 2:
                    return job, None, f"api_error: {exc}"
                time.sleep(2 * (attempt + 1))
        p, rationale = _parse_probability(text)
        if p is None:
            return job, None, f"parse_error: {text[:100]}"
        rec = {
            "market_id": row.market_id,
            "horizon_days": int(row.horizon_days),
            "arm": arm,
            "model": model_key,
            "sample": sample,
            "p_ai": p,
            "rationale": rationale,
            "p_mkt": float(row.p_mkt),
            "outcome": float(row.outcome),
            "event_slug": row.event_slug,
            "tag": row.tag,
            "forecast_ts": str(row.forecast_ts),
            "pack_sha": pack["sha"] if pack else None,
        }
        return job, rec, None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_job, j) for j in jobs]
        for i, fut in enumerate(as_completed(futures)):
            job, rec, err = fut.result()
            if rec is not None:
                with _write_lock:
                    out_fh.write(json.dumps(rec) + "\n")
                    out_fh.flush()
                n_ok += 1
            else:
                n_fail += 1
                if n_fail <= 20:
                    print(f"  ❌ {job[2]}/{job[1]} {job[0].market_id[:12]}: {err}")
            if (i + 1) % 500 == 0:
                print(f"  progress: {i + 1}/{len(jobs)} ({n_ok} ok, {n_fail} failed)", flush=True)

    out_fh.close()
    print(f"DONE: {n_ok} ok, {n_fail} failed")
    return 0 if n_ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
