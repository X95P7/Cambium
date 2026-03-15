# MICS 2026 Paper Outline and Timeline

## Paper Thesis

Training reinforcement learning agents in complex 3D environments like Minecraft PvP exposes a set of interconnected design decisions -- action space structure, episode management, reward engineering, and training infrastructure -- that each independently determine whether an agent learns at all. This paper investigates these decisions through the lens of building and iterating on a multi-agent PvP combat training system, providing practical guidance for RL practitioners facing high-dimensional, real-time environments.

---

## Paper Structure (Target: 6-8 pages, ACM or IEEE format)

### 1. Introduction (~0.75 pages)

- Reinforcement learning has been applied to increasingly complex game environments, from Atari (DQN) to StarCraft (AlphaStar) to Minecraft (MineRL). These works demonstrate that RL can work in rich environments, but they also rely on significant, purpose-built infrastructure and carefully designed training pipelines. This paper explores what that infrastructure and design work actually looks like in practice.
- Specifically, we investigate the challenges of training RL agents for Minecraft PvP combat -- a task that requires real-time coordination of movement, camera control, and combat actions against a moving opponent. We focus not on achieving state-of-the-art performance, but on documenting the design decisions that determine whether an agent learns anything at all.
- Existing Minecraft RL frameworks (MineRL, Project Malmo) target navigation and resource-gathering tasks and are constrained by deprecated dependencies, version locking, and no support for custom multi-agent PvP. Building our own training pipeline revealed a set of practical lessons about action space design, episode structure, reward engineering, and environment control.
- This paper contributes:
  1. A modular, containerized training infrastructure for headless multi-agent Minecraft PvP
  2. An investigation of four design axes and how each affects whether learning occurs
  3. Practical observations from training 8 simultaneous agents on HPC hardware

### 2. Background and Related Work (~1 page)

- **RL fundamentals**: MDP, policy gradient, PPO (brief -- audience is CS students)
- **Game AI**: Reference AlphaStar, OpenAI Five, and MineRL as examples of RL applied to complex games. Note the scale of infrastructure they required -- this paper operates at a much smaller scale but encounters many of the same categories of design problems (action space representation, episode design, reward density).
- **Minecraft RL**: MineRL competition (navigation/mining tasks, not PvP), Project Malmo (deprecated), Craftassist. Discuss their limitations for our use case: no multi-agent combat support, version-locked to old Minecraft builds, no headless client support. We are not claiming to improve on these -- they solve different problems. We needed to build new infrastructure because our task (PvP combat) falls outside their scope.
- **Action space design**: Cite factored/multi-discrete approaches (Tavakoli et al. 2018, Pierrot et al. 2021) vs flat categorical. Briefly explain the combinatorial explosion problem.

### 3. System Architecture (~1.5 pages)

- **Overview diagram** (figure): Minecraft Forge Server <-> N Headless Clients <-> FastAPI Backend (RL Agent + RCON)
- **Minecraft Forge Server**: 1.8.9, custom world with arena spawns, RCON for programmatic control
- **Headless Clients**: HeadlessMC + custom Forge mod (CambiumMod) that:
  - Extracts observation vectors (player state, entity positions, health, armor)
  - Sends observations to backend API every 3 game ticks
  - Applies returned actions (movement, camera, attack)
  - Reports reward events (damage dealt/taken, kills)
- **FastAPI Backend**: Receives observations, runs RL inference, returns actions, manages episodes via RCON
- **Containerization**: Docker Compose locally, adapted to Singularity + SLURM for HPC (discuss the challenges: no Docker daemon, fakeroot restrictions, PTY handling for interactive game clients)
- **Scaling**: 8 simultaneous bot clients, persistent RCON connection, asyncio coordination

### 4. Design Axis 1: Action Space Structure (~1 page)

*Your action space matters: why*

**Literature grounding**: Tavakoli et al. (2018) formalized the combinatorial explosion problem for discrete action spaces and proposed branching architectures that scale linearly with action dimensions instead of multiplicatively. Pierrot et al. (2021) extended this analysis to PPO and SAC. OpenAI Five (Berner et al. 2019) used a factored multi-discrete action space in practice for Dota 2, with separate softmax heads for target selection, spatial offsets, and movement.

