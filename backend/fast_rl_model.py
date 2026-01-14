"""
Fast RL Model - Multi-Discrete Action Space
Uses separate heads for each action component for better exploration
"""
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Tuple

class MultiDiscretePolicy(nn.Module):
    """
    Multi-discrete policy with separate heads for each action component.
    Total outputs: 8 (movement) + 2 (jump) + 2 (attack) + 16 (yaw) + 9 (pitch) = 37
    Much more efficient than 4608 flat action space!
    """
    def __init__(self, observation_dim: int, hidden_dim: int = 256):
        super(MultiDiscretePolicy, self).__init__()
        
        # Shared feature extractor
        self.shared = nn.Sequential(
            nn.Linear(observation_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU()
        )
        
        # Separate output heads for each action component
        self.movement_head = nn.Linear(hidden_dim, 8)   # 8 movement directions
        self.jump_head = nn.Linear(hidden_dim, 2)       # jump yes/no
        self.attack_head = nn.Linear(hidden_dim, 2)     # attack yes/no
        self.yaw_head = nn.Linear(hidden_dim, 16)       # 16 yaw buckets
        self.pitch_head = nn.Linear(hidden_dim, 9)      # 9 pitch buckets
    
    def forward(self, observation: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Returns dict of logits for each action component"""
        features = self.shared(observation)
        
        return {
            'movement': self.movement_head(features),
            'jump': self.jump_head(features),
            'attack': self.attack_head(features),
            'yaw': self.yaw_head(features),
            'pitch': self.pitch_head(features)
        }
    
    def get_action(self, observation: np.ndarray, deterministic: bool = False) -> Tuple[Dict[str, int], float]:
        """Sample action from policy, returns (action_dict, total_log_prob)"""
        with torch.no_grad():
            observation_tensor = torch.FloatTensor(observation).unsqueeze(0)
            logits_dict = self.forward(observation_tensor)
            
            actions = {}
            log_probs = []
            
            # Sample from each head independently
            for key, logits in logits_dict.items():
                probs = torch.softmax(logits, dim=-1)
                dist = torch.distributions.Categorical(probs)
                
                if deterministic:
                    action = torch.argmax(probs, dim=-1).item()
                else:
                    action = dist.sample().item()
                
                actions[key] = action
                log_probs.append(dist.log_prob(torch.tensor(action)))
            
            # Total log prob is sum (actions are independent)
            total_log_prob = sum(log_probs).item()
            
            return actions, total_log_prob


class FastRLAgent:
    """Fast RL Agent with multi-discrete action space and reward-to-go"""
    
    def __init__(self, observation_dim: int, device: str = 'cpu', hidden_dim: int = 256):
        self.observation_dim = observation_dim
        self.device = device
        self.policy = MultiDiscretePolicy(observation_dim, hidden_dim=hidden_dim).to(device)
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=3e-4)
        
        # Training buffers
        self.observations = []
        self.actions = []  # Now stores dicts instead of indices
        self.rewards = []
        self.reward_types = []  # Track reward types per sample: list of dicts {type: {'count': int, 'amount': float}}
        self.dones = []
        
        # Metrics
        self.bot_scores = {}
        self.bot_losses = {}
        self.last_loss = 0.0
        self.last_score = 0.0
        
        # Pre-allocate observation vector size
        # Player: 7, Entities: 10*6=60, Blocks: 20*5=100, Inventory: 9*3=27 = 194
        self.obs_vector_size = 194

    def _observation_to_vector_fast(self, observation: Dict, action_space: Dict) -> np.ndarray:
        """Optimized observation vectorization using pre-allocated numpy array"""
        vector = np.zeros(self.obs_vector_size, dtype=np.float32)
        idx = 0
        
        # Player data (7 features)
        if 'player' in observation:
            player = observation['player']
            vector[idx] = player.get('health', 0) / 20.0
            vector[idx+1] = player.get('x', 0) / 100.0
            vector[idx+2] = player.get('y', 0) / 100.0
            vector[idx+3] = player.get('z', 0) / 100.0
            vector[idx+4] = player.get('yaw', 0) / 180.0
            vector[idx+5] = player.get('pitch', 0) / 90.0
            vector[idx+6] = player.get('armor', 0) / 20.0
            idx += 7
        
        # Entities (10 entities × 6 features = 60)
        if 'entities' in observation:
            entities = observation['entities'][:10]
            for i, entity in enumerate(entities):
                base_idx = idx + (i * 6)
                vector[base_idx] = 1.0 if entity.get('isPlayer', False) else 0.0
                vector[base_idx+1] = 1.0 if entity.get('isProjectile', False) else 0.0
                vector[base_idx+2] = entity.get('health', 0) / 20.0
                vector[base_idx+3] = entity.get('relativeX', 0) / 10.0
                vector[base_idx+4] = entity.get('relativeY', 0) / 10.0
                vector[base_idx+5] = entity.get('relativeZ', 0) / 10.0
            idx += 60
        else:
            idx += 60
        
        # Blocks (20 blocks × 5 features = 100)
        if 'blocks' in observation:
            blocks = observation['blocks'][:20]
            for i, block in enumerate(blocks):
                base_idx = idx + (i * 5)
                vector[base_idx] = block.get('x', 0) / 20.0
                vector[base_idx+1] = block.get('y', 0) / 20.0
                vector[base_idx+2] = block.get('z', 0) / 20.0
                vector[base_idx+3] = block.get('distance', 0) / 20.0
                vector[base_idx+4] = 1.0 if block.get('solid', False) else 0.0
            idx += 100
        else:
            idx += 100
        
        # Inventory (9 slots × 3 features = 27)
        if 'inventory' in observation:
            inventory = observation['inventory'][:9]
            for i, inv in enumerate(inventory):
                base_idx = idx + (i * 3)
                vector[base_idx] = inv.get('count', 0) / 64.0
                vector[base_idx+1] = 1.0 if inv.get('isWeapon', False) else 0.0
                vector[base_idx+2] = inv.get('weaponDamage', 0) / 10.0
            idx += 27
        else:
            idx += 27
        
        return vector

    def _actions_dict_to_minecraft(self, actions_dict: Dict[str, int], action_space: Dict) -> Dict:
        """Convert action dict from policy to Minecraft action format"""
        yaw_bins = action_space.get("yawBins", 16)
        pitch_bins = action_space.get("pitchBins", 9)
        
        # Convert yaw/pitch bins to angles
        yaw = float((actions_dict['yaw'] / yaw_bins) * 45.0 - 22.5)
        pitch = float((actions_dict['pitch'] / (pitch_bins - 1)) * 45.0 - 22.5)
        
        return {
            "movement": int(actions_dict['movement']),
            "jump": bool(actions_dict['jump']),
            "sneak": False,
            "sprint": False,
            "attack": bool(actions_dict['attack']),
            "useItem": False,
            "hotbar": -1,
            "yaw": yaw,
            "pitch": pitch
        }

    def predict_action(self, observation: Dict, action_space: Dict, cached_vector: np.ndarray = None) -> Dict:
        """Fast prediction - returns Minecraft-formatted action"""
        if cached_vector is not None:
            obs_vector = cached_vector
        else:
            obs_vector = self._observation_to_vector_fast(observation, action_space)
        
        # Get action from policy (returns dict with component indices)
        actions_dict, _ = self.policy.get_action(obs_vector, deterministic=False)
        
        # Convert to Minecraft format
        minecraft_action = self._actions_dict_to_minecraft(actions_dict, action_space)
        
        # Store for training
        self.observations.append(obs_vector)
        self.actions.append(actions_dict)  # Store the dict, not minecraft_action
        self.rewards.append(0.0)  # Will be updated by add_reward
        self.reward_types.append({})  # Will be updated by add_reward
        
        return minecraft_action

    def add_reward(self, bot_name: str, current_state: Dict, events: List[Dict]):
        """Add reward for training - updates the last reward entry"""
        total_reward = 0.0
        reward_type_data = {}  # Track both count and amount per type: {type: {'count': int, 'amount': float}}
        
        for event in events:
            event_type = event.get('type', '')
            reward_amount = 0.0
            
            if event_type == 'damage_dealt':
                if 'damage_percentage' in event:
                    reward_amount = event.get('damage_percentage', 0) * 10.0
                else:
                    reward_amount = event.get('amount', 0) * 1.0
            elif event_type == 'damage_taken':
                reward_amount = -event.get('amount', 0) * 0.5
            elif event_type == 'good_aim':
                reward_amount = event.get('amount', 0.1)
            elif event_type == 'proximity':
                reward_amount = event.get('amount', 0)
            elif event_type == 'survival':
                reward_amount = event.get('amount', 0)
            elif event_type == 'yaw_exploration':
                reward_amount = event.get('amount', 0)
            elif event_type == 'pitch_control':
                reward_amount = event.get('amount', 0)
            elif event_type == 'won_duel':
                reward_amount = 10.0
            elif event_type == 'death':
                reward_amount = -1.0
            
            if event_type:  # Only track if event has a type
                # Track both count and amount
                if event_type not in reward_type_data:
                    reward_type_data[event_type] = {'count': 0, 'amount': 0.0}
                reward_type_data[event_type]['count'] += 1
                reward_type_data[event_type]['amount'] += reward_amount
                total_reward += reward_amount
        
        # Update the last reward entry
        # Only update if we have observations/actions to match
        # This prevents adding rewards when there are no corresponding actions
        if len(self.observations) == 0:
            # No observations yet, skip reward (will be added when action is predicted)
            return
        
        # Ensure rewards list matches observations length
        while len(self.rewards) < len(self.observations):
            self.rewards.append(0.0)
            self.reward_types.append({})  # Initialize empty reward type dict
        
        # Update the last reward entry (should now exist)
        if len(self.rewards) > 0:
            self.rewards[-1] += total_reward
            # Merge reward type data into last entry (both counts and amounts)
            for reward_type, data in reward_type_data.items():
                if reward_type not in self.reward_types[-1]:
                    self.reward_types[-1][reward_type] = {'count': 0, 'amount': 0.0}
                self.reward_types[-1][reward_type]['count'] += data['count']
                self.reward_types[-1][reward_type]['amount'] += data['amount']
        
        self.bot_scores[bot_name] = self.bot_scores.get(bot_name, 0.0) + total_reward

    def add_done(self, done: bool):
        """Mark episode as done"""
        self.dones.append(done)

    def train(self, batch_size: int = 64, epochs: int = 1) -> Dict:
        """Policy gradient training with reward-to-go and multi-discrete actions"""
        if len(self.observations) < batch_size:
            return {"status": "insufficient_data", "buffer_size": len(self.observations)}
        
        # Ensure all buffers have the same length
        min_len = min(len(self.observations), len(self.actions), len(self.rewards), len(self.reward_types))
        # Trim all buffers to the minimum length to keep them synchronized
        self.observations = self.observations[:min_len]
        self.actions = self.actions[:min_len]
        self.rewards = self.rewards[:min_len]
        self.reward_types = self.reward_types[:min_len]
        
        obs_tensor = torch.FloatTensor(np.array(self.observations)).to(self.device)
        
        # Extract each action component from the action dicts
        actions_movement = torch.LongTensor([a['movement'] for a in self.actions]).to(self.device)
        actions_jump = torch.LongTensor([a['jump'] for a in self.actions]).to(self.device)
        actions_attack = torch.LongTensor([a['attack'] for a in self.actions]).to(self.device)
        actions_yaw = torch.LongTensor([a['yaw'] for a in self.actions]).to(self.device)
        actions_pitch = torch.LongTensor([a['pitch'] for a in self.actions]).to(self.device)
        
        # Calculate reward-to-go (discounted returns)
        returns = []
        R = 0
        gamma = 0.99
        for r in reversed(self.rewards):
            R = r + gamma * R
            returns.insert(0, R)
        
        returns_tensor = torch.FloatTensor(returns).to(self.device)
        
        # Normalize returns (reduces variance)
        if len(returns_tensor) > 1:
            returns_normalized = (returns_tensor - returns_tensor.mean()) / (returns_tensor.std() + 1e-8)
        else:
            # If only one sample, can't normalize - use zero-centered
            returns_normalized = returns_tensor - returns_tensor.mean()
        
        self.optimizer.zero_grad()
        
        # Forward pass - get logits for all action components
        logits_dict = self.policy(obs_tensor)
        
        # Create distributions for each action component
        movement_dist = torch.distributions.Categorical(logits=logits_dict['movement'])
        jump_dist = torch.distributions.Categorical(logits=logits_dict['jump'])
        attack_dist = torch.distributions.Categorical(logits=logits_dict['attack'])
        yaw_dist = torch.distributions.Categorical(logits=logits_dict['yaw'])
        pitch_dist = torch.distributions.Categorical(logits=logits_dict['pitch'])
        
        # Calculate log probabilities for the actions that were taken
        log_prob_movement = movement_dist.log_prob(actions_movement)
        log_prob_jump = jump_dist.log_prob(actions_jump)
        log_prob_attack = attack_dist.log_prob(actions_attack)
        log_prob_yaw = yaw_dist.log_prob(actions_yaw)
        log_prob_pitch = pitch_dist.log_prob(actions_pitch)
        
        # Total log prob (sum because actions are independent)
        total_log_prob = log_prob_movement + log_prob_jump + log_prob_attack + log_prob_yaw + log_prob_pitch
        
        # Ensure both tensors are 1D and have the same shape
        total_log_prob = total_log_prob.squeeze()
        returns_normalized = returns_normalized.squeeze()
        
        # Verify shapes match
        if total_log_prob.dim() != 1 or returns_normalized.dim() != 1:
            raise ValueError(f"Expected 1D tensors: total_log_prob.dim()={total_log_prob.dim()}, returns_normalized.dim()={returns_normalized.dim()}")
        
        if total_log_prob.shape[0] != returns_normalized.shape[0]:
            raise ValueError(f"Shape mismatch: total_log_prob.shape={total_log_prob.shape}, returns_normalized.shape={returns_normalized.shape}, "
                           f"obs_tensor.shape={obs_tensor.shape}, len(actions)={len(self.actions)}, len(rewards)={len(self.rewards)}")
        
        # Policy gradient loss: maximize log_prob * return
        policy_loss = -(total_log_prob * returns_normalized).mean()
        
        # Entropy bonus for exploration (sum entropy of all heads)
        entropy = (movement_dist.entropy() + jump_dist.entropy() + 
                   attack_dist.entropy() + yaw_dist.entropy() + 
                   pitch_dist.entropy()).mean()
        
        entropy_bonus = 0.01
        entropy_loss = -entropy_bonus * entropy
        
        # Total loss
        loss = policy_loss + entropy_loss
        
        loss.backward()
        
        # Clip gradients
        torch.nn.utils.clip_grad_norm_(self.policy.parameters(), max_norm=1.0)
        
        self.optimizer.step()
        
        self.last_loss = loss.item()
        self.last_score = returns_tensor.sum().item()
        
        # Log training stats
        print(f"Training stats: loss={loss.item():.6f}, policy_loss={policy_loss.item():.6f}, "
              f"entropy={entropy.item():.4f}, return_mean={returns_tensor.mean().item():.4f}, "
              f"return_std={returns_tensor.std().item():.4f}, "
              f"min_return={returns_tensor.min().item():.4f}, max_return={returns_tensor.max().item():.4f}")
        
        # Clear buffers
        self.observations.clear()
        self.actions.clear()
        self.rewards.clear()
        self.reward_types.clear()
        self.dones.clear()
        
        return {
            "status": "success",
            "loss": self.last_loss,
            "policy_loss": policy_loss.item(),
            "entropy": entropy.item(),
            "return_mean": returns_tensor.mean().item(),
            "return_std": returns_tensor.std().item(),
            "score": self.last_score,
            "samples_trained": len(obs_tensor)
        }
    
    def get_bot_metrics(self, bot_name: str) -> Dict:
        """Get metrics for a specific bot"""
        return {
            "score": self.bot_scores.get(bot_name, 0.0),
            "loss": self.bot_losses.get(bot_name, 0.0),
            "total_rewards": self.bot_scores.get(bot_name, 0.0),
            "recent_rewards": []
        }