# Execution Reality at IBKR — $100k Retail Scale, 34 US-Listed Country ETFs

**Evidence miner 4 | 2026-07-02 | For the ASADO alpha book (hypothetical account, analysis only)**

Data provenance: 30-day median bid/ask spreads are the official SEC Rule 6c-11 disclosures scraped
directly from iShares.com fund pages (as of Jul 1, 2026) and SSGA's SPY page; AUM and expense
ratios from stockanalysis.com (Jul 2, 2026); ADV is the 3-month average daily dollar volume
computed from Yahoo Finance daily bars through Jul 2, 2026. Raw scraped data:
`etf_stats.jsonl`, `etf_spreads.jsonl`, `ishares_screener.json` in this directory; scrapers:
`fetch_etf_stats.py`, `fetch_spreads.py`, `build_table.py`.

---

## 1. IBKR US Commission Structure (2026)

| Plan | Rate (US stocks/ETFs) | Minimum | Maximum | Notes |
|---|---|---|---|---|
| **IBKR Lite** | $0 | — | — | PFOF routing, no SmartRouting; higher idle-cash haircut (benchmark −1.5%) |
| **IBKR Pro Fixed** | $0.005/share | $1.00/order | 1% of trade value | Exchange fees bundled; SEC/TAF passed through on sells |
| **IBKR Pro Tiered** (≤300k sh/mo) | $0.0035/share | $0.35/order | 1% of trade value | Exchange (~$0.0030/sh take), clearing (~$0.0002/sh), SEC/TAF passed through; rebates possible when adding liquidity |

**Worked numbers for our clip sizes** ($3k–$15k, ETF prices $11–$745):

- $7,500 clip of a $40 ETF (188 sh): Tiered ≈ $0.66 comm + $0.56 exchange + $0.04 clearing ≈ **$1.26 ≈ 1.7 bp**. Fixed ≈ $1.00 (min) ≈ 1.3 bp. Lite $0.
- $3,000 clip of a $40 ETF (75 sh): Tiered ≈ $0.62 ≈ **2.1 bp**; Fixed $1.00 = 3.3 bp; Lite $0.
- High-priced tickers (SPY $745, QQQ ~$713, EWY $180): share counts are tiny, commissions round to the minimums → **0.5–1 bp**.
- Low-priced tickers (EIDO $11.45, VNM $18.49, EWH $20.93): per-share pass-throughs bite — up to **3–6 bp** on tiered when taking liquidity. Posting non-marketable/midpoint SMART orders avoids the take fee and can flip it to a small rebate.

