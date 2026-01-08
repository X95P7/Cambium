import os
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from mcrcon import MCRcon
import asyncio
import multiprocessing
import botController as botController
from BotClass import Bot
from kits import classicKit
from kits.kitBase import Kit
from arena import areanaA
from typing import Optional, Dict, Any, List
import json
import numpy as np
from ppo_model import PPOAgent
from fast_rl_model import FastRLAgent

arenas = areanaA.Arenas

app = FastAPI()

# Serve static files (frontend)
import os
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    try:
        app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    except:
        pass  # Directory might not exist yet

@app.get("/")
async def read_root():
    """Serve the frontend dashboard."""
    frontend_file = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    if os.path.exists(frontend_file):
        return FileResponse(frontend_file)
    return {"message": "Frontend not found. Please create frontend/index.html"}

RCON_HOST = os.getenv("RCON_HOST", "mc-forge")  # "localhost" if not using Docker
RCON_PORT = int(os.getenv("RCON_PORT", 25575))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "minecraft")

# Global configuration storage
action_space_config = {
    "enableMovement": True,
    "enableJump": True,
    "enableSneak": False,
    "enableSprint": False,
    "enableAttack": True,
    "enableUseItem": True,
    "enableHotbar": True,
    "enableLook": True,
    "movementBins": 8,
    "yawBins": 16,
    "pitchBins": 9
}

observation_space_config = {
    "includePlayerData": True,
    "includeEntityData": True,
    "includeBlockData": True,
    "includeInventoryData": True,
    "maxEntities": 10,
    "maxBlocks": 20,  # REDUCED from 50 to 20 for performance
    "maxInventorySlots": 36,
    "includeHealth": True,
    "includePosition": True,
    "includeRotation": True,
    "includeVelocity": True,
    "includeArmor": True
}

# Model configuration - maps bot names to model versions
bot_model_mapping = {
    "Bot1": "0.1",
    "Bot2": "0.0",
}  # bot_name -> model_version (e.g., "0.0", "0.1", etc.)

# Removed tick_times tracking - not needed anymore

# Initialize PPO Agent
# Estimate observation and action dimensions based on config
def estimate_observation_dim():
    """Estimate observation dimension based on config - optimized for fast_rl_model."""
    # Fast RL model uses fixed dimensions: 7 (player) + 60 (entities) + 100 (blocks) + 27 (inventory) = 194
    dim = 0
    if observation_space_config.get("includePlayerData", True):
        dim += 7  # health, x, y, z, yaw, pitch, armor
    if observation_space_config.get("includeEntityData", True):
        dim += observation_space_config.get("maxEntities", 10) * 6  # 6 features per entity (reduced from 15)
    if observation_space_config.get("includeBlockData", True):
        dim += observation_space_config.get("maxBlocks", 20) * 5  # 5 features per block (reduced from 6)
    if observation_space_config.get("includeInventoryData", True):
        dim += 9 * 3  # 9 hotbar slots, 3 features each
    return dim

def estimate_action_dim():
    """Estimate action dimension based on config."""
    dim = 0
    if action_space_config.get("enableMovement", True):
        dim += action_space_config.get("movementBins", 8)
    if action_space_config.get("enableJump", True): dim += 1
    if action_space_config.get("enableSneak", True): dim += 1
    if action_space_config.get("enableSprint", True): dim += 1
    if action_space_config.get("enableAttack", True): dim += 1
    if action_space_config.get("enableUseItem", True): dim += 1
    if action_space_config.get("enableHotbar", True): dim += 10
    if action_space_config.get("enableLook", True):
        dim += action_space_config.get("yawBins", 16) + action_space_config.get("pitchBins", 9)
    return dim

# Initialize Fast RL agent (for version 0.1 - <50ms inference)
try:
    obs_dim = estimate_observation_dim()
    act_dim = estimate_action_dim()
    # Use FastRLAgent for version 0.1 - much faster than PPO
    fast_rl_agent = FastRLAgent(
        observation_dim=obs_dim,
        action_dim=act_dim,
        device='cpu'
    )
    print(f"Fast RL agent initialized successfully: obs_dim={obs_dim}, act_dim={act_dim}")
    # Keep PPO agent as None for now (can be used for future versions)
    ppo_agent = None
except Exception as e:
    print(f"ERROR initializing Fast RL agent: {e}")
    import traceback
    traceback.print_exc()
    fast_rl_agent = None
    ppo_agent = None

# Bot state tracking for rewards
bot_states = {}  # bot_name -> current state
bot_events = {}  # bot_name -> list of events

# Tick counting for backprop
bot_tick_counts = {}  # bot_name -> tick count
BACKPROP_INTERVAL = 100  # Train every 100 ticks

# Tick timing tracking for TPS calculation
tick_times = {}  # bot_name -> list of timestamps

# Training log tracking - stores statistics every 100 ticks
training_logs = []  # List of dicts with timestamp, stats, rewards, etc.
MAX_LOG_ENTRIES = 1000  # Keep last 1000 log entries

# Action caching to reduce computation (predictions are throttled in mod, but add safety here)
bot_last_actions = {}  # bot_name -> last action dict
bot_action_timestamps = {}  # bot_name -> timestamp of last prediction

# Simple observation cache to avoid re-processing identical observations
bot_last_observation_hash = {}  # bot_name -> hash of last observation
bot_cached_obs_vector = {}  # bot_name -> cached observation vector

