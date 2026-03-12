#!/bin/bash
################################################################################
# Cambium - One-time Rosie setup
#
# Run from the repo root on a Rosie management/login node:
#   bash rosie/setup.sh
#
# This script:
#   1. Pulls the Minecraft server Singularity image
#   2. Builds the HeadlessMC client Singularity image
#   3. Creates a Python venv for the FastAPI backend
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGES_DIR="$REPO_ROOT/rosie/images"
VENV_DIR="$REPO_ROOT/rosie/.venv"

mkdir -p "$IMAGES_DIR"
mkdir -p "$REPO_ROOT/rosie/logs"

echo "=========================================="
echo "  Cambium Rosie Setup"
echo "=========================================="

module load cuda/current openmpi/current singularity/current StdEnv

# ---------- 1. Minecraft Server Image ----------
MC_SIF="$IMAGES_DIR/minecraft-server-java8.sif"
if [ -f "$MC_SIF" ]; then
    echo "[1/3] Minecraft server image already exists: $MC_SIF"
else
    echo "[1/3] Pulling Minecraft server image (itzg/minecraft-server:java8)..."
    singularity pull "$MC_SIF" docker://itzg/minecraft-server:java8
    echo "       Done: $MC_SIF"
fi

# ---------- 2. HeadlessMC Client Image ----------
HMC_SIF="$IMAGES_DIR/cambium-headlessmc.sif"
if [ -f "$HMC_SIF" ]; then
    echo "[2/3] HeadlessMC image already exists: $HMC_SIF"
    echo "       To rebuild, delete $HMC_SIF and re-run this script."
else
    echo "[2/3] Building HeadlessMC client image..."
    echo "       This downloads Minecraft + Forge and takes a few minutes."
    cd "$REPO_ROOT"
    singularity build "$HMC_SIF" rosie/cambium-headlessmc.def
    echo "       Done: $HMC_SIF"
fi

# ---------- 3. Python Virtual Environment ----------
if [ -f "$VENV_DIR/bin/activate" ]; then
    echo "[3/3] Python venv already exists: $VENV_DIR"
    echo "       To rebuild, delete $VENV_DIR and re-run this script."
else
    echo "[3/3] Creating Python venv with CUDA-enabled PyTorch..."
    python3 -m venv --system-site-packages "$VENV_DIR"
    . "$VENV_DIR/bin/activate"
    pip install -q --upgrade pip
    pip install -q torch==2.5.1 torchvision==0.20.1 --extra-index-url https://download.pytorch.org/whl/cu124
    pip install -q fastapi uvicorn mcrcon numpy
    deactivate
    echo "       Done: $VENV_DIR"
fi

echo ""
echo "=========================================="
echo "  Setup complete!"
echo ""
echo "  To start training, run:"
echo "    sbatch rosie/cambium.sbatch"
echo "=========================================="
