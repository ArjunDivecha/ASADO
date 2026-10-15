#!/usr/bin/env python3
"""One durable, gated monthly ASADO collection -> validated NN publication attempt.

Inputs: /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/monthly_{worker,readiness}.json,
canonical ASADO/Data/, OpusBloomberg local quota ledgers, T2 NN existing models/state.
Outputs: ASADO/Data/monthly/{attempts,runs}/; approved ASADO data and T2 NN outputs
only after staged validation, independent NN parity and journaled publication.
No trades, credentials/access/VM changes, quota bypass, automatic retries or refits.
CLI: project venv/bin/python scripts/monthly_worker.py --tick.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from monthly_readiness import ROOT, PACIFIC, shift, read, sha, atomic, append, quota, alert_event
from monthly_publish import backup, publish, rollback


class StopAttempt(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).astimezone(PACIFIC)


def context(root, cfg, month):
    nn = Path(cfg["nn_root"])
    run = root / "Data/monthly/runs" / (month + "_" + now().strftime("%Y%m%d_%H%M%S"))
    return dict(root=str(root), nn_root=str(nn), bbg_root=cfg["bbg_root"], month=month,
                observation_month=shift(month, -1), run=str(run),
                snapshot_destination=str(nn / "Data/live" / ("asado_monthly_" + run.name) / "feature_panel_observed.parquet"),
                nn_run_destination=str(nn / "production/runs" / ("asado_monthly_" + run.name)))


def target_paths(c, cfg):
    """Closed destination set, backed up before any collection."""
    root, nn = Path(c["root"]), Path(c["nn_root"])
    rels = list(cfg["data_targets"])
    import calendar
    y, m = map(int, c["observation_month"].split("-"))
    for day in range(1, calendar.monthrange(y, m)[1] + 1):
        d = f"{y:04d}-{m:02d}-{day:02d}"
        rels += [f"Data/gdelt/country_day/{d}.parquet", f"Data/gdelt/manifests/country_day/{d}.json"]
    result = [root / rel for rel in rels]
    result += [nn / "production" / rel for rel in (
        "output/T2_NN_Country_Weights.xlsx", "output/nn_contract_latest.json", "output/nn_contract_latest.parquet",
        f"output/contracts/nn_contract_{c['month']}.json", f"output/contracts/nn_contract_{c['month']}.parquet", "state/holdings.json")]
    result += [Path(c["snapshot_destination"]), Path(c["snapshot_destination"]).with_name("MANIFEST.json")]
    result += [Path(c["nn_run_destination"]) / name for name in ("monthly_acceptance.json", "summary.json", "freshness_report.json", "run.log")]
    return result


def preflight(c, cfg):
    root, nn = Path(c["root"]), Path(c["nn_root"])
    if not cfg.get("enabled"):
        raise StopAttempt("Monthly worker disabled")
    for absolute, expected in cfg["pinned_sources"].items():
        if not Path(absolute).exists() or sha(absolute) != expected:
            raise StopAttempt("Pinned source changed: " + absolute)
    for key in ("asado_python", "bbg_python", "nn_python"):
        if not Path(cfg[key]).is_file() or not os.access(cfg[key], os.X_OK):
            raise StopAttempt("Required approved interpreter unavailable: " + cfg[key])
    if (root / "Data/asado.duckdb.wal").exists():
        raise StopAttempt("Warehouse WAL exists; reconcile the writer before monthly work")
    if (nn / f"production/output/contracts/nn_contract_{c['month']}.json").exists():
        raise StopAttempt("This month already has an NN publication; reconcile/adopt it, never collect again")
    accepted = read(root / f"Data/monthly/accepted/{shift(c['month'], -1)}.json")
    state = read(nn / "production/state/holdings.json", {})
    if not accepted or state.get("months", {}).get(shift(c["month"], -1), {}).get("source") != "live":
        raise StopAttempt("Previous trade month is not accepted with live NN holdings; no automatic gap replay")
    from monthly_readiness import consumer
    previous_consumer = consumer(nn, shift(c["month"], -1), cfg["factor_set_sha256"], accepted)
    if not previous_consumer["passed"]:
        raise StopAttempt("Previous accepted NN outputs/state changed; reconcile before monthly work")
    for rel in cfg["required_inputs"]:
        if not (root / rel).is_file():
            raise StopAttempt("Required source input absent before collection: " + rel)
    from duckdb_lock_guard import guarded_connect
    os.environ['ASADO_LOCK_GUARD_KILL']='0'
    con=guarded_connect(root/'Data/asado.duckdb',read_only=True,wait_budget_s=0,config={'threads':1})
    try:
        con.execute('SELECT 1').fetchone()
    finally:
        con.close()
    target = datetime.strptime(c["month"], "%Y-%m")
    cutoff = f"{target.year if target.month >= 2 else target.year - 1}-02"
    model = nn / "production/models" / ("fold_" + cutoff)
    meta = read(model / "meta.json")
    if not (model / "nets.pt").exists() or not meta or meta.get("factor_set_sha256") != cfg["factor_set_sha256"]:
        raise StopAttempt("Validated existing annual model cache absent/mismatched; automatic training is forbidden")
    c["model_dir"] = str(model)
    c["model_hashes"] = {p.name: sha(p) for p in (model / "nets.pt", model / "meta.json")}
    if c['model_hashes'] != cfg['validated_model_hashes'].get(cutoff):
        raise StopAttempt('Annual model bytes are not in the validated cache allowlist; no automatic refit/replacement')
    q = quota(Path(cfg["bbg_root"]), cfg["request_scope"], now(), cfg["quota_associations"])
    if not q["passed"]:
        raise StopAttempt("Bloomberg quota preflight stopped: " + "; ".join(q["reasons"]))
    c["quota_preflight"] = q
    required = sum(p.stat().st_size for p in target_paths(c, cfg) if p.exists()) * 3 + 2_000_000_000
    if shutil.disk_usage(root).free < required:
        raise StopAttempt(f"Insufficient staging/rollback disk headroom: need {required} bytes")
    return q


def verify_pins(cfg):
    for path, expected in cfg['pinned_sources'].items():
        if not Path(path).is_file() or sha(path) != expected:
            raise StopAttempt('Source changed during monthly work: '+path)


def heartbeat(path, record, stage):
    record.update(state="RUNNING", stage=stage, heartbeat_at=now().isoformat())
    atomic(path, record)
    # Short status, not a successful monthly acceptance. No per-hour retry.
    status = read(path.parent.parent / "status.json", {})
    status.update(checked_at=now().isoformat(), trade_month=record["month"], state="MONTHLY_RUNNING", accepted=False,
                  full_coverage=False, worker_stage=stage, worker_run=record["run"])
    atomic(path.parent.parent / "status.json", status)


def command(c, cfg, stage, deadline, state_path, record):
    root, run = Path(c["root"]), Path(c["run"])
    interpreter = cfg["bbg_python"] if stage == "collect" else cfg["asado_python"]
    script = {"collect": "monthly_collect.py", "stage": "monthly_stage.py", "nn": "monthly_nn.py"}[stage]
    env = dict(os.environ, ASADO_LOCK_GUARD_KILL="0", PYTHONUNBUFFERED="1", TZ="America/Los_Angeles", NN_NO_NOTIFICATIONS="1", ASADO_MONTHLY_LOCK_OWNER=str(os.getpid()))
    with (run / (stage + ".log")).open("a") as log:
        process = subprocess.Popen([interpreter, str(root / "scripts" / script), "--context", str(run / "context.json")],
                                   cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            last_heartbeat = 0
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise StopAttempt("Monthly deadline reached; stopped before quiet window/month rollover")
                if time.monotonic() - last_heartbeat >= 30:
                    heartbeat(state_path, record, stage)
                    last_heartbeat = time.monotonic()
                time.sleep(.5)
            if process.returncode:
                raise StopAttempt(f"{stage} failed exit {process.returncode}; see {run / (stage + '.log')}; no retry")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


def stopped(root, record, error):
    record.update(state="FAILED_STOPPED", error=str(error), finished_at=now().isoformat())
    path = root / f"Data/monthly/attempts/{record['month']}.json"
    atomic(path, record)
    append(root / "Data/monthly/worker_events.jsonl", record)
    status = read(root / "Data/monthly/status.json", {})
    status.update(checked_at=now().isoformat(), trade_month=record["month"], state="FAILED_STOPPED", accepted=False,
                  inputs_ready=False, full_coverage=False, problems=[str(error)], warnings=status.get("warnings", []), worker_run=record["run"])
    atomic(root / "Data/monthly/status.json", status)
    (root / "Data/monthly/status.md").write_text(f"# Monthly worker stopped: {record['month']}\n\n{error}\n\nEvidence: {record['run']}\n\nNo automatic retry. Reconcile the attempt and retained receipts before any new collection.\n")
    alert_event(root / "Data/monthly", status, notify=True)


def run_once(root, cfg, *, clock=None, executor=command, before=None, final=None):
    """Dependency injection is for isolated tests; installed CLI has no clock/retry switch."""
    root = Path(root)
    stamp = clock or now()
    month = stamp.astimezone(PACIFIC).strftime("%Y-%m")
    state_dir = root / "Data/monthly"
    accepted = state_dir / f"accepted/{month}.json"
    if accepted.exists() or month < cfg["first_trade_month"]:
        return "ACCEPTED_NOOP"
    local = stamp.astimezone(PACIFIC)
    minute = local.hour * 60 + local.minute
    if 240 <= minute < 510:
        return "DEFERRED_QUIET_WINDOW"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "attempts").mkdir(exist_ok=True)
    path = state_dir / f"attempts/{month}.json"
    roots = [root / "Data", Path(cfg["nn_root"]) / "production", Path(cfg["nn_root"]) / "Data/live"]
    with ExitStack() as locks:
        try:
            for p in (state_dir / ".worker.lock", root / "Data/.pipeline.lock", root / "Data/loop/.loop_daily.lock", root / "Data/.xo_monthly_repair.lock", Path(cfg["nn_root"]) / "production/.nn_monthly.lock"):
                p.parent.mkdir(parents=True, exist_ok=True)
                h = locks.enter_context(p.open("a"))
                fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "DEFERRED_OTHER_WORKER"
        old = read(path)
        if old:
            if old["state"] in ("CLAIMED", "RUNNING", "PUBLISHING"):
                try:
                    # A free singleton proves the old worker is gone. Only rollback,
                    # never resume collection or infer success from partial output.
                    rollback(Path(old["run"]) / "publication.jsonl", roots)
                    stopped(root, old, "Interrupted attempt reconciled/rolled back; no automatic retry")
                except BaseException as exc:
                    stopped(root, old, "Interrupted publication requires manual reconciliation: " + str(exc))
            return "STOPPED_NO_RETRY"
        c = context(root, cfg, month)
        record = dict(month=month, run=c["run"], state="CLAIMED", pid=os.getpid(), claimed_at=now().isoformat())
        with path.open("x") as f:
            json.dump(record, f); f.flush(); os.fsync(f.fileno())
        run = Path(c["run"])
        run.mkdir(parents=True, exist_ok=False)
        journal = run / "publication.jsonl"
        accepted_created = False
        try:
            (before or preflight)(c, cfg)
            originals = backup(target_paths(c, cfg), run / "backup", roots)
            c["originals"] = str(run / "backup/manifest.json")
            c["config"] = cfg
            atomic(run / "context.json", c)
            # Never cross month boundary; allow at most two hours, finish before06:00.
            local = (clock or now()).astimezone(PACIFIC)
            minute = local.hour * 60 + local.minute
            remaining = cfg["max_runtime_seconds"]
            if minute < 360:
                remaining = min(remaining, (360 - minute) * 60 - local.second)
            next_month = datetime.strptime(shift(month, 1), "%Y-%m").replace(tzinfo=PACIFIC)
            remaining = min(remaining, (next_month - local).total_seconds())
            deadline = time.monotonic() + remaining
            for stage in ("collect", "stage", "nn"):
                if not before:
                    verify_pins(cfg)
                heartbeat(path, record, stage)
                executor(c, cfg, stage, deadline, path, record)
                if not before:
                    verify_pins(cfg)
            plan = read(run / "publication_plan.json")
            if not plan:
                raise StopAttempt("No validated publication plan")
            if time.monotonic() + 300 >= deadline:
                raise StopAttempt("Insufficient publication/rollback time before safety deadline")
            record.update(state="PUBLISHING", stage="publish")
            atomic(path, record)
            def publication_deadline(*_):
                if time.monotonic() >= deadline:
                    raise StopAttempt("Publication deadline reached; rollback required")
            publish(plan, originals, journal, roots, fault=publication_deadline)
            if final:
                final(c, cfg)
            else:
                verify_publication(c, cfg)
            receipt = read(Path(c["nn_run_destination"]) / "monthly_acceptance.json")
            if not receipt or receipt.get("NN_scores_match_sandbox") is not True:
                raise StopAttempt("Canonical independent NN parity receipt absent")
            from monthly_readiness import load_counts, build_status, accept
            if not final:
                ready_cfg = read(root / "config/monthly_readiness.json")
                fs = read(Path(cfg["nn_root"]) / ready_cfg["factor_set"])
                rows = load_counts(root, fs["factors"], ready_cfg["countries"])
                prior = {p.stem: read(p) for p in (state_dir / "accepted").glob("*.json")}
                status = build_status(root, ready_cfg, now(), rows, prior)
                accept(state_dir, status, Path(c["nn_run_destination"]) / "monthly_acceptance.json")
                accepted_created = True
            record.update(state="ACCEPTED", finished_at=now().isoformat())
            atomic(path, record)
            append(journal, {"event": "ACCEPTED", "month": month})
            append(state_dir / "worker_events.jsonl", record)
            return "ACCEPTED"
        except BaseException as exc:
            # If durable acceptance exists, publication is committed. Never undo it
            # because a later log/status append failed.
            try:
                committed=read(accepted,{})
            except (ValueError,OSError):
                committed={}
            if accepted_created or (committed.get('trade_month')==month and committed.get('consumer_hashes')):
                return "ACCEPTED_STATUS_RECONCILIATION_NEEDED"
            try:
                rollback(journal, roots)
            except BaseException as conflict:
                exc = StopAttempt(f"{exc}; ROLLBACK NEEDS MANUAL RECONCILIATION: {conflict}")
            stopped(root, record, exc)
            return "FAILED_STOPPED"


def verify_publication(c, cfg):
    run = Path(c["run"])
    for row in read(run / "publication_plan.json"):
        if sha(row["destination"]) != row["sha256"]:
            raise StopAttempt("Canonical publication hash mismatch: " + row["destination"])
    check = read(run / "NN_VALIDATED.json")
    if not check or check.get("independent_parity") is not True:
        raise StopAttempt("Independent NN parity proof missing")
    if sha(Path(c['root'])/'Data/asado.duckdb') != check['warehouse_sha256']:
        raise StopAttempt("Canonical warehouse differs from validated staging")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tick", action="store_true", required=True)
    args = ap.parse_args()
    cfg = read(ROOT / "config/monthly_worker.json")
    # SIGTERM unwinds our own staged child/process group; never another user's job.
    def terminate(*_):
        raise StopAttempt("Worker terminated; no automatic retry")
    signal.signal(signal.SIGTERM, terminate)
    result = run_once(ROOT, cfg)
    print(result, flush=True)
    return 1 if result == "FAILED_STOPPED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
