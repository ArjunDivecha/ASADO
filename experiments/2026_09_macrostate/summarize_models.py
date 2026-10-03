"""Generate the fixed-contest comparison tables and charts from saved results."""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

B=Path(__file__).resolve().parent;O=B/'model_results';O.mkdir(exist_ok=True)
labels={'value_momentum':'Fixed value + momentum','market_only':'Learned market indicators',
 'primitives':'Linear: individual indicators','states':'Linear: economic states',
 'states_interactions':'Economic states + interactions','primitives_interactions':'Indicators + interactions',
 'trees_primitives':'Trees: individual indicators','trees_states':'Trees: economic states',
 'neural_primitives':'Neural: individual indicators','neural_states':'Neural: economic states',
 'market_masks':'Market + missing-data flags (diagnostic)'}
frames=[]
for stage in ['stage3','stage4','stage5']:
 d=pd.read_csv(B/stage/'results/scorecard.csv');d['stage']=stage;frames.append(d)
s=pd.concat(frames).drop_duplicates(['arm','hold_months'],keep='first')
s.to_csv(O/'combined_scorecard.csv',index=False)
order=list(labels)
pivot=s.pivot(index='arm',columns='hold_months',values='annualized_return').reindex(order)
fig,axes=plt.subplots(1,2,figsize=(13,7),layout='constrained')
for ax,hold in zip(axes,[1,12]):
 values=100*pivot[hold];ax.barh(range(len(order)),values,color=['#9babc0' if 'diagnostic' not in labels[a] else '#c08b50' for a in order])
 bench=float(s.loc[s.hold_months.eq(hold),'benchmark_annualized_return'].iloc[0])*100
 ax.axvline(bench,color='#222222',linestyle='--',label=f'Equal weight {bench:.2f}%')
 ax.set_yticks(range(len(order)),[labels[a] for a in order] if hold==1 else []);ax.invert_yaxis()
 for y,v in enumerate(values):ax.text(v+.08,y,f'{v:.2f}%',va='center',fontsize=8)
 ax.set_xlim(0,14.7);ax.set_xlabel('Annualized gross return (%)');ax.set_title(f'{hold}-month holdings');ax.legend(loc='lower right',fontsize=9)
fig.suptitle('MacroState: same 97 months, same 32–33 eligible markets\nJuly 2018–July 2026; monthly USD index-return proxy')
fig.savefig(O/'all_models.png',dpi=160);plt.close(fig)
fig,axes=plt.subplots(2,1,figsize=(11,8),layout='constrained')
for ax,hold,focus in zip(axes,[1,12],[['trees_primitives','primitives','value_momentum'],['states_interactions','market_masks','neural_states']]):
 curves={}
 for stage in ['stage3','stage4','stage5']:
  c=pd.read_csv(B/stage/f'results/curves_{hold}m.csv',parse_dates=['date']).set_index('date')
  for col in c:curves[col]=c[col]
 ax.plot(curves['equal_weight'],color='black',label='Equal weight',linewidth=2)
 for arm in focus:ax.plot(curves[arm],label=labels[arm])
 ax.set_title(f'{hold}-month holdings — selected comparisons; all arms in table');ax.set_ylabel('Wealth from $1');ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.savefig(O/'selected_curves.png',dpi=160);plt.close(fig)
