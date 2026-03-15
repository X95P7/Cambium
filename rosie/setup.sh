#!/bin/bash
################################################################################
# Cambium - One-time Rosie setup
#
# Run from the repo root on a Rosie management/login node:
#   bash rosie/setup.sh
#
# This script:
#   1. Pulls the Minecraft server Singularity image
#   2. Pulls a Java 8 base image (for HeadlessMC clients)
#   3. Downloads HeadlessMC + Minecraft 1.8.9 + Forge into a local directory
#   4. Creates a Python venv for the FastAPI backend
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGES_DIR="$REPO_ROOT/rosie/images"
VENV_DIR="$REPO_ROOT/rosie/.venv"
HMC_DIR="$REPO_ROOT/rosie/hmc"

HMC_VERSION=2.5.1
MC_VERSION=1.8.9

mkdir -p "$IMAGES_DIR"
mkdir -p "$REPO_ROOT/rosie/logs"

echo "=========================================="
echo "  Cambium Rosie Setup"
echo "=========================================="

module load cuda/current openmpi/current singularity/current StdEnv

# ---------- 1. Minecraft Server Image ----------
MC_SIF="$IMAGES_DIR/minecraft-server-java8.sif"
if [ -f "$MC_SIF" ]; then
    echo "[1/4] Minecraft server image already exists: $MC_SIF"
else
    echo "[1/4] Pulling Minecraft server image (itzg/minecraft-server:java8)..."
    singularity pull "$MC_SIF" docker://itzg/minecraft-server:java8
    echo "       Done: $MC_SIF"
fi

# ---------- 2. Java 8 Base Image (for HeadlessMC clients) ----------
JAVA8_SIF="$IMAGES_DIR/java8-base.sif"
if [ -f "$JAVA8_SIF" ]; then
    echo "[2/4] Java 8 base image already exists: $JAVA8_SIF"
else
    echo "[2/4] Pulling Java 8 base image (eclipse-temurin:8-jdk)..."
    singularity pull "$JAVA8_SIF" docker://eclipse-temurin:8-jdk
    echo "       Done: $JAVA8_SIF"
fi

# ---------- 3. HeadlessMC Setup ----------
if [ -d "$HMC_DIR/HeadlessMC" ]; then
    echo "[3/4] HeadlessMC already set up in $HMC_DIR"
    echo "       To rebuild, delete $HMC_DIR and re-run this script."
else
    echo "[3/4] Setting up HeadlessMC (downloading Minecraft $MC_VERSION + Forge)..."
    echo "       This takes a few minutes on first run."
    mkdir -p "$HMC_DIR/run/mods"

    cat > "$HMC_DIR/config.properties" <<EOF
hmc.java.versions=/opt/java/openjdk/bin/java
hmc.gamedir=/opt/hmc/run
hmc.offline=true
hmc.rethrow.launch.exceptions=true
hmc.exit.on.failed.command=false
hmc.assets.dummy=true
EOF

    echo "       Downloading HeadlessMC launcher v${HMC_VERSION}..."
    wget -qO "$HMC_DIR/headlessmc-launcher-${HMC_VERSION}.jar" \
        "https://github.com/3arthqu4ke/headlessmc/releases/download/${HMC_VERSION}/headlessmc-launcher-${HMC_VERSION}.jar"

    echo "       Copying mods..."
    cp "$REPO_ROOT"/headlessmc/mods/* "$HMC_DIR/run/mods/"

    echo "       Downloading Minecraft ${MC_VERSION}..."
    singularity exec \
        --bind "$HMC_DIR:/opt/hmc" \
        --pwd /opt/hmc \
        "$JAVA8_SIF" \
        java -jar "/opt/hmc/headlessmc-launcher-${HMC_VERSION}.jar" --command download "$MC_VERSION"

    echo "       Installing Forge for ${MC_VERSION}..."
    singularity exec \
        --bind "$HMC_DIR:/opt/hmc" \
        --pwd /opt/hmc \
        "$JAVA8_SIF" \
        java -jar "/opt/hmc/headlessmc-launcher-${HMC_VERSION}.jar" --command forge "$MC_VERSION" --java /opt/java/openjdk/bin/java

    echo "       Done: $HMC_DIR"
fi

# ---------- 4. Python Virtual Environment ----------
if [ -f "$VENV_DIR/bin/activate" ]; then
    echo "[4/4] Python venv already exists: $VENV_DIR"
    echo "       To rebuild, delete $VENV_DIR and re-run this script."
else
    echo "[4/4] Creating Python venv with CUDA-enabled PyTorch..."
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
