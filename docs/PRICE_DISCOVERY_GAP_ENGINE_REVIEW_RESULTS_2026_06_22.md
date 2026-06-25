# Price-Discovery Gap Engine Review Results

Date: 2026-06-22, updated 2026-06-23

Reviewed artifact: `PRD_Price_Discovery_Gap_Engine.md`

Review prompt: have Opus and Sakana review the plan for ASADO's Price-Discovery Gap Engine, focused on whether the PRD cleanly answers: what does the data know that price has not yet figured out?

## Executive Result

Both reviewers agreed the central abstraction is right: ASADO needs a durable gap-episode layer between raw detector rows and paper theses. Both reviewers recommended revisions before implementation.

The PRD was revised to v1.2 after those reviews, then re-vetted with Opus on 2026-06-23. Opus recommended a small v1.3 revision rather than redesign. After v1.3 was patched, a follow-up Opus pass returned `PROCEED`. The current v1.3 draft folds in the material blockers from Opus, Sakana/Fugu, the forced post-revision `fugu-ultra` pass, and the final Opus pass.

## Opus Review

Recommendation: `REVISE`

Main findings:

- Split claim, measurement, and expression. Do not let a gap episode, ETF implementation, and statistical test blur into one object.
- Make `gap = world-state - price-state` a per-class normalized comparison, not a single arithmetic formula.
- Use an additive, auditable tension score rather than a multiplicative formula with hidden penalties.
- Store numerator, denominator, and source for price absorption; cap/floor the denominator.
- Add child surfaces for price state and ETF expressions.
- Make mechanism text deterministic from templates.
- Add anti-HARKing invariants: immutable claim fields, one open episode per key, point-in-time marks, and explicit status handling.
- Cut prediction-market and stewardship concepts from v1 ranking unless they are diagnostic only.

Changes folded into PRD v1.2:

- `price_state_surface` and `gap_episode_expression` added.
- `gap_episodes` made an immutable claim table.
- Additive `tension_score` added with scalar component fields and scoring config hash.
- Price absorption made explicitly provisional with `expected_move_source`, floors, caps, and denominator audits.
- D8 stewardship and G8 prediction-market disagreement demoted out of v1 top-gap ranking.

## Sakana Review

The thin Sakana API script returned empty `{}` responses with zero token usage twice, so the review used the Sakana-backed `codex-fugu` fallback, then a forced `fugu-ultra` pass.

First Sakana/Fugu recommendation: `REVISE`

Main findings:

- The original `gap_id` design risked creating a new episode every day.
- ETF tracking gaps could be mostly FX/currency basis rather than expression quality.
- `config/etf_t2_map.json` does not include expense, spread, or liquidity metadata; v1 needs a separate overrides file and derived ADV.
- Absorption denominator cannot pretend to be analog-calibrated before episode history exists.
- Backfill over short `dislocation_daily` history is plumbing only, not ranking validation.
- Daily `1DRet` must only be used through the existing `loopdb.daily_country_returns()` / `returns_panel()` helpers.
- Brief rendering must be split so `build_gap_episodes.py` runs before the final brief renderer.
- Evidence-pack re-pointing should be deferred because GDELT throttling is fragile.
- Holdout should include ignored controls and a random-shadow negative control.

Changes folded into PRD v1.2:

- Stable episode lifecycle with `episode_key`, `episode_instance`, `gap_id_seed`, and `gap_id`.
- ETF `currency_basis`, raw basis, and FX-adjusted basis added.
- `config/etf_expression_overrides.yaml` required; ADV derived from `etf_prices_daily.close * volume`.
- Absorption V0 labeled as class-specific severity mapping, with audit.
- Backfill explicitly labeled as plumbing-only.
- Forward-return exception pinned to `loopdb` helpers.
- `render_dislocation_brief.py` added after `build_gap_episodes.py`.
- `gap_holdout_daily` added with controls and random-shadow score.

## Post-Revision Fugu-Ultra Pass

Recommendation: `REVISE`

Remaining blockers:

- `gap_id` lifecycle still needed an explicit reopen sequence.
- Tension-score component values needed first-class schema fields, not only JSON.
- Holdout rows needed reproducible `candidate_id`, frozen component vectors, and config hashes for ignored controls and random-shadow rows.

Changes folded into PRD v1.2 after this pass:

- `gap_id = sha1(episode_key|first_seen_date|episode_instance)`.
- `episode_instance` increments only after prior episode close/expire/invalidate/void.
- `gap_id_seed` is stored for audit.
- Score component columns added to both `gap_episodes` and `gap_holdout_daily`.
- `scoring_config_version` and `scoring_config_hash` added.
- `candidate_id = sha1(date|episode_key|candidate_signature)`.
- `candidate_signature` and random-shadow seeding rules defined.
- Tests and acceptance criteria updated for reopen sequencing, score components, and holdout reproducibility.

## Final Opus Pass

Recommendation: `REVISE`

Opus assessment:

- The architecture is ready.
- The remaining gaps are interpretation discipline and replay reproducibility, not data-model redesign.
- The engine should proceed as an enhancement layer, not a replacement for `dislocation_daily`, the harness, or the ledgers.

Remaining blockers:

- Add an inconclusive-holdout decision rule so a thin first window does not get over-interpreted.
- Pin historical replays/backfills to the scoring config hash live on each historical as-of date.
- Label absorption states as provisional when they are driven by `severity_mapping` or `neutral_default`.
- Deduplicate the top-5 brief at the `entity|direction` level so related same-country episodes do not crowd out breadth.
- Add governance dimension dependency mapping so amber-governance pass/fail is reproducible.

Changes folded into PRD v1.3:

- `config/gap_engine.yaml` now includes governance dependencies, holdout power thresholds, and explicit severity-to-expected-move mapping.
- Historical config pinning is required for backfills/replays.
- The brief and CoS must label severity-mapped absorption as provisional.
- The top-5 renderer applies entity/direction deduplication and nests related episodes.
- Holdout success/failure/inconclusive criteria now include minimum sample thresholds and random-shadow comparison.
- Implementation phases, risks, tests, and acceptance criteria were updated for these requirements.

## Follow-Up Opus Pass On v1.3

Recommendation: `PROCEED`

Opus assessment:

- No remaining design blockers before Phase A.
- Open scoring weights, ADV thresholds, and expected-move floors are implementation parameters, not PRD blockers, because config hashes and holdout rules make them auditable.
- The most realistic first holdout result may be `INCONCLUSIVE_SAMPLE`; that is acceptable as long as the UI and reports call the ranker pilot/provisional.

Implementation discipline notes:

- Treat `config/gap_engine.yaml` v1 parameter-setting as pre-registration: document weight/floor/cap/ADV-tier rationale and do not tune mid-holdout without an explicit v2 config bump.
- Add a brief-renderer regression baseline before Phase D so the old dislocation brief path is preserved when gap sections are disabled.
- Track `config/etf_expression_overrides.yaml` coverage and expected `research_only` share before launch.
- Add a simple rollback or feature-flag path for the new renderer because it touches the live daily brief contract.

## Current Status

Status after integration: v1.3 is Opus-vetted and ready for Phase A implementation planning, with open implementation parameters still called out in the PRD:

- v1 scoring weights,
- ADV liquidity thresholds,
- expected-move floors, class base moves, and caps,
- horizon defaults,
- whether Triptych priors enter v1,
- whether first-month autopsies require review.

Verification performed:

- No stale `first_seen_window` references remain.
- `git diff --check` passed for the edited docs.
- `PRD_Price_Discovery_Gap_Engine.md` is 941 lines after v1.3 review integration.
