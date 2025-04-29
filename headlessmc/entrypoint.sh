#!/bin/sh

echo "Waiting for Minecraft server to start..."
until nc -z -v -w30 mc-forge 25565; do
  echo "Waiting for mc-forge on port 25565..."
  sleep 5
done

echo "Minecraft server detected. Launching HeadlessMC setup..."

# Ensure the base game and Forge are downloaded before launching
java -jar headlessmc-launcher-${HMC_VERSION}.jar --command download ${MC_VERSION}
java -jar headlessmc-launcher-${HMC_VERSION}.jar --command forge ${MC_VERSION} --java $JAVA_HOME/bin/java

# Login
xvfb-run java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command login ${EMAIL} ${PASSWORD}

# Launch the game
xvfb-run java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command launch forge:1.8.9 $HEADLESSMC_COMMAND

# Finally, connect to the server
xvfb-run java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command connect ${SERVER}