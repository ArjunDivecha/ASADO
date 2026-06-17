#!/usr/bin/env python3
"""
spectral.py — Spectral diagnostics for ASADO.

Implements the three diagnostics described in docs/SPECTRAL_DIAGNOSTICS.md,
derived from Drusvyatskiy's DSC-243 convex-quadratic notes:

  1. Source-condition slope s'   -> IC-plateau triage          (sec. 1)
  2. Marchenko-Pastur edges      -> covariance noise floor     (sec. 2)
  3. Effective rank, gamma_c     -> stability / batch limits   (sec. 3)

All three are scalars/curves computed from matrices ASADO already forms:
the cross-sectional design X (variables x observations) and its Gram /
covariance matrix H.

USAGE
-----
    from diagnostics.spectral import (
        source_condition_slope, mp_edges, effective_rank, panel_report,
    )

    rep = panel_report(X, y)          # X: (n_obs, d_vars), y: (n_obs,)
    print(rep.as_text())

CLI
---
    python -m diagnostics.spectral --panel <path-to-design.npy/.parquet> \
                                   --target <path-to-target.npy>          \
                                   --out reports/spectral_<YYYY_MM>.md

NOTE ON DATA LOADING
--------------------
This module is deliberately agnostic about where X and y come from. The pure
linear-algebra functions below take numpy arrays and have no ASADO
dependencies. The `load_design_from_duckdb` hook at the bottom is a STUB:
wire it to the real unified_panel accessor (see CLAUDE.md "database bridge
patterns") before relying on the CLI. It is intentionally left unimplemented
rather than guessing the live schema.

Conventions follow CLAUDE.md: module docstring header, explicit failures
(raise, don't silently fallback), reports written to reports/.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import sys
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Core linear algebra (no ASADO dependencies; unit-testable in isolation)
# ---------------------------------------------------------------------------

def _gram(X: np.ndarray, normalize: bool) -> np.ndarray:
    """Return H = XᵀX, optionally normalized by n (=> sample covariance).

    X is (n_obs, d_vars). Raises on degenerate input rather than returning
    a silently-wrong matrix.
    """
    if X.ndim != 2:
        raise ValueError(f"X must be 2-D (n_obs, d_vars); got shape {X.shape}")
    n, d = X.shape
    if n == 0 or d == 0:
        raise ValueError(f"X has an empty dimension: shape {X.shape}")
    H = X.T @ X
    if normalize:
        H = H / float(n)
    return H


def eigenspectrum(H: np.ndarray) -> np.ndarray:
    """Eigenvalues of a symmetric PSD matrix, ascending, clipped at 0.

    Uses eigvalsh (symmetric solver). Tiny negative values from round-off are
    clipped to 0.
    """
    w = np.linalg.eigvalsh(H)
    return np.clip(w, 0.0, None)


@dataclasses.dataclass
class SourceConditionResult:
    slope: float                # s' : the matrix-level source exponent
    intercept: float
    r_squared: float
    n_modes_used: int
    regime: str                 # "learnable" | "marginal" | "noise-limited"
    note: str

    def as_text(self) -> str:
        return (
            f"Source-condition slope s' = {self.slope:+.3f} "
            f"(R^2={self.r_squared:.2f}, modes={self.n_modes_used})\n"
            f"  regime: {self.regime}\n  {self.note}"
        )


def source_condition_slope(
    X: np.ndarray,
    y: np.ndarray,
    *,
    eig_floor_frac: float = 1e-6,
    normalize: bool = False,
) -> SourceConditionResult:
    """Estimate the matrix-level source exponent s' (DSC-243 sec. 1).

    Procedure:
      H = XᵀX ; eigendecompose H = V diag(lambda) Vᵀ
      b_i = v_iᵀ (Xᵀy)            (projection of the target onto eigvec i)
      c_i = b_i / lambda_i        (initial GD-from-zero error coefficients)
      slope = OLS slope of log|c_i| on log lambda_i

    Interpretation of the slope (see docs/SPECTRAL_DIAGNOSTICS.md sec. 1):
      s' > 0      -> signal in well-conditioned directions: learnable;
                     plateau is model/optimizer-limited (IPCA can help)
      -0.5<s'<0   -> marginal; needs dimension-free estimators, not capacity
      s' <= -0.5  -> signal in the noise tail: plateau is information-theoretic

    Modes with lambda below eig_floor_frac * lambda_max are dropped (they are
    numerically zero and would dominate the log-log fit with noise).
    """
    if X.ndim != 2:
        raise ValueError(f"X must be 2-D; got {X.shape}")
    if y.ndim != 1 or y.shape[0] != X.shape[0]:
        raise ValueError(
            f"y must be 1-D of length n_obs={X.shape[0]}; got {y.shape}"
        )

    H = _gram(X, normalize=normalize)
    # Symmetric eigendecomposition: ascending eigenvalues, orthonormal vectors.
    lam, V = np.linalg.eigh(H)
    lam = np.clip(lam, 0.0, None)

    rhs = X.T @ y                       # Xᵀy  (length d)
    b = V.T @ rhs                       # projection onto each eigenvector

    lam_max = float(lam.max()) if lam.size else 0.0
    if lam_max <= 0.0:
        raise ValueError("H has no positive eigenvalues; design is degenerate.")

    keep = lam > eig_floor_frac * lam_max
    lam_k = lam[keep]
    b_k = b[keep]
    if lam_k.size < 3:
        raise ValueError(
            f"Only {lam_k.size} usable modes above the eigenvalue floor; "
            "cannot fit a slope. Lower eig_floor_frac or widen the window."
        )

    c = b_k / lam_k                     # initial-error coefficients
    # Guard against exact-zero projections before the log.
    nz = np.abs(c) > 0
    x_log = np.log(lam_k[nz])
    y_log = np.log(np.abs(c[nz]))
    n_used = int(nz.sum())
    if n_used < 3:
        raise ValueError("Too few nonzero projections to fit a slope.")

    # OLS slope/intercept of y_log ~ slope * x_log + intercept.
    slope, intercept = np.polyfit(x_log, y_log, deg=1)
    y_hat = slope * x_log + intercept
    ss_res = float(np.sum((y_log - y_hat) ** 2))
    ss_tot = float(np.sum((y_log - y_log.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    if slope > 0:
        regime = "learnable"
        note = ("Signal sits in well-conditioned directions. An IC plateau "
                "here is model/optimizer-limited; IPCA / richer features / "
                "more search can help.")
    elif slope > -0.5:
        regime = "marginal"
        note = ("Signal is partly in soft-edge directions. Gains require "
                "dimension-free estimators (ridge with ||u|| control), not "
                "more model capacity.")
    else:
        regime = "noise-limited"
        note = ("Signal lives in the noise tail. An IC plateau here is "
                "information-theoretic: change the target, horizon, or "
                "universe rather than adding search compute.")

    return SourceConditionResult(
        slope=float(slope),
        intercept=float(intercept),
        r_squared=float(r2),
        n_modes_used=n_used,
        regime=regime,
        note=note,
    )


@dataclasses.dataclass
class MPResult:
    gamma: float                # d / n
    lambda_minus: float         # informative-bulk lower edge ((1-sqrt(g))^2)
    lambda_plus: float          # bulk upper edge ((1+sqrt(g))^2)
    has_zero_atom: bool         # True when gamma > 1 (rank deficient)
    note: str

    def as_text(self) -> str:
        atom = " (+ zero-eigenvalue atom)" if self.has_zero_atom else ""
        return (
            f"Marchenko-Pastur: gamma=d/n={self.gamma:.3f}{atom}\n"
            f"  noise bulk edges  lambda- = {self.lambda_minus:.4f}, "
            f"lambda+ = {self.lambda_plus:.4f}\n  {self.note}"
        )


def mp_edges(d: int, n: int) -> MPResult:
    """Marchenko-Pastur bulk edges for a d x n design (DSC-243 sec. 2).

    Edges are lambda_pm = (1 +/- sqrt(gamma))^2 with gamma = d/n, computed on
    the NORMALIZED covariance H = (1/n) XᵀX (unit-variance entries assumed).
    Eigenvalues inside [lambda-, lambda+] are indistinguishable from noise.

    When gamma > 1 the matrix is rank-deficient (an atom of zero eigenvalues);
    the informative bulk uses |1 - sqrt(gamma)| for the lower edge.
    """
    if d <= 0 or n <= 0:
        raise ValueError(f"d and n must be positive; got d={d}, n={n}")
    gamma = d / n
    sg = np.sqrt(gamma)
    lambda_plus = (1.0 + sg) ** 2
    lambda_minus = (1.0 - sg) ** 2     # = (|1-sqrt(g)|)^2; correct for g>1 too
    has_atom = gamma > 1.0
    if has_atom:
        note = ("gamma>1: more variables than observations. A mass of exactly-"
                "zero eigenvalues exists; only directions with eigenvalue "
                "above lambda+ carry real structure.")
    else:
        note = ("gamma<1: full-rank regime. Sample-covariance directions with "
                "eigenvalue inside the bulk are noise; treat lambda+ as the "
                "shrinkage cutoff.")
    return MPResult(
        gamma=float(gamma),
        lambda_minus=float(lambda_minus),
        lambda_plus=float(lambda_plus),
        has_zero_atom=bool(has_atom),
        note=note,
    )


@dataclasses.dataclass
class EffectiveRankResult:
    trace: float
    lambda_max: float
    effective_rank: float       # Tr(H) / lambda_max  (participation ratio)
    mean_eigenvalue: float      # lambda_bar = Tr(H) / d
    critical_stepsize: float    # gamma_c = 2 d / Tr(H) = 2 / lambda_bar
    d: int

    def as_text(self) -> str:
        return (
            f"Effective rank Tr(H)/lambda_max = {self.effective_rank:.1f} "
            f"(of d={self.d})\n"
            f"  mean eigenvalue lambda_bar = {self.mean_eigenvalue:.4g}\n"
            f"  critical stepsize gamma_c = 2d/Tr(H) = "
            f"{self.critical_stepsize:.4g}\n"
            f"  (online estimators: keep stepsize < gamma_c; batching past "
            f"B_crit ~= {self.effective_rank:.0f} gives diminishing returns)"
        )


def effective_rank(H: np.ndarray) -> EffectiveRankResult:
    """Effective rank, mean eigenvalue, and critical stepsize (DSC-243 sec. 3).

      effective_rank = Tr(H) / lambda_max          (participation ratio)
      lambda_bar     = Tr(H) / d                    (average eigenvalue)
      gamma_c        = 2 / lambda_bar = 2 d / Tr(H) (SGD stability ceiling)
      B_crit         = Tr(H) / lambda_max           (critical batch size)

    Stability of any online/streaming estimator is set by the AVERAGE
    eigenvalue, not lambda_max — the counterintuitive result of the §10
    Volterra limit.
    """
    if H.ndim != 2 or H.shape[0] != H.shape[1]:
        raise ValueError(f"H must be square; got shape {H.shape}")
    d = H.shape[0]
    lam = eigenspectrum(H)
    trace = float(np.sum(lam))
    lam_max = float(lam.max())
    if lam_max <= 0.0:
        raise ValueError("H has no positive eigenvalues; design is degenerate.")
    lam_bar = trace / d
    return EffectiveRankResult(
        trace=trace,
        lambda_max=lam_max,
        effective_rank=trace / lam_max,
        mean_eigenvalue=lam_bar,
        critical_stepsize=2.0 / lam_bar,
        d=d,
    )


# ---------------------------------------------------------------------------
# Combined report
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class PanelReport:
    n_obs: int
    d_vars: int
    source: Optional[SourceConditionResult]
    mp: MPResult
    erank: EffectiveRankResult
    generated: str

    def as_text(self) -> str:
        lines = [
            "# Spectral diagnostics report",
            f"Generated: {self.generated}",
            f"Design: n_obs={self.n_obs}, d_vars={self.d_vars}",
            "",
            "## 1. Source condition (IC-plateau triage)",
        ]
        lines.append(self.source.as_text() if self.source
                     else "  (skipped: no target y supplied)")
        lines += ["", "## 2. Marchenko-Pastur noise floor", self.mp.as_text()]
        lines += ["", "## 3. Effective rank & stability", self.erank.as_text()]
        lines += ["", "See docs/SPECTRAL_DIAGNOSTICS.md for interpretation."]
        return "\n".join(lines)

    def as_markdown(self) -> str:
        # The text form is already valid Markdown for report purposes.
        return self.as_text() + "\n"


def panel_report(
    X: np.ndarray,
    y: Optional[np.ndarray] = None,
    *,
    normalize_cov: bool = True,
) -> PanelReport:
    """Run all three diagnostics on a design matrix X (and optional target y).

    X is (n_obs, d_vars). The source-condition test is skipped when y is None.
    The MP edges and effective rank use the (optionally normalized) covariance.
    """
    if X.ndim != 2:
        raise ValueError(f"X must be 2-D (n_obs, d_vars); got {X.shape}")
    n, d = X.shape
    H = _gram(X, normalize=normalize_cov)

    src = source_condition_slope(X, y) if y is not None else None
    mp = mp_edges(d=d, n=n)
    er = effective_rank(H)

    return PanelReport(
        n_obs=n,
        d_vars=d,
        source=src,
        mp=mp,
        erank=er,
        generated=_dt.datetime.now().isoformat(timespec="seconds"),
    )


# ---------------------------------------------------------------------------
# Data loading hook (STUB — wire to unified_panel before CLI use)
# ---------------------------------------------------------------------------

def load_design_from_duckdb(*args, **kwargs):  # pragma: no cover
    """STUB. Wire this to the real unified_panel accessor.

    Should return (X, y, meta) where X is (n_obs, d_vars), y is (n_obs,) or
    None, and meta carries column/date labels. Left unimplemented on purpose:
    see CLAUDE.md "database bridge patterns" for the canonical DuckDB access
    pattern, and fail explicitly rather than guessing the schema.
    """
    raise NotImplementedError(
        "load_design_from_duckdb is a stub. Wire it to the unified_panel "
        "DuckDB accessor (see CLAUDE.md) before using the CLI."
    )


def _load_array(path: str) -> np.ndarray:
    if path.endswith(".npy"):
        return np.load(path)
    if path.endswith(".csv"):
        return np.loadtxt(path, delimiter=",")
    if path.endswith(".parquet"):
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pandas required to read .parquet") from exc
        return pd.read_parquet(path).to_numpy()
    raise ValueError(f"Unsupported file type for {path!r}; use .npy/.csv/.parquet")


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description="ASADO spectral diagnostics.")
    p.add_argument("--panel", required=True,
                   help="Design matrix file (.npy/.csv/.parquet), shape (n_obs, d_vars).")
    p.add_argument("--target", default=None,
                   help="Optional target vector file (.npy/.csv), length n_obs.")
    p.add_argument("--out", default=None,
                   help="Write the Markdown report here (e.g. reports/spectral_2026_06.md).")
    p.add_argument("--no-normalize", action="store_true",
                   help="Use raw Gram XᵀX instead of (1/n) XᵀX for covariance diagnostics.")
    args = p.parse_args(argv)

    X = _load_array(args.panel)
    y = _load_array(args.target) if args.target else None
    if y is not None and y.ndim > 1:
        y = y.ravel()

    rep = panel_report(X, y, normalize_cov=not args.no_normalize)
    text = rep.as_markdown()

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
