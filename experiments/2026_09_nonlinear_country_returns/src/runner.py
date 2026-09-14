# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/runner.py
#
# PRD 11.3 — the frozen historical replay runner. One implementation serves
# both the P07 control studies (pseudo-labels) and the P08 real outer
# evaluation; the only difference is the LabelStore it is pointed at.
#
# For every scheduled fit:
#   * read mature rows through LabelStore.read_matured (timestamp-gated)
#   * intersect with the frozen eligible manifest and the 8y window
#   * annual (July) fits: run inner selection over all 72 configs with
#     per-candidate leaf audits; quarterly fits reuse the selected configs
#     and refit from scratch on the new window
#   * audit terminal leaf support on the selected tree fits; a selected
#     config that fails support at refit yields BLOCKED_FIT_SUPPORT, never
#     a substitute
#   * issue the full next-segment forecasts for all 8 streams on the frozen
#     eligible rows, and persist them immutably with content hashes
#
# Checkpoints: each fit writes fit_<cutoff>.json + forecasts_<cutoff>.parquet
# under out_dir; a resume re-verifies the recorded input hashes and skips
# completed fits (T48/T49). No real outer performance is printed or consumed
# while replay is incomplete (T45).
# =============================================================================
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from estimators import (MASTER_SEED, RIDGE_GRID, TREE_GRID, fit_ridge,
                        predict_ridge, row_weights, fit_fold_scaler,
                        apply_fold_scaler, quadratic_expand, b0_mean,
                        fit_hgb, leaf_support_audit, one_se_select)

EXP = Path(__file__).resolve().parents[1]
AUDIT = EXP / "audit"

P_COLS = ["P01", "P02", "P03", "P04", "P05", "P06", "P09", "P10", "P12",
          "P13", "P14", "P15", "P16", "P17", "P18", "P19", "P20",
          "P21", "P22", "P23", "P24"]
S_COLS = ["C01", "C02", "C03", "C04", "C06", "C07", "C08", "C09",
          "C10", "C11", "C12", "G01", "G02", "G03", "G04"]

# model -> (feature cols spec, kind)
MODELS = {
    "B0": (None, "mean"),
    "L_X": ("X", "ridge"),
    "L_S": ("S", "ridge"),
    "L_star": ("XS", "ridge_select"),
    "A_S": ("S", "tree_d1_l2"),
    "Q_S": ("SQ", "ridge"),
    "N_S": ("S", "tree_d2_l4"),
    "N_X": ("X", "tree_d2_l4"),
}
TREE_MODELS = {"A_S": (1, 2), "N_S": (2, 4), "N_X": (2, 4)}
RIDGE_MODELS = {"L_X": "X", "L_S": "S", "Q_S": "SQ"}
STREAMS = list(MODELS)


class BlockedFit(Exception):
    pass


def feature_matrix(df: pd.DataFrame, spec: str) -> np.ndarray:
    if spec == "X":
        return df[P_COLS].to_numpy()
    if spec == "S":
        return df[S_COLS].to_numpy()
    if spec == "SQ":
        return quadratic_expand(df[S_COLS].to_numpy())
    raise ValueError(spec)


def content_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
    return h.hexdigest()