# Calibration mode tracking (for version 0.0)
bot_calibration_start = {}  # bot_name -> datetime when calibration cycle started
CALIBRATION_MOVE_DURATION = 2.0  # seconds to hold each movement key
CALIBRATION_SPIN_DURATION = 2.0  # seconds to spin
CALIBRATION_CYCLE_DURATION = (CALIBRATION_MOVE_DURATION * 4) + CALIBRATION_SPIN_DURATION  # Total cycle time

def normalize_yaw(yaw):
    """Normalize yaw angle to -180 to 180 range"""
    while yaw > 180:
        yaw -= 360
    while yaw < -180:
        yaw += 360
    return yaw

def calculate_auto_rewards(bot_name: str, observation: Dict) -> List[Dict]:
    """
    Calculate automatic rewards based on observation data.
    Gives rewards for looking at enemies, being close to enemies, etc.
    Returns a list of reward events.
    """
    events = []
    
    if not observation:
        return events
    
    player = observation.get('player', {})
    entities = observation.get('entities', [])
    
    if not player or not entities:
        return events
    
    player_yaw = normalize_yaw(player.get('yaw', 0))
    player_pitch = player.get('pitch', 0)
    player_health = player.get('health', 0)
    
    # Find closest enemy player
    closest_enemy = None
    closest_distance = float('inf')
    
    for entity in entities:
        if entity.get('isPlayer', False) and entity.get('health', 0) > 0:
            rel_x = entity.get('relativeX', 0)
            rel_y = entity.get('relativeY', 0)
            rel_z = entity.get('relativeZ', 0)
            distance = (rel_x**2 + rel_y**2 + rel_z**2)**0.5
            
            if distance < closest_distance:
                closest_distance = distance
                closest_enemy = {
                    'relativeX': rel_x,
                    'relativeY': rel_y,
                    'relativeZ': rel_z,
                    'distance': distance
                }
    
    if closest_enemy:
        # Calculate angle to enemy
        target_yaw = normalize_yaw(np.arctan2(closest_enemy['relativeX'], closest_enemy['relativeZ']) * 180.0 / np.pi)
        target_pitch = normalize_yaw(np.arctan2(-closest_enemy['relativeY'], (closest_enemy['relativeX']**2 + closest_enemy['relativeZ']**2)**0.5) * 180.0 / np.pi)
        
        # Calculate angle differences
        yaw_diff = abs(normalize_yaw(player_yaw - target_yaw))
        pitch_diff = abs(player_pitch - target_pitch)
        
        # Reward for looking at enemy (percentage-based, more generous)
        # Perfect aim (within 5 degrees) = 1.0 reward
        # Within 10 degrees = 0.8 reward
        # Within 20 degrees = 0.5 reward
        # Within 45 degrees = 0.2 reward
        # Within 90 degrees = 0.05 reward
        
        max_angle = max(yaw_diff, pitch_diff)
        if max_angle < 5:
            aim_score = 1.0
        elif max_angle < 10:
            aim_score = 0.8
        elif max_angle < 20:
            aim_score = 0.5
        elif max_angle < 45:
            aim_score = 0.2
        elif max_angle < 90:
            aim_score = 0.05
        else:
            aim_score = 0.0
        
        if aim_score > 0:
            events.append({
                "type": "good_aim",
                "amount": aim_score,
                "yaw_diff": yaw_diff,
                "pitch_diff": pitch_diff,
                "distance": closest_enemy['distance']
            })
        
        # Reward for being close to enemy (encourages engagement)
        if closest_enemy['distance'] < 5:
            proximity_reward = (5 - closest_enemy['distance']) / 5.0 * 0.1  # Max 0.1 reward
            events.append({
                "type": "proximity",
                "amount": proximity_reward,
                "distance": closest_enemy['distance']
            })
    
    # Small survival reward (encourages staying alive)
    if player_health > 0:
        events.append({
            "type": "survival",
            "amount": 0.01  # Small constant reward for staying alive
        })
    
    # Reward for exploring different yaw angles (encourages yaw between -30 and -150)
    # This helps prevent the bot from getting stuck at 0 or -180 degrees
    if -150 <= player_yaw <= -30:
        # Calculate reward based on distance from center (-90 degrees)
        # Maximum reward (0.05) at -90 degrees, decreasing towards edges
        center_yaw = -90.0
        distance_from_center = abs(player_yaw - center_yaw)
        max_distance = 60.0  # Distance from center to edge (-30 to -90 or -90 to -150)
        
        # Linear decay from center to edge (1.0 at center, 0.0 at edge)
        yaw_exploration_score = 1.0 - (distance_from_center / max_distance)
        yaw_exploration_reward = yaw_exploration_score * 0.05  # Max 0.05 reward
        
        events.append({
            "type": "yaw_exploration",
            "amount": yaw_exploration_reward,
            "yaw": player_yaw,
            "distance_from_center": distance_from_center
        })
    
    return events

# Use multiprocessing for running the RCON command in a separate process
def mc_command(command: str):
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command(command)
        return response
    except Exception as e:
        return str(e)

# Helper function to run the command in a separate process
def run_rcon_command(command: str):
    with multiprocessing.Pool(1) as pool:
        result = pool.apply(mc_command, (command,))
    return result

async def send_mc_command(command: str):
    loop = asyncio.get_event_loop()
    # Run the RCON command in a separate process
    result = await loop.run_in_executor(None, run_rcon_command, command)
    return {"sent_command": command, "response": result}

