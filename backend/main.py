import os
import time
from fastapi import FastAPI, Request
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
from ppo_model import PPOAgent

arenas = areanaA.Arenas

app = FastAPI()

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
    "maxBlocks": 50,
    "maxInventorySlots": 36,
    "includeHealth": True,
    "includePosition": True,
    "includeRotation": True,
    "includeVelocity": True,
    "includeArmor": True
}

# Model configuration
current_model_version = "v1"
current_model_endpoint = None

# Tick timing tracking
tick_times = {}  # bot_name -> list of timestamps

# Initialize PPO Agent
# Estimate observation and action dimensions based on config
def estimate_observation_dim():
    """Estimate observation dimension based on config."""
    dim = 0
    if observation_space_config.get("includePlayerData", True):
        if observation_space_config.get("includeHealth", True): dim += 1
        if observation_space_config.get("includePosition", True): dim += 3
        if observation_space_config.get("includeRotation", True): dim += 2
        if observation_space_config.get("includeVelocity", True): dim += 3
        if observation_space_config.get("includeArmor", True): dim += 1
    if observation_space_config.get("includeEntityData", True):
        dim += observation_space_config.get("maxEntities", 10) * 15  # 15 features per entity
    if observation_space_config.get("includeBlockData", True):
        dim += observation_space_config.get("maxBlocks", 50) * 6  # 6 features per block
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

# Initialize PPO agent
obs_dim = estimate_observation_dim()
act_dim = estimate_action_dim()
ppo_agent = PPOAgent(
    observation_dim=obs_dim,
    action_dim=act_dim,
    lr=3e-4,
    gamma=0.99,
    eps_clip=0.2,
    value_coef=0.5,
    entropy_coef=0.01
)

# Bot state tracking for rewards
bot_states = {}  # bot_name -> current state
bot_events = {}  # bot_name -> list of events

# Tick counting for backprop
bot_tick_counts = {}  # bot_name -> tick count
BACKPROP_INTERVAL = 400  # Train every 400 ticks

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

async def trigger_backprop(bot_name: str = None):
    """
    Triggers backpropagation training.
    Can be called periodically or when a duel ends.
    """
    try:
        # Check if we have enough data to train
        # Need at least batch_size samples
        total_samples = len(ppo_agent.observations)
        if total_samples < 64:
            print(f"Skipping backprop for {bot_name or 'all bots'}: insufficient data ({total_samples} samples, need 64)")
            return {"status": "skipped", "reason": "insufficient_data", "samples": total_samples}
        
        # Train the model
        stats = ppo_agent.train(batch_size=64, epochs=4)
        print(f"Backprop completed for {bot_name or 'all bots'}: {stats}")
        return stats
    except Exception as e:
        print(f"Error in backprop: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

@app.post("/send-command/")
async def send_command(command: str):
    return await send_mc_command(command)

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
        ppo_agent.add_reward(name, bot_states[name], [{"type": "death", "amount": -1.0}])
        ppo_agent.add_done(True)
    
    # If bot has a pair, give winning reward to the pair
    if hasattr(bot, 'pair') and bot.pair and bot.pair != "NONE":
        pair_name = bot.pair.name
        if pair_name in bot_states:
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

def getOpenArena():
    for arena in arenas:
        if arena.status == "open":
            return arena
    return None

@app.post("/predict-action/{version}")
async def predict_action(version: str, request: Request):
    """
    Predicts an action using the PPO model.
    Receives observation and action space, returns action.
    Tracks timing for tick rate management.
    """
    start_time = time.time()
    data = await request.json()
    
    observation = data.get("observation", {})
    action_space = data.get("action_space", action_space_config)
    bot_name = data.get("bot_name", "unknown")
    
    # Store current state for reward calculation
    bot_states[bot_name] = observation
    
    # Use PPO agent to predict action
    try:
        action = ppo_agent.predict_action(observation, action_space)
    except Exception as e:
        print(f"Error in predict_action: {e}")
        # Fallback to default action
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
    
    # Calculate processing time
    processing_time = time.time() - start_time
    
    # Track tick timing
    current_time = time.time()
    if bot_name not in tick_times:
        tick_times[bot_name] = []
    tick_times[bot_name].append(current_time)
    
    # Keep only last 20 ticks
    if len(tick_times[bot_name]) > 20:
        tick_times[bot_name] = tick_times[bot_name][-20:]
    
    # Calculate tick rate based on 90th percentile of past 20 ticks
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
                tick_rate = 1.0 / avg_interval
    
    # Increment tick count and check if backprop is needed
    if bot_name not in bot_tick_counts:
        bot_tick_counts[bot_name] = 0
    bot_tick_counts[bot_name] += 1
    
    # Trigger backprop every 400 ticks
    if bot_tick_counts[bot_name] >= BACKPROP_INTERVAL:
        bot_tick_counts[bot_name] = 0
        # Trigger backprop asynchronously (don't block the response)
        asyncio.create_task(trigger_backprop(bot_name))
    
    return {
        "action": action,
        "tick_rate": tick_rate,
        "processing_time": processing_time
    }

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
        stats = ppo_agent.train(batch_size=batch_size, epochs=epochs)
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
async def get_model():
    """
    Returns the current model endpoint/version.
    """
    return {
        "version": current_model_version,
        "endpoint": current_model_endpoint
    }

@app.post("/set-model")
async def set_model(request: Request):
    """
    Sets the model endpoint/version to be used by the bot.
    """
    global current_model_version, current_model_endpoint
    data = await request.json()
    
    if "endpoint" in data:
        current_model_endpoint = data["endpoint"]
    if "version" in data:
        current_model_version = data["version"]
    
    return {
        "status": "success",
        "version": current_model_version,
        "endpoint": current_model_endpoint
    }

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
    """
    data = await request.json()
    bot_name = data.get("bot_name")
    events = data.get("events", [])
    current_state = data.get("current_state", {})
    
    if not bot_name:
        return {"status": "error", "message": "bot_name is required"}
    
    # Update bot state
    if current_state:
        bot_states[bot_name] = current_state
    
    # Add reward to PPO agent
    if bot_name in bot_states:
        ppo_agent.add_reward(bot_name, bot_states[bot_name], events)
        ppo_agent.add_done(False)  # Not done unless explicitly set
    
    return {
        "status": "success",
        "bot_name": bot_name,
        "events_count": len(events)
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
        await send_mc_command(f"/tp {bot1_name} {' '.join(map(str, arena.spawnCoords[0]))}")
        await send_mc_command(f"/tp {bot2_name} {' '.join(map(str, arena.spawnCoords[1]))}")
        bot1.updateBot("fighting")
        bot2.updateBot("fighting")
        return {"status": "success", "arena": arena.name}
    else:
        return {"status": "error", "message": "No open arenas available"}