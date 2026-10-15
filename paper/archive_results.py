import os
import shutil
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json

# Configuration
RUNS_DIR = "backend/runs"
OUTPUT_ROOT = "paper"
ROSIE_LOGS = "rosie/logs"

def get_available_runs():
    """Identify all runs in backend/runs and return list of (condition, seed, tag)"""
    runs = []
    if not os.path.exists(RUNS_DIR):
        return []
    for d in os.listdir(RUNS_DIR):
        if "_seed" in d:
            parts = d.split("_seed")
            exp = parts[0]
            try:
                seed = int(parts[1])
                runs.append((exp, seed, d))
            except:
                continue
    return sorted(runs)

def generate_seed_plots(exp_type, seed, output_dir):
    """Generate detailed performance plots for a specific seed."""
    # 1. Load data
    train_csv = os.path.join(OUTPUT_ROOT, "results", "all_runs.csv")
    eval_csv = os.path.join(OUTPUT_ROOT, "results", "all_eval_checkpoints.csv")
    
    if not os.path.exists(train_csv) or not os.path.exists(eval_csv):
        print(f"Skipping plots for {exp_type}_{seed}: missing data files")
        return

    try:
        df_train = pd.read_csv(train_csv)
        df_eval = pd.read_csv(eval_csv)
    except Exception as e:
        print(f"Error reading CSVs: {e}")
        return
    
    # Filter for this specific seed
    tag = f"{exp_type}_seed{seed}"
    df_t = df_train[df_train['run_tag'] == tag].copy()
    df_e = df_eval[df_eval['run_tag'] == tag].copy()
    
    if df_t.empty and df_e.empty:
        print(f"No data for {tag}")
        return

    # Set aesthetics
    sns.set_theme(style="whitegrid")
    
    # Plot 1: Eval Win Rate
    if not df_e.empty:
        plt.figure(figsize=(10, 5))
        sns.lineplot(data=df_e, x='triggered_at_interval', y='win_rate', marker='o', color='royalblue')
        plt.title(f"Baseline Evaluation Win-Rate: {exp_type} Seed {seed}")
        plt.xlabel("Training Interval")
        plt.ylabel("Win Rate (vs IT_WOKRS)")
        plt.ylim(-0.05, 1.05)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "win_rate_eval.png"), dpi=200)
        plt.close()

    # Plot 2: Training Reward Components (Moving Average for clarity)
    if not df_t.empty:
        reward_cols = [c for c in df_t.columns if c.startswith('r_') and c.endswith('_total')]
        if reward_cols:
            # Group by interval and mean to smooth if there are multiple logs
            df_t_grouped = df_t.groupby('interval')[reward_cols].mean().reset_index()
            
            # Melt for plotting
            df_melt = df_t_grouped.melt(id_vars=['interval'], value_vars=reward_cols, 
                                        var_name='Reward Type', value_name='Amount')
            df_melt['Reward Type'] = df_melt['Reward Type'].str.replace('r_', '').str.replace('_total', '')
            
            # Filter types to avoid clutter if needed, but here we show all
            plt.figure(figsize=(12, 7))
            sns.lineplot(data=df_melt, x='interval', y='Amount', hue='Reward Type')
            plt.title(f"Reward Component Trends: {exp_type} Seed {seed}")
            plt.xlabel("Interval")
            plt.ylabel("Reward Magnitude (SymLog)")
            plt.yscale('symlog', linthresh=0.1) # Handles negatives and positives
            plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, "reward_trends.png"), dpi=200)
            plt.close()

    # Plot 3: Entropy & Policy Loss
    if not df_t.empty and 'entropy' in df_t.columns:
        # Group to smooth
        df_t_dyn = df_t.groupby('interval')[['entropy', 'policy_loss']].mean().reset_index()
        
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax2 = ax1.twinx()
        
        sns.lineplot(data=df_t_dyn, x='interval', y='entropy', ax=ax1, color='forestgreen', label='Entropy')
        sns.lineplot(data=df_t_dyn, x='interval', y='policy_loss', ax=ax2, color='crimson', alpha=0.4, label='Policy Loss')
        
        ax1.set_ylabel("Entropy", color='forestgreen')
        ax1.set_ylim(0, 9)
        ax2.set_ylabel("Policy Loss", color='crimson')
        plt.title(f"Training Dynamics: {exp_type} Seed {seed}")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "entropy_loss.png"), dpi=200)
        plt.close()

def archive():
    print("=== Archiving Current Experiments ===")
    
    runs = get_available_runs()
    for exp, seed, tag in runs:
        print(f"Archiving {tag}...")
        
        # Create output directory
        target_dir = os.path.join(OUTPUT_ROOT, exp, str(seed))
        os.makedirs(target_dir, exist_ok=True)
        
        # 1. Update Logs (Live)
        log_src = os.path.join(RUNS_DIR, tag, "logs")
        log_dst = os.path.join(target_dir, "logs")
        if os.path.exists(log_src):
            if os.path.exists(log_dst):
                shutil.rmtree(log_dst)
            shutil.copytree(log_src, log_dst)
            print(f"  - Logs updated.")
            
        # 2. Generate Graphs
        graph_dir = os.path.join(target_dir, "graphs")
        os.makedirs(graph_dir, exist_ok=True)
        generate_seed_plots(exp, seed, graph_dir)
        print(f"  - Graphs updated in {graph_dir}.")

    print("\nArchiving complete. See paper/ folders for results.")

if __name__ == "__main__":
    archive()