lines=['# MacroState: first model results','',
'**Economic states plus two interactions lead the twelve-month comparison. Trees on individual indicators lead monthly rebalancing. The neural networks did not improve on those leaders.**','',
'The annual result is heavily tied to persistent US holdings and data-availability patterns. Treat this as a useful historical selection result with a limited demonstrated macro contribution, not proof that the model learned broad country transmission.','',
'## The results you asked for','',
'July 2018–July 2026: 97 monthly forecasts, 32–33 eligible market tokens, seven selected each month. All arms use identical dates and eligible markets. These are gross USD total-return index comparisons; no costs or statistical-significance gate.','',
'| Model | Monthly refreshed: annualized | Twelve-month holdings: annualized |','|---|---:|---:|',
'| Equal weight, same eligible markets | 8.95% | 9.19% |']
for arm in order:lines.append(f'| {labels[arm]} | {100*pivot.loc[arm,1]:.2f}% | {100*pivot.loc[arm,12]:.2f}% |')
lines += ['', 'The broader equal-weight benchmark, including markets without the required macro coverage, returned **9.12%** and **9.32%** respectively. The previous Stage 1–2 baseline started in 2006; its numbers are not comparable to this shorter shared model sample.', '',
'![All models](model_results/all_models.png)','',
'## What the comparison says','',
'- **Annual holdings:** states plus interactions returned 12.14%, against 9.19% equal weight, 7.04% fixed value/momentum, and 8.39% learned market-only. States without interactions returned 12.03%; the added terms made only a small difference.',
'- **Monthly refresh:** trees on individual indicators returned 12.85%, against 8.95% equal weight and 11.49% fixed value/momentum. Linear individual indicators returned 12.46%. Compressing inputs into states reduced this tree model’s monthly result to 7.34%.',
'- **Neural networks:** the fixed two-layer network returned 9.44%–9.74% with annual holdings and 9.77%–11.67% with monthly refresh. It did not beat the simpler leaders in this run. This is a result for these frozen settings, not a claim that neural networks can never help.', '',
'![Selected return curves](model_results/selected_curves.png)','',
'## The important diagnostic: why the annual result needs qualification','',
'The annual state-plus-interactions model selected **NASDAQ, U.S., US SmallCap and Denmark in all 97 forecast months**. Every new seven-market sleeve therefore put 42.9% into the three US tokens and another 14.3% into Denmark. Holdings drifted after purchase. National macro identity was grouped during training, but the agreed investment universe and portfolio still contain three US market sleeves.', '',
'A control specified **after seeing that pattern** used only the three market inputs and eleven missing-data flags—none of the observed macro values. It returned **11.57%** with annual holdings. The economic-state leader adds only **0.57 percentage points/year** beyond that control. The individual-indicator linear model, at 11.58%, is almost identical to the missingness control.', '',
'This does not prove every gain is spurious. It shows that data availability can act as a country label and explain much of the apparent advantage over a market-only model. Earlier scores remain unchanged; the diagnostic is clearly recorded as a follow-up, not disguised as an untouched preplanned test.', '',
'For the annual state/interactions model, total active final wealth was approximately **$0.488 per initial $1**. The combined US contribution was **+$0.628**, while all other markets together contributed **−$0.139**. Twelve markets had positive active contributions. This is arithmetic attribution, not a rerun of a portfolio excluding the US.', '',
'The monthly individual-indicator tree result was broader: **20 markets** contributed positively, and active contribution remained positive after subtracting the largest macro identity’s contribution. That is worth distinguishing from the annual leader’s concentration; it is still attribution rather than an independently refitted no-US strategy.', '',
'## Drawdowns and consistency','',
'| Comparison | Model max drawdown | Equal-weight max drawdown | Rolling 12M windows beating EW |','|---|---:|---:|---:|']
for arm,h in [('states_interactions',12),('trees_primitives',1),('neural_states',12)]:
 r=s[(s.arm==arm)&(s.hold_months==h)].iloc[0]
 lines.append(f'| {labels[arm]}, {h}M holdings | {100*r.max_drawdown:.2f}% | {100*r.benchmark_max_drawdown:.2f}% | {100*r.rolling_12m_outperformance_rate:.1f}% |')
