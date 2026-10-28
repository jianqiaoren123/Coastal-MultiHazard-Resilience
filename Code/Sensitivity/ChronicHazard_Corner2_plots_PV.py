
# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()
# Corner2 PV figures and report tables.
#
# Figure outputs:
#   Main_CumulativeCost_PV_Corner2
#   Main_Physical_3x2_PV_Corner2
#   Main_Social_3x2_PV_Corner2
#   Main_Economic_3x2_PV_Corner2
#   Main_NPV_Corner2
#
# Report outputs:
#   Results_report_Chronic_PV_1_Corner2.csv
#   Results_report_Chronic_PV_2_Corner2.csv
#
# Output directory:
#   Results/Sensitivity/
#
# Physical and social panels e/f show absolute benefit per simulation divided by cumulative cost.
# Economic panels a/b show baseline data, c/d show relative benefit, and e/f show benefit divided by cumulative cost.
# Main_NPV_Corner2 shows six Protect/Realign curves across Low, Med, and High SLR scenarios with mean and 95% CI.

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import matplotlib as mpl

# --- Settings ---
N_ITER = 50
output_dir = f'{REPO_ROOT}/Results/Sensitivity/'
economic_dir = f'{REPO_ROOT}/Results/EconomicAnalysis/'
input_dir = Path(output_dir)
Path(output_dir).mkdir(parents=True, exist_ok=True)

# Color mapping
colors = {'Baseline': '#FF0000', 'Protect': '#00FF00', 'Realign': '#0000FF'}
slr_styles = {'Low': (':', 1), 'Med': ('--', 2), 'High': ('-', 2)}
slr_shades = {'Low': 0.2, 'Med': 0.4, 'High': 0.6}
slr_reds = {'Low': '#ffcccc', 'Med': '#ff6666', 'High': '#990000'}
slr_greens = {'Low': '#ccffcc', 'Med': '#66ff66', 'High': '#009900'}
slr_blues = {'Low': '#ccccff', 'Med': '#6666ff', 'High': '#000099'}

# Metrics and hazards
metric_hazard_list = [
    ("Damaged", 'Flooding'),
    ("Eroded", 'Erosion'),
    ("PopulationImpacted", 'Flooding'),
    ("PopulationImpacted", 'Erosion'),
    ("EconomicLoss", 'Flooding'),
    ("EconomicLoss", 'Erosion')
]
metric_labels = [
    'Percent Change in Flood-Damaged Buildings (%)',
    'Percent Change in Eroded Buildings (%)',
    'Percent Change in Population Impacted by Flooding (%)',
    'Percent Change in Population Impacted by Erosion (%)',
    'Percent Change in Economic Loss by Flooding (%)',
    'Percent Change in Economic Loss by Erosion (%)'
]
metric_labels_baseline = [
    'Annual Flood-Damaged Buildings (#)',
    'Cumulative Eroded Buildings (#)',
    'Population Impacted by Flooding (#)',
    'Population Impacted by Erosion (#)',
    'Economic Loss by Flooding (M$)',
    'Economic Loss by Erosion (M$)'
]
metric_labels_cb = [
    'Percent Change in Flood-Damaged Buildings / M$',
    'Percent Change in Eroded Buildings / M$',
    'Percent Change in Population Impacted by Flooding / M$',
    'Percent Change in Population Impacted by Erosion / M$',
    'Percent Change in Economic Loss by Flooding / M$',
    'Percent Change in Economic Loss by Erosion / M$'
]

slr_scenarios = ['Low', 'Med', 'High']
proactive_policies = ['Protect', 'Realign']

# --- Helper for 95% CI ---
def get_ci(std):
    return 1.96 * std / np.sqrt(N_ITER)


def normalize_simulation_columns(df):
    return df.rename(
        columns={column: column.split(' ')[0] for column in df.columns if column.startswith('Sim_')}
    )


def ratio_statistics(numerator, denominator, merge_keys, scale=1):
    simulation_columns = sorted(
        set(column for column in numerator.columns if column.startswith('Sim_'))
        & set(column for column in denominator.columns if column.startswith('Sim_')),
        key=lambda column: int(column.split('_')[1])
    )
    merged = numerator[merge_keys + simulation_columns].merge(
        denominator[merge_keys + simulation_columns],
        on=merge_keys,
        suffixes=('_numerator', '_denominator')
    )
    numerator_values = merged[[f'{column}_numerator' for column in simulation_columns]].to_numpy()
    denominator_values = merged[[f'{column}_denominator' for column in simulation_columns]].to_numpy()
    ratios = np.divide(
        numerator_values,
        denominator_values,
        out=np.full_like(numerator_values, np.nan, dtype=float),
        where=denominator_values != 0
    ) * scale
    result = merged[merge_keys].copy()
    result['Mean'] = np.nanmean(ratios, axis=1)
    result['Std'] = np.nanstd(ratios, axis=1, ddof=1)
    return result


def recalculate_simulation_statistics(df, simulation_columns):
    values = df[simulation_columns].to_numpy(dtype=float)
    df = df.copy()
    df['Mean'] = np.nanmean(values, axis=1)
    df['Std'] = np.nanstd(values, axis=1, ddof=1)
    df['CoV'] = np.where(
        df['Mean'] == 0,
        np.nan,
        df['Std'] / df['Mean'] / np.sqrt(len(simulation_columns))
    )
    return df


def adjusted_absolute_and_relative_benefits(absolute_df, metric_df):
    absolute_df = absolute_df.copy()
    simulation_columns = sorted(
        [column for column in absolute_df.columns if column.startswith('Sim_')],
        key=lambda column: int(column.split('_')[1])
    )
    absolute_df[simulation_columns] = absolute_df[simulation_columns].clip(upper=0)
    absolute_df = recalculate_simulation_statistics(absolute_df, simulation_columns)

    merge_keys = ['SLR', 'Hazard', 'Metric', 'Year']
    baseline = metric_df[
        (metric_df['Policy'] == 'Baseline')
    ][merge_keys + simulation_columns]
    merged = absolute_df[merge_keys + ['ProactivePolicy'] + simulation_columns].merge(
        baseline,
        on=merge_keys,
        suffixes=('', '_baseline')
    )
    relative_values = merged[simulation_columns].to_numpy(dtype=float)
    baseline_values = merged[[f'{column}_baseline' for column in simulation_columns]].to_numpy(dtype=float)
    with np.errstate(divide='ignore', invalid='ignore'):
        relative_values = np.divide(
            relative_values,
            baseline_values,
            out=np.full_like(relative_values, np.nan),
            where=baseline_values != 0
        ) * 100
    relative_df = merged[merge_keys + ['ProactivePolicy']].copy()
    relative_df[simulation_columns] = relative_values
    relative_df = recalculate_simulation_statistics(relative_df, simulation_columns)
    return absolute_df, relative_df

