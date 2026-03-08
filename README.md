# Cambium - Reinforcement Learning PvP Bots for Minecraft

Cambium is a reinforcement learning system that trains Minecraft bots to fight in PvP combat. It runs two headless Minecraft clients that duel each other in arenas, learning from experience via a FastAPI backend that runs a policy gradient model.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Docker Compose                     │
│                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────┐ │
│  │headlessmc1│   │headlessmc2│   │   mc-forge       │ │
│  │  (Bot1)   │   │  (Bot2)   │   │ Minecraft 1.8.9  │ │
│  │ CambiumMod│   │ CambiumMod│   │  Forge Server    │ │
│  └─────┬─────┘   └─────┬─────┘   └────────┬─────────┘ │
│        │  HTTP          │  HTTP            │           │
│        └───────┬────────┘            RCON  │           │
│                ▼                           ▼           │
│        ┌──────────────────────────────────┐            │
│        │         backend (FastAPI)         │            │
│        │  - RL model (policy gradient)    │            │
│        │  - Bot management & pairing      │            │
│        │  - Training loop                 │            │
│        │  - Dashboard (localhost:8000)     │            │
│        └──────────────────────────────────┘            │
└─────────────────────────────────────────────────────┘
```

**Data flow per game tick:**
1. Mod collects observations (player position, nearby entities, health, etc.)
2. Mod sends observation to `POST /predict-action-v0.1` on the backend
3. Backend runs the RL model, returns an action (movement, attack, look direction)
4. Mod executes the action via `PhysicsController` (sets keys, applies delta yaw/pitch)
5. `RewardListener` detects combat events (damage dealt/taken, aim quality) and sends to `POST /add-reward/`
6. Every 100 ticks, the backend runs backpropagation on collected experience

## Prerequisites

- **Docker Desktop** (with Docker Compose)
- **Java JDK 8** (for building the mod)
- **Git**

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url> Cambium
cd Cambium

# 2. Build the mod (requires JDK 8)
cd mod/CambiumMod
./gradlew clean build        # Linux/Mac
# gradlew.bat clean build    # Windows
cd ../..

# 3. Copy the built mod JAR to the headlessmc mods folder
cp mod/CambiumMod/build/libs/CambiumMod-1.0.jar headlessmc/mods/

# 4. Start everything
docker compose up --build -d

# 5. Wait ~2 minutes for the Minecraft server and clients to start
# Watch logs with:
docker compose logs -f
```

