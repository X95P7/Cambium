"""
training.py — PPO training loop, logging, and model persistence.
trigger_backprop(), _write_training_log(), autosave_model().
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict

import state
import botController
from reward_engine import estimate_reward_amount


# ═══════════════════════ Training Trigger ═══════════════════════════

async def trigger_backprop(bot_name: str = None):
    """Trigger PPO training on all accumulated data.

    Called periodically by the backprop timer (every 30 s).
    In NO_TRAIN mode, logs stats but skips gradient updates.
    """
    try:
        agent = state.fast_rl_agent
        if agent is None:
            return {"status": "skipped", "reason": "no_agent"}

        # ---- Collect buffer stats ----
        all_rewards, all_actions = [], []
        total_samples = 0
        if hasattr(agent, '_buffers'):
            for buf in agent._buffers.values():
                total_samples += len(buf.observations)
                all_rewards.extend(buf.rewards)
                all_actions.extend(buf.actions)

        total_rewards_before = sum(all_rewards) if all_rewards else 0.0

        # ---- Pre-train reward-type aggregation ----
        reward_type_data: Dict[str, Dict] = {}
        if hasattr(agent, '_buffers'):
            for buf in agent._buffers.values():
                for rt_dict in buf.reward_types:
                    for rtype, data in rt_dict.items():
                        if rtype not in reward_type_data:
                            reward_type_data[rtype] = {'count': 0, 'amount': 0.0}
                        if isinstance(data, dict):
                            reward_type_data[rtype]['count'] += data.get('count', 0)
                            reward_type_data[rtype]['amount'] += data.get('amount', 0.0)
                        else:
                            reward_type_data[rtype]['count'] += data

        # ---- Backup: merge from bot_reward_events for synthetic events ----
        last_log_time = None
        if state.training_logs:
            try:
                ts_str = state.training_logs[-1].get("timestamp", "")
                if ts_str:
                    ts_clean = ts_str.replace('Z', '+00:00') if 'Z' in ts_str else ts_str
                    last_log_time = datetime.fromisoformat(ts_clean)
            except (ValueError, TypeError):
                pass

        for _bname, events in state.bot_reward_events.items():
            for ev_log in events:
                event_ts = ev_log.get("timestamp", "")
                if not event_ts:
                    continue
                try:
                    ts_clean = event_ts.replace('Z', '+00:00') if 'Z' in event_ts else event_ts
                    event_dt = datetime.fromisoformat(ts_clean)
                    if last_log_time is not None and event_dt <= last_log_time:
                        continue
                    ev = ev_log.get("event", {})
                    et = ev.get("type", "")
                    if et in ("episode_timeout", "no_damage_penalty"):
                        if state.EXPERIMENT_MODE == "sparse" and et in state.SPARSE_ZERO_REWARD_TYPES:
                            continue
                        if et not in reward_type_data:
                            reward_type_data[et] = {'count': 0, 'amount': 0.0}
                        reward_type_data[et]['count'] += 1
                        reward_type_data[et]['amount'] += estimate_reward_amount(et, ev)
                except (ValueError, TypeError):
                    continue

        # ---- Insufficient data check ----
        NO_TRAIN_THIS = state.NO_TRAIN
        if total_samples < 64:
            state.consecutive_empty_intervals += 1
            # ── DEADLOCK DETECTOR: Restart if bots are dead for 15 mins ──
            if state.consecutive_empty_intervals >= 30: # 15 minutes
                state.log_event("WATCHDOG", "Detected 15m of no bot activity — triggering full restart")
                print("\n[CRITICAL] Bot activity deadlock detected (15m silence). Exiting for restart...")
                time.sleep(1)
                os._exit(1)

            if bot_name != "periodic_sync":
                print(f"Skipping backprop for {bot_name or 'all'}: "
                      f"insufficient data ({total_samples} samples) [Streak: {state.consecutive_empty_intervals}]")
                # Still log a 0 row to keep the CSV contiguous for results.py
                # But we need to define stats etc. first.
                NO_TRAIN_THIS = True
            else:
                print(f"[TIMER] Low samples ({total_samples}), skipping training")
                NO_TRAIN_THIS = True
        else:
            state.consecutive_empty_intervals = 0

        avg_reward_before = total_rewards_before / len(all_rewards) if all_rewards else 0.0

        if reward_type_data:
            print(f"[BACKPROP] Reward type data for interval: {reward_type_data}")

        # ---- Train or skip ----
        if NO_TRAIN_THIS:
            stats = {"loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0,
                     "entropy": 0.0, "return_mean": 0.0, "return_std": 0.0,
                     "score": total_rewards_before, "samples_trained": total_samples,
                     "ppo_updates": 0}
            if hasattr(agent, '_buffers'):
                for buf in agent._buffers.values():
                    buf.clear()
            print(f"[BASELINE] Logged stats for {bot_name or 'all'}, "
                  f"skipped training (NO_TRAIN mode)")
        else:
            stats = agent.train(batch_size=64, epochs=4)
            print(f"Backprop completed for {bot_name or 'all'}: "
                  f"loss={stats.get('loss', 0):.6f}, "
                  f"policy_loss={stats.get('policy_loss', 0):.6f}, "
                  f"entropy={stats.get('entropy', 0):.4f}")

        # ---- Source-of-truth total from reward types ----
        total_rewards_for_interval = sum(
            d['amount'] for d in reward_type_data.values()
        )
        loss = stats.get("loss", 0.0)
        samples_trained = stats.get("samples_trained", 0)

        sparse_component = sum(
            reward_type_data.get(rt, {}).get("amount", 0.0)
            for rt in state.SPARSE_COMPONENT_TYPES
        )

        # ---- Bot statistics snapshot ----
        bot_stats = {}
        for bot in botController.bots:
            bot_stats[bot.name] = {
                "status": bot.status,
                "tick_count": state.bot_tick_counts.get(bot.name, 0),
                "score": agent.bot_scores.get(bot.name, 0.0),
                "model_version": state.bot_model_mapping.get(
                    bot.name, state.DEFAULT_VERSION),
            }

        # ---- Log entry ----
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "tick_interval": state.BACKPROP_INTERVAL,
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
                "sparse_component_reward": sparse_component,
                "reward_types": reward_type_data,
            },
            "bot_statistics": bot_stats,
            "system_stats": {
                "total_bots": len(botController.bots),
                "active_bots": len([b for b in botController.bots
                                    if b.status == "fighting"]),
                "ready_bots": len([b for b in botController.bots
                                   if b.status == "ready"]),
                "open_arenas": len([a for a in state.arenas
                                    if a.status == "open"]),
                "closed_arenas": len([a for a in state.arenas
                                      if a.status == "closed"]),
            },
        }
        state.training_logs.append(log_entry)
        if len(state.training_logs) > state.MAX_LOG_ENTRIES:
            state.training_logs.pop(0)

        # ---- Persistent log files ----
        try:
            _write_training_log(stats, reward_type_data, bot_stats,
                                samples_trained, bot_name or "all",
                                sparse_component_reward=sparse_component)
        except Exception as log_err:
            print(f"[LOG] Failed to write training log: {log_err}")

        # ---- Periodic eval phase trigger ----
        # Every EVAL_TRIGGER_INTERVAL intervals, start a 2-round eval against
        # the frozen reference checkpoint.  The phase ends (and CSV is written)
        # inside the death handler once eval_episodes_remaining hits 0.
        try:
            # ── WATCHDOG: Force-reset stuck eval phases ──
            if state.eval_phase_active and state.eval_start_time > 0:
                elapsed = time.time() - state.eval_start_time
                if elapsed > 600: # 10 minute maximum for 2 rounds
                    state.log_event("EVAL", "Watchdog: Eval phase timed out — force-resuming training",
                                    elapsed=round(elapsed, 1), remaining=state.eval_episodes_remaining)
                    # Write partial results if even one duel finished, otherwise just reset
                    if state.eval_wins + state.eval_losses + state.eval_timeouts > 0:
                        _write_eval_checkpoint()
                    else:
                        state.eval_phase_active = False

            if (state.EVAL_TRIGGER_INTERVAL > 0
                    and state.training_interval_counter % state.EVAL_TRIGGER_INTERVAL == 0
                    and not state.eval_phase_active
                    and getattr(state, 'eval_opponent_net', None) is not None):
                _trigger_eval_phase()
        except Exception as eval_err:
            print(f"[EVAL] Failed to trigger/monitor eval phase: {eval_err}")

        # ---- Auto-save check ----
        if not state.NO_TRAIN:
            state.autosave_counter += 1
            if state.autosave_counter >= state.AUTOSAVE_INTERVAL:
                state.autosave_counter = 0
                autosave_model(
                    f"interval_{state.training_interval_counter}")

        return stats
    except Exception as e:
        print(f"Error in backprop: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ═══════════════════════ Eval Phase Writer ═════════════════════════

EVAL_CHECKPOINT_CSV_PATH = os.path.join(
    state.LOGS_DIR, f"eval_checkpoints_{state.LOG_SESSION_ID}.csv")

def _write_eval_checkpoint():
    """Write one row to eval_checkpoints.csv after a periodic eval phase ends.
    Called from main.py death handler when eval_episodes_remaining reaches 0.
    Resets all eval counters for the next phase."""
    interval  = state.eval_checkpoint_interval
    ts        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wins      = state.eval_wins
    losses    = state.eval_losses
    timeouts  = state.eval_timeouts
    total_ep  = wins + losses + timeouts
    win_rate  = wins / total_ep if total_ep > 0 else 0.0
    learner_r = state.eval_learner_reward
    baseline_r= state.eval_baseline_reward
    reward_delta = learner_r - baseline_r

    row = {
        "triggered_at_interval": interval,
        "timestamp":             ts,
        "eval_wins":             wins,
        "eval_losses":           losses,
        "eval_timeouts":         timeouts,
        "total_episodes":        total_ep,
        "win_rate":              round(win_rate, 4),
        "learner_reward":        round(learner_r, 3),
        "baseline_reward":       round(baseline_r, 3),
        "reward_delta":          round(reward_delta, 3),
        "eval_opponent":         state.EVAL_OPPONENT_PATH,
    }

    state._rotate_log_if_needed(EVAL_CHECKPOINT_CSV_PATH)
    with open(EVAL_CHECKPOINT_CSV_PATH, "a", encoding="utf-8") as f:
        if not state.eval_checkpoint_header_written:
            f.write(",".join(row.keys()) + "\n")
            state.eval_checkpoint_header_written = True
        f.write(",".join(str(v) for v in row.values()) + "\n")

    print(f"[EVAL] ✓ Checkpoint @{interval}: "
          f"wins={wins} losses={losses} timeouts={timeouts} "
          f"win_rate={win_rate:.1%}  "
          f"Δreward={reward_delta:+.1f} "
          f"(learner={learner_r:.1f} vs baseline={baseline_r:.1f})")

    # Reset all eval counters for the next phase
    state.eval_wins              = 0
    state.eval_losses            = 0
    state.eval_timeouts          = 0
    state.eval_learner_reward    = 0.0
    state.eval_baseline_reward   = 0.0


def _trigger_eval_phase():
    """Start a periodic eval phase. Called by training loop every EVAL_TRIGGER_INTERVAL.
    Sets eval_phase_active=True and calculates how many episodes are needed.
    Episode budget = num_active_bots / 2 * EVAL_ROUNDS (one death per pair per round)."""
    if not state.eval_opponent_net:
        return   # no eval opponent loaded — skip

    import botController as _bc
    num_pairs = max(1, len(_bc.bots) // 2)
    state.eval_episodes_remaining = num_pairs * state.EVAL_ROUNDS
    state.eval_start_time      = time.time()
    state.eval_checkpoint_interval = state.training_interval_counter
    state.eval_phase_active    = True
    state.log_event("EVAL",
                    f"Starting eval phase (trigger every {state.EVAL_TRIGGER_INTERVAL} intervals)",
                    episodes_needed=state.eval_episodes_remaining,
                    rounds=state.EVAL_ROUNDS,
                    pairs=num_pairs)


# ═══════════════════════ Persistent Log Writer ═════════════════════

def _write_training_log(stats: Dict, reward_type_data: Dict,
                        bot_stats: Dict, samples: int,
                        trigger_reason: str,
                        sparse_component_reward: float = None):
    """Append one interval's stats to the .log and .csv files."""
    state.training_interval_counter += 1
    state.lifetime_samples += samples
    state.lifetime_reward += stats.get("score", 0.0)
    interval = state.training_interval_counter
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
            reward_type_data.get(rt, {}).get("amount", 0.0)
            for rt in state.SPARSE_COMPONENT_TYPES
        )

    # Per-reward-type breakdown
    rt_lines = []
    for rtype in sorted(reward_type_data.keys()):
        rd = reward_type_data[rtype]
        cnt = rd.get("count", 0)
        amt = rd.get("amount", 0.0)
        rt_lines.append(
            f"    {rtype:25s}  count={cnt:4d}  "
            f"total={amt:+9.4f}  avg={amt / max(cnt, 1):+.4f}")

    # CSV columns
    rt_csv = {}
    for rtype in state.CSV_REWARD_TYPES:
        rd = reward_type_data.get(rtype, {})
        rt_csv[f"r_{rtype}_count"] = rd.get("count", 0)
        rt_csv[f"r_{rtype}_total"] = round(rd.get("amount", 0.0), 4)

    # ---- Human-readable log ----
    block = [
        f"{'=' * 70}",
        f"  Interval {interval}  |  {ts}  |  trigger: {trigger_reason}",
        f"{'=' * 70}",
        f"  Samples:        {samples}",
        f"  PPO updates:    {ppo_updates}",
        f"  Total reward:   {score:+.4f}",
        f"  Sparse component (comparable): {sparse_component_reward:+.4f}",
        f"  Avg reward/step:{avg_reward:+.6f}",
        f"  Return mean:    {ret_mean:+.4f}   std: {ret_std:.4f}",
        f"  Loss:           {loss:.6f}  "
        f"(policy={policy_loss:.6f}  value={value_loss:.6f})",
        f"  Entropy:        {entropy:.4f}",
        f"  Reward weights in use:",
        f"    {state.REWARD_WEIGHTS}",
        f"  Reward breakdown:",
    ]
    block.extend(rt_lines if rt_lines else ["    (none)"])
    for bname, bdata in bot_stats.items():
        block.append(
            f"  Bot {bname}: score={bdata.get('score', 0):.2f}  "
            f"ticks={bdata.get('tick_count', 0)}  "
            f"status={bdata.get('status', '?')}")
    block.append("")

    state._rotate_log_if_needed(state.TRAINING_LOG_PATH)
    with open(state.TRAINING_LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(block) + "\n")

    # ---- CSV ----
    base = {
        "interval": interval, "timestamp": ts,
        "samples": samples, "ppo_updates": ppo_updates,
        "total_reward": round(score, 4),
        "sparse_component_reward": round(sparse_component_reward, 4),
        "avg_reward": round(avg_reward, 6),
        "return_mean": round(ret_mean, 4), "return_std": round(ret_std, 4),
        "loss": round(loss, 6), "policy_loss": round(policy_loss, 6),
        "value_loss": round(value_loss, 6), "entropy": round(entropy, 4),
    }
    row = {**base, **rt_csv}
    with open(state.TRAINING_CSV_PATH, "a", encoding="utf-8") as f:
        if not state.csv_header_written:
            f.write(",".join(row.keys()) + "\n")
            state.csv_header_written = True
        f.write(",".join(str(v) for v in row.values()) + "\n")