- **The problem**: PvP combat requires simultaneous control of movement (8 directions + idle), jumping, attacking, and camera (yaw bins x pitch bins). A flat categorical policy requires 9 x 2 x 2 x 9 x 5 = 1,620+ combinations. With sprint/sneak/hotbar this grows to 4,608.
- **Factored multi-discrete approach**: Independent output heads per dimension sharing a common trunk. Movement head (9 outputs), jump head (2), attack head (2), yaw head (9), pitch head (5) = 27 total outputs. The shared trunk (as advocated by Tavakoli et al.) implicitly learns correlations between dimensions without requiring explicit joint modeling.
- **Why it matters**:
  - Exploration efficiency: random sampling from 27 independent dimensions covers the space far more uniformly than sampling from 1,620 flat categories where most combinations go unvisited during early training.
  - Gradient signal: each head receives direct gradient feedback. The movement head can improve independently of camera control without waiting for a useful joint action to be sampled.
  - Computational cost: forward pass produces 5 small softmax vectors, not one massive one.
- **Trade-off**: assumes conditional independence between action dimensions (a simplification -- in reality, attacking while moving forward is more useful than attacking while retreating). This is the same trade-off made by OpenAI Five and acknowledged by Pierrot et al. In practice, the shared trunk and reward shaping compensate.

**Cite**: Tavakoli et al. 2018 (AAAI), Pierrot et al. 2021, Berner et al. 2019 (OpenAI Five)

### 5. Design Axis 2: Episode Structure (~1 page)

*Episodes are good and why*

**Literature grounding**: Episode structure determines the credit assignment horizon. Schulman et al. (2016) showed via Generalized Advantage Estimation (GAE) that the discount factor attenuates reward signal over long horizons, making it harder for early actions to receive meaningful gradient updates. Recent work on adaptive episode length in multi-agent RL (2025) demonstrates that shorter episodes in early training give faster feedback loops and more diverse starting states. The principle also connects to curriculum learning (Bengio et al. 2009): starting with simpler, bounded tasks before increasing complexity.

- **The problem**: Without explicit episodes, the agent experiences a continuous stream of states with sparse rewards. A PvP duel can last indefinitely if neither bot lands hits. Empirically, early random-policy agents produced 10-15 minute "duels" with zero learning signal -- the discount factor effectively zeroed out any eventual reward.
- **Episode design decisions**:
  - **Fixed time cap** (15 seconds): Bounds the credit assignment horizon. Forces the agent to act within a window where the discount factor still propagates meaningful signal to early actions.
  - **Passive play penalty**: Bots that deal no damage during an episode receive a negative reward (-0.5). This breaks the degenerate Nash equilibrium where "do nothing" is the lowest-risk strategy for both agents.
  - **Paired resets**: Both bots in a duel reset simultaneously with fresh health, equipment, and positions. Ensures symmetric experience and prevents state drift (one bot permanently weakened).
  - **Episode-end backpropagation trigger**: Training aligns with complete behavioral sequences rather than arbitrary tick counts, giving cleaner advantage estimates.
- **Key observation**: The 15-second cap was chosen empirically. Too short and the agent cannot complete a meaningful engagement. Too long and the discount factor washes out the signal. This mirrors the adaptive episode length finding in recent literature.

**Cite**: Schulman et al. 2016 (GAE), Schulman et al. 2017 (PPO), Bengio et al. 2009 (Curriculum Learning)

### 6. Design Axis 3: Reward Engineering (~1 page)

*What you reward is what you get*

**Literature grounding**: Ng, Harada, and Russell (1999) proved that potential-based reward shaping preserves the optimal policy, providing a theoretically sound framework for densifying sparse rewards. However, most practical RL applications (including this work) use heuristic shaping that does NOT satisfy potential-based constraints, meaning the shaped reward can change the optimal policy. This is a deliberate trade-off: we accept the risk of shaping bias in exchange for any learning signal at all in a setting where sparse rewards produce no learning.

Randlov and Alstrom (1998) demonstrated a classic failure of naive reward shaping: a bicycle agent trained with proximity-to-goal rewards learned to ride in circles, collecting shaping rewards without reaching the goal. We observed an analogous failure in early experiments.

- **Sparse vs dense**: Rewarding only kills/deaths (sparse terminal rewards) produced zero learning in our setting. The agent needs dense per-tick guidance to discover that approaching enemies and aiming at them leads to damage events.
- **Reward components** (table):

| Reward Type | Value | Frequency | Purpose |
|---|---|---|---|
| Damage dealt | +1.0 | Per hit | Primary objective signal |
| Damage taken | -0.1 | Per hit | Mild discouragement |
| Proximity | +0.01 | Per tick (within 3 blocks) | Encourages engagement |
| Aim accuracy | +0.03 | Per tick (on target) | Encourages tracking |
| Aim hold | +0.05 | Per tick (aimed + level pitch) | Rewards sustained aim |
| Pitch control | +0.02 | Per tick (scaling) | Prevents sky-staring |
| Extreme pitch | -0.03 | Per tick (\|pitch\| > 60) | Penalizes extreme angles |
| Won duel | +15.0 | Per episode (terminal) | Victory reward |
| Death | -2.0 | Per episode (terminal) | Defeat penalty |
| Episode timeout | -1.0 | Per episode (terminal) | Penalize stalling |
| No-damage penalty | -0.5 | Per episode (terminal) | Anti-passivity |

