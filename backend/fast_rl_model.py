"""
Fast RL Model - PPO with Multi-Discrete Action Space
Actor-critic architecture with separate heads for each action component.
Uses clipped surrogate objective, GAE advantages, and minibatch updates.
"""
import os
import torch
import torch.nn as nn
import numpy as np
import math
from typing import Dict, List, Tuple

YAW_BINS = [-20.0, -10.0, -5.0, -2.0, 0.0, 2.0, 5.0, 10.0, 20.0]
PITCH_BINS = [-5.0, -2.0, 0.0, 2.0, 5.0]

# Flat action space dimensions (for ablation)
# Layout: pitch(5) × yaw(9) × attack(2) × sprint(2) × jump(2) × movement(8)
_FLAT_DIMS = [5, 9, 2, 2, 2, 8]
FLAT_ACTION_SIZE = 1
for _d in _FLAT_DIMS:
    FLAT_ACTION_SIZE *= _d   # = 2880

def encode_flat_action(movement: int, jump: int, sprint: int,
                        attack: int, yaw: int, pitch: int) -> int:
    """Encode factored actions into a single flat index."""
    return (movement * (2 * 2 * 2 * 9 * 5) +
            jump     * (    2 * 2 * 9 * 5) +
            sprint   * (        2 * 9 * 5) +
            attack   * (            9 * 5) +
            yaw      *                  5  +
            pitch)

def decode_flat_action(idx: int) -> dict:
    """Decode a flat index back into the six action components."""
    pitch    = idx % 5;          idx //= 5
    yaw      = idx % 9;          idx //= 9
    attack   = idx % 2;          idx //= 2
    sprint   = idx % 2;          idx //= 2
    jump     = idx % 2;          idx //= 2
    movement = idx % 8
    return {'movement': movement, 'jump': jump, 'sprint': sprint,
            'attack': attack, 'yaw': yaw, 'pitch': pitch}