**Verdict for this book: IBKR Pro, Tiered.** Commission is 0.5–2 bp per side at our sizes — trivially small versus spread. What matters is that Pro gets SmartRouting + midpoint/Adaptive order types and no PFOF; on the B/C-tier internationals, midpoint fills routinely recover 25–50% of the quoted spread, which dwarfs the commission saved by Lite. Pro also pays ~1%/yr more on idle cash (benchmark −0.5% vs Lite's benchmark −1.5%). Lite is defensible only for a buy-and-hold sleeve in tier-A mega names.

**Fractional shares:** available on 10,500+ US stocks/ETFs (must be enabled in Client Portal; min trade $0.01, ~$1 minimum commission applies to fractional orders on Pro). Essential here: without fractionals, a $3k clip of QQQ ($713/sh) has 24% position granularity. The fractional component is executed by IBKR internally rather than routed; for the liquid names the cost difference is negligible.

## 2. Per-Ticker Table (sorted by spread)

Spread = official 30-day median bid/ask (SEC 6c-11 methodology, rounded to nearest 0.01% at
source; "0.4/1.0 bp" entries reflect the sub-rounding reality for SPY-class liquidity).
Prem/Disc = closing price vs NAV snapshot (Jul 1, 2026), illustrating fair-value noise, not a
persistent bias. Comm = IBKR Pro tiered all-in commission+exchange+clearing for a $7,500
marketable order. **All-in 1-way (bp) = spread/2 + commission + slippage allowance + SEC fee**
(slippage allowance: 0.5 bp mega / 1 bp tier A / 2 bp tier B / 5 bp tier C).

| Country | Ticker | AUM | ADV ($M/d) | Price | 30d Med Spread (bp) | Prem/Disc % | ER | Tier | Comm (bp, $7.5k) | All-in 1-way (bp) |
|---|---|---|---|---|---|---|---|---|---|---|
| U.S. | SPY | $783.07B | 39,698 | $744.78 | 0.4 | — | 0.09% | A | 0.5 | 1.3 |
| NASDAQ | QQQ | $480.53B | 30,908 | $712.60 | 1.0* | — | 0.18% | A | 0.5 | 1.6 |
| US SmallCap | IWM | $77.46B | 7,870 | $297.58 | 1.0 | 0.04 | 0.19% | A | 0.6 | 1.7 |
| Japan | EWJ | $21.20B | 574 | $93.14 | 1.0 | 1.24 | 0.49% | A | 0.8 | 2.4 |
| Taiwan | EWT | $10.68B | 591 | $104.86 | 1.0 | -0.56 | 0.59% | A | 0.8 | 2.4 |
| Switzerland | EWL | $1.80B | 32 | $63.98 | 2.0 | 0.08 | 0.50% | A | 1.0 | 3.1 |
| Italy | EWI | $672M | 24 | $60.63 | 2.0 | 0.30 | 0.50% | A | 1.1 | 3.2 |
| Korea | EWY | $23.37B | 3,420 | $180.14 | 4.0 | -2.13 | 0.59% | A | 0.6 | 3.2 |
| Canada | EWC | $5.68B | 111 | $57.77 | 2.0 | 0.09 | 0.50% | A | 1.2 | 3.3 |
| ChinaH | MCHI | $6.26B | 168 | $50.91 | 2.0 | 0.44 | 0.59% | A | 1.3 | 3.4 |
| India | INDA | $6.67B | 330 | $49.56 | 2.0 | 0.00 | 0.61% | A | 1.4 | 3.5 |
| U.K. | EWU | $3.66B | 70 | $47.16 | 2.0 | 0.46 | 0.50% | A | 1.4 | 3.5 |
| France | EWQ | $381M | 17 | $45.92 | 2.0 | 0.22 | 0.50% | A | 1.5 | 3.6 |
| Germany | EWG | $1.49B | 62 | $42.31 | 2.0 | 0.14 | 0.49% | A | 1.6 | 3.7 |
| Mexico | EWW | $2.02B | 110 | $75.50 | 4.0 | -0.05 | 0.50% | A | 0.9 | 4.0 |
| Saudi Arabia | KSA | $681M | 19 | $37.38 | 3.0 | 0.37 | 0.75% | A | 1.8 | 4.4 |
| Brazil | EWZ | $9.51B | 973 | $34.43 | 3.0 | 0.03 | 0.59% | A | 1.9 | 4.5 |
| ChinaA | ASHR | $1.65B | 161 | $35.16 | 3.0* | — | 0.65% | A | 1.9 | 4.5 |
| Singapore | EWS | $888M | 25 | $30.16 | 3.0 | -0.05 | 0.50% | A | 2.2 | 4.8 |
| Australia | EWA | $1.40B | 72 | $28.09 | 4.0 | -0.20 | 0.50% | A | 2.4 | 5.5 |
| Malaysia | EWM | $338M | 7.8 | $26.97 | 4.0 | -0.34 | 0.50% | A | 2.5 | 5.6 |
| Hong Kong | EWH | $1.18B | 70 | $20.93 | 5.0 | 0.93 | 0.50% | A | 3.2 | 6.8 |
| Vietnam | VNM | $561M | 12.4 | $18.49 | 5.5* | — | 0.66% | B | 3.6 | 8.5 |
| Poland | EPOL | $706M | 17 | $39.44 | 7.0 | -0.19 | 0.59% | B | 1.7 | 7.3 |
| Sweden | EWD | $310M | 8.0 | $50.48 | 10.0 | 0.15 | 0.51% | B | 1.3 | 8.4 |
| Spain | EWP | $1.75B | 23 | $59.66 | 12.0 | 0.35 | 0.50% | B | 1.1 | 9.2 |
| Netherlands | EWN | $651M | 12.0 | $67.56 | 15.0 | 0.36 | 0.50% | B | 1.0 | 10.6 |
| Indonesia | EIDO | $261M | 18 | $11.45 | 8.0 | 0.62 | 0.59% | B | 5.9 | 12.0 |
| Chile | ECH | $981M | 23 | $39.13 | 16.0 | -0.37 | 0.59% | C | 1.7 | 14.8 |
| Turkey | TUR | $175M | 11.9 | $39.34 | 17.0 | -0.06 | 0.59% | C | 1.7 | 15.3 |
| Thailand | THD | $288M | 8.1 | $71.62 | 19.0 | 0.83 | 0.59% | C | 0.9 | 15.5 |
| Philippines | EPHE | $128M | 2.9 | $24.48 | 20.0 | -0.86 | 0.59% | C | 2.7 | 17.8 |
| Denmark | EDEN | $196M | 0.8 | $114.67 | 26.0 | -0.36 | 0.53% | C | 0.7 | 18.8 |
| South Africa | EZA | $647M | 14.6 | $64.00 | 27.0 | 0.09 | 0.59% | C | 1.0 | 19.6 |

`*` = estimated, not official 6c-11 disclosure: QQQ from Invesco's published 0.00–0.01% (1¢ on
~$713); ASHR from a live 1¢-wide quote on ~$35 (multiple third-party quotes concur); VNM from a
1¢ quote on $18.35 (U.S. News, 06/24/26). All others are the issuer's official 30-day median.