# --- Group 1: Detailed Figures ---
metric_df = pd.read_csv(Path(output_dir) / 'Statistics_Chronic_Corner2_Metric_PerSim.csv')
absolute_benefit = normalize_simulation_columns(pd.read_csv(
    Path(output_dir) / 'Statistics_Chronic_Corner2_AbsoluteBenefit_PerSim.csv'
))
absolute_benefit, rel_benefit = adjusted_absolute_and_relative_benefits(
    absolute_benefit,
    metric_df
)
cum_cost = pd.read_csv(Path(output_dir) / 'Statistics_Chronic_Corner2_CumulativeCost_PerSim.csv')


for i, (metric, hazard) in enumerate(metric_hazard_list):
    fig, axes = plt.subplots(2, 3, figsize=(18, 10), sharex=True)
    panel_labels = ['(a)', '(b)', '(c)', '(d)', '(e)', '(f)']
    # --- Calculate y-limits for top and bottom panels (Detailed) ---
    # Top panels: Relative Benefit
    top_ymins, top_ymaxs = [], []
    for col, slr in enumerate(slr_scenarios):
        df = rel_benefit[(rel_benefit['SLR'] == slr) & (rel_benefit['Hazard'] == hazard) & (rel_benefit['Metric'] == metric)]
        if not df.empty:
            mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
            vals = df['Mean'][mask]
            ci = get_ci(df['Std'][mask])
            top_ymins.append((vals - ci).min())
            top_ymaxs.append((vals + ci).max())
    top_ylim = (np.floor(min(top_ymins)), np.ceil(max(top_ymaxs))) if top_ymins else (None, None)
    # Bottom panels: Cumulative Cost
    bottom_ymins, bottom_ymaxs = [], []
    for col, slr in enumerate(slr_scenarios):
        df = cum_cost[(cum_cost['SLR'] == slr)]
        if not df.empty:
            mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
            vals = df['Mean'][mask]
            ci = get_ci(df['Std'][mask])
            bottom_ymins.append((vals - ci).min())
            bottom_ymaxs.append((vals + ci).max())
    bottom_ylim = (np.floor(min(bottom_ymins)), np.ceil(max(bottom_ymaxs))) if bottom_ymins else (None, None)
    for col, slr in enumerate(slr_scenarios):
        # Top: Relative Benefit
        ax = axes[0, col]
        ax.text(0.03, 0.93, panel_labels[col], transform=ax.transAxes, fontsize=18, fontweight='bold', va='top', ha='left')
        for j, policy in enumerate(proactive_policies):
            df = rel_benefit[(rel_benefit['ProactivePolicy'] == policy) & (rel_benefit['SLR'] == slr) & (rel_benefit['Hazard'] == hazard) & (rel_benefit['Metric'] == metric)]
            if df.empty:
                continue
            # Filter years between 2025 and 2100
            mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
            years = df['Year'][mask]
            mean = df['Mean'][mask]
            ci = get_ci(df['Std'][mask])
            ax.plot(years, mean, color=colors[policy], label=policy, linewidth=2)
            ax.fill_between(years, mean - ci, mean + ci, color=colors[policy], alpha=0.2)
        if top_ylim[0] is not None:
            ax.set_ylim(top_ylim)
        if col == 0:
            ax.set_ylabel(metric_labels[i], fontsize=18, fontweight='bold')
        ax.set_title(f'SLR-{slr}', fontsize=18, fontweight='bold')
        ax.grid(True, alpha=0.3)
        if col == 2:
            ax.legend(fontsize=18, loc='upper left', frameon=False)
        ax.set_xticks([2025, 2050, 2075, 2100])
        ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=18)
        ax.tick_params(axis='y', labelsize=18)
    # Bottom: Cumulative Cost (same for all metrics)
    for col, slr in enumerate(slr_scenarios):
        ax = axes[1, col]
        ax.text(0.03, 0.93, panel_labels[3+col], transform=ax.transAxes, fontsize=18, fontweight='bold', va='top', ha='left')
        for j, policy in enumerate(proactive_policies):
            df = cum_cost[(cum_cost['ProactivePolicy'] == policy) & (cum_cost['SLR'] == slr)]
            if df.empty:
                continue
            # Filter years between 2025 and 2100
            mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
            years = df['Year'][mask]
            mean = df['Mean'][mask]
            ci = get_ci(df['Std'][mask])
            ax.plot(years, mean, color=colors[policy], label=policy, linewidth=2)
            ax.fill_between(years, mean - ci, mean + ci, color=colors[policy], alpha=0.2)
        if bottom_ylim[0] is not None:
            ax.set_ylim(bottom_ylim)
        if col == 0:
            ax.set_ylabel('Absolute Cumulative Cost Increase (M$)', fontsize=18, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_xticks([2025, 2050, 2075, 2100])
        ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=18)
        ax.tick_params(axis='y', labelsize=18)
    axes[1,1].set_xlabel('Time (Year)', fontsize=18, fontweight='bold', labelpad=16)
    plt.tight_layout()
    fname = f'Detailed_{metric}_{hazard}_6panel'
    fig.savefig(os.path.join(output_dir, fname + '.png'), dpi=300, bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, fname + '.svg'), bbox_inches='tight')
    plt.close()

