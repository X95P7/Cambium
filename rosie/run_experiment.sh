#!/usr/bin/env bash
# =============================================================================
# run_experiment.sh — Launch one Cambium experiment condition × seed on Rosie
#
# Usage:
#   REPO_ROOT=$(pwd) ./rosie/run_experiment.sh <condition> <seed> [max_intervals]
#
# Conditions:
#   full        — Full model with shaped rewards (default)
#   random      — Random baseline (no training)
#   sparse      — Sparse reward only (no shaping rewards)
#   no_timeout  — Full model minus episode timeouts (continuous horizon)
#   flat_action — Full model with flat 2880-action categorical head
#
# Example:
#   REPO_ROOT=$(pwd) ./rosie/run_experiment.sh full 1
#   REPO_ROOT=$(pwd) ./rosie/run_experiment.sh sparse 2 5760
#
# Port assignments (to avoid collisions when running in parallel):
#   Port base offsets per condition: full=0, random=100, sparse=200,
#                                    no_timeout=300, flat_action=400
#   Within condition, seed offsets by (seed-1)*10
#   MC_PORT    = 33565 + condition_offset + seed_offset
#   RCON_PORT  = 33575 + condition_offset + seed_offset
#   BACKEND_PORT = 33800 + condition_offset + seed_offset
# =============================================================================

set -euo pipefail

# Default values
CONDITION="full"
SEED="1"
MAX_INTERVALS="0"
FRESH=0

# Improved argument parsing
args=()
for arg in "$@"; do
    if [ "$arg" == "--fresh" ]; then
        FRESH=1
    else
        args+=("$arg")
    fi
done

# Assign positional arguments from filtered list
CONDITION="${args[0]:-full}"
SEED="${args[1]:-1}"
MAX_INTERVALS="${args[2]:-0}"

if [ -z "${REPO_ROOT:-}" ]; then
    echo "ERROR: REPO_ROOT is not set."
    echo "Run with:  REPO_ROOT=\$(pwd) ./rosie/run_experiment.sh <condition> <seed> [--fresh]"
    exit 1
fi

# ── Port and Tag calculation (Move up for fresh cleanup) ──
PORT_OFFSET=0
case "$CONDITION" in
    full)        PORT_OFFSET=0   ; NO_TRAIN=0 ; REWARD_MODE=shaped ; NO_TIMEOUT=0 ; FLAT_ACTION=0 ; SELF_PLAY=1 ;;
    random)      PORT_OFFSET=100 ; NO_TRAIN=1 ; REWARD_MODE=shaped ; NO_TIMEOUT=0 ; FLAT_ACTION=0 ; SELF_PLAY=0 ;;
    sparse)      PORT_OFFSET=200 ; NO_TRAIN=0 ; REWARD_MODE=sparse ; NO_TIMEOUT=0 ; FLAT_ACTION=0 ; SELF_PLAY=1 ;;
    no_timeout)  PORT_OFFSET=300 ; NO_TRAIN=0 ; REWARD_MODE=shaped ; NO_TIMEOUT=1 ; FLAT_ACTION=0 ; SELF_PLAY=1 ;;
    flat_action) PORT_OFFSET=400 ; NO_TRAIN=0 ; REWARD_MODE=shaped ; NO_TIMEOUT=0 ; FLAT_ACTION=1 ; SELF_PLAY=1 ;;
    *) echo "ERROR: Unknown condition '$CONDITION'"; exit 1 ;;
esac

SEED_OFFSET=$(( (SEED - 1) * 20 ))
MC_PORT=$(( 33565 + PORT_OFFSET + SEED_OFFSET ))
RCON_PORT=$(( 33575 + PORT_OFFSET + SEED_OFFSET ))
BACKEND_PORT=$(( 33800 + PORT_OFFSET + SEED_OFFSET ))
RUN_TAG="${CONDITION}_seed${SEED}"

# ── Fresh Start Logic ──────────────────────────────────────────────────
if [ "$FRESH" -eq 1 ]; then
    RUN_DIR="${REPO_ROOT}/backend/runs/${RUN_TAG}"
    if [ -d "$RUN_DIR" ]; then
        echo " [FRESH] Deleting existing run directory: $RUN_DIR"
        rm -rf "$RUN_DIR"
    fi
fi

# Default eval opponent: the March 24 reference model (can be overridden)
EVAL_OPPONENT="${CAMBIUM_EVAL_OPPONENT:-${REPO_ROOT}/backend/models/model_20260324_103625_IT_WOKRS.pt}"

echo "============================================="
echo "  Submitting experiment"
echo "  Condition:   $CONDITION"
echo "  Seed:        $SEED"
echo "  Run tag:     $RUN_TAG"
echo "  Max ivtervals: ${MAX_INTERVALS:-unlimited}"
echo "  Ports:       MC=$MC_PORT  RCON=$RCON_PORT  Backend=$BACKEND_PORT"
if [ "$FRESH" -eq 1 ]; then echo "  MODE:        CLEAN SLATE (Fresh Start)"; fi
echo "============================================="

NUM_BOTS=8 \
REPO_ROOT="$REPO_ROOT" \
MC_PORT="$MC_PORT" \
RCON_PORT="$RCON_PORT" \
BACKEND_PORT="$BACKEND_PORT" \
CAMBIUM_RUN_TAG="$RUN_TAG" \
CAMBIUM_SEED="$SEED" \
CAMBIUM_NO_TRAIN="$NO_TRAIN" \
CAMBIUM_REWARD_MODE="$REWARD_MODE" \
CAMBIUM_NO_TIMEOUT="$NO_TIMEOUT" \
CAMBIUM_FLAT_ACTION="$FLAT_ACTION" \
CAMBIUM_SELF_PLAY="$SELF_PLAY" \
CAMBIUM_MAX_INTERVALS="$MAX_INTERVALS" \
CAMBIUM_EVAL_OPPONENT="$EVAL_OPPONENT" \
CAMBIUM_FORCE_FRESH="$FRESH" \
    sbatch rosie/cambium.sbatch

echo "  Submitted. Monitor with squeue -u \$USER"
