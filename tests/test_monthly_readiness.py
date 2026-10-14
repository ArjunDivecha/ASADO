"""Isolated monthly readiness tests; all file I/O under temporary test roots.

Input: scripts/monthly_readiness.py and isolated synthetic monthly rows.
Output: unittest results only. No live DB, Bloomberg, NN training or producers.
"""
import importlib.util
import json
import fcntl
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/monthly_readiness.py"
spec = importlib.util.spec_from_file_location("monthly_readiness", SCRIPT)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


class MonthlyReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.nn, self.bbg = self.root / "NN", self.root / "BBG"
        self.now = datetime.fromisoformat("2026-10-13T17:00:00-07:00")
        self.factors = [dict(source=s, variable=v, lag_months=l) for s, v, l in
                        [("t2", "T", 0), ("gdelt", "G", 0), ("bloomberg", "B1", 1), ("bloomberg", "B2", 1), ("slow", "S", 1)]]
        self.rows = []
        for f in self.factors:
            need = M.shift("2026-10", -f["lag_months"])
            for offset in (-2, -1, 0):
                self.rows.append([f["source"], f["variable"], M.shift(need, offset), ["A", "B"]])
        self.rows.append(["t2", "1MRet", "2026-09", ["A", "B"]])
        def write(rel, data):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data))
            return p
        self.write = write
        fs = self.write("NN/rank_model/factor_set_v3_clean.json", {"factors": self.factors})
        self.write("BBG/budget_config.json", dict(monthly_ceiling=20, daily_hit_ceiling=100, free_new_per_caller_month=10))
        self.write("BBG/logs/gate_usage_2026-10.json", {"free": {"ASADO": 2, "recovery_collect.py": 3}})
        for key in ("2026-08", "2026-09", "2026-10"):
            self.write(f"BBG/logs/touched_securities_{key}.json", ["existing"])
        (self.bbg / "logs/master_bloomberg_log.csv").write_text("timestamp,est_hits\n2026-10-13T17:00:00-07:00,5\n2026-10-12T17:00:00-07:00,7\n")
        self.cfg = dict(nn_root=str(self.nn), bbg_root=str(self.bbg), countries=["A", "B"],
                        factor_set_sha256=M.sha(fs), source_hashes={},
                        quota_associations=[dict(month="2026-10", caller="recovery_collect.py")],
                        request_scope=dict(securities=["existing", "new"], estimated_hits=3))
        self.config = self.write("config/monthly_readiness.json", self.cfg)
        self.state = self.root / "Data/monthly"
        self.state.mkdir(parents=True)
        self.snapshot = self.root / "snapshot.parquet"
        self.snapshot.write_bytes(b"synthetic snapshot; never model input")

    def fr(self, rows=None):
        return M.freshness(rows if rows is not None else self.rows, self.factors, ["A", "B"], "2026-10")

    def status(self, accepted=None, rows=None, now=None):
        return M.build_status(self.root, self.cfg, now or self.now, self.rows if rows is None else rows, accepted or {})

    def contract(self):
        manifest = dict(trade_month="2026-10", factor_set_sha256=self.cfg["factor_set_sha256"],
                        freshness={"passed": True}, basket=list("ABCDEFGH"), run_dir=str(self.nn / "run"),
                        snapshot=str(self.snapshot), snapshot_sha256=M.sha(self.snapshot))
        p = self.write("NN/production/output/contracts/nn_contract_2026-10.json", manifest)
        p.with_suffix(".parquet").write_bytes(b"synthetic contract")
        self.write("NN/production/state/holdings.json", {"months": {"2026-10": {"held": manifest["basket"]}}})
        return self.write("publication.json", dict(NN_month="2026-10", NN_scores_match_sandbox=True,
                                                    accepted_at=self.now.isoformat(), NN_manifest=manifest))

    def test_month_semantics_completed_and_availability_labels(self):
        fr = self.fr()
        self.assertTrue(fr["passed"])
        needs = {f["source"]: f["required_month"] for f in fr["inputs"]}
        self.assertEqual(needs["t2"], "2026-10")
        self.assertEqual(needs["gdelt"], "2026-10")
        self.assertEqual(needs["bloomberg"], "2026-09")

    def test_missing_one_core_input_blocks_even_group_diluted(self):
        rows = [r for r in self.rows if r[:3] != ["bloomberg", "B2", "2026-09"]]
        fr = self.fr(rows)
        self.assertFalse(fr["passed"])
        self.assertTrue(any("bloomberg/B2" in p for p in fr["problems"]))

    def test_newer_row_does_not_replace_required_month(self):
        rows = [r for r in self.rows if r[:3] != ["bloomberg", "B2", "2026-09"]]
        rows.append(["bloomberg", "B2", "2026-10", ["A", "B"]])
        self.assertFalse(self.fr(rows)["passed"])

    def test_partial_source_warns_and_never_full_coverage(self):
        # Lots of unaffected inputs make aggregate pass while one input is thin.
        extra = [dict(source="bloomberg", variable=f"Extra{i}", lag_months=1) for i in range(10)]
        factors = self.factors + extra
        rows = [list(r) for r in self.rows]
        rows = [r if r[:3] != ["bloomberg", "B2", "2026-09"] else [*r[:3], ["A"]] for r in rows]
        for f in extra:
            for d in ["2026-07", "2026-08", "2026-09"]:
                rows.append(["bloomberg", f["variable"], d, ["A", "B"]])
        fr = M.freshness(rows, factors, ["A", "B"], "2026-10")
        self.assertTrue(fr["passed"])
        self.assertFalse(fr["full_coverage"])
        self.assertIn("missing B", " ".join(fr["warnings"]))

    def test_slow_source_gap_is_warning(self):
        fr = self.fr([r for r in self.rows if r[:3] != ["slow", "S", "2026-09"]])
        self.assertTrue(fr["passed"])
        self.assertFalse(fr["full_coverage"])

    def test_returns_require_all_countries(self):
        rows = [r for r in self.rows if r[1] != "1MRet"] + [["t2", "1MRet", "2026-09", ["A"]]]
        self.assertFalse(self.fr(rows)["passed"])

    def test_foreign_universe_country_cannot_supply_freshness(self):
        rows = [r for r in self.rows if r[:3] != ["t2", "T", "2026-10"]] + [["t2", "T", "2026-10", ["OUTSIDE"]]]
        self.assertFalse(self.fr(rows)["passed"])

    def test_associated_recovery_quota_is_not_second_allowance(self):
        q = M.quota(self.bbg, self.cfg["request_scope"], self.now, self.cfg["quota_associations"])
        self.assertEqual(q["associated_free_used"], 5)
        self.assertEqual(q["free_remaining"], 5)
        self.assertEqual(q["hits_today"], 5)

    def test_quota_stop_no_ledger_write(self):
        self.write("BBG/outputs/BLOOMBERG_HARD_STOP.json", {"stop": True})
        before = {str(p): M.sha(p) for p in self.bbg.rglob("*") if p.is_file()}
        q = M.quota(self.bbg, self.cfg["request_scope"], self.now, self.cfg["quota_associations"])
        self.assertFalse(q["passed"])
        self.assertEqual(before, {str(p): M.sha(p) for p in self.bbg.rglob("*") if p.is_file()})

    def test_free_global_and_daily_quota_boundaries(self):
        self.cfg["request_scope"] = dict(securities=[f"new{i}" for i in range(21)], estimated_hits=100)
        q = M.quota(self.bbg, self.cfg["request_scope"], self.now, self.cfg["quota_associations"])
        self.assertEqual(len(q["reasons"]), 3)

    def test_missing_hit_ledger_fails_closed(self):
        (self.bbg / "logs/master_bloomberg_log.csv").unlink()
        with self.assertRaises(RuntimeError):
            M.quota(self.bbg, self.cfg["request_scope"], self.now, [])

    def test_next_pacific_month_catches_missed_schedule(self):
        status = self.status(now=datetime.fromisoformat("2026-11-01T07:30:00+00:00"), accepted={"2026-09": {}})
        self.assertEqual(status["trade_month"], "2026-11")
        self.assertEqual(status["missed_trade_months"], ["2026-10"])
        self.assertEqual(status["state"], "WAITING_INPUTS")

    def test_dst_pacific_month_before_midnight(self):
        status = self.status(now=datetime.fromisoformat("2026-11-01T06:30:00+00:00"))
        self.assertEqual(status["trade_month"], "2026-10")

    def test_acceptance_once_and_no_rerun(self):
        receipt = self.contract()
        accepted = M.accept(self.state, self.status(), receipt)
        with self.assertRaises(FileExistsError):
            M.accept(self.state, self.status(), receipt)
        s = self.status(accepted={"2026-10": accepted})
        self.assertEqual(s["state"], "ACCEPTED")
        self.assertIn("readiness invokes no producer", s["producer_execution"])

    def test_changed_accepted_output_invalidates_no_replay(self):
        receipt = self.contract()
        accepted = M.accept(self.state, self.status(), receipt)
        (self.nn / "production/output/contracts/nn_contract_2026-10.parquet").write_bytes(b"changed")
        self.assertEqual(self.status({"2026-10": accepted})["state"], "ACCEPTANCE_INVALID")

    def test_changed_receipt_invalidates(self):
        receipt = self.contract()
        accepted = M.accept(self.state, self.status(), receipt)
        receipt.write_text("{}")
        self.assertEqual(self.status({"2026-10": accepted})["state"], "ACCEPTANCE_INVALID")

    def test_failure_receipt_cannot_be_accepted(self):
        receipt = self.contract()
        obj = M.read(receipt)
        obj["NN_scores_match_sandbox"] = False
        receipt.write_text(json.dumps(obj))
        with self.assertRaises(RuntimeError):
            M.accept(self.state, self.status(), receipt)

    def test_changed_snapshot_cannot_be_accepted(self):
        receipt = self.contract()
        self.snapshot.write_bytes(b"tampered")
        with self.assertRaises(RuntimeError):
            M.accept(self.state, self.status(), receipt)

    def test_acceptance_link_failure_leaves_no_partial_commit_marker(self):
        receipt = self.contract()
        with patch.object(M.os, 'link', side_effect=OSError('disk publication failure')):
            with self.assertRaises(OSError):
                M.accept(self.state, self.status(), receipt)
        self.assertFalse((self.state / 'accepted/2026-10.json').exists())
        self.assertFalse(list((self.state / 'accepted').glob('*.tmp')))

    def test_source_definition_drift_is_failure(self):
        p = self.write("scripts/fake.py", {"a": 1})
        self.cfg["source_hashes"] = {"scripts/fake.py": "incorrect"}
        self.assertIn("definition changed", " ".join(self.status()["problems"]))

    def test_sparse_t2_input_alerts_preserving_existing_source_gate(self):
        # Sparse selected T2 features must be visible without silently changing
        # the NN contract that accepts missing cells under its 90% source gate.
        factors = self.factors + [dict(source="t2", variable="AnnualGDP", lag_months=0)]
        rows = self.rows + [["t2", "AnnualGDP", "2026-01", ["A", "B"]]]
        fr = M.freshness(rows, factors, ["A", "B"], "2026-10")
        self.assertTrue(any("t2/AnnualGDP" in w for w in fr["warnings"]))
        self.assertFalse(fr["full_coverage"])

    def test_local_alerts_are_deduplicated_and_ticket_creation_stable(self):
        s = self.status()
        with patch.object(M.subprocess, "run") as send:
            M.persist(self.state, s)
            s["checked_at"] = (self.now + timedelta(hours=1)).isoformat()
            M.persist(self.state, s)
            send.assert_not_called()
        self.assertEqual(len((self.state / "alerts.jsonl").read_text().splitlines()), 1)
        self.assertEqual(M.read(self.state / "tickets/2026-10.json")["created_at"], self.now.isoformat())

    def test_duplicate_checker_does_not_write_or_run(self):
        lock = (self.state / ".readiness.lock").open("a")
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rows = self.write("rows.json", self.rows)
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), "--fixture-counts", str(rows)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.state / "status.json").exists())

    def test_other_producer_lock_defers_without_touching_database(self):
        for rel in ("Data/.pipeline.lock", "Data/loop/.loop_daily.lock", "Data/.xo_monthly_repair.lock"):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        handle = (self.root / "Data/.pipeline.lock").open("r")
        self.addCleanup(handle.close)
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(M.read(self.state / "status.json")["state"], "CHECK_DEFERRED")
        self.assertFalse((self.root / "Data/asado.duckdb").exists())

    def test_isolated_query_closes_connection(self):
        import duckdb
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copy2(SCRIPT.parent / "duckdb_lock_guard.py", scripts / "duckdb_lock_guard.py")
        db = self.root / "Data/asado.duckdb"
        con = duckdb.connect(str(db))
        con.execute("create table feature_panel_observed(source varchar,variable varchar,date date,country varchar,value double)")
        con.execute("insert into feature_panel_observed values ('t2','T','2026-10-01','A',1),('t2','T','2026-10-01','B',NULL)")
        con.close()
        rows = M.load_counts(self.root, self.factors, ["A", "B"])
        self.assertEqual(rows, [("t2", "T", "2026-10", ["A"])])
        con = duckdb.connect(str(db))
        con.execute("insert into feature_panel_observed values ('t2','T','2026-10-01','B',2)")
        con.close()


if __name__ == "__main__":
    unittest.main()
