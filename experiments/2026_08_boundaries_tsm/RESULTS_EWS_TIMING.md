# EWS composite / diffusion as a timing overlay on the live T2 Fuzzy strategy

**Run:** 2026-08-08 · **Artifacts:** `results/ews_timing.xlsx`, `results/ews_timing.json`
**Script:** `run_ews_timing.py` · Returns GROSS, no cost/turnover penalty (25bp law retracted)

**Verdict depends entirely on the objective, and the first version of this document got that
wrong. On ABSOLUTE return/drawdown the overlay is good. Measured against a fully-invested
equal-weight benchmark — the house convention — it is NEGATIVE. See §0.**

---

## 0. CORRECTION (2026-08-08, after Arjun asked "total or relative returns?")

The original write-up showed portfolio Sharpe 0.81→1.01 AND net Sharpe 0.96→1.04 in one
table, implying a single rule delivered both. **It does not.** Those are two different trades:

| # | Implementation | Result |
|---|---|---|
| 1 | **Total returns**, halve the book to cash | Sharpe 0.75 → **1.00**, maxDD −62.7% → **−40.0%** |
| 2 | **Relative returns**, stay fully invested, halve the ACTIVE bets | IR 0.95 → **1.04**, rel-DD −18.1% → −14.0% |
| 3 | **Halve to cash, measured vs a FULLY-INVESTED benchmark** *(not originally shown)* | IR 0.95 → **0.83**, TE 8.2% → 8.7%, rel-DD −18.1% → **−26.0%** |

Row 3 is what actually happens if the book de-risks and the benchmark does not — and it is
**worse on every relative measure**. Worst 12-month relative stretch goes from −8.3% to
**−14.3%**, over the twelve months ending 2010-02: de-risked straight through the 2009 rebound.

**Because the house convention reports every backtest against equal-weight, row 3 is the
number that should have led.** The overlay is attractive only under an ABSOLUTE-return
objective. Under a relative mandate it is a bet against the market that lost.

Rows 1 and 2 below stand as computed; the error was presentational — combining them as though
one rule produced both — and it flattered the result.

---

## Why this test is valid where the Shiller one was not

The Shiller attempt needed a 10-year valuation lookback, which started the sample in 2010 and
contained **no crash**; even a 5-year window left only one. The EWS panel is monthly back to
1964, so across the T2 strategy's whole life it covers **three** episodes: dot-com (33
months), GFC (24), COVID (12). That is the entire reason this test can answer the question.

Alignment: EWS is stamped month-end, T2 first-of-month holding that month's return, so an EWS
reading at the end of month M is mapped to the T2 return of month M+1 — a genuine one-month
gap. `composite_pctile` verified point-in-time (correlates 0.9998 with an expanding rank vs
0.9802 with a full-sample rank). The `hindsight` column was deliberately not used.

## Every rule tested improves both Sharpe and drawdown

| Rule (50% weight when in alarm) | % months de-risked | Portfolio Sharpe | Portfolio max DD | **Alpha (net) Sharpe** |
|---|---|---|---|---|
| diffusion ≥ 0.30 | 24% | 0.81 → **1.01** | −62.7% → **−40.0%** | 0.96 → **1.04** |
| composite_pctile ≥ 0.67 | 28% | 0.81 → **1.00** | −62.7% → **−39.5%** | 0.96 → **1.05** |
| state ≠ IN | 34% | 0.81 → 0.96 | −62.7% → −39.5% | 0.96 → 1.01 |
| composite_pctile ≥ 0.80 | 16% | 0.81 → 0.95 | −62.7% → −46.7% | 0.96 → 1.04 |
| diffusion ≥ 0.20 | 30% | 0.81 → 0.98 | −62.7% → −40.0% | 0.96 → 1.01 |

**All ten variants improve both metrics**, and robustness across two thresholds per signal is
itself reassuring — this is not one cherry-picked cut. Critically, **the alpha improves too**
(net Sharpe 0.96 → 1.01–1.05), which the Shiller version never managed (it made alpha worse).

### House-convention backtest, gross, vs equal-weight (rule: diffusion ≥ 0.30)

| Window | EW bench | T2 base | T2 scaled | base − EW | scaled − EW | base Sharpe | scaled Sharpe | base DD | scaled DD |
|---|---|---|---|---|---|---|---|---|---|
| Full | 7.6% | 15.6% | 16.1% | +8.1% | **+8.5%** | 0.75 | **1.00** | −62.7% | **−40.0%** |
| 5y | 9.8% | 15.4% | 16.7% | +5.6% | **+6.9%** | 0.96 | **1.13** | −18.4% | **−11.9%** |
| 3y | 15.6% | 18.8% | 17.9% | +3.2% | +2.3% | 1.39 | 1.33 | −7.6% | −7.6% |
| 1y | 25.8% | 41.9% | 41.9% | +16.1% | +16.1% | 2.50 | 2.50 | −7.6% | −7.6% |

24% of months de-risked, 23 switches over 316 months — a slow overlay, not a trading signal.
**It adds nothing in the last 3 years** (it has barely fired), so the gain is concentrated in
stressed periods, which is what it is for.

