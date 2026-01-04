# Reward System Documentation

## Overview

The PPO model uses a reward system with four main reward types to guide learning:

### Positive Rewards (+)

1. **Good Aim** (`good_aim`)
   - Reward: +0.1 per event
   - Triggered when: Bot is looking at an enemy player (within ~30 degrees)
   - Purpose: Encourage the bot to track and aim at opponents

2. **Doing Damage** (`doing_damage`)
   - Reward: +1.0 per damage point dealt
   - Triggered when: Bot deals damage to another player
   - Purpose: Encourage aggressive play and successful attacks

3. **Winning** (`won_duel`)
   - Reward: +10.0 per win
   - Triggered when: Bot's opponent dies (bot wins the duel)
   - Purpose: Strong incentive to win matches

### Negative Rewards (-)

4. **Taking Damage** (`taking_damage`)
   - Reward: -0.5 per damage point taken
   - Triggered when: Bot takes damage from any source
   - Purpose: Encourage defensive play and avoiding damage

## Reward Weights

Default reward weights (configurable in `RewardCalculator`):

```python
{
    'good_aim': 0.1,      # Small reward for tracking enemies
    'doing_damage': 1.0,  # Medium reward for dealing damage
    'winning': 10.0,      # Large reward for winning
    'taking_damage': -0.5 # Medium penalty for taking damage
}
```

## Event Types

Events are sent to the API via the `/add-reward/` endpoint:

### Damage Dealt
```json
{
    "type": "damage_dealt",
    "amount": 5.0
}
```

### Damage Taken
```json
{
    "type": "damage_taken",
    "amount": 3.0
}
```

### Good Aim
```json
{
    "type": "good_aim"
}
```

### Won Duel
```json
{
    "type": "won_duel"
}
```

## Usage

### From Mod

The mod can send reward events using the `sendRewardEvents` method in `RLControllerStrategy`:

```java
JsonArray events = new JsonArray();
JsonObject damageEvent = new JsonObject();
damageEvent.addProperty("type", "damage_dealt");
damageEvent.addProperty("amount", 5.0);
events.add(damageEvent);

sendRewardEvents(helper, events);
```

### From Backend

The backend automatically handles:
- **Death events**: When a bot dies, it receives a negative reward and its opponent receives a "won_duel" reward
- **Aim rewards**: Calculated automatically based on entity positions and player rotation

### Manual Reward Addition

You can manually add rewards via the API:

```bash
curl -X POST http://backend:8000/add-reward/ \
  -H "Content-Type: application/json" \
  -d '{
    "bot_name": "Bot1",
    "events": [
      {"type": "damage_dealt", "amount": 5.0},
      {"type": "good_aim"}
    ],
    "current_state": {...}
  }'
```

## Reward Calculation

The `RewardCalculator` class processes events and calculates total reward:

1. Processes all events in the event list
2. Applies reward weights to each event type
3. Calculates aim reward based on entity positions (if entities are present)
4. Returns total reward for the step

## Training Integration

Rewards are collected in the PPO agent's buffer and used during training:

1. Each action prediction stores the observation, action, and log probability
2. Rewards are added via `add_reward()` method
3. During `train()`, rewards are converted to discounted returns
4. Advantages are calculated (returns - values)
5. Policy and value networks are updated using PPO loss

## Tuning Rewards

To adjust reward weights, modify the `reward_weights` dictionary in `ppo_model.py`:

```python
self.reward_weights = {
    'good_aim': 0.2,      # Increase to encourage more tracking
    'doing_damage': 1.5,  # Increase to encourage more aggression
    'winning': 15.0,      # Increase to prioritize winning
    'taking_damage': -1.0 # Increase penalty to encourage defense
}
```

## Best Practices

1. **Balance**: Ensure positive and negative rewards are balanced to prevent the agent from being too aggressive or too defensive
2. **Scale**: Keep reward magnitudes reasonable (typically -10 to +10 range)
3. **Sparsity**: Winning reward should be large enough to overcome accumulated small penalties
4. **Frequency**: More frequent rewards (good_aim) should have smaller magnitudes than rare rewards (winning)

