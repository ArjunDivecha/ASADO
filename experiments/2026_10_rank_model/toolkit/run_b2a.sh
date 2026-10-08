#!/bin/zsh
# B2a driver: default net on the v3_heads panel, three seed draws. Log: results/b2a_launch.log
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model" || exit 1
P="/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_heads/feature_panel_v3_heads.parquet"
for seed in 0 1000 2000; do
  echo "=== $(date '+%F %T') heads_s$seed"
  .venv/bin/python walk_forward.py --panel "$P" --factor-set factor_set_v3_heads.json --seeds 30 --seed $seed --tag heads_s$seed 2>&1 | grep -v Warning | grep "panel:\|OUT-OF-SAMPLE \[buffer\|done in\|Traceback\|Error"
done
echo "=== $(date '+%F %T') B2A DONE"
