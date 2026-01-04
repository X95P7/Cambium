"""
PPO (Proximal Policy Optimization) Model for Minecraft PvP
Implements actor-critic architecture for reinforcement learning
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Tuple, Optional
import json

class ActorCritic(nn.Module):
    """
    Actor-Critic network for PPO.
    Actor outputs action probabilities, Critic outputs value estimates.
    """
    
    def __init__(self, observation_dim: int, action_dim: int, hidden_dims: List[int] = [256, 256]):
        super(ActorCritic, self).__init__()
        
        self.observation_dim = observation_dim
        self.action_dim = action_dim
        
        # Shared feature extractor
        layers = []
        input_dim = observation_dim
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(input_dim, hidden_dim))
            layers.append(nn.ReLU())
            input_dim = hidden_dim
        
        self.shared = nn.Sequential(*layers)
        
        # Actor head (policy network)
        self.actor = nn.Sequential(
            nn.Linear(input_dim, hidden_dims[-1]),
            nn.ReLU(),
            nn.Linear(hidden_dims[-1], action_dim)
        )
        
        # Critic head (value network)
        self.critic = nn.Sequential(
            nn.Linear(input_dim, hidden_dims[-1]),
            nn.ReLU(),
            nn.Linear(hidden_dims[-1], 1)
        )
        
        # Initialize weights
        self.apply(self._init_weights)
    
    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            torch.nn.init.orthogonal_(m.weight, gain=np.sqrt(2))
            m.bias.data.fill_(0.0)
    
    def forward(self, observations: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass through the network.
        
        Args:
            observations: Tensor of shape (batch_size, observation_dim)
        
        Returns:
            action_logits: Logits for action distribution
            value: Value estimate
        """
        features = self.shared(observations)
        action_logits = self.actor(features)
        value = self.critic(features)
        return action_logits, value
    
    def get_action(self, observation: np.ndarray, deterministic: bool = False) -> Tuple[int, float]:
        """
        Sample an action from the policy.
        
        Args:
            observation: Single observation array
            deterministic: If True, return most likely action; if False, sample
        
        Returns:
            action: Selected action index
            log_prob: Log probability of the action
        """
        with torch.no_grad():
            observation_tensor = torch.FloatTensor(observation).unsqueeze(0)
            action_logits, _ = self.forward(observation_tensor)
            action_probs = F.softmax(action_logits, dim=-1)
            
            if deterministic:
                action = torch.argmax(action_probs, dim=-1).item()
                log_prob = F.log_softmax(action_logits, dim=-1)[0, action].item()
            else:
                action_dist = torch.distributions.Categorical(action_probs)
                action = action_dist.sample().item()
                log_prob = action_dist.log_prob(torch.tensor(action)).item()
            
            return action, log_prob
    
    def evaluate_actions(self, observations: torch.Tensor, actions: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Evaluate actions for given observations.
        
        Args:
            observations: Tensor of shape (batch_size, observation_dim)
            actions: Tensor of action indices, shape (batch_size,)
        
        Returns:
            log_probs: Log probabilities of actions
            values: Value estimates
            entropy: Entropy of action distribution
        """
        action_logits, values = self.forward(observations)
        action_probs = F.softmax(action_logits, dim=-1)
        action_dist = torch.distributions.Categorical(action_probs)
        
        log_probs = action_dist.log_prob(actions)
        entropy = action_dist.entropy()
        
        return log_probs, values.squeeze(), entropy


class RewardCalculator:
    """
    Calculates rewards based on game events.
    Reward types:
    - Positive: good_aim, doing_damage, winning
    - Negative: taking_damage
    """
    
    def __init__(self):
        self.reward_weights = {
            'good_aim': 0.1,      # Reward for aiming at enemies
            'doing_damage': 1.0,  # Reward for dealing damage
            'winning': 10.0,      # Reward for winning a duel
            'taking_damage': -0.5 # Penalty for taking damage
        }
        
        # Track previous state for delta calculations
        self.previous_states = {}  # bot_name -> previous_state
    
    def calculate_reward(self, bot_name: str, current_state: Dict, events: List[Dict]) -> float:
        """
        Calculate reward for a bot based on current state and events.
        
        Args:
            bot_name: Name of the bot
            current_state: Current game state (health, position, etc.)
            events: List of events that occurred (damage dealt, damage taken, etc.)
        
        Returns:
            Total reward for this step
        """
        total_reward = 0.0
        prev_state = self.previous_states.get(bot_name, {})
        
        # Process events
        for event in events:
            event_type = event.get('type', '')
            
            if event_type == 'damage_dealt':
                # Positive reward for dealing damage
                damage = event.get('amount', 0)
                total_reward += self.reward_weights['doing_damage'] * damage
                
            elif event_type == 'damage_taken':
                # Negative reward for taking damage
                damage = event.get('amount', 0)
                total_reward += self.reward_weights['taking_damage'] * damage
                
            elif event_type == 'good_aim':
                # Positive reward for good aim (aiming at enemy)
                total_reward += self.reward_weights['good_aim']
                
            elif event_type == 'won_duel':
                # Large positive reward for winning
                total_reward += self.reward_weights['winning']
        
        # Calculate aim reward based on looking at enemies
        if 'entities' in current_state:
            entities = current_state['entities']
            player_yaw = current_state.get('player', {}).get('yaw', 0)
            player_pitch = current_state.get('player', {}).get('pitch', 0)
            
            # Check if player is looking at any enemy
            for entity in entities:
                if entity.get('isPlayer', False) and entity.get('health', 0) > 0:
                    # Calculate angle to entity
                    rel_x = entity.get('relativeX', 0)
                    rel_z = entity.get('relativeZ', 0)
                    
                    if abs(rel_x) < 2 and abs(rel_z) < 2:  # Close to enemy
                        # Check if looking in right direction (simplified)
                        target_yaw = np.arctan2(rel_x, rel_z) * 180 / np.pi
                        yaw_diff = abs(player_yaw - target_yaw)
                        if yaw_diff < 30 or yaw_diff > 330:  # Looking roughly at enemy
                            total_reward += self.reward_weights['good_aim'] * 0.1
        
        # Update previous state
        self.previous_states[bot_name] = current_state.copy()
        
        return total_reward


class PPOAgent:
    """
    PPO Agent that manages training and inference.
    """
    
    def __init__(
        self,
        observation_dim: int,
        action_dim: int,
        lr: float = 3e-4,
        gamma: float = 0.99,
        eps_clip: float = 0.2,
        value_coef: float = 0.5,
        entropy_coef: float = 0.01,
        max_grad_norm: float = 0.5,
        device: str = 'cpu'
    ):
        self.observation_dim = observation_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.eps_clip = eps_clip
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.max_grad_norm = max_grad_norm
        self.device = device
        
        # Create network
        self.network = ActorCritic(observation_dim, action_dim).to(device)
        self.optimizer = optim.Adam(self.network.parameters(), lr=lr)
        
        # Reward calculator
        self.reward_calculator = RewardCalculator()
        
        # Training buffers
        self.observations = []
        self.actions = []
        self.rewards = []
        self.log_probs = []
        self.values = []
        self.dones = []
    
    def predict_action(self, observation: Dict, action_space: Dict) -> Dict:
        """
        Predict an action given an observation.
        
        Args:
            observation: Observation dictionary from the game
            action_space: Action space configuration
        
        Returns:
            Action dictionary with movement, jump, attack, etc.
        """
        # Convert observation to tensor
        obs_vector = self._observation_to_vector(observation, action_space)
        
        # Get action from network
        action_idx, log_prob = self.network.get_action(obs_vector, deterministic=False)
        
        # Convert action index to action dictionary
        action = self._action_idx_to_dict(action_idx, action_space)
        
        # Store for training
        self.observations.append(obs_vector)
        self.actions.append(action_idx)
        self.log_probs.append(log_prob)
        
        # Get value estimate
        with torch.no_grad():
            obs_tensor = torch.FloatTensor(obs_vector).unsqueeze(0).to(self.device)
            _, value = self.network(obs_tensor)
            self.values.append(value.item())
        
        return action
    
    def add_reward(self, bot_name: str, current_state: Dict, events: List[Dict]):
        """
        Add reward for the last action.
        
        Args:
            bot_name: Name of the bot
            current_state: Current game state
            events: List of events that occurred
        """
        reward = self.reward_calculator.calculate_reward(bot_name, current_state, events)
        self.rewards.append(reward)
    
    def add_done(self, done: bool):
        """Mark if episode is done."""
        self.dones.append(done)
    
    def train(self, batch_size: int = 64, epochs: int = 4) -> Dict:
        """
        Train the PPO model on collected experience.
        
        Args:
            batch_size: Batch size for training
            epochs: Number of training epochs
        
        Returns:
            Training statistics
        """
        if len(self.observations) < batch_size:
            return {"status": "insufficient_data", "buffer_size": len(self.observations)}
        
        # Convert to tensors
        obs_tensor = torch.FloatTensor(np.array(self.observations)).to(self.device)
        actions_tensor = torch.LongTensor(self.actions).to(self.device)
        old_log_probs_tensor = torch.FloatTensor(self.log_probs).to(self.device)
        rewards_array = np.array(self.rewards)
        dones_array = np.array(self.dones)
        
        # Calculate returns (discounted rewards)
        returns = self._calculate_returns(rewards_array, dones_array)
        returns_tensor = torch.FloatTensor(returns).to(self.device)
        
        # Normalize returns
        returns_tensor = (returns_tensor - returns_tensor.mean()) / (returns_tensor.std() + 1e-8)
        
        # Get old values
        old_values_tensor = torch.FloatTensor(self.values).to(self.device)
        
        # Calculate advantages
        advantages = returns_tensor - old_values_tensor
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        total_loss = 0
        total_policy_loss = 0
        total_value_loss = 0
        total_entropy = 0
        
        # Training loop
        for epoch in range(epochs):
            # Shuffle data
            indices = torch.randperm(len(obs_tensor))
            
            for i in range(0, len(obs_tensor), batch_size):
                batch_indices = indices[i:i+batch_size]
                
                batch_obs = obs_tensor[batch_indices]
                batch_actions = actions_tensor[batch_indices]
                batch_old_log_probs = old_log_probs_tensor[batch_indices]
                batch_returns = returns_tensor[batch_indices]
                batch_advantages = advantages[batch_indices]
                
                # Forward pass
                log_probs, values, entropy = self.network.evaluate_actions(batch_obs, batch_actions)
                
                # Calculate ratios
                ratios = torch.exp(log_probs - batch_old_log_probs)
                
                # Policy loss (clipped)
                surr1 = ratios * batch_advantages
                surr2 = torch.clamp(ratios, 1 - self.eps_clip, 1 + self.eps_clip) * batch_advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # Value loss
                value_loss = F.mse_loss(values, batch_returns)
                
                # Entropy bonus
                entropy_loss = -entropy.mean()
                
                # Total loss
                loss = policy_loss + self.value_coef * value_loss + self.entropy_coef * entropy_loss
                
                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.network.parameters(), self.max_grad_norm)
                self.optimizer.step()
                
                total_loss += loss.item()
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.mean().item()
        
        # Clear buffers
        self.observations.clear()
        self.actions.clear()
        self.rewards.clear()
        self.log_probs.clear()
        self.values.clear()
        self.dones.clear()
        
        num_batches = (len(obs_tensor) // batch_size) * epochs
        
        return {
            "status": "success",
            "loss": total_loss / num_batches if num_batches > 0 else 0,
            "policy_loss": total_policy_loss / num_batches if num_batches > 0 else 0,
            "value_loss": total_value_loss / num_batches if num_batches > 0 else 0,
            "entropy": total_entropy / num_batches if num_batches > 0 else 0,
            "samples_trained": len(obs_tensor)
        }
    
    def _calculate_returns(self, rewards: np.ndarray, dones: np.ndarray) -> np.ndarray:
        """Calculate discounted returns."""
        returns = np.zeros_like(rewards)
        running_return = 0
        
        for i in reversed(range(len(rewards))):
            if dones[i]:
                running_return = 0
            running_return = rewards[i] + self.gamma * running_return
            returns[i] = running_return
        
        return returns
    
    def _observation_to_vector(self, observation: Dict, action_space: Dict) -> np.ndarray:
        """
        Convert observation dictionary to a vector.
        This is a simplified version - you may want to make this more sophisticated.
        """
        vector = []
        
        # Player data
        if 'player' in observation:
            player = observation['player']
            vector.extend([
                player.get('health', 0) / 20.0,  # Normalize health
                player.get('x', 0) / 100.0,      # Normalize position
                player.get('y', 0) / 100.0,
                player.get('z', 0) / 100.0,
                player.get('yaw', 0) / 180.0,   # Normalize rotation
                player.get('pitch', 0) / 90.0,
                player.get('armor', 0) / 20.0   # Normalize armor
            ])
        
        # Entities (limited to first 10)
        if 'entities' in observation:
            entities = observation['entities'][:10]
            for entity in entities:
                vector.extend([
                    1.0 if entity.get('isPlayer', False) else 0.0,
                    1.0 if entity.get('isProjectile', False) else 0.0,
                    entity.get('health', 0) / 20.0,
                    entity.get('relativeX', 0) / 10.0,
                    entity.get('relativeY', 0) / 10.0,
                    entity.get('relativeZ', 0) / 10.0
                ])
            # Pad if less than 10 entities
            while len(entities) < 10:
                vector.extend([0.0] * 6)
        
        # Blocks (limited to first 20)
        if 'blocks' in observation:
            blocks = observation['blocks'][:20]
            for block in blocks:
                vector.extend([
                    block.get('x', 0) / 20.0,
                    block.get('y', 0) / 20.0,
                    block.get('z', 0) / 20.0,
                    block.get('distance', 0) / 20.0,
                    1.0 if block.get('solid', False) else 0.0
                ])
            # Pad if less than 20 blocks
            while len(blocks) < 20:
                vector.extend([0.0] * 5)
        
        # Inventory (limited to first 9 hotbar slots)
        if 'inventory' in observation:
            inventory = observation['inventory'][:9]
            for inv in inventory:
                vector.extend([
                    inv.get('count', 0) / 64.0,
                    1.0 if inv.get('isWeapon', False) else 0.0,
                    inv.get('weaponDamage', 0) / 10.0
                ])
            # Pad if less than 9 slots
            while len(inventory) < 9:
                vector.extend([0.0] * 3)
        
        return np.array(vector, dtype=np.float32)
    
    def _action_idx_to_dict(self, action_idx: int, action_space: Dict) -> Dict:
        """
        Convert action index to action dictionary.
        This is a simplified version - you may want to make this more sophisticated.
        """
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
        
        # Simple action mapping - you may want to make this more sophisticated
        # For now, map action index to a combination of actions
        if action_space.get('enableMovement', True):
            movement_bins = action_space.get('movementBins', 8)
            if action_idx < movement_bins:
                action['movement'] = action_idx
                action_idx -= movement_bins
        
        if action_space.get('enableJump', True) and action_idx > 0:
            action['jump'] = (action_idx % 2 == 1)
            action_idx //= 2
        
        if action_space.get('enableAttack', True) and action_idx > 0:
            action['attack'] = (action_idx % 2 == 1)
        
        return action
    
    def save(self, path: str):
        """Save the model to disk."""
        torch.save({
            'network_state_dict': self.network.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'observation_dim': self.observation_dim,
            'action_dim': self.action_dim
        }, path)
    
    def load(self, path: str):
        """Load the model from disk."""
        checkpoint = torch.load(path, map_location=self.device)
        self.network.load_state_dict(checkpoint['network_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

