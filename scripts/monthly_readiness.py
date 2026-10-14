#!/usr/bin/env python3
"""Monthly ASADO -> T2 NN readiness, acceptance and local alerts (no producers).

Inputs: /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/monthly_readiness.json,
Data/asado.duckdb (guarded, short read), scripts/config/t2_bbg_manifest.json;
/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 NN/rank_model/factor_set_v3_clean.json,
production/output/contracts/nn_contract_YYYY-MM.{json,parquet}, production/state/holdings.json;
/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/{budget_config.json,
logs/touched_securities_YYYY-MM.json,logs/gate_usage_YYYY-MM.json,
logs/master_bloomberg_log.csv,outputs/BLOOMBERG_HARD_STOP.json,recurring_extra.json}.
Outputs under ASADO/Data/monthly/: status.json, status.md, tickets/YYYY-MM.json,
accepted/YYYY-MM.json (exclusive-create), alerts.jsonl, events.jsonl, alert_state.json,
.readiness.lock. One deduplicated macOS notification per changed alert set.
Roots/config/counts are injectable for isolated tests. No provider imports, credential
reads, network, collection, VM operations, DB writes, orders, or messaging.
"""
from __future__ import annotations
import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from contextlib import ExitStack

ROOT = Path(__file__).resolve().parents[1]
PACIFIC = ZoneInfo("America/Los_Angeles")
CORE = {"t2", "gdelt", "bloomberg"}


