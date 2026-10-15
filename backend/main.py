"""
main.py — FastAPI application.
Thin endpoint layer.  All logic lives in dedicated modules:
  state.py         — global state, constants, reward weights
  rcon.py          — Minecraft RCON communication
  reward_engine.py — per-tick auto-rewards, dashboard estimation
  game_logic.py    — bot management, arena, fighting, timeouts
  training.py      — PPO training loop, logging, auto-save
"""

import os
import sys
import time
import json
import asyncio
import torch
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import state
import rcon
import reward_engine
import game_logic
import training
import botController
from BotClass import Bot
from kits import classicKit
from kits.kitBase import Kit
from fast_rl_model import FastRLAgent

# ═══════════════════════ App Setup ══════════════════════════════════

app = FastAPI()

frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    try:
        app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    except Exception:
        pass

# ═══════════════════════ Agent Initialization ══════════════════════

# Seed for reproducibility
if state.SEED > 0:
    import torch as _torch
    import numpy as _np
    import random as _random
    _torch.manual_seed(state.SEED)
    _np.random.seed(state.SEED)
    _random.seed(state.SEED)
    if _torch.cuda.is_available():
        _torch.cuda.manual_seed_all(state.SEED)
    print(f"[SEED] Set torch/numpy/random seed to {state.SEED}")

state.log_event("SERVER", "Backend process starting",
                session=state.LOG_SESSION_ID,
                experiment=state.EXPERIMENT_MODE,
                reward_mode=state.REWARD_MODE,
                no_train=state.NO_TRAIN,
                no_timeout=state.NO_TIMEOUT,
                run_tag=state.RUN_TAG or "(none)",
                seed=state.SEED)

state.load_reward_weights()

OBS_DIM = 22  # 3 player + 7 opponent + 8 walls + 4 combat

try:
    rl_device = os.getenv("CAMBIUM_DEVICE", "cpu")
    state.fast_rl_agent = FastRLAgent(
        observation_dim=OBS_DIM, device=rl_device, hidden_dim=256,
        weights=state.REWARD_WEIGHTS,
    )
    print(f"Fast RL agent initialized: obs_dim={OBS_DIM}, device={rl_device}")
    # Propagate the already-loaded JSON weights into the agent
    if hasattr(state.fast_rl_agent, 'weights'):
        state.fast_rl_agent.weights.update(state.REWARD_WEIGHTS)

    # Auto-resume from most recent checkpoint (unless forced fresh)
    force_fresh = (os.getenv("CAMBIUM_FORCE_FRESH", "0") == "1")
    
    if force_fresh:
        state.log_event("SERVER", "Force Fresh Start: skipping model auto-resume")
    elif state.NO_TRAIN:
        state.log_event("SERVER", "Baseline mode: skipping model auto-resume")
    elif os.path.isdir(state.MODELS_DIR):
        import glob as _glob
        _pt_files = sorted(
            _glob.glob(os.path.join(state.MODELS_DIR, "*.pt")),
            key=os.path.getmtime)
        if _pt_files:
            _latest = _pt_files[-1]
            try:
                state.fast_rl_agent.load(_latest)
                state.log_event("SERVER", f"Resumed model from {_latest}")
                
                # Also restore training stats from _stats.json if it exists
                _stats_path = _latest.replace(".pt", "_stats.json")
                if os.path.exists(_stats_path):
                    with open(_stats_path, 'r') as f:
                        _prev = json.load(f)
                    
                    # Log the resumed stats
                    state.log_event("SERVER", "Previous session stats loaded",
                                    intervals=_prev.get('training_intervals', 0),
                                    samples=_prev.get('total_samples_trained', 0),
                                    reward=_prev.get('total_reward_accumulated', 0))
                    
                    state.training_interval_counter = _prev.get('training_intervals', 0)
                    state.lifetime_samples = _prev.get('total_samples_trained', 0)
                    state.lifetime_reward = float(_prev.get('total_reward_accumulated', 0.0))
                    
                    print(f"[STARTUP] Resumed counters: "
                          f"intervals={state.training_interval_counter}, "
                          f"samples={state.lifetime_samples}, "
                          f"reward={state.lifetime_reward:.2f}")
            except Exception as _le:
                state.log_event("SERVER", f"Error resuming model: {_le}")
                print(f"[STARTUP] Could not load {_latest}: {_le} — starting fresh")
        else:
            state.log_event("SERVER", "No saved models found in MODELS_DIR — starting fresh")
            print("[STARTUP] No saved models — starting fresh")
    else:
        state.log_event("SERVER", f"MODELS_DIR not found ({state.MODELS_DIR}) — starting fresh")
        print(f"[STARTUP] MODELS_DIR not found — starting fresh")
except Exception as e:
    state.log_event("SERVER", f"CRITICAL: Failed to initialize RL agent: {e}")
    print(f"ERROR initializing RL agent: {e}")
    # Fallback to CPU if device was GPU
    if os.getenv("CAMBIUM_DEVICE", "cpu") != "cpu":
        try:
            state.fast_rl_agent = FastRLAgent(
                observation_dim=OBS_DIM, device="cpu", hidden_dim=256)
            print("Fast RL agent initialized on CPU (fallback)")
        except Exception:
            state.fast_rl_agent = None
    else:
        state.fast_rl_agent = None

# Save config snapshot for reproducibility
state.save_config_snapshot()

