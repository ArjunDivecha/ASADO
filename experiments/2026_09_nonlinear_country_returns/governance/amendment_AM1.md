# Amendment AM-1 — ASADO_NL_20260913_V2

**Base spec:** ASADO_NL_20260913_V1 (vendored pack, `spec/`)
**Trigger:** P01 audit verdict `BLOCKED_DATA` — strict 24-primitive complete-case
ceiling is 15 markets < 20/origin floor (see `data_readiness.md`,
`audit/coverage_waterfall.json`).
**Approval:** owner directive 2026-09-13 — "loosen the blockers and make it run"
+ explicit "Drop P11" on the tenor question. Executed before any outer
evaluation, as required.

## Changes vs V1

| Item | V1 | V2 (this amendment) |
|---|---|---|
| P07 `bank_neighbor_return_21` | bank-edge focal required | **REMOVED** (21 focals → binding coverage constraint) |
| P08 `bank_neighbor_return_63` | bank-edge focal required | **REMOVED** |
| P11 `fx_rr25_3m_depreciation` | 3M 25-delta RR | **REMOVED** (3M tenor does not exist; owner chose removal over the 1M substitute) |
| Primitive count | 24 | **21** |
| X dimension | 24 | **21** |
| S dimension | 16 | **15** |
| C05 (bank-neighbor concept) | P07 | **removed** |
| C06 (FX-options complex) | (P09+P10+P11)/3 | **(P09+P10)/2** |
| ≥20-markets-per-origin floor | 20 | unchanged |
| Complete-case rule | all primitives per row | unchanged (now over 21) |
| Everything else | — | unchanged |

## Measured feasibility under AM-1 (level-1 eligibility, snapshot 2026-09-13)

- **22 markets ever eligible**: Australia, Brazil, Canada, ChinaA, France,
  Germany, India, Indonesia, Italy, Japan, Korea, Mexico, Netherlands, Poland,
  Singapore, South Africa, Spain, Sweden, Switzerland, Thailand, Turkey, U.K.
- **≥20 eligible markets from 2010-07-01** onward (Brazil SOV_2Y + Turkey 10Y
  are the last of the first 20; ChinaA joins 2011-02, Netherlands 2015-03).
- Expected panel start ≈ 2011-01 (consensus start 2007-10 + 126-obs
  normalization warm-up + ≥20-market constraint) → first outer fit ≈ July 2019
  → ~7y of outer origins ≈ 1,750 ≫ 756 floor.
- US complex (U.S./NASDAQ/US SmallCap), ChinaH, Taiwan, Chile, Hong Kong,
  Malaysia, Philippines, Saudi Arabia, Vietnam, Denmark excluded — the panel is
  DM+EM without the USD numeraire complex; the region map and leave-region-out
  diagnostics (P09) will report this honestly.

## What was NOT done

- No substitute feature was introduced (no 1M-RR stand-in, no holder-edge swap).
- The missingness rule was not relaxed to allow masked/imputed rows.
- No model was evaluated on real outer data.
