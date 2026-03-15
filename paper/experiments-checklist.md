# Experiments and Metrics Checklist — MICS 2026

This checklist tracks every metric, experiment, figure, and table needed for the paper,
which data source provides it, and which paper section uses it.

---

## Status Key

- [ ] Not started
- [x] Complete / data available

---

## 1. Passive Metrics (collected automatically from active training run)

**Data sources**:
- `backend/logs/training_*.csv` — per-interval: reward, loss, entropy, reward breakdown, sample counts
- `backend/logs/training_*.log` — human-readable per-interval summaries with per-bot scores and tick counts
- `backend/logs/events_*.log` — timestamped episode events (timeouts, deaths, kills, no-damage penalties)
- `backend/models/autosave_latest_stats.json` — rolling model checkpoint metadata

### 1.1 Reward Progression Over Training Intervals

- [ ] **Plot**: Total reward per training interval (y) vs interval number (x).
- **Source**: `training_*.csv`, column `total_reward`.
- **Shows**: Whether the agent's cumulative reward increases over time (= learning).
- **Paper section**: Section 8 (Preliminary Results).
- **How to produce**: Load CSV with pandas, plot `total_reward` column. Smooth with rolling average (window=10).
- **Fair comparison**: Use column `sparse_component_reward` (sum of damage_dealt, damage_taken, won_duel, death, episode_timeout, no_damage_penalty only) when comparing baseline vs sparse vs shaped runs — same scale so lower total in sparse run doesn’t mislead.

### 1.2 Reward Type Breakdown Over Time

- [ ] **Plot**: Stacked area or grouped bar chart of reward components over training intervals.
- **Source**: `training_*.csv`, columns `r_<type>_count` and `r_<type>_total` (aim_hold, good_aim, pitch_control, proximity, damage_dealt, damage_taken, extreme_pitch_penalty, won_duel, death, episode_timeout, no_damage_penalty).
- **Shows**: Which behaviors are being reinforced and how the composition shifts as the agent learns (e.g., aim rewards increase, no-damage penalties decrease).
- **Paper section**: Section 6 (Reward Engineering) and Section 8 (Results).
- **How to produce**: Load CSV, group reward columns by type, plot stacked area chart over intervals.

### 1.3 Loss Curves (Policy, Value, Entropy)

- [ ] **Plot**: Three-panel or overlay chart of policy_loss, value_loss, and entropy over training intervals.
- **Source**: `training_*.csv`, columns `policy_loss`, `value_loss`, `entropy`.
- **Shows**: Standard PPO diagnostics. Entropy should decrease as policy becomes less random. Value loss should decrease as the critic improves. Policy loss trending negative indicates learning.
- **Paper section**: Section 8 (Results).
- **How to produce**: Plot three columns from CSV. Include y-axis labels and a legend.

### 1.4 Episode Outcomes Over Time

- [ ] **Plot**: Ratio of kills vs timeouts per time window (e.g., per 10-minute bucket).
- **Source**: `events_*.log`, parse `[EPISODE] Timeout` lines and `[DEATH]` / kill lines.
- **Shows**: Whether agents transition from timing out (no combat) to actually fighting and killing.
- **Paper section**: Section 5 (Episode Structure) and Section 8 (Results).
- **How to produce**: Parse events log, bucket episodes by timestamp, compute kill-rate vs timeout-rate per bucket.

### 1.5 TPS (Ticks Per Second) Per Bot Over Time

- [ ] **Plot**: Line chart of TPS per bot over the training session.
- **Source**: Dashboard API (`/dashboard-data/`) reports `tick_rate` per bot. Alternatively, compute from bot log timestamps (time between consecutive reward events).
- **Shows**: System throughput and stability. Sudden drops indicate infrastructure issues.
- **Paper section**: Section 7 (Environment Control / Infrastructure) and Section 8 (Results).
- **How to produce**: Sample `/dashboard-data/` periodically during a run, or parse bot logs for timestamp gaps.

