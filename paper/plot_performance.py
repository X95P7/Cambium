import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Paths
RESULTS_DIR = "paper/results"
FIGURES_DIR = "paper/figures_live"
TRAIN_CSV = os.path.join(RESULTS_DIR, "all_runs.csv")
EVAL_CSV = os.path.join(RESULTS_DIR, "all_eval_checkpoints.csv")

def plot_all():
    if not os.path.exists(TRAIN_CSV):
        print(f"Error: {TRAIN_CSV} not found. Run 'python paper/collect_results.py' first.")
        return

    os.makedirs(FIGURES_DIR, exist_ok=True)
    
    # Load data
    df_train = pd.read_csv(TRAIN_CSV)
    df_eval = pd.read_csv(EVAL_CSV) if os.path.exists(EVAL_CSV) else pd.DataFrame()

    # Set style
    sns.set_theme(style="whitegrid", palette="muted")
    
    # 1. Plot Win Rate (Primary Performance Metric)
    if not df_eval.empty:
        plt.figure(figsize=(10, 6))
        # Plot mean and std shadow across seeds for each condition
        sns.lineplot(data=df_eval, x='triggered_at_interval', y='win_rate', hue='condition', marker='o')
        plt.title("Evaluation Win-Rate vs IT_WOKRS Baseline", fontsize=14, fontweight='bold')
        plt.xlabel("Training Intervals", fontsize=12)
        plt.ylabel("Win Rate", fontsize=12)
        plt.ylim(-0.05, 1.05)
        plt.legend(title="Condition", frameon=True)
        plt.tight_layout()
        plt.savefig(os.path.join(FIGURES_DIR, "win_rate_comparison.png"), dpi=200)
        print(f"Generated: {FIGURES_DIR}/win_rate_comparison.png")
        plt.close()

    # 2. Plot Sparse Reward (Combat Efficiency)
    plt.figure(figsize=(10, 6))
    # Filter out columns we want to track
    if 'sparse_component_reward' in df_train.columns:
        sns.lineplot(data=df_train, x='interval', y='sparse_component_reward', hue='condition')
        plt.title("Sparse Reward Progression (Mean + Std)", fontsize=14, fontweight='bold')
        plt.xlabel("Intervals", fontsize=12)
        plt.ylabel("Sparse Reward Amount", fontsize=12)
        plt.legend(title="Condition", frameon=True)
        plt.tight_layout()
        plt.savefig(os.path.join(FIGURES_DIR, "combat_intensity.png"), dpi=200)
        print(f"Generated: {FIGURES_DIR}/combat_intensity.png")
        plt.close()

    # 3. Plot Entropy (Exploration Decay)
    if 'entropy' in df_train.columns:
        plt.figure(figsize=(10, 6))
        sns.lineplot(data=df_train[df_train['condition'] != 'random'], x='interval', y='entropy', hue='condition')
        plt.title("Policy Entropy Decay (Learning Convergence)", fontsize=14, fontweight='bold')
        plt.xlabel("Intervals", fontsize=12)
        plt.ylabel("Entropy", fontsize=12)
        plt.ylim(0, 9)
        plt.legend(title="Condition", frameon=True)
        plt.tight_layout()
        plt.savefig(os.path.join(FIGURES_DIR, "entropy_decay.png"), dpi=200)
        print(f"Generated: {FIGURES_DIR}/entropy_decay.png")
        plt.close()

    print(f"\nAll plots saved to {FIGURES_DIR}")

if __name__ == "__main__":
    plot_all()
