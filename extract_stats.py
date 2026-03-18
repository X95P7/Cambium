import pandas as pd
import numpy as np

dfs = {
    'training': pd.read_csv('paper/training_parsed.csv'),
    'baseline': pd.read_csv('paper/baseline_parsed.csv'),
    'timeout': pd.read_csv('paper/timeout_parsed.csv'),
    'sparse': pd.read_csv('paper/sparse_parsed.csv')
}

print("=== QUANTITATIVE METRICS ===")

# Baseline Stats
print("\n[BASELINE - Random Policy]")
df_b = dfs['baseline']
if 'sparse_reward' in df_b.columns:
    print(f"Mean Sparse Reward: {df_b['sparse_reward'].mean():.4f}")
    if 'damage_dealt_total' in df_b.columns:
        print(f"Mean Damage Dealt per Interval: {df_b['damage_dealt_total'].mean():.4f}")

# Sparse Reward Ablation
print("\n[SPARSE ABLATION - Terminal Rewards Only]")
df_s = dfs['sparse']
if 'total_reward' in df_s.columns:
    print(f"Mean Total Reward: {df_s['total_reward'].mean():.4f}")
    if 'damage_dealt_total' in df_s.columns:
        print(f"Mean Damage Dealt per Interval: {df_s['damage_dealt_total'].mean():.4f}")

# Timeout Ablation
print("\n[TIMEOUT ABLATION - 120s Bounded Episodes]")
df_to = dfs['timeout']
if 'sparse_reward' in df_to.columns:
    print(f"Mean Sparse Reward (early intervals): {df_to['sparse_reward'].mean():.4f}")
    
# Full Training Run
print("\n[FULL TRAINING RUN - PPO Factored Policy]")
df_t = dfs['training']
print(f"Total Intervals: {len(df_t)}")
if 'sparse_reward' in df_t.columns:
    mean_all = df_t['sparse_reward'].mean()
    # Last 10% of training
    last_10_percent = int(len(df_t) * 0.1)
    mean_late = df_t['sparse_reward'].iloc[-last_10_percent:].mean()
    
    print(f"Mean Sparse Reward (overall): {mean_all:.4f}")
    print(f"Mean Sparse Reward (last 10%): {mean_late:.4f}")
    
if 'damage_dealt_total' in df_t.columns:
    mean_dmg_late = df_t['damage_dealt_total'].iloc[-last_10_percent:].mean()
    print(f"Mean Damage Dealt per Interval (last 10%): {mean_dmg_late:.4f}")

    max_dmg = df_t['damage_dealt_total'].max()
    print(f"Max Damage Dealt in single interval: {max_dmg:.4f}")
    
print("\n=== REWARD COMPONENT TOTALS (Full Run) ===")
cols = [c for c in df_t.columns if c.endswith('_total') and c != 'total_reward']
for c in cols:
    print(f"{c}: {df_t[c].sum():.2f}")
    
print("\n=== LOSS METRICS (Full Run Last 10%) ===")
if 'policy_loss' in df_t.columns:
    print(f"Mean Policy Loss: {df_t['policy_loss'].iloc[-last_10_percent:].mean():.4f}")
if 'value_loss' in df_t.columns:
    print(f"Mean Value Loss: {df_t['value_loss'].iloc[-last_10_percent:].mean():.4f}")
if 'entropy' in df_t.columns:
    print(f"Mean Entropy: {df_t['entropy'].iloc[-last_10_percent:].mean():.4f}")
    print(f"Initial Entropy: {df_t['entropy'].iloc[0]:.4f}")
