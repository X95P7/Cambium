# Cambium on Rosie (MSOE HPC)

Run the full Cambium RL training stack on MSOE's Rosie cluster using SLURM and Singularity.

See [Rosie docs](https://docs.hpc.msoe.edu/#/cli/sbatch) for general SLURM/sbatch reference.

## Architecture

Everything runs on **one compute node** (teaching partition, 1x T4 GPU):

| Component | Runs As | Port |
|---|---|---|
| Minecraft Server 1.8.9 Forge | Singularity container (Java 8) | 25565, 25575 (RCON) |
| FastAPI Backend (PyTorch) | Python venv with CUDA | 8000 |
| HeadlessMC Clients (N bots) | Singularity containers (Java 8) | -- |

All processes communicate via `localhost` on the same node. The backend uses the T4 GPU for PyTorch training.

## Prerequisites

- SSH access to Rosie (`ssh <username>@rosie.msoe.edu`)
- The Cambium repo cloned on Rosie (your home directory or shared storage)
- The mod JAR built and placed in `headlessmc/mods/` (see main README)

## Quick Start

```bash
# 1. Clone the repo on Rosie (if not already done)
git clone <your-repo-url> ~/Cambium
cd ~/Cambium

# 2. Make sure the mod JAR is in headlessmc/mods/
#    If you built the mod on your local machine, push it to the repo
#    or scp it over:
#    scp headlessmc/mods/CambiumMod-1.0.jar <user>@rosie.msoe.edu:~/Cambium/headlessmc/mods/
ls headlessmc/mods/CambiumMod-1.0.jar   # Verify it exists

# 3. Run one-time setup (builds Singularity images, creates Python venv)
#    This takes ~10-15 minutes the first time
bash rosie/setup.sh

# 4. Submit the training job (default: 4 bots)
sbatch rosie/cambium.sbatch

# Or with a custom number of bots:
NUM_BOTS=6 sbatch rosie/cambium.sbatch

# 5. Check job status
squeue -u $USER

# 6. Get the SSH tunnel command from the job log
head -30 rosie/logs/cambium_$(squeue -u $USER -h -o %i).log
```

## Connecting from Your PC

The Minecraft server and dashboard run on a compute node that isn't directly reachable from your PC. You need an **SSH tunnel** to forward the ports.

### Step 1: Find the tunnel command

The job log prints it at the top. Find it with:

```bash
# On Rosie:
head -30 rosie/logs/cambium_<JOB_ID>.log
```

It will look like:

```
ssh -L 8000:dh-nodeXX:8000 -L 25565:dh-nodeXX:25565 <your-user>@rosie.msoe.edu
```

### Step 2: Run the tunnel on your local machine

Open a terminal on your PC (not Rosie) and run the SSH command from the log:

```bash
ssh -L 8000:dh-nodeXX:8000 -L 25565:dh-nodeXX:25565 <your-user>@rosie.msoe.edu
```

Keep this terminal open while you want to connect.

### Step 3: Connect

- **Dashboard**: Open http://localhost:8000 in your browser
- **Minecraft**: Open Minecraft 1.8.9, add server `localhost:25565`, and join

You can now watch the bots fight in-game and monitor training on the dashboard.

### Step 4: Activate the bots

Once you're in the Minecraft server, type in chat:

1. `&setup` — registers and pairs all bots
2. `&bot-setup` — loads config from backend
3. `&run` — starts the RL loop

Or from Rosie via the MC server logs (if the entrypoint doesn't auto-send these).

## Viewing Logs

All logs are written to `rosie/logs/` and named with the SLURM job ID:

```bash
# On Rosie — main job output (startup messages, tunnel command):
tail -f rosie/logs/cambium_<JOB_ID>.log

# Backend (training stats, errors, predict timing):
tail -f rosie/logs/backend_<JOB_ID>.log

# Minecraft server (player joins, chat, commands):
tail -f rosie/logs/mc-server_<JOB_ID>.log

# Individual bot clients:
tail -f rosie/logs/Bot1_<JOB_ID>.log
tail -f rosie/logs/Bot2_<JOB_ID>.log
```

To find your job ID:
```bash
squeue -u $USER
# Or list recent logs:
ls -lt rosie/logs/ | head
```

## Managing Jobs

```bash
# Check running jobs
squeue -u $USER

# Cancel a job
scancel <JOB_ID>

# Cancel all your jobs
scancel -u $USER

# Check how long a job has been running
squeue -u $USER -o "%.10i %.9P %.20j %.8T %.10M %.6D %R"
```

## Scaling

The `NUM_BOTS` environment variable controls how many headless clients are spawned (default 4). Each bot runs as a separate Singularity container. The single-node setup comfortably handles 4-8 bots. Beyond that, the Minecraft server may become the bottleneck.

## Troubleshooting

**"Run 'bash rosie/setup.sh' first"**
The sbatch script checks that Singularity images and the Python venv exist. Run setup first.

**Minecraft server fails to start**
Check `rosie/logs/mc-server_<JOB_ID>.log`. Common issues:
- EULA not accepted (should be handled automatically)
- Port already in use (another job on the same node)

**Backend fails to start**
Check `rosie/logs/backend_<JOB_ID>.log`. Common issues:
- Missing Python dependencies (re-run `bash rosie/setup.sh`)
- CUDA not available (ensure `--gres=gpu:t4:1` is in the sbatch header)

**Bots don't connect**
Check individual bot logs `rosie/logs/Bot1_<JOB_ID>.log`. The bots wait for the MC server to be available before connecting. If the server takes longer than expected, the `nc` wait loop in the entrypoint handles it.

**Can't connect from your PC**
- Make sure the SSH tunnel is running (Step 2 above)
- Make sure you're using the correct node hostname from the log
- Make sure you're using Minecraft 1.8.9 (other versions won't work with Forge 1.8.9)
- If the tunnel drops, just re-run the SSH command

**Rebuild after code changes**
If you change the mod source code:
1. Build locally: `cd mod/CambiumMod && ./gradlew clean build` (or `.\gradlew.bat clean build` on Windows)
2. Copy JAR: `cp build/libs/CambiumMod-1.0.jar ../../headlessmc/mods/`
3. Push to git and pull on Rosie, or `scp` the JAR directly
4. Delete the old Singularity image: `rm rosie/images/cambium-headlessmc.sif`
5. Re-run: `bash rosie/setup.sh` to rebuild the image

If you change only backend Python code, no rebuild is needed -- the venv runs it directly from `backend/`. Just resubmit the job.

## File Layout

```
rosie/
  cambium.sbatch             # Main SLURM job script
  setup.sh                   # One-time setup (images + venv)
  cambium-headlessmc.def     # Singularity definition for HeadlessMC
  README.md                  # This file
  images/                    # Singularity .sif images (created by setup.sh)
  logs/                      # Job logs (created at runtime)
  mc-data/                   # Minecraft server data (created at runtime)
  bot-data/                  # Per-bot game directories (created at runtime)
  .venv/                     # Python virtual environment (created by setup.sh)
```
