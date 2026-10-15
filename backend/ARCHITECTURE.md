# Cambium Backend Architecture

## Overview

The backend is a FastAPI server that bridges a Minecraft Forge mod with a PPO reinforcement learning agent. 8 headless bots fight in 4 simultaneous 1v1 arenas. The server receives observations from the mod every 3 game ticks, returns actions, and handles reward events and death notifications.

---

## Module Layout

```
backend/
├── main.py           # FastAPI app + all HTTP endpoints (thin layer)
├── state.py          # All global state, constants, reward weights, event logger
├── rcon.py           # Minecraft RCON communication
├── reward_engine.py  # Per-tick auto-rewards + dashboard reward estimation
├── game_logic.py     # Bot management, arena control, episode timeouts
├── training.py       # PPO training loop, CSV/log writer, model autosave
├── fast_rl_model.py  # PPO actor-critic network, per-bot buffers, self-play
├── BotClass.py       # Bot data class
├── botController.py  # Bot list + pairing logic
├── arena/
│   ├── arenaClass.py # Arena data class
│   └── areanaA.py    # 4 arena spawn coordinate definitions
├── kits/
│   ├── kitBase.py    # Kit command builder
│   └── classicKit.py # Iron sword + full iron armor kit
├── reward_weights.json  # Runtime reward weights (single source of truth)
└── models/           # Saved model checkpoints (.pt + _stats.json)
```

---

## Module Dependency Graph

```
main.py
├── state.py          (constants, all mutable global state, REWARD_WEIGHTS)
├── rcon.py           (→ state)
├── reward_engine.py  (→ state)
├── game_logic.py     (→ state, rcon, botController)
├── training.py       (→ state, reward_engine, botController)
└── fast_rl_model.py  (standalone — only touched via state.fast_rl_agent)
```

No circular imports. `state.py` is the shared root — all modules read from it, none write to each other directly.

---

## Data Flow (Per Tick)

```
Minecraft Mod
    │
    │  POST /predict-action-v0.1  { observation, bot_name }
    ▼
main.py
    ├─ mark_bot_active()              track liveness
    ├─ cache observation              state.bot_states[bot_name]
    ├─ episode timeout check          15s cap → reset_bots_after_timeout()
    ├─ partner entity prioritisation  inject partner at entities[0]
    ├─ fast_rl_agent.predict_action() learner bots (odd)
    │  fast_rl_agent.predict_action_opponent()  frozen bots (even)
    ├─ reward_engine.calculate_auto_rewards()   proximity, pitch, aim_hold
    └─ agent.add_reward()             buffer auto-rewards
    │
    │  { action }
    ▼
Minecraft Mod
```

```
Minecraft Mod
    │
    │  POST /add-reward/  { bot_name, events: [damage_dealt, damage_taken, good_aim] }
    ▼
main.py
    ├─ update bot_states[bot_name]
    ├─ log to bot_reward_events[]
    ├─ suppress phantom damage during reset window
    └─ agent.add_reward()             buffer reward event
```

```
Minecraft Mod
    │
    │  POST /death/  { name }
    ▼
main.py
    ├─ agent.add_reward(loser, death=-20)
    ├─ agent.add_reward(winner, won_duel=+90)
    └─ fight_bots(bot, pair)          immediate rematch
```

---

## Background Timers (startup tasks)

| Timer | Interval | What it does |
|-------|----------|-------------|
| Idle checker | 10 s | Marks bots as idle if silent > 30 s; force-resets stuck episodes |
| Backprop timer | 30 s | Calls `trigger_backprop()` → PPO train → self-play snapshot check |
| Watchdog | 5 min check | Exits via `sys.exit(0)` after 1 hour so sbatch restart loop catches it |

---

## Self-Play

- **Odd bots** (Bot1, Bot3, Bot5, Bot7) are **learners** — use the live policy network.
- **Even bots** (Bot2, Bot4, Bot6, Bot8) are **frozen opponents** — use a snapshot copy of the policy.
- Every **25 training intervals** the snapshot is updated to the current policy.
- This creates an evolving opponent that prevents reward plateaus.