# --- Group 2: Summary Figures ---
cb_df = pd.read_csv(Path(output_dir) / 'Statistics_Chronic_Corner2_CostBenefit_PerSim.csv')
economic_baseline = normalize_simulation_columns(pd.read_csv(
    Path(economic_dir) / 'Results_Chronic_Corner2_Economics_Baseline_PerSim.csv'
))
economic_proactive = normalize_simulation_columns(pd.read_csv(
    Path(economic_dir) / 'Results_Chronic_Corner2_Economics_Proactive_PerSim.csv'
))
economic_proactive_simulation_columns = sorted(
    [column for column in economic_proactive.columns if column.startswith('Sim_')],
    key=lambda column: int(column.split('_')[1])
)
economic_proactive[economic_proactive_simulation_columns] = (
    economic_proactive[economic_proactive_simulation_columns].clip(lower=0)
)
economic_proactive = recalculate_simulation_statistics(
    economic_proactive,
    economic_proactive_simulation_columns
)
economic_proactive = economic_proactive.drop(
    columns=['Mean (M$)', 'Std (M$)'],
    errors='ignore'
).rename(columns={'Mean': 'Mean (M$)', 'Std': 'Std (M$)'})
economic_cumulative_cost = normalize_simulation_columns(pd.read_csv(
    Path(economic_dir) / 'Results_Chronic_Corner2_Economics_CumulativeCost_PerSim.csv'
))
economic_merge_keys = ['SLR', 'Hazard', 'Metric', 'Year']
economic_simulation_columns = [
    column for column in economic_baseline.columns if column.startswith('Sim_')
]
economic_proactive_metric = 'Economic_Loss_Reduction'

for i, (metric, hazard) in enumerate(metric_hazard_list):
    fig, axes = plt.subplots(2, 3, figsize=(18, 10), sharex=True)
    # --- Calculate y-limits for top and bottom panels (Summary) ---
    # Top panels: Baseline
    top_ymins, top_ymaxs = [], []
    for col, slr in enumerate(slr_scenarios):
        df = metric_df[(metric_df['Policy'] == 'Baseline') & (metric_df['SLR'] == slr) & (metric_df['Hazard'] == hazard) & (metric_df['Metric'] == metric)]
        if not df.empty:
            mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
            vals = df['Mean'][mask]
            ci = get_ci(df['Std'][mask])
            top_ymins.append((vals - ci).min())
            top_ymaxs.append((vals + ci).max())
    top_ylim = (np.floor(min(top_ymins)), np.ceil(max(top_ymaxs))) if top_ymins else (None, None)
    # Bottom panels: Cost-benefit
    bottom_ymins, bottom_ymaxs = [], []
    for col, slr in enumerate(slr_scenarios):
        for policy in proactive_policies:
            df = cb_df[(cb_df['ProactivePolicy'] == policy) & (cb_df['SLR'] == slr) & (cb_df['Hazard'] == hazard) & (cb_df['Metric'] == metric)]
            if not df.empty:
                mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
                vals = df['Mean'][mask]
                ci = get_ci(df['Std'][mask])
                bottom_ymins.append((vals - ci).min())
                bottom_ymaxs.append((vals + ci).max())
    bottom_ylim = (np.floor(min(bottom_ymins)), np.ceil(max(bottom_ymaxs))) if bottom_ymins else (None, None)
    for col, slr in enumerate(slr_scenarios):
        # Top: Baseline only
        ax = axes[0, col]
        df = metric_df[(metric_df['Policy'] == 'Baseline') & (metric_df['SLR'] == slr) & (metric_df['Hazard'] == hazard) & (metric_df['Metric'] == metric)]
        if not df.empty:
            mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
            years = df['Year'][mask]
            mean = df['Mean'][mask]
            ci = get_ci(df['Std'][mask])
            ax.plot(years, mean, color=colors['Baseline'], label='Baseline', linewidth=2)
            ax.fill_between(years, mean - ci, mean + ci, color=colors['Baseline'], alpha=0.2)
        if top_ylim[0] is not None:
            ax.set_ylim(top_ylim)
        if col == 0:
            ax.set_ylabel(metric_labels_baseline[i], fontsize=16)
        ax.set_title(f'SLR-{slr}', fontsize=16)
        ax.grid(True, alpha=0.3)
        ax.set_xticks([2025, 2050, 2075, 2100])
        ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=14)
        ax.tick_params(axis='y', labelsize=14)
    # Bottom: Cost-benefit (Protect & Realign)
    for col, slr in enumerate(slr_scenarios):
        ax = axes[1, col]
        for j, policy in enumerate(proactive_policies):
            df = cb_df[(cb_df['ProactivePolicy'] == policy) & (cb_df['SLR'] == slr) & (cb_df['Hazard'] == hazard) & (cb_df['Metric'] == metric)]
            if df.empty:
                continue
            mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
            years = df['Year'][mask]
            mean = df['Mean'][mask]
            ci = get_ci(df['Std'][mask])
            ax.plot(years, mean, color=colors[policy], label=policy, linewidth=2)
            ax.fill_between(years, mean - ci, mean + ci, color=colors[policy], alpha=0.2)
        if bottom_ylim[0] is not None:
            ax.set_ylim(bottom_ylim)
        if col == 0:
            ax.set_ylabel(metric_labels_cb[i], fontsize=16)
        ax.grid(True, alpha=0.3)
        ax.set_xticks([2025, 2050, 2075, 2100])
        ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=14)
        ax.tick_params(axis='y', labelsize=14)
        if col == 2:
            ax.legend(fontsize=14, loc='upper left')
    axes[1,1].set_xlabel('Time (Year)', fontsize=16)
    plt.tight_layout()
    fname = f'Summary_{metric}_{hazard}_6panel'
    fig.savefig(os.path.join(output_dir, fname + '.png'), dpi=300, bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, fname + '.svg'), bbox_inches='tight')
    plt.close()

# --- Group 3: Combined Figures ---
# --- Use a 9-color rainbow colormap for all policies/SLRs ---
# The code now uses a 9-color rainbow colormap: the first 3 colors (red, orange, yellow) for Baseline SLR-Low/Med/High, the middle 3 (green, cyan, teal) for Protect, and the last 3 (blue, indigo, purple) for Realign. This ensures all colors are visually related and grouped by policy, with smooth transitions.

# Use a custom high-contrast green palette for Protect
protect_colors = {
    'Low': '#2ca02c',    # vivid green
    'Med': '#006400',   # dark green
    'High': '#00c19f'   # teal-green (distinct from the others)
}
# Keep Realign and Baseline as before, using the rainbow colormap for those
cmap = mpl.cm.get_cmap('rainbow', 9)
rainbow_colors = [mpl.colors.to_hex(cmap(i)) for i in range(9)]
realign_colors = {'Low': rainbow_colors[2], 'Med': rainbow_colors[1], 'High': rainbow_colors[0]}
baseline_colors = {'Low': rainbow_colors[6], 'Med': rainbow_colors[7], 'High': rainbow_colors[8]}
slr_shades = {'Low': 0.2, 'Med': 0.2, 'High': 0.2}  # alpha for fill

