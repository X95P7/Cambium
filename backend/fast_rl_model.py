"""
Fast RL Model - Optimized for <50ms inference
Uses pre-allocated numpy arrays and minimal features
"""
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Tuple

class FastLinearPolicy(nn.Module):
    """2-layer MLP with ReLU for better expressiveness while maintaining fast inference"""
    def __init__(self, observation_dim: int, action_dim: int, hidden_dim: int = 256):
        super(FastLinearPolicy, self).__init__()
        self.hidden_dim = hidden_dim
        self.fc1 = nn.Linear(observation_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, action_dim)

    def forward(self, observation: torch.Tensor) -> torch.Tensor:
        x = self.fc1(observation)
        x = self.relu(x)
        x = self.fc2(x)
        return x

    def get_action(self, observation: np.ndarray, deterministic: bool = False) -> Tuple[int, float]:
        with torch.no_grad():
            observation_tensor = torch.FloatTensor(observation).unsqueeze(0)
            action_logits = self.forward(observation_tensor)
            action_probs = torch.nn.functional.softmax(action_logits, dim=-1)
            
            if deterministic:
                # Use argmax for deterministic actions
                action = int(torch.argmax(action_probs, dim=-1).item())
            else:
                # Sample from the probability distribution for exploration
                action_dist = torch.distributions.Categorical(action_probs)
                action = int(action_dist.sample().item())
        return action, 0.0


