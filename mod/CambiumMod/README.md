# CambiumMod - Reinforcement Learning System for Minecraft PvP

## Overview

CambiumMod is a Minecraft Forge mod that implements a reinforcement learning (RL) system for PvP combat. The mod enables bots to learn and improve their combat skills through interaction with a backend API that runs PPO (Proximal Policy Optimization) models.

## Architecture

The system consists of three main components:

1. **Minecraft Mod (CambiumMod)**: Collects observations, executes actions, and communicates with the backend
2. **Backend API (FastAPI)**: Manages bot lifecycle, model inference, training, and arena management
3. **RL Model**: PPO-based policy network that learns optimal combat strategies

## Event Loop

The system follows a structured event loop for managing bot duels:

### Bot Registration Flow
1. Controller sends `&setup` command in chat
2. Client mod calls `/bot-setup/` endpoint
3. Backend creates bot, gives kit, pairs with another bot
4. If pair found, automatically starts duel via `start_duel`

### Death Event Flow
1. Bot dies in game
2. Mod detects death and calls `/death/` endpoint
3. Backend updates bot status to "dead"
4. Opens arena for reuse
5. If bot has a pair, automatically starts new duel with paired bot
6. If no pair, attempts to pair with another available bot

### Duel Start Flow (`start_duel`)
1. Gives both bots their kits
2. Heals both bots to full health
3. Teleports bots to arena spawn coordinates
4. Sets bot status to "fighting"
5. Closes arena (marks as unavailable)

## API Endpoints

### Bot Management

#### `POST /bot-setup/`
Registers a new bot into the system.
- **Request**: `{"name": "bot_name"}`
- **Response**: Bot creation confirmation
- **Actions**: Creates bot, gives kit, pairs bots, starts duel if pair found

#### `POST /death/`
Handles bot death event.
- **Request**: `{"name": "bot_name"}`
- **Response**: Death confirmation
- **Actions**: Updates status, opens arena, starts new duel with paired bot

#### `POST /start-duel/`
Manually starts a duel between two bots.
- **Request**: `{"bot1": "name1", "bot2": "name2"}`
- **Response**: Duel start confirmation with arena name
- **Actions**: Gives kits, heals bots, teleports to arena

### Model Inference

#### `POST /predict-action/{version}`
Predicts an action using the PPO model.
- **Request Body**:
  ```json
  {
    "observation": {
      "player": {...},
      "entities": [...],
      "blocks": [...],
      "inventory": [...]
    },
    "action_space": {
      "enableMovement": true,
      "enableJump": true,
      ...
    }
  }
  ```
- **Response**:
  ```json
  {
    "action": {
      "movement": 0,
      "jump": false,
      "attack": false,
      "yaw": 0.0,
      "pitch": 0.0,
      ...
    },
    "tick_rate": 20.0,
    "processing_time": 0.05
  }
  ```
- **Timing**: Tracks processing time and calculates tick rate based on 90th percentile of past 20 ticks

#### `POST /backprop/{version}`
Conducts backpropagation on the model.
- **Request Body**:
  ```json
  {
    "observations": [...],
    "actions": [...],
    "rewards": [...],
    "dones": [...]
  }
  ```
- **Response**: Training status and loss

### Configuration

#### `GET /set-action-space`
Returns current action space configuration.

#### `POST /set-action-space`
Sets action space configuration.
- **Request Body**: Action space config JSON
- **Response**: Updated configuration

#### `GET /set-observation-space`
Returns current observation space configuration.

#### `POST /set-observation-space`
Sets observation space configuration.
- **Request Body**: Observation space config JSON
- **Response**: Updated configuration

#### `GET /set-model`
Returns current model endpoint/version.

#### `POST /set-model`
Sets the model endpoint to be used by bots.
- **Request Body**: `{"endpoint": "v1"}` or `{"version": "v1"}`
- **Response**: Updated model configuration

#### `POST /save-model`
Saves the active model to disk.
- **Request Body**: `{"path": "models/model_v1.pt"}`
- **Response**: Save confirmation with path

## Dynamic Action/Observation Spaces

The system supports dynamic configuration of action and observation spaces, allowing you to modify the bot's capabilities without rebuilding the mod.