# ── Eval opponent (frozen checkpoint for win-rate measurement) ────────────────
# Even-numbered bots play AGAINST this model; we log wins/losses per interval.
# Set CAMBIUM_EVAL_OPPONENT=/abs/path/to/model.pt to enable.
state.eval_opponent_net = None
_eval_path = state.EVAL_OPPONENT_PATH
if _eval_path and os.path.isfile(_eval_path):
    try:
        from fast_rl_model import ActorCritic as _AC, FlatActorCritic as _FAC
        _rl_device = os.getenv("CAMBIUM_DEVICE", "cpu")
        _ckpt = torch.load(_eval_path, map_location=_rl_device)
        
        # Decide architecture by inspecting checkpoint keys
        _sd = _ckpt
        if isinstance(_ckpt, dict) and "net_state_dict" in _ckpt:
            _sd = _ckpt["net_state_dict"]
        elif isinstance(_ckpt, dict) and "state_dict" in _ckpt:
            _sd = _ckpt["state_dict"]
            
        is_flat = any(k.startswith("action_head") for k in _sd.keys())
        _net_cls = _FAC if is_flat else _AC
        
        _eval_net = _net_cls(OBS_DIM, 256).to(_rl_device)
        # Use strict=False so old models load even if missing new heads (like sprint_head)
        _eval_net.load_state_dict(_sd, strict=False)
        _eval_net.eval()
        state.eval_opponent_net = _eval_net
        state.log_event("EVAL", f"Loaded frozen {'Flat' if is_flat else 'Factored'} eval opponent from {_eval_path}")
    except Exception as _ee:
        print(f"[EVAL] WARNING: Could not load eval opponent '{_eval_path}': {_ee}")
        state.eval_opponent_net = None
elif _eval_path:
    print(f"[EVAL] WARNING: CAMBIUM_EVAL_OPPONENT path not found: '{_eval_path}'")


# Helper used in predict_action: True when this bot is an "eval bot" (plays against frozen model)
def _is_eval_bot(bot_name: str) -> bool:
    """Even-numbered bots are designated eval opponents when eval is active."""
    if not state.eval_opponent_net:
        return False
    digits = "".join(c for c in bot_name if c.isdigit())
    return bool(digits) and int(digits) % 2 == 0


# ═══════════════════════ Startup / Shutdown ═════════════════════════

@app.on_event("startup")
async def _startup():
    async def _idle_loop():
        while True:
            await asyncio.sleep(10)
            game_logic.check_bot_idle()
            # Background timeout check for bots that stop calling the API
            if not state.NO_TIMEOUT:
                now = time.time()
                for bname, start in list(state.bot_episode_start.items()):
                    if (now - start) >= state.MAX_EPISODE_LENGTH_SEC:
                        bot_obj = game_logic.get_bot_by_name(bname)
                        if bot_obj and bot_obj.status == "fighting":
                            async def _bg_reset(b=bot_obj):
                                state.log_event("EPISODE",
                                    f"Background Timeout ({state.MAX_EPISODE_LENGTH_SEC}s)"
                                    f" for {b.name} — Force resetting")
                                if b.status == "fighting":
                                    async with game_logic.match_lock:
                                        await game_logic.reset_bots_after_timeout(b)
                            asyncio.create_task(_bg_reset())

    async def _backprop_timer():
        while True:
            await asyncio.sleep(state.BACKPROP_TIMER_SEC)
            print("[TIMER] Synchronizing global training step...")
            agent = state.fast_rl_agent
            if agent:
                for bname in list(state.bot_tick_counts.keys()):
                    digits = "".join(filter(str.isdigit, bname))
                    if state.SELF_PLAY_ENABLED and digits and int(digits) % 2 == 0:
                        continue
                    agent.add_done(bname, True)
                await training.trigger_backprop("periodic_sync")
                if state.SELF_PLAY_ENABLED:
                    state.training_interval_counter += 0  # counted in _write
                    # Check swap interval (use modulo on the real counter)
                    if (state.training_interval_counter > 0 and
                            state.training_interval_counter
                            % state.SELF_PLAY_SWAP_INTERVAL == 0):
                        agent.snapshot_opponent()
                # Check max-intervals limit
                if (state.MAX_INTERVALS > 0 and
                        state.training_interval_counter >= state.MAX_INTERVALS):
                    print(f"[LIMIT] Reached {state.MAX_INTERVALS} intervals. "
                          f"Saving and shutting down.")
                    training.autosave_model("max_intervals")
                    sys.exit(0)

    async def _watchdog():
        while True:
            await asyncio.sleep(300)
            elapsed = time.time() - state.startup_time
            if elapsed > state.RESTART_INTERVAL_HOURS * 3600:
                print(f"[WATCHDOG] Exiting after "
                      f"{state.RESTART_INTERVAL_HOURS}h to clear memory")
                # Instead of sys.exit(0), send SIGINT to ourselves.
                # This allows uvicorn to catch it, run the @app.on_event("shutdown") 
                # handler (which calls autosave), and close the socket properly.
                os.kill(os.getpid(), 2) # SIGINT

    asyncio.create_task(_idle_loop())
    asyncio.create_task(_backprop_timer())
    asyncio.create_task(_watchdog())


@app.on_event("shutdown")
async def _shutdown():
    try:
        training.autosave_model("shutdown")
    except Exception:
        pass
    try:
        rcon.close()
    except Exception:
        pass


