#!/usr/bin/env python3
"""Bounded monthly Bloomberg collection through the original OpusBloomberg gate.

Inputs: ASADO/Data/monthly/runs/<run>/context.json and pinned request blueprint;
/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/{bbg,budget_gate}.py.
Outputs: immutable raw replies, wire journal, collection manifest in that run only.
Runtime: OpusBloomberg/.venv/bin/python. One setup, one request per plan entry;
no retry, new ticker discovery, VM startup/login or access configuration.
"""
import argparse
from collections import defaultdict
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
from monthly_readiness import read, sha, atomic, append, shift, quota, PACIFIC


class ScopeStop(BaseException):
    """Not catchable as an ordinary provider/setup retry."""


def requests_for(c, cfg):
    manifest = read(Path(c["root"]) / "scripts/config/t2_bbg_manifest.json")
    groups = defaultdict(set)
    for sheet in manifest["sheets"]:
        currency = None if sheet["sheet"] == "10Yr Bond" else manifest["bdh_params"]["currency"]
        for col in sheet["columns"]:
            groups[(col["field"], currency)].add(col["ticker"])
    start = shift(c["observation_month"], -1).replace("-", "") + "01"
    import calendar
    y, m = map(int, c["observation_month"].split("-"))
    end = f"{y:04d}{m:02d}{calendar.monthrange(y,m)[1]:02d}"
    result = []
    for (field, currency), secs in sorted(groups.items(), key=lambda x: str(x[0])):
        result.append(dict(kind="t2", securities=sorted(secs), fields=[field], currency=currency))
    for req in cfg["bloomberg_requests"]:
        result.append(dict(kind="bloomberg", securities=[req["security"]], fields=req["fields"], currency=None, roles=req))
    for i, req in enumerate(result):
        req.update(id=f"{i:03d}", start=start, end=end, periodicity="MONTHLY")
    names = {s for r in result for s in r["securities"]} | {"AAPL US Equity"}
    hits = sum(len(r["securities"]) * len(r["fields"]) for r in result)
    if names != set(cfg["request_scope"]["securities"]) or hits != cfg["history_hits"]:
        raise ScopeStop("Derived request scope differs from approved blueprint")
    return result


class RequestGuard:
    def __init__(self, planned, max_setup_hits, journal, budget, ledger):
        self.planned = planned
        self.sent = set()
        self.setup_hits = 0
        self.max_setup_hits = max_setup_hits
        self.journal, self.budget, self.ledger = journal, budget, ledger

    def check(self, request):
        el = request.asElement()
        typ = self.ledger._extract_request_type(request)
        names = self.ledger._extract_securities(request)
        ff = el.getElement("fields")
        fields = [ff.getValueAsString(i) for i in range(ff.numValues())]
        def value(key):
            try:
                return el.getElementAsString(key) or None
            except Exception:
                return None
        if typ == "ReferenceDataRequest" and names == ["AAPL US Equity"] and fields in (["PX_LAST", "NAME"], ["PX_LAST"]):
            self.setup_hits += len(fields)
            if self.setup_hits > self.max_setup_hits:
                raise ScopeStop("Setup/ping bound exceeded")
            ident = "setup"
        elif typ == "HistoricalDataRequest":
            matches = [r for r in self.planned if r["securities"] == names and r["fields"] == fields
                       and all(value(k) == r[v] for k, v in (("startDate", "start"), ("endDate", "end"), ("periodicitySelection", "periodicity"), ("currency", "currency")))]
            if len(matches) != 1:
                raise ScopeStop("Wire request differs from exact securities/fields/dates/currency/frequency manifest")
            ident = matches[0]["id"]
            if ident in self.sent:
                raise ScopeStop("Repeated provider request forbidden")
            self.sent.add(ident)
        else:
            raise ScopeStop("Unapproved provider request type/scope")
        append(self.journal, dict(event="SEND_PLANNED", id=ident, securities=names, fields=fields,
                                  request_type=typ, at=datetime.now(PACIFIC).isoformat()))


def forbid_infrastructure_changes(original):
    def guarded(args, *a, **kw):
        parts = list(map(str, args)) if not isinstance(args, str) else [args]
        text = " ".join(parts).lower()
        # Only exact read-only mechanics already used by canonical setup.
        if any(t in text for t in ("prlctl", "netsh", "powershell")):
            lower=[p.lower() for p in parts]
            permitted = (Path(parts[0]).name.lower()=='prlctl' and lower[1:]==['list','-a'])
            if len(parts)==6 and Path(parts[0]).name.lower()=='prlctl' and lower[1]=='exec' and lower[3:5]==['cmd.exe','/c']:
                permitted=lower[5] in ('ipconfig','tasklist','netsh interface portproxy show v4tov4','netsh advfirewall firewall show rule name="bloomberg api"')
            if not permitted:
                raise ScopeStop("Infrastructure change forbidden; make Bloomberg available manually")
        return original(args, *a, **kw)
    return guarded


