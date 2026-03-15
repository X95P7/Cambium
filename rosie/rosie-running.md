# Running Cambium on Rosie — Notes & Findings

## Architecture (Rosie vs Docker)

| Component | Docker (local) | Rosie |
|---|---|---|
| MC Server | `itzg/minecraft-server:java8` container | Same image via `singularity exec` |
| Backend | Docker container with Python/PyTorch | Python venv (`rosie/.venv`) + GPU node |
| HeadlessMC bots | Custom Docker image with `expect` | Base `java8-base.sif` + pexpect on host |
| Orchestration | `docker-compose` | `sbatch` (SLURM) |

## Key Findings

### 1. Mods directory mismatch (root cause of bots not connecting)

HeadlessMC's `ProcessFactory` uses `~/.minecraft` as the game directory — **not** `/opt/hmc/run`.
The game searches `~/.minecraft/mods/` for Forge mods. We were copying mods to `/opt/hmc/run/mods/`
(bind-mounted per-bot), so **hmc-specifics never loaded**. Without hmc-specifics, the `connect`
and `say` console commands don't exist at all.

**Fix:** The entrypoint now copies mods from `/opt/hmc/run/mods/` → `~/.minecraft/mods/` before
launching Java.

### 2. PTY handling — `script` pipe vs `pexpect`

The Docker entrypoint uses Tcl `expect` which creates a real PTY via `spawn` and writes to it
with `send`. On Rosie, we initially tried `{commands} | script -qf /dev/null -c "java ..."`.
This echoed commands to the terminal but they were never processed by HeadlessMC's stdin handler.

**Fix:** Switched to `pexpect` (Python), which creates a real PTY identical to Tcl's `expect`.
The launcher (`rosie-bot-launcher.py`) runs on the host and spawns
`singularity exec ... bash rosie-bot-entrypoint.sh`, which `exec`s Java so it directly inherits
the PTY.

### 3. Singularity on Rosie — no `build`, no Docker

- `singularity build --fakeroot` fails — user not in `/etc/subuid`.
- Docker daemon socket is root:docker, user not in docker group.
- **Workaround:** Pull pre-built images from Docker Hub with `singularity pull docker://...`,
  then set up HeadlessMC natively into `rosie/hmc/` using `singularity exec java8-base.sif java -jar ...`.

### 4. Ports — shared device

Default ports (25565, 25575, 8000) conflict with other users on Rosie.
Changed to **33565** (MC), **33575** (RCON), **33800** (backend).

### 5. SLURM path resolution

`BASH_SOURCE[0]` inside an sbatch script resolves to SLURM's spool directory on the compute node,
not the original submission path. All paths must be absolute via `REPO_ROOT=$(pwd)`.

### 6. `#SBATCH --output` and `--error`

Using relative paths in `--output`/`--error` causes SLURM to try creating directories in its spool.
Set both to `/dev/null` and redirect manually with `exec > "$LOG_FILE" 2>&1`.

### 7. Bot concurrency — ZipException

Multiple bots launching simultaneously race on HeadlessMC's native library extraction in the
shared `$HMC_DIR/HeadlessMC/` directory, causing `ZipException`. Fixed by adding a 20-second
stagger between bot launches.

### 8. SSH tunneling

Rosie's management node is `dh-mgmt3.hpc.msoe.edu` (alias `msoe-hpc`), **not** `rosie.msoe.edu`.
Tunnel command:
```
ssh -L 33800:<node>:33800 -L 33565:<node>:33565 msoe-hpc
```
Where `<node>` is the compute node (e.g. `dh-node5`) shown in the job log.

### 9. Sound errors are harmless

HeadlessMC's headless LWJGL replacement doesn't implement audio. The `Source '...' not found in
method 'play'` errors are cosmetic and can be ignored.

### 10. Scaling to 8 bots

Resource allocation for 8 simultaneous bots on a single node:
- `--mem=64G` (SLURM), MC server `MEMORY=6G`, remaining split across 8 JVMs + backend
- `CAMBIUM_DEVICE=cuda` for GPU inference on the T4
- `--no-access-log` on uvicorn to reduce logging overhead
- Bot launch stagger reduced to 15s (from 20s)

### 11. RCON reliability

The `mcrcon` library uses `signal.alarm()` for timeouts, which fails in non-main threads
(`signal only works in main thread`). The backend monkey-patches `MCRcon.__init__`, `.connect`,
and `._read` to use `socket.settimeout()` instead. A single persistent `MCRcon` connection
protected by `threading.Lock` replaced per-command connections that caused connection flooding.

### 12. Bot pairing race conditions

Concurrent `/bot-setup`, `/death`, and episode timeout handlers could corrupt pairing state
(triangle pairings, 4 bots in one arena). Fixed by wrapping all state-modifying operations
in a global `asyncio.Lock` (`_match_lock`).

### 13. Frontend save-model path bug

