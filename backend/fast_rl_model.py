"""
Fast RL Model - PPO with Multi-Discrete Action Space
Actor-critic architecture with separate heads for each action component.
Uses clipped surrogate objective, GAE advantages, and minibatch updates.
"""
import os
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Tuple

YAW_BINS = [-20.0, -10.0, -5.0, -2.0, 0.0, 2.0, 5.0, 10.0, 20.0]
PITCH_BINS = [-5.0, -2.0, 0.0, 2.0, 5.0]


class ActorCritic(nn.Module):
    """
    Actor-critic network with shared feature extractor.
    Actor: multi-discrete policy heads (movement, jump, attack, yaw, pitch)
    Critic: single scalar value estimate V(s)
    """
    def __init__(self, observation_dim: int, hidden_dim: int = 256):
        super(ActorCritic, self).__init__()

        self.shared = nn.Sequential(
            nn.Linear(observation_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh()
        )

        # Actor heads
        self.movement_head = nn.Linear(hidden_dim, 8)
        self.jump_head = nn.Linear(hidden_dim, 2)
        self.attack_head = nn.Linear(hidden_dim, 2)
        self.yaw_head = nn.Linear(hidden_dim, len(YAW_BINS))
        self.pitch_head = nn.Linear(hidden_dim, len(PITCH_BINS))

        # Critic head
        self.value_head = nn.Linear(hidden_dim, 1)

        # Bias pitch toward center so it doesn't drift early on
        with torch.no_grad():
            center = len(PITCH_BINS) // 2
            self.pitch_head.bias.zero_()
            self.pitch_head.bias[center] = 2.0

        # Orthogonal init for better PPO convergence
        for module in [self.movement_head, self.jump_head, self.attack_head,
                       self.yaw_head, self.pitch_head]:
            nn.init.orthogonal_(module.weight, gain=0.01)
            nn.init.zeros_(module.bias)
        nn.init.orthogonal_(self.value_head.weight, gain=1.0)
        nn.init.zeros_(self.value_head.bias)
        # Re-apply pitch center bias after orthogonal init
        with torch.no_grad():
            self.pitch_head.bias[center] = 2.0
            self.jump_head.bias[0] = 2.0   # bias toward "don't jump"

    def forward(self, obs: torch.Tensor) -> Tuple[Dict[str, torch.Tensor], torch.Tensor]:
        """Returns (logits_dict, value)"""
        features = self.shared(obs)
        logits = {
            'movement': self.movement_head(features),
            'jump': self.jump_head(features),
            'attack': self.attack_head(features),
            'yaw': self.yaw_head(features),
            'pitch': self.pitch_head(features),
        }
        value = self.value_head(features).squeeze(-1)
        return logits, value

    def get_action_and_value(self, obs_np: np.ndarray, deterministic: bool = False):
        """Sample action, return (actions_dict, log_prob, value) — all scalars."""
        with torch.no_grad():
            device = next(self.parameters()).device
            obs_t = torch.FloatTensor(obs_np).unsqueeze(0).to(device)
            logits, value = self.forward(obs_t)

            actions = {}
            log_probs = []
            for key, lg in logits.items():
                dist = torch.distributions.Categorical(logits=lg)
                a = torch.argmax(lg, dim=-1).item() if deterministic else dist.sample().item()
                actions[key] = a
                log_probs.append(dist.log_prob(torch.tensor(a, device=device)))

            total_lp = sum(log_probs).item()
            return actions, total_lp, value.item()

    def evaluate_actions(self, obs_t: torch.Tensor,
                         act_movement: torch.Tensor, act_jump: torch.Tensor,
                         act_attack: torch.Tensor, act_yaw: torch.Tensor,
                         act_pitch: torch.Tensor):
        """
        Given a batch of observations and actions, return
        (log_probs, values, entropy)  — all batched tensors.
        """
        logits, values = self.forward(obs_t)

        dists = {k: torch.distributions.Categorical(logits=v) for k, v in logits.items()}

        lp = (dists['movement'].log_prob(act_movement)
              + dists['jump'].log_prob(act_jump)
              + dists['attack'].log_prob(act_attack)
              + dists['yaw'].log_prob(act_yaw)
              + dists['pitch'].log_prob(act_pitch))

        ent = sum(d.entropy() for d in dists.values())

        return lp, values, ent


class _BotBuffer:
    """Per-bot rollout buffer — keeps one bot's trajectory separate."""
    __slots__ = ('observations', 'actions', 'log_probs', 'values', 'rewards',
                 'reward_types', 'dones')

    def __init__(self):
        self.observations: List[np.ndarray] = []
        self.actions: List[Dict[str, int]] = []
        self.log_probs: List[float] = []
        self.values: List[float] = []
        self.rewards: List[float] = []
        self.reward_types: List[Dict] = []
        self.dones: List[bool] = []

    def __len__(self):
        return len(self.observations)

    def clear(self):
        for attr in self.__slots__:
            getattr(self, attr).clear()


class FastRLAgent:
    """PPO agent with multi-discrete actions, GAE, and clipped surrogate."""

    # PPO hyperparameters
    GAMMA = 0.99
    GAE_LAMBDA = 0.95
    CLIP_EPS = 0.2
    VF_COEF = 0.5
    ENT_COEF = 0.02
    MAX_GRAD_NORM = 0.5
    LR = 3e-4
    PPO_EPOCHS = 4
    MINIBATCH_SIZE = 64

    # Reward types that are zeroed in sparse mode (ablation: no shaping)
    SPARSE_ZERO_TYPES = frozenset({'good_aim', 'proximity', 'pitch_control', 'aim_hold', 'extreme_pitch_penalty'})

    def __init__(self, observation_dim: int, device: str = 'cpu', hidden_dim: int = 256):
        self.observation_dim = observation_dim
        self.device = device
        self.net = ActorCritic(observation_dim, hidden_dim).to(device)
        self.optimizer = torch.optim.Adam(self.net.parameters(), lr=self.LR, eps=1e-5)
        self.reward_mode = os.getenv("CAMBIUM_REWARD_MODE", "shaped")  # "sparse" = no shaping (ablation 2.3)

        # Per-bot rollout buffers (keyed by bot_name)
        self._buffers: Dict[str, _BotBuffer] = {}

        # Legacy flat accessors used by main.py for len checks / reward_types
        self.observations: List[np.ndarray] = []
        self.reward_types: List[Dict] = []

        # Metrics (same interface as before)
        self.bot_scores: Dict[str, float] = {}
        self.bot_losses: Dict[str, float] = {}
        self.last_loss = 0.0
        self.last_score = 0.0

        self.obs_vector_size = 194

        # Keep reference to policy for compatibility with main.py obs caching
        self.policy = self.net

    def _buf(self, bot_name: str) -> '_BotBuffer':
        if bot_name not in self._buffers:
            self._buffers[bot_name] = _BotBuffer()
        return self._buffers[bot_name]

    # ------------------------------------------------------------------
    # Observation vectorisation (unchanged)
    # ------------------------------------------------------------------
    def _observation_to_vector_fast(self, observation: Dict, action_space: Dict) -> np.ndarray:
        vector = np.zeros(self.obs_vector_size, dtype=np.float32)
        idx = 0

        if 'player' in observation:
            p = observation['player']
            vector[idx]   = p.get('health', 0) / 20.0
            vector[idx+1] = p.get('x', 0) / 100.0
            vector[idx+2] = p.get('y', 0) / 100.0
            vector[idx+3] = p.get('z', 0) / 100.0
            vector[idx+4] = p.get('yaw', 0) / 180.0
            vector[idx+5] = p.get('pitch', 0) / 90.0
            vector[idx+6] = p.get('armor', 0) / 20.0
            idx += 7

        if 'entities' in observation:
            for i, e in enumerate(observation['entities'][:10]):
                bi = idx + i * 6
                vector[bi]   = 1.0 if e.get('isPlayer', False) else 0.0
                vector[bi+1] = 1.0 if e.get('isProjectile', False) else 0.0
                vector[bi+2] = e.get('health', 0) / 20.0
                vector[bi+3] = e.get('relativeX', 0) / 10.0
                vector[bi+4] = e.get('relativeY', 0) / 10.0
                vector[bi+5] = e.get('relativeZ', 0) / 10.0
        idx += 60

        if 'blocks' in observation:
            for i, b in enumerate(observation['blocks'][:20]):
                bi = idx + i * 5
                vector[bi]   = b.get('x', 0) / 20.0
                vector[bi+1] = b.get('y', 0) / 20.0
                vector[bi+2] = b.get('z', 0) / 20.0
                vector[bi+3] = b.get('distance', 0) / 20.0
                vector[bi+4] = 1.0 if b.get('solid', False) else 0.0
        idx += 100

        if 'inventory' in observation:
            for i, inv in enumerate(observation['inventory'][:9]):
                bi = idx + i * 3
                vector[bi]   = inv.get('count', 0) / 64.0
                vector[bi+1] = 1.0 if inv.get('isWeapon', False) else 0.0
                vector[bi+2] = inv.get('weaponDamage', 0) / 10.0
        idx += 27

        return vector

    def _actions_dict_to_minecraft(self, ad: Dict[str, int], action_space: Dict) -> Dict:
        return {
            "movement": int(ad['movement']),
            "jump": False,  # disabled: no reward signal for jump, and airborne = worse aim
            "sneak": False,
            "sprint": False,
            "attack": bool(ad['attack']),
            "useItem": False,
            "hotbar": -1,
            "yaw": float(YAW_BINS[ad['yaw']]),
            "pitch": float(PITCH_BINS[ad['pitch']]),
        }

    # ------------------------------------------------------------------
    # predict_action  (same signature as before, now bot-name aware)
    # ------------------------------------------------------------------
    def predict_action(self, observation: Dict, action_space: Dict,
                       cached_vector: np.ndarray = None,
                       bot_name: str = "default") -> Dict:
        obs_vec = cached_vector if cached_vector is not None else \
            self._observation_to_vector_fast(observation, action_space)

        actions_dict, lp, val = self.net.get_action_and_value(obs_vec)
        mc_action = self._actions_dict_to_minecraft(actions_dict, action_space)

        buf = self._buf(bot_name)
        buf.observations.append(obs_vec)
        buf.actions.append(actions_dict)
        buf.log_probs.append(lp)
        buf.values.append(val)
        buf.rewards.append(0.0)
        buf.reward_types.append({})
        buf.dones.append(False)

        self.observations = buf.observations
        self.reward_types = buf.reward_types

        return mc_action

    def random_action(self, observation: Dict, action_space: Dict,
                      bot_name: str = "default") -> Dict:
        """Sample a uniformly random action; record to buffer like predict_action."""
        import random as _rng
        obs_vec = self._observation_to_vector_fast(observation, action_space)

        actions_dict = {
            'movement': _rng.randint(0, 8),
            'jump': _rng.randint(0, 1),
            'attack': _rng.randint(0, 1),
            'yaw': _rng.randint(0, len(YAW_BINS) - 1),
            'pitch': _rng.randint(0, len(PITCH_BINS) - 1),
        }
        mc_action = self._actions_dict_to_minecraft(actions_dict, action_space)

        buf = self._buf(bot_name)
        buf.observations.append(obs_vec)
        buf.actions.append(actions_dict)
        buf.log_probs.append(torch.tensor(0.0))
        buf.values.append(torch.tensor(0.0))
        buf.rewards.append(0.0)
        buf.reward_types.append({})
        buf.dones.append(False)

        self.observations = buf.observations
        self.reward_types = buf.reward_types

        return mc_action

    # ------------------------------------------------------------------
    # add_reward / add_done  (per-bot buffer aware)
    # ------------------------------------------------------------------
    def _compute_reward(self, ev: Dict) -> Tuple[str, float]:
        """Convert event to (type, reward_amount).

        Reward budget for a typical 15s episode (~105 ticks per bot):
            GOAL REWARDS  (sparse, strongly dominate learning signal)
              won_duel        +15.0   (the whole point)
              damage_dealt    dmg% × 10.0  (~2 hits → ~6.0 total)
              death           -2.0    (mild — dying is bad but shouldn't discourage fighting)
              episode_timeout -1.0    (couldn't finish = punishment, encourages aggression)
              damage_taken    -amt × 0.1   (~2 hits → ~-0.6 total, nearly free)
              no_damage_penalty -0.5  (no hits landed = passive play punished)
            SHAPING REWARDS  (frequent, kept small so they guide not override)
              good_aim        mod_score × 0.03  (~40 events → ~0.6 total)
              aim_hold        from event amt × 0.6  (~30 ticks → ~0.9)
              proximity       from event amt × 0.5  (~105 × 0.005 → ~0.5)
              pitch_control   from event amt × 0.5  (~105 × 0.01 → ~1.0)
              extreme_pitch   -0.03              (rare, only >60°)
        """
        et = ev.get('type', '')
        amt = 0.0
        if et == 'damage_dealt':
            amt = ev.get('damage_percentage', 0) * 10.0 if 'damage_percentage' in ev else ev.get('amount', 0) * 1.0
        elif et == 'damage_taken':
            amt = -ev.get('amount', 0) * 0.1
        elif et == 'good_aim':
            amt = ev.get('amount', 0.1) * 0.03
        elif et == 'proximity':
            amt = ev.get('amount', 0) * 0.5
        elif et == 'pitch_control':
            amt = ev.get('amount', 0) * 0.5
        elif et == 'extreme_pitch_penalty':
            amt = ev.get('amount', -0.03)
        elif et == 'aim_hold':
            amt = ev.get('amount', 0.05) * 0.6
        elif et == 'won_duel':
            amt = 15.0
        elif et == 'death':
            amt = -2.0
        elif et == 'episode_timeout':
            amt = -1.0
        elif et == 'no_damage_penalty':
            amt = -0.5
        elif et == 'survival':
            amt = 0.0
        elif et == 'yaw_exploration':
            amt = 0.0

        # Ablation: sparse mode zeros shaping rewards and omit from logs (return None so add_reward doesn't record)
        if getattr(self, 'reward_mode', 'shaped') == 'sparse' and et in self.SPARSE_ZERO_TYPES:
            return (None, 0.0)
        return et, amt

    def add_reward(self, bot_name: str, current_state: Dict, events: List[Dict]):
        buf = self._buf(bot_name)
        total_reward = 0.0
        rt_data: Dict[str, Dict] = {}

        for ev in events:
            et, amt = self._compute_reward(ev)
            if et:
                if et not in rt_data:
                    rt_data[et] = {'count': 0, 'amount': 0.0}
                rt_data[et]['count'] += 1
                rt_data[et]['amount'] += amt
                total_reward += amt

        if len(buf.observations) == 0:
            return

        while len(buf.rewards) < len(buf.observations):
            buf.rewards.append(0.0)
            buf.reward_types.append({})

        if buf.rewards:
            buf.rewards[-1] += total_reward
            for rtype, data in rt_data.items():
                if rtype not in buf.reward_types[-1]:
                    buf.reward_types[-1][rtype] = {'count': 0, 'amount': 0.0}
                buf.reward_types[-1][rtype]['count'] += data['count']
                buf.reward_types[-1][rtype]['amount'] += data['amount']

        self.bot_scores[bot_name] = self.bot_scores.get(bot_name, 0.0) + total_reward
        # Update flat accessor
        self.reward_types = buf.reward_types

    def add_done(self, bot_name: str, done: bool):
        """Mark the end of an episode for a specific bot."""
        buf = self._buf(bot_name)
        if buf.dones and done:
            buf.dones[-1] = True

    # ------------------------------------------------------------------
    # train()  — PPO with per-bot GAE then merged minibatch updates
    # ------------------------------------------------------------------
    def _gae_for_buffer(self, buf: '_BotBuffer') -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor,
                                                           torch.Tensor, torch.Tensor, torch.Tensor,
                                                           torch.Tensor, torch.Tensor, torch.Tensor]:
        """Compute GAE advantages for a single bot's contiguous trajectory."""
        N = len(buf.observations)
        min_len = min(N, len(buf.actions), len(buf.rewards),
                      len(buf.dones), len(buf.log_probs), len(buf.values))
        if min_len == 0:
            return (None,) * 9

        obs_np      = np.array(buf.observations[:min_len])
        obs_t       = torch.FloatTensor(obs_np).to(self.device)
        act_mov     = torch.LongTensor([a['movement'] for a in buf.actions[:min_len]]).to(self.device)
        act_jmp     = torch.LongTensor([a['jump']     for a in buf.actions[:min_len]]).to(self.device)
        act_atk     = torch.LongTensor([a['attack']   for a in buf.actions[:min_len]]).to(self.device)
        act_yaw     = torch.LongTensor([a['yaw']      for a in buf.actions[:min_len]]).to(self.device)
        act_pitch   = torch.LongTensor([a['pitch']    for a in buf.actions[:min_len]]).to(self.device)
        old_lp      = torch.FloatTensor(buf.log_probs[:min_len]).to(self.device)
        values_t    = torch.FloatTensor(buf.values[:min_len]).to(self.device)
        rewards_t   = torch.FloatTensor(buf.rewards[:min_len]).to(self.device)
        dones       = buf.dones[:min_len]

        with torch.no_grad():
            last_obs = torch.FloatTensor(buf.observations[min_len - 1]).unsqueeze(0).to(self.device)
            _, next_value = self.net(last_obs)
            next_value = next_value.squeeze()
            if dones[-1]:
                next_value = torch.tensor(0.0).to(self.device)

            advantages = torch.zeros(min_len).to(self.device)
            gae = 0.0
            for t in reversed(range(min_len)):
                if t == min_len - 1:
                    next_val = next_value
                else:
                    next_val = values_t[t + 1]
                    if dones[t]:
                        next_val = torch.tensor(0.0).to(self.device)
                delta = rewards_t[t] + self.GAMMA * next_val - values_t[t]
                mask = 0.0 if dones[t] else 1.0
                gae = delta + self.GAMMA * self.GAE_LAMBDA * mask * gae
                advantages[t] = gae

            returns_t = advantages + values_t

        return (obs_t, act_mov, act_jmp, act_atk, act_yaw, act_pitch,
                old_lp, advantages, returns_t)

    def train(self, batch_size: int = 64, epochs: int = 4) -> Dict:
        # Merge per-bot buffers after computing GAE independently per bot
        all_obs, all_mov, all_jmp, all_atk, all_yaw, all_pitch = [], [], [], [], [], []
        all_old_lp, all_adv, all_ret = [], [], []
        total_rewards_sum = 0.0

        for bot_name, buf in self._buffers.items():
            if len(buf) == 0:
                continue
            total_rewards_sum += sum(buf.rewards[:len(buf)])
            result = self._gae_for_buffer(buf)
            if result[0] is None:
                continue
            (obs_t, mov, jmp, atk, yaw, pitch, lp, adv, ret) = result
            all_obs.append(obs_t)
            all_mov.append(mov); all_jmp.append(jmp); all_atk.append(atk)
            all_yaw.append(yaw); all_pitch.append(pitch)
            all_old_lp.append(lp); all_adv.append(adv); all_ret.append(ret)

        if not all_obs:
            return {"status": "insufficient_data", "buffer_size": 0}

        obs_t       = torch.cat(all_obs)
        act_movement= torch.cat(all_mov)
        act_jump    = torch.cat(all_jmp)
        act_attack  = torch.cat(all_atk)
        act_yaw     = torch.cat(all_yaw)
        act_pitch   = torch.cat(all_pitch)
        old_log_probs_t = torch.cat(all_old_lp)
        advantages  = torch.cat(all_adv)
        returns_t   = torch.cat(all_ret)

        N = obs_t.shape[0]
        if N < batch_size:
            return {"status": "insufficient_data", "buffer_size": N}

        # Normalize advantages across all bots (standard PPO practice)
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # ---------- PPO minibatch updates ----------
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        total_loss_val = 0.0
        n_updates = 0

        indices = np.arange(N)
        mb = self.MINIBATCH_SIZE

        for epoch in range(self.PPO_EPOCHS):
            np.random.shuffle(indices)
            for start in range(0, N, mb):
                end = start + mb
                if end > N:
                    break
                mb_idx = indices[start:end]
                mb_idx_t = torch.LongTensor(mb_idx).to(self.device)

                mb_obs       = obs_t[mb_idx_t]
                mb_act_mov   = act_movement[mb_idx_t]
                mb_act_jmp   = act_jump[mb_idx_t]
                mb_act_atk   = act_attack[mb_idx_t]
                mb_act_yaw   = act_yaw[mb_idx_t]
                mb_act_pitch = act_pitch[mb_idx_t]
                mb_old_lp    = old_log_probs_t[mb_idx_t]
                mb_adv       = advantages[mb_idx_t]
                mb_ret       = returns_t[mb_idx_t]

                new_lp, new_val, ent = self.net.evaluate_actions(
                    mb_obs, mb_act_mov, mb_act_jmp, mb_act_atk,
                    mb_act_yaw, mb_act_pitch)

                # Clipped surrogate objective
                ratio = torch.exp(new_lp - mb_old_lp)
                surr1 = ratio * mb_adv
                surr2 = torch.clamp(ratio, 1.0 - self.CLIP_EPS, 1.0 + self.CLIP_EPS) * mb_adv
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss
                value_loss = 0.5 * (new_val - mb_ret).pow(2).mean()

                entropy_loss = -ent.mean()

                loss = policy_loss + self.VF_COEF * value_loss + self.ENT_COEF * entropy_loss

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), self.MAX_GRAD_NORM)
                self.optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += (-entropy_loss).item()
                total_loss_val += loss.item()
                n_updates += 1

        # ---------- Metrics ----------
        avg_policy = total_policy_loss / max(n_updates, 1)
        avg_value  = total_value_loss / max(n_updates, 1)
        avg_ent    = total_entropy / max(n_updates, 1)
        avg_loss   = total_loss_val / max(n_updates, 1)

        self.last_loss = avg_loss
        self.last_score = total_rewards_sum

        print(f"PPO stats: loss={avg_loss:.6f}, policy={avg_policy:.6f}, "
              f"value={avg_value:.6f}, entropy={avg_ent:.4f}, "
              f"return_mean={returns_t.mean().item():.4f}, "
              f"adv_std={advantages.std().item():.4f}, "
              f"updates={n_updates}, samples={N}")

        # Clear all per-bot buffers
        for buf in self._buffers.values():
            buf.clear()
        self.observations = []
        self.reward_types = []

        return {
            "status": "success",
            "loss": self.last_loss,
            "policy_loss": avg_policy,
            "value_loss": avg_value,
            "entropy": avg_ent,
            "return_mean": returns_t.mean().item(),
            "return_std": returns_t.std().item(),
            "score": self.last_score,
            "samples_trained": N,
            "ppo_updates": n_updates,
        }

    def get_bot_metrics(self, bot_name: str) -> Dict:
        return {
            "score": self.bot_scores.get(bot_name, 0.0),
            "loss": self.bot_losses.get(bot_name, 0.0),
            "total_rewards": self.bot_scores.get(bot_name, 0.0),
            "recent_rewards": [],
        }

    def save(self, path: str):
        torch.save({
            "net_state_dict": self.net.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "obs_dim": self.observation_dim,
            "bot_scores": self.bot_scores,
            "last_loss": self.last_loss,
            "last_score": self.last_score,
        }, path)
        print(f"[MODEL] Saved to {path}")

    def load(self, path: str):
        checkpoint = torch.load(path, map_location=self.device)
        self.net.load_state_dict(checkpoint["net_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.bot_scores = checkpoint.get("bot_scores", {})
        self.last_loss = checkpoint.get("last_loss", 0.0)
        self.last_score = checkpoint.get("last_score", 0.0)
        print(f"[MODEL] Loaded from {path}")
