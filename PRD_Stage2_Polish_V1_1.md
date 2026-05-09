# PRD: Stage 2 Calibration & Naming Pass
## ASADO — Stage 2 Polish (V1.1)

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Date** | 2026-05-09 |
| **Author** | Arjun Divecha (with Claude) |
| **Status** | Draft for review |
| **Depends on** | Stage 2 V1 (shipped 2026-05-08) plus Fixes 1–4 (Kalshi URL, strict resolver, orderbook parser, validate-only mode, optional auth) |
| **Companion to** | `PRD_Stage2_Prediction_Markets.md`, `config/predmkt_curated.yaml` |
| **Estimated effort** | 3–4 hours total |

---

## 1. Context

Stage 2 V1 plus the four URL/resolver/orderbook/auth fixes shipped yesterday. End-to-end verification confirmed the data is real: 16 markets resolved, probabilities reflect actual market consensus, MCP tools return correct titles, 38 country/signal combinations materialized. The data layer is no longer fictitious.

Five small items remain. None block use, but each pollutes interpretation in a way that compounds the longer the system runs without correction. Better to fix now than to retrofit a month of accumulated daily snapshots later.

The five items, in rough order of impact:

1. **Stale flag is too aggressive on Kalshi.** All three Kalshi markets show `is_stale=True` despite having tight bid/ask spreads and large book depth. The macro signals (`fed_cut_count_expectation`, `cpi_nowcast_yoy_next`, etc.) are returning empty as a result.
2. **Effectively-resolved markets dominate composites.** Russia-Ukraine ceasefire markets at probability 1.000 with thin/missing asks are flooding into `regional_conflict_premium_eastern_europe` (0.9995) and the Poland country composite (+0.49).
3. **Elasticity sign errors** on Russia-Ukraine ceasefire markets — Poland and Turkey have positive signs (saying "ceasefire is bad") when intuitively ceasefire reduces regional risk premium for both.
4. **`tariff_intensity_by_country` is fed by a tariff-resolution market**, so high signal value means agreement-likely, opposite of what the name implies.
5. **`predmkt_country_risk_composite` is named backwards** — positive values currently mean "implied spillover is good for this country," which contradicts the name "risk."

---

## 2. Goals and Non-Goals

### Goals

- **G1.** Stale flag respects book quality — markets with tight bid/ask and meaningful depth are not flagged stale even when no recent trades print.
- **G2.** Composites exclude effectively-resolved markets — `value ≥ 0.99 or ≤ 0.01` with one-sided book is treated as settled and dropped from composite computation.
- **G3.** Russia-Ukraine ceasefire elasticity signs corrected for Poland and Turkey.
- **G4.** Two to three tariff-escalation markets curated into the registry so `tariff_intensity_by_country` matches its name.
- **G5.** `predmkt_country_risk_composite` redefined so positive values = bad outcome for the country (matches name); `predmkt_country_opportunity_composite` keeps current semantics.

### Non-Goals

- **NG1.** No new MCP tools.
- **NG2.** No schema changes (table columns stay identical).
- **NG3.** No new platforms beyond Kalshi + Polymarket.
- **NG4.** No changes to the strict-resolver, validate-only mode, or auth wiring shipped yesterday — those are working correctly.
- **NG5.** No backfill of historical snapshots. Composite signals computed before this PR will reflect the old definitions; documented at the date of the change rather than rewritten.

---

## 3. Item A — Stale flag heuristic (book-aware)

### Current behavior

In `scripts/build_predmkt_panel.py` `_infer_stale`:

```python
def _infer_stale(platform, probability, last_traded_price, last_traded_ts, volume_24h):
    threshold = LIQUIDITY_THRESHOLD.get(platform, 500.0)
    no_flow = (volume_24h or 0.0) < threshold
    old_trade = True
    if last_traded_ts:
        old_trade = (datetime.now(timezone.utc) - last_traded_ts) > timedelta(hours=24)
    large_gap = False
    if probability is not None and last_traded_price is not None:
        large_gap = abs(last_traded_price - probability) > 0.05
    return bool(no_flow or old_trade or large_gap)
```