# ═══════════════════════ Endpoints ═════════════════════════════════

@app.get("/")
async def read_root():
    f = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    return FileResponse(f) if os.path.exists(f) else {
        "message": "Frontend not found."}


@app.post("/send-command/")
async def send_command(command: str):
    return await rcon.send(command)


# ─────────────────────── predict-action ────────────────────────────

@app.post("/predict-action-v{version}")
async def predict_action(version: str, request: Request):
    """Main tick handler.  Receives observation, returns action."""
    start_time = time.time()
    try:
        data = await request.json()
    except Exception:
        return _default_action_response()

    observation = data.get("observation", {})
    action_space = data.get("action_space", state.action_space_config)
    bot_name = data.get("bot_name", "unknown")

    game_logic.mark_bot_active(bot_name)

    # Tick counter
    if bot_name not in state.bot_tick_counts:
        state.bot_tick_counts[bot_name] = 0
    state.bot_tick_counts[bot_name] += 1

    # Cache observation
    if bot_name not in state.bot_states:
        state.bot_states[bot_name] = {}
    if "player" in observation:
        p = observation["player"]
        state.bot_states[bot_name]["abs_pos"] = {
            "x": p.get("x", 0), "y": p.get("y", 0), "z": p.get("z", 0),
            "yaw": p.get("yaw", 0), "pitch": p.get("pitch", 0),
            "health": p.get("health", 0), "timestamp": time.time(),
        }
    state.bot_states[bot_name]["latest_observation"] = observation
    state.bot_states[bot_name]["latest_observation_time"] = \
        datetime.now().isoformat()

    # TPS tracking
    now = time.time()
    if bot_name not in state.tick_times:
        state.tick_times[bot_name] = []
    state.tick_times[bot_name].append(now)
    if len(state.tick_times[bot_name]) > 20:
        state.tick_times[bot_name] = state.tick_times[bot_name][-20:]
    tick_rate = game_logic.calculate_tick_rate(bot_name)

    # Cap tick count for logging
    if state.bot_tick_counts[bot_name] >= state.BACKPROP_INTERVAL:
        state.bot_tick_counts[bot_name] = 0

    # ---- Calibration mode (v0.0) ----
    if version == "0.0":
        result = await game_logic.calibration_mode_action(bot_name)
        result["tick_rate"] = tick_rate
        return result

    # ---- RL mode (v0.1) ----
    if version == "0.1":
        agent = state.fast_rl_agent
        if agent is None:
            import random
            action = {"movement": random.randint(0, 7), "jump": False,
                      "sneak": False, "sprint": False, "attack": False,
                      "useItem": False, "hotbar": -1, "yaw": 0.0, "pitch": 0.0}
            return {"action": action, "tick_rate": tick_rate,
                    "processing_time": time.time() - start_time}

        bot_obj = game_logic.get_bot_by_name(bot_name)
        is_fighting = bot_obj and bot_obj.status == "fighting"
        action = None

        try:
            if not is_fighting:
                action = _idle_action()
            else:
                # 1. Episode timer (skipped when NO_TIMEOUT ablation is active)
                if bot_name not in state.bot_episode_start:
                    state.bot_episode_start[bot_name] = now
                elif not state.NO_TIMEOUT and \
                        (now - state.bot_episode_start[bot_name]) >= \
                        state.MAX_EPISODE_LENGTH_SEC:
                    state.bot_episode_start[bot_name] = now
                    state.log_event("EPISODE",
                        f"Timeout ({state.MAX_EPISODE_LENGTH_SEC}s) "
                        f"for {bot_name} while fighting — resetting")
                    async def _locked_reset(b=bot_obj):
                        async with game_logic.match_lock:
                            await game_logic.reset_bots_after_timeout(b)
                    asyncio.create_task(_locked_reset())

                # 2. Partner entity injection / prioritisation
                pair_name = (bot_obj.pair.name
                             if hasattr(bot_obj, 'pair')
                             and bot_obj.pair and bot_obj.pair != "NONE"
                             else None)
                entities = observation.get('entities', [])
                partner = None
                if pair_name:
                    for i, e in enumerate(entities):
                        if e.get('isPlayer') and e.get('name') == pair_name:
                            partner = entities.pop(i)
                            break
                    if not partner:
                        ps = state.bot_states.get(pair_name, {}).get("abs_pos")
                        ss = state.bot_states.get(bot_name, {}).get("abs_pos")
                        if ps and ss:
                            partner = {
                                "name": pair_name, "isPlayer": True,
                                "relativeX": ps["x"] - ss["x"],
                                "relativeY": ps["y"] - ss["y"],
                                "relativeZ": ps["z"] - ss["z"],
                                "health": ps.get("health", 20.0),
                                "facingYaw": ps.get("yaw", 0),
                                "facingPitch": ps.get("pitch", 0),
                            }
                if partner:
                    entities.insert(0, partner)
                observation['entities'] = entities

                # 3. Predict action — routing:
                #
                #   EVAL PHASE (eval_phase_active):
                #     even bot → frozen IT_WOKRS via predict_action_frozen() (no buffer)
                #     odd bot  → live policy via predict_action_eval()        (no buffer)
                #
                #   NORMAL TRAINING:
                #     NO_TRAIN → random_action()
                #     self-play even bot → predict_action_opponent() (self-play snapshot)
                #     all others → predict_action() (live policy, records to buffer)
                if state.eval_phase_active:
                    if _is_eval_bot(bot_name) and state.eval_opponent_net:
                        action = agent.predict_action_frozen(
                            state.eval_opponent_net, observation,
                            action_space, bot_name=bot_name)
                    else:
                        if state.NO_TRAIN:
                            action = agent.random_action(
                                observation, action_space, bot_name=bot_name)
                        else:
                            action = agent.predict_action_eval(
                                observation, action_space, bot_name=bot_name)
                elif state.NO_TRAIN:
                    action = agent.random_action(
                        observation, action_space, bot_name=bot_name)
                elif state.SELF_PLAY_ENABLED:
                    digits = "".join(filter(str.isdigit, bot_name))
                    is_opp = digits and int(digits) % 2 == 0
                    if is_opp:
                        action = agent.predict_action_opponent(
                            observation, action_space, bot_name=bot_name)
                    else:
                        action = agent.predict_action(
                            observation, action_space, bot_name=bot_name)
                else:
                    action = agent.predict_action(
                        observation, action_space, bot_name=bot_name)

                # 4. Auto-rewards
                #    During eval phase: accumulate to eval counters only (no buffer write).
                #    During normal training: record to bot_reward_events and add_reward.
                if not game_logic.in_reset_window(bot_name):
                    auto_events = reward_engine.calculate_auto_rewards(
                        bot_name, observation)
                    if auto_events:
                        if state.eval_phase_active:
                            if agent:
                                amt = agent.compute_reward_amount(auto_events)
                                if _is_eval_bot(bot_name):
                                    state.eval_baseline_reward += amt
                                else:
                                    state.eval_learner_reward += amt
                        else:
                            if bot_name not in state.bot_reward_events:
                                state.bot_reward_events[bot_name] = []
                            ts_now = datetime.now().isoformat()
                            for ev in auto_events:
                                state.bot_reward_events[bot_name].append(
                                    {"timestamp": ts_now, "bot_name": bot_name,
                                     "event": ev.copy()})
                            if len(state.bot_reward_events[bot_name]) > \
                                    state.MAX_REWARD_EVENTS_PER_BOT:
                                state.bot_reward_events[bot_name] = \
                                    state.bot_reward_events[bot_name][
                                        -state.MAX_REWARD_EVENTS_PER_BOT:]
                            agent.add_reward(bot_name, observation, auto_events)

            state.bot_last_actions[bot_name] = action
            state.bot_action_timestamps[bot_name] = time.time()
        except Exception as e:
            print(f"[PREDICT] ERROR for {bot_name}: {e}")
            if bot_name in state.bot_last_actions:
                action = state.bot_last_actions[bot_name]

        if action is None:
            action = _idle_action()
        return {"action": action, "tick_rate": tick_rate,
                "processing_time": time.time() - start_time}

    # Fallback
    return _default_action_response(tick_rate, time.time() - start_time)


