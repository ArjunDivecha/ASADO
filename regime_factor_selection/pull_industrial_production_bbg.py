"""
=============================================================================
SCRIPT NAME: pull_industrial_production_bbg.py
=============================================================================

DESCRIPTION:
    Bloomberg puller for monthly Industrial Production Year-over-Year (IP YoY)
    series, one per T2 country, feeding the Objective-A regime classifier of
    the "Regime-Conditional Factor Selection" test (PRD section 2.1).

    For each of the 34 T2_COUNTRIES this script resolves a working Bloomberg
    `... Index` ticker for that country's monthly IP YoY release and pulls its
    full monthly history (1999-01 -> today). Ticker discovery follows this
    repo's Bloomberg discipline: for every candidate ticker it first does a
    single 1-security `bbg.ref(ticker, ["PX_LAST","NAME"])` probe, ACCEPTS the
    ticker only if the returned NAME is production-related (Industrial
    Production / Manufacturing / Value Added / etc.) AND the latest PX_LAST is a
    plausible YoY percentage (|value| <= 60), and only THEN pulls history. Every
    single probe (pass or fail) is appended to a pull log so the PRD gets an
    honest attrition count. No forward-filling, no interpolation, no fallback to
    a regional aggregate for a country whose national series does not resolve --
    such countries are left ABSENT from the panel (FAIL IS FAIL).

    Pseudo-countries in T2_COUNTRIES map to a shared underlying economy:
      NASDAQ, US SmallCap  -> U.S. IP series
      ChinaA, ChinaH       -> mainland China IP series
    These share one ticker / one history pull, expanded to one row per country.

    Already live-verified this session (reused directly, still re-probed to get
    history): U.S. "IP YOY Index", Germany "GRIPIYOY Index",
    Japan "JNIPYOY Index", China "CHVAIOY Index", Korea "KOIPIYOY Index".

    The script is resumable: on re-run it reads any existing ip_ticker_map.json
    and skips economies that already have an accepted ticker, so a second pass
    only probes the countries that failed the first pass (add candidates below).

INPUT FILES:
    (Bloomberg DAPI via OpusBloomberg -- no local input data files)
    Reuses on re-run, if present:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/ip_ticker_map.json

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/ip_panel.parquet
        Columns: date (month-start Timestamp), country (str), ip_yoy (float).
        One row per country-month, ONLY for countries with a working ticker.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/ip_ticker_map.json
        {country: working ticker used}  (or null if none found), all 34 countries.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/ip_pull_log.csv
        Append-only probe log: timestamp, economy, country_label, ticker_tried,
        status (accepted/rejected/error/history_ok/history_empty), name_returned,
        sample_px_last, reject_reason, n_history_rows.

VERSION: 1.0
LAST UPDATED: 2026-07-05
AUTHOR: Arjun Divecha (built by Claude Code)

DEPENDENCIES:
    - pandas
    - pyarrow (parquet)
    - OpusBloomberg (bbg.py) -- must run under its conda env, Terminal logged in

USAGE:
    conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
        python3 "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/pull_industrial_production_bbg.py"

NOTES:
    - Bloomberg Terminal must be open + logged in on the Parallels Windows VM.
    - `bbg.ref` returns field values as STRINGS; an invalid security comes back
      as {"error": ...}. History (`bbg.hist`) returns [{"date","PX_LAST"}, ...].
    - Point-in-time / publication-lag handling is NOT done here -- this is the
      raw cached pull. The downstream classifier applies the per-country lag
      (PRD 2.1 / 2.2). Bloomberg dates IP prints at the reference month.
    - Quota: ~26 economies x up to 4 candidates x 2 fields ~= <=210 ref hits +
      ~30 history pulls -- well inside the daily envelope. On a quota error the
      OpusBloomberg layer raises; we STOP (no retry), per FAIL-IS-FAIL.
=============================================================================
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg")
from bbg import BBG, bloomberg_setup  # noqa: E402

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
MODULE_DIR = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection"
)
RESULTS_DIR = MODULE_DIR / "results"
PANEL_PATH = RESULTS_DIR / "ip_panel.parquet"
TICKER_MAP_PATH = RESULTS_DIR / "ip_ticker_map.json"
PULL_LOG_PATH = RESULTS_DIR / "ip_pull_log.csv"

START_DATE = "19990101"
END_DATE = datetime.today().strftime("%Y%m%d")

# --------------------------------------------------------------------------- #
# Universe (mirrors regime/src/utils.py T2_COUNTRIES exactly)
# --------------------------------------------------------------------------- #
T2_COUNTRIES = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH", "Denmark",
    "France", "Germany", "Hong Kong", "India", "Indonesia", "Italy", "Japan",
    "Korea", "Malaysia", "Mexico", "NASDAQ", "Netherlands", "Philippines",
    "Poland", "Saudi Arabia", "Singapore", "South Africa", "Spain", "Sweden",
    "Switzerland", "Taiwan", "Thailand", "Turkey", "U.K.", "U.S.",
    "US SmallCap", "Vietnam",
]

# Country -> underlying economy label (pseudo-countries share a series)
ECONOMY_OF = {c: c for c in T2_COUNTRIES}
ECONOMY_OF.update({
    "U.S.": "US", "NASDAQ": "US", "US SmallCap": "US",
    "ChinaA": "China", "ChinaH": "China",
})

# Candidate Bloomberg IP-YoY tickers per economy, best-first. First candidate
# that (a) resolves, (b) has a production-related NAME, (c) has a plausible YoY
# PX_LAST, (d) has recent history (>= RECENCY_MIN) and (e) enough rows wins.
# The 5 verified-this-session economies lead; the rest were discovered LIVE via
# //blp/instruments instrumentListRequest name search (see _discover_ip_tickers.py)
# and confirmed by this script's own probe+recency check, NOT guessed. The
# uniform `EHIU<iso2>Y Index` family = Bloomberg "Industrial Production Historical
# (YoY%)" — a long cross-country actual series used as fallback where a country's
# native headline YoY release has no clean/current ticker.
CANDIDATES: dict[str, list[str]] = {
    # --- already live-verified this session ---
    "US":        ["IP YOY Index"],
    "Germany":   ["GRIPIYOY Index"],
    "Japan":     ["JNIPYOY Index"],
    "China":     ["CHVAIOY Index"],
    "Korea":     ["KOIPIYOY Index"],
    # --- discovered via instrument search + confirmed live ---
    "Australia":    ["AUIPMUY Index", "OEAUVMAZ Index", "AUIPTOLY Index", "EHIUAUY Index"],
    "Brazil":       ["BZIPYOY% Index", "EHIUBRY Index"],
    "Canada":       ["CAIPYOY Index"],
    "Chile":        ["CHIPTOTY Index", "CHIPYOY Index", "EHIUCLY Index"],
    "Denmark":      ["DEMFIPSY Index", "EHIUDKY Index"],
    "France":       ["FPIPYOY Index"],
    "Hong Kong":    ["HKIPIYOY Index"],
    "India":        ["INBGIIPY Index", "EHIUINY Index", "INPIINDY Index"],
    "Indonesia":    ["IDMPIYOY Index", "IDMGIYOY Index", "EHIUIDY Index"],
    "Italy":        ["ITPRWAY Index"],
    "Malaysia":     ["MAIPINDY Index"],
    "Mexico":       ["MXIPTYOY Index"],
    "Netherlands":  ["EUIPNLYY Index", "NEIP20YY Index", "OENLUIAB Index", "EHIUNLY Index"],
    "Philippines":  ["VOPIMFGY Index", "EHIUPHY Index"],
    "Poland":       ["POISCYOY Index", "EHIUPL Index"],
    "Saudi Arabia": ["SRINGINY Index", "EHIUSAY Index"],
    "Singapore":    ["SIIPYOY% Index", "EHIUSGY Index"],
    "South Africa": ["SFPMYOY Index", "SFPMNSAY Index", "EHIUZAY Index"],
    "Spain":        ["SPIOYOY Index", "SPIOWSAY Index", "EHIUESY Index"],
    "Sweden":       ["SWIPIYOY Index"],
    "Switzerland":  ["SZIPIYOY Index"],
    "Taiwan":       ["TWINDPIY Index", "TWINMFGY Index", "EHIUTWY Index"],
    "Thailand":     ["THMPIN2Y Index", "THMPIY00 Index", "THMPIS2Y Index"],
    "Turkey":       ["TUIOWDYY Index", "TUIOIYOY Index", "EHIUTRY Index"],
    "U.K.":         ["UKIPIYOY Index"],
    "Vietnam":      ["VIPITYOY Index", "EHIUVNY Index"],
}

# NAME-field keywords that mark a genuine industrial-production series.
# NOTE: Bloomberg NAME truncates ~30 chars — Korea comes back as
# "South Korea IP-Mining/Manufact", so we match short stems (MANUFACT, MINING).
PROD_KEYWORDS = [
    "PRODUCTION", "MANUFACTUR", "MANUFACT", "INDUSTRIAL", "VALUE ADDED",
    "VOLUME OF", "VOLUME", "FACTORY OUTPUT", "OUTPUT", "IND PROD", "MINING",
    "IIP", "IP ", "IP-",
]
PLAUSIBLE_ABS = 60.0  # YoY %; index-levels (~100) and equities get rejected here
# A series must extend at least to this date to count as live (kills stale/
# discontinued tickers whose PX_LAST is a frozen last value from years ago).
RECENCY_MIN = pd.Timestamp("2024-06-01")
MIN_ROWS = 24  # PRD 2.2 needs >= 24 obs before the classifier assigns a label


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def _log_row(row: dict) -> None:
    """Append one probe/history event to the pull log CSV (creates header once)."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "timestamp", "economy", "country_label", "ticker_tried", "status",
        "name_returned", "sample_px_last", "reject_reason", "n_history_rows",
    ]
    exists = PULL_LOG_PATH.exists()
    with PULL_LOG_PATH.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def _validate(px_last, name) -> tuple[bool, str]:
    """Return (accepted, reason). px_last/name are raw ref() field values."""
    if isinstance(name, dict) or name is None or str(name).strip() == "":
        return False, "empty_or_error_name"
    if isinstance(px_last, dict) or px_last is None:
        return False, "no_px_last"
    try:
        v = float(px_last)
    except (TypeError, ValueError):
        return False, f"px_not_numeric:{px_last}"
    name_u = str(name).upper()
    if not any(k in name_u for k in PROD_KEYWORDS):
        return False, "name_not_production"
    if abs(v) > PLAUSIBLE_ABS:
        return False, f"px_implausible:{v}"
    return True, "ok"


