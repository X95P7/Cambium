# Start Xvfb with proper parameters and more verbose output
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait for Xvfb to initialize
echo "Waiting for Xvfb to start..."
for i in $(seq 1 10); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "Xvfb started successfully."
        break
    fi
    echo "Attempt $i: Xvfb not ready yet..."
    if [ $i -eq 10 ]; then
        echo "Failed to start Xvfb after 10 attempts."
        exit 1
    fi
    sleep 1
done

# Setup environment
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_GL_VERSION_OVERRIDE=3.0

# Test OpenGL is working
echo "Testing OpenGL rendering..."
glxinfo -display :99 | grep -i opengl || echo "WARNING: OpenGL information not available"
glxinfo -display :99 | grep -i "direct rendering" || echo "WARNING: Direct rendering information not available"

# Wait for the HeadlessMC run directory to be created
while [ ! -d "/opt/hmc/HeadlessMC" ]; do
    echo "Waiting for HeadlessMC directory to be created..."
    sleep 1
done

CONFIG_FILE="/opt/hmc/config.properties"
while [ ! -f "$CONFIG_FILE" ]; do
    echo "Waiting for config.properties to be created..."
    sleep 1
done

# Patch config.properties with proper flags
sed -i '/^hmc.invert.lwjgl.flag=/d' "$CONFIG_FILE"
sed -i '/^hmc.invert.pauls.flag=/d' "$CONFIG_FILE"
sed -i '/^hmc.always.lwjgl.flag=/d' "$CONFIG_FILE"
sed -i '/^hmc.always.pauls.flag=/d' "$CONFIG_FILE"

echo "hmc.invert.lwjgl.flag=false" >> "$CONFIG_FILE"
echo "hmc.invert.pauls.flag=false" >> "$CONFIG_FILE"
echo "hmc.always.lwjgl.flag=false" >> "$CONFIG_FILE"
echo "hmc.always.pauls.flag=false" >> "$CONFIG_FILE"

echo "Patched config.properties to allow rendering."

# Copy mods if they exist (mods are already copied to $HOME/.minecraft/mods during build)
# But we can also check for mods in the mounted volume
if [ -d "$HOME/.minecraft/mods" ] && [ "$(ls -A $HOME/.minecraft/mods)" ]; then
    echo "Mods directory exists with $(ls -1 $HOME/.minecraft/mods | wc -l) mod(s)"
fi

# Actually launch Minecraft
echo "[INFO] Launching Minecraft..."
cd /opt/hmc

# Wait for server to be ready
echo "Waiting for mc-forge server to be ready..."
until nc -z -v -w30 mc-forge 25565; do
    echo "Waiting for mc-forge on port 25565..."
    sleep 5
done

# Check if we should login (online mode) or skip (offline mode)
if [ -n "$EMAIL" ] && [ -n "$PASSWORD" ] && [ "$EMAIL" != "" ] && [ "$PASSWORD" != "" ]; then
    # Online mode: login first
    echo "Logging in with account: $EMAIL"
    java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command login "$EMAIL" "$PASSWORD"
    if [ $? -ne 0 ]; then
        echo "Login failed, exiting..."
        exit 1
    fi
else
    # Offline mode: skip login
    echo "Skipping login (offline mode - username: ${USERNAME:-Player})"
fi

# Launch Minecraft
echo "Launching Minecraft Forge ${MC_VERSION}..."
java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command launch forge:${MC_VERSION} &
MC_PID=$!

# Wait for Minecraft to start, then connect to server
echo "Waiting for Minecraft to initialize..."
sleep 10

# Connect to server if SERVER is set
if [ -n "$SERVER" ] && [ "$SERVER" != "" ]; then
    # Parse SERVER (format: host:port or just host)
    if [[ "$SERVER" == *":"* ]]; then
        SERVER_HOST=$(echo "$SERVER" | cut -d: -f1)
        SERVER_PORT=$(echo "$SERVER" | cut -d: -f2)
    else
        SERVER_HOST="$SERVER"
        SERVER_PORT="25565"
    fi
    
    echo "Connecting to server: $SERVER_HOST:$SERVER_PORT"
    # Note: This would need to be sent to the Minecraft process
    # For now, the entrypoint.sh handles this via expect
fi

# Wait for Minecraft process
wait $MC_PID