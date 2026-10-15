#!/usr/bin/env bash
# =============================================================================
# run_all_experiments.sh — Submit all paper experiment conditions to Rosie
#
# Usage:
#   REPO_ROOT=$(pwd) ./rosie/run_all_experiments.sh [condition_filter]
#
# Examples:
#   REPO_ROOT=$(pwd) ./rosie/run_all_experiments.sh          # all conditions
#   REPO_ROOT=$(pwd) ./rosie/run_all_experiments.sh full     # just full seeds
#   REPO_ROOT=$(pwd) ./rosie/run_all_experiments.sh sparse   # just sparse seeds
#
# At 30s/interval, 2 days = 5760 intervals.
# For 10k intervals, submit twice (the second run will resume from checkpoint).
# =============================================================================

# Parse arguments: [condition_filter] [--fresh]
FILTER="all"
FRESH=0

for arg in "$@"; do
    if [ "$arg" == "--fresh" ]; then
        FRESH=1
    elif [ "$arg" != "" ]; then
        FILTER="$arg"
    fi
done

if [ -z "${REPO_ROOT:-}" ]; then
    echo "ERROR: REPO_ROOT is not set."
    echo "Run with:  REPO_ROOT=\$(pwd) ./rosie/run_all_experiments.sh [filter] [--fresh]"
    exit 1
fi

LAUNCHER="$REPO_ROOT/rosie/run_experiment.sh"
FRESH_ARG=""
if [ "$FRESH" -eq 1 ]; then FRESH_ARG="--fresh"; fi

# ── Experiment schedule: condition seeds ─────────────────────────────────────
declare -a SCHEDULE=(
    "full 3"
    "random 3"
    "sparse 3"
    "no_timeout 2"
    "flat_action 2"
)

echo "============================================="
echo "  Cambium — Batch Experiment Submission"
echo "  Filter: ${FILTER}"
if [ "$FRESH" -eq 1 ]; then echo "  MODE:   CLEAN SLATE (Fresh Start ALL)"; fi
echo "============================================="
echo ""

TOTAL=0
for entry in "${SCHEDULE[@]}"; do
    COND=$(echo "$entry" | awk '{print $1}')
    NSEEDS=$(echo "$entry" | awk '{print $2}')

    # Apply filter
    if [ "$FILTER" != "all" ] && [ "$FILTER" != "$COND" ]; then
        continue
    fi

    for SEED in $(seq 1 "$NSEEDS"); do
        echo "  Submitting: $COND seed $SEED ${FRESH_ARG}"
        REPO_ROOT="$REPO_ROOT" bash "$LAUNCHER" "$COND" "$SEED" 0 "$FRESH_ARG"
        TOTAL=$((TOTAL + 1))
        sleep 2
    done
done

echo ""
echo "Submitted $TOTAL jobs. Monitor with squeue -u \$USER"
