# Addendum to the research brief — focus on training a nonlinear model

*2026-09-13. Companion to `docs/ASTRA_BRIEF_regime_model_2026_09_13.md`. The brief stands; this narrows the ask. Everything in the brief's "what has already been killed" and "data facts" sections still binds.*

---

## The refocus

The central question is now: **how would one train a nonlinear model on this dataset to predict forward country equity returns — and prove it beats a regularized linear model on identical, point-in-time-safe samples?**

Regime definitions from the brief remain relevant only insofar as they become *inputs* or *states* the nonlinear model can exploit. Do not spend the design on regime taxonomy. Spend it on the training problem.

## Why nonlinear is the interesting bet here, and why it usually fails

The case for it is the Macro State Model's fifth claimed advantage: a nonlinear learner can pick up **interactions among economically meaningful states** — cheap valuation matters differently when flows are leaving than when they are arriving; a curve inversion means one thing under an easing central bank and another under a tightening one. A flat ridge over hundreds of raw variables cannot represent that; a tree ensemble or a small network can.

The case against is the record: every flexible thing tried on this panel so far has either found nothing or found a search artifact. The two laws in the brief apply with full force to nonlinear training — *distrust a searched pass* is a direct statement about hyperparameter search, and the sample-size fact (≈4,063 independent dates, ≈64 non-overlapping 3-month windows, 28 countries with correlated cross-section) is the constraint that kills most nonlinear designs before they start.

Your job is to design the version that could survive that.

## What I want you to specify

Produce these numbered sections. Be concrete about tables and variables from the inventory; give numbers where a number decides something.

### 1. The feature set, at three altitudes

Design the input layer at three levels and say which the nonlinear model should see, and why:

- **Raw**: the daily Tier-A and Tier-B series from the brief (sovereign yields and CDS, FX implied vol / risk reversals / carry, ETF flows, consensus revisions, plus the global risk block and commodity futures), the T2 daily technicals and valuation ratios, and the point-in-time graph / lead-lag / similarity features.
- **Concept**: the ~14–15 economic concepts of the Macro State Model (growth cycle level and momentum, expectations gap, monetary impulse, credit, external vulnerability, valuation, flows and positioning, sovereign risk, network stress, …), each a small fixed combination of raw series.
- **State**: ~5–7 higher-level country states derived from the concepts.

For each altitude, state how many features it produces, how it is built without leakage (the concept and state layers must be constructed on expanding windows, never on the full sample), and what the *linear* baseline at that altitude is. The comparison that matters is nonlinear-on-states versus ridge-on-states versus ridge-on-raw, on identical folds.

### 2. Target and objective

Choose and defend: forward excess return versus cross-sectional rank versus sign versus a risk quantity, at 20-day, 63-day and 126-day horizons. Say whether the objective should be pointwise (MSE / Huber), ranking (pairwise or listwise across the 28 countries on each date), or classification, and why a ranking objective may be the right choice when the cross-section is the unit of decision. State the non-overlapping-window count for each horizon.

### 3. Model classes, ranked for this sample size

Give an ordered shortlist with a one-paragraph justification each, and say explicitly what is ruled out:

- Gradient-boosted trees with heavy regularization (shallow depth, strong subsampling, monotone constraints where the economics is one-signed, few hundred trees). Say which features should carry monotone constraints and in which direction.
- Small MLPs with strong weight decay and early stopping on a *time* validation fold, with the input layer being the concept or state altitude only.
- Kernel and Gaussian-process methods, which are often the right nonlinear tool at ~100 independent observations.
- Explicit low-order interaction models (pairwise products of states fed to a ridge) as the *honest* nonlinear baseline — if a GBM cannot beat a ridge over pairwise state interactions, the GBM has found nothing.
- Anything transformer- or sequence-model-shaped: state whether the panel is large enough for it at all, and what would have to be true for it to be.

For each class, give the effective parameter count you would allow relative to the number of independent observations.

### 4. Cross-validation and the search protocol

This is where nonlinear designs die. Specify:

- **Walk-forward with embargo**: expanding window, purged of overlapping-target rows between train and test, with an embargo at least as long as the target horizon. Give the fold count and the first test date.
- **Hyperparameter search discipline**: the search space, how small it is kept, that it runs only on the training portion of each fold, and how the final reported number is protected from the search — nested CV or a single held-out end-block never touched during design. Tie this to the *distrust a searched pass* law: a configuration found by search is reported with its search count and deflated accordingly.
- **The placebo**: shuffled-label and shuffled-date controls run through the *entire* pipeline including the search, so the null distribution reflects what the search alone can find. Say what the placebo result must be for the real result to count.
- **The flat baseline** trained under the identical protocol, because a nonlinear model that beats an under-tuned linear one has proved nothing.

### 5. What "earning its complexity" means, in numbers

State the pre-registered gates before any result is seen. At minimum: out-of-sample rank IC and its Newey-West t-statistic; deflated Sharpe of the top-minus-bottom quintile long-short portfolio, gross, against the equal-weight benchmark over Full / 5y / 3y / 1y; the fraction of years with positive IC; and the margin by which the nonlinear model must exceed the ridge-on-states baseline for the additional complexity to be accepted. Give the kill criteria as explicit thresholds.

### 6. Interpretability as a validation tool, not a report

Specify how SHAP or partial-dependence output is used to *falsify*: if the model's strongest interactions are between features that have no economic relationship, or its importance concentrates on a variable the brief lists as monthly-content-on-a-daily-grid, that is evidence of leakage or artifact, not discovery. Name three interaction patterns you would expect to see if the model were learning real economics, and three that would make you kill the run.

### 7. The 2024–26 sign flip

The second-order propagation family — the only survivor — reversed sign in 2024–26 and nobody knows why. A nonlinear model that conditions the propagation features on the regime-type states from the brief is one plausible way to *learn* the flip rather than be surprised by it. Say whether that is worth a dedicated experiment, how it would be set up, and how you would tell "learned a real conditional structure" from "fit the last two years."

### 8. Your honest prior, and the single first run

Given the record and the sample size, what probability do you put on a nonlinear model clearing WATCH against a properly tuned ridge on the same states? Name the one configuration you would run first — model class, altitude, target, horizon, gates — as a complete pre-registration a colleague could execute without asking you a question.

## Non-negotiables carried from the brief

- Forward-return variables are never features. Trailing momentum is the `*DTR_CS/_TS` family.
- Trading-day filtering via `daily_calendar` before any return or volatility calculation; account for its one-day lag.
- No cost or turnover penalty anywhere. Gross signal quality only.
- Every concept and state layer built on expanding windows. No full-sample standardization, PCA, or clustering anywhere upstream of a prediction.
- Report the search count with every result.
