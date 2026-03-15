import math
import os
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from mcrcon import MCRcon
import asyncio
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

# Protects all pairing, arena assignment, and episode reset operations
_match_lock = asyncio.Lock()

# Serve static files (frontend)
import os
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    try:
        app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    except:
        pass  # Directory might not exist yet

@app.on_event("startup")
async def _startup_idle_checker():
    """Background loop that checks for idle bots every 10 seconds."""
    async def _loop():
        while True:
            await asyncio.sleep(10)
            _check_bot_idle()
    asyncio.create_task(_loop())

@app.on_event("shutdown")
async def _shutdown_cleanup():
    """Save model and close RCON on shutdown."""
    try:
        _autosave_model("shutdown")
    except Exception:
        pass
    try:
        _close_rcon()
    except Exception:
        pass

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
    "enableMovement": False,
    "enableJump": False,
    "enableSneak": False,
    "enableSprint": False,
    "enableAttack": False,
    "enableUseItem": False,
    "enableHotbar": False,
    "enableLook": True,
    "movementBins": 8,
    "yawBins": 9,
    "pitchBins": 5
}

observation_space_config = {
    "includePlayerData": True,
    "includeEntityData": True,
    "includeBlockData": False,
    "includeInventoryData": False,
    "maxEntities": 10,
    "maxBlocks": 0,  # REDUCED from 50 to 20 for performance
    "maxInventorySlots": 36,
    "includeHealth": True,
    "includePosition": True,
    "includeRotation": True,
    "includeVelocity": False,
    "includeArmor": False
}

# Experiment mode: set CAMBIUM_EXPERIMENT=baseline to disable training (collect random-policy data only)
EXPERIMENT_MODE = os.getenv("CAMBIUM_EXPERIMENT", "training")
NO_TRAIN = os.getenv("CAMBIUM_NO_TRAIN", "0") == "1" or EXPERIMENT_MODE == "baseline"

# Sparse reward ablation (2.3): types zeroed in sparse mode; exclude from backup aggregation when CAMBIUM_REWARD_MODE=sparse
SPARSE_ZERO_REWARD_TYPES = frozenset({'good_aim', 'proximity', 'pitch_control', 'aim_hold', 'extreme_pitch_penalty'})
# Reward types that form the "sparse component" for fair comparison across baseline / sparse / shaped runs
SPARSE_COMPONENT_TYPES = frozenset({'damage_dealt', 'damage_taken', 'won_duel', 'death', 'episode_timeout', 'no_damage_penalty'})
# Fixed order of reward-type columns for CSV so header and every row have the same columns (no unnamed trailing columns)
CSV_REWARD_TYPES = (
    'aim_hold', 'damage_dealt', 'damage_taken', 'death', 'episode_timeout',
    'extreme_pitch_penalty', 'good_aim', 'no_damage_penalty', 'pitch_control',
    'proximity', 'won_duel'
)

# Model configuration - maps bot names to model versions
# In baseline mode, bots still use 0.1 path (so observations/rewards are recorded)
# but actions are sampled randomly instead of from the policy network.
_DEFAULT_VERSION = "0.1"
bot_model_mapping = {
    "Bot1": _DEFAULT_VERSION,
    "Bot2": _DEFAULT_VERSION,
}  # bot_name -> model_version (e.g., "0.0", "0.1", etc.)

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

# ---------------------------------------------------------------------------
# Logging setup (must be before agent init so auto-resume can log)
# ---------------------------------------------------------------------------
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
_experiment_tag = f"_{EXPERIMENT_MODE}" if EXPERIMENT_MODE != "training" else ""
_log_session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + _experiment_tag
EVENT_LOG_PATH = os.path.join(LOGS_DIR, f"events_{_log_session_id}.log")