lines += ['', 'Higher returns did not automatically mean lower risk. The annual leader lost 19.08% during 2022 against 11.12% for equal weight, and gained 20.81% in 2025 against 33.58%. It outperformed in five of seven complete calendar years (2019–2025). Rolling twelve-month win rates contain overlapping windows; they are descriptive consistency measures, not independent statistical trials.', '',
'## Exactly what ran','',
'All learned models forecast twelve-month USD returns relative to the decision-eligible equal-weight universe. They begin after 60 matured monthly training origins, then refit every July on expanding history: nine refits, with monthly predictions between fits. No future twelve-month outcome was used before its maturity date. Training gives equal total weight to dates and macro identities, split among duplicate market sleeves.', '',
'The linear contest used a fixed ridge penalty of 1.0. State construction groups the same primitives into growth, inflation, policy tightness and financial stress. Missing components receive a training-mean neutral value inside the fitted design, with explicit flags shared by macro representations; raw input gaps remain missing in the snapshot. Three market controls are included in both representations. The two explicit nonlinear terms are cheapness × improving growth and weak growth × tighter policy; the model estimates their return coefficients.', '',
'The automatic nonlinear contest used shallow histogram gradient-boosted trees (200 iterations, at most seven leaves/depth three) and a small ReLU neural network with layers of 16 and 8 neurons (300 fixed epochs). Primitive and state versions had the same training opportunity. Neural training used one fixed random seed; all 18 neural fits reached the predeclared epoch budget and emitted the expected iteration-limit warning. Losses and warnings are saved. No convergence or seed-stability claim is made, and no settings were changed to improve returns.', '',
'The twelve-month portfolio starts with twelve equal cash sleeves and invests one each month; maturing sleeves recycle their own NAV and other holdings drift. The same convention applies to its benchmark. Excluding the eleven partially invested months, the state/interactions comparison annualizes at **14.11% versus 10.67%**. Monthly selection is a separate portfolio expression, not compounded overlapping annual labels.', '',
'## Evidence, reproducibility and boundaries','',
'- [Stage 3 frozen protocol](stage3/protocol.json), [registration](stage3/registration.json), [scorecard](stage3/results/scorecard.csv), [predictions](stage3/results/predictions.csv), [yearly returns](stage3/results/calendar_returns.csv).',
'- [Nonlinear protocol](stage4/protocol.json), [registration](stage4/registration.json), [scorecard](stage4/results/scorecard.csv), [fit logs and warnings](stage4/results/fit_log.csv).',
'- [Post-result missingness protocol](stage5/protocol.json), [scorecard](stage5/results/scorecard.csv), [macro-value exclusion check](stage5/results/validation.json).',
'- [Combined scorecard](model_results/combined_scorecard.csv), per-country/identity contribution files in each results folder, and [model validation](MODEL_VALIDATION.json).', '',
'**36 automated tests and 15 end-to-end checks passed**, including repeatability of all saved linear/tree/neural forecasts, identical comparison rows, matured labels, real-data future-target perturbation, and identical benchmark calculations. The missingness diagnostic separately passes the same-sample and macro-value-invariance checks. Portfolio contribution reconciliation is asserted during every run.', '',
'Input histories remain conditional vendor-history reconstructions: fixed snapshots and causal code do not undo past vendor revisions. These are monthly index-return proxies, not executable next-session fills, and the universe is today’s configured market set. The nonlinear and missingness stages were designed after earlier results were seen, so this is a development sequence, not fresh confirmation. No production forecasting model, collection job or trading process was changed.', '',
'## What to pursue next','',
'Keep **individual-indicator trees for monthly selection** and **the simple state model for annual holdings** as the two practical candidates. Do not expand the neural architecture based on this run. The next useful comparison is a US-exposure-matched benchmark and a clearly declared restriction on duplicate US sleeves, alongside the missingness control. That would show how much improvement remains after matching the persistent US allocation, rather than adding more model complexity.', '',
'The annual model passes the original results-first comparison but has a modest incremental edge over its missingness control. The monthly tree result combines stronger return improvement with broader contribution. Both remain research candidates, not automatic deployment choices.']
(B/'MODEL_RESULTS.md').write_text('\n'.join(lines)+'\n')
print('Wrote MODEL_RESULTS.md, combined scorecard, and two charts.')