def _idle_action():
    return {"movement": 0, "jump": False, "sneak": False, "sprint": False,
            "attack": False, "useItem": False, "hotbar": -1,
            "yaw": 0.0, "pitch": 0.0}

def _default_action_response(tick_rate=20.0, proc_time=0.0):
    return {"action": _idle_action(), "tick_rate": tick_rate,
            "processing_time": proc_time}


# ─────────────────────── bot-setup ─────────────────────────────────

@app.post("/bot-setup/")
async def bot_setup(request: Request):
    data = await request.json()
    name = data.get("name")

    async with game_logic.match_lock:
        existing = game_logic.get_bot_by_name(name)
        if existing is not None:
            print(f"Bot reconnected: {name}")
            state.log_event("BOT", f"{name} reconnected via bot-setup")
            old_pair = existing.pair
            if old_pair and old_pair != "NONE":
                old_pair.pair = "NONE"
                old_pair.updateBot("ready")
                if hasattr(old_pair, 'arena') and old_pair.arena:
                    old_pair.arena.status = "open"
                    old_pair.arena = ""
            existing.updateBot("ready")
            existing.pair = "NONE"
            if hasattr(existing, 'arena') and existing.arena:
                existing.arena.status = "open"
                existing.arena = ""
            state.bot_episode_start[name] = time.time()
            await game_logic.give_kit(existing)
            move = botController.pairBot(existing)
            if move == 1:
                await game_logic.fight_bots(existing, existing.pair)
                return await rcon.send(
                    f"/say Bot {name} reconnected, "
                    f"paired with {existing.pair.name}!")
            return await rcon.send(
                f"/say Bot {name} reconnected. Waiting for pair...")

        print(f"Bot setup for: {name}")
        new_bot = Bot(name, "ready",
                      Kit(classicKit.kitStart, classicKit.kitEnd, name),
                      "agent")
        botController.addBot(new_bot)
        if name not in state.bot_model_mapping:
            state.bot_model_mapping[name] = state.DEFAULT_VERSION
        await game_logic.give_kit(new_bot)
        move = botController.pairBot(new_bot)
        if move == 1:
            await game_logic.fight_bots(new_bot, new_bot.pair)
            return await rcon.send(
                f"/say Bot {name} added and paired with {new_bot.pair.name}!")
        return await rcon.send(
            f"/say Bot {name} added. Waiting for pair...")


# ─────────────────────── death ─────────────────────────────────────