def _log_event(category: str, message: str, **extra):
    """Append a timestamped event line to the event log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = f"[{ts}] [{category}] {message}"
    if extra:
        details = "  ".join(f"{k}={v}" for k, v in extra.items())
        parts += f"  ({details})"
    try:
        with open(EVENT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(parts + "\n")
    except Exception:
        pass
    print(parts)

_log_event("SERVER", "Backend process starting", session=_log_session_id,
           experiment=EXPERIMENT_MODE, no_train=NO_TRAIN)

# Initialize Fast RL agent (for version 0.1)
try:
    # Fast RL model always uses fixed 194-dim vector (7 player + 60 entities + 100 blocks + 27 inventory)
    # regardless of observation_space_config, so we hardcode it here
    obs_dim = 194
    # Remove act_dim - not needed anymore
    rl_device = os.getenv("CAMBIUM_DEVICE", "cpu")
    fast_rl_agent = FastRLAgent(
        observation_dim=obs_dim,
        device=rl_device,
        hidden_dim=256
    )
    print(f"Fast RL agent initialized successfully: obs_dim={obs_dim}, device={rl_device}")

    # Auto-resume: look for the most recent .pt file in models/
    # In baseline mode, skip auto-resume so the agent starts with random weights
    _models_dir = os.path.join(os.path.dirname(__file__), "models")
    if NO_TRAIN:
        _log_event("SERVER", "Baseline mode: skipping model auto-resume (random weights)")
    elif os.path.isdir(_models_dir):
        import glob as _glob
        _pt_files = sorted(_glob.glob(os.path.join(_models_dir, "model_*.pt")),
                           key=os.path.getmtime)
        if _pt_files:
            _latest = _pt_files[-1]
            try:
                fast_rl_agent.load(_latest)
                _log_event("SERVER", f"Resumed model from {_latest}")
                _stats_file = _latest.replace(".pt", "_stats.json")
                if os.path.exists(_stats_file):
                    with open(_stats_file) as _sf:
                        _prev = json.load(_sf)
                    _log_event("SERVER", "Previous session stats",
                               intervals=_prev.get('training_intervals', 0),
                               samples=_prev.get('total_samples_trained', 0),
                               reward=_prev.get('total_reward_accumulated', 0),
                               reason=_prev.get('reason', 'manual'))
            except Exception as _le:
                print(f"[STARTUP] Could not load {_latest}: {_le} — starting fresh")
        else:
            print("[STARTUP] No saved models found — starting fresh")
    else:
        print("[STARTUP] Models directory not found — starting fresh")

    ppo_agent = None
except Exception as e:
    print(f"ERROR initializing Fast RL agent on {rl_device}: {e}")
    if rl_device != "cpu":
        print("Falling back to CPU for RL agent...")
        try:
            fast_rl_agent = FastRLAgent(
                observation_dim=obs_dim,
                device="cpu",
                hidden_dim=256
            )
            print(f"Fast RL agent initialized on CPU (fallback): obs_dim={obs_dim}")
        except Exception as e2:
            print(f"ERROR initializing Fast RL agent on CPU fallback: {e2}")
            fast_rl_agent = None
    else:
        fast_rl_agent = None
    ppo_agent = None

# Bot state tracking for rewards
bot_states = {}  # bot_name -> current state
bot_events = {}  # bot_name -> list of events

# Reward event logging - stores recent reward events per bot for frontend display
bot_reward_events = {}  # bot_name -> list of reward event dicts with timestamp
MAX_REWARD_EVENTS_PER_BOT = 100  # Keep last 100 reward events per bot

# Tick counting for backprop
bot_tick_counts = {}  # bot_name -> tick count
BACKPROP_INTERVAL = 200  # Train every 200 ticks (more samples = lower variance)

# Episode length cap - force episode end after N seconds (prevents 10-15 min duels)
# Override with CAMBIUM_EPISODE_TIMEOUT_SEC for ablation experiments (e.g. 120).
bot_episode_start = {}  # bot_name -> wall-clock time when current episode started
MAX_EPISODE_LENGTH_SEC = int(os.getenv("CAMBIUM_EPISODE_TIMEOUT_SEC", "15"))
timeout_killed_bots = set()  # bots killed by episode timeout — death endpoint should ignore these
bot_episode_damage_dealt: Dict[str, int] = {}  # bot_name -> count of damage_dealt events this episode
_bot_reset_until = {}  # bot_name -> timestamp: suppress damage events from /kill commands during reset

# Tick timing tracking for TPS calculation
tick_times = {}  # bot_name -> list of timestamps

# Training log tracking - stores statistics every 100 ticks
training_logs = []  # List of dicts with timestamp, stats, rewards, etc.
MAX_LOG_ENTRIES = 1000  # Keep last 1000 log entries

# ---------------------------------------------------------------------------
# File-based training logger (human-readable .log + machine-readable .csv)
# ---------------------------------------------------------------------------
TRAINING_LOG_PATH = os.path.join(LOGS_DIR, f"training_{_log_session_id}.log")
TRAINING_CSV_PATH = os.path.join(LOGS_DIR, f"training_{_log_session_id}.csv")
_csv_header_written = False
_training_interval_counter = 0

# Bot activity tracker — detect disconnects via inactivity
_bot_last_seen: Dict[str, float] = {}
_bot_connected: Dict[str, bool] = {}
BOT_IDLE_TIMEOUT_SEC = 30  # consider a bot disconnected after 30s of silence

def _mark_bot_active(bot_name: str):
    """Called on every predict-action / add-reward to track bot liveness."""
    now = time.time()
    prev = _bot_last_seen.get(bot_name)
    _bot_last_seen[bot_name] = now

    if not _bot_connected.get(bot_name):
        _bot_connected[bot_name] = True
        if prev is None:
            _log_event("BOT", f"{bot_name} connected (first seen)")
        else:
            gap = now - prev
            _log_event("BOT", f"{bot_name} reconnected after {gap:.0f}s idle")

def _check_bot_idle():
    """Check all known bots for idle timeout. Call periodically."""
    now = time.time()
    for bot_name, last in list(_bot_last_seen.items()):
        if _bot_connected.get(bot_name) and (now - last) > BOT_IDLE_TIMEOUT_SEC:
            _bot_connected[bot_name] = False
            idle_for = now - last
            _log_event("BOT", f"{bot_name} went idle (no data for {idle_for:.0f}s)")


# ---------------------------------------------------------------------------
# Auto-save & crash defense
# ---------------------------------------------------------------------------
AUTOSAVE_INTERVAL = 50  # Save model every N training intervals
_autosave_counter = 0
AUTOSAVE_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(AUTOSAVE_DIR, exist_ok=True)

_AUTOSAVE_PREFIX = "autosave_"

def _autosave_model(reason: str = "autosave"):
    """Save the model to disk. Overwrites the single rolling autosave file.
    Shutdown saves get a unique name; periodic saves overwrite the same file."""
    agent = fast_rl_agent or ppo_agent
    if agent is None:
        print(f"[AUTOSAVE] Skipped ({reason}): no agent")
        return
    try:
        total_intervals = len(training_logs)
        total_reward_all = 0.0
        total_samples_all = 0
        for log in training_logs:
            ts_stats = log.get("training_stats", {})
            total_reward_all += ts_stats.get("total_rewards", 0.0)
            total_samples_all += ts_stats.get("samples_trained", 0)

        summary = {
            "saved_at": datetime.now().isoformat(),
            "reason": reason,
            "training_intervals": total_intervals,
            "total_samples_trained": total_samples_all,
            "total_reward_accumulated": round(total_reward_all, 4),
            "avg_reward_per_sample": round(total_reward_all / max(total_samples_all, 1), 6),
            "bot_scores": agent.bot_scores if hasattr(agent, "bot_scores") else {},
        }

        if reason == "shutdown":
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_path = os.path.join(AUTOSAVE_DIR, f"model_{ts}_shutdown.pt")
            stats_path = os.path.join(AUTOSAVE_DIR, f"model_{ts}_shutdown_stats.json")
        else:
            model_path = os.path.join(AUTOSAVE_DIR, f"{_AUTOSAVE_PREFIX}latest.pt")
            stats_path = os.path.join(AUTOSAVE_DIR, f"{_AUTOSAVE_PREFIX}latest_stats.json")

        agent.save(model_path)
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print(f"[AUTOSAVE] Model saved ({reason}): {model_path}  "
              f"intervals={total_intervals}, samples={total_samples_all}, "
              f"reward={total_reward_all:.2f}")
    except Exception as e:
        print(f"[AUTOSAVE] FAILED ({reason}): {e}")
        import traceback
        traceback.print_exc()




def _write_training_log(stats: Dict, reward_type_data: Dict, bot_stats: Dict,
                        samples: int, trigger_reason: str,
                        sparse_component_reward: float = None):
    """Append one interval's stats to the .log and .csv files."""
    global _csv_header_written, _training_interval_counter
    _training_interval_counter += 1
    interval = _training_interval_counter
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    loss        = stats.get("loss", 0.0)
    policy_loss = stats.get("policy_loss", 0.0)
    value_loss  = stats.get("value_loss", 0.0)
    entropy     = stats.get("entropy", 0.0)
    ret_mean    = stats.get("return_mean", 0.0)
    ret_std     = stats.get("return_std", 0.0)
    score       = stats.get("score", 0.0)
    ppo_updates = stats.get("ppo_updates", 0)
    avg_reward  = score / max(samples, 1)
    if sparse_component_reward is None:
        sparse_component_reward = sum(
            reward_type_data.get(rt, {}).get("amount", 0.0) for rt in SPARSE_COMPONENT_TYPES
        )

    # Per-reward-type breakdown (human-readable log: only types present)
    rt_lines = []
    for rtype in sorted(reward_type_data.keys()):
        rd = reward_type_data[rtype]
        cnt = rd.get("count", 0)
        amt = rd.get("amount", 0.0)
        rt_lines.append(f"    {rtype:25s}  count={cnt:4d}  total={amt:+9.4f}  avg={amt/max(cnt,1):+.4f}")
    # CSV: fixed set of columns so header and every row match (no unnamed trailing columns)
    rt_csv_parts = {}
    for rtype in CSV_REWARD_TYPES:
        rd = reward_type_data.get(rtype, {})
        rt_csv_parts[f"r_{rtype}_count"] = rd.get("count", 0)
        rt_csv_parts[f"r_{rtype}_total"] = round(rd.get("amount", 0.0), 4)

    # --- Human-readable log ---
    block = [
        f"{'='*70}",
        f"  Interval {interval}  |  {ts}  |  trigger: {trigger_reason}",
        f"{'='*70}",
        f"  Samples:        {samples}",
        f"  PPO updates:    {ppo_updates}",
        f"  Total reward:   {score:+.4f}",
        f"  Sparse component (comparable): {sparse_component_reward:+.4f}",
        f"  Avg reward/step:{avg_reward:+.6f}",
        f"  Return mean:    {ret_mean:+.4f}   std: {ret_std:.4f}",
        f"  Loss:           {loss:.6f}  (policy={policy_loss:.6f}  value={value_loss:.6f})",
        f"  Entropy:        {entropy:.4f}",
        f"  Reward breakdown:",
    ]
    if rt_lines:
        block.extend(rt_lines)
    else:
        block.append("    (none)")

    # Bot scores
    for bname, bdata in bot_stats.items():
        block.append(f"  Bot {bname}: score={bdata.get('score',0):.2f}  ticks={bdata.get('tick_count',0)}  status={bdata.get('status','?')}")
    block.append("")

    with open(TRAINING_LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(block) + "\n")

    # --- CSV (one row per interval, easy to graph) ---
    base_fields = {
        "interval": interval,
        "timestamp": ts,
        "samples": samples,
        "ppo_updates": ppo_updates,
        "total_reward": round(score, 4),
        "sparse_component_reward": round(sparse_component_reward, 4),
        "avg_reward": round(avg_reward, 6),
        "return_mean": round(ret_mean, 4),
        "return_std": round(ret_std, 4),
        "loss": round(loss, 6),
        "policy_loss": round(policy_loss, 6),
        "value_loss": round(value_loss, 6),
        "entropy": round(entropy, 4),
    }
    row = {**base_fields, **rt_csv_parts}

    with open(TRAINING_CSV_PATH, "a", encoding="utf-8") as f:
        if not _csv_header_written:
            f.write(",".join(row.keys()) + "\n")
            _csv_header_written = True
        f.write(",".join(str(v) for v in row.values()) + "\n")

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

