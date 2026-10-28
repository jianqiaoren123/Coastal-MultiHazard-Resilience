
# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()
# This script is used to plot the DETAILED results of the acute hazard analysis.
# Figures 1-13 include boxplots, percentiles, or any distributional visualization, etc. 
# These figures need to be plotted with collecting all the data across all simulations and calculating detailed statistics first, then plotting. 

# The box: represents the interquartile range (IQR, 25th–75th percentile) of the data for each policy/metric.
# The horizontal line inside the box: the median value.
# The error bar (whiskers): the 95% confidence interval (CI) for the mean, calculated as mean ± 1.96 × (standard error).
# The diamond marker: the mean value for the data.
# The circles: individual data points that are considered “fliers” (outliers) by the boxplot algorithm, i.e., values 
# outside 1.5×IQR from the box.

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from dbfread import DBF

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (18, 6)
plt.rcParams['font.size'] = 10

# Number of iterations
N_ITER = 1000
# N_ITER = 10

# Define file paths
base_path = Path(f"{REPO_ROOT}/Simulations/Acute")
idu_path = Path(f"{REPO_ROOT}/Simulations/IDU/idu.dbf")
realign_idu_path = base_path / "Untargeted-Acute-Realign" / "Run0" / "idu_Year2101_Untargeted-Acute-Realign_Run0.dbf"

files = {
    'Baseline': {
        'EQ': base_path / 'Acute-Baseline' / 'Run0' / 'AcuteMetric' / 'EQ_M90_building_damage_detailed_Acute-Baseline_0.csv',
        'TSU': base_path / 'Acute-Baseline' / 'Run0' / 'AcuteMetric' / 'TSU_L1_MaxMF_building_damage_detailed_Acute-Baseline_0.csv',
        'Cumulative': base_path / 'Acute-Baseline' / 'Run0' / 'AcuteMetric' / 'Cumulative_building_damage_detailed_Acute-Baseline_0.csv'
    },
    'Protect': {
        'EQ': base_path / 'Untargeted-Acute-Protect' / 'Run0' / 'AcuteMetric' / 'EQ_M90_building_damage_detailed_Untargeted-Acute-Protect_0.csv',
        'TSU': base_path / 'Untargeted-Acute-Protect' / 'Run0' / 'AcuteMetric' / 'TSU_L1_MaxMF_building_damage_detailed_Untargeted-Acute-Protect_0.csv',
        'Cumulative': base_path / 'Untargeted-Acute-Protect' / 'Run0' / 'AcuteMetric' / 'Cumulative_building_damage_detailed_Untargeted-Acute-Protect_0.csv'
    },
    'Realign': {
        'EQ': base_path / 'Untargeted-Acute-Realign' / 'Run0' / 'AcuteMetric' / 'EQ_M90_building_damage_detailed_Untargeted-Acute-Realign_0.csv',
        'TSU': base_path / 'Untargeted-Acute-Realign' / 'Run0' / 'AcuteMetric' / 'TSU_L1_MaxMF_building_damage_detailed_Untargeted-Acute-Realign_0.csv',
        'Cumulative': base_path / 'Untargeted-Acute-Realign' / 'Run0' / 'AcuteMetric' / 'Cumulative_building_damage_detailed_Untargeted-Acute-Realign_0.csv'
    }
}

# Output paths
output_path = Path(f"{REPO_ROOT}/Results/Acute/")
output_path.mkdir(parents=True, exist_ok=True)
figure_output_path = output_path / "Acute_detailed"
figure_output_path.mkdir(parents=True, exist_ok=True)

# Color mapping
colors = {'Baseline': '#FF0000', 'Protect': '#00FF00', 'Realign': '#0000FF'}  # pure red, green, blue
darker_colors = {'Baseline': '#B20000', 'Protect': '#008000', 'Realign': '#000080'}  # darker pure red, green, blue


# Read IDU data for normalization (robust, only needed fields)
import struct
needed_fields = ['impr_value', 'TotalPop', 'BLDGVALUE']
field_types = {}
field_offsets = {}
field_lengths = {}
print("Reading IDU data for normalization (robust method)...")
with open(idu_path, 'rb') as f:
    header = f.read(32)
    num_records = struct.unpack('<I', header[4:8])[0]
    header_len = struct.unpack('<H', header[8:10])[0]
    record_len = struct.unpack('<H', header[10:12])[0]
    # Read field descriptors
    fields = []
    while True:
        field_desc = f.read(32)
        if field_desc[0] == 0x0D:
            break
        name = field_desc[:11].decode('ascii', errors='ignore').replace('\x00', '').strip()
        ftype = chr(field_desc[11])
        flen = field_desc[16]
        fields.append((name, ftype, flen))
    # Find offsets for needed fields
    offset = 1  # first byte is deletion flag
    for name, ftype, flen in fields:
        if name in needed_fields:
            field_types[name] = ftype
            field_offsets[name] = offset
            field_lengths[name] = flen
        offset += flen
    # Read records
    f.seek(header_len)
    data = {k: [] for k in needed_fields}
    for _ in range(num_records):
        rec = f.read(record_len)
        if not rec or rec[0] == 0x2A:  # deleted record
            continue
        for k in needed_fields:
            start = field_offsets[k]
            end = start + field_lengths[k]
            raw = rec[start:end]
            try:
                val = raw.decode('latin1', errors='ignore').strip()
                if val == '' or val is None:
                    data[k].append(np.nan)
                else:
                    data[k].append(float(val))
            except Exception:
                data[k].append(np.nan)
idu_df = pd.DataFrame(data)
idu_df = idu_df.dropna(subset=needed_fields)

# Read Realign IDU data to get REMOVED buildings
print("Reading Realign IDU data for REMOVED buildings...")
realign_idu_records = DBF(realign_idu_path, encoding='latin1')
realign_idu_df = pd.DataFrame(iter(realign_idu_records))

# Create mask for removed buildings (0 < REMOVED < 2070)
removed_mask = (realign_idu_df['REMOVED'] > 0) & (realign_idu_df['REMOVED'] < 2070)
removed_indices = realign_idu_df[removed_mask].index.tolist()
print(f"Number of removed buildings for Realign: {len(removed_indices)}")

# Create mask for buildings (impr_value > 10000) to filter damage data
building_mask = idu_df['impr_value'] > 10000
building_indices = idu_df[building_mask].index.tolist()
print(f"Number of buildings (impr_value > 10000): {len(building_indices)}")

# Calculate totals for normalization
total_buildings = len(building_indices)
total_population = idu_df['TotalPop'].sum()
total_property_value = idu_df[idu_df['impr_value'] > 10000]['BLDGVALUE'].sum()

print(f"Total buildings (impr_value > 10000): {total_buildings}")
print(f"Total population: {total_population}")
print(f"Total property value: ${total_property_value:,.2f}")
print("="*80)

