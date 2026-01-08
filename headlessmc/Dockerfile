# Use Java 8 (required by Forge 1.8.9)
FROM eclipse-temurin:8-jdk


# Allow these to be overridden at build time
ARG MC_VERSION=1.8.9
ARG HMC_VERSION=2.5.1


ENV EMAIL=
ENV PASSWORD=
ENV SERVER=
# Make them available at runtime too
ENV MC_VERSION=${MC_VERSION}
ENV HMC_VERSION=${HMC_VERSION}
# Regex to match the Forge installer jar
ENV FORGE_REGEX="forge:1.8.9"
# Default HeadlessMC launch flags
ENV HEADLESSMC_COMMAND=--jvm\ -Djava.awt.headless=true


ENV HOME=/root \
    MC_VERSION=${MC_VERSION} \
    HMC_VERSION=${HMC_VERSION} \
    HEADLESSMC_COMMAND=--jvm\ -Djava.awt.headless=true \
    USERNAME=Player


# Install all packages in one layer for better caching
# Note: netcat-openbsd and libasound2t64 are used instead of virtual packages in newer Ubuntu
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      netcat-openbsd expect \
      xvfb xauth x11-xserver-utils wget \
      libxext6 libxrender1 libxtst6 libxi6 libxt6 libx11-6 \
      libfontconfig1 libfreetype6 libasound2t64 \
    && rm -rf /var/lib/apt/lists/*


# Set working dir
WORKDIR /opt/hmc


# 1) Bootstrap HeadlessMC configuration
RUN mkdir -p run/mods && \
    cat > config.properties <<EOF
hmc.java.versions=$JAVA_HOME/bin/java
hmc.gamedir=$PWD/run
hmc.offline=true
hmc.rethrow.launch.exceptions=true
hmc.exit.on.failed.command=false
hmc.assets.dummy=true
EOF


# 2) Download the HeadlessMC launcher jar
RUN wget -qO headlessmc-launcher-${HMC_VERSION}.jar \
    https://github.com/3arthqu4ke/headlessmc/releases/download/${HMC_VERSION}/headlessmc-launcher-${HMC_VERSION}.jar


# 3) Download Minecraft and install Forge (slow - cached unless MC_VERSION changes)
RUN java -jar headlessmc-launcher-${HMC_VERSION}.jar --command download ${MC_VERSION} && \
    java -jar headlessmc-launcher-${HMC_VERSION}.jar --command forge ${MC_VERSION} --java $JAVA_HOME/bin/java


RUN find /opt/hmc/HeadlessMC -name 'liblwjgl*.so' -exec execstack -c {} \;


# Create the vanilla Minecraft mods folder under root (for compatibility)
RUN mkdir -p $HOME/.minecraft/mods


# Copy entrypoint first (changes less frequently)
COPY entrypoint.sh /opt/hmc/entrypoint.sh
RUN chmod +x /opt/hmc/entrypoint.sh


# Copy mods to BOTH locations:
# 1. /opt/hmc/run/mods - This is where the game actually looks (based on hmc.gamedir)
# 2. /root/.minecraft/mods - For compatibility/backup
# Copy mods LAST so mod changes don't invalidate the expensive Minecraft/Forge download cache
COPY mods/ /opt/hmc/run/mods/
COPY mods/ $HOME/.minecraft/mods/




# Expose the game directory as a volume if you want to persist saves or logs
VOLUME ["/opt/hmc/run"]


# Pre-download Minecraft version and Forge during build
#RUN java -jar headlessmc-launcher-${HMC_VERSION}.jar --yes --command download ${MC_VERSION} && \
 #   java -jar headlessmc-launcher-${HMC_VERSION}.jar --yes --command forge ${MC_VERSION} --java $JAVA_HOME/bin/java




ENTRYPOINT ["/opt/hmc/entrypoint.sh"]


#ENTRYPOINT ["sh", "-c", "\
#xvfb-run java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command login ${EMAIL} ${PASSWORD} && \
#xvfb-run java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command launch forge:1.8.9 ${HEADLESSMC_COMMAND} && \
#if [ ! -z \"$SERVER\" ]; then sleep 5 && echo 'connect $SERVER' > /dev/tty; fi"]


#ENTRYPOINT ["sh", "-c", "xvfb-run java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command launch forge:1.8.9 $HEADLESSMC_COMMAND"]
# ENTRYPOINT ["sh", "-c", "xvfb-run java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command login [EMAIL] [PASSWORD] && xvfb-run java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command launch forge:1.8.9 $HEADLESSMC_COMMAND"]