- **Key insight -- the Randlov problem**: Early iterations had proximity reward at +0.1 per tick. Over a 15-second episode (~100 ticks), an agent could accumulate +10.0 just by walking toward the enemy without attacking -- more than the death penalty. Agents learned to approach but never attack. Reducing proximity to +0.01 (total ~1.0 per episode) while keeping damage at +1.0 per hit restored the intended reward hierarchy.
- **Honest limitation**: This shaping is heuristic and not potential-based. The shaped optimal policy may differ from the true optimal policy. We accept this because the alternative (sparse rewards) produces no learning at all in the available training time.

**Cite**: Ng, Harada, Russell 1999 (ICML), Randlov and Alstrom 1998

### 7. Design Axis 4: Environment Control (~1 page)

*Your environment matters: why*

**Literature grounding**: Domain simplification is a form of curriculum learning (Bengio et al. 2009) applied to the environment itself rather than the task. By reducing the environment to its essential components, we reduce confounding variables that obscure the learning signal. This is analogous to the controlled experiment principle in science: vary one thing at a time. In the sim-to-real transfer literature, environment fidelity and controlled training conditions are recognized as critical factors that determine whether policies transfer at all.

- **Arena design**: Controlled flat arenas with fixed spawn points and walls. Eliminates terrain navigation, falling damage, and pathfinding as confounding variables. The agent's only task is combat -- movement, aiming, and attacking. Adding environmental complexity is future work (curriculum progression), not a starting point.
- **Kit standardization**: Both bots receive identical iron armor + iron sword + saturation effect (infinite food). Removes equipment variance, hunger mechanics, and durability concerns from the learning signal. The agent doesn't need to learn inventory management to learn combat.
- **Observation filtering**: Only the paired opponent appears in the observation vector, not spectators, other bot pairs, or item entities. This gives the model a deterministic input layout where slot 0 is always "the enemy." Without this, the agent must first learn which entity to attend to before learning how to fight it.
- **Symmetric resets**: Both bots start each episode at full health, identical equipment, at known positions in a known arena. This ensures the value function starts from a consistent baseline rather than an arbitrary mid-game state.
- **Infrastructure as environment**: The backend (RCON commands) acts as the equivalent of `gym.reset()` and `gym.step()` for Minecraft. The reliability of this interface directly affects training quality -- infrastructure bugs (RCON timeouts, race conditions in pairing) caused silent training corruption that was only detected through degraded metrics, not explicit errors.

**Cite**: Bengio et al. 2009 (Curriculum Learning)

### 8. Preliminary Results (~0.75 pages)

- Training configuration: 8 bots (4 pairs), T4 GPU, PPO with factored policy, 15-second episodes
- Metrics to present (collect over next 2-3 days of training):
  - TPS (ticks per second) over time -- shows system stability
  - Reward progression over training intervals -- shows learning signal
  - Reward type breakdown -- shows which behaviors are being reinforced
  - Episode outcomes (kills vs timeouts) over time
  - Qualitative observations: did agents learn to approach enemies? To attack? To track?
- Be honest about limitations: 5 days of training is preliminary. The contribution is the infrastructure and design investigation, not state-of-the-art combat.

### 9. Discussion and Future Work (~0.5 pages)

- **What worked**: Factored action space enabled exploration; episode timeouts prevented degenerate equilibria; dense reward shaping provided learning signal.
- **What remains challenging**: Camera control is the hardest dimension to learn (continuous discretized into bins loses precision); agents still struggle with timing attacks during movement.
- **Future work**: Curriculum learning (start with 1v1 stationary targets, progress to moving opponents), self-play with ELO rating, transfer from HPC training to local evaluation, exploring continuous action spaces for camera control.

### 10. Conclusion (~0.25 pages)

- Reinforcement learning in complex 3D environments is feasible but requires careful co-design of action spaces, episode structure, reward functions, and infrastructure.
- The "ML" part (choosing PPO, tuning hyperparameters) was a small fraction of the overall effort. The majority of the work was engineering the environment interface and designing the training loop -- a reality that is underrepresented in RL literature.
- The infrastructure and design patterns described here are not specific to Minecraft and apply to any RL application facing high-dimensional action spaces in real-time environments.

---

## Figures and Tables Plan

