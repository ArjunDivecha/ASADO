# E1 — network_spillover expression capture rerun

## Question

Does the already-frozen `network_spillover` nightly rank information survive when
the return is measured in a realistic expression and clock, rather than only in
the local-index close-to-close diagnostic?

## Frozen specification

- **Signal input:** the existing frozen nightly rank panel at
  `Data/work/experiments/flip_autopsy/snapshot_2026_07_13/family_ranks_daily.parquet`.
  No signal values are rebuilt, fitted, or searched. The four existing
  network-spillover rank columns (`graph_bank`, `graph_twohop`, `leadlag`, and
  `twins`) are converted to normalized rank strength and averaged equally when
  available. A country/date needs at least two member ranks.
- **Clock:** harness-v4 honest daily execution clock: effective lag = 1 trading
  day. A rank observed on date `t` cannot earn a return that opens at `t`'s
  close. The runner uses the same queued-next-day execution convention as the
  harness daily portfolio path and records the imported v4 lag helper result.
- **Expressions:**
  1. local country index return;
  2. roll-aware local equity-index futures, only where the Global Data Mart has
     a mapped equity-index future (`France/CF`, `Germany/GX`, `Hong Kong/HI`,
     `Japan/NK`, `U.K./Z`, `U.S./ES`);
  3. the next US-listed ETF session's open-to-close return;
  4. US-listed ETF close-to-close return (the existing null endpoint).
- **Portfolio:** top-7 long-only versus equal weight for broad expressions;
  top-2 for the six-country futures subset; top-minus-bottom equal-weighted
  long-short is reported as a secondary diagnostic. Horizons are 1, 5, and 21
  daily holding days with overlapping tranches.
- **Costs:** gross is the primary result. Execution diagnostics are shown at
  2.5, 5, 10, and 25 bp one-way; these are not research gates. The report also
  keeps the expression-specific sample and coverage visible. No new family,
  signal, or pipeline stage is created.

## Mechanism and invalidation

The network rank captures delayed cross-market propagation that local-market
participants may price before a country endpoint fully catches up; if that
information is tradable, the residual should appear more strongly in local
futures or the next ETF open than in the US ETF close-to-close return.

The capture claim is invalidated if every tradable expression is gross
non-positive versus equal weight, or if any apparent gross edge disappears at
the expression's realistic execution-cost case. A positive re-arm gate alone is
not evidence of capture and cannot authorize deployment.