def _estimate_reward_amount(event_type: str, event: dict) -> float:
    """Single source of truth for reward amounts (used by dashboard logging).
    Must stay in sync with FastRLAgent._compute_reward."""
    if event_type == 'damage_dealt':
        if 'damage_percentage' in event:
            return event.get('damage_percentage', 0) * 10.0
        return event.get('amount', 0) * 1.0
    if event_type == 'damage_taken':
        return -event.get('amount', 0) * 0.1
    if event_type == 'good_aim':
        return event.get('amount', 0.1) * 0.03
    if event_type == 'proximity':
        return event.get('amount', 0) * 0.5
    if event_type == 'pitch_control':
        return event.get('amount', 0) * 0.5
    if event_type == 'extreme_pitch_penalty':
        return event.get('amount', -0.03)
    if event_type == 'aim_hold':
        return event.get('amount', 0.05) * 0.6
    if event_type == 'won_duel':
        return 15.0
    if event_type == 'death':
        return -2.0
    if event_type == 'episode_timeout':
        return -1.0
    if event_type == 'no_damage_penalty':
        return -0.5
    return 0.0

def calculate_auto_rewards(bot_name: str, observation: Dict) -> List[Dict]:
    """
    Calculate automatic rewards that complement mod-sent rewards.
    Does NOT duplicate aim rewards (mod already sends those).
    """
    events = []
    
    # Safety check
    if 'player' not in observation or 'entities' not in observation:
        return events
    
    player = observation['player']
    entities = observation['entities']
    
    # Find nearest enemy player
    nearest_enemy = None
    min_dist = float('inf')
    
    for entity in entities:
        if entity.get('isPlayer', False):
            dx = entity.get('relativeX', 0)
            dy = entity.get('relativeY', 0)
            dz = entity.get('relativeZ', 0)
            dist = (dx**2 + dy**2 + dz**2)**0.5
            
            if dist < min_dist:
                min_dist = dist
                nearest_enemy = entity
    
    # === REWARD 1: Proximity (mod doesn't track this) ===
    # Encourage bot to get close to enemy
    # Constant reward within 3 blocks, then drops off beyond that
    if nearest_enemy is not None:
        if min_dist <= 3.0:
            proximity_reward = 0.01
        elif min_dist < 10.0:
            proximity_reward = 0.01 * (1.0 - (min_dist - 3.0) / 7.0)
        else:
            # No reward beyond 10 blocks
            proximity_reward = 0.0
        
        if proximity_reward > 0:
            events.append({
                "type": "proximity",
                "amount": proximity_reward
            })
    
    # === REWARD 2: Pitch Control ===
    # Reward for keeping pitch level (looking straight ahead).
    # Non-negative only: positive when pitch is reasonable, zero when extreme.
    current_pitch = player.get('pitch', 0)
    pitch_error = abs(current_pitch)
    
    # pitch=0° → 0.02, pitch=45° → 0.01, pitch=90° → 0.0
    # Kept small: fires every tick so total volume is high relative to sparse combat rewards
    pitch_reward = max(0.0, (1.0 - pitch_error / 90.0) * 0.02)
    
    events.append({
        "type": "pitch_control",
        "amount": pitch_reward
    })
    
    # === REWARD 3: Extreme Pitch Penalty ===
    # Penalize looking at sky/ground (|pitch| > 60°).
    if pitch_error > 60.0:
        events.append({
            "type": "extreme_pitch_penalty",
            "amount": -0.03
        })
    
    # === REWARD 4: Aim Hold ===
    # Bonus when on target AND pitch is level. Fires every tick when aimed, so kept small.
    # ~30 aimed ticks/episode × 0.05 = ~1.5 total — guides toward enemy without dominating.
    if nearest_enemy is not None and pitch_error < 30.0:
        dx = nearest_enemy.get('relativeX', 0)
        dy = nearest_enemy.get('relativeY', 0) + 0.9
        dz = nearest_enemy.get('relativeZ', 0)
        horizontal_dist = (dx**2 + dz**2)**0.5
        if horizontal_dist > 0.1:
            target_yaw = math.atan2(-dx, dz) * 180.0 / math.pi
            target_pitch = -math.atan2(dy, horizontal_dist) * 180.0 / math.pi
            player_yaw = normalize_yaw(player.get('yaw', 0))
            target_yaw_norm = normalize_yaw(target_yaw)
            yaw_diff = abs(normalize_yaw(player_yaw - target_yaw_norm))
            pitch_diff = abs(current_pitch - target_pitch)
            max_angle = max(yaw_diff, pitch_diff)
            if max_angle < 20.0:
                events.append({
                    "type": "aim_hold",
                    "amount": 0.05
                })
    
    return events

import threading
from concurrent.futures import ThreadPoolExecutor
from mcrcon import MCRconException

# ---------------------------------------------------------------------------
# Monkey-patch MCRcon so it uses socket.settimeout() instead of signal.alarm.
# signal.alarm only works in the main thread; we run RCON in a thread pool.
# ---------------------------------------------------------------------------
_MCRcon_orig_connect = MCRcon.connect

def _mcrcon_init_no_signal(self, host, password, port=25575, tlsmode=0, timeout=5):
    self.host = host
    self.password = password
    self.port = port
    self.tlsmode = tlsmode
    self.timeout = timeout

def _mcrcon_connect_with_socket_timeout(self):
    _MCRcon_orig_connect(self)
    if self.socket and self.timeout:
        self.socket.settimeout(self.timeout)

def _mcrcon_read_no_signal(self, length):
    data = b""
    while len(data) < length:
        chunk = self.socket.recv(length - len(data))
        if not chunk:
            raise MCRconException("Connection closed by server")
        data += chunk
    return data

MCRcon.__init__ = _mcrcon_init_no_signal
MCRcon.connect = _mcrcon_connect_with_socket_timeout
MCRcon._read = _mcrcon_read_no_signal
# ---------------------------------------------------------------------------

_rcon_lock = threading.Lock()
_rcon_conn: MCRcon | None = None
_rcon_pool = ThreadPoolExecutor(max_workers=1)

def _get_rcon() -> MCRcon:
    """Return (and lazily create) a persistent RCON connection."""
    global _rcon_conn
    if _rcon_conn is None:
        _rcon_conn = MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT)
        _rcon_conn.connect()
    return _rcon_conn

def _close_rcon():
    global _rcon_conn
    if _rcon_conn is not None:
        try:
            _rcon_conn.disconnect()
        except Exception:
            pass
        _rcon_conn = None

