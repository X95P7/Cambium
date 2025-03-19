FROM openjdk:8-jdk
WORKDIR /minecraft

# Copy all server files from your local directory
COPY . /minecraft

# Expose port
EXPOSE 25565

# Start the Forge server
CMD ["java", "-Xmx2G", "-Xms1G", "-jar", "server.jar", "nogui"]