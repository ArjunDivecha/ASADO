# ETF LAG STRATEGY RECOMMENDATIONS

Based on the test results from 2026-10-05.

## The Core Finding

| | IC | Interpretation |
|---|------|----------------|
| **Local Index Returns** | **+0.058** | Signal works |
| **ETF Returns (Daily)** | **-0.279** | Signal fails |
| **ETF Gap Closure** | **78% in 5 days** | Mechanical effect |

The combiner predicts local returns correctly, but the ETF lags so severely on daily horizons that the signal appears wrong. This is a **venue mismatch**, not a signal failure.

---

## Strategy Recommendations

### 1. Best: Trade Local Futures (Local Hours)

**Why:** You get direct exposure to the market the combiner was trained on. No lag, no timing mismatch.

**Implementation:**
- **Horizon:** Monthly (matches combiner signal)
- **Entry:** During local trading hours
- **Instrument:** Local index futures

| Country | Exchange | Ticker |
|---------|----------|--------|
| Japan | OSE | NKY |
| Korea | KRX | KOSPI200 |
| Taiwan | SGX | TWN |
| India | NSE/GIFT | NIFTY |
| Australia | ASX | AS50 |

**Expected Edge:** IC ~0.058 (same as local index test)

---

### 2. Acceptable: Hold ETFs Longer (1 Month)

**Why:** The -0.279 daily IC is misleading. The combiner is trained to predict **monthly** returns, not daily. The lag closes within 5 days, but you need the full month to capture the complete signal.

**Implementation:**
- **Horizon:** Monthly (rebalance monthly)
- **Entry:** Any time during the month
- **Instrument:** US-listed country ETFs

**Expected Edge:** IC ~0.058 (but execution costs may eat value)

---

### 3. Satellite: Mechanical Gap Capture

**Why:** After big local moves (>2%), the ETF lags and closes that gap 78% of the time **regardless of the combiner signal**.

**Implementation:**
- **Horizon:** 3-5 days
- **Trigger:** Big local move (>2%) with positive gap
- **Entry:** Buy ETF on big down day if local market was up
- **Exit:** 3-5 days later

**Expected Edge:** 78% win rate on gap closure, but not signal-driven (no alpha, just market microstructure)

---

## What NOT to Do

| Strategy | IC | Verdict |
|----------|-----|---------|
| **ETF trading with combiner (daily)** | **-0.279** | **KILL** |
| Gap prediction (combiner predicts closure) | **-0.006** | **KILL** |

---

## Summary

**Best:** Trade local futures during local hours (direct signal, no lag)
**If you must use ETFs:** Hold for a full month (don't trade daily)
**Satellite:** Big move mechanical capture (signal-agnostic)

**Don't:** Trade ETFs daily with the combiner signal

---

## Files

- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/analysis/etf_lag_test.py`
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/analysis/etf_lag_full_test.py`
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/analysis/etf_lag_combiner_test.py`
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/analysis/etf_lag/` (results)
