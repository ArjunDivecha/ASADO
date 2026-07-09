# ARJUN.md — product owner's memo

*Fable 5, 2026-07-06. Blunt, value-per-hour framing. No code was changed.*

## What this repo is worth

ASADO is **alive and it's the hub** — not dormant, not superseded, not a duplicate of anything
else in the ecosystem. It's the upstream that feeds `A Complete/Fable Daily Trading` (which reads
the loop DB read-only at 12:20 PT), and it's the only place in your stack that runs the full
loop: warehouse → dislocation detection → hypothesis → skeptic harness → thesis ledger → cockpit.
The genuinely valuable asset here isn't any single signal — it's the *discipline*. In the last
week alone the factory honestly killed three projects (`regime/` 0/52, `momentum_fragility`
failed walk-forward, `regime_factor_selection` 0/74 placebo-confirmed null). Most shops would
have found a "pass" by tuning; you built machinery that reports the null. That machinery is worth
more than the signals it rejects. The risk isn't that ASADO is dying — it's that its best rules
live in your head and in `AGENTS.md`, not in gates, and that its output stops at your Mac screen.

## Extensions ranked by value ÷ effort

1. **Ship the leakage/isolation guard into CI (this week).** *What:* the P0 in `FABLE.md` — one
   command that fails the build if a forward-return variable gets registered as a signal or an
   isolated table leaks into `feature_panel`. *Why now:* you have almost no CI (only
   `openwiki-update.yml`) and the whole value proposition is "no leakage" — right now that's
   enforced by memory. *First step:* run the embedded Divecha contract in Build Mode, then add a
   `.github/workflows` step. *Reuse:* the Divecha skill + the existing workflow pattern.

2. **Take the daily combiner out-of-sample in QuantConnect against the EW benchmark.** *What:* the
   combiner (`combiner_scores_daily`) is your strongest registered signal but you flagged it as an
   in-sample-selected ceiling — the honest next question is net-of-cost P&L on real ETFs vs
   equal-weight, over Full/5y/3y/1y. *Why now:* it's the only signal close to graduating, and a
   clean walk-forward backtest is the missing bridge from "survives the harness" to "trade it."
   *First step:* export the daily combiner ranks to a monthly-rebalance signal and run the
   `backtest` skill on the 34-country ETF universe. *Reuse:* QuantConnect/LEAN backtest skill,
   `Fable Daily Trading` as the eventual home.

3. **Push the nightly cockpit + dislocation brief to a private Vercel deploy.** *What:* the cockpit
   (`cos_mockups/`, `frontend/`) is local HTML; the brief lands in `Data/dislocations/` and you
   read it on the Mac. Put it behind a private URL so you can read the Edge Board and today's
   dislocations from your phone. *Why now:* you generate a brief every night and consume ~none of
   it away from the desk. *First step:* wire `build_cockpit_data.py` output into a static Vercel
   project. *Reuse:* Vercel (authenticated), existing frontend.

4. **Pipe kill/graduate verdicts into the personal-knowledge MCP.** *What:* every dead project is
   expensive, hard-won knowledge; capture *why* it died so neither you nor an agent re-runs it in
   six months. *Why now:* you just killed three tests in a week and `llmchat.md` (the only record)
   is already 20 commits stale — that knowledge is evaporating. *First step:* on each harness
   verdict, `create_entry`/`add_insight` in the personal-knowledge system with the spec_id, the
   verdict, and the one-line reason. *Reuse:* personal-knowledge MCP, `ledgers/*.jsonl`.

5. **Auto-refresh the state-of-play log nightly.** *What:* append the `git log` delta + the night's
   harness verdicts to `llmchat.md` (or a new `STATE.md`) as the last loop step. *Why now:* the
   log being 4 days / 20 commits behind means every fresh agent (and you, on Monday) starts from a
   wrong picture. *First step:* add a ~20-line append step to `loop_daily_job.py`. *Reuse:* the
   nightly job you already run.

6. **Turn the factory into a book chapter.** *What:* "How to run a research factory that mostly
   produces nulls — and why that's the edge" is a strong, differentiated chapter; the ledgers are
   the primary source. *Why now:* the material is freshest right after three honest kills. *First
   step:* dictate a voice memo walking through the three dead projects; hand it + the ledgers to
   the ghostwriter. *Reuse:* `book-ghostwriter` skill, `Book` repo.

## Quick wins (< 1 hour, outsized payoff)

- **Commit the two untracked dead experiments.** `momentum_fragility/` and
  `regime_factor_selection/` (plus their two PRD files) are untracked — a null result you paid for,
  one `rm -rf` away from gone. `git add` + commit (or move to `journal/graveyard/`) preserves the
  record. *(5 min; see FLAGS — this is the one thing I'd do first.)*
- **Add the nightly `STATE.md`/`llmchat` append** (extension 5) — kills the staleness that misleads
  every future session.
- **Add the leakage guard as a pre-commit hook** once it exists — makes extension 1 run for free on
  every change.

## What NOT to do

**Don't promote the daily combiner to live capital as-is, and don't add a 34th data source.** The
combiner's IC of 0.057 / NW-t 10.7 is a *stated in-sample ceiling* — pushing it into
`Fable Daily Trading` without clean walk-forward re-selection is precisely the p-hacking the whole
factory exists to prevent; you'd be spending your credibility to skip the one step that makes the
result real. And the tempting instinct — more detectors, more signal families, more sources — is
the low-ROI direction: your bottleneck is not signal *generation* (you generate plenty and kill
most), it's the honest out-of-sample path from "survives the harness" to "one survivor at live
size." Harden that path (extensions 1 and 2). Don't feed the hopper more.
