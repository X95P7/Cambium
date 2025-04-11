#!/bin/bash
set -e

# If using a .env file, you could source it here
if [ -f "/minecraft/.env" ]; then
  echo "Loading environment variables from /minecraft/.env"
  source /minecraft/.env
fi

# Sample: logging in a single account.
# You can extend this section to support multiple accounts, either via a loop or separate containers.
if [[ -n "${MC_EMAIL}" && -n "${MC_PASSWORD}" ]]; then
    echo "Logging into Minecraft account: ${MC_EMAIL}"
    # The following command uses headlessMC's login syntax.
    hmc login "${MC_EMAIL}" "${MC_PASSWORD}"
else
    echo "No account credentials provided. Make sure to set MC_EMAIL and MC_PASSWORD."
    exit 1
fi

# (Optional) Other configuration steps – for instance, if you need to set additional properties:
# You might pass system properties using -D syntax or adjust the config.properties file here.
# Example: export JAVA_OPTS="-Dhmc.gamedir=${MC_GAMEDIR}"

# Launch the game.
# We assume that you want to run Forge 1.8.9 with headless mode enabled via the lwjgl flag.
echo "Launching Minecraft Forge ${MC_VERSION} in headless mode..."
hmc launch forge:${MC_VERSION} -lwjgl

# If you want the container to remain running, you might have a loop or tail command.
# (For example, if you are running multiple bots that keep running, you may not need this.)
tail -f /dev/null
