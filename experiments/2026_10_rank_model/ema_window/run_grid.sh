#!/bin/zsh
# Driver for the rolling-vs-EMA grid (ema_window/PREREG.md). Runs 15 walk-forwards sequentially, each on all cores.
# Log: results/ema_grid_launch.log ; heartbeat per run in its own results/walk_*_<tag>/heartbeat.json
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model" || exit 1
for seed in 0 1000 2000; do
  echo "=== $(date '+%F %T') exp_s$seed"; .venv/bin/python walk_forward.py --window 0 --seeds 30 --seed $seed --tag exp_s$seed 2>&1 | grep -v Warning | grep "OUT-OF-SAMPLE\|done in\|Traceback\|Error"
  for hl in 24 36 60 120; do
    echo "=== $(date '+%F %T') ema${hl}_s$seed"; .venv/bin/python walk_forward.py --window 0 --half-life $hl --seeds 30 --seed $seed --tag ema${hl}_s$seed 2>&1 | grep -v Warning | grep "OUT-OF-SAMPLE\|done in\|Traceback\|Error"
  done
done
echo "=== $(date '+%F %T') GRID DONE"
