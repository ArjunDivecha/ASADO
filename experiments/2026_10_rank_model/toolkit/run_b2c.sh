#!/bin/zsh
# B2c driver: multi-task net at calibrated lambdas 0.005 and 0.05, three seed draws. Log: results/b2c_launch.log
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model" || exit 1
for seed in 0 1000 2000; do
  for arm in "mt0005:0.005" "mt005:0.05"; do
    tag=${arm%%:*}; lam=${arm#*:}
    echo "=== $(date '+%F %T') ${tag}_s$seed  (lambda $lam)"
    .venv/bin/python walk_forward.py --aux-lambda $lam --seeds 30 --seed $seed --tag ${tag}_s$seed 2>&1 | grep -v Warning | grep "OUT-OF-SAMPLE \[buffer\|done in\|Traceback\|Error" | cut -c1-160
  done
done
echo "=== $(date '+%F %T') B2C DONE"
