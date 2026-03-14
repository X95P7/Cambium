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
6. Every 200 ticks (or every 15 seconds, whichever comes first), the backend runs backpropagation on collected experience

## Prerequisites

- **Docker Desktop** (with Docker Compose v2)
- **Java JDK 8** (for building the mod — Forge 1.8.9 requires JDK 8, not newer)
- **Git**

> **JDK 8 only**: The mod will not compile with JDK 11+. On Windows, download [Adoptium/Temurin JDK 8](https://adoptium.net/temurin/releases/?version=8) and make sure `JAVA_HOME` points to it before running Gradle.

## Quick Start (Full Setup from Scratch)

### 1. Clone the repo

```bash
git clone <repo-url> Cambium
cd Cambium
```

### 2. Build the mod (requires JDK 8)

```bash
cd mod/CambiumMod

# Linux/Mac:
./gradlew clean build

# Windows (PowerShell):
.\gradlew.bat clean build

cd ../..
```

The output JAR is at `mod/CambiumMod/build/libs/CambiumMod-1.0.jar`.

> **First build** may take 5-10 minutes while Gradle downloads Forge and MCP mappings. Subsequent builds are faster (~30s).

### 3. Copy the mod JAR to the headlessmc mods folder

```bash
# Linux/Mac:
cp mod/CambiumMod/build/libs/CambiumMod-1.0.jar headlessmc/mods/

# Windows (PowerShell):
Copy-Item mod\CambiumMod\build\libs\CambiumMod-1.0.jar headlessmc\mods\ -Force
```

This is required before building the Docker containers because the headlessmc Dockerfile copies everything in `headlessmc/mods/` into the client image.

### 4. Start all services

```bash
docker compose up --build -d
```

This builds and starts 4 containers:
- `mc-forge` — Minecraft 1.8.9 Forge server (takes ~1-2 min to start)
- `backend` — FastAPI backend with the RL model
- `headlessmc1` — Bot1 client
- `headlessmc2` — Bot2 client

### 5. Wait for startup and verify

```bash
# Watch all logs (Ctrl+C to stop watching):
docker compose logs -f

# Or check individual services:
docker compose logs -f mc-forge        # Server ready when you see "Done (X.XXXs)!"
docker compose logs -f backend         # Should show "Fast RL agent initialized"
docker compose logs -f headlessmc1     # Should show "Sent connect command"
```

Startup takes ~2-3 minutes. The headlessmc clients wait for the server before connecting.

### 6. Activate the bots

Once both clients are connected to the server, send these commands via RCON (or type in server console):

```bash
# Using docker exec to send RCON commands:
docker exec mc-forge rcon-cli --password minecraft "say &setup"
# Wait 5 seconds for both bots to register and pair
docker exec mc-forge rcon-cli --password minecraft "say &bot-setup"
# Wait 2 seconds
docker exec mc-forge rcon-cli --password minecraft "say &run"
```

Or connect to the server as a player and type in chat:
1. `&setup` — registers both bots, pairs them, starts a duel
2. `&bot-setup` — loads action/observation config and model version
3. `&run` — starts the RL controller loop

### 7. Monitor training

Open the dashboard at **http://localhost:8000** to see:
- Bot status and tick rates
- Reward progression graphs
- Training loss over time
- Reward event breakdown

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
│       └── CambiumMod-1.0.jar  # ← Must exist before `docker compose build`
├── server/                     # Minecraft server data (mounted volume)
│   ├── server.properties       # Server config (online-mode=false, pvp=true, etc.)
│   └── ops.json                # OP'd players (Bot1 needs OP for some commands)
└── rosie/                      # MSOE Rosie HPC deployment files
```

## Build & Deploy

### Build the mod

The mod must be compiled with **JDK 8** (Forge 1.8.9 requirement):

```bash
cd mod/CambiumMod

# Verify JDK version (must be 1.8.x):
java -version

# Build:
./gradlew clean build        # Linux/Mac
.\gradlew.bat clean build    # Windows
```

The output JAR is at `mod/CambiumMod/build/libs/CambiumMod-1.0.jar`.

> **Important**: Always use `gradlew build`, never `gradlew jar` or `gradlew compileJava` alone. The `build` task includes a reobfuscation step that translates MCP names (like `Blocks.bedrock`) to SRG names used at runtime. Without it, the mod will crash with `NoSuchFieldError` when loaded by Forge.

### Deploy the mod

Copy the JAR into the headlessmc mods folder so the Docker build picks it up:

```bash
# Linux/Mac:
cp mod/CambiumMod/build/libs/CambiumMod-1.0.jar headlessmc/mods/

# Windows (PowerShell):
Copy-Item mod\CambiumMod\build\libs\CambiumMod-1.0.jar headlessmc\mods\ -Force
```

### Start the system

```bash
# Build and start all containers
docker compose up --build -d

# Or rebuild only specific services:
docker compose up -d --build backend                    # Backend only
docker compose up -d --build headlessmc1 headlessmc2    # Clients only (after mod rebuild)
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

## Server Configuration

The Minecraft server runs in offline mode with these key settings (in `server/server.properties`):

| Setting | Value | Why |
|---------|-------|-----|
| `online-mode` | `false` | Headless clients use offline accounts |
| `pvp` | `true` | Required for bots to fight each other |
| `spawn-monsters` | `false` | No mobs interfering with duels |
| `spawn-animals` | `false` | No animals interfering with duels |
| `allow-flight` | `true` | Prevents kick for movement glitches |
| `enable-rcon` | `true` | Backend sends commands via RCON |
| `rcon.password` | `minecraft` | Must match `RCON_PASSWORD` in `docker-compose.yml` |

Bot commands (`/give`, `/tp`, `/effect`, etc.) are sent via RCON which runs as the server console with full permissions. The bots themselves don't need to be OP.

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

These can be sent via RCON or typed in chat by any player on the server. All bots on the server respond to the same command (so `&setup` registers all connected bots at once).

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
| Mod | `good_aim` | +0.2 to +1.0 | Aim at enemy body center, sustained ~200ms (no reward for sweep-through or 45-90° cone) |
| Mod | `won_duel` | +10 | Bot's opponent died |
| Mod | `death` | -1 | Bot died |
| Auto | `proximity` | 0 to +0.1 | Reward for being close to the enemy |
| Auto | `pitch_control` | 0 to +0.15 | Reward for keeping pitch level |
| Auto | `extreme_pitch_penalty` | -0.05 | Penalty when \|pitch\| > 60° |
| Auto | `aim_hold` | +0.2 | Bonus when on target AND pitch is level |
| Auto | `episode_timeout` | -0.1 | Penalty when episode reaches 15s cap |

### Training

- **Algorithm**: REINFORCE (policy gradient with reward-to-go)
- **Backprop interval**: Every 200 ticks, or on death, or on 15-second episode timeout
- **Episode length cap**: 15 seconds — both bots are reset (healed, re-kitted, teleported) on timeout
- **Batch size**: 64 minimum samples
- **Discount**: gamma = 0.99 with episode boundary resets (`done` flag)
- **Entropy bonus**: 0.02 (encourages exploration, prevents degenerate spinning)
- **Gradient clipping**: max_norm = 1.0

### Episode Lifecycle

Episodes end when any of these occur:
1. **Bot dies** — death reward, backprop, both bots reset and start new duel
2. **15-second timeout** — timeout penalty for both bots, backprop, both bots healed/teleported/re-kitted
3. **200-tick backprop interval** — trains on accumulated experience, clears buffer

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

The headlessmc containers wait for the server port to be open before connecting. If the server is slow to start, the client retries automatically.

### Bots not fighting
Make sure both bots have run `&setup`, `&bot-setup`, and `&run`. Check the dashboard at `http://localhost:8000` to see bot status.

### Training not improving
Check the `/reward-progression` endpoint or the dashboard. Key things to look for:
- `avg_reward_per_sample` should generally trend upward
- `good_aim` reward should be positive (bot is looking at enemy)
- `pitch_control` should be positive (bot isn't staring at sky/ground)
- `aim_hold` should appear when the bot holds aim with level pitch
- Make sure the learning bot is on version `0.1`

### Bot stuck repeating same action / stopped sending data
After long runs (e.g. overnight), the API connection can fail (timeout, backend restart, Docker network). Fixes applied:
- **Idle fallback**: When the API returns null, the mod resets to idle (stand still) instead of repeating the last action
- **Retries**: API requests retry up to 2 times with 100ms delay before giving up
- **Shorter timeouts**: 3s connect, 5s read so failures are detected faster
- **15s episode cap**: Forces a reset even if neither bot dies, preventing indefinite stuck states

### Bot spinning in circles or looking down
If the bot learned a degenerate policy (spinning while looking at ground), the reward system includes:
- **aim_hold**: Bonus when on target AND pitch is level (rewards holding aim over sweeping)
- **extreme_pitch_penalty**: Penalty when |pitch| > 60°
- **Entropy bonus 0.02**: Discourages premature convergence to degenerate policies

**After backend reward changes, reset to train from scratch:**
```bash
docker compose down
docker compose up --build -d
# Then run &setup, &bot-setup, &run in-game again
```

### Mod crashes with `NoSuchFieldError: bedrock` (or similar)
The mod JAR was built with `gradlew jar` or `gradlew compileJava` instead of `gradlew build`. Without the reobfuscation step, MCP field names (e.g. `Blocks.bedrock`) don't match the SRG names Forge uses at runtime. Fix: rebuild with `gradlew clean build` and re-copy the JAR.

### Rebuilding after code changes

```bash
# If you changed Python backend code only:
docker compose stop backend
docker compose up -d --build backend

# If you changed Java mod code:
cd mod/CambiumMod
./gradlew clean build                                        # Linux/Mac
# .\gradlew.bat clean build                                  # Windows
cp build/libs/CambiumMod-1.0.jar ../../headlessmc/mods/      # Linux/Mac
# Copy-Item build\libs\CambiumMod-1.0.jar ..\..\headlessmc\mods\ -Force  # Windows
cd ../..
docker compose stop headlessmc1 headlessmc2
docker compose up -d --build headlessmc1 headlessmc2
# Then run &setup, &bot-setup, &run again
```

### Full reset (nuclear option)

If things are broken and you want to start completely fresh:

```bash
docker compose down -v                  # Stop everything and delete volumes
# Rebuild mod if needed (see above)
docker compose up --build -d            # Rebuild all images and start
# Wait 2-3 min, then activate bots: &setup, &bot-setup, &run
```

## Running on Rosie (MSOE HPC)

Cambium can run on MSOE's Rosie cluster for faster training with more bots and GPU acceleration. See [rosie/README.md](rosie/README.md) for full instructions.

```bash
# One-time setup
bash rosie/setup.sh

# Submit training job (default 4 bots)
sbatch rosie/cambium.sbatch
```