### Action Space Configuration

The action space defines what actions the bot can take:

- **Movement**: 8-directional movement (N, NE, E, SE, S, SW, W, NW)
- **Jump**: Boolean
- **Sneak**: Boolean
- **Sprint**: Boolean
- **Attack**: Boolean (left click)
- **Use Item**: Boolean (right click)
- **Hotbar**: 0-9 slot selection
- **Look**: Yaw and pitch adjustments

Configuration can be changed via the `/set-action-space` endpoint.

### Observation Space Configuration

The observation space defines what information the bot can observe:

- **Player Data**: Health, position, rotation, velocity, armor
- **Entity Data**: Nearby entities (players, mobs, projectiles) with relative positions, health, armor, etc.
- **Block Data**: Blocks in view with positions and properties
- **Inventory Data**: All inventory slots with item properties

Limits can be set for:
- Maximum entities observed (default: 10)
- Maximum blocks observed (default: 50)
- Maximum inventory slots (default: 36)

Configuration can be changed via the `/set-observation-space` endpoint.

## Tick Rate Management

The system implements intelligent tick rate management:

1. Tracks timing of past 20 ticks
2. Calculates 90th percentile of tick intervals
3. Uses this to determine optimal tick rate
4. Can adjust server tick rate via `/settickrate` command (requires server mod support)

The tick rate is included in the `predict-action` response and can be used to optimize performance.

## Feature Extractors

The mod includes several feature extractors:

### GetPlayer
Extracts player state information:
- Health
- Position (x, y, z)
- Rotation (yaw, pitch)
- Armor value

### GetEntities
Extracts information about nearby entities:
- Entity type (player, projectile, mob)
- Relative position
- Velocity
- Health and armor
- Facing direction

### GetBlocks
Performs raycasting to find blocks in view:
- Block positions (relative to player)
- Distance from player
- Block properties (solid, name)

### GetInventory
Extracts inventory information:
- Slot numbers
- Item counts
- Item types (weapon, block, projectile)
- Weapon damage values

## Usage

### Starting a Bot

1. Join a Minecraft server with the mod installed
2. Type `&setup` in chat
3. The bot will:
   - Register with the backend
   - Load action/observation space configurations
   - Load model endpoint
   - Start the RL controller strategy
   - Get paired with another bot
   - Start a duel if a pair is found

### Monitoring

The bot will display its status in the chat:
- "RL Controller started!" - When the controller is activated
- "Bot {name} has been added to the game" - On registration
- "Bot {name} has died!" - On death
- Error messages for any API failures

### Configuration

To change action/observation spaces or model endpoint:

1. Use the API endpoints to update configurations
2. The bot will automatically reload configurations on next setup
3. Or restart the bot by typing `&setup` again

## Development

### Mod Structure

```
mod/CambiumMod/src/net/famzangl/minecraft/minebot/
├── ai/
│   ├── cambiumInputs/
│   │   ├── APIClient.java              # HTTP client for API calls
│   │   ├── ActionSpaceConfig.java      # Action space configuration
│   │   ├── ObservationSpaceConfig.java # Observation space configuration
│   │   ├── DataClasses/                # Data structures
│   │   └── GetInformation/             # Feature extractors
│   ├── strategy/cambium/
│   │   └── RLControllerStrategy.java    # Main RL controller
│   ├── ChatListener.java               # Chat command handler
│   └── DeathListener.java              # Death event handler
└── PhysicsController.java              # Physics/input controller
```

### Backend Structure

```
backend/
├── main.py              # FastAPI application with all endpoints
├── BotClass.py          # Bot class definition
├── botController.py     # Bot management
└── arena/               # Arena management
```

## Future Enhancements

- [ ] Implement actual PPO model training
- [ ] Add reward shaping for combat performance
- [ ] Support multiple model versions simultaneously
- [ ] Add model versioning and rollback
- [ ] Implement distributed training across multiple bots
- [ ] Add visualization tools for training progress
- [ ] Support custom observation/action space definitions via config files

## Requirements

- Minecraft 1.8.x (or version compatible with Forge)
- Forge Mod Loader
- Python 3.8+ (for backend)
- FastAPI
- mcrcon (for RCON commands)

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

