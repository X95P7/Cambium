#!/bin/bash
################################################################################
# Cambium RL Training on Rosie
#
# Starts the Minecraft server, FastAPI backend (GPU), and N headless clients
# all on a single node.
#
# Usage (must set REPO_ROOT so paths resolve on the compute node):
#   REPO_ROOT=$(pwd) sbatch rosie/cambium.sbatch
#   REPO_ROOT=$(pwd) NUM_BOTS=6 sbatch rosie/cambium.sbatch
################################################################################

#SBATCH --job-name=cambium-${CAMBIUM_RUN_TAG:-rl}
#SBATCH --partition=teaching
#SBATCH --nodes=1
#SBATCH --gres=gpu:t4:1
# Use more CPU cores per GPU so bots + backend have more headroom.
# 32 should fit comfortably on T4 teaching nodes (≈72 logical CPUs total).
# Adjust down if jobs sit pending for lack of resources.
#SBATCH --cpus-per-gpu=36
#SBATCH --mem=64G
#SBATCH --time=1-0:0
# SBATCH stdout/stderr (for early failures before RUN_DIR exists; main log is RUN_DIR/cambium.log)
# Use relative path from cwd at submit time (repo root).
#SBATCH --output=rosie/logs/slurm-%j.out
#SBATCH --error=rosie/logs/slurm-%j.err

set -euo pipefail

# Ensure log dir exists so SLURM can write slurm-JOBID.out/err
mkdir -p rosie/logs

if [ -z "${REPO_ROOT:-}" ]; then
    echo "ERROR: REPO_ROOT is not set."
    echo "Submit with:  REPO_ROOT=\$(pwd) sbatch rosie/cambium.sbatch"
    exit 1
fi

IMAGES_DIR="$REPO_ROOT/rosie/images"
VENV_DIR="$REPO_ROOT/rosie/.venv"
HMC_DIR="$REPO_ROOT/rosie/hmc"
RUN_DIR="$REPO_ROOT/rosie/logs/${SLURM_JOB_ID}"
SERVER_DIR="$REPO_ROOT/server"

NUM_BOTS="${NUM_BOTS:-8}"
MC_PORT="${MC_PORT:-33565}"
RCON_PORT="${RCON_PORT:-33575}"
BACKEND_PORT="${BACKEND_PORT:-33800}"
NODE_HOSTNAME=$(hostname)

mkdir -p "$RUN_DIR"

# Redirect all script output to our own log file (SLURM output goes to /dev/null)
MAIN_LOG="$RUN_DIR/cambium.log"
exec > "$MAIN_LOG" 2>&1

echo "============================================="
echo "  Cambium RL Training - Job $SLURM_JOB_ID"
echo "============================================="
echo "  Node:       $NODE_HOSTNAME"
echo "  Bots:       $NUM_BOTS"
echo "  Run tag:    ${CAMBIUM_RUN_TAG:-default}"
echo "  Seed:       ${CAMBIUM_SEED:-0}"
echo "  Mode:       ${CAMBIUM_REWARD_MODE:-shaped} | no_timeout=${CAMBIUM_NO_TIMEOUT:-0} | flat=${CAMBIUM_FLAT_ACTION:-0}"
echo "  GPU:        $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
echo "  Start time: $(date)"
echo "============================================="
echo ""
echo "  >>> Run BOTH of these on your local machine to connect: <<<"
echo ""
echo "  1) Dashboard + MC server tunnel (one command):"
echo "     ssh -L ${BACKEND_PORT}:${NODE_HOSTNAME}:${BACKEND_PORT} -L ${MC_PORT}:${NODE_HOSTNAME}:${MC_PORT} msoe-hpc"
echo ""
echo "  2) Then open:"
echo "     Dashboard:  http://localhost:${BACKEND_PORT}"
echo "     Minecraft:  localhost:${MC_PORT}  (add as server in MC 1.8.9)"
echo ""
echo "  >>> Logs (run on Rosie): <<<"
echo "     tail -f rosie/logs/${SLURM_JOB_ID}/cambium.log"
echo "     tail -f rosie/logs/${SLURM_JOB_ID}/backend.log"
echo "     tail -f rosie/logs/${SLURM_JOB_ID}/Bot1.log"
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

