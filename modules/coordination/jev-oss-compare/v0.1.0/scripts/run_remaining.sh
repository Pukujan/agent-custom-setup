#!/usr/bin/env bash
set -uo pipefail
REPO="${HOME}/agent-custom-setup"
SCRIPTS="${REPO}/modules/coordination/jev-oss-compare/v0.1.0/scripts"
LOGDIR="${HOME}/acs-bench-work"
export CGM_ROOT="${HOME}/content-generation-modules"
export ACS_JEV_LIVE=1
export ACS_JEV_MODEL="${ACS_JEV_MODEL:-typesafe/jev-1.13}"
mkdir -p "$LOGDIR"
cd "$REPO"

# ensure CGM
if [ ! -f "$CGM_ROOT/scripts/verify_hsw_applied.py" ]; then
  git clone --depth 1 https://github.com/Pukujan/content-generation-modules.git "$CGM_ROOT"
fi
echo "CGM_ROOT=$CGM_ROOT"

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
  return 0
}

# Remaining after A-acs completed (JSON saved; HTML may need re-append)
# Re-run A acs quickly only if FORCE_A_ACS=1; else continue
if [ "${FORCE_A_ACS:-0}" = "1" ]; then
  run_one A acs
else
  echo "SKIP A acs (already have ftx-a-acs JSON); will re-append HTML via helper if needed"
  python3 "$LOGDIR/reappend_latest.py" A acs || true
fi
run_one A claude
run_one B acs
run_one B claude
echo "ALL_DONE $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "${LOGDIR}/ftx-all.log"
