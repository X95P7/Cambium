#!/bin/bash
################################################################################
# Rosie bot entrypoint (runs INSIDE Singularity)
#
# Sets up per-bot config, copies mods to the REAL game directory (~/.minecraft),
# then exec's Java so it inherits the PTY created by the pexpect launcher.
#
# IMPORTANT: HeadlessMC does in-memory launching (no child JVM), so any -D
# system properties must go BEFORE -jar, not via HeadlessMC's --jvm flag.
################################################################################

set -uo pipefail

USERNAME="${USERNAME:-Player}"
HMC_VERSION="${HMC_VERSION:-2.5.1}"
MC_VERSION="${MC_VERSION:-1.8.9}"
CAMBIUM_API_URL="${CAMBIUM_API_URL:-http://backend:8000}"

cd /opt/hmc

# HeadlessMC's ProcessFactory uses ~/.minecraft as the game directory.
# Mods MUST be there — NOT in /opt/hmc/run/mods.
mkdir -p "$HOME/.minecraft/mods"
cp -n /opt/hmc/run/mods/* "$HOME/.minecraft/mods/" 2>/dev/null || true

echo "[entrypoint] Mods in $HOME/.minecraft/mods:"
ls -1 "$HOME/.minecraft/mods/" 2>/dev/null || echo "  (none)"
echo "[entrypoint] API URL: $CAMBIUM_API_URL"

# Per-bot offline username (writable-tmpfs makes this container-local)
sed -i '/^hmc.offline.username=/d' config.properties 2>/dev/null || true
echo "hmc.offline.username=$USERNAME" >> config.properties

rm -f HeadlessMC/auth/.accounts.json 2>/dev/null || true

echo "[entrypoint] Launching HeadlessMC for $USERNAME..."

# exec replaces bash with Java — the PTY from pexpect passes straight through.
# -D properties go BEFORE -jar since HeadlessMC uses in-memory launching.
# -Xmx2G caps heap so 8 bots fit in ~20GB total.
exec java \
    -Xms512M -Xmx2G \
    -Dhmc.check.xvfb=false \
    -Dhmc.offline.username="$USERNAME" \
    -Djava.awt.headless=true \
    -Dcambium.api.url="$CAMBIUM_API_URL" \
    -jar "headlessmc-launcher-${HMC_VERSION}.jar" \
    --command launch "forge:${MC_VERSION}" -offline