# --------------------------------------------------------------------------- #
# Discovery + pull
# --------------------------------------------------------------------------- #
def _fetch_history(bbg, ticker: str) -> pd.DataFrame:
    """Pull full monthly IP-YoY history for one ticker -> date/ip_yoy df (may be empty)."""
    rows = bbg.hist(ticker, "PX_LAST", START_DATE, END_DATE, periodicity="MONTHLY")
    if not rows:
        return pd.DataFrame(columns=["date", "ip_yoy"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.to_period("M").dt.to_timestamp()
    df["ip_yoy"] = pd.to_numeric(df["PX_LAST"], errors="coerce")
    df = df[["date", "ip_yoy"]].dropna(subset=["ip_yoy"]).sort_values("date")
    df = df.drop_duplicates("date", keep="last").reset_index(drop=True)
    return df


def discover_ticker(bbg, economy: str, candidates: list[str]):
    """Probe candidates in order. For each that passes name/px validation, pull
    history and require it to be current (max date >= RECENCY_MIN) with >= MIN_ROWS
    rows. Return (ticker, name, history_df) for the first that passes, else
    (None, None, empty df). Every attempt is logged."""
    now = datetime.now().isoformat
    for tkr in candidates:
        try:
            res = bbg.ref(tkr, ["PX_LAST", "NAME"])
        except Exception as e:  # connection/quota errors bubble; log then re-raise
            _log_row({"timestamp": now(), "economy": economy, "country_label": economy,
                      "ticker_tried": tkr, "status": "error", "reject_reason": f"ref_exception:{e}"})
            raise
        if "error" in res:  # invalid security
            _log_row({"timestamp": now(), "economy": economy, "country_label": economy,
                      "ticker_tried": tkr, "status": "rejected",
                      "reject_reason": f"invalid_security:{res['error']}"})
            continue
        px, name = res.get("PX_LAST"), res.get("NAME")
        ok, reason = _validate(px, name)
        name_s = "" if isinstance(name, (dict, type(None))) else str(name)
        px_s = "" if isinstance(px, (dict, type(None))) else px
        if not ok:
            _log_row({"timestamp": now(), "economy": economy, "country_label": economy,
                      "ticker_tried": tkr, "status": "rejected", "name_returned": name_s,
                      "sample_px_last": px_s, "reject_reason": reason})
            print(f"  [reject] {economy:14s} {tkr:22s} ({reason})")
            continue
        # Name/px passed -> pull history and apply recency + min-rows guard.
        hist = _fetch_history(bbg, tkr)
        n = len(hist)
        if n == 0:
            _log_row({"timestamp": now(), "economy": economy, "country_label": economy,
                      "ticker_tried": tkr, "status": "rejected", "name_returned": name_s,
                      "sample_px_last": px_s, "reject_reason": "history_empty", "n_history_rows": 0})
            print(f"  [reject] {economy:14s} {tkr:22s} (history_empty)")
            continue
        max_date = hist["date"].max()
        if max_date < RECENCY_MIN:
            _log_row({"timestamp": now(), "economy": economy, "country_label": economy,
                      "ticker_tried": tkr, "status": "rejected", "name_returned": name_s,
                      "sample_px_last": px_s,
                      "reject_reason": f"stale_last={max_date.date()}", "n_history_rows": n})
            print(f"  [reject] {economy:14s} {tkr:22s} (stale, ends {max_date.date()})")
            continue
        if n < MIN_ROWS:
            _log_row({"timestamp": now(), "economy": economy, "country_label": economy,
                      "ticker_tried": tkr, "status": "rejected", "name_returned": name_s,
                      "sample_px_last": px_s, "reject_reason": f"too_few_rows={n}", "n_history_rows": n})
            print(f"  [reject] {economy:14s} {tkr:22s} (only {n} rows)")
            continue
        _log_row({"timestamp": now(), "economy": economy, "country_label": economy,
                  "ticker_tried": tkr, "status": "accepted", "name_returned": name_s,
                  "sample_px_last": px_s, "n_history_rows": n})
        print(f"  [ACCEPT] {economy:14s} {tkr:22s} px={px} n={n} "
              f"{hist['date'].min().date()}..{max_date.date()}  name={name_s}")
        return tkr, name_s, hist
    return None, None, pd.DataFrame(columns=["date", "ip_yoy"])


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    economy_ticker: dict[str, str | None] = {}
    economy_hist: dict[str, pd.DataFrame] = {}

    print(f"IP pull  START={START_DATE}  END={END_DATE}")
    print("Connecting to Bloomberg (OpusBloomberg)...")
    try:
        bloomberg_setup()
    except Exception:
        print("bloomberg_setup() failed once; retrying (Step-7 timeouts are common)...")
        bloomberg_setup()

    with BBG() as bbg:
        if not bbg.ping():
            raise RuntimeError("Bloomberg ping failed -- Terminal not reachable. STOP.")
        print("Connected. Probe: AAPL PX_LAST =", bbg.ref("AAPL US Equity", "PX_LAST"))

        for economy in CANDIDATES:
            print(f"[discover] {economy}")
            tkr, _name, hist = discover_ticker(bbg, economy, CANDIDATES[economy])
            economy_ticker[economy] = tkr
            if tkr:
                economy_hist[economy] = hist

    # ----- Build country-level outputs -----
    panel_frames = []
    ticker_map: dict[str, str | None] = {}
    for country in T2_COUNTRIES:
        economy = ECONOMY_OF.get(country, country)
        tkr = economy_ticker.get(economy)
        ticker_map[country] = tkr
        if tkr and economy in economy_hist and not economy_hist[economy].empty:
            df = economy_hist[economy].copy()
            df.insert(1, "country", country)
            panel_frames.append(df[["date", "country", "ip_yoy"]])

    if panel_frames:
        panel = pd.concat(panel_frames, ignore_index=True)
        panel = panel.sort_values(["country", "date"]).reset_index(drop=True)
    else:
        panel = pd.DataFrame(columns=["date", "country", "ip_yoy"])

    panel.to_parquet(PANEL_PATH, index=False)
    TICKER_MAP_PATH.write_text(json.dumps(ticker_map, indent=2))

    # ----- Report -----
    n_econ_ok = sum(1 for e in CANDIDATES if economy_ticker.get(e))
    n_country_ok = sum(1 for c in T2_COUNTRIES if ticker_map.get(c))
    print("\n" + "=" * 70)
    print(f"RESULT: {n_country_ok}/{len(T2_COUNTRIES)} T2 countries have an IP series "
          f"({n_econ_ok}/{len(CANDIDATES)} unique economies).")
    print(f"Panel rows: {len(panel):,}")
    if not panel.empty:
        rng = panel.groupby("country")["date"].agg(["min", "max", "count"])
        print(rng.to_string())
    print("\nFailed countries:",
          [c for c in T2_COUNTRIES if not ticker_map.get(c)])
    print("\nOutputs:")
    print(" ", PANEL_PATH)
    print(" ", TICKER_MAP_PATH)
    print(" ", PULL_LOG_PATH)


if __name__ == "__main__":
    main()