---

## Reward System

All reward values are loaded from `reward_weights.json` at startup into `state.REWARD_WEIGHTS` and passed into `FastRLAgent.weights` (same dict reference — no duplication).

### Reward Sources

| Source | Who triggers | Events |
|--------|-------------|--------|
| Minecraft mod | Mod code | `damage_dealt`, `damage_taken`, `good_aim` |
| Auto-rewards (per tick) | `reward_engine.py` | `proximity`, `pitch_control`, `aim_hold`, `extreme_pitch_penalty` |
| Episode timeout | `game_logic.py` | `episode_timeout`, `no_damage_penalty` (if no damage dealt) |
| Death endpoint | `main.py /death/` | `death` (loser), `won_duel` (winner) |

### Reward Values (`reward_weights.json`)

| Event | Default |
|-------|---------|
| `doing_damage` | +10.0 per hit |
| `taking_damage` | −2.0 per hit |
| `won_duel` | +90.0 |
| `death` | −20.0 |
| `episode_timeout` | −10.0 |
| `no_damage_penalty` | −10.0 (+ timeout, no damage dealt) |
| `good_aim` | +0.1 × amount |
| `proximity` | +0.05 × amount |
| `pitch_control` | +0.05 × amount |
| `aim_hold` | +0.1 × amount |
| `extreme_pitch_penalty` | −0.05 × amount |

---

## RL Model (`fast_rl_model.py`)

- **Architecture**: `ActorCritic` — shared 2-layer MLP (22→256→256), then separate heads.
- **Observation** (22 dims): `[player_health, yaw, pitch | opp_alive, health, relX, relY, relZ, yaw, pitch | 8 wall rays | dist, aim_dot, yaw_err, pitch_err]`
- **Action heads** (MultiDiscrete): movement (9), jump (2), sprint (2), attack (2), yaw (9), pitch (5)
- **Training**: PPO with GAE (γ=0.99, λ=0.95), clipped surrogate loss, entropy bonus, separate value network. Batched every 30 s across all bot buffers.
- **Self-play**: `snapshot_opponent()` deep-copies the live network weights into `self.opponent_net`.

---

## Persistence

- **Training**: `models/autosave_latest.pt` (rolling) + `model_YYYYMMDD_HHMMSS_shutdown.pt` on exit.
- **Stats**: Each `.pt` has a matching `_stats.json` with intervals, samples, reward totals.
- **Resume**: On startup, `main.py` loads the most recently modified `.pt` file and restores lifetime counters.

---

## Deployment (`rosie/cambium.sbatch`)

```
sbatch → compute node
         ├─ singularity: Minecraft server (Forge 1.8.9, port 33565)
         ├─ uvicorn:     FastAPI backend (CUDA, port 33800)
         │    ↑ entry: python -m uvicorn main:app --app-dir $REPO_ROOT/backend
         └─ rosie-bot-launcher.py × 8  (HeadlessMC clients, staggered 15 s apart)

Restart loop: backend exits (watchdog / 100-interval) → sbatch while-loop restarts it
              Minecraft server and bots stay alive across backend restarts.
```

**Environment variables** (set by sbatch):

| Variable | Default | Purpose |
|----------|---------|---------|
| `RCON_HOST` | `mc-forge` | Minecraft RCON address |
| `RCON_PORT` | 33575 | RCON port |
| `CAMBIUM_DEVICE` | `cpu` → `cuda` in sbatch | PyTorch device |
| `CAMBIUM_EXPERIMENT` | `training` | `baseline` disables training |
| `CAMBIUM_NO_TRAIN` | `0` | `1` skips gradient updates |
| `CAMBIUM_SELF_PLAY` | `1` | `0` disables opponent snapshot |
| `CAMBIUM_EPISODE_TIMEOUT_SEC` | `15` | Episode length cap |
| `CAMBIUM_MODELS_DIR` | `backend/models/` | Checkpoint directory |