combined_metrics = [
    [('Damaged', 'Flooding'), ('Eroded', 'Erosion')],
    [('PopulationImpacted', 'Flooding'), ('PopulationImpacted', 'Erosion')],
    [('EconomicLoss', 'Flooding'), ('EconomicLoss', 'Erosion')]
]
combined_labels = [
    ('Flood-Damaged Buildings', 'Eroded Buildings'),
    ('Population Impacted by Flooding', 'Population Impacted by Erosion'),
    ('Economic Loss by Flooding', 'Economic Loss by Erosion')
]
combined_cb_labels = [
    ('% Change in Flood-Damaged Buildings / M$', '% Change in Eroded Buildings / M$'),
    ('% Change in Population Impacted by Flooding / M$', '% Change in Population Impacted by Erosion / M$'),
    ('% Change in Economic Loss by Flooding / M$', '% Change in Economic Loss by Erosion / M$')
]
latex_entries = []
for idx, ((m1, h1), (m2, h2)) in enumerate(combined_metrics):
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True)
    # Top panels: Baseline, all SLRs (first 3 rainbow colors)
    for col, (metric, hazard, label) in enumerate([(m1, h1, combined_labels[idx][0]), (m2, h2, combined_labels[idx][1])]):
        ax = axes[0, col]
        for slr in slr_scenarios:
            df = metric_df[(metric_df['Policy'] == 'Baseline') & (metric_df['SLR'] == slr) & (metric_df['Hazard'] == hazard) & (metric_df['Metric'] == metric)]
            if df.empty:
                continue
            mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
            years = df['Year'][mask]
            mean = df['Mean'][mask]
            ci = get_ci(df['Std'][mask])
            # Always use thick solid line for mean, transparency for CI
            ax.plot(years, mean, linestyle='-', color=baseline_colors[slr], linewidth=3, label=f'SLR-{slr}')
            ax.fill_between(years, mean - ci, mean + ci, color=baseline_colors[slr], alpha=0.3)
        ax.set_ylabel(label, fontsize=15)
        ax.grid(True, alpha=0.3)
        ax.set_xticks([2025, 2050, 2075, 2100])
        ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=13)
        ax.tick_params(axis='y', labelsize=13)
        if col == 1:
            ax.legend(fontsize=12, loc='upper left', title='SLR Scenario')
    # Bottom panels: Protect (middle 3 rainbow), Realign (last 3 rainbow), each with 3 shades for SLR
    for col, (metric, hazard, label) in enumerate([(m1, h1, combined_cb_labels[idx][0]), (m2, h2, combined_cb_labels[idx][1])]):
        ax = axes[1, col]
        for policy in proactive_policies:
            for slr in slr_scenarios:
                df = cb_df[(cb_df['ProactivePolicy'] == policy) & (cb_df['SLR'] == slr) & (cb_df['Hazard'] == hazard) & (cb_df['Metric'] == metric)]
                if df.empty:
                    continue
                mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
                years = df['Year'][mask]
                mean = df['Mean'][mask]
                ci = get_ci(df['Std'][mask])
                # Always use thick solid line for mean, transparency for CI
                if policy == 'Protect':
                    color = protect_colors[slr]
                else:
                    color = realign_colors[slr]
                ax.plot(years, mean, linestyle='-', color=color, linewidth=3, label=f'{policy} SLR-{slr}')
                ax.fill_between(years, mean - ci, mean + ci, color=color, alpha=0.2)
        ax.set_ylabel(label, fontsize=15)
        ax.grid(True, alpha=0.3)
        ax.set_xticks([2025, 2050, 2075, 2100])
        ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=13)
        ax.tick_params(axis='y', labelsize=13)
        if col == 1:
            ax.legend(fontsize=12, loc='upper left', title='Policy & SLR')
    axes[1,0].set_xlabel('Time (Year)', fontsize=15)
    axes[1,1].set_xlabel('Time (Year)', fontsize=15)
    plt.tight_layout()
    fname = f'Combined_{m1}_{h1}_{m2}_{h2}_4panel'
    fig.savefig(os.path.join(output_dir, fname + '.png'), dpi=300, bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, fname + '.svg'), bbox_inches='tight')
    plt.close()


