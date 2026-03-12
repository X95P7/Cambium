#!/bin/bash
################################################################################
# Cambium RL Training on Rosie
#
# Starts the Minecraft server, FastAPI backend (GPU), and N headless clients
# all on a single node.
#
# Usage:
#   sbatch rosie/cambium.sbatch              # default 4 bots
#   NUM_BOTS=6 sbatch rosie/cambium.sbatch   # 6 bots
################################################################################

#SBATCH --job-name=cambium-rl
#SBATCH --partition=teaching
#SBATCH --nodes=1
#SBATCH --gres=gpu:t4:1
#SBATCH --cpus-per-gpu=8
#SBATCH --time=1-0:0
#SBATCH --output=rosie/logs/cambium_%j.log
#SBATCH --error=rosie/logs/cambium_%j.err

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGES_DIR="$REPO_ROOT/rosie/images"
VENV_DIR="$REPO_ROOT/rosie/.venv"
LOGS_DIR="$REPO_ROOT/rosie/logs"
SERVER_DIR="$REPO_ROOT/server"

NUM_BOTS="${NUM_BOTS:-4}"
MC_PORT=25565
RCON_PORT=25575
BACKEND_PORT=8000
NODE_HOSTNAME=$(hostname)

mkdir -p "$LOGS_DIR"

echo "============================================="
echo "  Cambium RL Training - Job $SLURM_JOB_ID"
echo "============================================="
echo "  Node:       $NODE_HOSTNAME"
echo "  Bots:       $NUM_BOTS"
echo "  GPU:        $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
echo "  Start time: $(date)"
echo "============================================="
echo ""
echo "  >>> Run BOTH of these on your local machine to connect: <<<"
echo ""
echo "  1) Dashboard + MC server tunnel (one command):"
echo "     ssh -L ${BACKEND_PORT}:${NODE_HOSTNAME}:${BACKEND_PORT} -L ${MC_PORT}:${NODE_HOSTNAME}:${MC_PORT} \$USER@rosie.msoe.edu"
echo ""
echo "  2) Then open:"
echo "     Dashboard:  http://localhost:${BACKEND_PORT}"
echo "     Minecraft:  localhost:${MC_PORT}  (add as server in MC 1.8.9)"
echo ""
echo "  >>> Logs (run on Rosie): <<<"
echo "     tail -f rosie/logs/cambium_${SLURM_JOB_ID}.log"
echo "     tail -f rosie/logs/backend_${SLURM_JOB_ID}.log"
echo "     tail -f rosie/logs/Bot1_${SLURM_JOB_ID}.log"
echo ""
echo "============================================="

module load cuda/current openmpi/current singularity/current StdEnv

# ---------- Verify setup ----------
if [ ! -f "$IMAGES_DIR/minecraft-server-java8.sif" ]; then
    echo "ERROR: Minecraft server image not found. Run 'bash rosie/setup.sh' first."
    exit 1
fi
if [ ! -f "$IMAGES_DIR/cambium-headlessmc.sif" ]; then
    echo "ERROR: HeadlessMC image not found. Run 'bash rosie/setup.sh' first."
    exit 1
fi
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "ERROR: Python venv not found. Run 'bash rosie/setup.sh' first."
    exit 1
fi

# Track background PIDs for cleanup
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

# Copy server data (world, properties, etc.) if not already present
if [ ! -f "$MC_DATA_DIR/server.properties" ]; then
    echo "  Copying server data from $SERVER_DIR..."
    cp -r "$SERVER_DIR"/* "$MC_DATA_DIR/" 2>/dev/null || true
fi

singularity exec \
    --bind "$MC_DATA_DIR:/data" \
    --env EULA=TRUE \
    --env TYPE=FORGE \
    --env VERSION=1.8.9 \
    --env MEMORY=8G \
    --env ENABLE_RCON=TRUE \
    --env RCON_PASSWORD=minecraft \
    "$IMAGES_DIR/minecraft-server-java8.sif" \
    /start > "$LOGS_DIR/mc-server_${SLURM_JOB_ID}.log" 2>&1 &
MC_PID=$!
PIDS+=("$MC_PID")

echo "  MC server PID: $MC_PID"
echo "  Waiting for MC server to be ready on port $MC_PORT..."

TIMEOUT=180
ELAPSED=0
while ! nc -z localhost "$MC_PORT" 2>/dev/null; do
    if ! kill -0 "$MC_PID" 2>/dev/null; then
        echo "  ERROR: MC server process died. Check $LOGS_DIR/mc-server_${SLURM_JOB_ID}.log"
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
#  2. Start FastAPI Backend (with GPU)
# ================================================================
echo "[2/$((NUM_BOTS + 2))] Starting FastAPI backend..."

. "$VENV_DIR/bin/activate"

RCON_HOST=localhost \
RCON_PORT=$RCON_PORT \
RCON_PASSWORD=minecraft \
CAMBIUM_DEVICE=cuda \
    python -m uvicorn main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
    --app-dir "$REPO_ROOT/backend" \
    > "$LOGS_DIR/backend_${SLURM_JOB_ID}.log" 2>&1 &
BACKEND_PID=$!
PIDS+=("$BACKEND_PID")

echo "  Backend PID: $BACKEND_PID"
echo "  Waiting for backend on port $BACKEND_PORT..."

ELAPSED=0
while ! nc -z localhost "$BACKEND_PORT" 2>/dev/null; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "  ERROR: Backend process died. Check $LOGS_DIR/backend_${SLURM_JOB_ID}.log"
        exit 1
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ "$ELAPSED" -ge 60 ]; then
        echo "  ERROR: Backend did not start within 60s"
        exit 1
    fi
done
echo "  Backend is ready!"

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
    mkdir -p "$BOT_RUN_DIR"

    singularity run \
        --bind "$BOT_RUN_DIR:/opt/hmc/run" \
        --env SERVER="$MC_SERVER" \
        --env USERNAME="$BOT_NAME" \
        --env EMAIL= \
        --env PASSWORD= \
        --env USE_XVFB=false \
        --env HEADLESSMC_COMMAND="--jvm -Djava.awt.headless=true --jvm -Dcambium.api.url=${API_URL}" \
        "$IMAGES_DIR/cambium-headlessmc.sif" \
        > "$LOGS_DIR/${BOT_NAME}_${SLURM_JOB_ID}.log" 2>&1 &
    BOT_PID=$!
    PIDS+=("$BOT_PID")
    echo "  $BOT_NAME PID: $BOT_PID"
done

echo ""
echo "============================================="
echo "  All $NUM_BOTS bots launched!"
echo "============================================="
echo "  Logs:"
echo "    MC server:  $LOGS_DIR/mc-server_${SLURM_JOB_ID}.log"
echo "    Backend:    $LOGS_DIR/backend_${SLURM_JOB_ID}.log"
echo "    Bot logs:   $LOGS_DIR/Bot*_${SLURM_JOB_ID}.log"
echo ""
echo "  SSH tunnel (run on your local machine):"
echo "    ssh -L ${BACKEND_PORT}:${NODE_HOSTNAME}:${BACKEND_PORT} -L ${MC_PORT}:${NODE_HOSTNAME}:${MC_PORT} \$USER@rosie.msoe.edu"
echo ""
echo "  Then open:"
echo "    Dashboard:  http://localhost:${BACKEND_PORT}"
echo "    Minecraft:  localhost:${MC_PORT}  (Minecraft 1.8.9 client)"
echo "============================================="

# Wait for all background processes -- job stays alive until SLURM kills it
# or all processes exit
wait