class FlatActorCritic(nn.Module):
    """
    Ablation variant: single flat categorical head over all 2880 action combinations.
    Same shared trunk as ActorCritic; exists solely to test the hypothesis that
    factored multi-discrete heads are easier to learn than a joint distribution.
    """
    def __init__(self, observation_dim: int, hidden_dim: int = 256):
        super(FlatActorCritic, self).__init__()

        self.shared = nn.Sequential(
            nn.Linear(observation_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh()
        )
        self.action_head = nn.Linear(hidden_dim, FLAT_ACTION_SIZE)
        self.value_head  = nn.Linear(hidden_dim, 1)

        nn.init.orthogonal_(self.action_head.weight, gain=0.01)
        nn.init.zeros_(self.action_head.bias)
        nn.init.orthogonal_(self.value_head.weight, gain=1.0)
        nn.init.zeros_(self.value_head.bias)

    def forward(self, obs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        features = self.shared(obs)
        logits = self.action_head(features)
        value  = self.value_head(features).squeeze(-1)
        return logits, value

    def get_action_and_value(self, obs_np: np.ndarray, deterministic: bool = False):
        with torch.no_grad():
            device = next(self.parameters()).device
            obs_t = torch.FloatTensor(obs_np).unsqueeze(0).to(device)
            logits, value = self.forward(obs_t)
            dist = torch.distributions.Categorical(logits=logits)
            flat_idx = (torch.argmax(logits, dim=-1).item()
                        if deterministic else dist.sample().item())
            lp = dist.log_prob(torch.tensor(flat_idx, device=device)).item()
            actions = decode_flat_action(flat_idx)
            actions['_flat_idx'] = flat_idx   # stored in buffer for training
            return actions, lp, value.item()

    def evaluate_actions(self, obs_t: torch.Tensor, flat_idx_t: torch.Tensor):
        logits, value = self.forward(obs_t)
        dist = torch.distributions.Categorical(logits=logits)
        log_prob = dist.log_prob(flat_idx_t)
        entropy  = dist.entropy()
        return log_prob, entropy, value



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
        self.sprint_head = nn.Linear(hidden_dim, 2) # NEW: Sprint head
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
        for module in [self.movement_head, self.jump_head, self.sprint_head, self.attack_head,
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
            'sprint': self.sprint_head(features), # NEW
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
                         act_sprint: torch.Tensor, # NEW
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
              + dists['sprint'].log_prob(act_sprint) # NEW
              + dists['attack'].log_prob(act_attack)
              + dists['yaw'].log_prob(act_yaw)
              + dists['pitch'].log_prob(act_pitch))

        ent = sum(d.entropy() for d in dists.values())

        return lp, values, ent


class _BotBuffer:
    """Per-bot rollout buffer — keeps one bot's trajectory separate."""
    __slots__ = ('observations', 'actions', 'log_probs', 'values', 'rewards',
                 'reward_types', 'dones', 'last_opp_state', 'last_wall_rays')

    def __init__(self):
        self.observations: List[np.ndarray] = []
        self.actions: List[Dict[str, int]] = []
        self.log_probs: List[float] = []
        self.values: List[float] = []
        self.rewards: List[float] = []
        self.reward_types: List[Dict] = []
        self.dones: List[bool] = []
        self.last_opp_state: Dict[str, float] = {}
        self.last_wall_rays: List[float] = [1.0] * 8

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
    ENT_COEF = 0.01 # Encourages deterministic policy convergence faster
    MAX_GRAD_NORM = 0.5
    LR = 3e-4
    PPO_EPOCHS = 4
    MINIBATCH_SIZE = 64

    # Reward types that are zeroed in sparse mode (ablation: no shaping)
    SPARSE_ZERO_TYPES = frozenset({'good_aim', 'proximity', 'pitch_control', 'aim_hold', 'extreme_pitch_penalty'})

    def __init__(self, observation_dim: int, device: str = 'cpu', hidden_dim: int = 256, weights: dict = None):
        self.observation_dim = observation_dim
        self.device = device
        self.reward_mode = os.getenv("CAMBIUM_REWARD_MODE", "shaped")

        # Weights come from the caller (state.REWARD_WEIGHTS, loaded from JSON).
        # Inline defaults here are a last-resort fallback only.
        if weights is not None:
            self.weights = weights
        else:
            self.weights = {
                "doing_damage": 10.0, "taking_damage": -2.0,
                "won_duel": 90.0, "death": -20.0,
                "episode_timeout": -10.0, "no_damage_penalty": -10.0,
                "good_aim": 0.1, "proximity": 0.05,
                "pitch_control": 0.05, "aim_hold": 0.1,
                "extreme_pitch_penalty": -0.05,
            }

        # Network selection: factored multi-discrete (default) or flat categorical (ablation)
        self.flat_action = os.getenv("CAMBIUM_FLAT_ACTION", "0") == "1"
        net_cls = FlatActorCritic if self.flat_action else ActorCritic
        if self.flat_action:
            print(f"[MODEL] Using FlatActorCritic ({FLAT_ACTION_SIZE} actions — ablation)")
        else:
            print(f"[MODEL] Using ActorCritic (factored multi-discrete — default)")

        self.net = net_cls(observation_dim, hidden_dim).to(device)
        self.optimizer = torch.optim.Adam(self.net.parameters(), lr=self.LR, eps=1e-5)

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

        self.obs_vector_size = 22  # 3 player + 7 opponent + 8 walls + 4 combat

        # Keep reference to policy for compatibility with main.py obs caching
        self.policy = self.net

        # Self-play: frozen opponent network (same type as live net)
        self._hidden_dim = hidden_dim
        self.opponent_net = net_cls(observation_dim, hidden_dim).to(device)
        self.opponent_net.load_state_dict(self.net.state_dict())
        self.opponent_net.eval()  # never trains
        self._opponent_snapshot_count = 0

    def _buf(self, bot_name: str) -> '_BotBuffer':
        if bot_name not in self._buffers:
            self._buffers[bot_name] = _BotBuffer()
        return self._buffers[bot_name]

    # ------------------------------------------------------------------
    # Observation vectorisation (unchanged)
    # ------------------------------------------------------------------
    def _observation_to_vector_fast(self, observation: Dict, action_space: Dict, bot_name: str = "") -> np.ndarray:
        """Convert observation dict to compact 21-dim vector.
        
        Layout:
          [0]     player health (0-1)
          [1]     player yaw normalized (-1 to 1)
          [2]     player pitch normalized (-1 to 1)
          [3]     opponent isAlive (0 or 1)
          [4]     opponent health (0-1)
          [5]     opponent relX (normalized)
          [6]     opponent relY (normalized)
          [7]     opponent relZ (normalized)
          [8]     opponent facingYaw normalized (-1 to 1)
          [9]     opponent facingPitch normalized (-1 to 1)
          [10-17] wall distances, 8 cardinal rays (normalized 0-1, 0=touching, 1=far)
          [18]    opponent distance (normalized)
          [19]    aim quality: dot product (-1 to 1, 1=on target)
          [20]    horizontal yaw error (normalized -1 to 1, 0=on target)
          [21]    vertical pitch error (normalized -1 to 1, 0=on target)
        """
        vector = np.zeros(22, dtype=np.float32) # Increased dim to 22
        idx = 0

        # --- Player (3 dims) ---
        player_yaw = 0.0
        player_pitch = 0.0
        player_x, player_y, player_z = 0.0, 0.0, 0.0
        if 'player' in observation:
            p = observation['player']
            vector[idx]   = p.get('health', 0) / 20.0
            player_yaw = p.get('yaw', 0)
            player_pitch = p.get('pitch', 0)
            
            # Normalize yaw to (-180, 180) to remove spin redundancy
            norm_yaw = (player_yaw + 180) % 360 - 180
            vector[idx+1] = norm_yaw / 180.0
            vector[idx+2] = player_pitch / 90.0
            
            player_x = p.get('x', 0)
            player_y = p.get('y', 0)
            player_z = p.get('z', 0)
        idx += 3

        # --- Opponent (7 dims) ---
        opp_rel_x, opp_rel_y, opp_rel_z = 0.0, 0.0, 0.0
        opp_distance = 10.0  # default far
        opp_health = 0.0
        opp_yaw = 0.0
        opp_pitch = 0.0
        is_alive = 0.0

        if 'entities' in observation and len(observation['entities']) > 0:
            e = observation['entities'][0]  # Only use the first (closest/paired) entity
            is_alive = 1.0
            opp_health = e.get('health', 0) / 20.0
            opp_rel_x = e.get('relativeX', 0)
            opp_rel_y = e.get('relativeY', 0)
            opp_rel_z = e.get('relativeZ', 0)
            opp_yaw = e.get('facingYaw', 0)
            opp_pitch = e.get('facingPitch', 0)
            
            if bot_name:
                buf = self._buf(bot_name)
                buf.last_opp_state = {
                    'rel_x': opp_rel_x, 'rel_y': opp_rel_y, 'rel_z': opp_rel_z,
                    'yaw': opp_yaw, 'pitch': opp_pitch, 'health': opp_health
                }
        else:
            is_alive = 0.0
            if bot_name:
                buf = self._buf(bot_name)
                cache = getattr(buf, 'last_opp_state', {})
                if cache and isinstance(cache, dict) and 'rel_x' in cache:
                    opp_rel_x = cache['rel_x']
                    opp_rel_y = cache['rel_y']
                    opp_rel_z = cache['rel_z']
                    opp_yaw = cache['yaw']
                    opp_pitch = cache['pitch']
                    opp_health = cache['health']

        vector[idx]   = is_alive
        vector[idx+1] = opp_health
        vector[idx+2] = opp_rel_x / 10.0
        vector[idx+3] = opp_rel_y / 10.0
        vector[idx+4] = opp_rel_z / 10.0
            
        # Normalize opponent yaw to (-180, 180)
        norm_e_yaw = (opp_yaw + 180) % 360 - 180
        vector[idx+5] = norm_e_yaw / 180.0
        vector[idx+6] = opp_pitch / 90.0
        opp_distance = (opp_rel_x**2 + opp_rel_y**2 + opp_rel_z**2) ** 0.5
        if is_alive == 0.0 and opp_distance == 0.0:
            opp_distance = 10.0 # Only default far if cache was empty
            
        idx += 7

        # Each ray = normalized distance to nearest wall (0=touching, 1=50+ blocks away)
        # Pre-fill with 1.0 (open space)
        wall_rays = [1.0] * 8
        if bot_name:
            buf = self._buf(bot_name)
            cached_rays = getattr(buf, 'last_wall_rays', [])
            if len(cached_rays) == 8:
                wall_rays = list(cached_rays)
            
        if 'blocks' in observation and len(observation['blocks']) > 0:
            # Update specific rays provided in the payload
            for i, b in enumerate(observation['blocks'][:8]):
                dist = b.get('distance', 50.0)
                # Bounds check to prevent "list assignment index out of range"
                if i < 8:
                    wall_rays[i] = max(0.0, min(dist / 50.0, 1.0))
            
            if bot_name:
                buf = self._buf(bot_name)
                buf.last_wall_rays = list(wall_rays)

        for i, val in enumerate(wall_rays):
            if i < 8: # Defensive
                vector[idx + i] = val
        idx += 8

        # --- Computed combat features (3 dims) ---
        # Distance to opponent (normalized)
        vector[idx] = min(opp_distance / 10.0, 1.0)

        # Aim quality: dot product of player look direction and direction to opponent
        if opp_distance > 0.01:
            yaw_rad = math.radians(player_yaw)
            pitch_rad = math.radians(player_pitch)
            # Player look direction
            look_x = -math.sin(yaw_rad) * math.cos(pitch_rad)
            look_y = -math.sin(pitch_rad)
            look_z = math.cos(yaw_rad) * math.cos(pitch_rad)
            # Direction to opponent (normalized)
            dir_x = opp_rel_x / opp_distance
            dir_y = opp_rel_y / opp_distance
            dir_z = opp_rel_z / opp_distance
            # Dot product: 1 = looking right at them, -1 = looking away
            dot = look_x * dir_x + look_y * dir_y + look_z * dir_z
            vector[idx+1] = dot
            
            # --- NEW: Explicit Aim Errors (Critical for learning directional aiming) ---
            # Horizontal (Yaw) Error
            # In MC: 0=S, 90=W, 180=N, 270=E. math.atan2(-x, z) gives this clockwise yaw.
            yaw_to_opp = math.degrees(math.atan2(-opp_rel_x, opp_rel_z))
            yaw_err = (yaw_to_opp - player_yaw + 180) % 360 - 180
            vector[idx+2] = yaw_err / 180.0
            
            # Vertical (Pitch) Error
            # MC Pitch: -90=UP, 0=Horiz, 90=DOWN
            pitch_to_opp = math.degrees(math.atan2(-opp_rel_y, max((opp_rel_x**2 + (opp_rel_z**2))**0.5, 0.01)))
            pitch_err = pitch_to_opp - player_pitch
            # Pitch error capped at 90 but already normalized below
            vector[idx+3] = pitch_err / 90.0 # Error index shifted by 1 due to yaw_err addition
        idx += 4 # Combat features now take 4 dimensions

        return vector

    def _actions_dict_to_minecraft(self, ad: Dict[str, int], action_space: Dict) -> Dict:
        return {
            "movement": int(ad['movement']),
            "jump": bool(ad['jump']),  # re-enabled: useful for combat movement
            "sneak": False,
            "sprint": bool(ad.get('sprint', False)), # NEW: Sprint enabled
            "attack": bool(ad['attack']),
            "useItem": False,
            "hotbar": -1,
            "yaw": float(YAW_BINS[ad['yaw']]),
            "pitch": float(PITCH_BINS[ad['pitch']]),
        }

    # ------------------------------------------------------------------
    # Self-play: frozen opponent
    # ------------------------------------------------------------------
    def snapshot_opponent(self):
        """Copy current policy weights to the frozen opponent network."""
        self.opponent_net.load_state_dict(self.net.state_dict())
        self.opponent_net.eval()
        self._opponent_snapshot_count += 1
        print(f"[SELF-PLAY] Opponent snapshot #{self._opponent_snapshot_count} created")

    def predict_action_opponent(self, observation: Dict, action_space: Dict,
                                bot_name: str = "default") -> Dict:
        """Use the frozen opponent network to pick an action.
        Does NOT record to any buffer — the opponent's data is not trained on."""
        obs_vec = self._observation_to_vector_fast(observation, action_space, bot_name)
        with torch.no_grad():
            device = next(self.opponent_net.parameters()).device
            obs_t = torch.FloatTensor(obs_vec).unsqueeze(0).to(device)
            logits, _ = self.opponent_net(obs_t)
            actions = {}
            for key, lg in logits.items():
                dist = torch.distributions.Categorical(logits=lg)
                actions[key] = dist.sample().item()
        return self._actions_dict_to_minecraft(actions, action_space)

    # ------------------------------------------------------------------
    # predict_action  (same signature as before, now bot-name aware)
    # ------------------------------------------------------------------
    def predict_action(self, observation: Dict, action_space: Dict,
                       cached_vector: np.ndarray = None,
                       bot_name: str = "default") -> Dict:
        obs_vec = cached_vector if cached_vector is not None else \
            self._observation_to_vector_fast(observation, action_space, bot_name)

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
        obs_vec = self._observation_to_vector_fast(observation, action_space, bot_name)

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

    def predict_action_eval(self, observation: Dict, action_space: Dict,
                            bot_name: str = "default") -> Dict:
        """Forward pass through the *live* policy without writing to buffer.
        Used during periodic eval episodes so learner acts normally but
        no gradient data is collected.  Reward accumulation is handled
        separately in the eval phase counters."""
        obs_vec = self._observation_to_vector_fast(observation, action_space, bot_name)
        actions_dict, _, _ = self.net.get_action_and_value(obs_vec)
        return self._actions_dict_to_minecraft(actions_dict, action_space)

    def predict_action_frozen(self, frozen_net, observation: Dict,
                              action_space: Dict, bot_name: str = "default") -> Dict:
        """Forward pass through an arbitrary frozen network without writing to buffer.
        Used for the IT_WOKRS baseline opponent during eval phases."""
        obs_vec = self._observation_to_vector_fast(observation, action_space, bot_name)
        with torch.no_grad():
            device = next(frozen_net.parameters()).device
            obs_t = torch.FloatTensor(obs_vec).unsqueeze(0).to(device)
            if hasattr(frozen_net, 'action_head'):   # FlatActorCritic
                logits, _ = frozen_net(obs_t)
                dist = torch.distributions.Categorical(logits=logits)
                flat_idx = dist.sample().item()
                ad = decode_flat_action(flat_idx)
            else:                                      # ActorCritic (factored)
                logits_dict, _ = frozen_net(obs_t)
                ad = {k: torch.distributions.Categorical(logits=lg).sample().item()
                      for k, lg in logits_dict.items()}
        return self._actions_dict_to_minecraft(ad, action_space)

    def compute_reward_amount(self, events: list) -> float:
        """Compute total reward for a list of events without touching the buffer.
        Used to accumulate both sides' rewards during eval episodes."""
        total = 0.0
        for ev in events:
            _, amt = self._compute_reward(ev)
            total += amt
        return total


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
            # Option B: Use weight as a literal per-event reward (static)
            amt = self.weights.get("doing_damage", 4.5)
        elif et == 'damage_taken':
            # Option B: Use weight as a literal per-event penalty (static)
            amt = self.weights.get("taking_damage", -1.0)
        elif et == 'good_aim':
            # Use centered weights
            weight = self.weights.get("good_aim", 0.05)
            amt = ev.get('amount', 0.1) * weight
        elif et == 'proximity':
            weight = self.weights.get("proximity", 0.05)
            amt = ev.get('amount', 0) * weight
        elif et == 'pitch_control':
            weight = self.weights.get("pitch_control", 0.02)
            amt = ev.get('amount', 0) * weight
        elif et == 'extreme_pitch_penalty':
            weight = self.weights.get("extreme_pitch_penalty", -0.5)
            amt = ev.get('amount', -0.03) * (weight / -0.5)
        elif et == 'aim_hold':
            weight = self.weights.get("aim_hold", 0.05)
            amt = ev.get('amount', 0.1) * weight
        elif et == 'won_duel':
            amt = self.weights.get("won_duel", 10.0)
        elif et == 'death':
            amt = self.weights.get("death", -1.0)
        elif et == 'episode_timeout':
            amt = self.weights.get("episode_timeout", -10.0)
        elif et == 'no_damage_penalty':
            amt = self.weights.get("no_damage_penalty", -10.0)
        # (legacy types 'survival'/'yaw_exploration' removed — no longer sent)

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
            # Still record in reward_types for logging purposes
            if not buf.reward_types:
                buf.reward_types.append({})
            for rtype, data in rt_data.items():
                if rtype not in buf.reward_types[-1]:
                    buf.reward_types[-1][rtype] = {'count': 0, 'amount': 0.0}
                buf.reward_types[-1][rtype]['count'] += data['count']
                buf.reward_types[-1][rtype]['amount'] += data['amount']
            self.reward_types = buf.reward_types
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
    def _gae_for_buffer(self, buf: '_BotBuffer') -> Tuple:
        """Compute GAE advantages for a single bot's contiguous trajectory."""
        min_len = min(len(buf.observations), len(buf.actions), len(buf.rewards),
                      len(buf.dones), len(buf.log_probs), len(buf.values))
        if min_len == 0:
            return (None,) * 10

        obs_np      = np.array(buf.observations[:min_len])
        obs_t       = torch.FloatTensor(obs_np).to(self.device)
        # Flat action index (ablation) or factored tensors (default)
        if self.flat_action:
            flat_idx = torch.LongTensor(
                [a.get('_flat_idx',
                        encode_flat_action(a['movement'], a['jump'],
                                           a.get('sprint', 0), a['attack'],
                                           a['yaw'], a['pitch']))
                 for a in buf.actions[:min_len]]).to(self.device)
            act_mov = act_jmp = act_spr = act_atk = act_yaw = act_pitch = flat_idx
        else:
            flat_idx    = None
            act_mov     = torch.LongTensor([a['movement'] for a in buf.actions[:min_len]]).to(self.device)
            act_jmp     = torch.LongTensor([a['jump']     for a in buf.actions[:min_len]]).to(self.device)
            act_spr     = torch.LongTensor([a.get('sprint', 0) for a in buf.actions[:min_len]]).to(self.device)
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

        return (obs_t, act_mov, act_jmp, act_spr, act_atk, act_yaw, act_pitch,
                old_lp, advantages, returns_t, values_t)

    # Reward weights are passed via __init__(weights=...) from state.REWARD_WEIGHTS.
    # No class-level defaults — single source of truth is reward_weights.json.

    def train(self, batch_size: int = 64, epochs: int = 4) -> Dict:
        # Merge per-bot buffers after computing GAE independently per bot
        all_obs, all_mov, all_jmp, all_spr, all_atk, all_yaw, all_pitch = [], [], [], [], [], [], []
        all_old_lp, all_adv, all_ret, all_val = [], [], [], []
        total_rewards_sum = 0.0

        for bot_name, buf in self._buffers.items():
            if len(buf) == 0:
                continue
            total_rewards_sum += sum(buf.rewards[:len(buf)])
            result = self._gae_for_buffer(buf)
            if result[0] is None:
                continue
            (obs_t, mov, jmp, spr, atk, yaw, pitch, lp, adv, ret, val) = result
            all_obs.append(obs_t)
            all_mov.append(mov); all_jmp.append(jmp); all_spr.append(spr); all_atk.append(atk)
            all_yaw.append(yaw); all_pitch.append(pitch)
            all_old_lp.append(lp); all_adv.append(adv); all_ret.append(ret); all_val.append(val)

        if not all_obs:
            return {"status": "insufficient_data", "buffer_size": 0}

        obs_t       = torch.cat(all_obs)
        act_movement= torch.cat(all_mov)
        act_jump    = torch.cat(all_jmp)
        act_sprint  = torch.cat(all_spr)
        act_attack  = torch.cat(all_atk)
        act_yaw     = torch.cat(all_yaw)
        act_pitch   = torch.cat(all_pitch)
        old_log_probs_t = torch.cat(all_old_lp)
        advantages  = torch.cat(all_adv)
        returns_t   = torch.cat(all_ret)
        values_t    = torch.cat(all_val)

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
                mb_old_lp    = old_log_probs_t[mb_idx_t]
                mb_adv       = advantages[mb_idx_t]
                mb_ret       = returns_t[mb_idx_t]
                mb_val       = values_t[mb_idx_t]

                if self.flat_action:
                    new_lp, ent, new_val = self.net.evaluate_actions(mb_obs, mb_act_mov)
                else:
                    mb_act_jmp   = act_jump[mb_idx_t]
                    mb_act_spr   = act_sprint[mb_idx_t]
                    mb_act_atk   = act_attack[mb_idx_t]
                    mb_act_yaw   = act_yaw[mb_idx_t]
                    mb_act_pitch = act_pitch[mb_idx_t]
                    new_lp, new_val, ent = self.net.evaluate_actions(
                        mb_obs, mb_act_mov, mb_act_jmp, mb_act_spr, mb_act_atk,
                        mb_act_yaw, mb_act_pitch)

                # Clipped surrogate objective
                ratio = torch.exp(new_lp - mb_old_lp)
                surr1 = ratio * mb_adv
                surr2 = torch.clamp(ratio, 1.0 - self.CLIP_EPS, 1.0 + self.CLIP_EPS) * mb_adv
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss with clipping (prevents 'breaking' the model on large reward spikes like wins)
                # This is standard PPO-2 practice to improve stability
                v_loss_unclipped = (new_val - mb_ret).pow(2)
                v_clipped = mb_val + torch.clamp(new_val - mb_val, -self.CLIP_EPS, self.CLIP_EPS)
                v_loss_clipped = (v_clipped - mb_ret).pow(2)
                value_loss = 0.5 * torch.max(v_loss_unclipped, v_loss_clipped).mean()

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
        # Important for self-play: sync the opponent snapshot with the resumed model
        if hasattr(self, 'opponent_net'):
            self.snapshot_opponent()
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.bot_scores = checkpoint.get("bot_scores", {})
        self.last_loss = checkpoint.get("last_loss", 0.0)
        self.last_score = checkpoint.get("last_score", 0.0)
        print(f"[MODEL] Loaded from {path}")