# --- Helper function: create_boxplot ---
def create_boxplot(ax, policy_list, hazard, metric_key, ylabel, title, percent_total=None):
    data_list = []
    colors_list = []
    for policy in policy_list:
        iteration_sums = results[policy][hazard][metric_key]['iteration_sums']
        if percent_total is not None:
            iteration_sums = (iteration_sums / percent_total) * 100
        data_list.append(iteration_sums)
        colors_list.append(colors[policy])
    # Calculate 95% CI for custom whiskers
    means = [np.mean(data) for data in data_list]
    stds = [np.std(data, ddof=1) for data in data_list]
    n = len(data_list[0])
    ci_margins = [1.96 * std / np.sqrt(n) for std in stds]
    ci_lower = [mean - margin for mean, margin in zip(means, ci_margins)]
    ci_upper = [mean + margin for mean, margin in zip(means, ci_margins)]
    q1 = [np.percentile(data, 25) for data in data_list]
    q3 = [np.percentile(data, 75) for data in data_list]
    medians = [np.median(data) for data in data_list]
    bp = ax.bxp([{
        'whislo': ci_low,
        'q1': q1_val,
        'med': med,
        'mean': mean_val,
        'q3': q3_val,
        'whishi': ci_high,
        'fliers': []
    } for ci_low, q1_val, med, mean_val, q3_val, ci_high in 
        zip(ci_lower, q1, medians, means, q3, ci_upper)],
        positions=[i+1 for i in range(len(data_list))], widths=0.6, patch_artist=True,
        showmeans=True, meanline=False,
        boxprops=dict(linewidth=1.5),
        whiskerprops=dict(linewidth=1.5),
        capprops=dict(linewidth=1.5),
        medianprops=dict(color='black', linewidth=2),
        meanprops=dict(marker='D', markerfacecolor='darkred', markeredgecolor='darkred', markersize=6))
    # Color boxes
    for patch, color in zip(bp['boxes'], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_xticks([i+1 for i in range(len(data_list))])
    ax.set_xticklabels(policy_list, fontsize=11)
    ax.set_xlabel('Policy', fontsize=12, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')

def save_figure(figure, filename):
    """Save a figure as PNG and SVG in the detailed-figure directory."""
    figure.savefig(figure_output_path / f"{filename}.png", dpi=300, bbox_inches='tight')
    figure.savefig(figure_output_path / f"{filename}.svg", bbox_inches='tight')
    print(f"Saved: {figure_output_path / filename}.png and .svg")
    
def read_metric_columns(df, metric_prefix, n_iter=N_ITER):
    """Read columns for a specific metric across all iterations"""
    columns = [f'{metric_prefix}_iter_{i}' for i in range(n_iter)]
    return df[columns].values

def calculate_stats(data):
    """Calculate mean, std, and 95% CI for data across iterations"""
    # data shape: (n_rows, n_iterations)
    # Sum over rows for each iteration
    iteration_sums = data.sum(axis=0)
    
    mean = np.mean(iteration_sums)
    std = np.std(iteration_sums, ddof=1)
    n = len(iteration_sums)
    
    # 95% CI using 1.96 * std / sqrt(n)
    ci_margin = 1.96 * std / np.sqrt(n)
    ci_lower = mean - ci_margin
    ci_upper = mean + ci_margin
    
    # Coefficient of Variation
    cov = std / mean / np.sqrt(n) if mean != 0 else 0
    
    return {
        'mean': mean,
        'std': std,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'cov': cov,
        'iteration_sums': iteration_sums
    }


def calculate_damage_state_stats(df, ds_value, building_indices, n_iter=N_ITER):
    """Calculate stats for specific damage state or total damage (ds_value > 0)"""
    ds_columns = [f'DS_iter_{i}' for i in range(n_iter)]
    # Filter to only buildings (impr_value > 10000)
    ds_data = df.loc[building_indices, ds_columns].values
    
    if ds_value == '>0':
        # Count buildings with any damage (DS > 0)
        mask_data = (ds_data > 0).astype(int)
    else:
        # Count buildings with specific damage state
        mask_data = (ds_data == ds_value).astype(int)
    
    return calculate_stats(mask_data)


# Dictionary to store all results
results = {}
results_normalized = {}
cov_records = []

print("Reading data and calculating statistics...")
print("="*80)

# Process each policy and hazard type
for policy in ['Baseline', 'Protect', 'Realign']:
    results[policy] = {}
    results_normalized[policy] = {}
    
    for hazard in ['EQ', 'TSU', 'Cumulative']:
        print(f"\nProcessing {policy} - {hazard}...")
        
        filepath = files[policy][hazard]
        df = pd.read_csv(filepath)
        print(f"  Loaded: {len(df)} rows")
        
        # Process Realign data: set DS and rep_cost to 0 for removed buildings
        if policy == 'Realign':
            print(f"  Processing Realign data: zeroing out {len(removed_indices)} removed buildings...")
            # Zero out DS columns for removed buildings
            ds_columns = [f'DS_iter_{i}' for i in range(N_ITER)]
            df.loc[removed_indices, ds_columns] = 0
            
            # Zero out rep_cost columns for removed buildings  
            rep_cost_columns = [f'rep_cost_iter_{i}' for i in range(N_ITER)]
            df.loc[removed_indices, rep_cost_columns] = 0
        
        results[policy][hazard] = {}
        results_normalized[policy][hazard] = {}
        
        # 1. Damage State Distribution (absolute and normalized)
        print(f"  Calculating Damage State metrics...")
        for ds in [0, 1, 2, 3, 4, '>0']:
            ds_stats = calculate_damage_state_stats(df, ds, building_indices, N_ITER)
            results[policy][hazard][f'DS_{ds}'] = ds_stats
            record = {
                'Policy': policy,
                'Hazard': hazard,
                'Metric': f'DS_{ds}',
            }
            for i, value in enumerate(ds_stats['iteration_sums']):
                record[f'Iter_{i}'] = value
            record['Mean'] = ds_stats['mean']
            record['Std'] = ds_stats['std']
            record['CoV'] = ds_stats['cov']
            cov_records.append(record)
        
        # 2. Life Safety (Fatality, Injury, Casualty) - absolute and normalized
        print(f"  Calculating Life Safety metrics...")
        ftly_data = read_metric_columns(df, 'ls_ftly', N_ITER)
        injy_data = read_metric_columns(df, 'ls_injy', N_ITER)
        
        ftly_stats = calculate_stats(ftly_data)
        injy_stats = calculate_stats(injy_data)
        # Normalization removed
        
        # Calculate casualty (fatality + injury) for each iteration
        casualty_data = ftly_data + injy_data
        casualty_stats = calculate_stats(casualty_data)
        # Normalization removed
        
        results[policy][hazard]['Fatality'] = ftly_stats
        results[policy][hazard]['Injury'] = injy_stats
        results[policy][hazard]['Casualty'] = casualty_stats
        
        # Normalization removed
        
        for metric, stats in [('Fatality', ftly_stats), ('Injury', injy_stats), ('Casualty', casualty_stats)]:
            record = {
                'Policy': policy,
                'Hazard': hazard,
                'Metric': metric,
            }
            for i, value in enumerate(stats['iteration_sums']):
                record[f'Iter_{i}'] = value
            record['Mean'] = stats['mean']
            record['Std'] = stats['std']
            record['CoV'] = stats['cov']
            cov_records.append(record)
        
        # 3. Economic Loss - absolute and normalized
        print(f"  Calculating Economic Loss metrics...")
        econ_data = read_metric_columns(df, 'rep_cost', N_ITER)
        econ_stats = calculate_stats(econ_data)
        # Normalization removed
        
        results[policy][hazard]['Economic_Loss'] = econ_stats
        # Normalization removed
        
        record = {
            'Policy': policy,
            'Hazard': hazard,
            'Metric': 'Economic_Loss',
        }
        for i, value in enumerate(econ_stats['iteration_sums']):
            record[f'Iter_{i}'] = value
        record['Mean'] = econ_stats['mean']
        record['Std'] = econ_stats['std']
        record['CoV'] = econ_stats['cov']
        cov_records.append(record)
        
        # 4. Population Impacted - absolute and normalized
        print(f"  Calculating Population Impacted metrics...")
        pop_data = read_metric_columns(df, 'pop_impacted', N_ITER)
        pop_stats = calculate_stats(pop_data)
        # Normalization removed
        
        results[policy][hazard]['Population_Impacted'] = pop_stats
        # Normalization removed
        
        record = {
            'Policy': policy,
            'Hazard': hazard,
            'Metric': 'Population_Impacted',
        }
        for i, value in enumerate(pop_stats['iteration_sums']):
            record[f'Iter_{i}'] = value
        record['Mean'] = pop_stats['mean']
        record['Std'] = pop_stats['std']
        record['CoV'] = pop_stats['cov']
        cov_records.append(record)

# Save CoV results and baseline statistics
print("\n" + "="*80)
print("Saving statistics and CoV results...")

# Create baseline statistics summary
baseline_stats = pd.DataFrame([
    {'Metric': 'Total_Buildings', 'Value': total_buildings, 'Unit': 'count', 'Description': 'Total buildings with impr_value > 10000'},
    {'Metric': 'Total_Population', 'Value': total_population, 'Unit': 'people', 'Description': 'Total population in Tillamook'},
    {'Metric': 'Total_Property_Value', 'Value': total_property_value / 1e6, 'Unit': 'million $', 'Description': 'Total building value for buildings with impr_value > 10000'}
])

# Save baseline statistics
baseline_stats.to_csv(output_path / "TotalNumber_Statistics.csv", index=False)
print(f"Saved: {output_path / 'TotalNumber_Statistics.csv'}")

# Save per-simulation statistics results
iter_columns = [f'Iter_{i}' for i in range(N_ITER)]
cov_df = pd.DataFrame(cov_records)
cov_df = cov_df[["Policy", "Hazard", "Metric", *iter_columns, "Mean", "Std", "CoV"]]
cov_df.to_csv(output_path / "Statistics_Acute_PerSim.csv", index=False)
print(f"Saved: {output_path / 'Statistics_Acute_PerSim.csv'}")

# Create box plot function with 95% CI whiskers
# Figure 1: Damage State Distribution
print("\n" + "="*80)
print("Creating Figure 1: Damage State Distribution...")
fig1, axes = plt.subplots(1, 3, figsize=(18, 6))
policy_list = ['Baseline', 'Protect', 'Realign']

for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    
    # Prepare data for all damage states as box plots
    ds_labels = ['DS 0', 'DS 1', 'DS 2', 'DS 3', 'DS 4', 'DS >0']
    ds_keys = [0, 1, 2, 3, 4, '>0']
    
    # Collect data for each damage state across all policies
    positions_list = []
    data_list = []
    colors_list = []
    pos = 1
    
    for ds in ds_keys:
        for policy in policy_list:
            iteration_sums = results[policy][hazard][f'DS_{ds}']['iteration_sums']
            data_list.append(iteration_sums)
            positions_list.append(pos)
            colors_list.append(colors[policy])
            pos += 1
        pos += 0.5  # Add space between damage states
    
    # Calculate 95% CI for custom whiskers
    means = [np.mean(data) for data in data_list]
    stds = [np.std(data, ddof=1) for data in data_list]
    n = len(data_list[0])
    ci_margins = [1.96 * std / np.sqrt(n) for std in stds]
    ci_lower = [mean - margin for mean, margin in zip(means, ci_margins)]
    ci_upper = [mean + margin for mean, margin in zip(means, ci_margins)]
    q1 = [np.percentile(data, 25) for data in data_list]
    q3 = [np.percentile(data, 75) for data in data_list]
    medians = [np.median(data) for data in data_list]
    
    bp = ax.bxp([{
        'whislo': ci_low,
        'q1': q1_val,
        'med': med,
        'mean': mean_val,
        'q3': q3_val,
        'whishi': ci_high,
        'fliers': []
    } for ci_low, q1_val, med, mean_val, q3_val, ci_high in 
        zip(ci_lower, q1, medians, means, q3, ci_upper)],
        positions=positions_list, widths=0.25, patch_artist=True,
        showmeans=True, meanline=False,
        boxprops=dict(linewidth=1.5),
        whiskerprops=dict(linewidth=1.5),
        capprops=dict(linewidth=1.5),
        medianprops=dict(color='black', linewidth=2),
        meanprops=dict(marker='D', markerfacecolor='darkred', markeredgecolor='darkred', markersize=6))
    
    # Color boxes
    for patch, color in zip(bp['boxes'], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    
    # Set x-axis labels
    ds_positions = [2, 5.5, 9, 12.5, 16, 19.5]
    ax.set_xticks(ds_positions)
    ax.set_xticklabels(ds_labels, fontsize=10)
    ax.set_xlabel('Damage State', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Buildings', fontsize=12, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    # Set custom hazard label for title
    if hazard == 'EQ':
        pretty_hazard = 'Earthquake'
    elif hazard == 'TSU':
        pretty_hazard = 'Tsunami'
    elif hazard == 'Cumulative':
        pretty_hazard = 'Earthquake+Tsunami'
    else:
        pretty_hazard = hazard_label
    ax.set_title(f'{pretty_hazard} Damage State Distribution', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Legend: only on the second subplot (idx == 1)
    if idx == 1:
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=colors[p], alpha=0.6, label=p) for p in policy_list]
        ax.legend(handles=legend_elements, fontsize=11, loc='upper right', frameon=False)

plt.tight_layout()
save_figure(fig1, "Fig1_Damage_State_Distribution")
plt.close()

# Figure 2: Population Impacted Distribution
print("Creating Figure 2: Population Impacted Distribution...")
fig2, axes = plt.subplots(1, 3, figsize=(18, 6))

for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    # Set custom hazard label for title
    if hazard == 'EQ':
        pretty_hazard = 'Earthquake'
    elif hazard == 'TSU':
        pretty_hazard = 'Tsunami'
    elif hazard == 'Cumulative':
        pretty_hazard = 'Earthquake+Tsunami'
    else:
        pretty_hazard = hazard
    create_boxplot(axes[idx], policy_list, hazard, 'Population_Impacted',
                   'Population Impacted', f'{pretty_hazard} Population Impacted Distribution')

plt.tight_layout()
save_figure(fig2, "Fig2_Population_Impacted_Distribution")
plt.close()

# Figure 3: Life Safety Distribution
print("Creating Figure 3: Life Safety Distribution...")
fig3, axes = plt.subplots(1, 3, figsize=(18, 6))

for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    
    # Prepare data for life safety metrics as box plots
    ls_labels = ['Fatality', 'Injury', 'Casualty']
    ls_keys = ['Fatality', 'Injury', 'Casualty']
    
    # Collect data for each metric across all policies
    positions_list = []
    data_list = []
    colors_list = []
    pos = 1
    
    for metric in ls_keys:
        for policy in policy_list:
            iteration_sums = results[policy][hazard][metric]['iteration_sums']
            data_list.append(iteration_sums)
            positions_list.append(pos)
            colors_list.append(colors[policy])
            pos += 1
        pos += 0.5  # Add space between metrics
    
    # Calculate 95% CI for custom whiskers
    means = [np.mean(data) for data in data_list]
    stds = [np.std(data, ddof=1) for data in data_list]
    n = len(data_list[0])
    ci_margins = [1.96 * std / np.sqrt(n) for std in stds]
    ci_lower = [mean - margin for mean, margin in zip(means, ci_margins)]
    ci_upper = [mean + margin for mean, margin in zip(means, ci_margins)]
    q1 = [np.percentile(data, 25) for data in data_list]
    q3 = [np.percentile(data, 75) for data in data_list]
    medians = [np.median(data) for data in data_list]
    
    bp = ax.bxp([{
        'whislo': ci_low,
        'q1': q1_val,
        'med': med,
        'mean': mean_val,
        'q3': q3_val,
        'whishi': ci_high,
        'fliers': []
    } for ci_low, q1_val, med, mean_val, q3_val, ci_high in 
        zip(ci_lower, q1, medians, means, q3, ci_upper)],
        positions=positions_list, widths=0.25, patch_artist=True,
        showmeans=True, meanline=False,
        boxprops=dict(linewidth=1.5),
        whiskerprops=dict(linewidth=1.5),
        capprops=dict(linewidth=1.5),
        medianprops=dict(color='black', linewidth=2),
        meanprops=dict(marker='D', markerfacecolor='darkred', markeredgecolor='darkred', markersize=6))
    
    # Color boxes
    for patch, color in zip(bp['boxes'], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    
    # Set x-axis labels
    metric_positions = [2, 5.5, 9]
    ax.set_xticks(metric_positions)
    ax.set_xticklabels(ls_labels, fontsize=11)
    ax.set_xlabel('Life Safety', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of People', fontsize=12, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    # Set custom hazard label for title
    if hazard == 'EQ':
        pretty_hazard = 'Earthquake'
    elif hazard == 'TSU':
        pretty_hazard = 'Tsunami'
    elif hazard == 'Cumulative':
        pretty_hazard = 'Earthquake+Tsunami'
    else:
        pretty_hazard = hazard_label
    ax.set_title(f'{pretty_hazard} Life Safety Distribution', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Legend
    # Legend removed as requested

plt.tight_layout()
save_figure(fig3, "Fig3_Life_Safety_Distribution")
plt.close()

# Figure 4: Economic Loss Distribution
print("Creating Figure 4: Economic Loss Distribution...")

# New custom figure: Direct Economic Loss, Protect vs Baseline (green), Realign vs Baseline (red)
print("Creating Custom Figure: Direct Economic Loss Comparison...")
fig_custom, axes_custom = plt.subplots(1, 3, figsize=(18, 6))

hazards = ['EQ', 'TSU', 'Cumulative']
bar_width = 0.35
bar_labels = ['EQ', 'TSU', 'EQ+TSU', 'EQ', 'TSU', 'EQ+TSU']

for idx, hazard in enumerate(hazards):
    ax = axes_custom[idx]
    # Get mean direct economic loss for each case
    # Protect vs Baseline (green)
    protect_loss = results['Protect'][hazard]['Economic_Loss']['iteration_sums']
    baseline_loss = results['Baseline'][hazard]['Economic_Loss']['iteration_sums']
    mean_protect = np.mean(protect_loss)
    mean_baseline = np.mean(baseline_loss)
    # Realign vs Baseline (red)
    realign_loss = results['Realign'][hazard]['Economic_Loss']['iteration_sums']
    mean_realign = np.mean(realign_loss)

    # Plot bars: left (Protect vs Baseline, green), right (Realign vs Baseline, red)
    ax.bar(0, mean_protect - mean_baseline, color='green', width=bar_width, label='Protect vs Baseline')
    ax.bar(1, mean_realign - mean_baseline, color='red', width=bar_width, label='Realign vs Baseline')

    # X-axis labels
    ax.set_xticks([0, 1])
    ax.set_xticklabels([hazard, hazard], fontsize=12)
    ax.set_xlabel('')
    ax.set_ylabel('Direct Economic Loss Difference (M$)', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    # No subplot title
    # Add legend only to first subplot
    if idx == 0:
        ax.legend(fontsize=12, loc='upper right', frameon=False)

plt.tight_layout()
save_figure(fig_custom, "Fig_Custom_Economic_Loss_Comparison")
plt.close()

# Figure 5: Damage State (raw values, not normalized)
print("Creating Figure 5: Damage State (raw values)...")
fig5, axes = plt.subplots(1, 3, figsize=(18, 6))
for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    ds_labels = ['DS 0', 'DS 1', 'DS 2', 'DS 3', 'DS 4', 'DS >0']
    for ds_idx, ds in enumerate([0, 1, 2, 3, 4, '>0']):
        data = results['Baseline'][hazard][f'DS_{ds}']['iteration_sums']
        ax.boxplot(data, positions=[ds_idx+1], widths=0.6, patch_artist=True,
                   boxprops=dict(facecolor=colors['Baseline'], alpha=0.6))
    ax.set_xticks(range(1, 7))
    ax.set_xticklabels(ds_labels, fontsize=9)
    ax.set_xlabel('Damage State', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Buildings', fontsize=12, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    if hazard == 'EQ':
        pretty_hazard = 'Earthquake'
    elif hazard == 'TSU':
        pretty_hazard = 'Tsunami'
    elif hazard == 'Cumulative':
        pretty_hazard = 'Earthquake+Tsunami'
    else:
        pretty_hazard = hazard_label
    ax.set_title(f'{pretty_hazard} Damage State (Raw)', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
save_figure(fig5, "Fig5_Damage_State_Raw")
plt.close()



# Figure 6: Life Safety (raw values, not normalized)
print("Creating Figure 6: Life Safety (raw values)...")
fig6, axes = plt.subplots(1, 3, figsize=(18, 6))
for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    ls_labels = ['Fatality', 'Injury', 'Casualty']
    for metric_idx, metric in enumerate(['Fatality', 'Injury', 'Casualty']):
        data = results['Baseline'][hazard][metric]['iteration_sums']
        ax.boxplot(data, positions=[metric_idx+1], widths=0.6, patch_artist=True,
                   boxprops=dict(facecolor=colors['Baseline'], alpha=0.6))
    ax.set_xticks(range(1, 4))
    ax.set_xticklabels(ls_labels, fontsize=11)
    ax.set_xlabel('Life Safety Metric', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of People', fontsize=12, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    if hazard == 'EQ':
        pretty_hazard = 'Earthquake'
    elif hazard == 'TSU':
        pretty_hazard = 'Tsunami'
    elif hazard == 'Cumulative':
        pretty_hazard = 'Earthquake+Tsunami'
    else:
        pretty_hazard = hazard_label
    ax.set_title(f'{pretty_hazard} Life Safety (Raw)', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
save_figure(fig6, "Fig6_Life_Safety_Raw")
plt.close()



# Figure 7: Economic Loss (raw values, not normalized)
print("Creating Figure 7: Economic Loss (raw values)...")
fig7, axes = plt.subplots(1, 3, figsize=(18, 6))
for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    data = results['Baseline'][hazard]['Economic_Loss']['iteration_sums']
    ax.boxplot(data, positions=[1], widths=0.6, patch_artist=True,
               boxprops=dict(facecolor=colors['Baseline'], alpha=0.6))
    ax.set_xticks([1])
    ax.set_xticklabels(['Economic Loss'], fontsize=11)
    ax.set_xlabel('Metric', fontsize=12, fontweight='bold')
    ax.set_ylabel('Economic Loss (USD)', fontsize=12, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    if hazard == 'EQ':
        pretty_hazard = 'Earthquake'
    elif hazard == 'TSU':
        pretty_hazard = 'Tsunami'
    elif hazard == 'Cumulative':
        pretty_hazard = 'Earthquake+Tsunami'
    else:
        pretty_hazard = hazard_label
    ax.set_title(f'{pretty_hazard} Economic Loss (Raw)', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
save_figure(fig7, "Fig7_Economic_Loss_Raw")
plt.close()



# Figure 8: Population Impacted (raw values, not normalized)
print("Creating Figure 8: Population Impacted (raw values)...")
fig8, axes = plt.subplots(1, 3, figsize=(18, 6))
for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    data = results['Baseline'][hazard]['Population_Impacted']['iteration_sums']
    ax.boxplot(data, positions=[1], widths=0.6, patch_artist=True,
               boxprops=dict(facecolor=colors['Baseline'], alpha=0.6))
    ax.set_xticks([1])
    ax.set_xticklabels(['Population Impacted'], fontsize=11)
    ax.set_xlabel('Metric', fontsize=12, fontweight='bold')
    ax.set_ylabel('Population Impacted', fontsize=12, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    if hazard == 'EQ':
        pretty_hazard = 'Earthquake'
    elif hazard == 'TSU':
        pretty_hazard = 'Tsunami'
    elif hazard == 'Cumulative':
        pretty_hazard = 'Earthquake+Tsunami'
    else:
        pretty_hazard = hazard_label
    ax.set_title(f'{pretty_hazard} Population Impacted (Raw)', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
save_figure(fig8, "Fig8_Population_Impacted_Raw")
plt.close()

# ============================================================================
# CHANGE FIGURES (Fig 9-12): Difference from Baseline (absolute numbers)
# ============================================================================

# Figure 9: Damage State Change from Baseline
print("Creating Figure 9: Damage State Change from Baseline...")
fig9, axes = plt.subplots(1, 3, figsize=(18, 6))
active_policies = ['Protect', 'Realign']

for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    
    ds_labels = ['DS 0\n(No damage)', 'DS 1\n(Slight)', 'DS 2\n(Moderate)', 
                 'DS 3\n(Extensive)', 'DS 4\n(Complete)', 'DS >0\n(Damage)']
    
    # Prepare data for box plots
    for ds_idx, ds in enumerate([0, 1, 2, 3, 4, '>0']):
        positions = []
        data_list = []
        
        for p_idx, policy in enumerate(active_policies):
            position = ds_idx * 2 + p_idx * 0.35
            positions.append(position)
            
            # Calculate change from Baseline for each iteration
            baseline_iters = results['Baseline'][hazard][f'DS_{ds}']['iteration_sums']
            policy_iters = results[policy][hazard][f'DS_{ds}']['iteration_sums']
            change_iters = policy_iters - baseline_iters
            data_list.append(change_iters)
        
        # Calculate 95% CI for custom whiskers
        means = [np.mean(data) for data in data_list]
        stds = [np.std(data, ddof=1) for data in data_list]
        n = len(data_list[0])
        ci_margins = [1.96 * std / np.sqrt(n) for std in stds]
        ci_lower = [mean - margin for mean, margin in zip(means, ci_margins)]
        ci_upper = [mean + margin for mean, margin in zip(means, ci_margins)]
        q1 = [np.percentile(data, 25) for data in data_list]
        q3 = [np.percentile(data, 75) for data in data_list]
        medians = [np.median(data) for data in data_list]
        
        # Create box plots with 95% CI whiskers
        bp = ax.bxp([{
            'whislo': ci_low,
            'q1': q1_val,
            'med': med,
            'mean': mean_val,
            'q3': q3_val,
            'whishi': ci_high,
            'fliers': []
        } for ci_low, q1_val, med, mean_val, q3_val, ci_high in 
            zip(ci_lower, q1, medians, means, q3, ci_upper)],
            positions=positions, widths=0.35, patch_artist=True,
            showfliers=False, manage_ticks=False,
            boxprops=dict(alpha=0.6),
            medianprops=dict(color='black', linewidth=1.5),
            whiskerprops=dict(linewidth=1.5),
            capprops=dict(linewidth=1.5))
        
        # Color boxes and add mean markers
        for patch, policy in zip(bp['boxes'], active_policies):
            patch.set_facecolor(colors[policy])
        
        # Add mean markers
        for pos, data, policy in zip(positions, data_list, active_policies):
            ax.plot(pos, np.mean(data), marker='D', color='darkred', 
                   markersize=6, zorder=3, markerfacecolor='darkred')
    
    # Add horizontal zero line
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.7)
    
    # Set x-axis
    ax.set_xlabel('Damage State', fontsize=12, fontweight='bold')
    ax.set_ylabel('Change in Number of Buildings', fontsize=12, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    ax.set_title(f'{hazard_label} Damage State Change', fontsize=13, fontweight='bold')
    ax.set_xticks([i * 2 + 0.175 for i in range(6)])
    ax.set_xticklabels(ds_labels, fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Legend only on the rightmost subplot
    if idx == 2:
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=colors[p], alpha=0.6, label=f'{p} vs Baseline') for p in active_policies]
        ax.legend(handles=legend_elements, fontsize=11, loc='upper right', frameon=False)

plt.tight_layout()
save_figure(fig9, "Fig9_Damage_State_Change")
plt.close()

# Figure 10: Life Safety Change from Baseline
print("Creating Figure 10: Life Safety Change from Baseline...")
fig10, axes = plt.subplots(1, 3, figsize=(18, 6))

for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    
    ls_labels = ['Fatality', 'Injury', 'Casualty']
    
    # Prepare data for box plots
    for metric_idx, metric in enumerate(['Fatality', 'Injury', 'Casualty']):
        positions = []
        data_list = []
        
        for p_idx, policy in enumerate(active_policies):
            position = metric_idx * 2 + p_idx * 0.35
            positions.append(position)
            
            # Calculate change from Baseline for each iteration
            baseline_iters = results['Baseline'][hazard][metric]['iteration_sums']
            policy_iters = results[policy][hazard][metric]['iteration_sums']
            change_iters = policy_iters - baseline_iters
            data_list.append(change_iters)
        
        # Calculate 95% CI for custom whiskers
        means = [np.mean(data) for data in data_list]
        stds = [np.std(data, ddof=1) for data in data_list]
        n = len(data_list[0])
        ci_margins = [1.96 * std / np.sqrt(n) for std in stds]
        ci_lower = [mean - margin for mean, margin in zip(means, ci_margins)]
        ci_upper = [mean + margin for mean, margin in zip(means, ci_margins)]
        q1 = [np.percentile(data, 25) for data in data_list]
        q3 = [np.percentile(data, 75) for data in data_list]
        medians = [np.median(data) for data in data_list]
        
        # Create box plots with 95% CI whiskers
        bp = ax.bxp([{
            'whislo': ci_low,
            'q1': q1_val,
            'med': med,
            'mean': mean_val,
            'q3': q3_val,
            'whishi': ci_high,
            'fliers': []
        } for ci_low, q1_val, med, mean_val, q3_val, ci_high in 
            zip(ci_lower, q1, medians, means, q3, ci_upper)],
            positions=positions, widths=0.35, patch_artist=True,
            showfliers=False, manage_ticks=False,
            boxprops=dict(alpha=0.6),
            medianprops=dict(color='black', linewidth=1.5),
            whiskerprops=dict(linewidth=1.5),
            capprops=dict(linewidth=1.5))
        
        # Color boxes and add mean markers
        for patch, policy in zip(bp['boxes'], active_policies):
            patch.set_facecolor(colors[policy])
        
        # Add mean markers
        for pos, data, policy in zip(positions, data_list, active_policies):
            ax.plot(pos, np.mean(data), marker='D', color='darkred', 
                   markersize=6, zorder=3, markerfacecolor='darkred')
    
    # Add horizontal zero line
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.7)
    
    # Set x-axis
    ax.set_xlabel('Life Safety Metric', fontsize=12, fontweight='bold')
    ax.set_ylabel('Change in Number of People', fontsize=12, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    ax.set_title(f'{hazard_label} Life Safety Change', fontsize=13, fontweight='bold')
    ax.set_xticks([i * 2 + 0.175 for i in range(3)])
    ax.set_xticklabels(ls_labels, fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Legend only on the rightmost subplot
    if idx == 2:
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=colors[p], alpha=0.6, label=f'{p} vs Baseline') for p in active_policies]
        ax.legend(handles=legend_elements, fontsize=11, loc='upper right', frameon=False)

plt.tight_layout()
save_figure(fig10, "Fig10_Life_Safety_Change")
plt.close()

# Figure 11: Economic Loss Change from Baseline
print("Creating Figure 11: Economic Loss Change from Baseline...")
fig11, axes = plt.subplots(1, 3, figsize=(18, 6))

for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    
    positions = []
    data_list = []
    labels = []
    box_colors = []
    
    pos = 1
    for policy in active_policies:
        baseline_iters = results['Baseline'][hazard]['Economic_Loss']['iteration_sums']
        policy_iters = results[policy][hazard]['Economic_Loss']['iteration_sums']
        change_iters = (policy_iters - baseline_iters) / 1e6  # Convert to M$
        
        data_list.append(change_iters)
        positions.append(pos)
        labels.append(f'{policy} vs Baseline')
        box_colors.append(colors[policy])
        pos += 1
    
    # Calculate 95% CI for custom whiskers
    means = [np.mean(data) for data in data_list]
    stds = [np.std(data, ddof=1) for data in data_list]
    n = len(data_list[0])
    ci_margins = [1.96 * std / np.sqrt(n) for std in stds]
    ci_lower = [mean - margin for mean, margin in zip(means, ci_margins)]
    ci_upper = [mean + margin for mean, margin in zip(means, ci_margins)]
    q1 = [np.percentile(data, 25) for data in data_list]
    q3 = [np.percentile(data, 75) for data in data_list]
    medians = [np.median(data) for data in data_list]
    
    bp = ax.bxp([{
        'whislo': ci_low,
        'q1': q1_val,
        'med': med,
        'mean': mean_val,
        'q3': q3_val,
        'whishi': ci_high,
        'fliers': []
    } for ci_low, q1_val, med, mean_val, q3_val, ci_high in 
        zip(ci_lower, q1, medians, means, q3, ci_upper)],
        positions=positions, widths=0.6, patch_artist=True,
        showmeans=True, meanline=True,
        boxprops=dict(linewidth=1.5),
        whiskerprops=dict(linewidth=1.5),
        capprops=dict(linewidth=1.5),
        medianprops=dict(color='black', linewidth=2),
        meanprops=dict(color='darkred', linewidth=2, linestyle='--'))
    
    for patch, color in zip(bp['boxes'], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.7)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=11, fontweight='bold')
    ax.set_ylabel('Change in Economic Loss (M$)', fontsize=12, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    ax.set_title(f'{hazard_label} Economic Loss Change', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)

plt.tight_layout()
save_figure(fig11, "Fig11_Economic_Loss_Change")
plt.close()

# Figure 12: Population Impacted Change from Baseline
print("Creating Figure 12: Population Impacted Change from Baseline...")
fig12, axes = plt.subplots(1, 3, figsize=(18, 6))

for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    
    positions = []
    data_list = []
    labels = []
    box_colors = []
    
    pos = 1
    for policy in active_policies:
        baseline_iters = results['Baseline'][hazard]['Population_Impacted']['iteration_sums']
        policy_iters = results[policy][hazard]['Population_Impacted']['iteration_sums']
        change_iters = policy_iters - baseline_iters
        
        data_list.append(change_iters)
        positions.append(pos)
        labels.append(f'{policy} vs Baseline')
        box_colors.append(colors[policy])
        pos += 1
    
    # Calculate 95% CI for custom whiskers
    means = [np.mean(data) for data in data_list]
    stds = [np.std(data, ddof=1) for data in data_list]
    n = len(data_list[0])
    ci_margins = [1.96 * std / np.sqrt(n) for std in stds]
    ci_lower = [mean - margin for mean, margin in zip(means, ci_margins)]
    ci_upper = [mean + margin for mean, margin in zip(means, ci_margins)]
    q1 = [np.percentile(data, 25) for data in data_list]
    q3 = [np.percentile(data, 75) for data in data_list]
    medians = [np.median(data) for data in data_list]
    
    bp = ax.bxp([{
        'whislo': ci_low,
        'q1': q1_val,
        'med': med,
        'mean': mean_val,
        'q3': q3_val,
        'whishi': ci_high,
        'fliers': []
    } for ci_low, q1_val, med, mean_val, q3_val, ci_high in 
        zip(ci_lower, q1, medians, means, q3, ci_upper)],
        positions=positions, widths=0.6, patch_artist=True,
        showmeans=True, meanline=True,
        boxprops=dict(linewidth=1.5),
        whiskerprops=dict(linewidth=1.5),
        capprops=dict(linewidth=1.5),
        medianprops=dict(color='black', linewidth=2),
        meanprops=dict(color='darkred', linewidth=2, linestyle='--'))
    
    for patch, color in zip(bp['boxes'], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.7)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=11, fontweight='bold')
    ax.set_ylabel('Change in Population Impacted', fontsize=12, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    ax.set_title(f'{hazard_label} Population Impacted Change', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)

plt.tight_layout()
save_figure(fig12, "Fig12_Population_Impacted_Change")
plt.close()

# ============================================================================
# PERCENTAGE CHANGE FIGURES (Fig 13-16): Percentage change from Baseline
# ============================================================================

# Figure 13: Damage State Percentage Change from Baseline
print("Creating Figure 13: Damage State Percentage Change from Baseline...")
fig13, axes = plt.subplots(1, 3, figsize=(18, 6))

for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    
    # Prepare data for box plots
    for ds_idx, ds in enumerate([0, 1, 2, 3, 4, '>0']):
        positions = []
        data_list = []
        
        for p_idx, policy in enumerate(active_policies):
            position = ds_idx * 2 + p_idx * 0.35
            positions.append(position)
            
            # Calculate percentage change from Baseline for each iteration
            baseline_iters = results['Baseline'][hazard][f'DS_{ds}']['iteration_sums']
            policy_iters = results[policy][hazard][f'DS_{ds}']['iteration_sums']
            change_iters = ((policy_iters - baseline_iters) / baseline_iters) * 100
            data_list.append(change_iters)
        
        # Calculate 95% CI for custom whiskers
        means = [np.mean(data) for data in data_list]
        stds = [np.std(data, ddof=1) for data in data_list]
        n = len(data_list[0])
        ci_margins = [1.96 * std / np.sqrt(n) for std in stds]
        ci_lower = [mean - margin for mean, margin in zip(means, ci_margins)]
        ci_upper = [mean + margin for mean, margin in zip(means, ci_margins)]
        q1 = [np.percentile(data, 25) for data in data_list]
        q3 = [np.percentile(data, 75) for data in data_list]
        medians = [np.median(data) for data in data_list]
        
        # Create box plots with 95% CI whiskers
        bp = ax.bxp([{
            'whislo': ci_low,
            'q1': q1_val,
            'med': med,
            'mean': mean_val,
            'q3': q3_val,
            'whishi': ci_high,
            'fliers': []
        } for ci_low, q1_val, med, mean_val, q3_val, ci_high in 
            zip(ci_lower, q1, medians, means, q3, ci_upper)],
            positions=positions, widths=0.35, patch_artist=True,
            showfliers=False, manage_ticks=False,
            boxprops=dict(alpha=0.6),
            medianprops=dict(color='black', linewidth=1.5),
            whiskerprops=dict(linewidth=1.5),
            capprops=dict(linewidth=1.5))
        
        # Color boxes and add mean markers with darker colors matching box colors
        for patch, policy in zip(bp['boxes'], active_policies):
            patch.set_facecolor(colors[policy])
        
        # Add mean markers with darker colors matching each policy's box color
        for pos, data, policy in zip(positions, data_list, active_policies):
            # Use darker version of the policy color for mean marker
            if policy == 'Protect':
                marker_color = '#1f7a1f'  # darker green
            elif policy == 'Realign':
                marker_color = '#0d4d8f'  # darker blue
            else:
                marker_color = '#a01d1d'  # darker red for Baseline
            ax.plot(pos, np.mean(data), marker='D', color=marker_color, 
                   markersize=6, zorder=3, markerfacecolor=marker_color)
    
    # Add horizontal zero line
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.7)
    
    # Cleaner x-axis labels without damage descriptors
    clean_ds_labels = ['DS 0', 'DS 1', 'DS 2', 'DS 3', 'DS 4', 'DS >0']
    
    # Set subplot title
    if hazard == 'EQ':
        ax.set_title('EQ', fontsize=18, fontweight='bold')
    elif hazard == 'TSU':
        ax.set_title('TSU', fontsize=18, fontweight='bold')
    elif hazard == 'Cumulative':
        ax.set_title('EQ+TSU', fontsize=18, fontweight='bold')
    
    # Set x-axis
    ax.set_xlabel('Damage State', fontsize=18, fontweight='bold')
    ax.set_ylabel('Percentage Change (%)', fontsize=18, fontweight='bold')
    hazard_label = 'Joint' if hazard == 'Cumulative' else hazard
    ax.set_xticks([i * 2 + 0.175 for i in range(6)])
    ax.set_xticklabels(clean_ds_labels, fontsize=18)
    ax.tick_params(axis='y', labelsize=18)
    ax.grid(True, alpha=0.3, axis='y')
    


# Add legend to Figure 13 (right top of subplot 3)
if len(axes) > 2:
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=colors[p], alpha=0.6, label=f'{p} vs Baseline') for p in active_policies if p != 'Baseline']
    axes[2].legend(handles=legend_elements, fontsize=18, loc='upper right', frameon=False)

plt.tight_layout()
save_figure(fig13, "Fig13_Damage_State_Percentage_Change")
plt.close()


# Figure 14: Life Safety Percentage Change from Baseline
print("Creating Figure 14: Life Safety Percentage Change from Baseline...")

fig14, axes = plt.subplots(1, 3, figsize=(18, 6))
ls_labels = ['Fatality', 'Injury', 'Casualty']
hazard_titles = ['EQ', 'TSU', 'EQ + TSU']
for idx, hazard in enumerate(['EQ', 'TSU', 'Cumulative']):
    ax = axes[idx]
    for metric_idx, metric in enumerate(['Fatality', 'Injury', 'Casualty']):
        positions = []
        data_list = []
        for p_idx, policy in enumerate(active_policies):
            position = metric_idx * 2 + p_idx * 0.35
            positions.append(position)
            baseline_iters = results['Baseline'][hazard][metric]['iteration_sums']
            policy_iters = results[policy][hazard][metric]['iteration_sums']
            change_iters = ((policy_iters - baseline_iters) / baseline_iters) * 100
            data_list.append(change_iters)
        means = [np.mean(data) for data in data_list]
        stds = [np.std(data, ddof=1) for data in data_list]
        n = len(data_list[0])
        ci_margins = [1.96 * std / np.sqrt(n) for std in stds]
        ci_lower = [mean - margin for mean, margin in zip(means, ci_margins)]
        ci_upper = [mean + margin for mean, margin in zip(means, ci_margins)]
        q1 = [np.percentile(data, 25) for data in data_list]
        q3 = [np.percentile(data, 75) for data in data_list]
        medians = [np.median(data) for data in data_list]
        bp = ax.bxp([{
            'whislo': ci_low,
            'q1': q1_val,
            'med': med,
            'mean': mean_val,
            'q3': q3_val,
            'whishi': ci_high,
            'fliers': []
        } for ci_low, q1_val, med, mean_val, q3_val, ci_high in 
            zip(ci_lower, q1, medians, means, q3, ci_upper)],
            positions=positions, widths=0.35, patch_artist=True,
            showfliers=False, manage_ticks=False,
            boxprops=dict(alpha=0.6),
            medianprops=dict(color='black', linewidth=1.5),
            whiskerprops=dict(linewidth=1.5),
            capprops=dict(linewidth=1.5))
        for patch, policy in zip(bp['boxes'], active_policies):
            patch.set_facecolor(colors[policy])
        for pos, data, policy in zip(positions, data_list, active_policies):
            ax.plot(pos, np.mean(data), marker='D', color='darkred', markersize=6, zorder=3, markerfacecolor='darkred')
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.7)
    # Set subplot title
    ax.set_title(hazard_titles[idx], fontsize=18, fontweight='bold')
    # Set x-ticks for each metric group
    ax.set_xticks([i * 2 + 0.175 for i in range(3)])
    ax.set_xticklabels(ls_labels, fontsize=16, fontweight='bold')
    # Add Life Safety as a second line below x-ticks
    ax.set_xlabel('Life Safety', fontsize=18, fontweight='bold', labelpad=16)
    ax.set_ylabel('Percentage Change (%)', fontsize=18, fontweight='bold')
    ax.tick_params(axis='y', labelsize=16)
    ax.grid(True, alpha=0.3, axis='y')
    # Add legend to the second panel only, positioned a little lower
    if idx == 1:
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=colors[p], alpha=0.6, label=f'{p} vs Baseline') for p in active_policies]
        ax.legend(handles=legend_elements, fontsize=18, loc='upper right', bbox_to_anchor=(1, 0.75), frameon=False)
plt.tight_layout()
save_figure(fig14, "Fig14_Life_Safety_Percentage_Change")
plt.close()


# Figure 15: Economic Loss Percentage Change from Baseline (3-panel)
print("Creating Figure 15: Economic Loss Percentage Change from Baseline (3-panel)...")
fig15, axes = plt.subplots(1, 3, figsize=(18, 6))
hazards = ['EQ', 'TSU', 'Cumulative']
hazard_titles = ['EQ', 'TSU', 'EQ + TSU']
policies = ['Protect', 'Realign']
color_map = {'Protect': colors['Protect'], 'Realign': colors['Realign']}
darker_map = {'Protect': darker_colors['Protect'], 'Realign': darker_colors['Realign']}

for idx, hazard in enumerate(hazards):
    ax = axes[idx]
    positions = []
    data_list = []
    for p_idx, policy in enumerate(policies):
        position = p_idx  # 0 for Protect, 1 for Realign
        positions.append(position)
        baseline_iters = results['Baseline'][hazard]['Economic_Loss']['iteration_sums']
        policy_iters = results[policy][hazard]['Economic_Loss']['iteration_sums']
        change_iters = ((policy_iters - baseline_iters) / baseline_iters) * 100
        data_list.append(change_iters)
    # Boxplot for Protect and Realign
    bp = ax.boxplot(data_list, positions=positions, widths=0.5, patch_artist=True,
                    showmeans=False,
                    boxprops=dict(linewidth=1.5),
                    whiskerprops=dict(linewidth=1.5),
                    capprops=dict(linewidth=1.5),
                    medianprops=dict(color='black', linewidth=2))
    for patch, policy in zip(bp['boxes'], policies):
        patch.set_facecolor(color_map[policy])
        patch.set_alpha(0.6)
    # Add mean markers
    for pos, data, policy in zip(positions, data_list, policies):
        marker_color = darker_map[policy]
        ax.plot(pos, np.mean(data), marker='D', color=marker_color, 
                markersize=8, zorder=3, markerfacecolor=marker_color)
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.7)
    # Set x-ticks (no labels)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['', ''])
    # Add Direct Economic Loss as xlabel below x-ticks
    ax.set_xlabel('Direct Economic Loss', fontsize=16, fontweight='bold', labelpad=16)
    ax.set_ylabel('Percentage Change (%)', fontsize=16, fontweight='bold')
    ax.set_title(hazard_titles[idx], fontsize=18, fontweight='bold')
    ax.tick_params(axis='y', labelsize=14)
    ax.grid(True, alpha=0.3, axis='y')
    # Add legend to the rightmost panel only, positioned a little lower
    if idx == 2:
        from matplotlib.patches import Patch
        legend_handles = [Patch(facecolor=color_map['Protect'], alpha=0.6, label='Protect vs Baseline'),
                          Patch(facecolor=color_map['Realign'], alpha=0.6, label='Realign vs Baseline')]
        ax.legend(handles=legend_handles, fontsize=18, loc='upper right', bbox_to_anchor=(1, 0.75), frameon=False)

plt.tight_layout()
save_figure(fig15, "Fig15_Economic_Loss_Percentage_Change")
plt.close()


# Figure 16: Population Impacted Percentage Change from Baseline (Combined Plot)

print("Creating Figure 16: Population Impacted Percentage Change from Baseline (3-panel)...")
fig16, axes = plt.subplots(1, 3, figsize=(18, 6))
hazards = ['EQ', 'TSU', 'Cumulative']
hazard_titles = ['EQ', 'TSU', 'EQ + TSU']
policies = ['Protect', 'Realign']
color_map = {'Protect': colors['Protect'], 'Realign': colors['Realign']}
darker_map = {'Protect': darker_colors['Protect'], 'Realign': darker_colors['Realign']}

for idx, hazard in enumerate(hazards):
    ax = axes[idx]
    positions = []
    data_list = []
    for p_idx, policy in enumerate(policies):
        position = p_idx  # 0 for Protect, 1 for Realign
        positions.append(position)
        baseline_iters = results['Baseline'][hazard]['Population_Impacted']['iteration_sums']
        policy_iters = results[policy][hazard]['Population_Impacted']['iteration_sums']
        change_iters = ((policy_iters - baseline_iters) / baseline_iters) * 100
        data_list.append(change_iters)
    # Boxplot for Protect and Realign
    bp = ax.boxplot(data_list, positions=positions, widths=0.5, patch_artist=True,
                    showmeans=False,
                    boxprops=dict(linewidth=1.5),
                    whiskerprops=dict(linewidth=1.5),
                    capprops=dict(linewidth=1.5),
                    medianprops=dict(color='black', linewidth=2))
    for patch, policy in zip(bp['boxes'], policies):
        patch.set_facecolor(color_map[policy])
        patch.set_alpha(0.6)
    # Add mean markers
    for pos, data, policy in zip(positions, data_list, policies):
        marker_color = darker_map[policy]
        ax.plot(pos, np.mean(data), marker='D', color=marker_color, 
                markersize=8, zorder=3, markerfacecolor=marker_color)
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.7)
    # Set x-ticks (no labels)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['', ''])
    # Add Population Impacted as xlabel below x-ticks
    ax.set_xlabel('Population Impacted', fontsize=16, fontweight='bold', labelpad=16)
    ax.set_ylabel('Percentage Change (%)', fontsize=16, fontweight='bold')
    ax.set_title(hazard_titles[idx], fontsize=18, fontweight='bold')
    ax.tick_params(axis='y', labelsize=14)
    ax.grid(True, alpha=0.3, axis='y')
    # Add legend to the rightmost panel only, positioned a little lower
    if idx == 2:
        from matplotlib.patches import Patch
        legend_handles = [Patch(facecolor=color_map['Protect'], alpha=0.6, label='Protect vs Baseline'),
                          Patch(facecolor=color_map['Realign'], alpha=0.6, label='Realign vs Baseline')]
        ax.legend(handles=legend_handles, fontsize=18, loc='upper right', bbox_to_anchor=(1, 0.75), frameon=False)

plt.tight_layout()
save_figure(fig16, "Fig16_Population_Impacted_Percentage_Change")
plt.close()

print("\n" + "="*80)
print("All figures, statistics, and Word documents have been saved successfully!")
print("="*80)
print(f"\nOutput location: {output_path}")
print("Files created:")
print("  - TotalNumber_Statistics.csv (Total buildings, population, property value)")
print("  - Statistics_Acute_PerSim.csv (Per-iteration values and summary stats for all metrics)")
print("  - Fig1_Damage_State_Distribution.png")
print("  - Fig2_Life_Safety_Distribution.png")
print("  - Fig3_Economic_Loss_Distribution.png")
print("  - Fig4_Population_Impacted_Distribution.png")
print("  - Fig5_Damage_State_Percentage.png")
print("  - Fig6_Life_Safety_Percentage.png")
print("  - Fig7_Economic_Loss_Percentage.png")
print("  - Fig8_Population_Impacted_Percentage.png")
print("  - Fig9_Damage_State_Change.png")
print("  - Fig10_Life_Safety_Change.png")
print("  - Fig11_Economic_Loss_Change.png")
print("  - Fig12_Population_Impacted_Change.png")
print("  - Fig13_Damage_State_Percentage_Change.png")
print("  - Fig14_Life_Safety_Percentage_Change.png")
print("  - Fig15_Economic_Loss_Percentage_Change.png")
print("  - Fig16_Population_Impacted_Percentage_Change.png")