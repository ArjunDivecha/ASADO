# Own analysis before the outside reviews (2026-10-07, evening)

Working notes; the discussion document is DESIGN.md.

## Three measured facts that shape the design

1. **Reward noise.** Per-month signal-to-noise of candidate rewards, from the default model's out-of-sample scores:
   top-8 excess 0.075, rank IC over all 34 countries 0.109, pairwise ordering accuracy 0.107, score-weighted long-short 0.084.
   A 60-month training window therefore carries t ≈ 0.11 × √60 ≈ 0.8 of evidence about a policy as good as the default.
   RL on realised returns cannot *discover* reasoning inside one window; it can at best *calibrate* priors the LLM brings.
2. **Learnable auxiliary targets.** Rolling 60-month ridge, out of sample, per-month rank IC SNR for next-month *changes*:
   20-day vol 2.48, trailing EPS 0.99, LT growth 0.90, forward (BEST) EPS 0.68, ROE 0.66, inflation 0.60, 10Y yield 0.27,
   returns 0.13, currency 0.12. Fundamentals are 5–19× more learnable than returns; market prices (currency, returns) are not.
   These are verifiable rewards with real signal — the closest thing to "pretraining" this problem has.
3. **Leakage.** Within-month factor ranks persist (median autocorrelation 0.91); nearest-neighbour on a country's rank vector
   re-identifies it next month 93.5% of the time (87% with 20 factors). Any context holding two months lets the model track
   countries across time. One month per context, fresh random IDs every month, ranks not levels, size features removed —
   and an explicit re-identification audit (can the LLM name the country or the year?).

## Implications

- The engine has to be the LLM's prior (structural economic knowledge), with outcomes used to calibrate, not discover.
  So the first, cheapest test is **prior-only**: zero-shot ranking from factor names and ranks, no outcomes, no training.
  If an anonymised zero-shot ranking has no edge, RL has very little to calibrate.
- **Never ask the LLM to explain one noisy month.** Either (a) validate every month-level lesson on the *other* months of the
  window and against a placebo run on permuted outcomes, or (b) give it window-level evidence (a factor "tear sheet":
  each factor's trailing spreads, hit rates, stability, regime splits — 60 months aggregated, SNR × √60) and let it reason
  over statistics plus priors to set the month's strategy. (b) is the "LLM as quant PM" variant and never fits single months.
- **Reward = multi-task:** rank IC on returns + rank IC on next-month changes in fundamentals (EPS, forward EPS, inflation, vol),
  group-relative advantages (GRPO). Curriculum: economy first, market second.
- **Weight-level RL is high-dimensional and data-starved.** Prefer learning over a low-dimensional space the LLM proposes
  (rules / factor weights / conditional statements), with the LLM as proposer and the walk-forward as the scorer — the
  "hill-climb" in the original sense. Keep weight fine-tuning (SFT + GRPO) as a later phase, warm-started fold to fold.
- **Power.** Paired monthly difference between two good models has sd ≈ 1.5%/month. Over 260 months, beating the default
  at t = 2 needs ≈ +2.2%/yr. A realistic success criterion is diversification: an LLM arm near 2–3%/yr with correlation
  ≤ 0.5 to the default, raising a pre-registered 50/50 blend's IR materially.
- **Compute.** Local GRPO on the M4 (≈ 8B model, LoRA): roughly days per walk-forward run. Rented GPUs (8× H100 class,
  vLLM rollouts): hours. Phase 0/1 can run on flat-rate subscription CLIs where rate limits allow.
- **Forward (owner's point).** The named arm's knowledge is contaminating in backtest and valuable forward. Production arm =
  named + live news, frozen prompts and model version, model knowledge cutoff recorded, pre-registered decision rule.
  Each model upgrade starts a new forward record.
