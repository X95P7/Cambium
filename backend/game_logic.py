"""
game_logic.py — Bot management, arena logic, and episode handling.
fight_bots, give_kit, death handling, episode timeouts, bot activity tracking.
"""

import asyncio
import time
from datetime import datetime
from typing import Optional

import state
import rcon
from BotClass import Bot
from kits.kitBase import Kit
import botController

# Lock protecting all pairing, arena assignment, and episode reset operations.
match_lock = asyncio.Lock()

# Track recent timeout applications to prevent duplicate penalties (BUG 2 fix).
_recent_timeout_applied: dict = {}   # bot_name -> timestamp

RESET_WINDOW_SEC = 3.0  # seconds to suppress buffer writes + damage after reset


def in_reset_window(bot_name: str) -> bool:
    """Returns True if this bot is inside the post-reset suppression window.
    During this window: damage events AND auto-rewards are NOT buffered.
    Actions are still returned normally so the bot can move."""
    deadline = state.bot_reset_until.get(bot_name, 0)
    return time.time() < deadline


# ═══════════════════════ Helpers ════════════════════════════════════

def get_bot_by_name(name: str) -> Optional[Bot]:
    for bot in botController.bots:
        if bot.name == name:
            return bot
    return None


def get_open_arena():
    for arena in state.arenas:
        if arena.status == "open":
            return arena
    return None


async def give_kit(bot: Bot):
    for command in bot.kit.commands:
        await rcon.send(command)


def calculate_tick_rate(bot_name: str) -> float:
    """Calculate TPS for a bot based on recent tick timing.
    API is called once every 3 MC ticks, so TPS = api_rate × (20/3).
    """
    times = state.tick_times.get(bot_name)
    if not times or len(times) < 2:
        return 20.0

    intervals = [times[i] - times[i - 1] for i in range(1, len(times))]
    if not intervals:
        return 20.0

    intervals.sort()
    idx = min(int(len(intervals) * 0.9), len(intervals) - 1)
    avg = intervals[idx]
    if avg > 0:
        return (1.0 / avg) * (20.0 / 3.0)
    return 20.0


# ═══════════════════════ Fighting ═══════════════════════════════════

async def fight_bots(bot1: Bot, bot2: Bot):
    """Pair two bots, claim an arena, teleport, and kit them.
    Caller MUST hold match_lock."""
    # Release any previous arena
    for b in (bot1, bot2):
        if hasattr(b, 'arena') and b.arena:
            b.arena.status = "open"
            b.arena = ""

    arena = get_open_arena()
    if arena is None:
        print(f"[MATCH] No open arenas for {bot1.name} and {bot2.name}")
        return

    arena.status = "closed"
    bot1.updateBot("fighting")
    bot2.updateBot("fighting")
    bot1.setArena(arena)
    bot2.setArena(arena)
    bot1.pairAgainst(bot2)

    now = time.time()
    state.bot_episode_start[bot1.name] = now
    state.bot_episode_start[bot2.name] = now
    state.bot_episode_damage_dealt[bot1.name] = 0
    state.bot_episode_damage_dealt[bot2.name] = 0

    # Set reset window BEFORE RCON calls so no stale ticks slip through
    reset_deadline = time.time() + RESET_WINDOW_SEC
    state.bot_reset_until[bot1.name] = reset_deadline
    state.bot_reset_until[bot2.name] = reset_deadline

    c1 = ' '.join(map(str, arena.spawnCoords[0]))
    c2 = ' '.join(map(str, arena.spawnCoords[1]))
    await rcon.send(f"/tp {bot1.name} {c1}")
    await rcon.send(f"/tp {bot2.name} {c2}")
    await give_kit(bot1)
    await give_kit(bot2)
    await rcon.send(f"/effect {bot1.name} minecraft:instant_health 1 5")
    await rcon.send(f"/effect {bot2.name} minecraft:instant_health 1 5")
    await rcon.send(f"/effect {bot1.name} minecraft:saturation 9999 100")
    await rcon.send(f"/effect {bot2.name} minecraft:saturation 9999 100")


# ═══════════════════════ Timeout Handling ═══════════════════════════

