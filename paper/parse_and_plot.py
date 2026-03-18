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
            # e.g. "Interval 1  |  2026-03-15 10:20:45  |  trigger: Bot7"
            parts = line.split("|")
            interval_num = int(re.search(r'Interval\s+(\d+)', parts[0]).group(1))
            current_interval['interval'] = interval_num
        elif line.startswith("Samples:"):
            current_interval['samples'] = int(re.search(r'Samples:\s+(\d+)', line).group(1))
        elif line.startswith("Total reward:"):
            current_interval['total_reward'] = float(re.search(r'Total reward:\s+([\-\+\d\.]+)', line).group(1))
        elif line.startswith("Sparse component"):
            try:
                current_interval['sparse_reward'] = float(re.search(r'Sparse component \(comparable\):\s+([\-\+\d\.]+)', line).group(1))
            except:
                current_interval['sparse_reward'] = 0.0
        elif line.startswith("Return mean:"):
            m = re.search(r'Return mean:\s+([\-\+\d\.]+)\s+std:\s+([\-\+\d\.]+)', line)
            current_interval['return_mean'] = float(m.group(1))
            current_interval['return_std'] = float(m.group(2))
        elif line.startswith("Loss:"):
            m = re.search(r'Loss:\s+([\-\+\d\.]+)\s+\(policy=([\-\+\d\.]+)\s+value=([\-\+\d\.]+)\)', line)
            if m:
                current_interval['loss'] = float(m.group(1))
                current_interval['policy_loss'] = float(m.group(2))
                current_interval['value_loss'] = float(m.group(3))
        elif line.startswith("Entropy:"):
            current_interval['entropy'] = float(re.search(r'Entropy:\s+([\-\+\d\.]+)', line).group(1))
        elif line.startswith("damage_dealt"):
            m = re.search(r'count=\s*(\d+)\s+total=\s*([\-\+\d\.]+)', line)
            if m:
                current_interval['damage_dealt_count'] = int(m.group(1))
                current_interval['damage_dealt_total'] = float(m.group(2))
                
    if current_interval:
        data.append(current_interval)
        
    df = pd.DataFrame(data)
    # Fill missing columns with 0
    if not df.empty:
        for col in ['damage_dealt_total']:
            if col not in df.columns:
                df[col] = 0.0
    return df

base_dir = '/home/ad.msoe.edu/edex/Cambium/Cambium'
logs = {
    'training': f'{base_dir}/backend/logs/training_20260315_101754.log',
    'baseline': f'{base_dir}/experimental logs/2.1/training_20260314_171656_baseline.log',
    'timeout': f'{base_dir}/experimental logs/2.2/training_20260314_205334_timeout_ablation.log',
    'sparse': f'{base_dir}/experimental logs/2.3/training_20260314_213638_sparse_reward.log'
}

dfs = {}
for k, v in logs.items():
    if os.path.exists(v):
        dfs[k] = parse_log(v)
        dfs[k].to_csv(f'{base_dir}/paper/{k}_parsed.csv', index=False)
        print(f"Parsed {k}, shape {dfs[k].shape}")
    else:
        print(f"File not found: {v}")

# Create Figures
os.makedirs(f'{base_dir}/paper/figures', exist_ok=True)

# 1.1 Reward Progression Over Training Intervals
if 'training' in dfs and 'baseline' in dfs:
    plt.figure(figsize=(10, 5))
    df_t = dfs['training']
    df_b = dfs['baseline']
    df_s = dfs.get('sparse')
    
    plt.plot(df_t['interval'], df_t['sparse_reward'].rolling(10).mean(), label='Training (Sparse Component)', alpha=0.8)
    if 'sparse_reward' in df_b.columns:
        plt.plot(df_b['interval'], df_b['sparse_reward'].rolling(10).mean(), label='Random Baseline', alpha=0.8)
    if df_s is not None and 'sparse_reward' in df_s.columns:
        plt.plot(df_s['interval'], df_s['total_reward'].rolling(10).mean(), label='Sparse Reward Only', alpha=0.8)

    plt.title('Sparse Reward Over Training Intervals')
    plt.xlabel('Interval')
    plt.ylabel('Smoothed Sparse Reward')
    plt.legend()
    plt.tight_layout()
    plt.savefig(f'{base_dir}/paper/figures/reward_progression.png')
    plt.close()

# 1.3 Loss Curves
if 'training' in dfs:
    df_t = dfs['training']
    if 'policy_loss' in df_t.columns and 'value_loss' in df_t.columns:
        fig, ax1 = plt.subplots(figsize=(10,5))
        ax1.plot(df_t['interval'], df_t['policy_loss'].rolling(10).mean(), label='Policy Loss', color='b')
        ax1.plot(df_t['interval'], df_t['value_loss'].rolling(10).mean(), label='Value Loss', color='g')
        ax1.set_xlabel('Interval')
        ax1.set_ylabel('Loss')
        
        ax2 = ax1.twinx()
        ax2.plot(df_t['interval'], df_t['entropy'].rolling(10).mean(), label='Entropy', color='r', linestyle='--')
        ax2.set_ylabel('Entropy')
        
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper right')
        
        plt.title('Loss Curves and Entropy')
        plt.tight_layout()
        plt.savefig(f'{base_dir}/paper/figures/loss_curves.png')
        plt.close()

# 1.6 Damage Dealt Over Time
if 'training' in dfs:
    df_t = dfs['training']
    if 'damage_dealt_total' in df_t.columns:
        plt.figure(figsize=(10, 5))
        plt.plot(df_t['interval'], df_t['damage_dealt_total'].rolling(10).mean(), label='Damage Dealt')
        plt.title('Smoothed Damage Dealt per Interval')
        plt.xlabel('Interval')
        plt.ylabel('Damage Reward')
        plt.legend()
        plt.tight_layout()
        plt.savefig(f'{base_dir}/paper/figures/damage_dealt.png')
        plt.close()

print("Done plotting.")
