"""
=============================================================================
SCRIPT NAME: test_bloomberg_connection.py
=============================================================================

INPUT FILES:
- None

OUTPUT FILES:
- Data/processed/bloomberg_connection_test.xlsx
  (Small sample of sovereign data to verify Bloomberg access works)

VERSION: 1.0
LAST UPDATED: 2026-04-12
AUTHOR: Arjun Divecha / ASADO

DESCRIPTION:
Simple test script to verify Bloomberg connectivity from the ASADO repo
using the OpusBloomberg connection pathway (macOS → Parallels → bbcomm → BBG).

Tests three categories of the data we'll need for the full Bloomberg pull:
  1. Ping — basic connectivity
  2. Reference data — current sovereign CDS spreads (snapshot)
  3. Historical data — US 10Y yield monthly time series (small pull)

PREREQUISITES:
  - Bloomberg Terminal must be open and logged in on Windows (Parallels)
  - Run via the OpusBloomberg conda env:
    conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" python scripts/test_bloomberg_connection.py

DEPENDENCIES:
- blpapi (from OpusBloomberg conda env)
- pandas, openpyxl (from OpusBloomberg conda env)
=============================================================================
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, '/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg')
from bbg import BBG, bloomberg_setup

ASADO_ROOT = '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO'
OUTPUT_DIR = os.path.join(ASADO_ROOT, 'Data', 'processed')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'bloomberg_connection_test.xlsx')


def main():
    print("=" * 70)
    print("  ASADO Bloomberg Connection Test")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # =========================================================================
    # STEP 1: Run bloomberg_setup() — handles bbcomm, port forwarding, etc.
    # =========================================================================
    print("\n[1/4] Running bloomberg_setup()...")
    try:
        vm_ip = bloomberg_setup(verbose=True)
        print(f"  PASS: Connected to VM at {vm_ip}")
    except Exception as e:
        print(f"  FAIL: bloomberg_setup() failed: {e}")
        print("\n  Make sure Bloomberg Terminal is open and logged in on Windows.")
        sys.exit(1)

    # =========================================================================
    # STEP 2: Ping — basic health check
    # =========================================================================
    print("\n[2/4] Ping test (AAPL last price)...")
    try:
        with BBG() as bbg:
            ok = bbg.ping()
            if ok:
                data = bbg.ref("AAPL US Equity", ["PX_LAST", "NAME"])
                print(f"  PASS: {data.get('NAME', 'N/A')} — ${data.get('PX_LAST', 'N/A')}")
            else:
                print("  FAIL: ping() returned False")
                sys.exit(1)
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # =========================================================================
    # STEP 3: Reference data — sovereign CDS spreads (a few countries)
    # =========================================================================
    print("\n[3/4] Sovereign data test (CDS spreads + govt bond yields)...")

    test_tickers = {
        "USGG2YR Index":  "US 2Y Yield",
        "USGG5YR Index":  "US 5Y Yield",
        "USGG10YR Index": "US 10Y Yield",
        "USGG30YR Index": "US 30Y Yield",
        "GDBR10 Index":   "Germany 10Y Yield",
        "GJGB10 Index":   "Japan 10Y Yield",
        "GUKG10 Index":   "UK 10Y Yield",
        "GACGB10 Index":  "Australia 10Y Yield",
        "GCAN10YR Index": "Canada 10Y Yield",
        "GFRN10 Index":   "France 10Y Yield",
    }

    try:
        with BBG() as bbg:
            ref_results = bbg.ref_batch(
                list(test_tickers.keys()),
                ["PX_LAST", "NAME"]
            )

            print(f"  Retrieved {len(ref_results)} tickers:")
            successes = 0
            for ticker, data in ref_results.items():
                label = test_tickers.get(ticker, ticker)
                if "error" in data:
                    print(f"    FAIL  {label}: {data['error']}")
                else:
                    px = data.get("PX_LAST", "N/A")
                    name = data.get("NAME", "N/A")
                    print(f"    OK    {label}: {px}  ({name})")
                    successes += 1

            if successes == 0:
                print("  FAIL: No tickers returned data")
                sys.exit(1)
            else:
                print(f"  PASS: {successes}/{len(test_tickers)} tickers returned data")

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # =========================================================================
    # STEP 4: Historical data — US 10Y yield, monthly, last 2 years
    # =========================================================================
    print("\n[4/4] Historical data test (US 10Y yield, monthly, 2024-2026)...")

    try:
        import pandas as pd

        with BBG() as bbg:
            hist = bbg.hist(
                "USGG10YR Index",
                "PX_LAST",
                "20240101",
                datetime.now().strftime("%Y%m%d"),
                periodicity="MONTHLY"
            )

            if not hist:
                print("  FAIL: No historical data returned")
                sys.exit(1)

            df = pd.DataFrame(hist)
            df["date"] = pd.to_datetime(df["date"])
            df["PX_LAST"] = pd.to_numeric(df["PX_LAST"], errors="coerce")
            df = df.sort_values("date")

            print(f"  Retrieved {len(df)} monthly observations")
            print(f"  Date range: {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
            print(f"  Yield range: {df['PX_LAST'].min():.3f}% to {df['PX_LAST'].max():.3f}%")
            print(f"\n  Last 5 observations:")
            for _, row in df.tail(5).iterrows():
                print(f"    {row['date'].strftime('%Y-%m-%d')}: {row['PX_LAST']:.3f}%")

            # Save to Excel
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
                # Sheet 1: Reference data snapshot
                ref_rows = []
                for ticker, data in ref_results.items():
                    ref_rows.append({
                        "ticker": ticker,
                        "label": test_tickers.get(ticker, ticker),
                        "PX_LAST": data.get("PX_LAST"),
                        "NAME": data.get("NAME"),
                        "error": data.get("error"),
                    })
                pd.DataFrame(ref_rows).to_excel(writer, sheet_name="Reference_Data", index=False)

                # Sheet 2: Historical data
                df.to_excel(writer, sheet_name="US_10Y_Monthly", index=False)

            print(f"\n  Results saved to: {OUTPUT_FILE}")
            print(f"  PASS: Historical data pull works")

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("  ALL TESTS PASSED — Bloomberg connection is working!")
    print("  Ready to build the full ASADO Bloomberg data collector.")
    print("=" * 70)


if __name__ == "__main__":
    main()
