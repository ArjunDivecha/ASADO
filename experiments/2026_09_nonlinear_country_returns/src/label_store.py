# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/label_store.py
#
# PRD 8.5 — LabelStore: the ONLY path by which model fitting/selection reads
# outcomes. read_matured(fit_cutoff, row_manifest) returns just the rows whose
# label_available_at < fit_cutoff. Every read is appended to an audit log
# (ledger of who/when/what boundary). Outcomes stay in a separate store from
# features and forecasts; a live forecast record never contains a future
# return. Ordinary file permissions + this API are the safeguard — not a
# cryptographic claim.
# =============================================================================
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


class LabelStore:
    def __init__(self, outcome_path: str | Path,
                 audit_log: str | Path | None = None):
        self.outcome_path = Path(outcome_path)
        self.audit_log = Path(audit_log) if audit_log else None
        self._labels = None  # lazy

    def _load(self) -> pd.DataFrame:
        if self._labels is None:
            df = pd.read_parquet(self.outcome_path)
            df["origin_date"] = pd.to_datetime(df["origin_date"])
            df["exit_date"] = pd.to_datetime(df["exit_date"])
            # label_available_at = the exit session's date; its close precedes
            # 23:59 UTC that day, so available strictly before the NEXT day
            # 00:00 UTC. Conservative comparison happens in read_matured.
            self._labels = df
        return self._labels

    def read_matured(self, fit_cutoff: pd.Timestamp, row_manifest=None,
                     horizon: str = "h20", reader: str = "unknown") -> pd.DataFrame:
        """Rows with exit_date strictly before fit_cutoff's date (the label is
        observed at the exit session's close, before that day's 23:59 UTC).

        `row_manifest` (optional frame with origin_date/market) restricts to
        the frozen eligible population — never an inner-join to whatever
        outcomes happen to exist.
        """
        cut = pd.Timestamp(fit_cutoff).normalize()
        lab = self._load()
        lab = lab[lab["horizon"] == horizon]
        matured = lab[lab["exit_date"].notna() & (lab["exit_date"] < cut)]
        if row_manifest is not None:
            matured = matured.merge(
                row_manifest[["origin_date", "market"]],
                on=["origin_date", "market"], how="inner")
        self._log(reader=reader, fit_cutoff=str(cut.date()),
                  horizon=horizon, rows=len(matured))
        return matured

    def _log(self, **rec) -> None:
        if self.audit_log is None:
            return
        rec["read_at_utc"] = datetime.now(timezone.utc).isoformat()
        with open(self.audit_log, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
