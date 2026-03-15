#!/bin/bash
################################################################################
# Cambium RL Baseline Experiment
#
# Identical to cambium.sbatch but runs in BASELINE mode:
#   - No model auto-resume (random initial weights)
#   - No backpropagation (no training)
#   - All metrics still logged (rewards, events, TPS)
#   - Log files tagged with "_baseline" suffix for easy identification
#
# Usage:
#   REPO_ROOT=$(pwd) sbatch rosie/cambium-baseline.sbatch
################################################################################

#SBATCH --job-name=cambium-baseline
#SBATCH --partition=teaching
#SBATCH --nodes=1
#SBATCH --gres=gpu:t4:1
#SBATCH --cpus-per-gpu=16
#SBATCH --mem=64G
#SBATCH --time=0-1:0
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null

set -euo pipefail

if [ -z "${REPO_ROOT:-}" ]; then
    echo "ERROR: REPO_ROOT is not set."
    echo "Submit with:  REPO_ROOT=\$(pwd) sbatch rosie/cambium-baseline.sbatch"
    exit 1
fi

IMAGES_DIR="$REPO_ROOT/rosie/images"
VENV_DIR="$REPO_ROOT/rosie/.venv"
HMC_DIR="$REPO_ROOT/rosie/hmc"
RUN_DIR="$REPO_ROOT/rosie/logs/${SLURM_JOB_ID}_baseline"
SERVER_DIR="$REPO_ROOT/server"

NUM_BOTS="${NUM_BOTS:-8}"
MC_PORT="${MC_PORT:-33565}"
RCON_PORT="${RCON_PORT:-33575}"
BACKEND_PORT="${BACKEND_PORT:-33800}"
NODE_HOSTNAME=$(hostname)

mkdir -p "$RUN_DIR"

MAIN_LOG="$RUN_DIR/cambium.log"
exec > "$MAIN_LOG" 2>&1

echo "============================================="
echo "  Cambium BASELINE Experiment - Job $SLURM_JOB_ID"
echo "============================================="
echo "  Node:       $NODE_HOSTNAME"
echo "  Bots:       $NUM_BOTS"
echo "  Mode:       BASELINE (no training, random policy)"
echo "  GPU:        $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
echo "  Start time: $(date)"
echo "  Duration:   1 hour"
echo "============================================="
echo ""
echo "  >>> SSH tunnel: <<<"
echo "     ssh -L ${BACKEND_PORT}:${NODE_HOSTNAME}:${BACKEND_PORT} -L ${MC_PORT}:${NODE_HOSTNAME}:${MC_PORT} msoe-hpc"
echo ""
echo "============================================="

module load cuda/current openmpi/current singularity/current StdEnv

# ---------- Verify setup ----------
if [ ! -f "$IMAGES_DIR/minecraft-server-java8.sif" ]; then
    echo "ERROR: Minecraft server image not found. Run 'bash rosie/setup.sh' first."
    exit 1
fi
if [ ! -f "$IMAGES_DIR/java8-base.sif" ]; then
    echo "ERROR: Java 8 base image not found. Run 'bash rosie/setup.sh' first."
    exit 1
fi
if [ ! -d "$HMC_DIR/HeadlessMC" ]; then
    echo "ERROR: HeadlessMC not set up. Run 'bash rosie/setup.sh' first."
    exit 1
fi
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "ERROR: Python venv not found. Run 'bash rosie/setup.sh' first."
    exit 1
fi

PIDS=()
cleanup() {
    echo ""
    echo "[CLEANUP] Shutting down all processes..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "  Stopping PID $pid"
            kill "$pid" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null || true
    echo "[CLEANUP] Done."
}
trap cleanup EXIT INT TERM

# ================================================================
#  1. Start Minecraft Server
# ================================================================
echo "[1/$((NUM_BOTS + 2))] Starting Minecraft server..."

MC_DATA_DIR="$REPO_ROOT/rosie/mc-data"
mkdir -p "$MC_DATA_DIR"