The `old_trade` check defaults to `True` when `last_traded_ts` is None. Macro markets with healthy resting orders but no recent prints all flag stale. This zeroes out their contribution to composites because the signal computation downweights stale markets to zero.

### Target behavior

Add a "live book" override: a market is *not* stale if both bid and ask exist AND the bid-ask spread is reasonable, regardless of `last_traded_ts`.

### Code diff

In `_infer_stale`, change the signature and logic to accept book quality as additional inputs:

```python
def _infer_stale(
    platform: str,
    probability: Optional[float],
    last_traded_price: Optional[float],
    last_traded_ts: Optional[datetime],
    volume_24h: Optional[float],
    bid: Optional[float] = None,
    ask: Optional[float] = None,
) -> bool:
    """
    A market is stale if AT LEAST ONE of:
      - 24h volume below platform threshold AND no live two-sided book
      - last_traded_ts older than 24h AND no live two-sided book
      - last_traded_price diverges from quoted mid by > 5%

    A "live two-sided book" overrides the volume/recency checks because
    actively-quoted macro markets often go hours between prints while
    the book stays tight (KXRATECUT-26DEC31 is the canonical example —
    $11M depth, 80bps spread, no recent trade because it's a long-dated
    market with patient liquidity providers).
    """
    threshold = LIQUIDITY_THRESHOLD.get(platform, 500.0)
    no_flow = (volume_24h or 0.0) < threshold

    old_trade = True
    if last_traded_ts:
        old_trade = (datetime.now(timezone.utc) - last_traded_ts) > timedelta(hours=24)

    # Live book override: both sides quoted with spread <= 5% of midpoint
    has_live_book = (
        bid is not None and ask is not None
        and bid > 0 and ask > 0 and ask > bid
        and (ask - bid) <= 0.05
    )

    if has_live_book:
        no_flow = False
        old_trade = False

    large_gap = False
    if probability is not None and last_traded_price is not None:
        large_gap = abs(last_traded_price - probability) > 0.05

    return bool(no_flow or old_trade or large_gap)
```

Update both call sites in `_pull_kalshi_market` and `_pull_polymarket_market` to pass `bid` and `ask`:

```python
# In _pull_kalshi_market, both YES and NO blocks:
stale_yes = _infer_stale("kalshi", prob_yes, last_yes, last_trade_ts, volume_24h,
                         bid=bid_yes, ask=ask_yes)
# ...
stale_no = _infer_stale("kalshi", prob_no, last_no, last_trade_ts, volume_24h,
                        bid=bid_no, ask=ask_no)

# In _pull_polymarket_market:
stale = _infer_stale("polymarket", probability, last_price, last_trade_ts, volume_24h,
                     bid=bid, ask=ask)
```

### Validation

After applying:

```sql
SELECT market_id, ROUND(bid,3), ROUND(ask,3), ROUND(ask-bid,3) AS spread,
       liquidity_usd, is_stale
FROM predmkt_daily
WHERE platform='kalshi'
  AND snapshot_date = (SELECT MAX(snapshot_date) FROM predmkt_daily);
```

Expected: `KXRATECUT-26DEC31` (spread 0.008, liquidity $11M) should now show `is_stale=False`. `KXCPI-26MAY-T1.0` (spread 0.010) should be False. `KXCPI-26MAY-T-0.2` (one-sided book, ask=NaN) should remain True.

The MCP smoke test should now populate previously-empty signals:

```python
predmkt_snapshot(category='cpi')          # should return both Kalshi CPI markets
predmkt_snapshot(category='fed_policy')   # should include KXRATECUT-26DEC31
```

And in the composites, `fed_cut_count_expectation` and `cpi_nowcast_yoy_next` should appear (currently missing because all constituent Kalshi markets are downweighted to zero).

---

## 4. Item B — Effectively-resolved market filter

### Current behavior