# === Main Figure A (3x2) for each metric, with LaTeX entries ===
main_latex_entries = []
main_metrics = [
    ('Damaged', 'Flooding', 'Eroded', 'Erosion', 'Physical'),
    ('PopulationImpacted', 'Flooding', 'PopulationImpacted', 'Erosion', 'Social'),
    ('EconomicLoss', 'Flooding', 'EconomicLoss', 'Erosion', 'Economic')
]
for metric1, hazard1, metric2, hazard2, metric_label in main_metrics:
    fig, axes = plt.subplots(3, 2, figsize=(14, 15), sharex=True)
    # Panel labels (a)-(f) for 3x2 grid, top left to bottom right
    panel_labels = ['(a)', '(b)', '(c)', '(d)', '(e)', '(f)']
    # Panel label positions for each metric_label
    # Each entry: (row, col): (x, ha) for ax.text(x, y, ...)
    panel_label_pos = {}
    if metric_label == 'Physical':
        # (a) right, (b) left; (c) right, (d) left; (e) right, (f) left
        panel_label_pos = {
            (0,0): (0.97, 'right'), (0,1): (0.03, 'left'),
            (1,0): (0.97, 'right'), (1,1): (0.03, 'left'),
            (2,0): (0.97, 'right'), (2,1): (0.03, 'left')
        }
    elif metric_label == 'Social':
        # (a) right, (b) left; (c)-(f) keep as before
        panel_label_pos = {
            (0,0): (0.97, 'right'), (0,1): (0.03, 'left'),
            (1,0): (0.97, 'right'), (1,1): (0.03, 'left'),
            (2,0): (0.97, 'right'), (2,1): (0.03, 'left')
        }
    elif metric_label == 'Economic':
        # (a) right, (b) left; (c) right, (d) left; (e) right, (f) left
        panel_label_pos = {
            (0,0): (0.97, 'right'), (0,1): (0.03, 'left'),
            (1,0): (0.97, 'right'), (1,1): (0.03, 'left'),
            (2,0): (0.97, 'right'), (2,1): (0.03, 'left')
        }
    # y-labels for top panels from Combined figures
    combined_labels_dict = {
        'Physical': ('Flood-Damaged Buildings (#)', 'Cumulative Eroded Buildings (#)'),
        'Social': ('Flood-Impacted Population (#)', 'Erosion-Impacted Population (#)'),
        'Economic': ('Flood Economic Loss ($M)', 'Erosion Economic Loss ($M)')
    }
    # y-labels for middle panels (c)-(d)
    detailed_labels_dict = {
        'Physical': ('Flood-damaged Buildings (% change)', 'Cumulative Eroded Buildings (% change)'),
        'Social': ('Flood-impacted Population (% change)', 'Erosion-impacted Population (% change)'),
        'Economic': ('Flood Economic Loss (% change)', 'Erosion Economic Loss (% change)')
    }
    # y-labels for bottom panels (e)-(f)
    # Economic omitted here: its panel (e)/(f) label is set directly below via the M$/M$ override.
    combined_cb_labels_dict = {
        'Physical': ('Flood-damaged Buildings (# change / M$)', 'Cumulative Eroded Buildings (# change / M$)'),
        'Social': ('Flood-impacted Population (# change / M$)', 'Erosion-impacted Population (# change / M$)')
    }
    # Row 1: Baseline absolute (all SLRs)
    for col, (metric, hazard) in enumerate([(metric1, hazard1), (metric2, hazard2)]):
        ax = axes[0, col]
        # Add panel label for first row
        x, ha = panel_label_pos.get((0,col), (0.03, 'left'))
        ax.text(x, 0.93, panel_labels[col], transform=ax.transAxes, fontsize=16, fontweight='bold', va='top', ha=ha)
        for slr in slr_scenarios:
            if metric_label == 'Economic':
                df = economic_baseline[
                    (economic_baseline['Policy'] == 'Baseline')
                    & (economic_baseline['SLR'] == slr)
                    & (economic_baseline['Hazard'] == hazard)
                    & (economic_baseline['Metric'] == 'Economic_Loss')
                ]
            else:
                df = metric_df[(metric_df['Policy'] == 'Baseline') & (metric_df['SLR'] == slr) & (metric_df['Hazard'] == hazard) & (metric_df['Metric'] == metric)]
            if df.empty:
                continue
            mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
            years = df['Year'][mask]
            if metric_label == 'Economic':
                mean = df['Mean (M$)'][mask]
                ci = 1.96 * df['Std (M$)'][mask] / np.sqrt(len(economic_simulation_columns))
            else:
                mean = df['Mean'][mask]
                ci = get_ci(df['Std'][mask])
            ax.plot(years, mean, linestyle='-.', color=baseline_colors[slr], linewidth=3, label=f'Baseline SLR-{slr}')
            ax.fill_between(years, mean - ci, mean + ci, color=baseline_colors[slr], alpha=0.2)
        # Use Combined figure y-labels for top row
        ax.set_ylabel(combined_labels_dict[metric_label][col], fontsize=16)
        ax.grid(True, alpha=0.3)
        ax.set_xticks([2025, 2050, 2075, 2100])
        ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=18)
        ax.tick_params(axis='y', labelsize=18)
        # Move Baseline legend in panel (a) to upper left for Physical, Social, and Economic
        if col == 0 and metric_label in ['Physical', 'Social', 'Economic']:
            ax.legend(fontsize=14, loc='upper left', frameon=False)
        # No legend for panel (b) (col==1)
    # Row 2: Relative benefit (percent change), all SLRs in one panel for each hazard
    for col, (metric, hazard) in enumerate([(metric1, hazard1), (metric2, hazard2)]):
        ax = axes[1, col]
        # Add panel label for second row
        x, ha = panel_label_pos.get((1,col), (0.03, 'left'))
        ax.text(x, 0.93, panel_labels[2+col], transform=ax.transAxes, fontsize=16, fontweight='bold', va='top', ha=ha)
        legend_handles = []
        legend_labels = []
        # First Protect, then Realign, for each SLR in order
        for policy in proactive_policies:
            for slr in slr_scenarios:
                if metric_label == 'Economic':
                    numerator = economic_proactive[
                        (economic_proactive['ProactivePolicy'] == policy)
                        & (economic_proactive['SLR'] == slr)
                        & (economic_proactive['Hazard'] == hazard)
                        & (economic_proactive['Metric'] == economic_proactive_metric)
                    ]
                    denominator = economic_baseline[
                        (economic_baseline['Policy'] == 'Baseline')
                        & (economic_baseline['SLR'] == slr)
                        & (economic_baseline['Hazard'] == hazard)
                        & (economic_baseline['Metric'] == 'Economic_Loss')
                    ]
                    df = ratio_statistics(
                        numerator, denominator,
                        ['SLR', 'Hazard', 'Year'],
                        scale=-100
                    )
                else:
                    df = rel_benefit[(rel_benefit['ProactivePolicy'] == policy) & (rel_benefit['SLR'] == slr) & (rel_benefit['Hazard'] == hazard) & (rel_benefit['Metric'] == metric)]
                if df.empty:
                    continue
                mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
                years = df['Year'][mask]
                mean = df['Mean'][mask]
                ci = (
                    1.96 * df['Std'][mask] / np.sqrt(len(economic_simulation_columns))
                    if metric_label == 'Economic'
                    else get_ci(df['Std'][mask])
                )
                if policy == 'Protect':
                    color = protect_colors[slr]
                else:
                    color = realign_colors[slr]
                line, = ax.plot(years, mean, linestyle='-.', color=color, linewidth=3, label=f'{policy} vs Baseline SLR-{slr}')
                ax.fill_between(years, mean - ci, mean + ci, color=color, alpha=0.2)
                legend_handles.append(line)
                legend_labels.append(f'{policy} vs Baseline SLR-{slr}')
        # Use Detailed figure y-labels for bottom row
        ax.set_ylabel(detailed_labels_dict[metric_label][col], fontsize=16)
        ax.grid(True, alpha=0.3)
        ax.set_xticks([2025, 2050, 2075, 2100])
        ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=18)
        ax.tick_params(axis='y', labelsize=18)
        if col == 1:
            if metric_label == 'Social':
                ax.legend(legend_handles, legend_labels, fontsize=12, loc='upper right', frameon=False)
            else:
                ax.legend(legend_handles, legend_labels, fontsize=14, loc='lower left', frameon=False)
    # Row 3: Cost-benefit (Protect & Realign, all SLRs)
    for col, (metric, hazard) in enumerate([(metric1, hazard1), (metric2, hazard2)]):
        ax = axes[2, col]
        # Add panel label for third row
        x, ha = panel_label_pos.get((2,col), (0.03, 'left'))
        ax.text(x, 0.93, panel_labels[4+col], transform=ax.transAxes, fontsize=16, fontweight='bold', va='top', ha=ha)
        legend_handles3 = []
        legend_labels3 = []
        for policy in proactive_policies:
            for slr in slr_scenarios:
                if metric_label == 'Economic':
                    numerator = economic_proactive[
                        (economic_proactive['ProactivePolicy'] == policy)
                        & (economic_proactive['SLR'] == slr)
                        & (economic_proactive['Hazard'] == hazard)
                        & (economic_proactive['Metric'] == economic_proactive_metric)
                    ]
                    denominator = economic_cumulative_cost[
                        (economic_cumulative_cost['ProactivePolicy'] == policy)
                        & (economic_cumulative_cost['SLR'] == slr)
                    ]
                    df = ratio_statistics(
                        numerator, denominator,
                        ['ProactivePolicy', 'SLR', 'Year'],
                        scale=-1
                    )
                elif metric_label in {'Physical', 'Social'}:
                    numerator = absolute_benefit[
                        (absolute_benefit['ProactivePolicy'] == policy)
                        & (absolute_benefit['SLR'] == slr)
                        & (absolute_benefit['Hazard'] == hazard)
                        & (absolute_benefit['Metric'] == metric)
                    ]
                    denominator = economic_cumulative_cost[
                        (economic_cumulative_cost['ProactivePolicy'] == policy)
                        & (economic_cumulative_cost['SLR'] == slr)
                    ]
                    df = ratio_statistics(
                        numerator, denominator,
                        ['ProactivePolicy', 'SLR', 'Year']
                    )
                if df.empty:
                    continue
                mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
                years = df['Year'][mask]
                mean = df['Mean'][mask]
                ci = 1.96 * df['Std'][mask] / np.sqrt(len(economic_simulation_columns))
                ci_ub = (mean + ci).clip(upper=0)
                ci_lb = (mean - ci).clip(upper=0)
                if policy == 'Protect':
                    color = protect_colors[slr]
                else:
                    color = realign_colors[slr]
                line3, = ax.plot(years, mean, linestyle='-.', color=color, linewidth=3, label=f'{policy} vs Baseline SLR-{slr}')
                ax.fill_between(years, ci_lb, ci_ub, color=color, alpha=0.2)
                legend_handles3.append(line3)
                legend_labels3.append(f'{policy} vs Baseline SLR-{slr}')
        # Use Combined figure y-labels for bottom row
        if metric_label == 'Economic':
            ax.set_ylabel(
                ('Flood benefit-cost ratio (BCR)', 'Erosion benefit-cost ratio (BCR)')[col],
                fontsize=16
            )
        else:
            ax.set_ylabel(combined_cb_labels_dict[metric_label][col], fontsize=16)
        ax.grid(True, alpha=0.3)
        ax.set_xticks([2025, 2050, 2075, 2100])
        ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=18)
        ax.tick_params(axis='y', labelsize=18)
        # Move legend from panel (f) to lower right of panel (e) for all Main Figure A
        if col == 0:
            ax.legend(legend_handles3, legend_labels3, fontsize=14, loc='lower right', frameon=False)
    axes[2,0].set_xlabel('Time (Year)', fontsize=18)
    axes[2,1].set_xlabel('Time (Year)', fontsize=18)
    plt.tight_layout()
    fname = f'Main_{metric_label}_3x2_PV_Corner2'
    fig.savefig(os.path.join(output_dir, fname + '.png'), dpi=300, bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, fname + '.svg'), bbox_inches='tight')
    plt.close()
    # Add LaTeX entry for Main Figure A with detailed captions
    if metric_label == 'Physical':
        caption = ("Chronic hazard adaptation effectiveness for physical damage metrics under flooding (left column) and erosion (right column). "
                   "\\textbf{Top row (a--b):} Mean and 95\\% CI of annual flood-damaged buildings (a) and cumulative eroded buildings (b) under Baseline across SLR-Low, SLR-Medium, and SLR-High scenarios. "
                   "\\textbf{Middle row (c--d):} Relative benefit of Protect and Realign relative to Baseline—percent change in flood-damaged buildings (c) and cumulative eroded buildings (d)—across all SLR scenarios; mean and 95\\% CI shown. "
                   "\\textbf{Bottom row (e--f):} Cost-effectiveness of Protect and Realign reported as benefit per $1M additional expenditure relative to Baseline (C1), for flood-damaged buildings (e) and cumulative eroded buildings (f), across all SLR scenarios; mean and 95\\% CI shown.")
        label = 'fig:main_physical_3x2'
    elif metric_label == 'Social':
        caption = ("Chronic hazard adaptation effectiveness for social impact metrics under flooding (left column) and erosion (right column). "
                   "\\textbf{Top row (a--b):} Mean and 95\\% CI of annual flood-impacted population (a) and cumulative erosion-impacted population (b) under Baseline across SLR-Low, SLR-Medium, and SLR-High scenarios. "
                   "\\textbf{Middle row (c--d):} Relative benefit of Protect and Realign relative to Baseline—percent change in flood-impacted population (c) and erosion-impacted population (d)—across all SLR scenarios; mean and 95\\% CI shown. "
                   "\\textbf{Bottom row (e--f):} Cost-effectiveness of Protect and Realign reported as benefit per $1M additional expenditure relative to Baseline (C1), for flood-impacted population (e) and erosion-impacted population (f), across all SLR scenarios; mean and 95\\% CI shown.")
        label = 'fig:main_social_3x2'
    elif metric_label == 'Economic':
        caption = ("Chronic hazard adaptation effectiveness for economic loss metrics under flooding (left column) and erosion (right column). "
                   "\\textbf{Top row (a--b):} Mean and 95\\% CI of annual flood-induced economic loss (a) and cumulative erosion-induced economic loss (b) under Baseline across SLR-Low, SLR-Medium, and SLR-High scenarios. "
                   "\\textbf{Middle row (c--d):} Relative benefit of Protect and Realign relative to Baseline—percent change in flood-induced loss (c) and erosion-induced loss (d)—across all SLR scenarios; mean and 95\\% CI shown. "
                   "\\textbf{Bottom row (e--f):} Cost-effectiveness of Protect and Realign reported as benefit per $1M additional expenditure relative to Baseline (C1), for flood-induced loss (e) and erosion-induced loss (f), across all SLR scenarios; mean and 95\\% CI shown.")
        label = 'fig:main_economic_3x2'
    else:
        caption = f"Main Figure: Baseline, relative benefit, and cost-benefit for {metric_label.lower()} metrics (rows) under Flooding and Erosion (columns). Mean and 95% CI shown for all SLR and policy combinations."
        label = f'fig:main_{metric_label.lower()}_3x2'
    main_latex_entries.append({
        'file': fname + '.png',
        'caption': caption,
        'label': label
    })