async def _apply_timeout_reward(bot: Bot):
    """Apply episode timeout penalty.  Handles both bots in the pair
    but deduplicates so each bot is penalised at most once per timeout."""
    if not bot or not state.fast_rl_agent:
        return

    now_iso = datetime.now().isoformat()
    now = time.time()
    timeout_amount = state.REWARD_WEIGHTS.get("episode_timeout", -10.0)

    bots_to_process = [bot]
    if hasattr(bot, 'pair') and bot.pair and bot.pair != "NONE":
        bots_to_process.append(bot.pair)

    for b in bots_to_process:
        bname = b.name

        # ---- BUG 2 FIX: skip if already penalised within 5 s ----
        if now - _recent_timeout_applied.get(bname, 0) < 5.0:
            continue
        _recent_timeout_applied[bname] = now

        events = [{"type": "episode_timeout", "amount": timeout_amount}]
        stalling = state.bot_episode_damage_dealt.get(bname, 0) == 0
        if stalling:
            no_dmg = state.REWARD_WEIGHTS.get("no_damage_penalty", -10.0)
            events.append({"type": "no_damage_penalty", "amount": no_dmg})
            state.log_event("REWARD", f"{bname} penalized for stalling (no damage)")

        if state.eval_phase_active:
            # ── EVAL PHASE: accumulate timeout, no buffer writes ──
            try:
                from main import _is_eval_bot
                pair = getattr(bot, 'pair', None)
                pair_name = pair.name if pair and pair != "NONE" else None
                in_eval_match = (_is_eval_bot(bname) or
                                 (pair_name and _is_eval_bot(pair_name)))
                # Only count once: on the ODD (learner) bot to avoid double-counting
                if in_eval_match and not _is_eval_bot(bname):
                    timeout_reward = sum(e["amount"] for e in events)
                    # Both sides get the same timeout reward for this episode
                    state.eval_learner_reward  += timeout_reward
                    state.eval_baseline_reward += timeout_reward
                    state.eval_timeouts += 1
                    state.eval_episodes_remaining = max(
                        0, state.eval_episodes_remaining - 1)
                    if state.eval_episodes_remaining == 0:
                        state.eval_phase_active = False
                        state.log_event("EVAL", "Eval phase complete (timeout) — resuming")
                        try:
                            import training as _tr
                            _tr._write_eval_checkpoint()
                        except Exception as _ee:
                            print(f"[EVAL] Failed to write checkpoint: {_ee}")
            except ImportError:
                pass
        else:
            # ── NORMAL TRAINING: add to buffer ──
            obs = state.bot_states.get(bname, {}).get(
                "current_state",
                state.bot_states.get(bname, {}).get("latest_observation", {}),
            )
            state.fast_rl_agent.add_reward(bname, obs, events)

            if bname not in state.bot_reward_events:
                state.bot_reward_events[bname] = []
            for e in events:
                state.bot_reward_events[bname].append({"timestamp": now_iso, "event": e})

        # Reset per-episode counters (always)
        state.bot_episode_damage_dealt[bname] = 0
        state.bot_tick_counts[bname] = 0
        state.bot_episode_start[bname] = now



async def reset_bots_after_timeout(bot: Bot):
    """Reset both bots after episode timeout — reward, TP, re-kit, re-fight."""
    try:
        if bot is None:
            return

        await _apply_timeout_reward(bot)

        if hasattr(bot, 'arena') and bot.arena:
            bot.arena.status = "open"
        if hasattr(bot, 'pair') and bot.pair and bot.pair != "NONE":
            bot.updateBot("ready")
            bot.pair.updateBot("ready")
            await fight_bots(bot, bot.pair)  # fight_bots sets reset window itself
        else:
            state.bot_reset_until[bot.name] = time.time() + 2.0
            bot.updateBot("ready")
            await give_kit(bot)
    except Exception as e:
        print(f"[RESET] Error resetting bots after timeout: {e}")
        import traceback
        traceback.print_exc()


# ═══════════════════════ Bot Activity Tracking ═════════════════════

def mark_bot_active(bot_name: str):
    """Called on every predict-action / add-reward to track liveness."""
    now = time.time()
    prev = state.bot_last_seen.get(bot_name)
    state.bot_last_seen[bot_name] = now

    if not state.bot_connected.get(bot_name):
        state.bot_connected[bot_name] = True
        if prev is None:
            state.log_event("BOT", f"{bot_name} connected (first seen)")
        else:
            state.log_event("BOT",
                            f"{bot_name} reconnected after {now - prev:.0f}s idle")


def check_bot_idle():
    """Check all known bots for idle timeout."""
    now = time.time()
    for bot_name, last in list(state.bot_last_seen.items()):
        if state.bot_connected.get(bot_name) and \
           (now - last) > state.BOT_IDLE_TIMEOUT_SEC:
            state.bot_connected[bot_name] = False
            state.log_event("BOT",
                            f"{bot_name} went idle (no data for {now - last:.0f}s)")


# ═══════════════════════ Calibration (v0.0) ═════════════════════════

async def calibration_mode_action(bot_name: str):
    """Cycle through W→A→S→D→spin for version 0.0 calibration."""
    processing_start = time.time()
    now = datetime.now()

    if bot_name not in state.bot_calibration_start:
        state.bot_calibration_start[bot_name] = now
    elapsed = (now - state.bot_calibration_start[bot_name]).total_seconds()
    pos = elapsed % state.CALIBRATION_CYCLE_DURATION
    md = state.CALIBRATION_MOVE_DURATION

    base = {"jump": False, "sneak": False, "sprint": False,
            "attack": False, "useItem": False, "hotbar": -1,
            "yaw": 0.0, "pitch": 0.0}

    if pos < md:
        action = {**base, "movement": 0}
    elif pos < md * 2:
        action = {**base, "movement": 6}
    elif pos < md * 3:
        action = {**base, "movement": 4}
    elif pos < md * 4:
        action = {**base, "movement": 2}
    else:
        yaw_delta = 360.0 / (state.CALIBRATION_SPIN_DURATION * 20.0)
        action = {**base, "movement": 0, "yaw": yaw_delta}

    return {"action": action, "processing_time": time.time() - processing_start}
