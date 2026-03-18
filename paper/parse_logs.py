import sys
import re
import pandas as pd
import matplotlib.pyplot as plt
import os

def parse_log(filepath):
    data = []
    current_interval = {}
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        if line.startswith("Interval"):
            if current_interval:
                data.append(current_interval)
            current_interval = {}
            m = re.search(r'Interval\s+(\d+)', line)
            if m:
                current_interval['interval'] = int(m.group(1))
        elif line.startswith("Samples:"):
            m = re.search(r'Samples:\s+(\d+)', line)
            if m:
                current_interval['samples'] = int(m.group(1))
        elif line.startswith("Total reward:"):
            m = re.search(r'Total reward:\s+([\-\+\d\.]+)', line)
            if m:
                current_interval['total_reward'] = float(m.group(1))
        elif line.startswith("Sparse component"):
            m = re.search(r'Sparse component \(comparable\):\s+([\-\+\d\.]+)', line)
            if m:
                current_interval['sparse_reward'] = float(m.group(1))
        elif line.startswith("Return mean:"):
            m = re.search(r'Return mean:\s+([\-\+\d\.]+)\s+std:\s+([\-\+\d\.]+)', line)
            if m:
                current_interval['return_mean'] = float(m.group(1))
                current_interval['return_std'] = float(m.group(2))
        elif line.startswith("Loss:"):
            m = re.search(r'Loss:\s+([\-\+\d\.]+)\s+\(policy=([\-\+\d\.]+)\s+value=([\-\+\d\.]+)\)', line)
            if m:
                current_interval['loss'] = float(m.group(1))
                current_interval['policy_loss'] = float(m.group(2))
                current_interval['value_loss'] = float(m.group(3))
        elif line.startswith("Entropy:"):
            m = re.search(r'Entropy:\s+([\-\+\d\.]+)', line)
            if m:
                current_interval['entropy'] = float(m.group(1))
        elif line.startswith("damage_dealt"):
            m = re.search(r'count=\s*(\d+)\s+total=\s*([\-\+\d\.]+)', line)
            if m:
                current_interval['damage_dealt_count'] = int(m.group(1))
                current_interval['damage_dealt_total'] = float(m.group(2))
        elif line.startswith("aim_hold") or line.startswith("good_aim") or line.startswith("pitch_control") or line.startswith("proximity") or line.startswith("death") or line.startswith("won_duel"):
            parts = line.split()
            name = parts[0]
            m = re.search(r'count=\s*(\d+)\s+total=\s*([\-\+\d\.]+)', line)
            if m:
                current_interval[f'{name}_count'] = int(m.group(1))
                current_interval[f'{name}_total'] = float(m.group(2))
                
    if current_interval:
        data.append(current_interval)
        
    df = pd.DataFrame(data)
    return df

logs = {
    'training': '../backend/logs/training_20260315_101754.log',
    'baseline': '../experimental logs/2.1/training_20260314_171656_baseline.log',
    'timeout': '../experimental logs/2.2/training_20260314_205334_timeout_ablation.log',
    'sparse': '../experimental logs/2.3/training_20260314_213638_sparse_reward.log'
}

dfs = {}
for k, v in logs.items():
    if os.path.exists(v):
        try:
            dfs[k] = parse_log(v)
            dfs[k].to_csv(f'{k}_parsed.csv', index=False)
            print(f"Parsed {k}, shape {dfs[k].shape}")
        except Exception as e:
            print(f"Failed to parse {k}: {e}")
    else:
        print(f"File not found: {v}")

os.makedirs('figures', exist_ok=True)

# 1.1 Sparse Reward Progression
if 'training' in dfs:
    plt.figure(figsize=(10, 5))
    df_t = dfs['training']
    if 'sparse_reward' in df_t.columns:
        plt.plot(df_t['interval'], df_t['sparse_reward'].rolling(20).mean(), label='Training (PPO Factored Policy)')
    if 'baseline' in dfs and 'sparse_reward' in dfs['baseline'].columns:
        df_b = dfs['baseline']
        plt.plot(df_b['interval'], df_b['sparse_reward'].rolling(20).mean(), label='Random Baseline')
    if 'sparse' in dfs and 'total_reward' in dfs['sparse'].columns:
        df_inv = dfs['sparse']
        plt.plot(df_inv['interval'], df_inv['total_reward'].rolling(20).mean(), label='Sparse Reward Only (No Shaping)')
        
    plt.title('Agent Performance: Sparse Rewards over Training Intervals')
    plt.xlabel('Training Interval')
    plt.ylabel('Smoothed Sparse Reward')
    plt.legend()
    plt.tight_layout()
    plt.savefig('figures/reward_progression.png')
    plt.close()

# 1.2 Reward Components Breakdown
if 'training' in dfs:
    df_t = dfs['training'].fillna(0)
    cols_to_plot = [c for c in df_t.columns if c.endswith('_total') and c != 'total_reward' and c != 'sparse_reward']
    if cols_to_plot:
        plt.figure(figsize=(12, 6))
        for c in ['aim_hold_total', 'proximity_total', 'pitch_control_total', 'good_aim_total', 'damage_dealt_total']:
            if c in cols_to_plot:
                plt.plot(df_t['interval'], df_t[c].rolling(50).mean(), label=c.replace('_total', ''))
        plt.title('Reward Components Over Time (Smoothed)')
        plt.xlabel('Training Interval')
        plt.ylabel('Accumulated Reward')
        plt.legend(loc='upper left')
        plt.tight_layout()
        plt.savefig('figures/reward_breakdown.png')
        plt.close()

# 1.3 Loss Data
if 'training' in dfs:
    df_t = dfs['training']
    if 'policy_loss' in df_t.columns and 'value_loss' in df_t.columns:
        fig, ax1 = plt.subplots(figsize=(10,5))
        ax1.plot(df_t['interval'], df_t['policy_loss'].rolling(20).mean(), label='Policy Loss', color='b')
        ax1.plot(df_t['interval'], df_t['value_loss'].rolling(20).mean(), label='Value Loss', color='g')
        ax1.set_xlabel('Training Interval')
        ax1.set_ylabel('Loss', color='k')
        
        if 'entropy' in df_t.columns:
            ax2 = ax1.twinx()
            ax2.plot(df_t['interval'], df_t['entropy'].rolling(20).mean(), label='Entropy', color='r', linestyle='--')
            ax2.set_ylabel('Entropy', color='r')
            
        fig.legend(loc="upper right", bbox_to_anchor=(0.9,0.9), bbox_transform=ax1.transAxes)
        plt.title('Loss Curves and Entropy')
        plt.tight_layout()
        plt.savefig('figures/loss_curves.png')
        plt.close()
        
print("Figures generated in 'figures/' directory.")
