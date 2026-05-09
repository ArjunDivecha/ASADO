"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/config.py
=============================================================================

INPUT FILES:
- (none — pure constants)

OUTPUT FILES:
- (none)

VERSION: 1.0
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Central configuration for Strategy #1 — World-State Analog country selection,
v1 MVP. All defaults from PRD §8.3 live here. Phase 2 will sweep these; v1
keeps them frozen.

DEPENDENCIES:
- (stdlib only)

USAGE:
  from scripts.strategy.analogs import config as C

NOTES:
- Transaction costs are intentionally OUT OF SCOPE for v1 (per user direction).
  Backtest reports gross returns only; turnover is logged so a future phase
  can layer costs on without reworking the harness.
- Random seed is fixed for reproducibility (PRD §8.5).
=============================================================================
"""

from pathlib import Path

# -----------------------------------------------------------------------------
# Repo paths (this file lives at scripts/strategy/analogs/config.py)
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "Data"
STRATEGY_DIR = DATA_DIR / "strategy" / "analogs" / "v1"
LOG_DIR = STRATEGY_DIR / "logs"
DOCS_DIR = BASE_DIR / "docs" / "strategy" / "analogs" / "v1"

DUCKDB_PATH = DATA_DIR / "asado.duckdb"
T2_MASTER_XLSX = DATA_DIR / "T2 Master.xlsx"

# Headline hurdle: analog strategy must beat equal-weight by this much,
# annualized, gross of costs. Success criterion (PRD §10):
#   analog_ann_return − equal_weight_ann_return ≥ BENCHMARK_HURDLE_EXCESS_ANNUAL
BENCHMARK_HURDLE_EXCESS_ANNUAL = 0.06

# Output artifacts (PRD §4)
SIGNALS_PARQUET = STRATEGY_DIR / "signals.parquet"
ANALOG_MATCHES_PARQUET = STRATEGY_DIR / "analog_matches.parquet"
BACKTEST_PARQUET = STRATEGY_DIR / "backtest.parquet"
BASELINES_PARQUET = STRATEGY_DIR / "baselines.parquet"
WORLDSTATES_PARQUET = STRATEGY_DIR / "worldstates.parquet"
PIT_AUDIT_CSV = STRATEGY_DIR / "pit_audit.csv"
COUNTRY_FORECASTS_XLSX = STRATEGY_DIR / "Country_Forecasts.xlsx"
GO_NO_GO_MD = DOCS_DIR / "go_no_go.md"

# DuckDB tables we read or write
RETURNS_TABLE = "country_returns_monthly"
FEATURE_PANEL_VIEW = "feature_panel"
T2_MASTER_TABLE = "t2_master"

# -----------------------------------------------------------------------------
# Backtest / model parameters (PRD §8.3)
# -----------------------------------------------------------------------------
BACKTEST_START = "2008-01-31"        # First decision date
MIN_LAG_MONTHS = 12                  # Analog must precede t by ≥ this many months
K_ANALOGS = 10                       # Top-k similar historical states
SOFTMAX_TAU = 1.0                    # Temperature for similarity → weight
MIN_FEATURE_HISTORY_MONTHS = 60      # Variable needs ≥ this many obs before t to qualify
PCA_VARIANCE_TARGET = 0.80           # Retain enough comps for ≥ this variance
PCA_MAX_COMPONENTS = 30              # Cap regardless of variance target
FEATURE_PREFIX = "_CS"               # v1 uses cross-sectional z-scored features
TOP_N = 7                            # Long-only: hold top-N by forecast (≈ quintile of 34)
FORWARD_HORIZON_MONTHS = 1           # 1-month-forward only in v1

# -----------------------------------------------------------------------------
# Reproducibility
# -----------------------------------------------------------------------------
RANDOM_SEED = 42

# -----------------------------------------------------------------------------
# Identifiers
# -----------------------------------------------------------------------------
MODEL_VERSION = "v1-mvp-2026-04"

# The 34 T2 country names — exact strings, must match feature_panel.country and
# T2 Master 1MRet column headers. Maintained here so a single mis-spelling is
# loud, not silent.
T2_COUNTRIES = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH",
    "Denmark", "France", "Germany", "Hong Kong", "India", "Indonesia",
    "Italy", "Japan", "Korea", "Malaysia", "Mexico", "NASDAQ",
    "Netherlands", "Philippines", "Poland", "Saudi Arabia", "Singapore",
    "South Africa", "Spain", "Sweden", "Switzerland", "Taiwan",
    "Thailand", "Turkey", "U.K.", "U.S.", "US SmallCap", "Vietnam",
]
assert len(T2_COUNTRIES) == 34, f"Expected 34 T2 countries, found {len(T2_COUNTRIES)}"


def ensure_dirs() -> None:
    """Create output directories if missing. Safe to call repeatedly."""
    for d in (STRATEGY_DIR, LOG_DIR, DOCS_DIR):
        d.mkdir(parents=True, exist_ok=True)
