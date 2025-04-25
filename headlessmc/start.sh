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
while [ ! -d "/headlessmc/HeadlessMC" ]; do
    echo "Waiting for run directory to be created..."
    sleep 1
done

CONFIG_FILE="/headlessmc/HeadlessMC/config.properties"
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

# Copy mods if they exist
mkdir -p "/headlessmc/HeadlessMC/run/mods"
if [ -d "/mods" ] && [ "$(ls -A /mods)" ]; then
    echo "Copying mods to Minecraft directory..."
    cp /mods/*.jar "/headlessmc/HeadlessMC/run/mods"
fi

# Actually launch Minecraft
echo "[INFO] Launching Minecraft..."
cd /headlessmc

# Combined login and launch command
echo "Logging in and launching Minecraft..."
hmc login Xylimalt@gmail.com Xsoccer98! && hmc launch forge:1.8.9 -commands