# === Main Figure B: Cumulative cost (single panel, 6 curves), with LaTeX entry ===
main_cum_cost = pd.read_csv(
    Path(economic_dir) / 'Results_Chronic_Corner2_Economics_CumulativeCost_PerSim.csv'
)
main_simulation_columns = [
    column for column in main_cum_cost.columns if column.startswith('Sim_')
]
main_n_iter = len(main_simulation_columns)

fig, ax = plt.subplots(figsize=(7, 5))
for policy in proactive_policies:
    for slr in slr_scenarios:
        df = main_cum_cost[
            (main_cum_cost['ProactivePolicy'] == policy)
            & (main_cum_cost['SLR'] == slr)
        ]
        if df.empty:
            continue
        mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
        years = df['Year'][mask]
        mean = df['Mean (M$)'][mask]
        ci = 1.96 * df['Std (M$)'][mask] / np.sqrt(main_n_iter)
        if policy == 'Protect':
            color = protect_colors[slr]
        else:
            color = realign_colors[slr]
        ax.plot(years, mean, linestyle='--', color=color, linewidth=2, label=f'{policy} vs Baseline SLR-{slr}')
        ax.fill_between(years, mean - ci, mean + ci, color=color, alpha=0.2)
ax.set_ylabel('Cumulative Cost Change (M$)', fontsize=14)
ax.set_xlabel('Time (Year)', fontsize=14)
ax.set_xticks([2025, 2050, 2075, 2100])
ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=14)
ax.tick_params(axis='y', labelsize=14)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=12, loc='upper left', frameon=False)
plt.tight_layout()
main_b_fname = 'Main_CumulativeCost_PV_Corner2'
fig.savefig(os.path.join(output_dir, main_b_fname + '.png'), dpi=300, bbox_inches='tight')
fig.savefig(os.path.join(output_dir, main_b_fname + '.svg'), bbox_inches='tight')
plt.close()
main_latex_entries.append({
    'file': main_b_fname + '.png',
    'caption': "Cumulative incremental cost trajectories for Protect and Realign relative to Baseline under SLR-Low, SLR-Medium, and SLR-High scenarios (2025--2100). Total actual expenditure above Baseline is shown, reflecting trigger-based allocation in which policies may not exhaust the $5M annual budget in all years, particularly in early simulation years or after most eligible buildings have been treated. Mean and 95% CI shown.",
    'label': 'fig:main_cumulativecost'
})

