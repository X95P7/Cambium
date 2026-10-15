# Minecraft PvP RL Paper — Improvement Checklist

## The Four Axes (no changes needed)

### Axis 1: Action Space Structure
Decomposes the joint action space into five independent output heads (movement, jump, attack, yaw, pitch) rather than a single flat categorical distribution. This reduces the effective exploration dimensionality from ~1,620 combinations to 27 parameters, allowing the agent to discover useful sub-behaviors (e.g., good camera tracking) without needing to stumble onto the full correct action tuple by chance.

### Axis 2: Episode Structure
Caps each engagement at 15 seconds with a timeout penalty applied to both agents if neither dies. This prevents the passive Nash equilibrium where both agents learn to do nothing, and ensures the discount factor can propagate terminal reward signals back to early actions within a single rollout.

### Axis 3: Reward Engineering
Splits the reward signal into a sparse component (wins, kills, damage) and a dense heuristic component (proximity, aim-hold, pitch control). The sparse component provides ground truth objectives; the dense component provides tick-level scaffolding so the agent gets a gradient signal before it ever lands a hit. Reward magnitudes are calibrated so heuristic rewards cannot be farmed to outweigh combat rewards.

### Axis 4: Environment Control
Strips all non-combat Minecraft mechanics — flat arena, fixed equipment, no hunger, no item drops. Removes confounding variables from the observation space and policy, ensuring the agent's only task is combat. Intended as the starting point of a curriculum, not the final environment.

---

## Experiments to Run

- [ ] Re-run all 3 conditions (random, sparse, full model) with at least **3 random seeds each**
- [ ] Extend full model training to **10,000+ intervals** (20k if compute allows)
- [ ] Run the following **ablation conditions**, each with at least 2 seeds:
  - Full model **minus episode timeouts** (continuous horizon)
  - Full model **minus dense rewards** (sparse only, but with factored action space and bounded episodes)
  - Full model **with flat action space** instead of factored multi-discrete heads
- [ ] Confirm each ablation runs long enough to clearly succeed or fail

---

## Statistics to Report

- [ ] **Mean ± standard deviation** across seeds for all key metrics at convergence
- [ ] **Final-window stats** (last 10% of training): policy loss, value loss, entropy, episode reward
- [ ] **Sample efficiency**: steps to first successful kill per condition
- [ ] **Peak vs. plateau reward**: quantifies the reward ceiling problem already identified
- [ ] **Timeout rate over training**: percentage of episodes ending in timeout vs. kill — proves passivity was solved

---

## Graphs to Add

- [ ] **Learning curves with shaded std deviation bands** across seeds for episode reward — the single most important plot
- [ ] **Entropy over training** for all conditions on one graph — shows factored vs. flat policy diverging cleanly
- [ ] **Reward component breakdown over time** (proximity, aim-hold, damage dealt, wins) overlaid — extends what you already have and tells the curriculum story visually
- [ ] **Ablation comparison**: one curve per condition on a single episode reward plot — makes axis contributions visually undeniable
- [ ] **Timeout rate over training**: line graph showing % of episodes hitting the 15s limit declining over intervals

---

## Self-Play Considerations

Self-play improves long-term agent quality by providing an ever-improving opponent, preventing the policy from saturating against a fixed target. However it introduces **non-stationarity** — both agents are changing simultaneously — which makes reward signals harder to interpret. This should be framed explicitly in the paper as a known challenge with a concrete mitigation strategy, not hidden.

### Problems to Address in Writing
- [ ] **Acknowledge non-stationarity explicitly** — declining or noisy dense reward metrics (proximity, aim-hold) may reflect opponent improvement rather than agent regression. The paper must make clear that raw reward curves are not a clean signal of policy quality in self-play
- [ ] **Reframe the passive Nash equilibrium discussion** — in self-play, mutual aggression can emerge naturally as a stable equilibrium as both agents improve, which is actually a positive emergent property worth noting

### New Stats to Report
- [ ] **Win rate against frozen checkpoints** — periodically freeze a snapshot of the current policy and evaluate the live policy against it. A rising win rate is the cleanest objective signal of improvement, independent of reward noise
- [ ] **ELO or relative skill rating over training** — if running round-robin evaluations against multiple checkpoints, an ELO curve over training intervals gives reviewers an intuitive skill progression signal

### New Graphs to Add
- [ ] **Checkpoint win-rate curve** — x-axis is training interval, y-axis is win rate against a fixed early checkpoint (e.g., the policy at interval 500). Should trend upward if self-play is working
- [ ] **ELO over training** — if compute allows round-robin evals, plot estimated ELO vs. training interval alongside the reward curves to give an objective anchor

### Infrastructure Note
- [ ] Document how checkpoint freezing is implemented in the pipeline — how often snapshots are saved, how the evaluation opponent is swapped in, and whether evaluation episodes are excluded from gradient updates. Reviewers will ask.

---

## Writing Fixes (minor, no new content needed)

- [ ] Reframe the contribution in the abstract and intro explicitly as a **systems/engineering paper** — preempt reviewers who might penalize for not proposing a new algorithm
- [ ] Add a **results table** summarizing final-window mean ± std across all conditions and seeds
- [ ] Sharpen the corner-farming discussion into a named limitation with a **concrete proposed fix** (e.g., dynamic reward targets or arena randomization), not just an observation