**Notes on the watch-list names:**
- **EDEN is the outlier** — $0.8M/day ADV (30-day avg volume just ~3,700–6,700 sh/day). A $10k order is ~1.25% of ADV. Work it with resting limits over hours; never market orders; a daily-turnover strategy should exclude it.
- **EZA (27 bp) and ECH (16 bp) trade wider than their ADV suggests** ($14.6M and $22.6M/day); their quoted depth is thin even though volume is adequate — patient midpoint orders recover a lot here.
- **EPHE** ($2.9M/day) and **THD/TUR/EWD** ($8–12M/day) are volume-thin but fine at our size (<0.15% of ADV); the cost is the spread, not impact.
- **KSA, ASHR, VNM, EWM, EPOL** — often assumed illiquid — are actually tier A/B now (KSA 3 bp official; EPOL 7 bp; EWM 4 bp).
- Surprises vs stale priors: **EWI/EWQ/EWP tightened** (2/2/12 bp); **EWY** is a monster ($3.4B/day) after Korea's re-rating; **EWN at 15 bp** is the widest of the developed-Europe set.

## 3. Execution Tactics for International ETFs at Retail Size

1. **Never use market orders on anything below mega-tier.** Default = **marketable limit** (limit at NBBO offer, or offer +1¢) or IBKR **Adaptive** orders; for B/C tier use a **midpoint peg (SMART)** and accept minutes of latency — recovering half the spread on a 20 bp name is worth 10 bp, ~10x the commission.
2. **Time of day.** Avoid the first 15–30 minutes (spreads 2–5x wider, iNAV not yet meaningful) and the last-minute scramble. For **European ETFs** the tightest window is ~9:45–11:30 ET while the home market is still open (Europe closes ~11:30 ET); after that, spreads widen and price discovery moves to the ETF itself. For **Asia ETFs** the home market is *always* closed during US hours — market makers hedge with index futures/ADRs/FX, so spreads are structurally wider but stable; mid-day (11:00–15:00 ET) is fine. **Americas ETFs** (EWC, EWW, EWZ, ECH) overlap all day.
3. **MOC/LOC auctions are the natural default for daily-rebalance strategies.** The 4pm close is the deepest liquidity event, the fill *is* the official close (matching close-to-close backtest assumptions in the ASADO harness), and closing-auction spread cost is near zero for tier A. For tier C names use **LOC with a limit band** rather than MOC — closing auctions in EDEN/EPHE can be thin — and expect occasional partial fills.
4. **Premium/discount awareness.** When the home market is closed, the ETF price is the market's live estimate of fair value and the published NAV/iNAV is stale (iNAV for Asia funds ticks only on FX during US hours). The Jul 1 snapshot shows ±0.3–1.2% prem/disc across the set and **EWY at −2.13%** — on fair-value-NAV days these gaps are mostly NAV-timing artifacts, but *entering on a rich premium and exiting on a discount is a real, avoidable ~50–100 bp round-trip tax on Asia names in volatile weeks*. Practical retail check before a large clip: compare the ETF's move to the relevant index future/proxy (NKY, KOSPI200, FTSE China A50, MSCI Taiwan futures) rather than trusting iNAV.
5. **Clip sizing:** at $3–10k every name except EDEN is <0.35% of ADV — impact is negligible; the spread is the whole game. Don't slice orders; one midpoint-pegged or marketable-limit order is correct at this scale.

## 4. Practical Frictions