Once the bots connect to the server, they need to be activated via in-game chat commands (sent automatically or via RCON). See [Bot Chat Commands](#bot-chat-commands) below.

## Project Structure

```
Cambium/
├── docker-compose.yml          # Orchestrates all services
├── backend/                    # FastAPI backend (Python)
│   ├── main.py                 # API endpoints, reward logic, training loop
│   ├── fast_rl_model.py        # Policy gradient RL model (multi-discrete actions)
│   ├── ppo_model.py            # PPO model (unused, for future use)
│   ├── BotClass.py             # Bot entity class
│   ├── botController.py        # Bot registry and pairing
│   ├── arena/                  # Arena definitions and spawn coordinates
│   ├── kits/                   # Kit loadouts (items given to bots)
│   ├── frontend/               # Dashboard UI (served at localhost:8000)
│   ├── dockerfile              # Backend container image
│   └── requirements.txt        # Python dependencies
├── mod/CambiumMod/             # Forge mod (Java, Minecraft 1.8.9)
│   ├── src/.../minebot/
│   │   ├── PhysicsController.java          # Applies actions (keys + mouse deltas)
│   │   ├── ai/
│   │   │   ├── RewardListener.java         # Detects combat events, sends rewards
│   │   │   ├── ChatListener.java           # Handles & chat commands
│   │   │   ├── cambiumInputs/
│   │   │   │   ├── APIClient.java          # HTTP client (talks to backend)
│   │   │   │   ├── ActionSpaceConfig.java  # Action space definition
│   │   │   │   ├── ObservationSpaceConfig.java
│   │   │   │   ├── DataClasses/            # PlayerData, EntityData, etc.
│   │   │   │   └── GetInformation/         # Feature extractors
│   │   │   └── strategy/cambium/
│   │   │       └── RLControllerStrategy.java  # Main RL tick loop
│   │   └── ...
│   ├── build.gradle
│   └── gradlew / gradlew.bat
├── headlessmc/                 # Headless Minecraft client container
│   ├── Dockerfile              # Builds HeadlessMC + Forge 1.8.9
│   ├── entrypoint.sh           # Startup script (wait for server, connect, etc.)
│   └── mods/                   # Mod JARs copied into client containers
│       └── CambiumMod-1.0.jar
└── server/                     # Minecraft server data (mounted volume)
```

## Build & Deploy

### Build the mod

The mod must be compiled with JDK 8 (Forge 1.8.9 requirement):

```bash
cd mod/CambiumMod
./gradlew clean build
```

The output JAR is at `mod/CambiumMod/build/libs/CambiumMod-1.0.jar`.

### Deploy the mod

Copy the JAR into the headlessmc mods folder so the Docker build picks it up:

```bash
cp mod/CambiumMod/build/libs/CambiumMod-1.0.jar headlessmc/mods/
```

### Start the system

```bash
# Build and start all containers
docker compose up --build -d

# Or rebuild only specific services:
docker compose up -d --build backend              # Backend only
docker compose up -d --build headlessmc1 headlessmc2  # Clients only (after mod rebuild)
```

### Stop the system

```bash
docker compose down          # Stop all containers
docker compose down -v       # Stop and remove volumes (wipes world data)
```

### View logs

```bash
docker compose logs -f                  # All services
docker compose logs -f backend          # Backend only
docker compose logs -f headlessmc1      # Bot1 only
docker compose logs -f mc-forge         # Minecraft server only
```

## Bot Chat Commands

Once a bot's Minecraft client is connected to the server, it responds to chat commands prefixed with `&`:

| Command | Description |
|---------|-------------|
| `&setup` | Registers the bot with the backend (`/bot-setup/`). Gives kit, pairs with another bot, starts duel if pair found. |
| `&bot-setup` | Loads configuration from backend: action space, observation space, model version. Creates the RL strategy. |
| `&run` | Starts the RL controller loop. The bot begins observing, predicting actions, and executing them every tick. |
| `&reset` | Stops all strategies and resets the bot state. |

**Typical startup sequence:**
1. `&setup` — register and pair
2. `&bot-setup` — load config
3. `&run` — start the RL loop

These can be sent via RCON or typed in chat by any player on the server.

## Backend API

The backend runs on **port 8000** and serves both the API and a dashboard UI.

### Dashboard

Open `http://localhost:8000` in a browser to see:
- Bot status and tick rates
- Reward progression graphs
- Training loss over time
- Reward event breakdown

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict-action-v{version}` | POST | Model inference. Receives observation, returns action. |
| `/add-reward/` | POST | Receives reward events from the mod (damage, aim, etc.) |
| `/bot-setup/` | POST | Registers a bot and starts pairing/dueling. |
| `/death/` | POST | Handles bot death, restarts duel. |
| `/game-state` | GET | Full game state (bots, arenas, training stats). |
| `/stats` | GET | Quick training statistics. |
| `/training-logs` | GET | Detailed per-interval training logs. |
| `/reward-progression` | GET | Reward data for graphing. |
| `/reward-events` | GET | Recent reward events per bot. |
| `/set-action-space` | GET/POST | View or update action space config. |
| `/set-observation-space` | GET/POST | View or update observation space config. |
| `/set-model` | GET/POST | View or update bot-to-model-version mapping. |
| `/backprop/{version}` | POST | Manually trigger training. |

## RL Model

### Observation Space (194 dimensions)

| Component | Features | Dimensions |
|-----------|----------|------------|
| Player | health, x, y, z, yaw, pitch, armor | 7 |
| Entities (10 max) | isPlayer, isProjectile, health, relativeX/Y/Z | 60 |
| Blocks (20 max) | x, y, z, distance, solid | 100 |
| Inventory (9 slots) | count, isWeapon, weaponDamage | 27 |

### Action Space (26 total bins)

| Component | Bins | Values |
|-----------|------|--------|
| Movement | 8 | N, NE, E, SE, S, SW, W, NW |
| Jump | 2 | yes / no |
| Attack | 2 | yes / no |
| Yaw delta | 9 | -20, -10, -5, -2, 0, +2, +5, +10, +20 deg/tick |
| Pitch delta | 5 | -5, -2, 0, +2, +5 deg/tick |

### Rewards

| Source | Type | Range | Description |
|--------|------|-------|-------------|
| Mod | `damage_dealt` | +0 to +10 | Scaled by % of target's max health |
| Mod | `damage_taken` | -0 to -10 | Penalty for taking damage |
| Mod | `good_aim` | +0.05 to +1.0 | How accurately the bot aims at the enemy |
| Mod | `won_duel` | +10 | Bot's opponent died |
| Mod | `death` | -1 | Bot died |
| Auto | `proximity` | 0 to +0.1 | Reward for being close to the enemy |
| Auto | `pitch_control` | 0 to +0.15 | Reward for keeping pitch level |

### Training

- **Algorithm**: REINFORCE (policy gradient with reward-to-go)
- **Backprop interval**: Every 100 ticks (~5 seconds at 20 TPS)
- **Batch size**: 64 minimum samples
- **Discount**: gamma = 0.99 with episode boundary resets
- **Entropy bonus**: 0.01 (encourages exploration)
- **Gradient clipping**: max_norm = 1.0

## Model Versions

Bots can be assigned different model versions via the `/set-model` endpoint:

| Version | Behavior |
|---------|----------|
| `0.0` | **Calibration mode** — Cycles through W, A, S, D, spin. Used for testing movement/physics. |
| `0.1` | **RL model** — Policy gradient with multi-discrete actions. The active learning model. |

Default mapping: `Bot1 → 0.1` (learning), `Bot2 → 0.0` (calibration).

## Troubleshooting

### Backend not responding
```bash
docker compose logs backend          # Check for Python errors
docker compose restart backend       # Restart the backend
```

### Bots not connecting
```bash
docker compose logs headlessmc1      # Check client startup
docker compose logs mc-forge         # Check server status
```

### Bots not fighting
Make sure both bots have run `&setup`, `&bot-setup`, and `&run`. Check the dashboard at `http://localhost:8000` to see bot status.

### Training not improving
Check the `/reward-progression` endpoint or the dashboard. Key things to look for:
- `total_rewards` should generally trend upward
- `good_aim` reward should be positive (bot is looking at enemy)
- `pitch_control` should be positive (bot isn't staring at sky/ground)
- Make sure the learning bot is on version `0.1`

### Rebuilding after code changes

```bash
# If you changed Python backend code:
docker compose up -d --build backend

# If you changed Java mod code:
cd mod/CambiumMod
./gradlew clean build
cp build/libs/CambiumMod-1.0.jar ../../headlessmc/mods/
cd ../..
docker compose up -d --build headlessmc1 headlessmc2
```