def associated_budget(budget, names, cfg):
    key = budget.month_key()
    used = budget.load_usage(key).get('free', {})
    callers = {'ASADO'} | {a['caller'] for a in cfg['quota_associations'] if a['month'] == key}
    total = sum(used.get(name, 0) for name in callers)
    new = set(names) - budget._touched(key) - budget.recurring_set(key)
    if total + len(new) > budget.load_config()['free_new_per_caller_month']:
        raise ScopeStop('ASADO-associated allowance exhausted, including recovery caller aliases; no second allowance')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--context", type=Path, required=True)
    args = ap.parse_args()
    c = read(args.context); cfg = c["config"]
    run, bbgroot = Path(c["run"]), Path(c["bbg_root"])
    if Path(sys.prefix).resolve() != Path(cfg["bbg_prefix"]).resolve():
        raise ScopeStop("Bloomberg calls require the shared gated OpusBloomberg runtime")
    if not os.environ.get("ASADO_MONTHLY_LOCK_OWNER"):
        raise ScopeStop("Monthly parent locks required")
    q = quota(bbgroot, cfg["request_scope"], datetime.now(PACIFIC), cfg["quota_associations"])
    if not q["passed"]:
        raise ScopeStop("Quota preflight refused; no setup/probe permitted: " + str(q["reasons"]))
    planned = requests_for(c, cfg)
    atomic(run / "provider_manifest.json", planned)
    sys.path.insert(0, str(bbgroot))
    import budget_gate, master_ledger, quota_guard, bbg, bloomberg_connect
    quota_guard.assert_bloomberg_calls_allowed("refdata")
    guard = RequestGuard(planned, cfg["max_setup_hits"], run / "wire.jsonl", budget_gate, master_ledger)
    original_gate = budget_gate.gated_send
    def gated(request, send, **kwargs):
        if budget_gate.in_gate():
            return original_gate(request, send, **kwargs)
        from monthly_owner import assert_owner
        assert_owner(c)
        if os.getppid() != int(os.environ['ASADO_MONTHLY_LOCK_OWNER']):
            raise ScopeStop('Collector parent exited; no new provider requests')
        guard.check(request)
        associated_budget(budget_gate, master_ledger._extract_securities(request), cfg)
        # Preserve the original gate; charge this workflow to ASADO, including
        # caller aliases in the additional associated-budget check above.
        kwargs["caller"] = "ASADO"
        return original_gate(request, send, **kwargs)
    budget_gate.gated_send = gated
    bbg._gated_send = gated  # Imported alias must participate, as well as raw hook.
    subprocess.run = forbid_infrastructure_changes(subprocess.run)
    original_connect = bloomberg_connect.connect
    connections = 0
    def connect_once(*a, **kw):
        nonlocal connections
        connections += 1
        if connections > 1:
            raise ScopeStop("Failed setup is not automatically retried")
        return original_connect(*a, **kw)
    bloomberg_connect.connect = connect_once
    host = bbg.bloomberg_setup(verbose=False)
    raw = run / "raw"; raw.mkdir(exist_ok=False)
    receipts = []
    with bbg.BBG(host=host) as client:
        if not client.ping():
            raise ScopeStop("Existing Bloomberg session ping failed; no retries")
        for req in planned:
            if req["kind"] == "t2":
                values = client.hist_batch(req["securities"], req["fields"][0], req["start"], req["end"], periodicity="MONTHLY", currency=req["currency"])
                if not any(rows for rows in values.values()):
                    raise ScopeStop("An entire T2 field batch returned no history; no automatic retry")
            else:
                values = client.hist(req["securities"][0], req["fields"], req["start"], req["end"], periodicity="MONTHLY")
            path = raw / (req["id"] + ".json")
            if path.exists():
                raise ScopeStop("Immutable reply already exists")
            atomic(path, {"request": req, "rows": values})
            receipts.append(dict(id=req["id"], file=str(path), sha256=sha(path)))
            atomic(run / "collection_receipts.json", receipts)
            print(f"Collected {len(receipts)}/{len(planned)}; receipt {req['id']}", flush=True)
    quota_guard.assert_bloomberg_calls_allowed("refdata")
    if guard.sent != {r["id"] for r in planned}:
        raise ScopeStop("Wire requests and immutable receipts differ; reconcile before any publication")
    atomic(run / "COLLECTED.json", dict(history_hits=cfg["history_hits"], setup_hits=guard.setup_hits,
                                      requests=len(planned), independent_receipts=len(receipts), caller="ASADO"))


if __name__ == "__main__":
    main()
