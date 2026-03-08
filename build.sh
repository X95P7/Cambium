#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE_DIR"

# Parse arguments
BUILD_MOD=false
BUILD_BACKEND=false
BUILD_CLIENTS=false
BUILD_ALL=false
START=false

if [ $# -eq 0 ]; then
    BUILD_ALL=true
    START=true
fi

for arg in "$@"; do
    case $arg in
        mod)       BUILD_MOD=true ;;
        backend)   BUILD_BACKEND=true ;;
        clients)   BUILD_CLIENTS=true ;;
        all)       BUILD_ALL=true; START=true ;;
        start)     START=true ;;
        stop)      docker compose down; exit 0 ;;
        logs)      docker compose logs -f; exit 0 ;;
        status)    docker compose ps; exit 0 ;;
        *)         echo "Usage: $0 [mod|backend|clients|all|start|stop|logs|status]"
                   echo ""
                   echo "  mod       Build the Java mod only"
                   echo "  backend   Rebuild and restart the backend container"
                   echo "  clients   Rebuild and restart headlessmc containers"
                   echo "  all       Build everything and start (default)"
                   echo "  start     Start containers without rebuilding"
                   echo "  stop      Stop all containers"
                   echo "  logs      Tail logs from all containers"
                   echo "  status    Show container status"
                   exit 0 ;;
    esac
done

if $BUILD_ALL; then
    BUILD_MOD=true
    BUILD_BACKEND=true
    BUILD_CLIENTS=true
fi

# Step 1: Build the mod
if $BUILD_MOD; then
    echo "========================================="
    echo "  Building CambiumMod..."
    echo "========================================="
    cd "$BASE_DIR/mod/CambiumMod"

    if [ -f gradlew ]; then
        chmod +x gradlew
        ./gradlew clean build
    elif [ -f gradlew.bat ]; then
        cmd.exe /c "gradlew.bat clean build"
    else
        echo "ERROR: No gradlew found in mod/CambiumMod"
        exit 1
    fi

    echo "Copying JAR to headlessmc/mods..."
    cp "$BASE_DIR/mod/CambiumMod/build/libs/CambiumMod-1.0.jar" "$BASE_DIR/headlessmc/mods/"
    echo "Mod build complete."
    cd "$BASE_DIR"
fi

# Step 2: Build and restart backend
if $BUILD_BACKEND; then
    echo ""
    echo "========================================="
    echo "  Building backend..."
    echo "========================================="
    docker compose up -d --build backend
    echo "Backend deployed."
fi

# Step 3: Build and restart headlessmc clients
if $BUILD_CLIENTS; then
    echo ""
    echo "========================================="
    echo "  Building headlessmc clients..."
    echo "========================================="
    docker compose up -d --build headlessmc1 headlessmc2
    echo "Clients deployed."
fi

# Step 4: Start (if not already started by build steps)
if $START && ! $BUILD_BACKEND && ! $BUILD_CLIENTS; then
    echo ""
    echo "========================================="
    echo "  Starting all containers..."
    echo "========================================="
    docker compose up -d
fi

echo ""
echo "========================================="
echo "  Done!"
echo "========================================="
docker compose ps
echo ""
echo "Dashboard: http://localhost:8000"
echo "Minecraft: localhost:25565"
echo ""
echo "View logs:  docker compose logs -f"
echo "Stop:       docker compose down"