1. **System architecture diagram** (Section 3) -- show Docker/Singularity containers, data flow
2. **Action space comparison diagram** (Section 4) -- flat 1,620 outputs vs factored 27 outputs
3. **Reward progression chart** (Section 8) -- total reward over training intervals
4. **Episode outcome chart** (Section 8) -- kills vs timeouts over time
5. **Reward type breakdown table** (Section 6) -- the reward components table
6. **TPS/throughput chart** (Section 8) -- system performance

---

## Key References

1. **Tavakoli, Pardo, Kormushev (2018)** "Action Branching Architectures for Deep Reinforcement Learning." AAAI 2018.
2. **Pierrot et al. (2021)** "Factored Action Spaces in Deep Reinforcement Learning." OpenReview.
3. **Berner et al. (2019)** "Dota 2 with Large Scale Deep Reinforcement Learning." arXiv:1912.06680.
4. **Schulman et al. (2017)** "Proximal Policy Optimization Algorithms." arXiv:1707.06347.
5. **Schulman et al. (2016)** "High-Dimensional Continuous Control Using Generalized Advantage Estimation." ICLR 2016.
6. **Ng, Harada, Russell (1999)** "Policy Invariance Under Reward Transformations: Theory and Application to Reward Shaping." ICML 1999.
7. **Randlov, Alstrom (1998)** "Learning to Drive a Bicycle Using Reinforcement Learning and Shaping." ICML 1998.
8. **Bengio et al. (2009)** "Curriculum Learning." ICML 2009.
9. **Vinyals et al. (2019)** "Grandmaster Level in StarCraft II Using Multi-agent Reinforcement Learning." Nature.
10. **Guss et al. (2019)** "MineRL: A Large-Scale Dataset of Minecraft Demonstrations." IJCAI 2019.
11. **Mnih et al. (2015)** "Human-Level Control Through Deep Reinforcement Learning." Nature.

---

## Revised Abstract (Draft)

Applying reinforcement learning to complex 3D game environments involves design challenges that extend beyond model architecture selection. This paper investigates four design axes -- action space structure, episode management, reward engineering, and training infrastructure -- through the development of a multi-agent Minecraft player-versus-player combat training system. We describe how a factored multi-discrete policy architecture, which decomposes simultaneous control of movement, camera, and combat actions into independent output heads, reduces the exploration problem from thousands of action combinations to a manageable set of independent dimensions. We discuss how bounded episode structure with timeout penalties helps prevent degenerate agent behaviors such as passivity, and how dense reward shaping provides the learning signal that sparse terminal rewards alone cannot. We also describe the training infrastructure we built: a containerized, headless, multi-agent Minecraft environment that addresses limitations of existing frameworks for PvP scenarios and scales to eight simultaneous agents on HPC hardware. Our findings offer practical observations for reinforcement learning practitioners working with high-dimensional, real-time environments where engineering the training loop is as important as choosing the learning algorithm.

---

## 5-Day Timeline

### Day 1 (Saturday March 15): Foundation

- **Morning**: Write Sections 1 (Introduction) and 2 (Background/Related Work)
- **Afternoon**: Write Section 3 (System Architecture), create architecture diagram
- **Evening**: Start a long training run (leave running overnight) to collect results data
- **Deliverable**: ~3 pages drafted, training job running

### Day 2 (Sunday March 16): Core Technical Sections

- **Morning**: Write Section 4 (Action Space) and Section 5 (Episode Structure)
- **Afternoon**: Write Section 6 (Reward Engineering) and Section 7 (Environment/Infrastructure)
- **Evening**: Check training run, collect intermediate metrics, create reward table
- **Deliverable**: ~6-7 pages drafted (all technical sections complete)

### Day 3 (Monday March 17): Results and Figures

- **Morning**: Pull training data, create charts (reward progression, episode outcomes, TPS)
- **Afternoon**: Write Section 8 (Preliminary Results) using actual data
- **Evening**: Write Section 9 (Discussion/Future Work) and Section 10 (Conclusion)
- **Deliverable**: Full first draft complete, figures created

### Day 4 (Tuesday March 18): Revision

- **Morning**: Revise abstract to match the actual paper content
- **Afternoon**: Full read-through for flow, clarity, and consistency. Cut to page limit if needed.
- **Evening**: Have someone else read it (advisor, classmate). Fix formatting (ACM/IEEE template).
- **Deliverable**: Polished second draft

### Day 5 (Wednesday March 19): Final Polish and Submit

- **Morning**: Address any feedback from readers
- **Afternoon**: Final formatting pass, check references, verify figures render correctly
- **Evening**: Submit
- **Deliverable**: Submitted paper
