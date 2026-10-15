"""
state.py — Central state for the Cambium backend.
All shared mutable state, configuration constants, and the event logger.
Other modules import from here; this module imports nothing from our codebase.
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Set

# ═══════════════════════════ Configuration ═══════════════════════════

# RCON
RCON_HOST = os.getenv("RCON_HOST", "mc-forge")
RCON_PORT = int(os.getenv("RCON_PORT", 25575))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "minecraft")

# ── Experiment identity ──
EXPERIMENT_MODE = os.getenv("CAMBIUM_EXPERIMENT", "training")
NO_TRAIN = os.getenv("CAMBIUM_NO_TRAIN", "0") == "1" or EXPERIMENT_MODE == "baseline"
RUN_TAG = os.getenv("CAMBIUM_RUN_TAG", "")         # e.g. "full_seed1"
SEED = int(os.getenv("CAMBIUM_SEED", "0"))          # 0 = no seed set

# ── Ablation flags ──
NO_TIMEOUT = os.getenv("CAMBIUM_NO_TIMEOUT", "0") == "1"  # disable episode timeouts
REWARD_MODE = os.getenv("CAMBIUM_REWARD_MODE", "shaped")   # shaped | sparse

# Self-play
SELF_PLAY_ENABLED = os.getenv("CAMBIUM_SELF_PLAY", "1") == "1"
SELF_PLAY_SWAP_INTERVAL = 25

# Episode
MAX_EPISODE_LENGTH_SEC = int(os.getenv("CAMBIUM_EPISODE_TIMEOUT_SEC", "15"))
BACKPROP_INTERVAL = 200       # Tick-count cap (logging only; training is timer-based)
BACKPROP_TIMER_SEC = 30       # Train every 30 seconds
MAX_REWARD_EVENTS_PER_BOT = 100
MAX_LOG_ENTRIES = 5000   # in-memory dashboard log cap (CSV is uncapped)
BOT_IDLE_TIMEOUT_SEC = 30

# Training limits
MAX_INTERVALS = int(os.getenv("CAMBIUM_MAX_INTERVALS", "0"))  # 0 = unlimited
AUTOSAVE_INTERVAL = 250
RESTART_INTERVAL_HOURS = float(os.getenv("CAMBIUM_RESTART_HOURS", "2.0"))

# Eval opponent: frozen model used to measure win-rate vs. a fixed checkpoint.
# Set to an absolute .pt path to enable. Eval bots (even-numbered) will use
# this model instead of the self-play snapshot.
EVAL_OPPONENT_PATH = os.getenv("CAMBIUM_EVAL_OPPONENT", "")

# Periodic eval phase: every EVAL_TRIGGER_INTERVAL training intervals, even-numbered
# bots switch to the frozen checkpoint for exactly EVAL_ROUNDS episodes per pair.
# No gradients are computed during eval episodes.
EVAL_TRIGGER_INTERVAL = int(os.getenv("CAMBIUM_EVAL_INTERVAL", "50"))
EVAL_ROUNDS = 5   # episodes per bot-pair during each eval phase

# Log file size cap (bytes) — rotate if exceeded to prevent disk-full crashes
LOG_MAX_BYTES = 50 * 1024 * 1024  # 50 MB

# ── Directory setup ──
def _get_writable_dir(primary_path: str, fallback_path: str) -> str:
    """Check if a directory is writable; return it if so, else return fallback."""
    try:
        os.makedirs(primary_path, exist_ok=True)
        test_file = os.path.join(primary_path, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return primary_path
    except Exception:
        print(f"[DISK] '{primary_path}' is full or not writable. "
              f"Using fallback: '{fallback_path}'")
        os.makedirs(fallback_path, exist_ok=True)
        return fallback_path

_backend_dir = os.path.dirname(__file__)
_user = os.environ.get('USER', 'default')

# When RUN_TAG is set, namespace everything under runs/<tag>/
if RUN_TAG:
    _run_root = os.path.join(_backend_dir, "runs", RUN_TAG)
    _primary_logs = os.path.join(_run_root, "logs")
    _primary_models = os.path.join(_run_root, "models")
else:
    _primary_logs = os.path.join(_backend_dir, "logs")
    _primary_models = os.getenv("CAMBIUM_MODELS_DIR",
                                 os.path.join(_backend_dir, "models"))

_fallback_logs = f"/tmp/cambium_logs_{_user}"
_fallback_models = f"/tmp/cambium_models_{_user}"
LOGS_DIR = _get_writable_dir(_primary_logs, _fallback_logs)
MODELS_DIR = _get_writable_dir(_primary_models, _fallback_models)

_experiment_tag = f"_{EXPERIMENT_MODE}" if EXPERIMENT_MODE != "training" else ""
LOG_SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + _experiment_tag
EVENT_LOG_PATH = os.path.join(LOGS_DIR, f"events_{LOG_SESSION_ID}.log")
TRAINING_LOG_PATH = os.path.join(LOGS_DIR, f"training_{LOG_SESSION_ID}.log")
TRAINING_CSV_PATH = os.path.join(LOGS_DIR, f"training_{LOG_SESSION_ID}.csv")

# Model default
DEFAULT_VERSION = "0.1"

# Calibration
CALIBRATION_MOVE_DURATION = 2.0
CALIBRATION_SPIN_DURATION = 2.0
CALIBRATION_CYCLE_DURATION = (CALIBRATION_MOVE_DURATION * 4) + CALIBRATION_SPIN_DURATION

# Sparse reward sets (for ablation experiments)
SPARSE_ZERO_REWARD_TYPES = frozenset({
    'good_aim', 'proximity', 'pitch_control', 'aim_hold', 'extreme_pitch_penalty'
})
SPARSE_COMPONENT_TYPES = frozenset({
    'damage_dealt', 'damage_taken', 'won_duel', 'death',
    'episode_timeout', 'no_damage_penalty'
})
CSV_REWARD_TYPES = (
    'aim_hold', 'damage_dealt', 'damage_taken', 'death', 'episode_timeout',
    'extreme_pitch_penalty', 'good_aim', 'no_damage_penalty', 'pitch_control',
    'proximity', 'won_duel'
)

# ═══════════════════════ Reward Weights (single source of truth) ════
REWARD_WEIGHTS: Dict[str, float] = {
    "doing_damage": 10.0,
    "taking_damage": -2.0,
    "won_duel": 90.0,
    "death": -20.0,
    "episode_timeout": -10.0,
    "no_damage_penalty": -10.0,
    "good_aim": 0.1,
    "proximity": 0.05,
    "pitch_control": 0.05,
    "aim_hold": 0.1,
    "extreme_pitch_penalty": -0.05,
}

def load_reward_weights():
    """Load reward weights from JSON. Call before creating the agent.
    To propagate to an existing agent, do: agent.weights.update(data) after calling this.
    """
    try:
        config_path = os.path.join(os.path.dirname(__file__), "reward_weights.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = json.load(f)
            REWARD_WEIGHTS.update(data)
            log_event("REWARDS", f"Loaded weights from {config_path}")
            log_event("REWARDS", f"Current weights: {REWARD_WEIGHTS}")
        else:
            log_event("REWARDS", "No reward_weights.json found, using defaults.")
    except Exception as e:
        log_event("REWARDS", f"ERROR loading: {e}")

# Agent reference — set in main.py after initialization.
# Other modules (game_logic, training) import state and read this.
fast_rl_agent = None

# ═══════════════════════ Arenas ═════════════════════════════════════
from arena import areanaA     # noqa: E402 (deferred so constants above exist first)
arenas = areanaA.Arenas

# ═══════════════════════ Mutable Bot State ══════════════════════════
bot_states:               Dict[str, dict]  = {}
bot_reward_events:        Dict[str, list]  = {}
bot_tick_counts:          Dict[str, int]   = {}
bot_episode_start:        Dict[str, float] = {}
bot_episode_damage_dealt: Dict[str, int]   = {}
bot_last_actions:         Dict[str, dict]  = {}
bot_action_timestamps:    Dict[str, float] = {}
tick_times:               Dict[str, list]  = {}
bot_calibration_start:    Dict[str, object]= {}   # bot -> datetime
bot_model_mapping:        Dict[str, str]   = {}

# Bot activity tracking
bot_last_seen:   Dict[str, float] = {}
bot_connected:   Dict[str, bool]  = {}
bot_reset_until: Dict[str, float] = {}   # suppress phantom damage after /kill
timeout_killed_bots: Set[str]     = set()

# ═══════════════════════ Training State ═════════════════════════════
training_logs:              List[dict] = []
training_interval_counter:  int   = 0
lifetime_samples:           int   = 0
lifetime_reward:            float = 0.0
autosave_counter:           int   = 0
consecutive_empty_intervals: int  = 0   # watchdog for dead bots
csv_header_written:         bool  = False
startup_time:               float = time.time()

# ═══════════════════════ Eval Phase State ══════════════════════════
# Periodic eval: every EVAL_TRIGGER_INTERVAL intervals, even bots use the
# frozen checkpoint for EVAL_ROUNDS episodes. No learning during eval.
eval_phase_active:           bool  = False
eval_episodes_remaining:     int   = 0   # counts down; when 0 → phase ends
eval_start_time:             float = 0.0 # to detect stuck phases
eval_checkpoint_interval:    int   = 0   # which training interval triggered this
eval_learner_reward:         float = 0.0 # cumulative reward for odd (learner) bots
eval_baseline_reward:        float = 0.0 # cumulative reward for even (baseline) bots
eval_wins:                   int   = 0   # learner wins vs frozen model
eval_losses:                 int   = 0   # learner losses vs frozen model
eval_timeouts:               int   = 0   # draws (timeout, no kill)
eval_checkpoint_header_written: bool = False

# Action/observation space configs (served via dashboard API)
action_space_config = {
    "enableMovement": False, "enableJump": False, "enableSneak": False,
    "enableSprint": False, "enableAttack": False, "enableUseItem": False,
    "enableHotbar": False, "enableLook": True,
    "movementBins": 8, "yawBins": 9, "pitchBins": 5,
}
observation_space_config = {
    "includePlayerData": True, "includeEntityData": True,
    "includeBlockData": True, "includeInventoryData": False,
    "maxEntities": 1, "maxBlocks": 8, "maxInventorySlots": 0,
    "includeHealth": True, "includePosition": False,
    "includeRotation": True, "includeVelocity": False, "includeArmor": False,
}

# ═══════════════════════ Config Snapshot ════════════════════════════

def get_config_snapshot() -> dict:
    """Return a dict of all experiment-relevant config for reproducibility."""
    return {
        "run_tag": RUN_TAG,
        "seed": SEED,
        "experiment_mode": EXPERIMENT_MODE,
        "reward_mode": REWARD_MODE,
        "no_train": NO_TRAIN,
        "no_timeout": NO_TIMEOUT,
        "self_play": SELF_PLAY_ENABLED,
        "self_play_swap_interval": SELF_PLAY_SWAP_INTERVAL,
        "max_episode_length_sec": MAX_EPISODE_LENGTH_SEC,
        "backprop_timer_sec": BACKPROP_TIMER_SEC,
        "autosave_interval": AUTOSAVE_INTERVAL,
        "max_intervals": MAX_INTERVALS,
        "restart_interval_hours": RESTART_INTERVAL_HOURS,
        "reward_weights": dict(REWARD_WEIGHTS),
        "obs_dim": 22,
        "hidden_dim": 256,
        "timestamp": datetime.now().isoformat(),
    }

def save_config_snapshot():
    """Write config.json to the run directory for reproducibility."""
    config_path = os.path.join(LOGS_DIR, "config.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(get_config_snapshot(), f, indent=2)
        print(f"[CONFIG] Saved experiment config to {config_path}")
    except Exception as e:
        print(f"[CONFIG] Failed to save config: {e}")

# ═══════════════════════ Event Logger ═══════════════════════════════

def _rotate_log_if_needed(path: str):
    """Rotate a log file if it exceeds LOG_MAX_BYTES."""
    try:
        if os.path.exists(path) and os.path.getsize(path) > LOG_MAX_BYTES:
            rotated = path + ".1"
            if os.path.exists(rotated):
                os.remove(rotated)
            os.rename(path, rotated)
            print(f"[LOG] Rotated {os.path.basename(path)} (exceeded {LOG_MAX_BYTES // (1024*1024)} MB)")
    except Exception:
        pass

def log_event(category: str, message: str, **extra):
    """Append a timestamped event line to the event log and print it."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = f"[{ts}] [{category}] {message}"
    if extra:
        details = "  ".join(f"{k}={v}" for k, v in extra.items())
        parts += f"  ({details})"
    try:
        _rotate_log_if_needed(EVENT_LOG_PATH)
        with open(EVENT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(parts + "\n")
    except Exception:
        pass
    print(parts)
