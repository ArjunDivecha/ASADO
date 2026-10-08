#!/bin/zsh
# B2b driver: multi-task net, three arms x three seed draws, full v3_clean panel. Log: results/b2b_launch.log
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model" || exit 1
for seed in 0 1000 2000; do
  for arm in "mt05:--aux-lambda 0.5" "mt2:--aux-lambda 2" "mt2w:--aux-lambda 2 --aux-warmup 30"; do
    tag=${arm%%:*}; flags=${arm#*:}
    echo "=== $(date '+%F %T') ${tag}_s$seed  ($flags)"
    .venv/bin/python walk_forward.py ${=flags} --seeds 30 --seed $seed --tag ${tag}_s$seed 2>&1 | grep -v Warning | grep "OUT-OF-SAMPLE \[buffer\|done in\|Traceback\|Error" | cut -c1-160
  done
done
echo "=== $(date '+%F %T') B2B DONE"