@app.post("/death/")
async def death(request: Request):
    data = await request.json()
    name = data.get("name")

    async with game_logic.match_lock:
        bot = game_logic.get_bot_by_name(name)
        if not bot:
            return {"status": "error", "message": f"Bot {name} not found"}

        if name in state.timeout_killed_bots:
            state.timeout_killed_bots.discard(name)
            return {"status": "ignored",
                    "message": f"Death for {name} from timeout, handled elsewhere"}

        state.log_event("DUEL", f"{name} died",
                        arena=getattr(bot, 'arena', None),
                        pair=getattr(bot, 'pair', None))
        bot.updateBot("dead")
        state.bot_episode_start[name] = time.time()
        pair = (bot.pair if hasattr(bot, 'pair')
                and bot.pair and bot.pair != "NONE" else None)
        if pair:
            state.bot_episode_start[pair.name] = time.time()

        # Death + win rewards — eval-phase aware
        agent = state.fast_rl_agent
        death_amt = state.REWARD_WEIGHTS.get("death", -20.0)
        win_amt   = state.REWARD_WEIGHTS.get("won_duel", 90.0)

        if state.eval_phase_active and pair and agent:
            # ── EVAL PHASE: accumulate stats, count down episodes, no buffer ──
            is_eval_loser = _is_eval_bot(name)   # even bot = baseline; odd = learner

            # Attribute terminal reward to each side
            if is_eval_loser:
                state.eval_baseline_reward += death_amt
                state.eval_learner_reward  += win_amt
                state.eval_wins += 1
            else:
                state.eval_learner_reward  += death_amt
                state.eval_baseline_reward += win_amt
                state.eval_losses += 1

            state.eval_episodes_remaining = max(0, state.eval_episodes_remaining - 1)
            if state.eval_episodes_remaining == 0:
                state.eval_phase_active = False
                state.log_event("EVAL", "Eval phase complete — resuming self-play",
                                wins=state.eval_wins,
                                losses=state.eval_losses,
                                learner_reward=round(state.eval_learner_reward, 2),
                                baseline_reward=round(state.eval_baseline_reward, 2))
                try:
                    import training as _tr
                    _tr._write_eval_checkpoint()
                except Exception as _ee:
                    print(f"[EVAL] Failed to write checkpoint: {_ee}")

        else:
            # ── NORMAL TRAINING: buffer rewards as usual ──
            if name in state.bot_states and agent:
                death_event = {"type": "death", "amount": death_amt}
                state.bot_reward_events.setdefault(name, [])
                state.bot_reward_events[name].append({
                    "timestamp": datetime.now().isoformat(),
                    "bot_name": name, "event": death_event.copy(),
                    "source": "death_endpoint",
                })
                if len(state.bot_reward_events[name]) > state.MAX_REWARD_EVENTS_PER_BOT:
                    state.bot_reward_events[name] = \
                        state.bot_reward_events[name][-state.MAX_REWARD_EVENTS_PER_BOT:]
                agent.add_reward(name, state.bot_states[name], [death_event])

            if pair and agent and pair.name in state.bot_states:
                pname = pair.name
                won_event = {"type": "won_duel", "amount": win_amt}
                state.bot_reward_events.setdefault(pname, [])
                state.bot_reward_events[pname].append({
                    "timestamp": datetime.now().isoformat(),
                    "bot_name": pname, "event": won_event.copy(),
                    "source": "death_endpoint",
                })
                if len(state.bot_reward_events[pname]) > \
                        state.MAX_REWARD_EVENTS_PER_BOT:
                    state.bot_reward_events[pname] = \
                        state.bot_reward_events[pname][
                            -state.MAX_REWARD_EVENTS_PER_BOT:]
                agent.add_reward(pname, state.bot_states[pname], [won_event])

        state.bot_episode_damage_dealt[name] = 0
        if pair:
            state.bot_episode_damage_dealt[pair.name] = 0

        if hasattr(bot, 'arena') and bot.arena:
            bot.arena.status = "open"

        if pair:
            bot.updateBot("ready")
            pair.updateBot("ready")
            await game_logic.fight_bots(bot, pair)
            return await rcon.send(
                f"/say Bot {name} died! Quick reset for continuous combat.")
        else:
            bot.updateBot("ready")
            move = botController.pairBot(bot)
            if move == 1:
                await game_logic.fight_bots(bot, bot.pair)
                return await rcon.send(
                    f"/say Bot {name} died! Paired with {bot.pair.name}.")

    return await rcon.send(f"/say Bot {name} has died!")


# ─────────────────────── add-reward ────────────────────────────────

