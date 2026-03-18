# Cambium Techniques & Assumptions Validation

This document breaks down the core techniques, models, and assumptions used to engineer the Cambium RL PvP environment, referencing industry precedents to validate the system design choices.

## 1. Action Space Structure: Factored Multi-Discrete Policy
**Assumption**: A flat categorical action space for multi-dimensional simultaneous outputs (like Minecraft) is sample-inefficient and fails to explore effectively.
**Technique**: Implement a factored multi-discrete policy, utilizing a shared feature extraction trunk that branches into completely independent softmax output heads for each action dimension (movement, jump, attack, yaw, pitch).
**Validation**:
- **Why it works**: A flat policy for Minecraft combat logic results in ~4,600+ unique categorical bins. In early training, a model samples uniformly. With a flat policy, the "jump-forward-attack" bin would be explored extremely rarely. By separating into independent heads, the model samples probabilities per dimension. 
- **Literature**: Tavakoli et al. (2018) proved that action branching scales linearly with action dimensions instead of multiplicatively. Pierrot et al. (2021) expanded on this by proving that PPO combined with a factored policy significantly improves sample complexity in continuous/discrete hybrid domains. OpenAI Five (Berner et al., 2019) utilized the exact same shared-trunk branching architecture for Dota 2.

## 2. Episode Management: Bounded Timeouts
**Assumption**: Continuous infinite environments with sparse rewards prevent successful credit assignment.
**Technique**: Implement rigid 15-second episodes (`MAX_EPISODE_LENGTH_SEC`). If no agent dies within 15 seconds, penalize passivity with a negative reward (`episode_timeout`), instantly reset both agents, and trigger backpropagation.
**Validation**:
- **Why it works**: Without episode limits, a duel without hits could theoretically last indefinitely, rendering the eventual terminal reward fully attenuated by the temporal discount factor ($\gamma = 0.99$). 
- **Literature**: As demonstrated by Schulman et al. (2016) in their work on Generalized Advantage Estimation (GAE), standard policy gradients fail if credit assignment horizons are too long. Adaptive episode limiting acts as a temporal curriculum constraint (Bengio et al., 2009).

## 3. Reward Engineering: Dense Heuristic Shaping
**Assumption**: A sparse terminal reward (`+10` for winning, `-1` for dying) combined with large action spaces yields no meaningful gradient signal in early random-exploration phases.
**Technique**: Implement dense heuristic reward shaping. Provide positive feedback on a granular per-tick level (`aim_hold`, `good_aim`, `pitch_control`, `proximity`) and direct reward scaling for `damage_dealt`.
**Validation**:
- **Why it works**: In early training, the probability of an agent perfectly stringing together movement, camera targeting, and attacking to kill an evasive opponent is virtually zero. Dense shaping gives the gradient a local slope to climb immediately.
- **The Randlov Pitfall**: Randlov & Alstrom (1998) detailed the classic bicycle problem where agents exploit shaping rewards without achieving the terminal goal. Early versions of Cambium saw agents walking up to enemies and standing still to farm the `proximity` reward. This was validated by actively deprecating the `proximity` weight to `+0.01` while scaling `damage_dealt` up to `+10.0`, proving that peak task-orientated outcomes must outweigh the sum of the shaping metrics.
- **Literature**: Ng, Harada, and Russell (1999) formally investigated reward shaping and proved that improperly scaled shaping risks altering the optimal policy path. While heuristic shaping introduces bias, it is an accepted and virtually required paradigm for complex real-time RL applications.

## 4. Environment Simplification: Predefined Symmetry
**Assumption**: A highly variable environment introduces confounding factors that obscure the RL objective function.
**Technique**: Force deterministic setups. Create flat enclosed arenas devoid of terrain blocks. Ensure both bots spawn with symmetric `iron_armor` and `iron_sword` loadouts alongside infinite saturation.
**Validation**:
- **Why it works**: Pathfinding and inventory management are distinct RL challenges. Attempting to train an agent to simultaneously pathfind around obstacles while learning PvP combat distributes the learning scope across too many dimensions. 
- **Literature**: Standard Sim-to-Real principles validate this. Start with heavily simplified and deterministic mechanics and progressively complexify them over time via Curriculum Learning (Bengio et al., 2009).

## 5. Model Inference: Low-Latency Constraints
**Assumption**: Real-time multi-agent gaming necessitates highly optimized neural network forward passes to prevent lag spikes and tick dropping over Minecraft servers.
**Technique**: Utilize a heavily optimized 2-Layer MLP (Hidden dimension: 256) running completely on raw NumPy vectorization on the CPU.
**Validation**:
- **Why it works**: Because each agent submits state vectors entirely asynchronously, batching parallel inputs across the PyTorch GPU yields minimal benefits during active inference. Pre-allocating the CPU overhead to compute sub-50ms predictions ensures no timeouts against the 20 Hz (50ms tick rate) limitations imposed by Minecraft's internal loop. The GPU (T4) is reserved explicitly for large-batch backpropagation processes spanning all 8 agents concurrently.
