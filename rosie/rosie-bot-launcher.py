#!/usr/bin/env python3
"""Rosie bot launcher — mirrors Docker's expect-based entrypoint using pexpect.

Runs on the host and spawns HeadlessMC inside Singularity with a proper PTY so
that stdin commands (connect, say, etc.) are delivered exactly as Docker's
``expect`` / ``send`` mechanism does.

Required env vars:  REPO_ROOT, BOT_RUN_DIR
Optional env vars:  SERVER, USERNAME, HMC_VERSION, MC_VERSION, HEADLESSMC_COMMAND
"""

import os
import subprocess
import sys
import time

import pexpect


def main():
    repo_root = os.environ["REPO_ROOT"]
    bot_run_dir = os.environ["BOT_RUN_DIR"]
    images_dir = os.path.join(repo_root, "rosie", "images")
    hmc_dir = os.path.join(repo_root, "rosie", "hmc")

    username = os.environ.get("USERNAME", "Player")
    server = os.environ.get("SERVER", "")
    hmc_version = os.environ.get("HMC_VERSION", "2.5.1")
    mc_version = os.environ.get("MC_VERSION", "1.8.9")
    cambium_api_url = os.environ.get("CAMBIUM_API_URL", "http://backend:8000")

    mc_host = ""
    mc_port = "33565"
    if server:
        parts = server.split(":")
        mc_host = parts[0]
        if len(parts) > 1:
            mc_port = parts[1]

    # Build singularity command as a list to avoid shell-quoting headaches.
    cmd_args = [
        "singularity", "exec",
        "--writable-tmpfs",
        "--bind", f"{hmc_dir}:/opt/hmc",
        "--bind", f"{bot_run_dir}:/opt/hmc/run",
        "--env", f"USERNAME={username}",
        "--env", f"SERVER={server}",
        "--env", f"HMC_VERSION={hmc_version}",
        "--env", f"MC_VERSION={mc_version}",
        "--env", f"CAMBIUM_API_URL={cambium_api_url}",
        f"{images_dir}/java8-base.sif",
        "bash", f"{repo_root}/rosie/rosie-bot-entrypoint.sh",
    ]

    print(f"=== {username} starting (pexpect launcher) ===")
    print(f"Command: {' '.join(cmd_args)}")
    sys.stdout.flush()

    # pexpect.spawn creates a real PTY — the same mechanism expect's `spawn` uses
    child = pexpect.spawn(
        cmd_args[0], cmd_args[1:],
        encoding="utf-8", codec_errors="replace", timeout=None,
    )
    child.logfile_read = sys.stdout

    # ------------------------------------------------------------------
    #  Wait for game to fully load (mirrors Docker entrypoint pattern)
    # ------------------------------------------------------------------
    game_loaded = False
    try:
        child.expect(r"Created: (?:1024x512|512x512) textures-atlas", timeout=180)
        game_loaded = True
        print("\n[launcher] Game fully loaded (textures-atlas detected)")
        print("[launcher] Waiting for mods to initialise...")
        sys.stdout.flush()
        time.sleep(8)
    except pexpect.TIMEOUT:
        print("\n[launcher] Timeout waiting for textures-atlas, proceeding anyway...")
        sys.stdout.flush()
        time.sleep(10)
    except pexpect.EOF:
        print("\n[launcher] Process exited before game loaded.")
        sys.stdout.flush()
        return

    if game_loaded:
        print("[launcher] Waiting for command system...")
        sys.stdout.flush()
        time.sleep(5)
    else:
        print("[launcher] Game-load uncertain, waiting extra time...")
        sys.stdout.flush()
        time.sleep(10)

    print("[launcher] Waiting for main menu...")
    sys.stdout.flush()
    time.sleep(5)

    # ------------------------------------------------------------------
    #  Send connect (same as Docker's  send "connect $host $port\r" )
    # ------------------------------------------------------------------
    if mc_host:
        print(f"[launcher] Connecting to {mc_host}:{mc_port}")
        sys.stdout.flush()
        time.sleep(1)
        child.sendline(f"connect {mc_host} {mc_port}")
        print(f"[launcher] Sent: connect {mc_host} {mc_port}")
        sys.stdout.flush()

        print("[launcher] Waiting for connection to establish...")
        sys.stdout.flush()
        time.sleep(15)

        print("[launcher] Sending chat message...")
        sys.stdout.flush()
        time.sleep(2)
        child.sendline("say Hello, world!")
        child.sendline("gui")
        print("[launcher] Sent: say Hello, world!")
        sys.stdout.flush()
    else:
        print("[launcher] No SERVER set, skipping connection")
        sys.stdout.flush()

    # ------------------------------------------------------------------
    #  Reconnection loop (mirrors Docker entrypoint)
    # ------------------------------------------------------------------
    print("[launcher] Entering reconnection watch loop...")
    sys.stdout.flush()

    disconnect_re = (
        r"Disconnected|Connection [Ll]ost|Connection [Rr]eset"
        r"|io\.netty\.|Timed out|Internal Exception|Server closed"
    )

    while True:
        try:
            idx = child.expect([disconnect_re, pexpect.EOF], timeout=None)

            if idx == 0:
                print("\n[launcher] === DISCONNECTED from server ===")
                print("[launcher] Waiting 15s before checking server...")
                sys.stdout.flush()
                time.sleep(15)

                while True:
                    print(f"[launcher] Checking {mc_host}:{mc_port}...")
                    sys.stdout.flush()
                    ret = subprocess.run(
                        ["bash", "-c", f"nc -z -w5 {mc_host} {mc_port} 2>/dev/null"],
                        capture_output=True,
                    )
                    if ret.returncode == 0:
                        break
                    print("[launcher] Server not available, retrying in 10s...")
                    sys.stdout.flush()
                    time.sleep(10)

                print("[launcher] Server is back! Waiting 20s for full startup...")
                sys.stdout.flush()
                time.sleep(20)

                child.sendline(f"connect {mc_host} {mc_port}")
                print("[launcher] Reconnect command sent.")
                sys.stdout.flush()
                time.sleep(15)
                child.sendline("say I'm back!")
                print("[launcher] Reconnection complete.")
                sys.stdout.flush()

            else:
                print("\n[launcher] HeadlessMC exited.")
                sys.stdout.flush()
                break

        except pexpect.EOF:
            print("\n[launcher] Process ended.")
            sys.stdout.flush()
            break

    print(f"=== {username} exited ===")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
