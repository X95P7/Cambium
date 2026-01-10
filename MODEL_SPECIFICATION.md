# Cambium RL Model Specification

## Overview

This document describes the reinforcement learning model architecture, observation space (inputs), action space (outputs), and reward system for the Cambium Minecraft bot training system.

---

## Model Architecture

### FastRLAgent (Version 0.1)

The model uses a **2-layer Multi-Layer Perceptron (MLP)** with ReLU activation for fast inference (<50ms target).

**Architecture:**
```
Input Layer:  194 features (observation_dim)
    ↓
Hidden Layer: 256 units + ReLU activation
    ↓
Output Layer: 35+ actions (action_dim)
```

**Key Features:**
- **Optimization**: Pre-allocated numpy arrays for observation vectorization
- **Training**: Simple policy gradient with Adam optimizer (lr=1e-3)
- **Batch Size**: 64 samples minimum
- **Training Frequency**: Every 100 API calls (ticks)
- **Device**: CPU (optimized for low-latency inference)

**Model Parameters:**
- Input dimension: **194** (fixed)
- Hidden dimension: **256** (configurable)
- Output dimension: **35+** (varies by action space config)
- Total parameters: ~50,000

---

## Observation Space (Model Inputs)

The model receives a **194-dimensional vector** representing the current game state. This vector is constructed from normalized features:

### 1. Player Data (7 features)
- `health` (normalized: /20.0) - Player health (0-20)
- `x` (normalized: /100.0) - X position
- `y` (normalized: /100.0) - Y position
- `z` (normalized: /100.0) - Z position
- `yaw` (normalized: /180.0) - Horizontal rotation angle (-180 to 180)
- `pitch` (normalized: /90.0) - Vertical rotation angle (-90 to 90)
- `armor` (normalized: /20.0) - Armor points (0-20)

### 2. Entity Data (60 features = 10 entities × 6 features)
Up to **10 nearest entities**, each with:
- `isPlayer` (0.0 or 1.0) - Boolean flag
- `isProjectile` (0.0 or 1.0) - Boolean flag
- `health` (normalized: /20.0) - Entity health
- `relativeX` (normalized: /10.0) - Relative X position to player
- `relativeY` (normalized: /10.0) - Relative Y position to player
- `relativeZ` (normalized: /10.0) - Relative Z position to player

**Note**: If fewer than 10 entities exist, remaining slots are zero-padded.

### 3. Block Data (100 features = 20 blocks × 5 features)
Up to **20 nearest blocks**, each with:
- `x` (normalized: /20.0) - Block X position
- `y` (normalized: /20.0) - Block Y position
- `z` (normalized: /20.0) - Block Z position
- `distance` (normalized: /20.0) - Distance from player
- `solid` (0.0 or 1.0) - Boolean flag for solid blocks

**Note**: If fewer than 20 blocks exist, remaining slots are zero-padded.

### 4. Inventory Data (27 features = 9 slots × 3 features)
First **9 hotbar slots**, each with:
- `count` (normalized: /64.0) - Item stack count
- `isWeapon` (0.0 or 1.0) - Boolean flag
- `weaponDamage` (normalized: /10.0) - Weapon damage value

**Total Observation Vector Size: 7 + 60 + 100 + 27 = 194 features**

---

## Action Space (Model Outputs)

The model outputs a **discrete action index** that is decoded into an action dictionary. The action space is configurable, but by default includes:

### Action Components

1. **Movement** (8 bins)
   - 0: Forward (W)
   - 1: Forward-Right
   - 2: Right (D)
   - 3: Back-Right
   - 4: Back (S)
   - 5: Back-Left
   - 6: Left (A)
   - 7: Forward-Left

2. **Jump** (1 bin)
   - Boolean: `true` or `false`

3. **Attack** (1 bin)
   - Boolean: `true` or `false`

4. **Yaw** (16 bins)
   - Converted to angle: `(yaw_bin / 16) * 360.0 - 180.0`
   - Range: -180° to +180° (in 22.5° increments)

