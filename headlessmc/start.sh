#!/bin/bash

# Wait until the mods directory is created
while [ ! -d "/headlessmc/HeadlessMC" ]; do
    echo "Waiting for run directory to be created..."
    sleep 1
done

# Create the mods folder (just in case)
mkdir -p "/headlessmc/HeadlessMC/run/mods"

# Copy all .jar mod files to the run/mods directory
cp /mods/*.jar "/headlessmc/HeadlessMC/run/mods"

echo "[INFO] Starting interactive shell..."
exec /bin/bash