#!/bin/sh
set -ex

JAR="headlessmc-launcher-${HMC_VERSION}.jar"

if [ -n "$HMC_EMAIL" ] && [ -n "$HMC_PASSWORD" ] ; then
  echo "⏳ Logging into Minecraft account…"
  java -jar "$JAR" --command login "$HMC_EMAIL" "$HMC_PASSWORD"
fi

echo "🚀 Launching Minecraft under Xvfb…"
echo "CMD: xvfb-run java -Dhmc.check.xvfb=true -jar $JAR --command launch forge:${MC_VERSION} $HEADLESSMC_COMMAND"

exec xvfb-run java \
  -Dhmc.check.xvfb=true \
  -jar "$JAR" \
  --command launch forge:"${MC_VERSION}" \
  $HEADLESSMC_COMMAND