# === Main Figure C: Net present value (six curves) ===
main_npv = normalize_simulation_columns(pd.read_csv(
    Path(economic_dir) / 'Results_Chronic_Corner2_Economics_NPV_PerSim.csv'
))
main_npv_simulation_columns = [
    column for column in main_npv.columns if column.startswith('Sim_')
]
main_npv_n_iter = len(main_npv_simulation_columns)

fig, ax = plt.subplots(figsize=(7, 5))
for policy in proactive_policies:
    for slr in slr_scenarios:
        df = main_npv[
            (main_npv['ProactivePolicy'] == policy)
            & (main_npv['SLR'] == slr)
        ]
        if df.empty:
            continue
        mask = (df['Year'] >= 2025) & (df['Year'] <= 2100)
        years = df['Year'][mask]
        mean = df['Mean (M$)'][mask]
        ci = 1.96 * df['Std (M$)'][mask] / np.sqrt(main_npv_n_iter)
        color = protect_colors[slr] if policy == 'Protect' else realign_colors[slr]
        ax.plot(
            years, mean, linestyle='--', color=color, linewidth=2,
            label=f'{policy} SLR-{slr}'
        )
        ax.fill_between(years, mean - ci, mean + ci, color=color, alpha=0.2)
ax.set_ylabel('Net Present Value (M$)', fontsize=14)
ax.set_xlabel('Time (Year)', fontsize=14)
ax.set_xticks([2025, 2050, 2075, 2100])
ax.set_xticklabels(['2025', '2050', '2075', '2100'], fontsize=14)
ax.tick_params(axis='y', labelsize=14)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=12, loc='upper left', frameon=False)
plt.tight_layout()
main_npv_fname = 'Main_NPV_Corner2'
fig.savefig(os.path.join(output_dir, main_npv_fname + '.png'), dpi=300, bbox_inches='tight')
fig.savefig(os.path.join(output_dir, main_npv_fname + '.svg'), bbox_inches='tight')
plt.close()
main_latex_entries.append({
    'file': main_npv_fname + '.png',
    'caption': "Net present value trajectories for Protect and Realign under SLR-Low, SLR-Medium, and SLR-High scenarios (2025--2100). Mean and 95% CI shown.",
    'label': 'fig:main_npv'
})

# === Save the data underlying Main_Corner2_CumulativeCost_PV, ===
# === Main_Corner2_Physical_3x2_PV, Main_Corner2_Social_3x2_PV, ===
# === Main_Corner2_Economic_3x2_PV, and Main_Corner2_NPV to report CSVs ===
N_ECON = len(economic_simulation_columns)


def stat_frame(df, metric, n, hazard=None, mean_col='Mean', std_col='Std', policy_col='Policy'):
    d = df.copy()
    if policy_col != 'Policy':
        d = d.rename(columns={policy_col: 'Policy'})
    if mean_col != 'Mean':
        d = d.rename(columns={mean_col: 'Mean', std_col: 'Std'})
    if hazard is not None:
        d['Hazard'] = hazard
    d['Metric'] = metric
    ci = 1.96 * d['Std'] / np.sqrt(n)
    d['CoV'] = d['Std'] / d['Mean']
    d['95CI_LB'] = d['Mean'] - ci
    d['95CI_UB'] = d['Mean'] + ci
    return d[['Policy', 'SLR', 'Hazard', 'Metric', 'Year', 'Mean', 'Std', 'CoV', '95CI_LB', '95CI_UB']]