async def calibration_mode_action(bot_name: str):
    """
    Calibration mode for version 0.0.
    Cycles through: W (forward) -> A (left) -> S (back) -> D (right) -> spin
    Each movement lasts 2 seconds, spin lasts 2 seconds.
    """
    processing_start = time.time()  # For processing time calculation
    now = datetime.now()
    
    # Initialize calibration start time if not set
    if bot_name not in bot_calibration_start:
        bot_calibration_start[bot_name] = now
    
    calibration_start = bot_calibration_start[bot_name]
    elapsed = (now - calibration_start).total_seconds()
    
    # Calculate position in cycle (loop if needed)
    cycle_position = elapsed % CALIBRATION_CYCLE_DURATION
    
    # Determine which action to perform
    if cycle_position < CALIBRATION_MOVE_DURATION:
        # W (forward) - movement bin 0
        action = {
            "movement": 0,
            "jump": False,
            "sneak": False,
            "sprint": False,
            "attack": False,
            "useItem": False,
            "hotbar": -1,
            "yaw": 0.0,
            "pitch": 0.0
        }
    elif cycle_position < CALIBRATION_MOVE_DURATION * 2:
        # A (left) - movement bin 6
        action = {
            "movement": 6,
            "jump": False,
            "sneak": False,
            "sprint": False,
            "attack": False,
            "useItem": False,
            "hotbar": -1,
            "yaw": 0.0,
            "pitch": 0.0
        }
    elif cycle_position < CALIBRATION_MOVE_DURATION * 3:
        # S (back) - movement bin 4
        action = {
            "movement": 4,
            "jump": False,
            "sneak": False,
            "sprint": False,
            "attack": False,
            "useItem": False,
            "hotbar": -1,
            "yaw": 0.0,
            "pitch": 0.0
        }
    elif cycle_position < CALIBRATION_MOVE_DURATION * 4:
        # D (right) - movement bin 2
        action = {
            "movement": 2,
            "jump": False,
            "sneak": False,
            "sprint": False,
            "attack": False,
            "useItem": False,
            "hotbar": -1,
            "yaw": 0.0,
            "pitch": 0.0
        }
    else:
        # Spin - continuously rotate yaw
        # Calculate delta yaw per tick to complete 360 degrees in CALIBRATION_SPIN_DURATION seconds
        # Assuming ~20 ticks per second: 360 degrees / (CALIBRATION_SPIN_DURATION * 20 ticks/sec)
        # For 2 seconds: 360 / (2 * 20) = 9 degrees per tick
        yaw_delta = 360.0 / (CALIBRATION_SPIN_DURATION * 20.0)  # ~9 degrees per tick for 2 second spin
        action = {
            "movement": 0,  # No movement during spin
            "jump": False,
            "sneak": False,
            "sprint": False,
            "attack": False,
            "useItem": False,
            "hotbar": -1,
            "yaw": yaw_delta,  # Delta yaw per tick for continuous rotation
            "pitch": 0.0
        }
    
    processing_time = time.time() - processing_start
    
    return {
        "action": action,
        "processing_time": processing_time
    }