# Track background PIDs for cleanup
PIDS=()
cleanup() {
    echo ""
    echo "[CLEANUP] Shutting down session processes..."
    # 1. Send SIGTERM to all tracked PIDs
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "  Stopping PID $pid"
            kill "$pid" 2>/dev/null || true
        fi
    done
    # 2. Short wait for graceful exit
    sleep 5
    # 3. Force kill (-9) any survivors
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "  Force-killing PID $pid (-9)"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    # 4. Kill any leftover bot-launcher or singularity processes from THIS job
    #    so they don't auto-reconnect and race with the next MC server startup.
    pkill -9 -u "$USER" -f "rosie-bot-launcher.py" 2>/dev/null || true
    pkill -9 -u "$USER" -f "java8-base.sif" 2>/dev/null || true
    pkill -9 -u "$USER" -f "minecraft-server-java8" 2>/dev/null || true
    pkill -9 -u "$USER" -f "forge.*\.jar" 2>/dev/null || true
    pkill -9 -u "$USER" -f "net.minecraft" 2>/dev/null || true

    # 5. Wait for ALL ports to be released before returning
    echo "  Ensuring ports are released..."
    for port_to_check in "$BACKEND_PORT" "$MC_PORT" "$RCON_PORT"; do
        while nc -z localhost "$port_to_check" 2>/dev/null; do
            echo "  Port $port_to_check still bound, waiting..."
            sleep 5
            fuser -k "$port_to_check/tcp" 2>/dev/null || true
        done
    done
    echo "  Ports are free."
    sleep 5
    wait 2>/dev/null || true
    # 6. Clean up this job's working directory
    if [ -n "${WORK_DIR:-}" ] && [ -d "${WORK_DIR:-}" ]; then
        echo "  Skipping workdir removal to persist world changes: $WORK_DIR"
        # rm -rf "$WORK_DIR" || true
    fi
    echo "[CLEANUP] Done."
}
trap cleanup EXIT INT TERM

MAX_RESTARTS=20
RESTART_COUNT=0

while [ $RESTART_COUNT -lt $MAX_RESTARTS ]; do
    echo ""
    IT=$((RESTART_COUNT + 1))
    echo "============================================="
    echo "  Starting Run Loop iteration: $IT / $MAX_RESTARTS"
    echo "============================================="
    PIDS=()

# ================================================================
#  1. Start Minecraft Server
# ================================================================
echo "[1/$((NUM_BOTS + 2))] Starting Minecraft server..."

# Use job-specific data directories to avoid collisions in parallel runs.
# These will be cleaned up on exit if chosen, but keeping them aids debugging.
WORK_DIR="$REPO_ROOT/rosie/workdirs/${SLURM_JOB_ID}"
MC_DATA_DIR="$WORK_DIR/mc-data"
mkdir -p "$MC_DATA_DIR"