def ratio_frame(v1_df):
    # Ratio is undefined without both Protect and Realign present (e.g. Baseline-only metrics).
    wide = v1_df.pivot_table(index=['SLR', 'Hazard', 'Metric', 'Year'], columns='Policy', values='Mean').reset_index()
    if 'Protect' not in wide.columns or 'Realign' not in wide.columns:
        return pd.DataFrame(columns=['SLR', 'Hazard', 'Metric', 'Year', 'ProtectRealignRatio', 'RealignProtectRatio'])
    wide['ProtectRealignRatio'] = wide['Protect'] / wide['Realign']
    wide['RealignProtectRatio'] = wide['Realign'] / wide['Protect']
    return wide[['SLR', 'Hazard', 'Metric', 'Year', 'ProtectRealignRatio', 'RealignProtectRatio']]


report_v1_blocks = []
report_v2_blocks = []


def add_block(df, metric, n, hazard=None, mean_col='Mean', std_col='Std', policy_col='Policy', ratio=True):
    block = stat_frame(df, metric, n, hazard=hazard, mean_col=mean_col, std_col=std_col, policy_col=policy_col)
    report_v1_blocks.append(block)
    if ratio:
        report_v2_blocks.append(ratio_frame(block))


# --- Main_CumulativeCost_PV: Cost_Cumulatively_Increased ---
add_block(
    main_cum_cost, 'Cost_Cumulatively_Increased', main_n_iter, hazard='Chronic',
    mean_col='Mean (M$)', std_col='Std (M$)', policy_col='ProactivePolicy'
)

# --- Main_Physical_3x2_PV (Damaged/Eroded) and Main_Social_3x2_PV (PopulationImpacted) ---
physical_social_metrics = [
    ('Damaged', 'Flooding', 'Eroded', 'Erosion'),
    ('PopulationImpacted', 'Flooding', 'PopulationImpacted', 'Erosion'),
]
for metric1, hazard1, metric2, hazard2 in physical_social_metrics:
    pairs = [(metric1, hazard1), (metric2, hazard2)]
    for metric, hazard in pairs:
        add_block(
            metric_df[(metric_df['Policy'] == 'Baseline') & (metric_df['Hazard'] == hazard) & (metric_df['Metric'] == metric)],
            metric, N_ITER, ratio=False
        )
    for metric, hazard in pairs:
        add_block(
            absolute_benefit[(absolute_benefit['Hazard'] == hazard) & (absolute_benefit['Metric'] == metric)],
            f'{metric}_Reduction', N_ITER, policy_col='ProactivePolicy'
        )
    for metric, hazard in pairs:
        add_block(
            rel_benefit[(rel_benefit['Hazard'] == hazard) & (rel_benefit['Metric'] == metric)],
            f'{metric}_Reduction_PercentChange', N_ITER, policy_col='ProactivePolicy'
        )
    for metric, hazard in pairs:
        numerator = absolute_benefit[(absolute_benefit['Hazard'] == hazard) & (absolute_benefit['Metric'] == metric)]
        cb = ratio_statistics(numerator, economic_cumulative_cost, ['ProactivePolicy', 'SLR', 'Year'])
        add_block(cb, f'{metric}_CostBenefit', N_ECON, hazard=hazard, policy_col='ProactivePolicy')

# --- Main_Economic_3x2_PV (Economic_Loss) ---
for hazard in ['Flooding', 'Erosion']:
    add_block(
        economic_baseline[
            (economic_baseline['Policy'] == 'Baseline') & (economic_baseline['Hazard'] == hazard)
            & (economic_baseline['Metric'] == 'Economic_Loss')
        ],
        'Economic_Loss', N_ECON, mean_col='Mean (M$)', std_col='Std (M$)', ratio=False
    )
for hazard in ['Flooding', 'Erosion']:
    add_block(
        economic_proactive[(economic_proactive['Hazard'] == hazard) & (economic_proactive['Metric'] == economic_proactive_metric)],
        'Economic_Loss_Reduction', N_ECON, mean_col='Mean (M$)', std_col='Std (M$)', policy_col='ProactivePolicy'
    )
for hazard in ['Flooding', 'Erosion']:
    denominator = economic_baseline[
        (economic_baseline['Policy'] == 'Baseline') & (economic_baseline['Hazard'] == hazard)
        & (economic_baseline['Metric'] == 'Economic_Loss')
    ]
    for policy in proactive_policies:
        numerator = economic_proactive[
            (economic_proactive['ProactivePolicy'] == policy) & (economic_proactive['Hazard'] == hazard)
            & (economic_proactive['Metric'] == economic_proactive_metric)
        ]
        # ratio_statistics drops ProactivePolicy since it's absent from the Baseline-only denominator.
        pct = ratio_statistics(numerator, denominator, ['SLR', 'Hazard', 'Year'], scale=-100)
        pct['ProactivePolicy'] = policy
        add_block(pct, 'Economic_Loss_Reduction_PercentChange', N_ECON, policy_col='ProactivePolicy')
for hazard in ['Flooding', 'Erosion']:
    numerator = economic_proactive[(economic_proactive['Hazard'] == hazard) & (economic_proactive['Metric'] == economic_proactive_metric)]
    cb = ratio_statistics(numerator, economic_cumulative_cost, ['ProactivePolicy', 'SLR', 'Year'], scale=-1)
    add_block(cb, 'Economic_Loss_CostBenefit', N_ECON, hazard=hazard, policy_col='ProactivePolicy')

# --- Main_NPV: Net_Present_Value ---
add_block(
    main_npv, 'Net_Present_Value', main_npv_n_iter, hazard='Chronic',
    mean_col='Mean (M$)', std_col='Std (M$)', policy_col='ProactivePolicy'
)

report_v1 = pd.concat(report_v1_blocks, ignore_index=True)
report_v2 = pd.concat(report_v2_blocks, ignore_index=True)
report_v1 = report_v1[(report_v1['Year'] >= 2025) & (report_v1['Year'] <= 2100)]
report_v2 = report_v2[(report_v2['Year'] >= 2025) & (report_v2['Year'] <= 2100)]
report_v1.to_csv(os.path.join(output_dir, 'Results_report_Chronic_PV_1_Corner2.csv'), index=False)
report_v2.to_csv(os.path.join(output_dir, 'Results_report_Chronic_PV_2_Corner2.csv'), index=False)