5. **Pitch** (9 bins)
   - Converted to angle: `(pitch_bin / 9) * 180.0 - 90.0`
   - Range: -90° to +90° (in 20° increments)

### Action Dictionary Format

The decoded action is returned as:
```json
{
  "movement": 0-7,
  "jump": true/false,
  "sneak": false,
  "sprint": false,
  "attack": true/false,
  "useItem": false,
  "hotbar": -1,
  "yaw": -180.0 to 180.0,
  "pitch": -90.0 to 90.0
}
```

**Total Action Space Size: 8 × 2 × 2 × 16 × 9 = 4,608 possible actions**

**Note**: The model uses a flattened action index, so the actual action_dim may be larger if additional action components are enabled (sneak, sprint, useItem, hotbar).

---

## Reward System

The reward system uses a combination of **event-based rewards** (detected by the mod) and **auto-calculated rewards** (computed from observations). Rewards are accumulated per action and used for policy gradient training.

### Reward Event Types

#### 1. `damage_dealt` (Mod-Detected)
**Trigger**: Bot successfully deals damage to an enemy player.

**Reward Calculation**:
- **Percentage-based** (preferred): `damage_percentage * 10.0`
  - `damage_percentage` = damage / target's max health (capped at 1.0)
  - Example: Dealing 50% of enemy's health = 5.0 reward
  - Example: Dealing 100% of enemy's health = 10.0 reward
- **Fallback**: `damage_amount * 1.0` (if percentage not available)

**Purpose**: Encourages the bot to deal damage to enemies. Percentage-based rewards scale with the significance of the damage relative to enemy health.

**Cooldown**: 100ms between events to prevent spam.

---

#### 2. `damage_taken` (Mod-Detected)
**Trigger**: Bot takes damage from any source.

**Reward Calculation**:
- `-damage_amount * 0.5`
- Example: Taking 2.0 damage = -1.0 reward

**Purpose**: Penalizes the bot for taking damage, encouraging defensive behavior.

**Cooldown**: 100ms between events.

---

#### 3. `good_aim` (Mod-Detected + Auto-Calculated)
**Trigger**: 
- **Mod**: Checks every 100ms if bot is looking at an enemy within 50 blocks
- **Backend**: Calculated every observation if closest enemy exists

**Reward Calculation** (Percentage-based):
- Perfect aim (within 5°): **1.0** reward
- Within 10°: **0.8** reward
- Within 20°: **0.5** reward
- Within 45°: **0.2** reward
- Within 90°: **0.05** reward
- Beyond 90°: **0.0** reward

**Angle Calculation**:
- `yaw_diff` = absolute difference between bot's yaw and target yaw
- `pitch_diff` = absolute difference between bot's pitch and target pitch
- `max_angle` = maximum of yaw_diff and pitch_diff

**Purpose**: Encourages the bot to aim at enemies, with higher rewards for better accuracy.

---

#### 4. `proximity` (Auto-Calculated)
**Trigger**: Calculated every observation if closest enemy is within 5 blocks.

**Reward Calculation**:
- `(5 - distance) / 5.0 * 0.1`
- Maximum reward (0.1) when distance = 0 blocks
- Minimum reward (0.0) when distance = 5 blocks
- No reward beyond 5 blocks

**Purpose**: Encourages the bot to engage enemies at close range (melee combat).

---

#### 5. `survival` (Auto-Calculated)
**Trigger**: Calculated every observation if bot's health > 0.

**Reward Calculation**:
- Constant: **0.01** per observation

**Purpose**: Provides a small constant reward for staying alive, encouraging survival behavior.

---

#### 6. `yaw_exploration` (Auto-Calculated)
**Trigger**: Calculated every observation if bot's yaw is between -30° and -150°.

**Reward Calculation**:
- Center yaw: -90° (maximum reward)
- `distance_from_center` = |yaw - (-90°)|
- `max_distance` = 60° (distance from center to edge)
- `yaw_exploration_score` = 1.0 - (distance_from_center / max_distance)
- `reward` = yaw_exploration_score * 0.05
- Maximum reward (0.05) at -90°
- Minimum reward (0.0) at -30° or -150°

