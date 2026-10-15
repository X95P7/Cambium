"""
reward_engine.py — Reward calculation and estimation.
Per-tick auto-rewards (proximity, pitch, aim_hold) and the dashboard
estimation function that MUST stay in sync with FastRLAgent._compute_reward().
"""

import math
from typing import Dict, List

import state


def normalize_yaw(yaw: float) -> float:
    """Normalize yaw angle to (-180, 180]."""
    return (yaw + 180) % 360 - 180


def estimate_reward_amount(event_type: str, event: dict) -> float:
    """Estimate the reward the model actually computes for this event.

    Used by the dashboard / CSV logger.  Must mirror
    FastRLAgent._compute_reward() exactly — both use static per-event
    rewards pulled from REWARD_WEIGHTS.
    """
    w = state.REWARD_WEIGHTS

    if event_type == 'damage_dealt':
        return w.get("doing_damage", 10.0)          # static per-event
    if event_type == 'damage_taken':
        return w.get("taking_damage", -2.0)          # static per-event
    if event_type == 'good_aim':
        return event.get('amount', 0.1) * w.get("good_aim", 0.1)
    if event_type == 'proximity':
        return event.get('amount', 0) * w.get("proximity", 0.05)
    if event_type == 'pitch_control':
        return event.get('amount', 0) * w.get("pitch_control", 0.05)
    if event_type == 'extreme_pitch_penalty':
        weight = w.get("extreme_pitch_penalty", -0.05)
        return event.get('amount', -0.03) * (weight / -0.5)
    if event_type == 'aim_hold':
        return event.get('amount', 0.1) * w.get("aim_hold", 0.1)
    if event_type == 'won_duel':
        return w.get("won_duel", 90.0)
    if event_type == 'death':
        return w.get("death", -20.0)
    if event_type == 'episode_timeout':
        return w.get("episode_timeout", -10.0)
    if event_type == 'no_damage_penalty':
        return w.get("no_damage_penalty", -10.0)
    return 0.0


def calculate_auto_rewards(bot_name: str, observation: Dict) -> List[Dict]:
    """Per-tick shaping rewards computed from the current observation.

    These complement mod-sent rewards (damage_dealt, damage_taken, good_aim).
    """
    events: List[Dict] = []

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
            dist = (dx**2 + dy**2 + dz**2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                nearest_enemy = entity

    # --- Proximity: encourage closing distance ---
    if nearest_enemy is not None:
        if min_dist <= 3.0:
            prox = 1.0
        elif min_dist < 10.0:
            prox = 1.0 * (1.0 - (min_dist - 3.0) / 7.0)
        else:
            prox = 0.0
        if prox > 0:
            events.append({"type": "proximity", "amount": prox})

    # --- Pitch control: reward level pitch ---
    current_pitch = player.get('pitch', 0)
    pitch_error = abs(current_pitch)
    pitch_reward = max(0.0, 1.0 - pitch_error / 90.0)
    events.append({"type": "pitch_control", "amount": pitch_reward})

    # --- Extreme pitch penalty ---
    if pitch_error > 60.0:
        events.append({"type": "extreme_pitch_penalty", "amount": -0.03})

    # --- Aim hold: bonus when on target AND pitch is level ---
    if nearest_enemy is not None and pitch_error < 30.0:
        dx = nearest_enemy.get('relativeX', 0)
        dy = nearest_enemy.get('relativeY', 0) + (0.9 - 1.62)
        dz = nearest_enemy.get('relativeZ', 0)
        hdist = (dx**2 + dz**2) ** 0.5
        if hdist > 0.1:
            target_yaw = math.atan2(-dx, dz) * 180.0 / math.pi
            target_pitch = -math.atan2(dy, hdist) * 180.0 / math.pi
            player_yaw = normalize_yaw(player.get('yaw', 0))
            yaw_diff = abs(normalize_yaw(player_yaw - normalize_yaw(target_yaw)))
            pitch_diff = abs(current_pitch - target_pitch)
            if max(yaw_diff, pitch_diff) < 20.0:
                events.append({"type": "aim_hold", "amount": 1.0})

    return events