@app.post("/add-reward/")
async def add_reward(request: Request):
    data = await request.json()
    bot_name = data.get("bot_name")
    events = data.get("events", [])
    current_state = data.get("current_state", {})

    game_logic.mark_bot_active(bot_name)
    bot_obj = game_logic.get_bot_by_name(bot_name)
    if not bot_obj or bot_obj.status != "fighting":
        return {"status": "ignored", "reason": "not_fighting",
                "bot_name": bot_name}

    # BUG 1 FIX: state update was unreachable due to indentation error
    if bot_name not in state.bot_states:
        state.bot_states[bot_name] = {}
    state.bot_states[bot_name].update(current_state)
    if "player" in current_state or "entities" in current_state:
        state.bot_states[bot_name]["latest_observation"] = current_state
        state.bot_states[bot_name]["latest_observation_time"] = \
            datetime.now().isoformat()

    # Log events
    if bot_name not in state.bot_reward_events:
        state.bot_reward_events[bot_name] = []
    for event in events:
        state.bot_reward_events[bot_name].append({
            "timestamp": datetime.now().isoformat(),
            "bot_name": bot_name, "event": event.copy(),
        })
    if len(state.bot_reward_events[bot_name]) > state.MAX_REWARD_EVENTS_PER_BOT:
        state.bot_reward_events[bot_name] = \
            state.bot_reward_events[bot_name][-state.MAX_REWARD_EVENTS_PER_BOT:]

    # Suppress phantom damage during reset window
    deadline = state.bot_reset_until.get(bot_name, 0)
    if time.time() < deadline:
        events = [e for e in events
                  if e.get("type") not in ("damage_taken", "damage_dealt")]
        if not events:
            return {"status": "suppressed", "bot_name": bot_name,
                    "message": "damage events during reset window ignored"}

    # Track damage for passive-play penalty
    for ev in events:
        if ev.get("type") == "damage_dealt":
            state.bot_episode_damage_dealt[bot_name] = \
                state.bot_episode_damage_dealt.get(bot_name, 0) + 1

    # Feed to training buffer — suppressed during eval phase (no learning)
    agent = state.fast_rl_agent
    ver = state.bot_model_mapping.get(bot_name, state.DEFAULT_VERSION)
    if agent and events and ver == "0.1" and not state.eval_phase_active:
        s = current_state if current_state else state.bot_states.get(bot_name, {})
        agent.add_reward(bot_name, s, events)
    elif state.eval_phase_active and agent and events:
        # During eval: accumulate reward to the right side's counter
        amt = agent.compute_reward_amount(events)
        if _is_eval_bot(bot_name):
            state.eval_baseline_reward += amt
        else:
            state.eval_learner_reward += amt

    return {"status": "success", "bot_name": bot_name,
            "events_count": len(events), "events": events}


# ─────────────────────── backprop ──────────────────────────────────

@app.post("/backprop/{version}")
async def backprop(version: str, request: Request):
    data = await request.json()
    agent = state.fast_rl_agent
    if not agent:
        return {"status": "error", "message": "No agent available"}
    try:
        stats = agent.train(
            batch_size=data.get("batch_size", 64),
            epochs=data.get("epochs", 4))
        return {"status": "success", "version": version, **stats}
    except Exception as e:
        return {"status": "error", "message": str(e), "version": version}


# ─────────────────────── config endpoints ──────────────────────────

@app.get("/set-action-space")
async def get_action_space():
    return state.action_space_config

@app.post("/set-action-space")
async def set_action_space(request: Request):
    data = await request.json()
    state.action_space_config.update(data)
    return {"status": "success", "config": state.action_space_config}

@app.get("/set-observation-space")
async def get_observation_space():
    return state.observation_space_config

@app.post("/set-observation-space")
async def set_observation_space(request: Request):
    data = await request.json()
    state.observation_space_config.update(data)
    return {"status": "success", "config": state.observation_space_config}


# ─────────────────────── model management ──────────────────────────

@app.get("/set-model")
async def get_model(request: Request):
    bot_name = request.query_params.get("bot_name")
    if not bot_name:
        return {"status": "error", "message": "bot_name required"}
    return {"status": "success", "bot_name": bot_name,
            "version": state.bot_model_mapping.get(
                bot_name, state.DEFAULT_VERSION)}

@app.post("/set-model")
async def set_model(request: Request):
    data = await request.json()
    if "bot_name" in data and "version" in data:
        state.bot_model_mapping[data["bot_name"]] = data["version"]
        return {"status": "success", "bot_name": data["bot_name"],
                "version": data["version"]}
    if isinstance(data, dict):
        state.bot_model_mapping.update(data)
        return {"status": "success", "mapping": state.bot_model_mapping}
    return {"status": "error", "message": "Invalid request format"}

@app.get("/list-models")
async def list_models():
    import glob as _g
    if not os.path.isdir(state.MODELS_DIR):
        return {"models": []}
    pts = sorted(_g.glob(os.path.join(state.MODELS_DIR, "*.pt")),
                 key=os.path.getmtime, reverse=True)
    result = []
    for pt in pts:
        name = os.path.basename(pt)
        sf = pt.replace(".pt", "_stats.json")
        meta = {}
        if os.path.exists(sf):
            try:
                with open(sf) as f:
                    meta = json.load(f)
            except Exception:
                pass
        result.append({
            "filename": name,
            "size_kb": round(os.path.getsize(pt) / 1024, 1),
            "modified": datetime.fromtimestamp(
                os.path.getmtime(pt)).isoformat(),
            "intervals": meta.get("training_intervals", 0),
            "samples": meta.get("total_samples_trained", 0),
            "reward": meta.get("total_reward_accumulated", 0),
            "reason": meta.get("reason", meta.get("label", "")),
        })
    return {"models": result}