def mc_command(command: str) -> str:
    """Send an RCON command using the persistent connection with retry."""
    global _rcon_conn
    with _rcon_lock:
        for attempt in range(3):
            try:
                conn = _get_rcon()
                return conn.command(command)
            except Exception as e:
                print(f"[RCON ERROR] attempt {attempt+1}/3 '{command}': {e}")
                _close_rcon()
                if attempt == 2:
                    return f"RCON_FAIL: {e}"
                time.sleep(0.1 * (attempt + 1))
    return "RCON_FAIL: exhausted retries"

_gamerules_set = False
_RCON_SPACING_SEC = 0.02

async def send_mc_command(command: str):
    global _gamerules_set
    loop = asyncio.get_event_loop()
    if not _gamerules_set:
        _gamerules_set = True
        await loop.run_in_executor(_rcon_pool, mc_command, "/gamerule sendCommandFeedback false")
        await loop.run_in_executor(_rcon_pool, mc_command, "/gamerule commandBlockOutput false")
        await loop.run_in_executor(_rcon_pool, mc_command, "/gamerule logAdminCommands false")

    await asyncio.sleep(_RCON_SPACING_SEC)
    result = await loop.run_in_executor(_rcon_pool, mc_command, command)
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
    In NO_TRAIN mode (baseline experiment), logs reward stats but skips training.
    """
    try:
        agent = fast_rl_agent if fast_rl_agent else ppo_agent
        if agent is None:
            return {"status": "skipped", "reason": "no_agent"}
        
        all_rewards = []
        all_actions = []
        total_samples = 0
        if fast_rl_agent and hasattr(fast_rl_agent, '_buffers'):
            for buf in fast_rl_agent._buffers.values():
                total_samples += len(buf.observations)
                all_rewards.extend(buf.rewards)
                all_actions.extend(buf.actions)
        else:
            total_samples = len(agent.observations) if hasattr(agent, 'observations') else 0
            all_rewards = list(agent.rewards) if hasattr(agent, 'rewards') else []
            all_actions = list(agent.actions) if hasattr(agent, 'actions') else []

        if total_samples < 64:
            print(f"Skipping backprop for {bot_name or 'all bots'}: insufficient data ({total_samples} samples, need 64)")
            return {"status": "skipped", "reason": "insufficient_data", "samples": total_samples}

        total_rewards_before = sum(all_rewards) if all_rewards else 0.0
        avg_reward_before = total_rewards_before / len(all_rewards) if all_rewards else 0.0
        bot_rewards_before = {}
        if fast_rl_agent:
            bot_rewards_before = {name: score for name, score in fast_rl_agent.bot_scores.items()}

        try:
            if all_actions and isinstance(all_actions[0], dict):
                action_keys = ['movement', 'jump', 'attack', 'yaw', 'pitch']
                action_tuples = [tuple(a.get(k, 0) for k in action_keys) for a in all_actions]
            else:
                action_tuples = all_actions
            unique_actions = len(set(action_tuples)) if action_tuples else 0
            action_diversity = unique_actions / len(all_actions) if all_actions else 0.0
            print(f"{'[BASELINE] ' if NO_TRAIN else ''}Interval with {total_samples} samples, rewards: min={min(all_rewards) if all_rewards else 0:.4f}, "
                  f"max={max(all_rewards) if all_rewards else 0:.4f}, "
                  f"mean={avg_reward_before:.4f}, sum={total_rewards_before:.4f}, "
                  f"action_diversity={action_diversity:.2%} ({unique_actions}/{len(all_actions)} unique)")
        except (IndexError, AttributeError, TypeError) as e:
            print(f"{'[BASELINE] ' if NO_TRAIN else ''}Interval with {total_samples} samples, sum={total_rewards_before:.4f} (stats skipped: {e})")
        
        if NO_TRAIN:
            stats = {
                "loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0,
                "entropy": 0.0, "return_mean": 0.0, "return_std": 0.0,
                "score": total_rewards_before, "samples_trained": total_samples,
                "ppo_updates": 0,
            }
            if fast_rl_agent and hasattr(fast_rl_agent, '_buffers'):
                for buf in fast_rl_agent._buffers.values():
                    buf.clear()
            print(f"[BASELINE] Logged stats for {bot_name or 'all bots'}, skipped training (NO_TRAIN mode)")
        else:
            stats = agent.train(batch_size=64, epochs=4)
            print(f"Backprop completed for {bot_name or 'all bots'}: loss={stats.get('loss', 0):.6f}, "
                  f"policy_loss={stats.get('policy_loss', 0):.6f}, entropy={stats.get('entropy', 0):.4f}")
        
        # Calculate statistics after training
        # Note: stats["score"] is the sum of rewards before clearing, which is what we want
        total_rewards_for_interval = stats.get("score", total_rewards_before)  # Use score from stats (sum of rewards)
        loss = stats.get("loss", 0.0)
        samples_trained = stats.get("samples_trained", 0)
        
        # Aggregate reward type data from the interval.
        # (Buffers were just cleared by train(), so we use bot_reward_events backup below if this is empty.)
        reward_type_data = {}  # {type: {'count': int, 'amount': float}}
        
        if fast_rl_agent and hasattr(fast_rl_agent, '_buffers'):
            for buf in fast_rl_agent._buffers.values():
                for reward_type_dict in buf.reward_types:
                    for reward_type, data in reward_type_dict.items():
                        if reward_type not in reward_type_data:
                            reward_type_data[reward_type] = {'count': 0, 'amount': 0.0}
                        if isinstance(data, dict):
                            reward_type_data[reward_type]['count'] += data.get('count', 0)
                            reward_type_data[reward_type]['amount'] += data.get('amount', 0.0)
                        else:
                            reward_type_data[reward_type]['count'] += data
        
        # Also compute from bot_reward_events as backup (events that occurred since last backprop)
        # This ensures we capture all events even if fast_rl_agent.reward_types is incomplete
        current_time = datetime.now()
        # Find the timestamp of the last training log (if any) to determine the interval window
        last_log_time = None
        if training_logs and len(training_logs) > 0:
            try:
                last_log_ts = training_logs[-1].get("timestamp", "")
                if last_log_ts:
                    last_log_time = datetime.fromisoformat(last_log_ts.replace('Z', '+00:00') if 'Z' in last_log_ts else last_log_ts)
            except (ValueError, TypeError):
                pass
        
        # Aggregate events from bot_reward_events for this interval
        for bot_name, events in bot_reward_events.items():
            for event_log in events:
                event_ts = event_log.get("timestamp", "")
                if event_ts:
                    try:
                        event_ts_clean = event_ts.replace('Z', '+00:00') if 'Z' in event_ts else event_ts
                        event_dt = datetime.fromisoformat(event_ts_clean)
                        # Include events from the last backprop to now (or all events if no previous log)
                        if last_log_time is None or event_dt >= last_log_time:
                            event = event_log.get("event", {})
                            event_type = event.get("type", "")
                            if event_type:
                                # Sparse ablation: don't record shaping types in logs when CAMBIUM_REWARD_MODE=sparse
                                if os.getenv("CAMBIUM_REWARD_MODE") == "sparse" and event_type in SPARSE_ZERO_REWARD_TYPES:
                                    continue
                                if event_type not in reward_type_data:
                                    reward_type_data[event_type] = {'count': 0, 'amount': 0.0}
                                reward_type_data[event_type]['count'] += 1
                                amount = _estimate_reward_amount(event_type, event)
                                reward_type_data[event_type]['amount'] += amount
                    except (ValueError, TypeError):
                        continue
        
        # Debug logging
        if reward_type_data:
            print(f"[BACKPROP] Reward type data for interval: {reward_type_data}")
        else:
            print(f"[BACKPROP] WARNING: No reward types found")
        
        # Comparable metric: reward from sparse components only (same scale for baseline / sparse / shaped runs)
        sparse_component_reward = sum(
            reward_type_data.get(rt, {}).get("amount", 0.0) for rt in SPARSE_COMPONENT_TYPES
        )

        # Get current bot statistics
        bot_stats = {}
        for bot in botController.bots:
            bot_name_key = bot.name
            bot_stats[bot_name_key] = {
                "status": bot.status,
                "tick_count": bot_tick_counts.get(bot_name_key, 0),
                "score": fast_rl_agent.bot_scores.get(bot_name_key, 0.0) if fast_rl_agent else 0.0,
                "model_version": bot_model_mapping.get(bot_name_key, _DEFAULT_VERSION)
            }
        
        # Create log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "tick_interval": BACKPROP_INTERVAL,
            "bot_name": bot_name,
            "training_stats": {
                "samples_trained": samples_trained,
                "loss": loss,
                "policy_loss": stats.get("policy_loss", 0.0),
                "value_loss": stats.get("value_loss", 0.0),
                "entropy": stats.get("entropy", 0.0),
                "total_rewards": total_rewards_for_interval,
                "avg_reward_per_sample": avg_reward_before,
                "reward_delta": total_rewards_for_interval - total_rewards_before,
                "sparse_component_reward": sparse_component_reward,
                "reward_types": reward_type_data
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

        # Write to persistent log files
        try:
            _write_training_log(stats, reward_type_data, bot_stats,
                                samples_trained, bot_name or "all",
                                sparse_component_reward=sparse_component_reward)
        except Exception as log_err:
            print(f"[LOG] Failed to write training log: {log_err}")

        if not NO_TRAIN:
            global _autosave_counter
            _autosave_counter += 1
            if _autosave_counter >= AUTOSAVE_INTERVAL:
                _autosave_counter = 0
                _autosave_model(f"interval_{len(training_logs)}")

        return stats
    except Exception as e:
        print(f"Error in backprop: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

async def _reset_bots_after_timeout(bot):
    """Reset both bots after episode timeout — TP back, re-kit, and re-fight.
    No /kill needed: giveKit already clears inventory, heals to full, and
    fightBots applies saturation + teleports. Skipping /kill avoids the
    1-second respawn wait and phantom damage_taken events."""
    try:
        if bot is None:
            return
        if hasattr(bot, 'arena') and bot.arena:
            bot.arena.status = "open"
        if hasattr(bot, 'pair') and bot.pair and bot.pair != "NONE":
            suppress_until = time.time() + 2.0
            _bot_reset_until[bot.name] = suppress_until
            _bot_reset_until[bot.pair.name] = suppress_until
            bot.updateBot("ready")
            bot.pair.updateBot("ready")
            await fightBots(bot, bot.pair)
        else:
            _bot_reset_until[bot.name] = time.time() + 2.0
            bot.updateBot("ready")
            await giveKit(bot)
    except Exception as e:
        print(f"[RESET] Error resetting bots after timeout: {e}")
        import traceback
        traceback.print_exc()

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
    start_time = time.time()
    
    try:
        data = await request.json()
    except Exception as e:
        return {"action": {"movement": 0, "jump": False, "sneak": False, "sprint": False, "attack": False, "useItem": False, "hotbar": -1, "yaw": 0.0, "pitch": 0.0}}
    
    observation = data.get("observation", {})
    action_space = data.get("action_space", action_space_config)
    bot_name = data.get("bot_name", "unknown")

    _mark_bot_active(bot_name)

    # IMPORTANT: Increment tick count FIRST for ALL versions (this is the accurate tick counter)
    if bot_name not in bot_tick_counts:
        bot_tick_counts[bot_name] = 0
    bot_tick_counts[bot_name] += 1
    
    # Store latest observation for visualization
    if bot_name not in bot_states:
        bot_states[bot_name] = {}
    bot_states[bot_name]["latest_observation"] = observation
    bot_states[bot_name]["latest_observation_time"] = datetime.now().isoformat()
    
    # Auto-rewards are calculated AFTER action prediction (inside v0.1 handler)
    # so they're credited to the current step, not the previous one.
    
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
    
    # Backprop is triggered only on episode end (timeout or duel end), not every N ticks.
    # Still cap tick count so it doesn't grow unbounded (for logging).
    if bot_tick_counts[bot_name] >= BACKPROP_INTERVAL:
        bot_tick_counts[bot_name] = 0
    
    # Calibration mode for version 0.0
    if version == "0.0":
        result = await calibration_mode_action(bot_name)
        result["tick_rate"] = tick_rate
        
        return result
    
    # Version 0.1: Use Fast RL model (<50ms inference)
    if version == "0.1":
        # Store state for rewards (but don't overwrite latest_observation)
        if bot_name not in bot_states:
            bot_states[bot_name] = {}
        bot_states[bot_name]["current_state"] = observation
        
        # Check if Fast RL agent is available
        if fast_rl_agent is None:
            print(f"[PREDICT] WARNING: Fast RL agent not initialized, using random fallback")
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

            # Episode length cap: force episode end after MAX_EPISODE_LENGTH_SEC.
            # Only the first bot in a pair to detect the timeout handles it;
            # the paired bot's timer is also reset so it won't double-fire.
            now = time.time()
            if bot_name not in bot_episode_start:
                bot_episode_start[bot_name] = now
            elif (now - bot_episode_start[bot_name]) >= MAX_EPISODE_LENGTH_SEC:
                bot_obj = getBotByName(bot_name)
                pair_name = None
                if bot_obj and hasattr(bot_obj, 'pair') and bot_obj.pair and bot_obj.pair != "NONE":
                    pair_name = bot_obj.pair.name

                # Immediately reset BOTH timers so the paired bot's next
                # predict-action won't also trigger a timeout.
                bot_episode_start[bot_name] = now
                if pair_name:
                    bot_episode_start[pair_name] = now

                timeout_event = {"type": "episode_timeout", "amount": -0.1}

                timeout_events_self = [timeout_event]
                if bot_episode_damage_dealt.get(bot_name, 0) == 0:
                    timeout_events_self.append({"type": "no_damage_penalty"})
                    _log_event("REWARD", f"{bot_name} penalized for no damage dealt this episode")

                state = bot_states[bot_name].get("current_state", bot_states[bot_name].get("latest_observation", {}))
                fast_rl_agent.add_reward(bot_name, state, timeout_events_self)
                fast_rl_agent.add_done(bot_name, True)

                if pair_name:
                    timeout_events_pair = [timeout_event]
                    if bot_episode_damage_dealt.get(pair_name, 0) == 0:
                        timeout_events_pair.append({"type": "no_damage_penalty"})
                        _log_event("REWARD", f"{pair_name} penalized for no damage dealt this episode")
                    if pair_name in bot_states:
                        fast_rl_agent.add_reward(pair_name, bot_states[pair_name], timeout_events_pair)
                        fast_rl_agent.add_done(pair_name, True)
                    bot_episode_damage_dealt[pair_name] = 0
                    bot_tick_counts[pair_name] = 0

                asyncio.create_task(trigger_backprop(f"episode_timeout_{bot_name}"))
                bot_episode_damage_dealt[bot_name] = 0
                bot_tick_counts[bot_name] = 0
                _log_event("EPISODE", f"Timeout ({MAX_EPISODE_LENGTH_SEC}s) for {bot_name} — resetting both bots")

                async def _locked_reset(b):
                    async with _match_lock:
                        await _reset_bots_after_timeout(b)
                asyncio.create_task(_locked_reset(bot_obj))


            # Filter entities to only include the paired opponent (not spectators/user).
            # Then sort so the opponent is always in slot 0 of the observation vector,
            # giving the model a deterministic input layout.
            if 'entities' in observation:
                bot_obj = getBotByName(bot_name)
                pair_name = None
                if bot_obj and hasattr(bot_obj, 'pair') and bot_obj.pair and bot_obj.pair != "NONE":
                    pair_name = bot_obj.pair.name
                opponent = []
                non_players = []
                for ent in observation['entities']:
                    if ent.get('isPlayer', False):
                        ent_name = ent.get('name', '')
                        if pair_name and ent_name == pair_name:
                            opponent.append(ent)
                        elif not ent_name:
                            opponent.append(ent)
                    else:
                        non_players.append(ent)
                observation['entities'] = opponent + non_players

            if NO_TRAIN:
                action = fast_rl_agent.random_action(observation, action_space, bot_name=bot_name)
            else:
                action = fast_rl_agent.predict_action(observation, action_space, bot_name=bot_name)
            
            # Auto-rewards applied AFTER prediction so they credit the current step
            auto_reward_events = calculate_auto_rewards(bot_name, observation)
            if auto_reward_events:
                if bot_name not in bot_reward_events:
                    bot_reward_events[bot_name] = []
                for event in auto_reward_events:
                    bot_reward_events[bot_name].append({
                        "timestamp": datetime.now().isoformat(),
                        "bot_name": bot_name,
                        "event": event.copy(),
                        "source": "auto_calculated"
                    })
                if len(bot_reward_events[bot_name]) > MAX_REWARD_EVENTS_PER_BOT:
                    bot_reward_events[bot_name] = bot_reward_events[bot_name][-MAX_REWARD_EVENTS_PER_BOT:]
                fast_rl_agent.add_reward(bot_name, observation, auto_reward_events)
            
            pred_time = time.time() - pred_start
            if pred_time > 0.1:
                print(f"[PREDICT] Fast RL prediction took {pred_time*1000:.1f}ms for {bot_name} (target: <50ms)")
            bot_last_actions[bot_name] = action
            bot_action_timestamps[bot_name] = time.time()
        except Exception as e:
            print(f"[PREDICT] ERROR in Fast RL prediction for {bot_name}: {e}")
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
        
        return {
            "action": action,
            "tick_rate": tick_rate,
            "processing_time": processing_time
        }
    
    # Version 0.2+ would use PPO (when we fix it)
    # For now, fallback to random
    print(f"[PREDICT] Unknown version {version}, using random fallback")
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

@app.post("/bot-setup/")
async def bot_setup(request: Request):
    """
    Handles bot registration and reconnection.
    If the bot already exists (reconnecting after server crash), re-pair and re-fight.
    Otherwise create a new bot, give kit, pair, and start duel.
    """
    data = await request.json()
    name = data.get("name")

    async with _match_lock:
        existingBot = getBotByName(name)
        if existingBot is not None:
            print(f"Bot reconnected: {name} (already registered)")
            _log_event("BOT", f"{name} reconnected via bot-setup")

            oldPair = existingBot.pair
            if oldPair and oldPair != "NONE":
                oldPair.pair = "NONE"
                oldPair.updateBot("ready")
                if hasattr(oldPair, 'arena') and oldPair.arena:
                    oldPair.arena.status = "open"
                    oldPair.arena = ""

            existingBot.updateBot("ready")
            existingBot.pair = "NONE"
            if hasattr(existingBot, 'arena') and existingBot.arena:
                existingBot.arena.status = "open"
                existingBot.arena = ""

            bot_episode_start[name] = time.time()

            await giveKit(existingBot)

            move = botController.pairBot(existingBot)
            if move == 1:
                await fightBots(existingBot, existingBot.pair)
                return await send_mc_command(f"/say Bot {name} reconnected and paired with {existingBot.pair.name}!")
            else:
                return await send_mc_command(f"/say Bot {name} reconnected. Waiting for pair...")

        print(f"Bot setup for: {name}")
        currentBot = Bot(name, "ready", Kit(classicKit.kitStart, classicKit.kitEnd, name), "agent")
        botController.addBot(currentBot)
        await giveKit(currentBot)

        move = botController.pairBot(currentBot)
        if move == 1:
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

    async with _match_lock:
        bot = getBotByName(name)

        if not bot:
            return {"status": "error", "message": f"Bot {name} not found"}

        if name in timeout_killed_bots:
            timeout_killed_bots.discard(name)
            return {"status": "ignored", "message": f"Death for {name} caused by episode timeout, handled elsewhere"}

        _log_event("DUEL", f"{name} died", arena=getattr(bot, 'arena', None),
                   pair=getattr(bot, 'pair', None))
        bot.updateBot("dead")

        bot_episode_start[name] = time.time()
        pair = bot.pair if hasattr(bot, 'pair') and bot.pair and bot.pair != "NONE" else None
        if pair:
            bot_episode_start[pair.name] = time.time()

        if name in bot_states:
            death_event = {"type": "death", "amount": -1.0}

            if name not in bot_reward_events:
                bot_reward_events[name] = []
            bot_reward_events[name].append({
                "timestamp": datetime.now().isoformat(),
                "bot_name": name,
                "event": death_event.copy(),
                "source": "death_endpoint"
            })
            if len(bot_reward_events[name]) > MAX_REWARD_EVENTS_PER_BOT:
                bot_reward_events[name] = bot_reward_events[name][-MAX_REWARD_EVENTS_PER_BOT:]

            if fast_rl_agent:
                fast_rl_agent.add_reward(name, bot_states[name], [death_event])
                fast_rl_agent.add_done(name, True)
            elif ppo_agent:
                ppo_agent.add_reward(name, bot_states[name], [death_event])
                ppo_agent.add_done(name, True)

        if pair:
            pair_name = pair.name
            if pair_name in bot_states:
                won_duel_event = {"type": "won_duel", "amount": 10.0}

                if pair_name not in bot_reward_events:
                    bot_reward_events[pair_name] = []
                bot_reward_events[pair_name].append({
                    "timestamp": datetime.now().isoformat(),
                    "bot_name": pair_name,
                    "event": won_duel_event.copy(),
                    "source": "death_endpoint"
                })
                if len(bot_reward_events[pair_name]) > MAX_REWARD_EVENTS_PER_BOT:
                    bot_reward_events[pair_name] = bot_reward_events[pair_name][-MAX_REWARD_EVENTS_PER_BOT:]

                if fast_rl_agent:
                    fast_rl_agent.add_reward(pair_name, bot_states[pair_name], [won_duel_event])
                    fast_rl_agent.add_done(pair_name, True)
                elif ppo_agent:
                    ppo_agent.add_reward(pair_name, bot_states[pair_name], [won_duel_event])
                    ppo_agent.add_done(pair_name, True)

        asyncio.create_task(trigger_backprop(f"{name}_duel_end"))

        bot_episode_damage_dealt[name] = 0
        if pair:
            bot_episode_damage_dealt[pair.name] = 0

        if hasattr(bot, 'arena') and bot.arena:
            bot.arena.status = "open"

        if pair:
            bot.updateBot("ready")
            pair.updateBot("ready")
            await fightBots(bot, pair)
            return await send_mc_command(f"/say Bot {name} has died! Starting new duel.")
        else:
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
    """Pair two bots, claim an arena, teleport, and kit them.
    Caller MUST hold _match_lock."""
    # Release any arena these bots were previously in
    for b in (bot1, bot2):
        if hasattr(b, 'arena') and b.arena:
            b.arena.status = "open"
            b.arena = ""

    arena = getOpenArena()
    if arena is None:
        print(f"[MATCH] No open arenas for {bot1.name} and {bot2.name}")
        return

    # Atomically claim
    arena.status = "closed"
    bot1.updateBot("fighting")
    bot2.updateBot("fighting")
    bot1.setArena(arena)
    bot2.setArena(arena)
    bot1.pairAgainst(bot2)

    # Reset episode timers
    now = time.time()
    bot_episode_start[bot1.name] = now
    bot_episode_start[bot2.name] = now
    bot_episode_damage_dealt[bot1.name] = 0
    bot_episode_damage_dealt[bot2.name] = 0

    coords1 = ' '.join(map(str, arena.spawnCoords[0]))
    coords2 = ' '.join(map(str, arena.spawnCoords[1]))
    await send_mc_command(f"/tp {bot1.name} {coords1}")
    await send_mc_command(f"/tp {bot2.name} {coords2}")
    await giveKit(bot1)
    await giveKit(bot2)
    await send_mc_command(f"/effect {bot1.name} minecraft:saturation 9999 100")
    await send_mc_command(f"/effect {bot2.name} minecraft:saturation 9999 100")

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
    
    model_version = bot_model_mapping.get(bot_name, _DEFAULT_VERSION)
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

@app.get("/list-models")
async def list_models():
    """List all saved .pt model files with metadata."""
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    if not os.path.isdir(models_dir):
        return {"models": []}
    import glob as _g
    pt_files = sorted(_g.glob(os.path.join(models_dir, "*.pt")),
                      key=os.path.getmtime, reverse=True)
    result = []
    for pt in pt_files:
        name = os.path.basename(pt)
        stats_file = pt.replace(".pt", "_stats.json")
        meta = {}
        if os.path.exists(stats_file):
            try:
                with open(stats_file) as f:
                    meta = json.load(f)
            except Exception:
                pass
        result.append({
            "filename": name,
            "size_kb": round(os.path.getsize(pt) / 1024, 1),
            "modified": datetime.fromtimestamp(os.path.getmtime(pt)).isoformat(),
            "intervals": meta.get("training_intervals", 0),
            "samples": meta.get("total_samples_trained", 0),
            "reward": meta.get("total_reward_accumulated", 0),
            "reason": meta.get("reason", meta.get("label", "")),
        })
    return {"models": result}

@app.post("/load-model")
async def load_model(request: Request):
    """Load a specific .pt model file into the active agent."""
    data = await request.json()
    filename = data.get("filename", "")
    if not filename:
        return {"status": "error", "message": "filename is required"}
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    model_path = os.path.join(models_dir, filename)
    if not os.path.exists(model_path):
        return {"status": "error", "message": f"Model not found: {filename}"}
    agent = fast_rl_agent or ppo_agent
    if not agent:
        return {"status": "error", "message": "No agent initialized"}
    try:
        agent.load(model_path)
        training_logs.clear()
        _log_event("SERVER", f"Model loaded from dashboard: {filename}")
        stats_file = model_path.replace(".pt", "_stats.json")
        meta = {}
        if os.path.exists(stats_file):
            with open(stats_file) as f:
                meta = json.load(f)
        return {
            "status": "success",
            "message": f"Loaded {filename}",
            "intervals": meta.get("training_intervals", 0),
            "samples": meta.get("total_samples_trained", 0),
            "reward": meta.get("total_reward_accumulated", 0),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

@app.post("/reset-model")
async def reset_model():
    """Reset the agent to a fresh untrained state."""
    agent = fast_rl_agent
    if not agent:
        return {"status": "error", "message": "No agent initialized"}
    try:
        obs_dim = agent.observation_dim
        device = agent.device
        hidden = agent.net.shared[0].out_features
        agent.__init__(observation_dim=obs_dim, device=str(device), hidden_dim=hidden)
        training_logs.clear()
        _log_event("SERVER", "Model reset to fresh state from dashboard")
        return {"status": "success", "message": "Model reset to fresh untrained state"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

@app.post("/save-model")
async def save_model(request: Request):
    """
    Saves the active model and a companion stats JSON to disk.
    """
    data = await request.json()
    label = data.get("label", "")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = label.replace(" ", "_")[:40] if label else ""
    filename = f"model_{ts}{'_' + safe_label if safe_label else ''}"
    model_path = os.path.join(AUTOSAVE_DIR, f"{filename}.pt")
    stats_path = os.path.join(AUTOSAVE_DIR, f"{filename}_stats.json")

    try:
        agent = fast_rl_agent or ppo_agent

        # Gather training summary
        total_intervals = len(training_logs)
        recent = training_logs[-1] if training_logs else {}
        recent_stats = recent.get("training_stats", {})

        # Aggregate reward type totals across all logged intervals
        agg_rewards = {}
        total_reward_all = 0.0
        total_samples_all = 0
        for log in training_logs:
            ts_stats = log.get("training_stats", {})
            total_reward_all += ts_stats.get("total_rewards", 0.0)
            total_samples_all += ts_stats.get("samples_trained", 0)
            for rtype, rdata in ts_stats.get("reward_types", {}).items():
                if rtype not in agg_rewards:
                    agg_rewards[rtype] = {"count": 0, "amount": 0.0}
                if isinstance(rdata, dict):
                    agg_rewards[rtype]["count"] += rdata.get("count", 0)
                    agg_rewards[rtype]["amount"] += rdata.get("amount", 0.0)

        summary = {
            "saved_at": datetime.now().isoformat(),
            "label": label,
            "model_file": model_path,
            "training_intervals": total_intervals,
            "total_samples_trained": total_samples_all,
            "total_reward_accumulated": round(total_reward_all, 4),
            "avg_reward_per_sample": round(total_reward_all / max(total_samples_all, 1), 6),
            "latest_interval": {
                "loss": recent_stats.get("loss", 0.0),
                "total_rewards": recent_stats.get("total_rewards", 0.0),
                "avg_reward_per_sample": recent_stats.get("avg_reward_per_sample", 0.0),
                "samples_trained": recent_stats.get("samples_trained", 0),
                "reward_types": recent_stats.get("reward_types", {}),
            },
            "lifetime_reward_breakdown": agg_rewards,
            "bot_scores": agent.bot_scores if hasattr(agent, "bot_scores") else {},
        }

        agent.save(model_path)
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return {
            "status": "success",
            "path": model_path,
            "stats_path": stats_path,
            "message": f"Model saved to {model_path}",
            "summary": summary,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
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

    _mark_bot_active(bot_name)

    # Update bot state (use current_state from request, or merge with existing)
    if current_state:
        if bot_name not in bot_states:
            bot_states[bot_name] = {}
        bot_states[bot_name].update(current_state)
        # Also update latest observation if provided
        if "player" in current_state or "entities" in current_state:
            bot_states[bot_name]["latest_observation"] = current_state
            bot_states[bot_name]["latest_observation_time"] = datetime.now().isoformat()
    
    # Log reward events for frontend display
    if bot_name not in bot_reward_events:
        bot_reward_events[bot_name] = []
    
    # Add each event with timestamp
    for event in events:
        event_log = {
            "timestamp": datetime.now().isoformat(),
            "bot_name": bot_name,
            "event": event.copy()  # Copy to avoid reference issues
        }
        bot_reward_events[bot_name].append(event_log)
        
        # Keep only the most recent events
        if len(bot_reward_events[bot_name]) > MAX_REWARD_EVENTS_PER_BOT:
            bot_reward_events[bot_name] = bot_reward_events[bot_name][-MAX_REWARD_EVENTS_PER_BOT:]
    
    # Suppress damage events during episode reset window (/kill creates phantom damage)
    reset_deadline = _bot_reset_until.get(bot_name, 0)
    if time.time() < reset_deadline:
        events = [e for e in events if e.get("type") not in ("damage_taken", "damage_dealt")]
        if not events:
            return {"status": "suppressed", "bot_name": bot_name,
                    "message": "damage events during reset window ignored"}

    # Track damage_dealt events per episode for passive-play penalty
    for ev in events:
        if ev.get("type") == "damage_dealt":
            bot_episode_damage_dealt[bot_name] = bot_episode_damage_dealt.get(bot_name, 0) + 1

    # Only add rewards to training buffer for bots running the RL model.
    bot_version = bot_model_mapping.get(bot_name, _DEFAULT_VERSION)
    agent = fast_rl_agent if fast_rl_agent else ppo_agent
    if agent and events and bot_version == "0.1":
        state_to_use = current_state if current_state else bot_states.get(bot_name, {})
        agent.add_reward(bot_name, state_to_use, events)
    
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
    """
    data = await request.json()
    bot1_name = data.get("bot1")
    bot2_name = data.get("bot2")

    async with _match_lock:
        bot1 = getBotByName(bot1_name)
        bot2 = getBotByName(bot2_name)

        if not bot1 or not bot2:
            return {"status": "error", "message": "One or both bots not found"}

        await fightBots(bot1, bot2)
        return {"status": "success", "arena": getattr(bot1, 'arena', {})}

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
                    tick_rate = api_call_rate / 3.0
        
        bot_info = {
            "name": bot.name,
            "status": bot.status,
            "pair": bot.pair.name if hasattr(bot, 'pair') and bot.pair != "NONE" else None,
            "arena": bot.arena.name if hasattr(bot, 'arena') and bot.arena else None,
            "model_version": bot_model_mapping.get(bot.name, _DEFAULT_VERSION),
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
    # Get training statistics
    agent = fast_rl_agent if fast_rl_agent else ppo_agent
    training_stats = {
        "total_samples": len(agent.observations) if agent else 0,
        "backprop_interval": BACKPROP_INTERVAL,
        "observation_dim": obs_dim if 'obs_dim' in globals() else 0,
        # Remove action_dim - no longer relevant
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
        "rl_samples": sum(len(b) for b in fast_rl_agent._buffers.values()) if fast_rl_agent else (len(ppo_agent.observations) if ppo_agent else 0),
        "rl_rewards": sum(len(b.rewards) for b in fast_rl_agent._buffers.values()) if fast_rl_agent else (len(ppo_agent.rewards) if ppo_agent else 0),
        "last_loss": fast_rl_agent.last_loss if fast_rl_agent else 0.0,
        "last_score": fast_rl_agent.last_score if fast_rl_agent else 0.0
    }
    return stats

@app.get("/training-logs")
async def get_training_logs():
    """
    Returns training logs - statistics recorded every 100 ticks.
    """
    try:
        return {
            "logs": training_logs[-100:] if training_logs else [],  # Return last 100 entries
            "total_logs": len(training_logs) if training_logs else 0,
            "backprop_interval": BACKPROP_INTERVAL
        }
    except Exception as e:
        print(f"Error in get_training_logs: {e}")
        import traceback
        traceback.print_exc()
        return {
            "logs": [],
            "total_logs": 0,
            "backprop_interval": BACKPROP_INTERVAL,
            "error": str(e)
        }

@app.get("/reward-events")
async def get_reward_events(bot_name: str = None):
    """
    Returns reward events for a specific bot or all bots.
    Shows full JSON output of all reward events received.
    """
    if bot_name:
        # Return events for specific bot
        events = bot_reward_events.get(bot_name, [])
        return {
            "status": "success",
            "bot_name": bot_name,
            "events": events,
            "total_events": len(events)
        }
    else:
        # Return events for all bots
        all_events = {}
        for name, events in bot_reward_events.items():
            all_events[name] = events
        return {
            "status": "success",
            "bots": all_events,
            "total_bots": len(all_events)
        }

@app.get("/reward-progression")
async def get_reward_progression():
    """
    Returns reward progression data for graphing.
    Extracts reward data from training logs and computes reward_types from bot_reward_events.
    """
    try:
        from datetime import datetime as dt
        progression = []
        if training_logs:
            # Build a list of interval timestamps for time-based matching
            interval_timestamps = []
            for log in training_logs:
                log_timestamp = log.get("timestamp", "")
                if log_timestamp:
                    try:
                        # Parse timestamp (handle both with and without timezone)
                        ts = log_timestamp.replace('Z', '+00:00') if 'Z' in log_timestamp else log_timestamp
                        interval_timestamps.append(dt.fromisoformat(ts))
                    except (ValueError, TypeError):
                        interval_timestamps.append(None)
                else:
                    interval_timestamps.append(None)
            
            for idx, log in enumerate(training_logs):
                try:
                    training_stats = log.get("training_stats", {})
                    bot_statistics = log.get("bot_statistics", {})
                    log_timestamp = log.get("timestamp", "")
                    
                    # Use saved reward_types from training logs (this is the primary source)
                    # This data was saved at backprop time and won't be deleted like bot_reward_events
                    reward_types = training_stats.get("reward_types", {})
                    
                    # If reward_types is empty or missing, try to compute from bot_reward_events as fallback
                    # (only for recent intervals where events might still be available)
                    if not reward_types:
                        # Determine time window for this interval
                        interval_start = None
                        interval_end = None
                        
                        if idx > 0 and interval_timestamps[idx - 1] is not None:
                            interval_start = interval_timestamps[idx - 1]
                        
                        if interval_timestamps[idx] is not None:
                            interval_end = interval_timestamps[idx]
                        
                        # Aggregate events from all bots for this interval (fallback only)
                        if interval_start is not None and interval_end is not None:
                            # Collect events from all bots in this time window
                            for bot_name, events in bot_reward_events.items():
                                for event_log in events:
                                    event_ts = event_log.get("timestamp", "")
                                    if event_ts:
                                        try:
                                            # Parse event timestamp
                                            event_ts_clean = event_ts.replace('Z', '+00:00') if 'Z' in event_ts else event_ts
                                            event_dt = dt.fromisoformat(event_ts_clean)
                                            
                                            # Check if event is in this interval (between previous and current log timestamp)
                                            if event_dt >= interval_start and event_dt < interval_end:
                                                event = event_log.get("event", {})
                                                event_type = event.get("type", "")
                                                if event_type:
                                                    if event_type not in reward_types:
                                                        reward_types[event_type] = {'count': 0, 'amount': 0.0}
                                                    reward_types[event_type]['count'] += 1
                                                    amount = _estimate_reward_amount(event_type, event)
                                                    reward_types[event_type]['amount'] += amount
                                        except (ValueError, TypeError) as e:
                                            continue
                    
                    progression.append({
                        "timestamp": log_timestamp,
                        "interval": idx + 1,  # Interval number (1, 2, 3, ...)
                        "total_rewards": training_stats.get("total_rewards", 0.0),
                        "avg_reward": training_stats.get("avg_reward_per_sample", 0.0),
                        "loss": training_stats.get("loss", 0.0),
                        "samples_trained": training_stats.get("samples_trained", 0),
                        "bot_rewards": {name: stats.get("score", 0.0) for name, stats in bot_statistics.items()},
                        "reward_types": reward_types  # Breakdown by reward type from bot_reward_events
                    })
                except Exception as e:
                    print(f"Error processing log entry {idx}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
        # Return all progression data (not limited to 50) so frontend can show full history
        return {
            "progression": progression,  # Return all intervals, not just last 50
            "total_intervals": len(progression)
        }
    except Exception as e:
        print(f"Error in get_reward_progression: {e}")
        import traceback
        traceback.print_exc()
        return {
            "progression": [],
            "total_intervals": 0,
            "error": str(e)
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