class ReplayRunner:
    """Deterministic, restartable, hash-checked replay of the locked
    schedule. `labels_path` may point at real labels or a pseudo-label
    store with identical schema/maturity metadata (T46)."""

    def __init__(self, out_dir: str | Path, labels_path: str | Path | None = None,
                 tag: str = "real", quiet: bool = True,
                 train_filter=None):
        """train_filter: optional callable(df)->bool mask applied to the
        outer training set only (P09 omission sensitivities; inner
        selection is NOT affected — sensitivities reuse frozen configs)."""
        from label_store import LabelStore
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.tag = tag
        self.quiet = quiet
        self.splits = json.loads((AUDIT / "splits.json").read_text())
        self.X = pd.read_parquet(AUDIT / "features_X.parquet")
        self.S = pd.read_parquet(AUDIT / "features_S.parquet")
        self.el = pd.read_parquet(AUDIT / "eligible_rows.parquet")
        for df in (self.X, self.S, self.el):
            df["origin_date"] = pd.to_datetime(df["origin_date"])
        self.manifest = self.el[["origin_date", "market"]]
        # frozen base-calendar origin index for the 20-origin leaf bins
        # (PRD 9.4: bins are by the origin's index in the frozen base
        # calendar, NOT a per-fit subset numbering)
        self.base_index = {d: i for i, d in enumerate(
            np.sort(self.el["origin_date"].unique()))}
        self.train_filter = train_filter
        self.store = LabelStore(labels_path or (AUDIT / "labels.parquet"),
                                audit_log=self.out_dir / "label_reads.jsonl")
        self.inp_hash = {
            "splits": hashlib.sha256((AUDIT / "splits.json").read_bytes()).hexdigest(),
            "features_X": hashlib.sha256((AUDIT / "features_X.parquet").read_bytes()).hexdigest(),
            "features_S": hashlib.sha256((AUDIT / "features_S.parquet").read_bytes()).hexdigest(),
            "eligible_rows": hashlib.sha256((AUDIT / "eligible_rows.parquet").read_bytes()).hexdigest(),
            "labels": hashlib.sha256(Path(labels_path or (AUDIT / "labels.parquet")).read_bytes()).hexdigest(),
        }

    @staticmethod
    def _fit_seed(fit_cutoff: str, salt: int) -> int:
        """Deterministic per-fit seed: master seed + sha256(fit id, salt).
        Python's hash() is process-salted and MUST NOT be used here."""
        h = hashlib.sha256(f"{fit_cutoff}|{salt}".encode()).hexdigest()
        return (MASTER_SEED + int(h[:8], 16)) % (2 ** 31)

    # ------------------------------------------------------------------
    def log(self, msg: str) -> None:
        if not self.quiet:
            print(f"[{self.tag}] {msg}", flush=True)

    def panel(self, origins=None) -> pd.DataFrame:
        if getattr(self, "_panel_cache", None) is None:
            self._panel_cache = (self.manifest
                .merge(self.X[["origin_date", "market"] + P_COLS],
                       on=["origin_date", "market"])
                .merge(self.S[["origin_date", "market"] + S_COLS],
                       on=["origin_date", "market"]))
        df = self._panel_cache
        if origins is not None:
            df = df[df["origin_date"].isin(origins)]
        return df

    def train_set(self, cutoff: pd.Timestamp) -> pd.DataFrame:
        """Matured h20 labels strictly before cutoff, origin >= cutoff-8y,
        intersected with the frozen manifest + feature panel."""
        lo = cutoff - pd.DateOffset(years=8)
        lab = self.store.read_matured(cutoff, self.manifest,
                                    reader=f"{self.tag}:{cutoff.date()}")
        lab = lab[lab["origin_date"] >= lo]
        df = (lab.merge(self.manifest, on=["origin_date", "market"])
                 .merge(self.X[["origin_date", "market"] + P_COLS],
                        on=["origin_date", "market"])
                 .merge(self.S[["origin_date", "market"] + S_COLS],
                        on=["origin_date", "market"])
                 .dropna(subset=P_COLS + S_COLS + ["label"]))
        if getattr(self, "train_filter", None) is not None:
            df = df[self.train_filter(df)]
        return df.sort_values(["origin_date", "market"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    def _fit_ridge_pipeline(self, trd, lam):
        Xr = feature_matrix(trd, RIDGE_MODELS[self._cur_model])
        w = np.asarray(row_weights(trd["origin_date"]))
        mu, sd = fit_fold_scaler(Xr, w)
        Xs = apply_fold_scaler(Xr, mu, sd)
        coef = fit_ridge(Xs, trd["label"].to_numpy(), w, lam)
        return {"mu": mu, "sd": sd, "coef": coef}

    def _pred_ridge_pipeline(self, fitobj, df):
        Xs = apply_fold_scaler(feature_matrix(df, RIDGE_MODELS[self._cur_model]),
                               fitobj["mu"], fitobj["sd"])
        return predict_ridge(fitobj["coef"], Xs)

    def _fit_tree(self, trd, cfg, depth, leaves):
        Xr = feature_matrix(trd, "S" if self._cur_model != "N_X" else "X")
        w = np.asarray(row_weights(trd["origin_date"]))
        wm = w / w.mean()
        est = fit_hgb(Xr, trd["label"].to_numpy(), wm, cfg, depth, leaves)
        return est

    # ------------------------------------------------------------------
    def inner_selection(self, fit_spec) -> dict:
        """Run the locked inner procedure for every tuned learner at an
        annual retune. Returns {model: selected_config, ...} plus audit and
        per-candidate loss records."""
        fit0_blocks = fit_spec["inner_blocks"]
        train_lo = pd.Timestamp(fit0_blocks[0]["train_lo"])
        # canonical inner origin axis: all eligible origins inside any block
        seg_lo = min(pd.Timestamp(b["predict_start"]) for b in fit0_blocks)
        seg_hi = max(pd.Timestamp(b["predict_end"]) for b in fit0_blocks)
        axis = np.sort(self.manifest.loc[
            (self.manifest.origin_date >= seg_lo) &
            (self.manifest.origin_date <= seg_hi), "origin_date"].unique())
        oidx = {d: i for i, d in enumerate(axis)}

        cand = {}
        for m in RIDGE_MODELS:
            for lam in RIDGE_GRID:
                cand[f"{m}|lam={lam:g}"] = {"model": m, "lam": float(lam)}
        for m in TREE_MODELS:
            for cfg in TREE_GRID:
                cand[f"{m}|it={cfg[0]}|lf={cfg[1]}|l2={cfg[2]:g}"] = \
                    {"model": m, "cfg": cfg}

        losses = {c: np.full(len(axis), np.nan) for c in cand}
        inadmissible = {c: [] for c in cand}
        t0 = time.time()
        for bi, blk in enumerate(fit0_blocks):
            fits = list(blk["inner_fits"])
            ends = fits[1:] + [blk["predict_end"]]
            for fit_d, seg_end in zip(fits, ends):
                fit_d, seg_end = pd.Timestamp(fit_d), pd.Timestamp(seg_end)
                trd = self.train_set(fit_d)
                trd = trd[trd["origin_date"] >= train_lo]
                seg = self.panel()
                seg = seg[(seg.origin_date >= fit_d) &
                          (seg.origin_date <= seg_end)]
                seg_lab = self.store.read_matured(
                    pd.Timestamp(seg_end) + pd.Timedelta(days=400),
                    self.manifest, reader=f"{self.tag}:inner_eval")
                # inner evaluation uses the labels themselves at replay
                # time (controls: pseudo-labels; real run: real labels — the
                # inner segment is always inside the pre-cutoff window, so
                # its outcomes are historically known by construction).
                seg = seg.merge(seg_lab[["origin_date", "market", "label"]],
                                on=["origin_date", "market"], how="left")
                seg = seg.dropna(subset=["label"])
                if seg.empty or len(trd) < 500:
                    continue
                w_seg = np.asarray(row_weights(seg["origin_date"]))
                for cid, spec in cand.items():
                    m = spec["model"]
                    try:
                        self._cur_model = m
                        if m in RIDGE_MODELS:
                            fo = self._fit_ridge_pipeline(trd, spec["lam"])
                            pr = self._pred_ridge_pipeline(fo, seg)
                        else:
                            depth, leaves = TREE_MODELS[m]
                            est = self._fit_tree(trd, spec["cfg"],
                                                 depth, leaves)
                            aud = leaf_support_audit(
                                est, feature_matrix(
                                    trd, "S" if m != "N_X" else "X"),
                                trd[["origin_date", "market"]],
                                self.base_index)
                            if (~aud["supported"]).any():
                                inadmissible[cid].append(str(fit_d.date()))
                                continue
                            pr = est.predict(feature_matrix(
                                seg, "S" if m != "N_X" else "X"))
                    except BlockedFit:
                        inadmissible[cid].append(str(fit_d.date()))
                        continue
                    resid = (seg["label"].to_numpy() - pr) ** 2
                    ldf = pd.DataFrame({"o": seg["origin_date"].to_numpy(),
                                        "r": resid, "w": w_seg})
                    per_o = (ldf.groupby("o")
                             .apply(lambda g: np.average(g.r, weights=g.w))
                             )
                    for o, v in per_o.items():
                        losses[cid][oidx[np.datetime64(o)]] = v
            self.log(f"inner block {bi} done ({time.time()-t0:.0f}s)")

        selected, inner_records = {}, {}
        for m in list(RIDGE_MODELS) + list(TREE_MODELS):
            ids = [c for c in cand if cand[c]["model"] == m]
            admissible = {c for c in ids
                          if len(inadmissible[c]) == 0}
            kind = "ridge" if m in RIDGE_MODELS else "tree"
            per_o = {c: losses[c] for c in ids}
            if not admissible:
                selected[m] = {"status": "BLOCKED_FIT_SUPPORT",
                               "detail": "no admissible candidate"}
                inner_records[m] = {
                    "mean_losses": {c: (float(np.nanmean(losses[c]))
                                      if np.isfinite(losses[c]).any()
                                      else None)
                                    for c in ids},
                    "inadmissible": {c: inadmissible[c] for c in ids}}
                continue
            if kind == "ridge":
                sel = one_se_select(per_o, admissible, "ridge",
                                    seed=self._fit_seed(fit_spec["fit_cutoff"], 1))
                selected[m] = {"status": "ok", "config_id": sel,
                               "lambda": float(sel.split("=")[1])}
            else:
                cfg_sel = one_se_select(per_o, admissible, "tree",
                                        seed=self._fit_seed(fit_spec["fit_cutoff"], 2))
                it, lf, l2 = (cfg_sel.split("|")[1].split("=")[1],
                              cfg_sel.split("|")[2].split("=")[1],
                              cfg_sel.split("|")[3].split("=")[1])
                selected[m] = {"status": "ok", "config_id": cfg_sel,
                               "cfg": (int(it), float(lf), float(l2))}
            inner_records[m] = {
                "mean_losses": {c: float(np.nanmean(losses[c]))
                                for c in ids},
                "inadmissible": {c: inadmissible[c] for c in ids
                                 if inadmissible[c]}}

        # L_star: compare selected L_X vs L_S inner losses (ties -> L_X)
        lx = selected.get("L_X", {}).get("config_id")
        ls = selected.get("L_S", {}).get("config_id")
        if lx and ls:
            m_lx = float(np.nanmean(losses[lx]))
            m_ls = float(np.nanmean(losses[ls]))
            chosen = "L_S" if m_ls < m_lx else "L_X"
            selected["L_star"] = {"status": "ok", "member": chosen,
                                  "member_loss": min(m_lx, m_ls),
                                  "lx_loss": m_lx, "ls_loss": m_ls}
        else:
            selected["L_star"] = {"status": "BLOCKED_FIT_SUPPORT"}
        return {"selected": selected, "inner_records": inner_records,
                "axis_len": len(axis)}

    # ------------------------------------------------------------------
    def run_fit(self, fit_spec, selected=None) -> dict:
        """Fit all streams on the cutoff's training window, audit trees,
        issue the next-segment forecasts on frozen eligible rows."""
        cutoff = pd.Timestamp(fit_spec["fit_cutoff"])
        trd = self.train_set(cutoff)
        nxt = self._next_cutoff(cutoff)
        seg = self.panel()
        seg = seg[(seg.origin_date >= cutoff) &
                  (seg.origin_date < nxt if nxt is not None else True)]
        if trd.empty or seg.empty:
            raise BlockedFit(f"{cutoff.date()}: empty train/segment")

        fits, preds, audits = {}, {}, {}
        w = np.asarray(row_weights(trd["origin_date"]))
        ytr = trd["label"].to_numpy()

        fits["B0"] = {"mean": b0_mean(ytr, w)}
        preds["B0"] = np.full(len(seg), fits["B0"]["mean"])

        for m in ("L_X", "L_S", "Q_S"):
            self._cur_model = m
            sel = selected[m]
            if sel["status"] != "ok":
                preds[m] = np.full(len(seg), np.nan)
                fits[m] = sel
                continue
            fo = self._fit_ridge_pipeline(trd, sel["lambda"])
            fits[m] = {"config_id": sel["config_id"], "lambda": sel["lambda"]}
            preds[m] = self._pred_ridge_pipeline(fo, seg)

        m = "L_star"
        sel = selected[m]
        if sel["status"] == "ok":
            member = sel["member"]
            preds[m] = preds[member]
            fits[m] = {"member": member,
                       "config_id": selected[member]["config_id"]}
        else:
            preds[m] = np.full(len(seg), np.nan)
            fits[m] = sel

        for m, (depth, leaves) in TREE_MODELS.items():
            self._cur_model = m
            sel = selected[m]
            if sel["status"] != "ok":
                preds[m] = np.full(len(seg), np.nan)
                fits[m] = sel
                continue
            est = self._fit_tree(trd, sel["cfg"], depth, leaves)
            Xtr = feature_matrix(trd, "S" if m != "N_X" else "X")
            aud = leaf_support_audit(
                est, Xtr, trd[["origin_date", "market"]],
                self.base_index)
            n_bad = int((~aud["supported"]).sum())
            audits[m] = {"n_leaves": int(len(aud)),
                         "n_unsupported": n_bad}
            if n_bad:
                fits[m] = {"status": "BLOCKED_FIT_SUPPORT",
                           "config_id": sel["config_id"],
                           "unsupported_leaves": int(n_bad)}
                preds[m] = np.full(len(seg), np.nan)
                continue
            fits[m] = {"config_id": sel["config_id"], "cfg": sel["cfg"]}
            preds[m] = est.predict(
                feature_matrix(seg, "S" if m != "N_X" else "X"))

        out = seg[["origin_date", "market"]].copy()
        for m in STREAMS:
            out[m] = preds[m]
        return {"fit_cutoff": str(cutoff.date()), "selected": fits,
                "audits": audits, "n_train_rows": int(len(trd)),
                "n_scored_rows": int(len(out)), "forecasts": out}

    def _next_cutoff(self, cutoff: pd.Timestamp):
        dates = sorted(pd.Timestamp(f["fit_cutoff"])
                       for f in self.splits["outer_fits"])
        for d in dates:
            if d > cutoff:
                return d
        return None

    # ------------------------------------------------------------------
    def fit_record_path(self, cutoff: str) -> Path:
        return self.out_dir / f"fit_{cutoff}.json"

    def fc_path(self, cutoff: str) -> Path:
        return self.out_dir / f"forecasts_{cutoff}.parquet"

    def run(self) -> dict:
        """Replay the whole schedule; skip hash-verified completed fits."""
        selected = None
        state_p = self.out_dir / "runner_state.json"
        done = set()
        if state_p.exists():
            st = json.loads(state_p.read_text())
            if st.get("inp_hash") == self.inp_hash:
                done = set(st.get("completed", []))
                selected = st.get("selected")
            else:
                # changed config on resume -> reject (T49)
                raise RuntimeError("input hash mismatch on resume — "
                                   "refusing to mix run versions")
        for fs in self.splits["outer_fits"]:
            c = fs["fit_cutoff"]
            if c in done and self.fit_record_path(c).exists():
                continue
            if fs["retunes"]:
                self.log(f"inner selection at {c}")
                sel_res = self.inner_selection(fs)
                selected = sel_res["selected"]
                (self.out_dir / f"inner_{c}.json").write_text(
                    json.dumps(sel_res["inner_records"], indent=1))
            if selected is None:
                raise RuntimeError(f"fit {c} has no selected config")
            rec = self.run_fit(fs, selected)
            fc = rec.pop("forecasts")
            fc.to_parquet(self.fc_path(c), index=False)
            rec["forecast_rows"] = int(len(fc))
            rec["forecast_hash"] = content_hash(
                fc[["origin_date", "market"]])
            rec["input_hash"] = self.inp_hash
            self.fit_record_path(c).write_text(json.dumps(rec, indent=1))
            done.add(c)
            state_p.write_text(json.dumps(
                {"inp_hash": self.inp_hash, "completed": sorted(done),
                 "selected": selected}, indent=1))
            self.log(f"fit {c} done")
        return {"completed": sorted(done), "n_fits": len(done)}