**Purpose**: Encourages the bot to explore yaw angles in a preferred range, preventing it from getting stuck at extreme angles (0° or -180°).

---

#### 7. `won_duel` (Mod-Detected)
**Trigger**: Bot wins a duel (enemy dies).

**Reward Calculation**:
- Constant: **+10.0** reward

**Purpose**: Large reward for winning, encouraging successful combat outcomes.

---

#### 8. `death` (Mod-Detected)
**Trigger**: Bot dies.

**Reward Calculation**:
- Constant: **-1.0** reward

**Purpose**: Penalty for dying, encouraging survival.

---

### Reward Aggregation

1. **Per Action**: Each `predict_action()` call initializes a reward of `0.0` for that action.

2. **Event Accumulation**: As events occur (damage, aim checks, etc.), rewards are added to the last action's reward:
   ```python
   self.rewards[-1] += total_reward
   ```

3. **Training**: Every 100 actions, the model trains on the accumulated rewards using policy gradient:
   ```python
   loss = -(log_probs * rewards_tensor).mean()
   ```

### Reward Scaling Summary

| Event Type | Reward Range | Typical Value |
|------------|--------------|---------------|
| `damage_dealt` | 0.0 to 10.0 | 2.0-5.0 (per hit) |
| `damage_taken` | -10.0 to 0.0 | -1.0 to -2.0 (per hit) |
| `good_aim` | 0.05 to 1.0 | 0.2-0.8 (per check) |
| `proximity` | 0.0 to 0.1 | 0.05 (when close) |
| `survival` | 0.01 | 0.01 (per tick) |
| `yaw_exploration` | 0.0 to 0.05 | 0.02-0.05 (when in range) |
| `won_duel` | 10.0 | 10.0 (one-time) |
| `death` | -1.0 | -1.0 (one-time) |

**Expected Reward per 100 Ticks**: Approximately 1.0 to 5.0 (depending on combat activity)

---

## Training Process

1. **Data Collection**: 
   - Bot makes actions via `predict_action()` every 3 game ticks (~6.67 times per second)
   - Observations, actions, and rewards are stored in buffers

2. **Reward Assignment**:
   - Events detected by mod or calculated by backend are added to the last action's reward
   - Rewards accumulate over time

3. **Training Trigger**:
   - Every **100 API calls** (ticks), training is triggered
   - Requires minimum **64 samples** in buffer

4. **Training Step**:
   - Policy gradient update using accumulated rewards
   - Buffers are cleared after training
   - Statistics are logged for monitoring

5. **Monitoring**:
   - Average rewards, loss, and bot scores are logged every 100 ticks
   - Frontend dashboard displays real-time training metrics

---

## Expected Learning Outcomes

With this reward system, the bot should learn to:

1. **Aim at enemies** (via `good_aim` rewards)
2. **Deal damage** (via `damage_dealt` rewards)
3. **Engage at close range** (via `proximity` rewards)
4. **Avoid taking damage** (via `damage_taken` penalties)
5. **Survive** (via `survival` rewards and `death` penalties)
6. **Win duels** (via `won_duel` rewards)
7. **Explore yaw angles** (via `yaw_exploration` rewards)

The combination of percentage-based rewards for aim and damage, along with continuous survival rewards, should guide the bot toward effective PvP combat behavior over time.

---

## Configuration Files

- **Observation Space**: `backend/main.py` → `observation_space_config`
- **Action Space**: `backend/main.py` → `action_space_config`
- **Reward Calculation**: `backend/main.py` → `calculate_auto_rewards()`
- **Reward Processing**: `backend/fast_rl_model.py` → `add_reward()`
- **Event Detection**: `mod/CambiumMod/src/net/famzangl/minecraft/minebot/ai/RewardListener.java`

---

## Notes

- All observation features are **normalized** to approximately [-1, 1] range for stable training
- Yaw angles are **normalized to -180° to 180°** range before processing
- Rewards are **accumulated per action**, not per event (multiple events can contribute to one action's reward)
- The model uses **simple policy gradient** (not PPO) for fast training
- Training occurs **every 100 ticks** to balance learning speed and stability