@app.post("/load-model")
async def load_model(request: Request):
    data = await request.json()
    filename = data.get("filename", "")
    if not filename:
        return {"status": "error", "message": "filename required"}
    path = os.path.join(state.MODELS_DIR, filename)
    if not os.path.exists(path):
        return {"status": "error", "message": f"Not found: {filename}"}
    agent = state.fast_rl_agent
    if not agent:
        return {"status": "error", "message": "No agent initialized"}
    try:
        agent.load(path)
        state.training_logs.clear()
        state.log_event("SERVER", f"Model loaded: {filename}")
        sf = path.replace(".pt", "_stats.json")
        meta = {}
        if os.path.exists(sf):
            with open(sf) as f:
                meta = json.load(f)
        return {"status": "success", "message": f"Loaded {filename}",
                "intervals": meta.get("training_intervals", 0),
                "samples": meta.get("total_samples_trained", 0),
                "reward": meta.get("total_reward_accumulated", 0)}
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e)}

@app.post("/reset-model")
async def reset_model():
    agent = state.fast_rl_agent
    if not agent:
        return {"status": "error", "message": "No agent initialized"}
    try:
        agent.__init__(observation_dim=agent.observation_dim,
                       device=str(agent.device),
                       hidden_dim=agent.net.shared[0].out_features)
        state.training_logs.clear()
        state.log_event("SERVER", "Model reset to fresh state")
        return {"status": "success", "message": "Model reset"}
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e)}

@app.post("/save-model")
async def save_model(request: Request):
    data = await request.json()
    label = data.get("label", "")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = label.replace(" ", "_")[:40] if label else ""
    fname = f"model_{ts}{'_' + safe if safe else ''}"
    m_path = os.path.join(state.MODELS_DIR, f"{fname}.pt")
    s_path = os.path.join(state.MODELS_DIR, f"{fname}_stats.json")
    try:
        agent = state.fast_rl_agent
        total_intervals = len(state.training_logs)
        recent = state.training_logs[-1] if state.training_logs else {}
        rs = recent.get("training_stats", {})
        agg = {}
        total_r, total_s = 0.0, 0
        for log in state.training_logs:
            ts2 = log.get("training_stats", {})
            total_r += ts2.get("total_rewards", 0.0)
            total_s += ts2.get("samples_trained", 0)
            for rt, rd in ts2.get("reward_types", {}).items():
                if rt not in agg:
                    agg[rt] = {"count": 0, "amount": 0.0}
                if isinstance(rd, dict):
                    agg[rt]["count"] += rd.get("count", 0)
                    agg[rt]["amount"] += rd.get("amount", 0.0)
        summary = {
            "saved_at": datetime.now().isoformat(), "label": label,
            "model_file": m_path,
            "training_intervals": total_intervals,
            "total_samples_trained": total_s,
            "total_reward_accumulated": round(total_r, 4),
            "avg_reward_per_sample": round(total_r / max(total_s, 1), 6),
            "latest_interval": {
                "loss": rs.get("loss", 0.0),
                "total_rewards": rs.get("total_rewards", 0.0),
                "samples_trained": rs.get("samples_trained", 0),
                "reward_types": rs.get("reward_types", {}),
            },
            "lifetime_reward_breakdown": agg,
            "bot_scores": agent.bot_scores if hasattr(agent, "bot_scores") else {},
        }
        agent.save(m_path)
        with open(s_path, "w") as f:
            json.dump(summary, f, indent=2)
        return {"status": "success", "path": m_path, "summary": summary}
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ─────────────────────── start-duel ────────────────────────────────

@app.post("/start-duel/")
async def start_duel(request: Request):
    data = await request.json()
    async with game_logic.match_lock:
        b1 = game_logic.get_bot_by_name(data.get("bot1"))
        b2 = game_logic.get_bot_by_name(data.get("bot2"))
        if not b1 or not b2:
            return {"status": "error", "message": "Bot(s) not found"}
        await game_logic.fight_bots(b1, b2)
        return {"status": "success", "arena": getattr(b1, 'arena', {})}


# ─────────────────────── dashboard / stats ─────────────────────────

@app.get("/game-state")
async def get_game_state():
    agent = state.fast_rl_agent
    bots_data = []
    for bot in botController.bots:
        tick_rate = game_logic.calculate_tick_rate(bot.name)
        info = {
            "name": bot.name, "status": bot.status,
            "pair": (bot.pair.name if hasattr(bot, 'pair')
                     and bot.pair != "NONE" else None),
            "arena": (bot.arena.name if hasattr(bot, 'arena')
                      and bot.arena else None),
            "model_version": state.bot_model_mapping.get(
                bot.name, state.DEFAULT_VERSION),
            "tick_count": state.bot_tick_counts.get(bot.name, 0),
            "tick_rate": tick_rate,
        }
        if agent:
            m = agent.get_bot_metrics(bot.name)
            info.update({"score": m["score"], "loss": m["loss"],
                         "total_rewards": m["total_rewards"]})
        else:
            info.update({"score": 0.0, "loss": 0.0, "total_rewards": 0})
        bots_data.append(info)

    arenas_data = [{"name": a.name, "status": a.status,
                    "spawn_coords": a.spawnCoords}
                   for a in state.arenas]

    ts = {
        "total_samples": (sum(len(b) for b in agent._buffers.values())
                          if agent and hasattr(agent, '_buffers') else 0),
        "backprop_interval": state.BACKPROP_INTERVAL,
        "observation_dim": OBS_DIM,
        "last_loss": agent.last_loss if agent else 0.0,
        "last_score": agent.last_score if agent else 0.0,
    }
    return {"bots": bots_data, "arenas": arenas_data, "training": ts,
            "action_space": state.action_space_config,
            "observation_space": state.observation_space_config,
            "model_mappings": state.bot_model_mapping}


