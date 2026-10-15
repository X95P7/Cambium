# Cambium Backend - Architecture & API Guide

This document explains the architecture of the reinforcement learning backend, the differences between model implementations, and how the API endpoints coordinate the bot's behavior.

## Core Architecture

The backend is built as a **FastAPI** server that acts as a central brain for multiple Minecraft bots. It manages bot registration, duel matchmaking, arena state, and the reinforcement learning (RL) training loops.

### Primary Files

1.  **`main.py`**: The central orchestrator.
    *   **REST API**: Defines all endpoints that the Minecraft mod calls.
    *   **Bot Management**: Tracks bot states, health, and pairings.
    *   **Arena Logic**: Manage available arenas and resets.
    *   **Automatic Rewards**: Calculates rewards that aren't easily tracked by the mod (e.g., proximity to enemy, keeping pitch level, aim hold).
    *   **Training Loop**: Triggers the `FastRLAgent` training process periodically via the `backprop_timer`.

2.  **`fast_rl_model.py` (High Performance - PvP Optimized)**:
    *   **Model**: Implements a highly optimized **Actor-Critic** network using **Multi-Discrete** action heads.
    *   **Observations**: Uses a compact **22-dimension** vector focused strictly on PvP-relevant data (relative positions, wall distance rays, aiming errors).
    *   **Actions**: Maps actions to specific bins (e.g., 8 movement directions, 11 yaw bins).
    *   **Training**: Implements **GAE (Generalized Advantage Estimation)** and **Value Function Clipping** to handle the high variance of Minecraft combat.
    *   **Reward Mapping**: Acts as the single source of truth for converting event types (e.g., `damage_dealt`) into numeric reward values for the trainer.

3.  **`ppo_model.py` (Generic / legacy)**:
    *   **Approach**: A more generic PPO implementation.
    *   **Data Density**: Uses a much larger observation vector (~200+ dimensions) that include full inventory slots, surrounding blocks, and many more entities.
    *   **Complexity**: While more detailed, this model is slower to train and prone to "information overload" in high-speed PvP compared to the `FastRLAgent`.

---

## API Endpoints

The Minecraft mod interacts with the backend through these primary REST endpoints:

### 1. The Interaction Loop
*   **`POST /predict/`**: 
    *   **Purpose**: The "Heartbeat" of the bot. Called every tick (~20 times per second).
    *   **Flow**: Mod sends current observation JSON -> Backend vectorizes it -> RL Model predicts actions -> Mod receives and executes actions.
*   **`POST /add-reward/`**:
    *   **Purpose**: Receives event-driven feedback.
    *   **Flow**: The mod detects events like `damage_dealt`, `damage_taken`, or `good_aim` and pushes them here. The backend pipes these into the agent's buffer for training.

### 2. State & Lifecycle
*   **`POST /bot-setup/`**: 
    *   **Purpose**: Registration and Reconnection.
    *   **Flow**: When a bot joins or the server restarts, this endpoint initializes the bot object, assigns a kit, and finds an arena/pair for it.
*   **`POST /death/`**:
    *   **Purpose**: Handing episode termination.
    *   **Flow**: Triggered when a bot dies. It awards the `won_duel` reward to the opponent (+15.0), applies a `death` penalty (-2.0) to the victim, and resets the duel in the arena.

### 3. Model Management
*   **`GET /list-models/`**: Returns all saved `.pt` checkpoints available for loading.
*   **`POST /set-model/`**: Allows the user or mod to switch which model version (e.g., `0.1` for Fast RL, `0.0` for legacy) a specific bot name should use.
*   **`GET/POST /set-observation-space/`**: Configures which features are included in the observation vector (health, pos, etc.). Note: `FastRLAgent` currently defaults to a fixed 22-dim layout for stability.

---

## Why this Architecture?

1.  **Decoupling**: The Minecraft mod handles game physics and data collection, while the Python backend handles the heavy neural network computations. This allows training to run on GPUs while the game runs on separate CPUs.
2.  **Concurrency**: The system treats each bot as an independent trajectory. We collect data from 8+ arenas simultaneously, but consolidate all that experience into a single global model update every 30 seconds.
3.  **Stability**: By using `/predict/` for every action, we ensure that every single observation/action pair is recorded into the training buffer, maximizing data efficiency.