class FastRLAgent:
    """Fast RL Agent with optimized observation processing"""
    
    def __init__(self, observation_dim: int, action_dim: int, device: str = 'cpu', hidden_dim: int = 256):
        self.observation_dim = observation_dim
        self.action_dim = action_dim
        self.device = device
        self.policy = FastLinearPolicy(observation_dim, action_dim, hidden_dim=hidden_dim).to(device)
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=1e-3)
        
        # Training buffers
        self.observations = []
        self.actions = []
        self.rewards = []
        self.dones = []
        
        # Metrics
        self.bot_scores = {}
        self.bot_losses = {}
        self.last_loss = 0.0
        self.last_score = 0.0
        
        # Pre-allocate observation vector size (optimized dimensions)
        # Player: 7, Entities: 10*6=60, Blocks: 20*5=100, Inventory: 9*3=27 = 194
        self.obs_vector_size = 194

    def _observation_to_vector_fast(self, observation: Dict, action_space: Dict) -> np.ndarray:
        """
        Optimized observation vectorization using pre-allocated numpy array.
        Reduced features: 20 blocks max, 10 entities max, minimal features per entity.
        """
        # Pre-allocate array - much faster than list operations
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
            entities = observation['entities'][:10]  # Limit to 10
            for i, entity in enumerate(entities):
                base_idx = idx + (i * 6)
                vector[base_idx] = 1.0 if entity.get('isPlayer', False) else 0.0
                vector[base_idx+1] = 1.0 if entity.get('isProjectile', False) else 0.0
                vector[base_idx+2] = entity.get('health', 0) / 20.0
                vector[base_idx+3] = entity.get('relativeX', 0) / 10.0
                vector[base_idx+4] = entity.get('relativeY', 0) / 10.0
                vector[base_idx+5] = entity.get('relativeZ', 0) / 10.0
            idx += 60  # Always 60 (10 entities × 6)
        else:
            idx += 60
        
        # Blocks (20 blocks × 5 features = 100) - REDUCED from 50
        if 'blocks' in observation:
            blocks = observation['blocks'][:20]  # Limit to 20 instead of 50
            for i, block in enumerate(blocks):
                base_idx = idx + (i * 5)
                vector[base_idx] = block.get('x', 0) / 20.0
                vector[base_idx+1] = block.get('y', 0) / 20.0
                vector[base_idx+2] = block.get('z', 0) / 20.0
                vector[base_idx+3] = block.get('distance', 0) / 20.0
                vector[base_idx+4] = 1.0 if block.get('solid', False) else 0.0
            idx += 100  # Always 100 (20 blocks × 5)
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
            idx += 27  # Always 27 (9 slots × 3)
        else:
            idx += 27
        
        return vector

    def _action_idx_to_dict_fast(self, action_idx: int, action_space: Dict) -> Dict:
        """Convert action index to action dictionary - returns native Python types for JSON serialization"""
        # Simplified action space: movement (8) + jump (1) + attack (1) + yaw (16) + pitch (9) = 35
        # But we use the full action_dim which might be larger
        movement_bins = action_space.get("movementBins", 8)
        yaw_bins = action_space.get("yawBins", 16)
        pitch_bins = action_space.get("pitchBins", 9)
        
        # Decode action index - ensure it's a Python int
        remaining = int(action_idx)
        
        # Movement (0-7)
        movement = int(remaining % movement_bins)
        remaining //= movement_bins
        
        # Jump (0-1)
        jump = bool((remaining % 2) == 1)
        remaining //= 2
        
        # Attack (0-1)
        attack = bool((remaining % 2) == 1)
        remaining //= 2
        
        # Yaw (0-15)
        yaw_bin = int(remaining % yaw_bins)
        remaining //= yaw_bins
        
        # Pitch (0-8)
        pitch_bin = int(remaining % pitch_bins)
        
        # Convert bins to angles - ensure float
        yaw = float((yaw_bin / yaw_bins) * 45.0 - 22.5)
        pitch = float((pitch_bin / pitch_bins) * 45.0 - 22.5)
        
        return {
            "movement": movement,
            "jump": jump,
            "sneak": False,
            "sprint": False,
            "attack": attack,
            "useItem": False,
            "hotbar": -1,
            "yaw": yaw,
            "pitch": pitch
        }

    def predict_action(self, observation: Dict, action_space: Dict, cached_vector: np.ndarray = None) -> Dict:
        """Fast prediction - optimized for speed. Can use cached observation vector."""
        if cached_vector is not None:
            obs_vector = cached_vector
        else:
            obs_vector = self._observation_to_vector_fast(observation, action_space)
        
        action_idx, _ = self.policy.get_action(obs_vector, deterministic=False)
        action = self._action_idx_to_dict_fast(action_idx, action_space)
        
        # Store for training - ensure we have matching observations, actions, and rewards
        self.observations.append(obs_vector)
        self.actions.append(action_idx)
        # Add default reward of 0.0 - will be updated when events occur
        self.rewards.append(0.0)
        
        return action

    def add_reward(self, bot_name: str, current_state: Dict, events: List[Dict]):
        """
        Add reward for training - updates the last reward entry.
        Handles all event types that the mod might send:
        - damage_dealt: Positive reward for dealing damage
        - damage_taken: Negative reward for taking damage
        - good_aim: Reward for aiming at enemies (percentage-based)
        - won_duel: Large reward for winning
        - death: Penalty for dying
        - proximity: Reward for being close to enemies (auto-calculated)
        - survival: Small constant reward for staying alive (auto-calculated)
        """
        total_reward = 0.0
        for event in events:
            event_type = event.get('type', '')
            if event_type == 'damage_dealt':
                # Reward for dealing damage
                # If damage_percentage is provided, use it for percentage-based reward
                # Otherwise use raw damage amount
                if 'damage_percentage' in event:
                    # Percentage-based: damage_percentage * 10.0 (so 100% damage = 10.0 reward)
                    total_reward += event.get('damage_percentage', 0) * 10.0
                else:
                    # Fallback to raw damage amount
                    total_reward += event.get('amount', 0) * 1.0
            elif event_type == 'damage_taken':
                # Penalty for taking damage - amount is damage taken
                total_reward -= event.get('amount', 0) * 0.5  # Less penalty than damage dealt reward
            elif event_type == 'good_aim':
                # Use the amount directly (percentage-based, 0.0 to 1.0)
                # If mod sends without amount, use default 0.1
                total_reward += event.get('amount', 0.1)
            elif event_type == 'proximity':
                # Auto-calculated reward for being close to enemies
                total_reward += event.get('amount', 0)
            elif event_type == 'survival':
                # Auto-calculated small constant reward
                total_reward += event.get('amount', 0)
            elif event_type == 'yaw_exploration':
                # Reward for exploring different yaw angles (between -30 and -150)
                total_reward += event.get('amount', 0)
            elif event_type == 'won_duel':
                # Large reward for winning a duel
                total_reward += 10.0
            elif event_type == 'death':
                # Penalty for dying
                total_reward -= 1.0
        
        # Update the last reward entry (which was set to 0.0 in predict_action)
        # If rewards list is empty, append (shouldn't happen, but safety check)
        if len(self.rewards) > 0:
            self.rewards[-1] += total_reward
        else:
            self.rewards.append(total_reward)
        
        self.bot_scores[bot_name] = self.bot_scores.get(bot_name, 0.0) + total_reward

    def add_done(self, done: bool):
        """Mark episode as done"""
        self.dones.append(done)

    def train(self, batch_size: int = 64, epochs: int = 1) -> Dict:
        """Simple policy gradient training"""
        if len(self.observations) < batch_size:
            return {"status": "insufficient_data", "buffer_size": len(self.observations)}
        
        # Ensure all buffers have the same length
        min_len = min(len(self.observations), len(self.actions), len(self.rewards))
        if min_len < len(self.observations):
            # Trim to match - this shouldn't happen if code is correct, but safety check
            self.observations = self.observations[:min_len]
            self.actions = self.actions[:min_len]
            self.rewards = self.rewards[:min_len]
        
        obs_tensor = torch.FloatTensor(np.array(self.observations)).to(self.device)
        actions_tensor = torch.LongTensor(self.actions).to(self.device)
        rewards_tensor = torch.FloatTensor(self.rewards).to(self.device)
        
        # Verify tensor sizes match
        if len(obs_tensor) != len(rewards_tensor) or len(actions_tensor) != len(rewards_tensor):
            return {
                "status": "error",
                "message": f"Buffer size mismatch: obs={len(obs_tensor)}, actions={len(actions_tensor)}, rewards={len(rewards_tensor)}"
            }
        
        # Policy gradient with reward normalization and entropy bonus
        self.optimizer.zero_grad()
        action_logits = self.policy(obs_tensor)
        action_probs = torch.nn.functional.softmax(action_logits, dim=-1)
        action_dist = torch.distributions.Categorical(action_probs)
        
        log_probs = action_dist.log_prob(actions_tensor)
        
        # Normalize rewards (subtract mean) to reduce variance and improve learning
        # This centers rewards around 0, which helps policy gradient
        rewards_mean = rewards_tensor.mean()
        rewards_normalized = rewards_tensor - rewards_mean
        
        # Policy gradient loss: maximize log_prob * reward
        policy_loss = -(log_probs * rewards_normalized).mean()
        
        # Add entropy bonus to encourage exploration (prevent getting stuck)
        entropy = action_dist.entropy().mean()
        entropy_bonus = 0.01  # Small bonus to encourage exploration
        entropy_loss = -entropy_bonus * entropy
        
        # Total loss
        loss = policy_loss + entropy_loss
        
        loss.backward()
        
        # Clip gradients to prevent exploding gradients
        torch.nn.utils.clip_grad_norm_(self.policy.parameters(), max_norm=1.0)
        
        self.optimizer.step()
        
        self.last_loss = loss.item()
        self.last_score = rewards_tensor.sum().item()
        
        # Log additional info for debugging
        print(f"Training stats: loss={loss.item():.6f}, policy_loss={policy_loss.item():.6f}, "
              f"entropy={entropy.item():.4f}, reward_mean={rewards_mean.item():.4f}, "
              f"reward_std={rewards_tensor.std().item():.4f}, "
              f"min_reward={rewards_tensor.min().item():.4f}, max_reward={rewards_tensor.max().item():.4f}")
        
        # Clear buffers
        self.observations.clear()
        self.actions.clear()
        self.rewards.clear()
        self.dones.clear()
        
        return {
            "status": "success",
            "loss": self.last_loss,
            "policy_loss": policy_loss.item(),
            "entropy": entropy.item(),
            "reward_mean": rewards_mean.item(),
            "reward_std": rewards_tensor.std().item(),
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