# Copy server data (world, properties, etc.) if not already present
if [ ! -f "$MC_DATA_DIR/server.properties" ]; then
    echo "  Copying server data from $SERVER_DIR..."
    cp -r "$SERVER_DIR"/* "$MC_DATA_DIR/" 2>/dev/null || true
fi

# Log filenames include iteration ID to prevent overwriting during auto-restarts
MC_LOG="$RUN_DIR/mc-server_it${IT}.log"
BACKEND_LOG="$RUN_DIR/backend_it${IT}.log"

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
    /start > "$MC_LOG" 2>&1 &
MC_PID=$!
PIDS+=("$MC_PID")
echo "  MC server PID: $MC_PID"
echo "  Waiting for MC server to be ready on port $MC_PORT..."

TIMEOUT=300 # Increased to 5 minutes for high-load node stability
ELAPSED=0
while ! nc -z localhost "$MC_PORT" 2>/dev/null; do
    if ! kill -0 "$MC_PID" 2>/dev/null; then
        echo "  ERROR: MC server process died. Check $MC_LOG"
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
CAMBIUM_RUN_TAG="${CAMBIUM_RUN_TAG:-}" \
CAMBIUM_SEED="${CAMBIUM_SEED:-0}" \
CAMBIUM_NO_TRAIN="${CAMBIUM_NO_TRAIN:-0}" \
CAMBIUM_REWARD_MODE="${CAMBIUM_REWARD_MODE:-shaped}" \
CAMBIUM_NO_TIMEOUT="${CAMBIUM_NO_TIMEOUT:-0}" \
CAMBIUM_FLAT_ACTION="${CAMBIUM_FLAT_ACTION:-0}" \
CAMBIUM_SELF_PLAY="${CAMBIUM_SELF_PLAY:-1}" \
CAMBIUM_MAX_INTERVALS="${CAMBIUM_MAX_INTERVALS:-0}" \
CAMBIUM_RESTART_HOURS="${CAMBIUM_RESTART_HOURS:-2.0}" \
CAMBIUM_EVAL_OPPONENT="${CAMBIUM_EVAL_OPPONENT:-}" \
CAMBIUM_FORCE_FRESH="${CAMBIUM_FORCE_FRESH:-0}" \
    python -m uvicorn main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
    --app-dir "$REPO_ROOT/backend" \
    --no-access-log \
    > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
PIDS+=("$BACKEND_PID")
echo "  Backend PID: $BACKEND_PID"
echo "  Waiting for backend on port $BACKEND_PORT..."

ELAPSED=0
while ! nc -z localhost "$BACKEND_PORT" 2>/dev/null; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "  ERROR: Backend process died. Check $BACKEND_LOG"
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

    BOT_RUN_DIR="$WORK_DIR/bot-data/${BOT_NAME}_it${IT}"
    mkdir -p "$BOT_RUN_DIR/mods"

    # Copy mods so the entrypoint can stage them into ~/.minecraft/mods
    cp -n "$REPO_ROOT"/headlessmc/mods/* "$BOT_RUN_DIR/mods/" 2>/dev/null || true

    # Launch via pexpect-based Python launcher (mirrors Docker's expect entrypoint).
    # pexpect creates a real PTY so stdin commands reach HeadlessMC properly.
    REPO_ROOT="$REPO_ROOT" \
    BOT_RUN_DIR="$BOT_RUN_DIR" \
    SERVER="$MC_SERVER" \
    USERNAME="$BOT_NAME" \
    HMC_VERSION="2.5.1" \
    MC_VERSION="1.8.9" \
    CAMBIUM_API_URL="$API_URL" \
        python "$REPO_ROOT/rosie/rosie-bot-launcher.py" \
        >> "$RUN_DIR/${BOT_NAME}.log" 2>&1 &
    BOT_PID=$!
    PIDS+=("$BOT_PID")
    echo "  $BOT_NAME PID: $BOT_PID"

    # Stagger launches so bots don't race on shared native extraction in ~/.minecraft
    if [ "$i" -lt "$NUM_BOTS" ]; then
        echo "  Waiting 15s before next bot..."
        sleep 15
    fi
done

echo ""
echo "============================================="
echo "  All $NUM_BOTS bots launched!"
echo "============================================="
echo "  Logs (rosie/logs/${SLURM_JOB_ID}/):"
echo "    MC server:  $RUN_DIR/mc-server.log"
echo "    Backend:    $RUN_DIR/backend.log"
echo "    Bot logs:   $RUN_DIR/Bot*.log"
echo ""
echo "  SSH tunnel (run on your local machine):"
echo "    ssh -L ${BACKEND_PORT}:${NODE_HOSTNAME}:${BACKEND_PORT} -L ${MC_PORT}:${NODE_HOSTNAME}:${MC_PORT} msoe-hpc"
echo ""
echo "  Then open:"
echo "    Dashboard:  http://localhost:${BACKEND_PORT}"
echo "    Minecraft:  localhost:${MC_PORT}  (Minecraft 1.8.9 client)"
echo "============================================="

# Wait for all background processes -- job stays alive until SLURM kills it
# or all processes exit
wait $BACKEND_PID || true
    echo "[RESTART] Backend exited (likely 100-interval auto-restart). Cleaning up..."
    cleanup
    RESTART_COUNT=$((RESTART_COUNT + 1))
    echo "Sleeping 5s before next iteration..."
    sleep 5
done