### 1.6 Damage Dealt Per Episode Over Time

- [ ] **Plot**: Average damage dealt per episode over time.
- **Source**: `training_*.csv`, column `r_damage_dealt_total` normalized by episode count (derive from events log timeout/death counts).
- **Shows**: Direct measure of combat effectiveness — are bots landing more hits over time?
- **Paper section**: Section 8 (Results).
- **How to produce**: Combine CSV damage counts with events log episode boundaries.

### 1.7 Return Mean and Std Over Time

- [ ] **Plot**: Line chart with confidence band for return_mean ± return_std over training intervals.
- **Source**: `training_*.csv`, columns `return_mean`, `return_std`.
- **Shows**: PPO's own estimate of expected return. Rising mean = the agent believes it's getting better. Narrowing std = more consistent value estimates.
- **Paper section**: Section 8 (Results).
- **How to produce**: Plot return_mean with shaded ±return_std band.

---

## 2. Active Experiments (require separate SLURM jobs)

### 2.1 Random Policy Baseline

- [X] **Experiment**: Run 8 bots with calibration mode (version 0.0 — random/scripted actions) for 30+ minutes.
- [X] **Collect**: Same metrics as above (reward progression, episode outcomes, damage dealt).
- **Shows**: The "no learning" baseline. All episodes should end via timeout with near-zero damage. Provides the comparison point for trained agent metrics.
- **Paper section**: Section 8 (Results) — overlaid on the trained agent's charts.
- **How to run**: Set all bots to model version 0.0 via `/set-bot-model/` endpoint, or submit a fresh job with the model disabled.
- **Priority**: **MUST HAVE** — without this, reward charts have no baseline reference.

### 2.2 Episode Timeout Ablation (if time permits)

- [X] **Experiment**: Run a short job (~15 min) with `MAX_EPISODE_LENGTH_SEC` set to 120s (or removed entirely).
- [X] **Collect**: Reward progression, damage dealt, episode length distribution.
- **Shows**: Without bounded episodes, agents stall — credit assignment horizon is too long for discount factor to propagate meaningful signal.
- **Paper section**: Section 5 (Episode Structure) — demonstrates why the 15s timeout is necessary.
- **How to run**: Modify `MAX_EPISODE_LENGTH_SEC` in `backend/main.py` temporarily, submit job.
- **Priority**: NICE TO HAVE — even 10 min of data showing flat reward would be compelling.

### 2.3 Reward Shaping Ablation (if time permits)

- [X] **Experiment**: Run a short job (~15 min) with only sparse rewards (kill/death/timeout — disable proximity, aim, pitch rewards).
- [X] **Collect**: Reward progression, damage dealt.
- **Shows**: Without dense shaping, agent receives no learning signal in early training (all episodes timeout with zero combat).
- **Paper section**: Section 6 (Reward Engineering) — demonstrates why dense shaping is necessary.
- **How to run**: Zero out shaping reward coefficients in `fast_rl_model.py:_compute_reward()`, submit job.
- **Priority**: NICE TO HAVE.

---

## 3. Figures and Tables to Create

### 3.1 System Architecture Diagram

- [ ] **Figure**: Block diagram showing Minecraft Forge Server, N HeadlessMC Clients, FastAPI Backend, RCON channel, HTTP observation/action flow, GPU inference.
- **Tool**: draw.io, Excalidraw, or TikZ.
- **Paper section**: Section 3 (System Architecture).
- **Priority**: MUST HAVE.

### 3.2 Action Space Comparison Figure

- [ ] **Figure**: Side-by-side comparison of flat categorical policy (one head, 1620+ outputs) vs factored multi-discrete policy (5 independent heads, 27 total outputs). Show the shared trunk branching into separate softmax heads.
- **Tool**: draw.io or TikZ.
- **Paper section**: Section 4 (Action Space Structure).
- **Priority**: MUST HAVE.

