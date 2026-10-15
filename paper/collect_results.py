#!/usr/bin/env python3
"""
collect_results.py — Aggregate experiment CSVs into a single analysis-ready dataset.

Usage:
    python paper/collect_results.py                    # scan backend/runs/
    python paper/collect_results.py --runs-dir /path   # custom runs dir
    python paper/collect_results.py --condition full   # single condition

Output files (written to paper/results/):
    all_runs.csv             — raw merged CSV with condition + seed columns
    summary_mean_std.csv     — mean ± std per condition over seeds
    final_window.csv         — last 10% of training per run
    sample_efficiency.csv    — first interval with a kill per run
    timeout_rate.csv         — % episodes timing out per interval per condition
"""

import os
import sys
import glob
import json
import argparse
import pandas as pd
import numpy as np

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_RUNS_DIR = os.path.join(REPO_ROOT, "backend", "runs")
OUTPUT_DIR = os.path.join(REPO_ROOT, "paper", "results")

# ── Known conditions ──────────────────────────────────────────────────────────
CONDITIONS = ["full", "random", "sparse", "no_timeout", "flat_action"]


def parse_run_tag(run_tag: str):
    """Parse 'full_seed1' → ('full', 1)."""
    for cond in sorted(CONDITIONS, key=len, reverse=True):
        if run_tag.startswith(cond):
            remainder = run_tag[len(cond):]
            seed_part = remainder.lstrip("_seed").lstrip("_")
            try:
                seed = int(seed_part) if seed_part else 0
            except ValueError:
                seed = 0
            return cond, seed
    return run_tag, 0