The Russia-Ukraine ceasefire markets (`0xa93b...` and `0xe546...`) show `probability=1.000`, `bid=0.001`, `ask=NaN`. These are markets that have effectively settled YES — someone is paying $0.001 for shares that no one will sell, because YES paid out at $1.00. The Polymarket `closed` flag may not be set yet (resolution hasn't been finalized administratively) but the market is no longer providing forward-looking signal.

These markets currently flow into:
- `regional_conflict_premium_eastern_europe = 0.9995` (almost entirely from the two ceasefire markets at 1.0)
- `predmkt_country_risk_composite[Poland] = +0.486` (driven by these markets × elasticity)

### Target behavior

Mark markets with `probability ≥ 0.99 or ≤ 0.01` AND a one-sided or absent ask as `is_settled_effective=True`. These are dropped from composite signal computation but still recorded in `predmkt_daily` for historical reference.

### Code diff

In `_pull_kalshi_market` and `_pull_polymarket_market`, add a new boolean column `is_settled_effective` to each daily row (this will require a one-line schema migration to add the column):

```python
# Helper at module level:
def _is_settled_effective(
    probability: Optional[float],
    bid: Optional[float],
    ask: Optional[float],
) -> bool:
    """
    A market is effectively settled when probability is at the rail (≤0.01 or ≥0.99)
    AND the book is one-sided (only bids on the winning side, no asks).
    Distinct from is_resolved: the API may not have flagged the market resolved yet
    even though the trading is effectively done.
    """
    if probability is None:
        return False
    at_rail = probability >= 0.99 or probability <= 0.01
    one_sided = (ask is None) or (bid is None)
    return at_rail and one_sided
```

Then in each row construction, add the field:

```python
# Existing row dict, add one new key:
{
    ...
    "is_stale": stale,
    "is_resolved": is_resolved,
    "is_settled_effective": _is_settled_effective(prob_yes, bid_yes, ask_yes),
    ...
}
```

Schema migration in `_create_tables`:

```python
con.execute("""
    CREATE TABLE IF NOT EXISTS predmkt_daily (
        ...
        is_stale BOOLEAN,
        is_resolved BOOLEAN,
        is_settled_effective BOOLEAN,  -- NEW
        resolution_value DOUBLE,
        PRIMARY KEY (snapshot_date, platform, market_id, outcome_id)
    )
""")
# For existing tables, also run:
try:
    con.execute("ALTER TABLE predmkt_daily ADD COLUMN is_settled_effective BOOLEAN DEFAULT FALSE")
except Exception:
    pass  # column already exists
```

Then in `_compute_signals`, filter settled-effective rows out of the primary outcome set:

```python
# In _primary_outcome_rows, after the merge:
merged = merged[~merged["is_settled_effective"].fillna(False)]
```

### Validation

After applying, with the Russia-Ukraine ceasefire markets still in the registry:

```sql
SELECT market_id, probability, is_settled_effective
FROM predmkt_daily
WHERE platform='polymarket' AND market_id LIKE '0xa93b%' OR market_id LIKE '0xe546%';
```

Expected: both rows show `is_settled_effective=True`.

```sql
SELECT signal_name, value FROM predmkt_signals_daily
WHERE signal_name IN ('regional_conflict_premium_eastern_europe',
                      'predmkt_country_risk_composite')
  AND country IN ('__GLOBAL__', 'Poland');
```

Expected: the regional premium drops from 0.9995 to whatever it would be without these markets (likely 0 if these are the only EE markets), and Poland's risk composite drops from +0.49 to a small number.

---

## 5. Item C — Elasticity sign correction

### Current state

In `config/predmkt_curated.yaml`, Russia-Ukraine ceasefire markets have these spillover entries:

```yaml
# Both ceasefire markets (May 31 and June 30)
spillover_countries:
  - country: Germany
    elasticity: -0.30   # ceasefire helps Germany ✓ correct
    channel: trade_partner
  - country: Poland
    elasticity: +0.50   # WRONG — ceasefire helps Poland (regional stability)
    channel: regional_proximity
  - country: Turkey
    elasticity: +0.20   # WRONG — ceasefire helps Turkey (regional stability)
    channel: regional_proxy
```

Convention reminder: elasticity sign captures "the direction this country's equity moves when YES resolves at 1.0 vs 0.0." Positive elasticity = "YES outcome lifts equity." Russia-Ukraine ceasefire (YES = peace) should help Poland (less defense spend pressure, more trade) and Turkey (regional stability premium decline).

### Target state

Flip the signs on Poland and Turkey for both ceasefire markets:

```yaml
- country: Poland
  elasticity: -0.50
  channel: regional_proximity
- country: Turkey
  elasticity: -0.20
  channel: regional_proxy
```

Apply to both `0xa93b28a6...` and `0xe546672750...` entries.

### Validation

After updating YAML and re-running the snapshot:

```sql
SELECT country, ROUND("value",4) FROM predmkt_signals_daily
WHERE signal_name='predmkt_country_risk_composite' AND country IN ('Poland', 'Turkey')
  AND snapshot_date=(SELECT MAX(snapshot_date) FROM predmkt_signals_daily);
```

Expected: Poland and Turkey show negative or near-zero values now (assuming Item B excluded the settled markets). If Item B is *not* applied first, signs flip from large positive to large negative for these countries, which itself is informative validation that the elasticity correction worked.

---

## 6. Item D — Curate tariff-escalation markets

### Current state

The registry has one tariff market:

```yaml
- platform: polymarket
  market_id: "0x2e17fe4fd80ffaa342b1ce15d59e56c0347a90422d90e6345048be78e1963b17"
  slug: us-x-china-tariff-agreement-by-may-31
  asado_category: tariff
  asado_subcategory: us_china_tariff_agreement
```

This is a *resolution* market — YES means "agreement reached." A high YES probability flowing into `tariff_intensity_by_country` produces a high reading, but that reading actually means "tariffs likely to be resolved." Semantics are inverted.

### Target state

Add 2–3 markets where YES = escalation. Candidate search queries against Polymarket Gamma API:

```python
# Query suggestions for the curator:
for query in ['tariff increase', 'tariff escalation', 'new tariffs',
              'tariff hike', 'china tariff increase', 'reciprocal tariff']:
    r = requests.get('https://gamma-api.polymarket.com/markets',
                     params={'limit': 10, 'closed':'false','active':'true',
                             'order':'volume24hr','ascending':'false'})
    # Filter results for the query terms
```

Expected to find markets like:
- "Will Trump impose new tariffs on China by [date]?"
- "Will [country] tariffs increase by [date]?"
- "Will the US implement reciprocal tariffs by [date]?"

For each market the curator picks, write a YAML entry following the existing pattern. Spillover graph for an escalation market should reflect:

```yaml
- platform: polymarket
  market_id: "0x..."  # real condition_id
  slug: ...
  asado_category: tariff
  asado_subcategory: tariff_escalation_<descriptor>
  contract_type: binary
  resolution_clarity: high
  resolution_source: "Official tariff implementation announcements"
  spillover_countries:
    - country: ChinaA
      elasticity: +0.55     # escalation hurts China = positive elasticity since YES = bad for China
      channel: trade_partner
      confidence: high
    - country: Mexico
      elasticity: +0.30     # if US-broad tariffs, hurts Mexico (USMCA-adjacent)
      channel: trade_partner
      confidence: medium
    - country: Taiwan
      elasticity: +0.25     # escalation likely accelerates supply-chain disruption
      channel: tech_supply_chain
      confidence: medium
```

Note the elasticity sign convention: tariff *escalation* market has YES = escalation = bad for the trade partner = positive elasticity. The existing tariff *agreement* market has the opposite — YES = agreement = good for ChinaA = negative elasticity. After this curation, both market types will live in the registry side by side, with opposite elasticity signs reflecting their opposite meanings.

The signal `tariff_intensity_by_country` will then weighted-average across both market types, naturally combining "probability of escalation" (positive contribution to tariff_intensity) with "1 minus probability of resolution" (also positive contribution). The signal name then matches its computation.

### Optional cleanup

If the resolution-market `0x2e17...` is kept in the registry, consider renaming its `asado_subcategory` to clarify direction:

```yaml
asado_subcategory: us_china_tariff_resolution_prob   # (was: us_china_tariff_agreement)
```

This makes it explicit when querying the registry.

### Validation

```sql
SELECT m.title, m.asado_subcategory, ROUND(d.probability, 3)
FROM predmkt_daily d
JOIN predmkt_market_meta m USING (platform, market_id)
WHERE m.asado_category='tariff' AND d.snapshot_date=(SELECT MAX(snapshot_date) FROM predmkt_daily)
  AND d.outcome_id NOT LIKE '%NO%';
```

Expected: 3–4 markets, mix of resolution and escalation subcategories. The composite signal:

```sql
SELECT country, ROUND("value", 3) FROM predmkt_signals_daily
WHERE signal_name='tariff_intensity_by_country'
  AND snapshot_date=(SELECT MAX(snapshot_date) FROM predmkt_signals_daily);
```

Expected: ChinaA, Mexico, Taiwan with values that reflect a blend of escalation probability and 1-minus-resolution probability, weighted by liquidity.

---

## 7. Item E — Composite signal naming and semantics

### Current state

In `_compute_signals`, the country-level composite is computed as:

```python
country_join["signed_effect"] = (
    country_join["probability"]
    * country_join["elasticity"].fillna(0.0)
    * country_join["effective_weight"]
)
# Then:
risk_value = float(grp["signed_effect"].sum() / liq_sum)
append_signal("predmkt_country_risk_composite", risk_value, ...)
append_signal("predmkt_country_opportunity_composite", -risk_value, ...)
```

So `risk_composite = signed_effect`, where positive `signed_effect` means "the spillover-weighted equity move is positive" (good for the country). The name "risk" implies the opposite. `opportunity_composite` is just `-1 × risk_composite`, a redundant inverse.

### Target state

Flip the sign convention so the names match intuition:

- **`predmkt_country_risk_composite`** — positive values = implied spillover is *bad* for the country (high risk).
- **`predmkt_country_opportunity_composite`** — positive values = implied spillover is *good* for the country (high opportunity).

Mathematically this is just a sign flip on `risk_composite`:

```python
# Replace:
risk_value = float(grp["signed_effect"].sum() / liq_sum)
append_signal("predmkt_country_risk_composite", risk_value, ...)
append_signal("predmkt_country_opportunity_composite", -risk_value, ...)

# With:
expected_effect = float(grp["signed_effect"].sum() / liq_sum)
append_signal("predmkt_country_risk_composite", -expected_effect, ...)        # flip sign
append_signal("predmkt_country_opportunity_composite", expected_effect, ...)  # keep sign
```

### Documentation

Update the docstring in `_compute_signals`:

```python
"""
predmkt_country_risk_composite: spillover-weighted IMPLIED downside.
  Positive values mean: probabilities × elasticities (in their native
  "YES-outcome moves equity" convention) sum to NEGATIVE, i.e., the
  market is pricing outcomes that hurt this country's equity.
  Range: roughly [-1, +1]. Saudi at +0.05 means the market is pricing
  ~5% expected downside spillover. Saudi at -0.05 means ~5% expected
  upside spillover.

predmkt_country_opportunity_composite: -1 × risk_composite.
  Provided for symmetry; agents who prefer "high = good" can use this
  field directly.
"""
```

Also update the MCP tool `country_signal_now` to document this convention in its return shape — a one-paragraph addition to the tool description.

### Validation

After applying, Saudi Arabia's `risk_composite` should change from +0.017 to -0.017, and `opportunity_composite` from -0.017 to +0.017. ChinaA risk should flip from -0.308 to +0.308 (currently the math says US-China tariff agreement at high prob is good for ChinaA, so the new convention says low risk for ChinaA — but with the new tariff-escalation markets from Item D, ChinaA risk may net higher).

---

## 8. Build Plan

| Block | Item | Time | Validation |
|---|---|---|---|
| AM-1 | Item A — book-aware stale flag, modify `_infer_stale` and call sites | 30 min | Kalshi macro markets show `is_stale=False`; previously empty composites populate |
| AM-2 | Item B — `is_settled_effective` column + filter | 45 min | RU-UA ceasefire markets flagged settled; Poland risk drops from 0.49 |
| AM-3 | Item C — flip Poland/Turkey signs in YAML | 10 min | YAML re-validated, regenerates correctly |
| Lunch | — | — | — |
| PM-1 | Item D — curate 2–3 tariff escalation markets | 60 min | New markets resolve via `--validate-only`, tariff_intensity_by_country computes from escalation+resolution mix |
| PM-2 | Item E — flip risk_composite sign + docstrings | 15 min | Saudi flips +0.017 → -0.017, ChinaA flips -0.308 → +0.308 |
| PM-3 | End-to-end rebuild + smoke tests | 45 min | All five validations pass, MCP tools return expected outputs |
| PM-4 | Update PRD_Stage2 to v1.1 with new convention notes | 15 min | Single source of truth for downstream docs |

Total: ~3.5 working hours.

---

## 9. Acceptance Criteria

1. **Kalshi macro markets are not stale.** `KXRATECUT-26DEC31`, `KXCPI-26MAY-T1.0` show `is_stale=False`; one-sided `KXCPI-26MAY-T-0.2` remains stale.

2. **Effectively-resolved markets are excluded from composites.** Russia-Ukraine ceasefire markets at probability 1.0 show `is_settled_effective=True` in `predmkt_daily` but do not appear in `predmkt_signals_daily.constituent_markets` for any signal.

3. **Macro signals populate.** `fed_cut_count_expectation`, `cpi_nowcast_yoy_next` (or whichever the active CPI ladder supports) show non-NULL values in `predmkt_signals_daily`.

4. **Poland and Turkey risk composites are sign-corrected.** With ceasefire markets excluded by Item B, both should be near zero. Without that filter, both should be moderately negative (ceasefire helps them).

5. **Tariff signal direction matches name.** With escalation markets curated, `tariff_intensity_by_country` for ChinaA is positive when escalation is likely; goes down when agreement market probability rises.

6. **Risk/opportunity composites have intuitive signs.** Saudi `risk_composite` and `opportunity_composite` are negatives of each other; positive values of `risk_composite` mean "implied downside." Saudi at +0.017 risk = small implied downside.

7. **Existing MCP smoke tests still pass.** `predmkt_snapshot('oil_shock')` returns WTI markets, `country_signal_now('Saudi Arabia')` returns the channel breakdown, `event_market_set('iran')` returns the peace deal market.

8. **Migration is non-destructive.** Existing daily snapshots from before this PR are not rewritten. The new `is_settled_effective` column is added with default FALSE for existing rows. Composite signals from before this PR keep their old values; new snapshots use new conventions.

---

## 10. Open Questions

1. **Should we backfill `is_settled_effective` for the single existing snapshot?** The 2026-05-09 snapshot has 32 rows with `is_settled_effective` defaulting to FALSE after the migration. Recommendation: leave it. The first re-run after this PR computes the field correctly going forward, and one snapshot of historical data with the column missing is fine.

2. **Should `predmkt_country_opportunity_composite` be retained?** It's mathematically just `-1 × risk_composite`. Two arguments for retention: (a) some queries are clearer with `opportunity_composite > 0` than `risk_composite < 0`, (b) the variable_meta table already lists both. Recommendation: keep both, document the relationship explicitly in the tool description.

3. **What if no liquid tariff-escalation markets exist on Polymarket?** Possible — Trump-era tariff markets may have all already resolved. Fallback: search for "trade war" or "reciprocal tariff" markets, or search Kalshi for trade-related macro markets. If still nothing, document the `tariff_intensity_by_country` signal as "currently disabled — no qualifying tariff-escalation markets in registry" rather than ship it broken.

4. **`is_settled_effective` versus harder semantics on `is_resolved`.** Could we tighten the `is_resolved` check on the puller side and skip adding a new column? Polymarket's `closed` flag and `winningOutcome` field both exist; we could be more aggressive there. Recommendation: keep both columns. `is_resolved` reflects the platform's official resolution flag (post-payout); `is_settled_effective` captures the practical "no longer trading meaningfully" state. They diverge for ~24h around resolution time.

5. **Whether to rename composite signals more dramatically.** The names `risk_composite` and `opportunity_composite` are conventional but a reader without context might still be confused. Alternative: `predmkt_country_implied_drawdown` and `predmkt_country_implied_upside`. Recommendation: keep current names with corrected semantics — renaming twice in two days is its own confusion source.

---

## 11. References

- `PRD_Stage2_Prediction_Markets.md` — original Stage 2 PRD (signals layer §7.4 documents the original composite formulas)
- `scripts/build_predmkt_panel.py` — composite computation in `_compute_signals`
- `config/predmkt_curated.yaml` — registry being modified
- 2026-05-09 verification thread — origin of the five issues listed in §1

---

*End of PRD*