### 3.3 Reward Components Table

- [ ] **Table**: Columns: Reward Type, Value, Frequency, Purpose. Rows for each reward signal.
- **Source**: Already drafted in outline.md Section 6.
- **Paper section**: Section 6 (Reward Engineering).
- **Priority**: MUST HAVE.

### 3.4 Training Configuration Table

- [ ] **Table**: Hardware specs, software versions, hyperparameters.
- **Contents**:
  - Hardware: Tesla T4 GPU, 16 CPUs, 64GB RAM (Rosie HPC)
  - Minecraft: 1.8.9 Forge, custom CambiumMod
  - Clients: HeadlessMC 2.5.1, 8 simultaneous bots
  - Backend: Python 3.12, PyTorch, FastAPI, uvicorn
  - PPO hyperparameters: learning rate, gamma, GAE lambda, clip epsilon, batch size (64), epochs (4), backprop interval (200 ticks)
  - Episode: 15-second timeout, symmetric resets
- **Source**: `backend/fast_rl_model.py` and `rosie/cambium.sbatch` for exact values.
- **Paper section**: Section 8 (Results).
- **Priority**: MUST HAVE.

### 3.5 Reward Progression Chart

- [ ] Same as metric 1.1 — formatted for paper.
- **Priority**: MUST HAVE.

### 3.6 Episode Outcome Chart

- [ ] Same as metric 1.4 — formatted for paper.
- **Priority**: MUST HAVE.

### 3.7 TPS/Throughput Chart

- [ ] Same as metric 1.5 — formatted for paper.
- **Priority**: SHOULD HAVE.

---

## 4. Qualitative Observations

### 4.1 Behavioral Snapshots

- [ ] **Observe**: Watch bots via Minecraft client at different training stages. Note:
  - Do agents approach enemies?
  - Do they attack when in range?
  - Do they track enemies with camera?
  - Do they exhibit any emergent strategies (strafing, retreating)?
- [ ] **Screenshots**: Capture 2-3 annotated screenshots showing bot behavior.
- **Paper section**: Section 8 (Results) and Section 9 (Discussion).
- **Priority**: SHOULD HAVE.

---

## 5. Data Extraction Scripts Needed

### 5.1 CSV Analysis Script

- [ ] **Script**: `paper/analyze_training.py` — loads `training_*.csv`, produces:
  - Reward progression plot (1.1)
  - Reward breakdown plot (1.2)
  - Loss curves (1.3)
  - Return mean/std plot (1.7)
  - Damage-per-interval chart (1.6)
- **Dependency**: matplotlib, pandas, numpy.

### 5.2 Events Log Parser

- [ ] **Script**: `paper/analyze_events.py` — parses `events_*.log`, produces:
  - Episode outcome distribution (1.4) — timeouts vs kills over time
  - Episode rate (episodes per minute)
  - Per-bot kill/death/timeout counts
- **Dependency**: matplotlib, re (regex), datetime.

---

## Priority Summary

| Priority | Item | Section |
|----------|------|---------|
| MUST HAVE | Reward progression chart | 8 |
| MUST HAVE | Episode outcomes chart | 5, 8 |
| MUST HAVE | Reward breakdown table | 6 |
| MUST HAVE | Architecture diagram | 3 |
| MUST HAVE | Action space figure | 4 |
| MUST HAVE | Training config table | 8 |
| MUST HAVE | Random baseline comparison | 8 |
| SHOULD HAVE | Loss curves | 8 |
| SHOULD HAVE | Damage-per-episode chart | 8 |
| SHOULD HAVE | TPS chart | 7, 8 |
| SHOULD HAVE | Qualitative observations + screenshots | 8, 9 |
| NICE TO HAVE | Timeout ablation experiment | 5 |
| NICE TO HAVE | Reward shaping ablation experiment | 6 |