The `/save-model` endpoint used a relative `models/` path (relative to CWD), which on Rosie
resolves differently than `backend/models/`. Fixed to use the same absolute `AUTOSAVE_DIR` as
the autosave system.

## Running Experiments

### Training run (default)

```bash
REPO_ROOT=$(pwd) sbatch rosie/cambium.sbatch
```

8 bots, T4 GPU, PPO with factored policy, 15-second episodes. Model auto-resumes from
the latest checkpoint in `backend/models/`. Data goes to:
- `rosie/logs/<JOB_ID>/` — per-bot logs, MC server log, backend log
- `backend/logs/training_<timestamp>.csv` — per-interval metrics
- `backend/logs/events_<timestamp>.log` — episode events (timeouts, kills, deaths)

### Baseline experiment (random policy)

```bash
REPO_ROOT=$(pwd) sbatch rosie/cambium-baseline.sbatch
```

Same infrastructure, but:
- `CAMBIUM_EXPERIMENT=baseline` + `CAMBIUM_NO_TRAIN=1` environment variables
- **Random policy**: actions sampled uniformly from each dimension (no model inference)
- **No model auto-resume**: agent starts with random weights (never used for inference)
- **No training**: `trigger_backprop` logs reward stats but skips `.train()`
- **No autosave**: doesn't overwrite trained model checkpoints
- Log directory: `rosie/logs/<JOB_ID>_baseline/`
- Data files tagged: `backend/logs/training_*_baseline.csv`, `events_*_baseline.log`
- 1-hour time limit (vs 1-day for training)

**Port conflict**: baseline and training share ports 33565/33575/33800. Cancel one before
starting the other, or override ports:
```bash
MC_PORT=33666 RCON_PORT=33676 BACKEND_PORT=33900 REPO_ROOT=$(pwd) sbatch rosie/cambium-baseline.sbatch
```

### Timeout ablation (Experiment 2.2)

```bash
REPO_ROOT=$(pwd) sbatch rosie/cambium-timeout-ablation.sbatch
```

- **Purpose**: Show that without bounded episodes (15s), agents stall — credit assignment horizon too long.
- **Config**: `CAMBIUM_EPISODE_TIMEOUT_SEC=120` and `CAMBIUM_EXPERIMENT=timeout_ablation`.
- **Same training as normal** (model, backprop, autosave); only episode cap is 120s.
- **Log directory**: `rosie/logs/<JOB_ID>_timeout_ablation/` (does not overwrite baseline or training).
- **Data files**: `backend/logs/training_*_timeout_ablation.csv`, `events_*_timeout_ablation.log`.
- **Duration**: 30 minutes (short run for ablation).
- Optional: override timeout, e.g. `CAMBIUM_EPISODE_TIMEOUT_SEC=300 REPO_ROOT=$(pwd) sbatch rosie/cambium-timeout-ablation.sbatch`.

### Sparse reward ablation (Experiment 2.3)

```bash
REPO_ROOT=$(pwd) sbatch rosie/cambium-sparse-reward.sbatch
```

- **Purpose**: Show that without dense reward shaping, the agent gets no learning signal (episodes timeout with zero combat).
- **Config**: `CAMBIUM_REWARD_MODE=sparse` and `CAMBIUM_EXPERIMENT=sparse_reward`. Shaping rewards (good_aim, proximity, pitch_control, aim_hold, extreme_pitch_penalty) are zeroed. Kept: damage_dealt, damage_taken, won_duel, death, episode_timeout, no_damage_penalty.
- **Log directory**: `rosie/logs/<JOB_ID>_sparse_reward/`
- **Data files**: `backend/logs/training_*_sparse_reward.csv`, `events_*_sparse_reward.log`
- **Duration**: 30 minutes.

## Quick Reference

```bash
# One-time setup
bash rosie/setup.sh

# Submit training (8 bots, default ports)
REPO_ROOT=$(pwd) sbatch rosie/cambium.sbatch

# Submit baseline experiment
REPO_ROOT=$(pwd) sbatch rosie/cambium-baseline.sbatch

# Submit timeout ablation (Experiment 2.2)
REPO_ROOT=$(pwd) sbatch rosie/cambium-timeout-ablation.sbatch

# Submit sparse reward ablation (Experiment 2.3)
REPO_ROOT=$(pwd) sbatch rosie/cambium-sparse-reward.sbatch

# Check status
squeue -u $USER

# Read logs (replace JOB_ID)
ls rosie/logs/<JOB_ID>/
tail -f rosie/logs/<JOB_ID>/cambium.log
tail -f rosie/logs/<JOB_ID>/backend.log

# Cancel
scancel <JOB_ID>

# SSH tunnel (replace dh-nodeX with actual node from log)
ssh -L 33800:dh-nodeX:33800 -L 33565:dh-nodeX:33565 msoe-hpc
```