if [ ! -f "$MC_DATA_DIR/server.properties" ]; then
    echo "  Copying server data from $SERVER_DIR..."
    cp -r "$SERVER_DIR"/* "$MC_DATA_DIR/" 2>/dev/null || true
fi

singularity exec \
    --bind "$MC_DATA_DIR:/data" \
    --env EULA=TRUE \
    --env TYPE=FORGE \
    --env VERSION=1.8.9 \
    --env MEMORY=6G \
    --env SERVER_PORT="$MC_PORT" \
    --env ENABLE_RCON=TRUE \
    --env RCON_PORT="$RCON_PORT" \
    --env RCON_PASSWORD=minecraft \
    "$IMAGES_DIR/minecraft-server-java8.sif" \
    /start > "$RUN_DIR/mc-server.log" 2>&1 &
MC_PID=$!
PIDS+=("$MC_PID")

echo "  MC server PID: $MC_PID"
echo "  Waiting for MC server to be ready on port $MC_PORT..."

TIMEOUT=180
ELAPSED=0
while ! nc -z localhost "$MC_PORT" 2>/dev/null; do
    if ! kill -0 "$MC_PID" 2>/dev/null; then
        echo "  ERROR: MC server process died. Check $RUN_DIR/mc-server.log"
        exit 1
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "  ERROR: MC server did not start within ${TIMEOUT}s"
        exit 1
    fi
    echo "  Waited ${ELAPSED}s..."
done
echo "  MC server is ready!"

# ================================================================
#  2. Start FastAPI Backend -- BASELINE MODE
# ================================================================
echo "[2/$((NUM_BOTS + 2))] Starting FastAPI backend (BASELINE mode)..."

. "$VENV_DIR/bin/activate"

RCON_HOST=localhost \
RCON_PORT=$RCON_PORT \
RCON_PASSWORD=minecraft \
CAMBIUM_DEVICE=cuda \
CAMBIUM_EXPERIMENT=baseline \
CAMBIUM_NO_TRAIN=1 \
    python -m uvicorn main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
    --app-dir "$REPO_ROOT/backend" \
    --no-access-log \
    > "$RUN_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
PIDS+=("$BACKEND_PID")

echo "  Backend PID: $BACKEND_PID"
echo "  Waiting for backend on port $BACKEND_PORT..."

ELAPSED=0
while ! nc -z localhost "$BACKEND_PORT" 2>/dev/null; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "  ERROR: Backend process died. Check $RUN_DIR/backend.log"
        exit 1
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ "$ELAPSED" -ge 60 ]; then
        echo "  ERROR: Backend did not start within 60s"
        exit 1
    fi
done
echo "  Backend is ready (BASELINE mode: no training, random policy)!"

# ================================================================
#  3. Start Headless Minecraft Clients
# ================================================================
API_URL="http://localhost:${BACKEND_PORT}"
MC_SERVER="localhost:${MC_PORT}"

for i in $(seq 1 "$NUM_BOTS"); do
    BOT_NAME="Bot${i}"
    STEP=$((i + 2))
    echo "[$STEP/$((NUM_BOTS + 2))] Starting headless client: $BOT_NAME..."

    BOT_RUN_DIR="$REPO_ROOT/rosie/bot-data/${BOT_NAME}"
    mkdir -p "$BOT_RUN_DIR/mods"

    cp -n "$REPO_ROOT"/headlessmc/mods/* "$BOT_RUN_DIR/mods/" 2>/dev/null || true

    REPO_ROOT="$REPO_ROOT" \
    BOT_RUN_DIR="$BOT_RUN_DIR" \
    SERVER="$MC_SERVER" \
    USERNAME="$BOT_NAME" \
    HMC_VERSION="2.5.1" \
    MC_VERSION="1.8.9" \
    CAMBIUM_API_URL="$API_URL" \
        python "$REPO_ROOT/rosie/rosie-bot-launcher.py" \
        > "$RUN_DIR/${BOT_NAME}.log" 2>&1 &
    BOT_PID=$!
    PIDS+=("$BOT_PID")
    echo "  $BOT_NAME PID: $BOT_PID"

    if [ "$i" -lt "$NUM_BOTS" ]; then
        echo "  Waiting 15s before next bot..."
        sleep 15
    fi
done

echo ""
echo "============================================="
echo "  BASELINE: All $NUM_BOTS bots launched!"
echo "  No training will occur. Collecting reward"
echo "  data under random policy for ~1 hour."
echo "============================================="
echo "  Logs: rosie/logs/${SLURM_JOB_ID}_baseline/"
echo "  Data: backend/logs/training_*_baseline.csv"
echo "        backend/logs/events_*_baseline.log"
echo "============================================="

wait