@app.get("/bot/{bot_name}/observation")
async def get_bot_observation(bot_name: str):
    if bot_name not in state.bot_states or \
       "latest_observation" not in state.bot_states[bot_name]:
        return {"status": "error",
                "message": f"No observation for {bot_name}"}

    raw = state.bot_states[bot_name]["latest_observation"]
    resp = {"bot_name": bot_name,
            "timestamp": state.bot_states[bot_name].get(
                "latest_observation_time", ""),
            "raw_json": raw}
    agent = state.fast_rl_agent
    if agent:
        try:
            vec = agent._observation_to_vector_fast(
                raw, state.action_space_config, bot_name=bot_name)
            labels = [
                "player_health", "player_yaw", "player_pitch",
                "opp_isAlive", "opp_health", "opp_relX_10m",
                "opp_relY_10m", "opp_relZ_10m", "opp_yaw", "opp_pitch",
                "wall_ray_N", "wall_ray_NE", "wall_ray_E", "wall_ray_SE",
                "wall_ray_S", "wall_ray_SW", "wall_ray_W", "wall_ray_NW",
                "opp_dist_10m", "aim_dot", "yaw_error", "pitch_error",
            ]
            resp["nn_target_vector_22"] = {
                labels[i] if i < len(labels) else f"dim_{i}":
                    round(float(vec[i]), 4)
                for i in range(len(vec))
            }
        except Exception as e:
            resp["nn_error"] = str(e)
    return resp


@app.get("/stats")
async def get_stats():
    agent = state.fast_rl_agent
    return {
        "bot_tick_counts": state.bot_tick_counts,
        "total_bots": len(botController.bots),
        "active_bots": len([b for b in botController.bots
                            if b.status == "fighting"]),
        "ready_bots": len([b for b in botController.bots
                           if b.status == "ready"]),
        "dead_bots": len([b for b in botController.bots
                          if b.status == "dead"]),
        "open_arenas": len([a for a in state.arenas
                            if a.status == "open"]),
        "closed_arenas": len([a for a in state.arenas
                              if a.status == "closed"]),
        "rl_samples": (sum(len(b) for b in agent._buffers.values())
                       if agent else 0),
        "rl_rewards": (sum(len(b.rewards)
                           for b in agent._buffers.values())
                       if agent else 0),
        "last_loss": agent.last_loss if agent else 0.0,
        "last_score": agent.last_score if agent else 0.0,
    }


@app.get("/training-logs")
async def get_training_logs():
    return {
        "logs": state.training_logs[-100:],
        "total_logs": len(state.training_logs),
        "backprop_interval": state.BACKPROP_INTERVAL,
    }


@app.get("/reward-events")
async def get_reward_events(bot_name: str = None):
    if bot_name:
        evts = state.bot_reward_events.get(bot_name, [])
        return {"status": "success", "bot_name": bot_name,
                "events": evts, "total_events": len(evts)}
    return {"status": "success", "bots": dict(state.bot_reward_events),
            "total_bots": len(state.bot_reward_events)}


@app.get("/reward-progression")
async def get_reward_progression():
    try:
        progression = []
        if not state.training_logs:
            return {"progression": [], "total_intervals": 0}

        ts_list = []
        for log in state.training_logs:
            ts_str = log.get("timestamp", "")
            try:
                ts_list.append(datetime.fromisoformat(
                    ts_str.replace('Z', '+00:00') if 'Z' in ts_str
                    else ts_str) if ts_str else None)
            except (ValueError, TypeError):
                ts_list.append(None)

        for idx, log in enumerate(state.training_logs):
            ts2 = log.get("training_stats", {})
            rt = ts2.get("reward_types", {})

            # Fallback: compute from bot_reward_events if empty
            if not rt:
                t0 = ts_list[idx - 1] if idx > 0 else None
                t1 = ts_list[idx]
                if t0 and t1:
                    for _bn, evts in state.bot_reward_events.items():
                        for el in evts:
                            ets = el.get("timestamp", "")
                            if not ets:
                                continue
                            try:
                                edt = datetime.fromisoformat(
                                    ets.replace('Z', '+00:00')
                                    if 'Z' in ets else ets)
                                if t0 <= edt < t1:
                                    ev = el.get("event", {})
                                    et = ev.get("type", "")
                                    if et:
                                        if et not in rt:
                                            rt[et] = {'count': 0, 'amount': 0.0}
                                        rt[et]['count'] += 1
                                        rt[et]['amount'] += \
                                            reward_engine.estimate_reward_amount(
                                                et, ev)
                            except (ValueError, TypeError):
                                continue

            bs = log.get("bot_statistics", {})
            progression.append({
                "timestamp": log.get("timestamp", ""),
                "interval": idx + 1,
                "total_rewards": ts2.get("total_rewards", 0.0),
                "avg_reward": ts2.get("avg_reward_per_sample", 0.0),
                "loss": ts2.get("loss", 0.0),
                "samples_trained": ts2.get("samples_trained", 0),
                "bot_rewards": {n: s.get("score", 0.0)
                                for n, s in bs.items()},
                "reward_types": rt,
            })

        return {"progression": progression,
                "total_intervals": len(progression)}
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"progression": [], "total_intervals": 0, "error": str(e)}