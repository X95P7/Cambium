FROM eclipse-temurin:21-jdk-noble AS build

COPY . /headlessmc
WORKDIR /headlessmc

VOLUME /screenshots

RUN chmod +x ./gradlew
RUN ./gradlew headlessmc-launcher-wrapper:build

RUN rm headlessmc-launcher-wrapper/build/libs/headlessmc-launcher-*-dev.jar
RUN rm headlessmc-launcher-wrapper/build/libs/headlessmc-launcher-*-javadoc.jar
RUN rm headlessmc-launcher-wrapper/build/libs/headlessmc-launcher-*-sources.jar

FROM eclipse-temurin:21-jre-noble

# Install dependencies for OpenGL + virtual X server
RUN apt-get update && apt-get install -y \
    xvfb \
    x11-utils \
    libx11-6 \
    libgl1 \
    mesa-utils \
    libxext6 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    # Add these packages for better OpenGL support
    libgl1-mesa-dri \
    xfonts-base \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /headlessmc/headlessmc-scripts /headlessmc
COPY --from=build /headlessmc/headlessmc-launcher-wrapper/build/libs/headlessmc-launcher-*.jar /headlessmc

WORKDIR /headlessmc
ENV PATH="/headlessmc:${PATH}"

RUN sed -i 's/\r$//' hmc
RUN chmod +x hmc

# Copy mods and start script
COPY mods /mods
COPY start.sh /start.sh
RUN chmod +x /start.sh

ENV LIBGL_ALWAYS_SOFTWARE=1

# Start HeadlessMC inside a virtual framebuffer (Xvfb)
ENTRYPOINT ["/start.sh"]
