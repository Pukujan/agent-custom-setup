#!/usr/bin/env bash
set -euo pipefail
REPO="${HOME}/agent-custom-setup"
SCRIPTS="${REPO}/modules/coordination/jev-oss-compare/v0.1.0/scripts"
LOGDIR="${HOME}/acs-bench-work"
mkdir -p "$LOGDIR"
cd "$REPO"
export ACS_JEV_LIVE=1
export ACS_JEV_MODEL="${ACS_JEV_MODEL:-typesafe/jev-1.13}"
# Do NOT bash-source configs.env (BOM). Python loader in the script reads .env + configs.env.

run_one () {
  local abl="$1" stream="$2"
  local log="${LOGDIR}/ftx-${abl}-${stream}.log"
  echo "==== START ablation=${abl} stream=${stream} $(date -u +%Y-%m-%dT%H:%M:%SZ) ====" | tee -a "$log"
  python3 "$SCRIPTS/full_tx_ab_walkforward.py" \
    --ablation "$abl" \
    --stream "$stream" \
    --live \
    --workers 16 \
    --append-html \
    --claude-jsonl-dir "$HOME/claude-hades-v2-jsonl" \
    2>&1 | tee -a "$log"
  local rc=${PIPESTATUS[0]}
  echo "==== DONE ablation=${abl} stream=${stream} rc=${rc} $(date -u +%Y-%m-%dT%H:%M:%SZ) ====" | tee -a "$log"
  return $rc
}

run_one A acs
run_one A claude
run_one B acs
run_one B claude
echo "ALL_DONE $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "${LOGDIR}/ftx-all.log"