- **SEC Section 31 fee (sells only):** $20.60 per $1M effective Apr 4, 2026 → **0.206 bp on sells** (~0.1 bp per side averaged). **FINRA TAF:** $0.000195/sh on sells (≈$0.04 on a typical clip) — negligible.
- **No stamp duty / FTT** on US-listed ETFs (unlike UK/HK/local lines). All 34 tickers are US-listed — one of the strongest arguments for this implementation.
- **Idle cash interest (IBKR):** benchmark-linked — **Pro: BM −0.5%, Lite: BM −1.5%** on USD balances **above $10,000; the first $10k earns zero**. Full published rate requires NAV ≥ $100k (prorated below). Mid-2026 quoted Pro USD rate ≈ **3.1–3.8%** (sources conflict on the exact print; IBKR's rate page blocks scraping — treat as ~benchmark −0.5%). Design note: model cash yield as `(BM − 0.5%) × max(0, cash − $10k)/cash`; a 30%-cash defensive stance earns roughly ⅔ of the published rate on its cash sleeve.
- **Pattern-day-trader rule:** applies to margin accounts with **< $25k equity**; a $100k account is comfortably exempt — unlimited day trades. Use a margin-type account (even at zero leverage) so T+1 settlement never blocks re-entry; a *cash* account would impose settled-funds waits.
- **Taxes (one line):** holds < 1 year are short-term gains taxed as ordinary income, so a high-turnover version of this book is materially less efficient in a taxable account than in an IRA.

## 5. Cost Inputs for Strategy Design (the deliverable)

Realistic **all-in one-way** cost, $3–10k clips, IBKR Pro tiered, disciplined execution
(marketable-limit / midpoint / MOC, mid-session), including half-spread + commission&fees +
slippage:

| Tier | Names | Realistic range | **Design input (use this)** |
|---|---|---|---|
| A-mega | SPY, QQQ, IWM, EWJ, EWT, EWY | 1.3–3.2 bp | **3 bp** |
| A | EWC MCHI INDA EWU EWQ EWG EWI EWL EWW EWZ ASHR KSA EWS EWA EWM EWH | 3.1–6.8 bp | **5 bp** |
| B | EPOL VNM EWD EWP EWN EIDO | 7.3–12.0 bp | **10 bp** |
| C | ECH TUR THD EPHE EDEN EZA | 14.8–19.6 bp | **20 bp** |
| D | none (no ticker exceeds 40 bp) | — | — |

**Implications against the harness cost grid** (12 signals clear 5 bp, 4 clear 10 bp, none at 25 bp):
- **Daily-turnover strategies are viable only inside the 22 tier-A names** (5 bp world). That set covers most combiner-relevant liquidity and 6 of the "mega" names at ~3 bp.
- **Tier B can carry weekly-or-slower rebalancing** (10 bp one-way amortized over ≥5 days ≈ ≤2 bp/day).
- **Tier C is reserved for slow signals** — 21-day holds (SOV_2S10S class) and event-driven entries (downgrade/CDS-inversion drift), where 20 bp one-way ≈ 1 bp/day. **EDEN additionally has a capacity/patience constraint** (work orders, LOC not MOC); exclude it from anything faster than monthly.
- Turnover budget context: a daily strategy running 20% one-way turnover/day confined to tier A at 4 bp costs ≈ 2.0% NAV/yr; the same turnover in tier C would cost ≈ 10%/yr — fatal. Cost-aware universe selection is worth more than commission-plan selection by an order of magnitude.

## Sources

- IBKR pricing: [interactivebrokers.com commissions-stocks](https://www.interactivebrokers.com/en/pricing/commissions-stocks.php) (page blocks scraping; rates cross-confirmed via [BrokerChooser](https://brokerchooser.com/broker-reviews/interactive-brokers-review/interactive-brokers-fees), [The Poor Swiss](https://thepoorswiss.com/ib-fixed-or-tiered-pricing/), [MatchMyBroker](https://www.matchmybroker.com/articles/ibkr-fixed-vs-tiered-pricing-a-complete-fee-analysis))
- IBKR Lite vs Pro routing/PFOF: [BrokerChooser execution](https://brokerchooser.com/education/investing/interactive-brokers-order-execution), [IBKR Lite](https://www.interactivebrokers.com/en/trading/why-ibkr-lite.php)
- Fractional shares: [IBKR fractional trading](https://www.interactivebrokers.com/en/trading/fractional-trading.php)
- Cash interest: [IBKR interest rates](https://www.interactivebrokers.com/en/accounts/fees/pricing-interest-rates.php), [BrokerChooser USD cash interest](https://brokerchooser.com/invest-long-term/learn/USD-cash-interest-at-interactive-brokers), [TradersUnion](https://tradersunion.com/brokers/fond/view/interactive_brokers/cash-interest-rates/)
- SEC Section 31 FY2026: [SEC fee-rate advisory](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2), [FINRA notice](https://www.finra.org/rules-guidance/notices/information-notice-20260317); FINRA TAF: [FINRA TAF FAQ](https://www.finra.org/rules-guidance/guidance/faqs/trading-activity-fee)
- Spreads/volumes: iShares.com product pages (30 funds, scraped Jul 2, 2026; spread as-of Jul 1, 2026), [SSGA SPY](https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-500-etf-trust-spy), [U.S. News VNM](https://money.usnews.com/funds/etfs/miscellaneous-region/vaneck-vietnam-etf/vnm), Yahoo Finance chart API (3-mo ADV), stockanalysis.com (AUM/ER)
