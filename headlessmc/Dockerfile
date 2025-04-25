# Use Java 8 (required by Forge 1.8.9)
FROM openjdk:8-jdk-slim

# install everything we need: xvfb, xauth, x11 tools, wget
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      xvfb xauth x11-xserver-utils wget && \
    rm -rf /var/lib/apt/lists/*

# Allow these to be overridden at build time
ARG MC_VERSION=1.8.9
ARG HMC_VERSION=2.5.1

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
    HEADLESSMC_COMMAND=--jvm\ -Djava.awt.headless=true


# Install Xvfb and wget
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      xvfb xauth x11-xserver-utils wget \
      libxext6 libxrender1 libxtst6 libxi6 libxt6 libx11-6 \
      libfontconfig1 libfreetype6 libasound2 \
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

# 3) Download Minecraft and install Forge
RUN java -jar headlessmc-launcher-${HMC_VERSION}.jar --command download ${MC_VERSION} && \
    java -jar headlessmc-launcher-${HMC_VERSION}.jar --command forge ${MC_VERSION} --java $JAVA_HOME/bin/java


RUN find /opt/hmc/HeadlessMC -name 'liblwjgl*.so' -exec execstack -c {} \;

# Create the vanilla Minecraft mods folder under root
RUN mkdir -p $HOME/.minecraft/mods

# Copy your local mods directory into the container
COPY mods/ $HOME/.minecraft/mods/


# Expose the game directory as a volume if you want to persist saves or logs
VOLUME ["/opt/hmc/run"]

# Default command: run under Xvfb and launch the Forge client
ENTRYPOINT ["sh", "-c", "xvfb-run java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command login [EMAIL] [PASSWORD] && xvfb-run java -Dhmc.check.xvfb=true -jar headlessmc-launcher-${HMC_VERSION}.jar --command launch forge:1.8.9 $HEADLESSMC_COMMAND"]

