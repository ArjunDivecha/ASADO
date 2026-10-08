---
title: "Country top-8 ranking model — close-out"
subtitle: "ASADO experiment 2026_10_rank_model · 7–8 October 2026 · decision: keep the default"
---

# The decision

**The default model stays, unchanged.** It is a neural network trained on 238 monthly factor z-scores for 34
countries, refitted each year on the trailing five years only, averaged over 30 independently trained nets, and
traded with a buffer: buy the top eight, hold each name while it stays in the top sixteen.

Out of sample from February 2005 to September 2026, gross of costs, against the equal-weight average of all 34:

| | Default | Equal-weight 34 |
|---|---|---|
| Annualised return | 11.2% | 8.3% |
| Excess over equal weight | +3.2% a year (t 2.5) | — |
| Annualised standard deviation | 20.2% | 17.7% |
| Maximum drawdown | −61% (2008) | −58% (2008) |
| Worst drawdown against equal weight | −18% (Dec 2005 – Nov 2008) | — |
| Turnover, one-way | about 260% a year (1.8 names a month) | — |

The last five years are its strongest stretch: 15.1% a year against 9.7%, an excess of 5.2 points. The average of
three independent training runs is +3.1% a year with t 2.8, and the runs agree to within a quarter of a point,
which matters more than any single number here.

Everything tried after the default was set failed to beat it by a margin distinguishable from noise. That is the
main result of the second day: the default sits near the ceiling of what this data supports, and every added
layer, input or weighting cost more than it earned.

# What was tried after the default, and why it didn't make the cut

**A blend of the net with a ridge regression.** No improvement under the buffer rule (2.9% against 3.1%). The
buffer and the blend do the same job — damp noisy picks — so stacking them adds nothing.

**Training on all history with more weight on recent years** (both outside reviewers' preference over the
rolling five-year window). Half-lives of 24, 36, 60 and 120 months and plain all-history were all within a paired
t of ±0.7 of the rolling window, and far less stable: their three runs spread over 2.7 to 4.5 points, against 0.26
for the rolling window. The rolling window is the robust choice, as Arjun had argued.

**GDELT news, three ways** (veto the most news-shocked holding; exclude countries with bad news; boost countries
with good news). All three failed their pre-registered tests; excluding bad-news countries cost 1.2% a year. The
daily GDELT theme file turned out to be empty. GDELT now has a family verdict in Investment Learnings and is closed
for this project. News was then dropped from the programme altogether.

**The fundamentals toolkit.** The idea: next month's changes in earnings, inflation, volatility and yields are five
to twenty times more predictable than returns, so a model that learns them first might pick countries better.

- The forecasts themselves are real: six of seven beat naive baselines out of sample (volatility rank correlation
  0.39, earnings 0.17–0.18, inflation 0.13).
- Hindsight ceiling: one perfect swap a month would add 23% a year, so the action space was never the constraint.
- A second-stage ridge combining the forecasts with the default's score lost 2.1% a year — and the same ridge with
  the default's score alone lost 1.7%. A fitted second stage damages a good score on its own.
- The forecasts as six extra inputs lost 2.9% a year; six columns of shuffled noise lost 1.6%. Extra inputs carry
  a tax at this data size, and the forecasts' content (worth a fraction of a point) does not pay it.
- **One net learning returns and fundamentals together** (Arjun's design) was the best variant. At weight 0.5 it
  made 12.1% a year against 11.2%, ahead in all three runs, with a smaller worst drawdown against equal weight
  (−11.6% against −18%). But the paired t was 0.76, and the advantage is one episode: 2005–08, when the training
  window held only the dot-com years. Since 2010 the default's worst relative drawdown is 9.3% against the
  multi-task net's 11.6%, and over the last three years the default leads by 3 points a year. Five weightings were
  tried; the gain rises to a peak at 0.5 and falls away either side. A 50/50 score combination of the two did not
  help in the recent years.

**Why the default was kept.** The multi-task net is a portfolio of about the same quality with a better worst
case in one historical episode — insurance against a short, misleading training history — paid for with weaker
results in calmer stretches including the most recent ones. The evidence does not separate them; the choice is a
judgment, and Arjun chose the simpler model with the stronger recent record.

# The LLM programme

The discussion that started this day — an LLM trained on realised outcomes, then a hybrid in which a frontier
model uses a quantitative toolkit — produced a reviewed design (GPT and Sakana) and six decisions, all closed:
the ladder adopted; rolling five years confirmed by test; capital decisions by owner's judgment, no numerical
targets; point-in-time models only for measuring hindsight; news dropped; Bloomberg not used for news. With news
dropped and the toolkit closed, there is nothing for an LLM to add in the monthly loop that the July LLM-1M
verdict (an LLM reading numbers predicts nothing) does not already rule out. The design document is kept as the
record; nothing from it is scheduled.

# What would reopen any of this

- A forward record of the default that diverges from its backtest.
- A regime break of the 2005–08 kind, in which case the multi-task net (weight 0.5) is the ready alternative —
  code and results are in place, and its pre-registered comparison is done.
- A genuinely new information source that is not a function of the 238 factors (the lesson of the toolkit is that
  re-expressions of the same inputs do not help).

# Next

Forward paper-trade the default, with each month's basket timestamped before the month starts. Vintage-archived
slow inputs and the T2 macro lag remain on the list from the first day.

# Where everything is

All in `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/`
(branch `exp/NN`, pushed):

- `README.md` — every step, with numbers; `results/report.html` — the stage-by-stage report from the first day.
- `results/default_20261007_155223/` — the default's three-run record.
- `ema_window/` — the window test; `gdelt_veto/` — the three GDELT tests; `toolkit/` — ceiling, heads, comparator,
  forecasts-as-inputs, multi-task net, the close look, and the three-way comparison (`README.md` and `PREREG.md`).
- `results/three_way_20261008_091245/report.html` — default, multi-task and 50/50 side by side.
- `llm_rl/DESIGN.html` — the LLM design and its decisions.
- Investment Learnings: `GDELT Country Rotation Conditioning.md` and `Country Top-8 Rank Model.md`.