def load_run_csv(run_dir: str, run_tag: str) -> pd.DataFrame | None:
    """Load and concatenate all training CSVs for a run (handles multi-job restarts)."""
    logs_dir = os.path.join(run_dir, "logs")
    csv_files = sorted(glob.glob(os.path.join(logs_dir, "training_*.csv")),
                       key=os.path.getmtime)
    if not csv_files:
        return None

    frames = []
    for path in csv_files:
        try:
            df = pd.read_csv(path)
            df["_source_file"] = os.path.basename(path)
            frames.append(df)
        except Exception as e:
            print(f"  [WARN] Could not read {path}: {e}")

    if not frames:
        return None

    merged = pd.concat(frames, ignore_index=True)
    # Drop exact duplicate intervals (from overlapping restarts)
    merged = merged.drop_duplicates(subset=["interval"], keep="last")
    merged = merged.sort_values("interval").reset_index(drop=True)
    # Re-number intervals sequentially so multi-job runs are continuous
    merged["interval"] = range(1, len(merged) + 1)

    cond, seed = parse_run_tag(run_tag)
    merged["condition"] = cond
    merged["seed"] = seed
    merged["run_tag"] = run_tag

    # Load config snapshot if available
    config_path = os.path.join(logs_dir, "config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
        merged["reward_mode"] = config.get("reward_mode", "shaped")
        merged["no_timeout"] = config.get("no_timeout", False)
        merged["flat_action"] = config.get("flat_action", False)
        merged["seed_actual"] = config.get("seed", seed)

    return merged


def load_eval_csv(run_dir: str, run_tag: str) -> pd.DataFrame | None:
    """Load and concatenate all eval_checkpoints CSVs for a run."""
    logs_dir = os.path.join(run_dir, "logs")
    csv_files = sorted(glob.glob(os.path.join(logs_dir, "eval_checkpoints_*.csv")),
                       key=os.path.getmtime)
    if not csv_files:
        return None

    frames = []
    for path in csv_files:
        try:
            df = pd.read_csv(path)
            frames.append(df)
        except Exception as e:
            print(f"  [WARN] Could not read eval CSV {path}: {e}")

    if not frames:
        return None

    merged = pd.concat(frames, ignore_index=True)
    # Deduplicate by trigger interval
    merged = merged.drop_duplicates(subset=["triggered_at_interval"], keep="last")
    merged = merged.sort_values("triggered_at_interval").reset_index(drop=True)

    cond, seed = parse_run_tag(run_tag)
    merged["condition"] = cond
    merged["seed"] = seed
    merged["run_tag"] = run_tag
    return merged


def compute_summary(all_df: pd.DataFrame) -> pd.DataFrame:
    """Mean ± std per condition over seeds for convergence metrics."""
    metrics = [
        "total_reward", "sparse_component_reward", "avg_reward",
        "return_mean", "return_std", "loss", "policy_loss",
        "value_loss", "entropy", "samples",
    ]
    # Also include per-reward-type totals if present
    for col in all_df.columns:
        if col.startswith("r_") and col.endswith("_total"):
            metrics.append(col)

    metrics = [m for m in metrics if m in all_df.columns]

    rows = []
    for cond in all_df["condition"].unique():
        group = all_df[all_df["condition"] == cond]
        # Use last 10% of each seed's training as "convergence window"
        final_windows = []
        for seed, seed_df in group.groupby("seed"):
            n = max(1, int(len(seed_df) * 0.1))
            final_windows.append(seed_df.tail(n))
        final = pd.concat(final_windows)

        row = {"condition": cond, "n_seeds": group["seed"].nunique()}
        for m in metrics:
            row[f"{m}_mean"] = final[m].mean()
            row[f"{m}_std"] = final[m].std()
        rows.append(row)

    return pd.DataFrame(rows)


def compute_sample_efficiency(all_df: pd.DataFrame) -> pd.DataFrame:
    """First interval with any won_duel count > 0 per run."""
    rows = []
    if "r_won_duel_count" not in all_df.columns:
        print("  [WARN] r_won_duel_count column not found — skipping sample efficiency")
        return pd.DataFrame()

    for (cond, seed), df in all_df.groupby(["condition", "seed"]):
        df = df.reset_index(drop=True)
        kills = df[df["r_won_duel_count"] > 0]
        first_kill = kills["interval"].min() if not kills.empty else None
        rows.append({
            "condition": cond, "seed": seed,
            "first_kill_interval": first_kill,
            "total_kills": df["r_won_duel_count"].sum(),
            "total_intervals": len(df),
        })
    return pd.DataFrame(rows)


def compute_timeout_rate(all_df: pd.DataFrame) -> pd.DataFrame:
    """Percentage of episodes ending in timeout per interval window, per condition."""
    if "r_episode_timeout_count" not in all_df.columns:
        print("  [WARN] r_episode_timeout_count column not found — skipping timeout rate")
        return pd.DataFrame()

    WINDOW = 50  # smooth over 50-interval windows
    rows = []
    for (cond, seed), df in all_df.groupby(["condition", "seed"]):
        df = df.copy().reset_index(drop=True)
        total = (df.get("r_won_duel_count", 0) +
                 df.get("r_episode_timeout_count", 0) +
                 df.get("r_death_count", 0))
        timeout = df.get("r_episode_timeout_count", 0)
        df["timeout_rate"] = timeout / total.clip(lower=1)
        df["window"] = (df["interval"] - 1) // WINDOW
        windowed = df.groupby("window")["timeout_rate"].mean().reset_index()
        windowed["condition"] = cond
        windowed["seed"] = seed
        windowed["interval_approx"] = windowed["window"] * WINDOW + WINDOW // 2
        rows.append(windowed)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def compute_eval_summary(eval_df: pd.DataFrame) -> pd.DataFrame:
    """Average win-rate and reward delta per condition/seed over training time."""
    # We want to see how eval performance improves over 'triggered_at_interval'
    rows = []
    for (cond, seed), df in eval_df.groupby(["condition", "seed"]):
        df = df.sort_values("triggered_at_interval")
        # Final performance (last 2 checkpoints)
        final = df.tail(2)
        rows.append({
            "condition": cond, "seed": seed,
            "final_win_rate": final["win_rate"].mean(),
            "final_reward_delta": final["reward_delta"].mean(),
            "max_win_rate": df["win_rate"].max(),
            "avg_win_rate": df["win_rate"].mean(),
            "total_eval_episodes": df["total_episodes"].sum(),
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Aggregate Cambium experiment results")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR,
                        help="Path to backend/runs directory")
    parser.add_argument("--condition", default=None,
                        help="Filter to a specific condition")
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Scanning runs in: {args.runs_dir}")
    if not os.path.isdir(args.runs_dir):
        print(f"ERROR: runs directory not found: {args.runs_dir}")
        sys.exit(1)

    # Discover all run directories
    run_dirs = [
        d for d in sorted(os.listdir(args.runs_dir))
        if os.path.isdir(os.path.join(args.runs_dir, d))
    ]
    if args.condition:
        run_dirs = [d for d in run_dirs if d.startswith(args.condition)]

    if not run_dirs:
        print("No runs found. Have you submitted any experiments yet?")
        sys.exit(0)

    # Load all runs
    frames = []
    for run_tag in run_dirs:
        run_dir = os.path.join(args.runs_dir, run_tag)
        print(f"  Loading: {run_tag} ... ", end="")
        df = load_run_csv(run_dir, run_tag)
        if df is None:
            print("no CSV found — skipping")
            continue
        print(f"{len(df)} intervals")
        frames.append(df)

    if not frames:
        print("No training data loaded — nothing to aggregate.")
        sys.exit(0)

    all_df = pd.concat(frames, ignore_index=True)
    print(f"\nTotal training rows: {len(all_df)} across {len(frames)} runs")

    # Load eval data
    eval_frames = []
    for run_tag in run_dirs:
        run_dir = os.path.join(args.runs_dir, run_tag)
        edf = load_eval_csv(run_dir, run_tag)
        if edf is not None:
            eval_frames.append(edf)

    all_eval_df = None
    if eval_frames:
        all_eval_df = pd.concat(eval_frames, ignore_index=True)
        print(f"Total eval rows: {len(all_eval_df)} across {len(eval_frames)} runs")

    # ── Outputs ────────────────────────────────────────────────────────────
    out_all = os.path.join(args.output_dir, "all_runs.csv")
    all_df.to_csv(out_all, index=False)
    print(f"  Saved: {out_all}")

    summary = compute_summary(all_df)
    out_summary = os.path.join(args.output_dir, "summary_mean_std.csv")
    summary.to_csv(out_summary, index=False)
    print(f"  Saved: {out_summary}")

    efficiency = compute_sample_efficiency(all_df)
    if not efficiency.empty:
        out_eff = os.path.join(args.output_dir, "sample_efficiency.csv")
        efficiency.to_csv(out_eff, index=False)
        print(f"  Saved: {out_eff}")

    timeout = compute_timeout_rate(all_df)
    if not timeout.empty:
        out_timeout = os.path.join(args.output_dir, "timeout_rate.csv")
        timeout.to_csv(out_timeout, index=False)
        print(f"  Saved: {out_timeout}")

    if all_eval_df is not None:
        out_eval_all = os.path.join(args.output_dir, "all_eval_checkpoints.csv")
        all_eval_df.to_csv(out_eval_all, index=False)
        print(f"  Saved: {out_eval_all}")

        eval_summary = compute_eval_summary(all_eval_df)
        out_eval_sum = os.path.join(args.output_dir, "eval_summary.csv")
        eval_summary.to_csv(out_eval_sum, index=False)
        print(f"  Saved: {out_eval_sum}")

    # ── Print quick summary table ──────────────────────────────────────────
    print("\n=== Quick Summary (final 10% window) ===")
    if not summary.empty:
        display_cols = ["condition", "n_seeds",
                        "sparse_component_reward_mean", "sparse_component_reward_std",
                        "entropy_mean", "loss_mean"]
        display_cols = [c for c in display_cols if c in summary.columns]
        print(summary[display_cols].to_string(index=False))

    print(f"\nDone. Results written to {args.output_dir}/")


if __name__ == "__main__":
    main()