async def trigger_backprop(bot_name: str = None):
    """
    Triggers backpropagation training.
    Can be called periodically or when a duel ends.
    Logs statistics every 100 ticks.
    """
    try:
        # Check if we have enough data to train
        agent = fast_rl_agent if fast_rl_agent else ppo_agent
        if agent is None:
            return {"status": "skipped", "reason": "no_agent"}
        
        total_samples = len(agent.observations)
        if total_samples < 64:
            print(f"Skipping backprop for {bot_name or 'all bots'}: insufficient data ({total_samples} samples, need 64)")
            return {"status": "skipped", "reason": "insufficient_data", "samples": total_samples}
        
        # Calculate statistics before training
        total_rewards_before = sum(agent.rewards) if agent.rewards else 0.0
        avg_reward_before = total_rewards_before / len(agent.rewards) if agent.rewards else 0.0
        bot_rewards_before = {}
        if fast_rl_agent:
            bot_rewards_before = {name: score for name, score in fast_rl_agent.bot_scores.items()}
        
        # Train the model
        stats = agent.train(batch_size=64, epochs=4)
        print(f"Backprop completed for {bot_name or 'all bots'}: {stats}")
        
        # Calculate statistics after training
        # Note: stats["score"] is the sum of rewards before clearing, which is what we want
        total_rewards_for_interval = stats.get("score", total_rewards_before)  # Use score from stats (sum of rewards)
        loss = stats.get("loss", 0.0)
        samples_trained = stats.get("samples_trained", 0)
        
        # Get current bot statistics
        bot_stats = {}
        for bot in botController.bots:
            bot_name_key = bot.name
            bot_stats[bot_name_key] = {
                "status": bot.status,
                "tick_count": bot_tick_counts.get(bot_name_key, 0),
                "score": fast_rl_agent.bot_scores.get(bot_name_key, 0.0) if fast_rl_agent else 0.0,
                "model_version": bot_model_mapping.get(bot_name_key, "0.0")
            }
        
        # Create log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "tick_interval": BACKPROP_INTERVAL,
            "bot_name": bot_name,
            "training_stats": {
                "samples_trained": samples_trained,
                "loss": loss,
                "total_rewards": total_rewards_for_interval,  # Total rewards collected in this 400-tick interval
                "avg_reward_per_sample": avg_reward_before,
                "reward_delta": total_rewards_for_interval - total_rewards_before
            },
            "bot_statistics": bot_stats,
            "system_stats": {
                "total_bots": len(botController.bots),
                "active_bots": len([b for b in botController.bots if b.status == "fighting"]),
                "ready_bots": len([b for b in botController.bots if b.status == "ready"]),
                "open_arenas": len([a for a in arenas if a.status == "open"]),
                "closed_arenas": len([a for a in arenas if a.status == "closed"])
            }
        }
        
        # Add to training logs
        training_logs.append(log_entry)
        
        # Keep only last MAX_LOG_ENTRIES
        if len(training_logs) > MAX_LOG_ENTRIES:
            training_logs.pop(0)
        
        return stats
    except Exception as e:
        print(f"Error in backprop: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

@app.post("/send-command/")
async def send_command(command: str):
    return await send_mc_command(command)

@app.post("/predict-action-v{version}")
async def predict_action(version: str, request: Request):
    """
    Predicts an action using the PPO model.
    Receives observation and action space, returns action.
    Tracks timing for tick rate management.
    Version format: 0.0, 0.1, etc.
    
    Version 0.0: Calibration mode - cycles W -> A -> S -> D -> spin
    Version 0.1: Simple random actions (PPO disabled for now due to performance issues)
    """
    # Log immediately - this should always print
    print(f"[PREDICT-START] Version: {version}, Time: {time.time()}")
    import sys
    sys.stdout.flush()  # Force flush to ensure logs appear
    
    start_time = time.time()
    
    try:
        data = await request.json()
    except Exception as e:
        print(f"[PREDICT] Error parsing JSON: {e}")
        sys.stdout.flush()
        return {"action": {"movement": 0, "jump": False, "sneak": False, "sprint": False, "attack": False, "useItem": False, "hotbar": -1, "yaw": 0.0, "pitch": 0.0}}
    
    observation = data.get("observation", {})
    action_space = data.get("action_space", action_space_config)
    bot_name = data.get("bot_name", "unknown")
    
    #print(f"[PREDICT] Bot: {bot_name}, Version: {version}")
    sys.stdout.flush()
    
    # IMPORTANT: Increment tick count FIRST for ALL versions (this is the accurate tick counter)
    if bot_name not in bot_tick_counts:
        bot_tick_counts[bot_name] = 0
    bot_tick_counts[bot_name] += 1
    
    # Store latest observation for visualization
    if bot_name not in bot_states:
        bot_states[bot_name] = {}
    bot_states[bot_name]["latest_observation"] = observation
    bot_states[bot_name]["latest_observation_time"] = datetime.now().isoformat()
    
    # Calculate automatic rewards based on observation (looking at targets, etc.)
    # This gives continuous rewards for good behavior that the mod might not track
    # These are ADDITIONAL rewards - mod can still send its own rewards via /add-reward/
    # Auto-rewards supplement mod-sent rewards (e.g., mod sends damage_dealt, we add good_aim)
    auto_reward_events = calculate_auto_rewards(bot_name, observation)
    if auto_reward_events:
        agent = fast_rl_agent if fast_rl_agent else ppo_agent
        if agent:
            # Add auto-rewards - these supplement mod-sent rewards
            agent.add_reward(bot_name, observation, auto_reward_events)
    
    # Track tick timing for TPS calculation
    current_time = time.time()
    if bot_name not in tick_times:
        tick_times[bot_name] = []
    tick_times[bot_name].append(current_time)
    
    # Keep only last 20 ticks for TPS calculation
    if len(tick_times[bot_name]) > 20:
        tick_times[bot_name] = tick_times[bot_name][-20:]
    
    # Calculate tick rate based on 90th percentile of past 20 ticks
    # Multiply by 20/3 because API is called once every 3 ticks
    tick_rate = 20.0  # Default
    if len(tick_times[bot_name]) >= 2:
        intervals = []
        for i in range(1, len(tick_times[bot_name])):
            intervals.append(tick_times[bot_name][i] - tick_times[bot_name][i-1])
        if intervals:
            intervals.sort()
            percentile_idx = int(len(intervals) * 0.9)
            if percentile_idx >= len(intervals):
                percentile_idx = len(intervals) - 1
            avg_interval = intervals[percentile_idx]
            if avg_interval > 0:
                # Calculate API call rate, then multiply by 20/3 to get actual game TPS
                api_call_rate = 1.0 / avg_interval
                tick_rate = api_call_rate * (20.0 / 3.0)
    
    # Check if backprop is needed (every 400 ticks)
    should_trigger_backprop = False
    if bot_tick_counts[bot_name] >= BACKPROP_INTERVAL:
        bot_tick_counts[bot_name] = 0
        should_trigger_backprop = True
    
    # Calibration mode for version 0.0
    if version == "0.0":
        #print(f"[PREDICT] Using calibration mode for {bot_name}")
        sys.stdout.flush()
        result = await calibration_mode_action(bot_name)
        result["tick_rate"] = tick_rate
        
        # Trigger backprop if needed (asynchronously, don't block)
        if should_trigger_backprop:
            asyncio.create_task(trigger_backprop(bot_name))
        
        return result
    
    # Version 0.1: Use Fast RL model (<50ms inference)
    if version == "0.1":
        # Store state for rewards (but don't overwrite latest_observation)
        if bot_name not in bot_states:
            bot_states[bot_name] = {}
        bot_states[bot_name]["current_state"] = observation
        
        # Simple observation caching - hash observation to avoid re-processing
        import hashlib
        obs_str = json.dumps(observation, sort_keys=True)
        obs_hash = hashlib.md5(obs_str.encode()).hexdigest()
        
        # Check if Fast RL agent is available
        if fast_rl_agent is None:
            print(f"[PREDICT] WARNING: Fast RL agent not initialized, using random fallback")
            sys.stdout.flush()
            import random
            action = {
                "movement": random.randint(0, 7),
                "jump": random.random() < 0.1,
                "sneak": False,
                "sprint": random.random() < 0.3,
                "attack": random.random() < 0.2,
                "useItem": False,
                "hotbar": random.randint(0, 8) if random.random() < 0.1 else -1,
                "yaw": random.uniform(-180, 180),
                "pitch": random.uniform(-90, 90)
            }
            processing_time = time.time() - start_time
            return {
                "action": action,
                "tick_rate": tick_rate,
                "processing_time": processing_time
            }
        
        # Use Fast RL agent - should be <50ms
        action = None
        try:
            pred_start = time.time()
            
            # Use cached observation vector if available and observation hasn't changed
            cached_vector = None
            if bot_name in bot_last_observation_hash and bot_name in bot_cached_obs_vector:
                if obs_hash == bot_last_observation_hash[bot_name]:
                    cached_vector = bot_cached_obs_vector[bot_name]
            
            # Run synchronously - should be fast enough
            action = fast_rl_agent.predict_action(observation, action_space, cached_vector=cached_vector)
            
            # Cache the observation vector for next time (if we computed a new one)
            if cached_vector is None and len(fast_rl_agent.observations) > 0:
                bot_cached_obs_vector[bot_name] = fast_rl_agent.observations[-1].copy()
                bot_last_observation_hash[bot_name] = obs_hash
            
            pred_time = time.time() - pred_start
            if pred_time > 0.1:  # Warn if >100ms
                print(f"[PREDICT] Fast RL prediction took {pred_time*1000:.1f}ms for {bot_name} (target: <50ms)")
            sys.stdout.flush()
            bot_last_actions[bot_name] = action
            bot_action_timestamps[bot_name] = time.time()
        except Exception as e:
            print(f"[PREDICT] ERROR in Fast RL prediction for {bot_name}: {e}")
            sys.stdout.flush()
            import traceback
            traceback.print_exc()
            # Use cached action if available
            if bot_name in bot_last_actions and bot_name in bot_action_timestamps:
                cache_age = time.time() - bot_action_timestamps[bot_name]
                if cache_age < 2.0:
                    action = bot_last_actions[bot_name]
        
        # Fallback to default action if no action yet
        if action is None:
            action = {
                "movement": 0,
                "jump": False,
                "sneak": False,
                "sprint": False,
                "attack": False,
                "useItem": False,
                "hotbar": -1,
                "yaw": 0.0,
                "pitch": 0.0
            }
        
        processing_time = time.time() - start_time
        
        # Trigger backprop if needed (asynchronously, don't block)
        if should_trigger_backprop:
            asyncio.create_task(trigger_backprop(bot_name))
        
        return {
            "action": action,
            "tick_rate": tick_rate,
            "processing_time": processing_time
        }
    
    # Version 0.2+ would use PPO (when we fix it)
    # For now, fallback to random
    print(f"[PREDICT] Unknown version {version}, using random fallback")
    sys.stdout.flush()
    import random
    action = {
        "movement": random.randint(0, 7),
        "jump": random.random() < 0.1,
        "sneak": False,
        "sprint": random.random() < 0.3,
        "attack": random.random() < 0.2,
        "useItem": False,
        "hotbar": random.randint(0, 8) if random.random() < 0.1 else -1,
        "yaw": random.uniform(-180, 180),
        "pitch": random.uniform(-90, 90)
    }
    processing_time = time.time() - start_time
    
    # Trigger backprop if needed (asynchronously, don't block)
    if should_trigger_backprop:
        asyncio.create_task(trigger_backprop(bot_name))
    
    return {
        "action": action,
        "tick_rate": tick_rate,
        "processing_time": processing_time
    }

@app.post("/bot-setup/")
async def bot_setup(request: Request):
    """
    Handles bot registration.
    Creates bot, gives kit, pairs bots, and starts duel if pair found.
    """
    data = await request.json()
    name = data.get("name")
    print(f"Bot setup for: {name}")
    
    currentBot = Bot(name, "ready", Kit(classicKit.kitStart, classicKit.kitEnd, name), "agent")
    botController.addBot(currentBot)
    await giveKit(currentBot)
    
    # Try to pair with another bot
    move = botController.pairBot(currentBot)
    if move == 1:
        # Pair found, start duel
        await fightBots(currentBot, currentBot.pair)
        return await send_mc_command(f"/say Bot {name} has been added and paired with {currentBot.pair.name}!")
    else:
        return await send_mc_command(f"/say Bot {name} has been added to the game. Waiting for pair...")


@app.post("/death/")
async def death(request: Request):
    """
    Handles bot death event.
    Updates bot status and starts a new duel with the paired bot.
    """
    data = await request.json()
    name = data.get("name")
    bot = getBotByName(name)
    
    if not bot:
        return {"status": "error", "message": f"Bot {name} not found"}
    
    bot.updateBot("dead")
    
    # Add reward event for death (negative reward)
    if name in bot_states:
        if fast_rl_agent:
            fast_rl_agent.add_reward(name, bot_states[name], [{"type": "death", "amount": -1.0}])
            fast_rl_agent.add_done(True)
        elif ppo_agent:
            ppo_agent.add_reward(name, bot_states[name], [{"type": "death", "amount": -1.0}])
            ppo_agent.add_done(True)
    
    # If bot has a pair, give winning reward to the pair
    if hasattr(bot, 'pair') and bot.pair and bot.pair != "NONE":
        pair_name = bot.pair.name
        if pair_name in bot_states:
            if fast_rl_agent:
                fast_rl_agent.add_reward(pair_name, bot_states[pair_name], [{"type": "won_duel"}])
                fast_rl_agent.add_done(True)
            elif ppo_agent:
                ppo_agent.add_reward(pair_name, bot_states[pair_name], [{"type": "won_duel"}])
                ppo_agent.add_done(True)
    
    # Trigger backprop when duel ends (asynchronously, don't block)
    asyncio.create_task(trigger_backprop(f"{name}_duel_end"))
    
    # Open the arena if bot was in one
    if hasattr(bot, 'arena') and bot.arena:
        bot.arena.status = "open"
    
    # Start new duel with paired bot if available
    if hasattr(bot, 'pair') and bot.pair and bot.pair != "NONE":
        # Reset both bots to ready
        bot.updateBot("ready")
        bot.pair.updateBot("ready")
        # Start new duel by calling fightBots directly
        await fightBots(bot, bot.pair)
        return await send_mc_command(f"/say Bot {name} has died! Starting new duel.")
    else:
        # Try to pair with another bot
        move = botController.pairBot(bot)
        if move == 1:
            await fightBots(bot, bot.pair)
            return await send_mc_command(f"/say Bot {name} has died! Paired with {bot.pair.name}.")
    
    return await send_mc_command(f"/say Bot {name} has died!")

async def giveKit(bot: Bot):
    for command in bot.kit.commands:
        await send_mc_command(command)

def getBotByName(name):
    for bot in botController.bots:
        if bot.name == name:
            return bot
    return None

async def fightBots(bot1, bot2):
    arena = getOpenArena()
    if arena == None:
        print("No open arenas")
        return await send_mc_command(f"/say ERROR: No open areans for {bot1.name} and {bot2.name} to fight in.")
    await giveKit(bot1)
    await giveKit(bot2)
    bot1.updateBot("fighting")
    bot2.updateBot("fighting")
    bot1.setArena(arena)
    bot2.setArena(arena)
    arena.status = "closed"
    print(f"/tp {bot1.name} {arena.spawnCoords[0]}")
    await send_mc_command(f"/tp {bot1.name} {' '.join(map(str, arena.spawnCoords[0]))}")
    await send_mc_command(f"/tp {bot2.name} {' '.join(map(str, arena.spawnCoords[1]))}")
    
    # Set spawn points at arena positions
    await send_mc_command(f"/spawnpoint {bot1.name} {' '.join(map(str, arena.spawnCoords[0]))}")
    await send_mc_command(f"/spawnpoint {bot2.name} {' '.join(map(str, arena.spawnCoords[1]))}")

def getOpenArena():
    for arena in arenas:
        if arena.status == "open":
            return arena
    return None

@app.post("/backprop/{version}")
async def backprop(version: str, request: Request):
    """
    Conducts backpropagation on the model.
    Trains the PPO model on collected experience.
    """
    data = await request.json()
    
    batch_size = data.get("batch_size", 64)
    epochs = data.get("epochs", 4)
    
    # Train the PPO agent
    try:
        agent = fast_rl_agent if fast_rl_agent else ppo_agent
        if agent is None:
            return {"status": "error", "message": "No agent available"}
        stats = agent.train(batch_size=batch_size, epochs=epochs)
        return {
            "status": "success",
            "version": version,
            **stats
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "version": version
        }

@app.get("/set-action-space")
async def get_action_space():
    """
    Returns the current action space configuration.
    """
    return action_space_config

@app.post("/set-action-space")
async def set_action_space(request: Request):
    """
    Sets the action space configuration.
    """
    global action_space_config
    data = await request.json()
    action_space_config.update(data)
    return {"status": "success", "config": action_space_config}

@app.get("/set-observation-space")
async def get_observation_space():
    """
    Returns the current observation space configuration.
    """
    return observation_space_config

@app.post("/set-observation-space")
async def set_observation_space(request: Request):
    """
    Sets the observation space configuration.
    """
    global observation_space_config
    data = await request.json()
    observation_space_config.update(data)
    return {"status": "success", "config": observation_space_config}

@app.get("/set-model")
async def get_model(request: Request):
    """
    Returns the model version for a specific bot.
    Expects bot_name as query parameter.
    """
    bot_name = request.query_params.get("bot_name")
    if not bot_name:
        return {"status": "error", "message": "bot_name query parameter required"}
    
    model_version = bot_model_mapping.get(bot_name, "0.0")
    return {
        "status": "success",
        "bot_name": bot_name,
        "version": model_version
    }

@app.post("/set-model")
async def set_model(request: Request):
    """
    Sets the model version mapping for bots.
    Accepts JSON with bot_name -> model_version mapping.
    Example: {"Bot1_pvp1": "0.0", "Bot2_pvp2": "0.1"}
    Or single bot: {"bot_name": "Bot1_pvp1", "version": "0.0"}
    """
    global bot_model_mapping
    data = await request.json()
    
    # Check if it's a single bot assignment
    if "bot_name" in data and "version" in data:
        bot_name = data["bot_name"]
        version = data["version"]
        bot_model_mapping[bot_name] = version
        return {
            "status": "success",
            "bot_name": bot_name,
            "version": version
        }
    
    # Otherwise, treat as a mapping of bot names to versions
    if isinstance(data, dict):
        bot_model_mapping.update(data)
        return {
            "status": "success",
            "mapping": bot_model_mapping
        }
    
    return {"status": "error", "message": "Invalid request format"}

@app.post("/save-model")
async def save_model(request: Request):
    """
    Saves the active model to disk.
    """
    data = await request.json()
    model_path = data.get("path", f"models/model_{int(time.time())}.pt")
    
    # Create models directory if it doesn't exist
    os.makedirs(os.path.dirname(model_path) if os.path.dirname(model_path) else "models", exist_ok=True)
    
    try:
        ppo_agent.save(model_path)
        return {
            "status": "success",
            "path": model_path,
            "message": "Model saved successfully"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "path": model_path
        }

@app.post("/add-reward/")
async def add_reward(request: Request):
    """
    Adds reward/event information for a bot.
    Used to track damage dealt, damage taken, good aim, etc.
    
    Event types from mod (as per RLControllerStrategy.java):
    - damage_dealt: Bot dealt damage (amount = damage dealt)
    - damage_taken: Bot took damage (amount = damage taken)
    - good_aim: Bot is aiming at enemy (amount = aim quality, optional)
    - won_duel: Bot won a duel
    - death: Bot died
    
    These rewards are ADDED to any auto-calculated rewards from observation analysis.
    """
    data = await request.json()
    bot_name = data.get("bot_name")
    events = data.get("events", [])
    current_state = data.get("current_state", {})
    
    if not bot_name:
        return {"status": "error", "message": "bot_name is required"}
    
    # Update bot state (use current_state from request, or merge with existing)
    if current_state:
        if bot_name not in bot_states:
            bot_states[bot_name] = {}
        bot_states[bot_name].update(current_state)
        # Also update latest observation if provided
        if "player" in current_state or "entities" in current_state:
            bot_states[bot_name]["latest_observation"] = current_state
            bot_states[bot_name]["latest_observation_time"] = datetime.now().isoformat()
    
    # Add reward to agent
    agent = fast_rl_agent if fast_rl_agent else ppo_agent
    if agent and events:
        # Use current_state if provided, otherwise use stored state
        state_to_use = current_state if current_state else bot_states.get(bot_name, {})
        agent.add_reward(bot_name, state_to_use, events)
        agent.add_done(False)  # Not done unless explicitly set
    
    return {
        "status": "success",
        "bot_name": bot_name,
        "events_count": len(events),
        "events": events  # Echo back for debugging
    }

@app.post("/start-duel/")
async def start_duel(request: Request):
    """
    Starts a duel between two bots.
    Gives bots items, heals them, and teleports them to arena.
    """
    data = await request.json()
    bot1_name = data.get("bot1")
    bot2_name = data.get("bot2")
    
    bot1 = getBotByName(bot1_name)
    bot2 = getBotByName(bot2_name)
    
    if not bot1 or not bot2:
        return {"status": "error", "message": "One or both bots not found"}
    
    # Give kits
    await giveKit(bot1)
    await giveKit(bot2)
    
    # Heal bots
    await send_mc_command(f"/heal {bot1_name}")
    await send_mc_command(f"/heal {bot2_name}")
    
    # Get arena and teleport
    arena = getOpenArena()
    if arena:
        bot1.setArena(arena)
        bot2.setArena(arena)
        arena.status = "closed"
        
        # Teleport bots to arena positions
        await send_mc_command(f"/tp {bot1_name} {' '.join(map(str, arena.spawnCoords[0]))}")
        await send_mc_command(f"/tp {bot2_name} {' '.join(map(str, arena.spawnCoords[1]))}")
        
        # Set spawn points at arena positions
        await send_mc_command(f"/spawnpoint {bot1_name} {' '.join(map(str, arena.spawnCoords[0]))}")
        await send_mc_command(f"/spawnpoint {bot2_name} {' '.join(map(str, arena.spawnCoords[1]))}")
        
        bot1.updateBot("fighting")
        bot2.updateBot("fighting")
        return {"status": "success", "arena": arena.name}
    else:
        return {"status": "error", "message": "No open arenas available"}

@app.get("/game-state")
async def get_game_state():
    """
    Returns the current game state including bots, arenas, and statistics.
    """
    # Get bot information
    bots_data = []
    for bot in botController.bots:
        # Calculate tick rate if available
        # Multiply by 20/3 because API is called once every 3 ticks
        tick_rate = 20.0  # Default
        if bot.name in tick_times and len(tick_times[bot.name]) >= 2:
            intervals = []
            for i in range(1, len(tick_times[bot.name])):
                intervals.append(tick_times[bot.name][i] - tick_times[bot.name][i-1])
            if intervals:
                intervals.sort()
                percentile_idx = int(len(intervals) * 0.9)
                if percentile_idx >= len(intervals):
                    percentile_idx = len(intervals) - 1
                avg_interval = intervals[percentile_idx]
                if avg_interval > 0:
                    # Calculate API call rate, then multiply by 20/3 to get actual game TPS
                    api_call_rate = 1.0 / avg_interval
                    tick_rate = api_call_rate * (20.0 / 3.0)
        
        bot_info = {
            "name": bot.name,
            "status": bot.status,
            "pair": bot.pair.name if hasattr(bot, 'pair') and bot.pair != "NONE" else None,
            "arena": bot.arena.name if hasattr(bot, 'arena') and bot.arena else None,
            "model_version": bot_model_mapping.get(bot.name, "0.0"),
            "tick_count": bot_tick_counts.get(bot.name, 0),
            "tick_rate": tick_rate
        }
        
        bots_data.append(bot_info)
    
    # Get arena information
    arenas_data = []
    for arena in arenas:
        arenas_data.append({
            "name": arena.name,
            "status": arena.status,
            "spawn_coords": arena.spawnCoords
        })
    
    # Get training statistics
    agent = fast_rl_agent if fast_rl_agent else ppo_agent
    training_stats = {
        "total_samples": len(agent.observations) if agent else 0,
        "backprop_interval": BACKPROP_INTERVAL,
        "observation_dim": obs_dim if 'obs_dim' in globals() else 0,
        "action_dim": act_dim if 'act_dim' in globals() else 0,
        "last_loss": fast_rl_agent.last_loss if fast_rl_agent else 0.0,
        "last_score": fast_rl_agent.last_score if fast_rl_agent else 0.0
    }
    
    # Add bot-specific metrics
    for bot_info in bots_data:
        bot_name = bot_info["name"]
        if fast_rl_agent:
            metrics = fast_rl_agent.get_bot_metrics(bot_name)
            bot_info["score"] = metrics["score"]
            bot_info["loss"] = metrics["loss"]
            bot_info["total_rewards"] = metrics["total_rewards"]
        else:
            bot_info["score"] = 0.0
            bot_info["loss"] = 0.0
            bot_info["total_rewards"] = 0
    
    return {
        "bots": bots_data,
        "arenas": arenas_data,
        "training": training_stats,
        "action_space": action_space_config,
        "observation_space": observation_space_config,
        "model_mappings": bot_model_mapping
    }

@app.get("/stats")
async def get_stats():
    """
    Returns detailed training statistics.
    """
    stats = {
        "bot_tick_counts": bot_tick_counts,
        "total_bots": len(botController.bots),
        "active_bots": len([b for b in botController.bots if b.status == "fighting"]),
        "ready_bots": len([b for b in botController.bots if b.status == "ready"]),
        "dead_bots": len([b for b in botController.bots if b.status == "dead"]),
        "open_arenas": len([a for a in arenas if a.status == "open"]),
        "closed_arenas": len([a for a in arenas if a.status == "closed"]),
        "rl_samples": len(fast_rl_agent.observations) if fast_rl_agent else (len(ppo_agent.observations) if ppo_agent else 0),
        "rl_rewards": len(fast_rl_agent.rewards) if fast_rl_agent else (len(ppo_agent.rewards) if ppo_agent else 0),
        "last_loss": fast_rl_agent.last_loss if fast_rl_agent else 0.0,
        "last_score": fast_rl_agent.last_score if fast_rl_agent else 0.0
    }
    return stats

@app.get("/training-logs")
async def get_training_logs():
    """
    Returns training logs - statistics recorded every 400 ticks.
    """
    return {
        "logs": training_logs[-100:],  # Return last 100 entries
        "total_logs": len(training_logs),
        "backprop_interval": BACKPROP_INTERVAL
    }

@app.get("/reward-progression")
async def get_reward_progression():
    """
    Returns reward progression data for graphing.
    Extracts reward data from training logs.
    """
    progression = []
    for log in training_logs:
        progression.append({
            "timestamp": log["timestamp"],
            "interval": len(progression) + 1,  # Interval number (1, 2, 3, ...)
            "total_rewards": log["training_stats"]["total_rewards"],
            "avg_reward": log["training_stats"]["avg_reward_per_sample"],
            "loss": log["training_stats"]["loss"],
            "samples_trained": log["training_stats"]["samples_trained"],
            "bot_rewards": {name: stats["score"] for name, stats in log["bot_statistics"].items()}
        })
    
    return {
        "progression": progression[-50:],  # Last 50 intervals
        "total_intervals": len(progression)
    }

@app.get("/bot-observation/{bot_name}")
async def get_bot_observation(bot_name: str):
    """
    Returns the latest observation data for a specific bot.
    Normalizes yaw to -180 to 180 range for display.
    """
    if bot_name not in bot_states or "latest_observation" not in bot_states[bot_name]:
        return {
            "status": "error",
            "message": f"No observation data found for bot {bot_name}"
        }
    
    # Get observation and normalize yaw for display
    observation = bot_states[bot_name]["latest_observation"].copy()
    if 'player' in observation and 'yaw' in observation['player']:
        observation['player'] = observation['player'].copy()
        observation['player']['yaw'] = normalize_yaw(observation['player']['yaw'])
    
    return {
        "status": "success",
        "bot_name": bot_name,
        "observation": observation,
        "timestamp": bot_states[bot_name].get("latest_observation_time", ""),
        "tick_count": bot_tick_counts.get(bot_name, 0)
    }