## The mechanism is volatility, not return prediction

| Signal | Calm-tercile vol | Alarm-tercile vol |
|---|---|---|
| composite | 15.4% | **28.3%** |
| diffusion | 15.7% | **25.7%** |
| equal-weight benchmark | 13.6% | **24.0%** |

Volatility roughly **doubles** in alarm states. Meanwhile every return regression is
**statistically insignificant** (t between −0.54 and −1.23). So the EWS is not predicting
losses — it is identifying high-volatility regimes, and the Sharpe gain comes from not being
fully exposed in them. That is precisely what vol-scaling is supposed to do, and it is a more
defensible mechanism than return prediction.

## Benefit is spread across episodes, not driven by one

| Episode | Base max DD | Scaled max DD |
|---|---|---|
| dot-com 2000-02 | −33.5% | **−17.3%** |
| GFC 2008-09 | −52.6% | **−29.2%** |
| COVID 2020 | −21.2% | **−14.5%** |
| **All other 247 months** | −21.7% | **−17.8%** |

Contrast the Shiller rule, whose non-crisis effect was **exactly zero** (−21.7% → −21.7%).
This one helps in all three episodes *and* outside them.

## Did it warn in advance? Partly — and the failure is informative

- **GFC:** flipped to **OUT in December 2007**, ~9 months before the September 2008 collapse.
  Consistent with the *Market Top* record's "leads by ~9–12 months".
- **COVID:** **no warning at all** — Oct/Nov/Dec 2019 all read IN with percentile 0.39–0.41.
  The COVID benefit therefore came from de-risking *during* the drawdown, not before it.

That failure is the honest shape of the tool: it detects **built-up financial fragility**, not
exogenous shocks. Nobody should expect it to see a pandemic.

## THE CAVEAT THAT MATTERS: this is in-sample

The EWS's 12 signals were **selected and calibrated on these very episodes** — the *Market
Top* record describes "6/6 events caught at calibrated 0.80 pctile". So a test of the EWS
against the same crashes is not an out-of-sample test of the EWS, and some of the drawdown
improvement reflects that fitting.

Two partial defences, neither decisive:
1. The **application is new**. The EWS was built to time US market tops; nothing in its
   construction saw the T2 country strategy's returns. The mapping being tested here is novel
   even though the crash dates are not.
2. The result is **robust to threshold and signal choice** (all ten variants), which is less
   consistent with a knife-edge fit.

The genuinely unforeseen event in the sample — COVID — got **no advance warning**, which is
the most honest available read on what the signal does when it has not been fitted.

## Recommendation

Worth taking seriously, and clearly better than the Shiller-extremeness idea, but **do not
size it off this backtest**. The credible next step is a **forward paper track**: log the rule's
weight monthly alongside the live book and compare after 12–18 months. That is the only way to
get an honest out-of-sample read given the EWS was calibrated on the historical crashes.

Second-best, if a decision is needed sooner: test the same rules on the **pre-2000 EWS
history** against a proxy equity book, where the T2 strategy did not exist — still not clean
(the EWS saw those crashes too) but it adds episodes.

---

## §0b. IT IS PURE BETA TIMING — it has nothing to do with the T2 strategy

Arjun's question: "is this just a beta strategy, i.e. it has NOTHING to do with my strategy,
and would deliver similar improvement to an SPX long-only?" **Yes. Tested and confirmed.**

Same rule (diffusion ≥ 0.30 → half weight), same period 2000-04 → 2026-07:

| Applied to | ΔSharpe | ΔMax drawdown |
|---|---|---|
| T2 Fuzzy (the strategy) | +0.24 | +22.6pp |
| Equal-weight 34-country | +0.20 | +22.0pp |
| **S&P 500 long-only** | **+0.22** | **+20.0pp** |

And standalone on **66 years** of SPX (1960-02 → 2026-07): Sharpe 0.52 → 0.64,
max drawdown −52.6% → −32.6%, de-risked 27% of months.

T2's beta to SPX is **1.06**, so halving the book removes ~0.53 units of market beta. That is
the entire mechanism.

**This was structurally inevitable and should have been anticipated before running it.** The
rule multiplies the whole book by a scalar. It cannot change which countries are held or their
relative weights; the only thing it can do to active return is SHRINK it. There was never a
mechanism by which it could improve selection, so any improvement was always going to be beta.

It also explains §0 row 3: measured against a fully-invested benchmark, removing beta must
look bad, because the benchmark keeps the beta you gave up.

### Consequences

1. **Not a T2 improvement — a separate asset-allocation decision.** "Half my equity exposure
   in cash when the EWS flashes" is independent of "which countries do I own".
2. **If the exposure timing is wanted, implement it on SPY/futures**, not by shrinking the
   country book — same benefit, cheaper, and it leaves the alpha engine at full size. Halving
   T2 halves the active return for no compensating gain.
3. **The one non-beta use left** is scaling ACTIVE risk rather than total exposure (§0 row 2,
   IR 0.95 → 1.04). That never bets against the market, so it cannot be dismissed as beta
   timing — the only variant worth further work under a relative mandate, and so far tested
   only in passing.
