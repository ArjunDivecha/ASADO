#!/bin/zsh
# T2-only ablation: the default model on the 91 T2 factors only (no GDELT, Bloomberg, IMF, EPU, BIS, GPR). Log: results/t2only_launch.log
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model" || exit 1
for seed in 0 1000 2000; do
  echo "=== $(date '+%F %T') t2only_s$seed"
  .venv/bin/python walk_forward.py --factor-set factor_set_v3_t2only.json --seeds 30 --seed $seed --tag t2only_s$seed 2>&1 | grep -v Warning | grep "panel:\|OUT-OF-SAMPLE \[buffer\|done in\|Traceback\|Error" | cut -c1-170
done
echo "=== $(date '+%F %T') T2ONLY DONE"