# ═══════════════════════ Auto-save ═════════════════════════════════

_AUTOSAVE_PREFIX = "autosave_"

def autosave_model(reason: str = "autosave"):
    """Save the model to disk.  Shutdown saves get unique names;
    periodic saves overwrite a single rolling file."""
    agent = state.fast_rl_agent
    if agent is None:
        print(f"[AUTOSAVE] Skipped ({reason}): no agent")
        return
    try:
        summary = {
            "saved_at": datetime.now().isoformat(),
            "reason": reason,
            "training_intervals": state.training_interval_counter,
            "total_samples_trained": state.lifetime_samples,
            "total_reward_accumulated": round(state.lifetime_reward, 4),
            "avg_reward_per_sample": round(
                state.lifetime_reward / max(state.lifetime_samples, 1), 6),
            "bot_scores": agent.bot_scores if hasattr(agent, "bot_scores") else {},
            "last_loss": getattr(agent, "last_loss", 0.0),
            "last_score": getattr(agent, "last_score", 0.0),
        }

        if reason == "shutdown":
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_path = os.path.join(state.MODELS_DIR,
                                      f"model_{ts}_{reason}.pt")
            stats_path = os.path.join(state.MODELS_DIR,
                                      f"model_{ts}_{reason}_stats.json")
        else:
            model_path = os.path.join(state.MODELS_DIR,
                                      f"{_AUTOSAVE_PREFIX}latest.pt")
            stats_path = os.path.join(state.MODELS_DIR,
                                      f"{_AUTOSAVE_PREFIX}latest_stats.json")

        agent.save(model_path)
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print(f"[AUTOSAVE] Model saved ({reason}): {model_path}  "
              f"intervals={state.training_interval_counter}, "
              f"samples={state.lifetime_samples}, "
              f"reward={state.lifetime_reward:.2f}")

        if (reason == "interval_restart" or
                (reason.startswith("interval_")
                 and state.training_interval_counter >= state.AUTOSAVE_INTERVAL)):
            print(f"[RESTART] Autosave interval ({state.AUTOSAVE_INTERVAL}) reached. "
                  f"Triggering restart to clear memory.")
            os.kill(os.getpid(), 2) # SIGINT

    except Exception as e:
        print(f"[AUTOSAVE] FAILED ({reason}): {e}")
        import traceback
        traceback.print_exc()