def shift(month, offset):
    y, m = map(int, month.split("-"))
    n = y * 12 + m - 1 + offset
    return f"{n // 12:04d}-{n % 12 + 1:02d}"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def read(path, default=None):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with tmp.open("w") as f:
        f.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def append(path, event):
    with Path(path).open("a") as f:
        f.write(json.dumps(event, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def freshness(rows, factors, countries, target):
    """Exact required date, never MAX(date) alone; monthly availability lags apply.

    rows: source,variable,YYYY-MM,list-of-non-null-countries. T2/GDELT M+1
    labels require target; Bloomberg M requires target-1. Slow sources warn.
    Empty Bloomberg/GDELT inputs block; T2 per-input emptiness warns because
    its selected inputs include sparse/annual/quarterly observations. Preserve
    the NN's existing T2 source-level 90% gate; do not invent monthly values.
    Thin coverage always warns, aggregate <90% blocks core sources.
    """
    universe = set(countries)
    counts = {(s, v, d): set(c) & universe for s, v, d, c in rows}
    details, problems, warnings, groups = [], [], [], {}
    for f in factors:
        src, var, lag = f["source"], f["variable"], int(f["lag_months"])
        need = shift(target, -lag)
        history = [(d, c) for (s, v, d), c in counts.items() if s == src and v == var and c]
        latest = max((d for d, _ in history), default=None)
        have = counts.get((src, var, need), set())
        # Same denominator as NN: observed months, trailing 12; no invented cells.
        prior = [(d, c) for d, c in history if shift(need, -12) <= d < need]
        baseline = sum(len(c) for _, c in prior) / len(prior) if prior else 0
        ratio = len(have) / baseline if baseline else 0
        historically_present = set().union(*(c for _, c in prior)) if prior else set()
        missing = sorted(historically_present - have)
        state = "CURRENT" if have else "MISSING"
        if have and (not baseline or ratio < .90):
            state = "THIN"
        msg = f"{src}/{var}: requires {need}, latest {latest or 'none'}, {len(have)} countries; trailing mean {baseline:.1f}; missing {','.join(missing) or 'none'}"
        if not have:
            (problems if src in {"bloomberg", "gdelt"} else warnings).append(msg)
        elif state == "THIN":
            warnings.append(msg)
        details.append(dict(source=src, variable=var, lag_months=lag, required_month=need,
                            latest_month=latest, countries=len(have), trailing12_mean=round(baseline, 3),
                            coverage_ratio=round(ratio, 4), missing_countries=missing,
                            status=state, action="Refresh upstream and rebuild normalized input; do not fill missing cells" if state != "CURRENT" else None))
        groups.setdefault((src, lag), []).append(var)
    source_details = []
    for (src, lag), variables in sorted(groups.items()):
        need = shift(target, -lag)
        monthly = {}
        for (s, v, d), c in counts.items():
            if s == src and v in variables:
                monthly[d] = monthly.get(d, 0) + len(c)
        previous = [n for d, n in monthly.items() if shift(need, -12) <= d < need]
        baseline = sum(previous) / len(previous) if previous else 0
        have = monthly.get(need, 0)
        ratio = have / baseline if baseline else 0
        ok = have > 0 and ratio >= .90
        source_details.append(dict(source=src, lag_months=lag, required_month=need,
                                   rows=have, trailing12_mean=baseline, coverage_ratio=ratio, passed=ok))
        if not ok:
            (problems if src in CORE else warnings).append(f"{src} group requires {need}: {have} rows, {ratio:.1%} of trailing mean (90% gate)")
    prev = shift(target, -1)
    returns = counts.get(("t2", "1MRet", prev), set())
    if returns != universe:
        problems.append(f"Realized {prev} 1MRet: {len(returns)}/{len(universe)} countries; missing {','.join(sorted(universe - returns))}")
    return dict(passed=not problems, full_coverage=not problems and not warnings,
                problems=problems, warnings=warnings, inputs=details, sources=source_details,
                returns=dict(required_month=prev, countries=len(returns), missing=sorted(universe - returns)))


def load_counts(root, factors, countries):
    # Shared exclusion is held by caller; bounded one-thread query, close promptly.
    sys.path.insert(0, str(root / "scripts"))
    from duckdb_lock_guard import guarded_connect
    os.environ["ASADO_LOCK_GUARD_KILL"] = "0"
    con = guarded_connect(root / "Data/asado.duckdb", read_only=True, wait_budget_s=0, config={"threads": 1})
    try:
        selected = sorted({f["variable"] for f in factors} | {"1MRet"})
        return con.execute("""select source,variable,strftime(date,'%Y-%m'),list(distinct country)
            from feature_panel_observed where value is not null and isfinite(value)
            and variable in (select unnest(?)) and country in (select unnest(?))
            group by source,variable,date""", [selected, countries]).fetchall()
    finally:
        con.close()


def quota(root, scope, now, associations):
    """Read-only, conservative local arithmetic; NEVER calls decide/refusal writers.

    Preview only: not a quota reservation and not permission to send requests.
    A producer still must use the original hard-stop/gated-send at every request.
    """
    key = now.astimezone(PACIFIC).strftime("%Y-%m")
    cfg = read(root / "budget_config.json")
    if not cfg:
        raise RuntimeError("Bloomberg budget configuration absent")
    def touched(m):
        value = read(root / f"logs/touched_securities_{m}.json")
        if value is None:
            # A new month's ledger may legitimately not exist yet. Historical
            # absence is conservative: no recurring exemptions are inferred.
            return set()
        return set(value)
    existing = touched(key)
    recurring = (touched(shift(key, -1)) & touched(shift(key, -2))) | set(read(root / "recurring_extra.json", []))
    usage_file = root / f"logs/gate_usage_{key}.json"
    if existing and not usage_file.exists():
        raise RuntimeError("Current month touched names exist but gate usage missing; preflight unknown")
    usage = read(usage_file, {"free": {}})["free"]
    callers = {"ASADO"} | {a["caller"] for a in associations if a["month"] == key}
    used = sum(int(usage.get(c, 0)) for c in callers)
    names = set(scope["securities"])
    new = names - existing
    free_new = new - recurring
    today = now.astimezone(PACIFIC).date()
    hits = 0
    ledger = root / "logs/master_bloomberg_log.csv"
    if not ledger.exists():
        raise RuntimeError("Master Bloomberg hit ledger missing; preflight cannot establish headroom")
    with ledger.open(newline="") as f:
        for row in csv.DictReader(f):
            stamp = datetime.fromisoformat(row["timestamp"])
            if stamp.tzinfo is None:
                raise RuntimeError("Naive master ledger timestamp")
            if stamp.astimezone(PACIFIC).date() == today:
                hits += int(row["est_hits"] or 0)
            if stamp.astimezone(PACIFIC).strftime("%Y-%m") == key and not (root / f"logs/touched_securities_{key}.json").exists():
                raise RuntimeError("Current month master requests exist but touched-name ledger missing")
    reasons = []
    if (root / "outputs/BLOOMBERG_HARD_STOP.json").exists():
        reasons.append("Bloomberg hard-stop sentinel active; do not retry or clear automatically")
    if len(existing) + len(new) > cfg["monthly_ceiling"]:
        reasons.append("Projected distinct names exceed global monthly ceiling")
    if used + len(free_new) > cfg["free_new_per_caller_month"]:
        reasons.append("Projected ASADO-associated nonrecurring names exceed allowance")
    if hits + scope["estimated_hits"] > cfg["daily_hit_ceiling"]:
        reasons.append("Projected hits exceed daily ceiling")
    return dict(passed=not reasons, reasons=reasons, month=key, associated_callers=sorted(callers),
                associated_free_used=used, free_remaining=cfg["free_new_per_caller_month"] - used,
                scope_names=len(names), new_names=len(new), new_nonrecurring_names=len(free_new),
                projected_names=len(existing) + len(new), global_headroom=cfg["monthly_ceiling"] - len(existing),
                hits_today=hits, estimated_hits=scope["estimated_hits"],
                new_nonrecurring_securities=sorted(free_new), local_preview_only=True)


def consumer(nn, target, fs_hash, accepted=None):
    contract = nn / f"production/output/contracts/nn_contract_{target}.json"
    parquet = contract.with_suffix(".parquet")
    manifest = read(contract)
    if not manifest or not parquet.exists():
        return dict(passed=False, problems=[f"No published NN contract for {target}"], paths=[])
    problems = []
    if manifest.get("trade_month") != target or manifest.get("factor_set_sha256") != fs_hash:
        problems.append("NN contract month/factor-set mismatch")
    if not manifest.get("freshness", {}).get("passed"):
        problems.append("NN contract did not pass freshness")
    holdings = read(nn / "production/state/holdings.json", {}).get("months", {}).get(target, {})
    if sorted(holdings.get("held", [])) != sorted(manifest.get("basket", [])) or len(manifest.get("basket", [])) != 8:
        problems.append("NN basket/holdings state mismatch")
    paths = [contract, parquet]
    hashes = {str(p): sha(p) for p in paths}
    if accepted and hashes != accepted.get("consumer_hashes"):
        problems.append("Accepted monthly NN contract changed; reconcile before accepting/replaying")
    return dict(passed=not problems, problems=problems, consumer_hashes=hashes,
                run_dir=manifest.get("run_dir"), paths=list(hashes))


def build_status(root, cfg, now, rows, accepted):
    target = now.astimezone(PACIFIC).strftime("%Y-%m")
    fs_path = Path(cfg["nn_root"]) / "rank_model/factor_set_v3_clean.json"
    fs = read(fs_path)
    problems = []
    fs_hash = sha(fs_path)
    if fs_hash != cfg["factor_set_sha256"]:
        problems.append("NN factor set changed; review monthly readiness contract")
    for rel, digest in cfg["source_hashes"].items():
        if not (root / rel).exists() or sha(root / rel) != digest:
            problems.append(f"Request/producer definition changed: {rel}; recompute bounded scope")
    for rel, digest in cfg.get("consumer_source_hashes", {}).items():
        path = Path(cfg["nn_root"]) / rel
        if not path.exists() or sha(path) != digest:
            problems.append(f"NN consumer definition changed: {rel}; review month/lag contract")
    fr = freshness(rows, fs["factors"], cfg["countries"], target)
    q = quota(Path(cfg["bbg_root"]), cfg["request_scope"], now, cfg["quota_associations"])
    receipt = accepted.get(target)
    nn = consumer(Path(cfg["nn_root"]), target, fs_hash, receipt)
    older = sorted(m for m in accepted if m < target)
    missed = []
    if older:
        m = shift(older[-1], 1)
        while m < target:
            missed.append(m)
            m = shift(m, 1)
    warnings = list(fr["warnings"])
    if missed:
        problems.append("Unaccepted intervening trade months: " + ",".join(missed) + "; reconcile manually, no automatic replay")
    if receipt:
        evidence = Path(receipt["evidence"])
        if not evidence.exists() or sha(evidence) != receipt["evidence_sha256"]:
            problems.append("Accepted publication evidence absent/changed; reconcile before replay")
        problems += nn["problems"] + fr["problems"]
        state = "ACCEPTED_WITH_WARNINGS" if warnings else "ACCEPTED"
        if problems:
            state = "ACCEPTANCE_INVALID"
    else:
        problems += fr["problems"]
        problems += nn["problems"]
        if not fr["passed"]:
            state = "WAITING_INPUTS"
        elif not nn["passed"]:
            state = "READY_FOR_NN"
        else:
            state = "AWAITING_ACCEPTANCE"
        if not q["passed"] and not fr["passed"]:
            state = "QUOTA_BLOCKED"
        if any("changed:" in p or "factor set changed" in p for p in problems):
            state = "CONTRACT_REVIEW_REQUIRED"
    return dict(schema_version=1, checked_at=now.isoformat(), timezone="America/Los_Angeles",
                trade_month=target, observation_month=shift(target, -1), state=state,
                accepted=receipt is not None, accepted_at=receipt.get("accepted_at") if receipt else None,
                inputs_ready=fr["passed"], full_coverage=fr["full_coverage"],
                problems=problems, warnings=warnings, freshness=fr, quota=q, consumer=nn,
                missed_trade_months=missed, next_eligibility=shift(target, 1) + "-01T00:00:00 America/Los_Angeles",
                daily_success_does_not_cover_monthly=True, producer_execution="manual bounded refresh; readiness job never invokes producers",
                accepted_receipt=str(root / f"Data/monthly/accepted/{target}.json") if receipt else None)


def accept(state_dir, status, receipt_path):
    """Adopt verified publication once; never infer completion from exit 0.

    Receipt must attest independent sandbox parity and refer to the canonical
    run. Current content is verified before durable acceptance. This operation
    invokes no producer; subsequent changes invalidate, never rerun acceptance.
    """
    receipt = read(receipt_path)
    if not receipt:
        raise RuntimeError("Publication receipt missing")
    target = status["trade_month"]
    if not status["inputs_ready"] or status["problems"] or not status["consumer"]["passed"]:
        raise RuntimeError("Cannot accept: source/consumer/contract verification failed")
    if receipt.get("NN_month") != target or receipt.get("NN_scores_match_sandbox") is not True:
        raise RuntimeError("Receipt lacks matching month and independent sandbox parity")
    if receipt.get("NN_manifest", {}).get("run_dir") != status["consumer"]["run_dir"]:
        raise RuntimeError("Receipt and canonical NN run disagree")
    at = datetime.fromisoformat(receipt["accepted_at"])
    if at.tzinfo is None or at > datetime.fromisoformat(status["checked_at"]) + timedelta(minutes=2):
        raise RuntimeError("Receipt timestamp is naive/future-dated")
    snapshot = Path(receipt["NN_manifest"]["snapshot"])
    if sha(snapshot) != receipt["NN_manifest"]["snapshot_sha256"]:
        raise RuntimeError("Accepted NN snapshot hash mismatch")
    value = dict(trade_month=target, observation_month=status["observation_month"],
                 accepted_at=receipt["accepted_at"], adopted_at=status["checked_at"],
                 evidence=str(Path(receipt_path).resolve()), evidence_sha256=sha(receipt_path),
                 consumer_hashes=status["consumer"]["consumer_hashes"],
                 full_coverage=status["full_coverage"], warnings=status["warnings"])
    path = state_dir / "accepted" / f"{target}.json"
    path.parent.mkdir(exist_ok=True)
    with path.open("x") as f:
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    append(state_dir / "events.jsonl", {"event": "accepted", **value})
    return value


def alert_event(state_dir, status, notify=False):
    """Durable, deduplicated local alert; notification failure does not erase health."""
    report = state_dir / "status.md"
    alert = dict(month=status["trade_month"], state=status["state"], problems=status["problems"], warnings=status["warnings"])
    if not status["accepted"] and status.get("quota", {}).get("passed") is False:
        alert["quota_stops"] = status["quota"]["reasons"]
    fingerprint = hashlib.sha256(json.dumps(alert, sort_keys=True).encode()).hexdigest()
    prior = read(state_dir / "alert_state.json", {})
    if fingerprint == prior.get("fingerprint"):
        return
    event = {"at": status["checked_at"], "fingerprint": fingerprint, "report": str(report), **alert}
    append(state_dir / "alerts.jsonl", event)
    atomic(state_dir / "alert_state.json", event)
    if notify and (status["problems"] or status["warnings"] or not status["accepted"]):
        message = f"{status['trade_month']}: {status['state']}; {len(status['problems'])} gaps, {len(status['warnings'])} warnings. See ASADO/Data/monthly/status.md"
        try:
            # Pass strings as arguments; never interpolate AppleScript source.
            result = subprocess.run(["/usr/bin/osascript", "-e", 'on run argv\ndisplay notification (item 1 of argv) with title "ASADO monthly readiness"\nend run', message], capture_output=True, text=True, timeout=10)
            if result.returncode:
                raise RuntimeError(result.stderr)
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            append(state_dir / "events.jsonl", {"event": "notification_failed", "at": status["checked_at"], "error": str(exc)})


def persist(state_dir, status, notify=False):
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "tickets").mkdir(exist_ok=True)
    ticket_path = state_dir / "tickets" / f"{status['trade_month']}.json"
    ticket = read(ticket_path, {"created_at": status["checked_at"], "trade_month": status["trade_month"]})
    previous = ticket.get("state")
    ticket.update(state=status["state"], checked_at=status["checked_at"], observation_month=status["observation_month"],
                  producer_execution=status["producer_execution"])
    atomic(ticket_path, ticket)
    if previous != status["state"]:
        append(state_dir / "events.jsonl", {"event": "state_changed", "from": previous, "to": status["state"],
                                            "trade_month": status["trade_month"], "at": status["checked_at"]})
    atomic(state_dir / "status.json", status)
    lines = [f"# ASADO monthly readiness: {status['trade_month']} — {status['state']}", "",
             f"Checked {status['checked_at']}. Observation month {status['observation_month']}.",
             f"Inputs ready: {status['inputs_ready']}; full coverage: {status['full_coverage']}.",
             "Daily success does not establish monthly completion. This job sends no provider requests.", "",
             "## Problems", *["- " + p for p in status["problems"]], "", "## Warnings",
             *["- " + p for p in status["warnings"]], "", "## Bloomberg local preflight",
             json.dumps(status["quota"], indent=2), "", "## Next action",
             "Accepted months are never rerun by this readiness job. For an unaccepted month: inspect input gaps; obtain a bounded refresh receipt; validate a separate NN sandbox; publish; adopt its verified receipt."]
    report = state_dir / "status.md"
    tmp = report.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n")
    tmp.replace(report)
    alert_event(state_dir, status, notify)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--fixture-counts", type=Path, help="offline rows; never used by installed schedule")
    parser.add_argument("--now", help="fixture-only aware timestamp")
    parser.add_argument("--adopt-receipt", type=Path)
    parser.add_argument("--notify", action="store_true")
    args = parser.parse_args()
    if args.now and not args.fixture_counts:
        parser.error("--now requires offline fixture counts")
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc).astimezone(PACIFIC)
    if now.tzinfo is None:
        parser.error("aware timestamp required")
    root = args.root.resolve()
    cfg = read(args.config or root / "config/monthly_readiness.json")
    state_dir = root / "Data/monthly"
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / ".readiness.lock").open("a") as singleton:
        locks = ExitStack()
        try:
            fcntl.flock(singleton, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Readiness checker already running; no duplicate invocation")
            return 0
        try:
            if args.fixture_counts:
                rows = read(args.fixture_counts)
            else:
                # All three existing coordination locks: no producer/repair overlap.
                for relative in ("Data/.pipeline.lock", "Data/loop/.loop_daily.lock", "Data/.xo_monthly_repair.lock"):
                    handle = locks.enter_context((root / relative).open("r"))
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fs = read(Path(cfg["nn_root"]) / "rank_model/factor_set_v3_clean.json")
                rows = load_counts(root, fs["factors"], cfg["countries"])
            accepted_dir = state_dir / "accepted"
            accepted = {p.stem: read(p) for p in accepted_dir.glob("*.json")} if accepted_dir.exists() else {}
            status = build_status(root, cfg, now, rows, accepted)
            if args.adopt_receipt and not status["accepted"]:
                accepted[status["trade_month"]] = accept(state_dir, status, args.adopt_receipt)
                status = build_status(root, cfg, now, rows, accepted)
            persist(state_dir, status, args.notify)
            print(f"{status['trade_month']} {status['state']}; inputs_ready={status['inputs_ready']}; full_coverage={status['full_coverage']}; no producers invoked")
            return 0
        except Exception as exc:
            # Preserve last successful acceptance; publish an explicit current failure.
            status = dict(schema_version=1, checked_at=now.isoformat(), timezone="America/Los_Angeles",
                          trade_month=now.astimezone(PACIFIC).strftime("%Y-%m"),
                          state="CHECK_DEFERRED" if isinstance(exc, BlockingIOError) else "CHECK_FAILED",
                          problems=[str(exc)], warnings=[], full_coverage=False, accepted=False)
            atomic(state_dir / "status.json", status)
            append(state_dir / "events.jsonl", {"event": "check_failed", **status})
            (state_dir / "status.md").write_text(f"# ASADO monthly readiness: {status['state']}\n\n{status['checked_at']}\n\n{exc}\n\nThe accepted ledger is preserved. Daily status cannot establish monthly readiness.\n")
            alert_event(state_dir, status, args.notify)
            print(json.dumps(status), file=sys.stderr)
            return 2 if isinstance(exc, BlockingIOError) else 1
        finally:
            locks.close()


if __name__ == "__main__":
    raise SystemExit(main())
