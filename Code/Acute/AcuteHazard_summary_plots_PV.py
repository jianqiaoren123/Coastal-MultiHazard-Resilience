
# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()
N_ITER = 1000
# This script is used to plot the SUMMARY results of the acute hazard analysis.

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.patches import Patch

# Color mapping (pure RGB)
colors = {'Baseline': '#FF0000', 'Protect': '#00FF00', 'Realign': '#0000FF'}

# Output path
output_path = Path(f'{REPO_ROOT}/Results/Acute')
output_path.mkdir(parents=True, exist_ok=True)


def make_results_report_acute_pv():
    """Save the complete PV result matrix with derived totals and percent changes."""
    per_sim_path = Path(f'{REPO_ROOT}/Results/EconomicAnalysis/Results_Acute_Economics_PerSim.csv')
    report_path = output_path / 'Results_report_Acute_PV.csv'
    econ_df = pd.read_csv(per_sim_path)
    iter_cols = [column for column in econ_df.columns if column.startswith('Iter_')]
    if not iter_cols:
        raise ValueError(f'No Iter_ columns found in {per_sim_path}')

    def get_row(category, policy, hazard, metric):
        rows = econ_df[
            (econ_df['Category'] == category)
            & (econ_df['Policy'] == policy)
            & (econ_df['Hazard'] == hazard)
            & (econ_df['Metric'] == metric)
        ]
        return None if rows.empty else rows.iloc[0]

    def get_values(category, policy, hazard, metric):
        row = get_row(category, policy, hazard, metric)
        if row is not None:
            return row[iter_cols].astype(float).to_numpy()
        if category == 'Building_AND_Life':
            building_values = get_values('Building_Damage', policy, hazard, metric)
            life_safety_values = get_values('Life_Safety', policy, hazard, metric)
            if building_values is not None and life_safety_values is not None:
                return building_values + life_safety_values
        return None

    def summarize(values):
        n_values = len(values)
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1)) if n_values > 1 else 0.0
        cov = 0.0 if np.isclose(mean, 0.0) else std / mean
        ci_margin = 1.96 * std / np.sqrt(n_values)
        return mean, std, cov, mean - ci_margin, mean + ci_margin

    def make_record(category, policy, hazard, metric, values):
        mean, std, cov, ci_lower, ci_upper = summarize(values)
        source_row = get_row(category, policy, hazard, metric)
        if source_row is not None:
            mean = pd.to_numeric(source_row.get('Mean (M$)'), errors='coerce')
            std = pd.to_numeric(source_row.get('Std (M$)'), errors='coerce')
            cov = pd.to_numeric(source_row.get('CoV'), errors='coerce')
            calculated_mean, calculated_std, calculated_cov, _, _ = summarize(values)
            mean = calculated_mean if pd.isna(mean) else mean
            std = calculated_std if pd.isna(std) else std
            cov = calculated_cov if pd.isna(cov) else cov
            ci_lower = mean - 1.96 * std / np.sqrt(len(values))
            ci_upper = mean + 1.96 * std / np.sqrt(len(values))
        return {
            'Category': category,
            'Policy': policy,
            'Hazard': hazard,
            'Metric': metric,
            'Mean': mean,
            'Std': std,
            'CoV': cov,
            '95CI_LB': ci_lower,
            '95CI_UB': ci_upper,
        }

    def make_percent_change_record(category, policy, hazard, baseline_values, reduction_values):
        baseline_mean, baseline_std, _, _, _ = summarize(baseline_values)
        reduction_mean, reduction_std, _, _, _ = summarize(reduction_values)
        if np.isclose(baseline_mean, 0.0):
            mean = 0.0
            std = 0.0
        else:
            mean = -100.0 * reduction_mean / baseline_mean
            std = 100.0 * np.sqrt(
                (reduction_std / baseline_mean) ** 2
                + (reduction_mean * baseline_std / baseline_mean ** 2) ** 2
            )
        cov = 0.0 if np.isclose(mean, 0.0) else std / mean
        ci_margin = 1.96 * std / np.sqrt(len(baseline_values))
        return {
            'Category': category,
            'Policy': policy,
            'Hazard': hazard,
            'Metric': 'Economic_Loss_Reduction_PercentChange',
            'Mean': mean,
            'Std': std,
            'CoV': cov,
            '95CI_LB': mean - ci_margin,
            '95CI_UB': mean + ci_margin,
        }

    records = []
    categories = ['Building_Damage', 'Life_Safety', 'Building_AND_Life']
    hazards = ['EQ', 'TSU', 'EQ_AND_TSU']
    policies = ['Protect', 'Realign']

    for category in categories:
        for hazard in hazards:
            baseline_values = get_values(category, 'Baseline', hazard, 'Economic_Loss')
            if baseline_values is not None:
                records.append(make_record(category, 'Baseline', hazard, 'Economic_Loss', baseline_values))

    for policy in policies:
        for category in categories:
            for hazard in hazards:
                reduction_values = get_values(category, policy, hazard, 'Economic_Loss_Reduction')
                if reduction_values is not None:
                    records.append(make_record(category, policy, hazard, 'Economic_Loss_Reduction', reduction_values))

        for metric in ['Cost_Cumulatively_Increased', 'Net_Present_Value']:
            values = get_values('Building_AND_Life', policy, 'EQ_AND_TSU', metric)
            if values is not None:
                records.append(make_record('Building_AND_Life', policy, 'EQ_AND_TSU', metric, values))

        for category in categories:
            for hazard in hazards:
                baseline_values = get_values(category, 'Baseline', hazard, 'Economic_Loss')
                reduction_values = get_values(category, policy, hazard, 'Economic_Loss_Reduction')
                if baseline_values is None or reduction_values is None:
                    continue
                records.append(make_percent_change_record(
                    category,
                    policy,
                    hazard,
                    baseline_values,
                    reduction_values,
                ))

    report_df = pd.DataFrame(records)
    report_df.to_csv(report_path, index=False)
    print(f'Saved: {report_path}')

# Read summary statistics
stats = pd.read_csv(output_path / 'Statistics_Acute_PerSim.csv')

metrics = [
    {
        'name': 'Damage',
        'keys': [0, 1, 2, 3, 4, '>0'],
        'labels': ['DS 0', 'DS 1', 'DS 2', 'DS 3', 'DS 4', 'DS >0'],
        'ylabel': 'Number of Buildings (#)',
        'change_ylabel': 'Buildings (% change)',
        'result_key': lambda ds: f'DS_{ds}',
        'fig_name': 'Summary_Damage_6panel'
    },
    {
        'name': 'Life Safety',
        'keys': ['Fatality', 'Injury', 'Casualty'],
        'labels': ['Fatality', 'Injury', 'Casualty'],
        'ylabel': 'Number of People (#)',
        'change_ylabel': 'People (% change)',
        'result_key': lambda k: k,
        'fig_name': 'Summary_LifeSafety_6panel'
    },
    {
        'name': 'Population Impacted',
        'keys': ['Population_Impacted'],
        'labels': ['Population Impacted'],
        'ylabel': 'Population Impacted (#)',
        'change_ylabel': 'Population (% change)',
        'result_key': lambda k: k,
        'fig_name': 'Summary_PopImp_6panel'
    }
]

hazards = ['EQ', 'TSU', 'Cumulative']

for metric in metrics:
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    panel_labels = ['(a)', '(b)', '(c)', '(d)', '(e)', '(f)']
    # --- Top row: Absolute values for Baseline (mean + 95% CI from Statistics_Acute_PerSim.csv) ---
    for col, hazard in enumerate(hazards):
        ax = axes[0, col]
        # For Summary_Damage_6panel, move (b) and (f) to top right
        if metric['fig_name'] == 'Summary_Damage_6panel' and col == 1:
            ax.text(0.97, 0.93, panel_labels[col], transform=ax.transAxes, fontsize=20, fontweight='bold', va='top', ha='right')
        else:
            ax.text(0.03, 0.93, panel_labels[col], transform=ax.transAxes, fontsize=20, fontweight='bold', va='top', ha='left')
        if col == 0:
            ax.set_title('EQ', fontsize=20, fontweight='bold')
        elif col == 1:
            ax.set_title('TSU', fontsize=20, fontweight='bold')
        elif col == 2:
            ax.set_title('EQ + TSU', fontsize=20, fontweight='bold')
        if col == 0:
            if metric['fig_name'] == 'Summary_EconLoss_6panel':
                ax.set_ylabel('Economic Loss (M$)', fontsize=20)
            else:
                ax.set_ylabel(metric['ylabel'], fontsize=20)
        else:
            ax.set_ylabel("")
        # Prepare data for bar plot
        means = []
        cis = []
        bar_positions = []
        if metric['fig_name'] == 'Summary_LifeSafety_6panel':
            bar_positions = [0.65, 1, 1.35]
            for i, key in enumerate(metric['keys']):
                rk = metric['result_key'](key)
                row = stats[(stats['Policy'] == 'Baseline') & (stats['Hazard'] == hazard) & (stats['Metric'] == rk)]
                if not row.empty:
                    mean = row['Mean'].values[0]
                    std = row['Std'].values[0]
                    ci = 1.96 * std / np.sqrt(N_ITER)
                    means.append(mean)
                    cis.append(ci)
                else:
                    means.append(0)
                    cis.append(0)
            ax.bar(bar_positions, means, yerr=cis, capsize=6, color=colors['Baseline'], width=0.144, alpha=0.8, error_kw={'ecolor': colors['Baseline']})
            ax.set_xlim([0.5, 1.5])
        else:
            if metric['fig_name'] == 'Summary_EconLoss_6panel':
                bar_positions = [1]
                for key in metric['keys']:
                    rk = metric['result_key'](key)
                    row = stats[(stats['Policy'] == 'Baseline') & (stats['Hazard'] == hazard) & (stats['Metric'] == rk)]
                    if not row.empty:
                        mean = row['Mean'].values[0] / 1e6
                        std = row['Std'].values[0] / 1e6
                        ci = 1.96 * std / np.sqrt(N_ITER)
                        means.append(mean)
                        cis.append(ci)
                    else:
                        means.append(0)
                        cis.append(0)
                ax.bar(bar_positions, means, yerr=cis, capsize=6, color=colors['Baseline'], width=0.1, alpha=0.8, error_kw={'ecolor': colors['Baseline']})
            else:
                bar_positions = np.arange(1, len(metric['keys'])+1)
                for i, key in enumerate(metric['keys']):
                    rk = metric['result_key'](key)
                    row = stats[(stats['Policy'] == 'Baseline') & (stats['Hazard'] == hazard) & (stats['Metric'] == rk)]
                    if not row.empty:
                        mean = row['Mean'].values[0]
                        std = row['Std'].values[0]
                        ci = 1.96 * std / np.sqrt(N_ITER)
                        means.append(mean)
                        cis.append(ci)
                    else:
                        means.append(0)
                        cis.append(0)
                ax.bar(bar_positions, means, yerr=cis, capsize=6, color=colors['Baseline'], width=0.5, alpha=0.8, error_kw={'ecolor': colors['Baseline']})
        # Remove x-axis ticks and labels for all top panels
        ax.set_xticks([])
        ax.set_xticklabels([])
        ax.tick_params(axis='x', bottom=False, labelbottom=False)
        ax.tick_params(axis='y', labelsize=20)
        ax.grid(True, alpha=0.3, axis='y')
        # Add more y-tick labels for panel (c) of Summary_EconLoss_6panel (top right)
        if metric['fig_name'] == 'Summary_EconLoss_6panel' and col == 2:
            # Set y-ticks every 100 from 0 to the nearest 100 above the current max
            y_max = ax.get_ylim()[1]
            y_ticks = np.arange(0, y_max + 100, 100)
            ax.set_yticks(y_ticks)
        # Add vertical grid lines
        if metric['fig_name'] == 'Summary_Damage_6panel':
            x_positions = np.arange(1, 7)
        elif metric['fig_name'] == 'Summary_LifeSafety_6panel':
            if ax in axes[0]:
                x_positions = [0.65, 1, 1.35]
            else:
                x_positions = []
        elif metric['fig_name'] == 'Summary_EconLoss_6panel':
            if ax in axes[0]:
                x_positions = [0.75, 1, 1.25]
            else:
                x_positions = []
        elif metric['fig_name'] == 'Summary_PopImp_6panel':
            x_positions = np.arange(1, 3)
        else:
            x_positions = []
        for xpos in x_positions:
            ax.axvline(x=xpos, color='gray', linestyle=':', alpha=0.5, zorder=0)
    # Restore Baseline legend in panel (b) (axes[0,1]) for Summary_Damage_6panel and Summary_LifeSafety_6panel
    if metric['fig_name'] in ['Summary_Damage_6panel', 'Summary_LifeSafety_6panel']:
        baseline_patch = Patch(facecolor=colors['Baseline'], alpha=0.6)
        axes[0, 1].legend([baseline_patch], ['Baseline'], fontsize=18, loc='upper center', bbox_to_anchor=(0.5, 1.05), frameon=False)
    elif metric['fig_name'] == 'Summary_EconLoss_6panel':
        baseline_patch = Patch(facecolor=colors['Baseline'], alpha=0.6)
        axes[0, 1].legend([baseline_patch], ['Baseline'], fontsize=18, loc='lower left', bbox_to_anchor=(0, 0), frameon=False)

    # --- Bottom row: Protect/Realign vs Baseline (mean + 95% CI from Statistics_Acute_PerSim.csv) ---
    active_policies = ['Protect', 'Realign']
    for col, hazard in enumerate(hazards):
        ax = axes[1, col]
        # For Summary_Damage_6panel, move only (d) and (f) to top right
        if metric['fig_name'] == 'Summary_Damage_6panel' and col in [0, 2]:
            ax.text(0.97, 0.93, panel_labels[3+col], transform=ax.transAxes, fontsize=20, fontweight='bold', va='top', ha='right')
        else:
            ax.text(0.03, 0.93, panel_labels[3+col], transform=ax.transAxes, fontsize=20, fontweight='bold', va='top', ha='left')
        ax.set_title("")
        if col == 0:
            ax.set_ylabel(metric['change_ylabel'], fontsize=20)
        else:
            ax.set_ylabel("")
        ax.tick_params(axis='y', labelsize=20)
        ax.grid(True, alpha=0.3, axis='y')
        ax.grid(True, alpha=0.3, axis='x')
        # Explicitly add vertical grid lines at the correct x positions
        if metric['fig_name'] == 'Summary_Damage_6panel':
            x_positions = [i * 2 + 0.175 for i in range(6)]
        elif metric['fig_name'] == 'Summary_LifeSafety_6panel':
            x_positions = [i * 2 + 0.175 for i in range(3)]
        elif metric['fig_name'] == 'Summary_EconLoss_6panel':
            x_positions = [0.75, 1, 1.25]
        elif metric['fig_name'] == 'Summary_PopImp_6panel':
            x_positions = [0, 0.18]
        else:
            x_positions = []
        for xpos in x_positions:
            ax.axvline(x=xpos, color='gray', linestyle=':', alpha=0.5, zorder=0)
        if metric['fig_name'] == 'Summary_Damage_6panel':
            bar_positions = []
            means = []
            cis = []
            colors_list = []
            for ds_idx, ds in enumerate([0, 1, 2, 3, 4, '>0']):
                for p_idx, policy in enumerate(active_policies):
                    base_row = stats[(stats['Policy'] == 'Baseline') & (stats['Hazard'] == hazard) & (stats['Metric'] == f'DS_{ds}')]
                    pol_row = stats[(stats['Policy'] == policy) & (stats['Hazard'] == hazard) & (stats['Metric'] == f'DS_{ds}')]
                    position = ds_idx * 2 + p_idx * 0.35
                    bar_positions.append(position)
                    colors_list.append(colors[policy])
                    if not base_row.empty and not pol_row.empty:
                        base_mean = base_row['Mean'].values[0]
                        pol_mean = pol_row['Mean'].values[0]
                        base_std = base_row['Std'].values[0]
                        pol_std = pol_row['Std'].values[0]
                        if base_mean == 0 and pol_mean == 0:
                            means.append(0)
                            cis.append(0)
                        elif base_mean != 0:
                            pct_change = 100 * (pol_mean - base_mean) / base_mean
                            pct_std = 100 * np.sqrt((pol_std / base_mean) ** 2 + (pol_mean * base_std / base_mean ** 2) ** 2)
                            ci = 1.96 * pct_std / np.sqrt(N_ITER)
                            means.append(pct_change)
                            cis.append(ci)
                        else:
                            means.append(0)
                            cis.append(0)
                    else:
                        means.append(0)
                        cis.append(0)
            for i in range(len(bar_positions)):
                ax.bar(bar_positions[i], means[i], yerr=cis[i], capsize=6, color=colors_list[i], width=0.36, alpha=0.8, error_kw={'ecolor': colors_list[i]})  # increased width
            ax.set_xticks([i * 2 + 0.175 for i in range(6)])
            ax.set_xticklabels(metric['labels'], fontsize=20)
        elif metric['fig_name'] == 'Summary_LifeSafety_6panel':
            # For bottom panels, make Protect and Realign bars truly adjacent (edges touch)
            bar_width = 0.06
            metric_centers = [0.65, 1, 1.35]
            means = []
            cis = []
            colors_list = []
            bar_positions = []
            for metric_idx, key in enumerate(['Fatality', 'Injury', 'Casualty']):
                left_center = metric_centers[metric_idx] - bar_width/2
                right_center = metric_centers[metric_idx] + bar_width/2
                for p_idx, policy in enumerate(active_policies):
                    base_row = stats[(stats['Policy'] == 'Baseline') & (stats['Hazard'] == hazard) & (stats['Metric'] == key)]
                    pol_row = stats[(stats['Policy'] == policy) & (stats['Hazard'] == hazard) & (stats['Metric'] == key)]
                    if p_idx == 0:
                        position = left_center
                    else:
                        position = right_center
                    bar_positions.append(position)
                    colors_list.append(colors[policy])
                    if not base_row.empty and not pol_row.empty:
                        base_mean = base_row['Mean'].values[0]
                        pol_mean = pol_row['Mean'].values[0]
                        base_std = base_row['Std'].values[0]
                        pol_std = pol_row['Std'].values[0]
                        if base_mean != 0:
                            pct_change = 100 * (pol_mean - base_mean) / base_mean
                            pct_std = 100 * np.sqrt((pol_std / base_mean) ** 2 + (pol_mean * base_std / base_mean ** 2) ** 2)
                        else:
                            pct_change = 0
                            pct_std = 0
                        ci = 1.96 * pct_std / np.sqrt(N_ITER)
                        means.append(pct_change)
                        cis.append(ci)
                    else:
                        means.append(0)
                        cis.append(0)
            for i in range(len(bar_positions)):
                ax.bar(bar_positions[i], means[i], yerr=cis[i], capsize=6, color=colors_list[i], width=bar_width, alpha=0.8, error_kw={'ecolor': colors_list[i]})
            ax.set_xlim([0.5, 1.5])
            ax.set_xticks([0.65, 1, 1.35])
            ax.set_xticklabels(metric['labels'], fontsize=20)
        elif metric['fig_name'] == 'Summary_EconLoss_6panel':
            econloss_xs = [0.75, 1.25]
            means = []
            cis = []
            colors_list = []
            for p_idx, policy in enumerate(active_policies):
                base_row = stats[(stats['Policy'] == 'Baseline') & (stats['Hazard'] == hazard) & (stats['Metric'] == 'Economic_Loss')]
                pol_row = stats[(stats['Policy'] == policy) & (stats['Hazard'] == hazard) & (stats['Metric'] == 'Economic_Loss')]
                position = econloss_xs[p_idx]
                colors_list.append(colors[policy])
                if not base_row.empty and not pol_row.empty:
                    base_mean = base_row['Mean'].values[0]
                    pol_mean = pol_row['Mean'].values[0]
                    base_std = base_row['Std'].values[0]
                    pol_std = pol_row['Std'].values[0]
                    if base_mean != 0:
                        pct_change = 100 * (pol_mean - base_mean) / base_mean
                        pct_std = 100 * np.sqrt((pol_std / base_mean) ** 2 + (pol_mean * base_std / base_mean ** 2) ** 2)
                    else:
                        pct_change = 0
                        pct_std = 0
                    ci = 1.96 * pct_std / np.sqrt(N_ITER)
                    means.append(pct_change)
                    cis.append(ci)
                else:
                    means.append(0)
                    cis.append(0)
            for i in range(len(econloss_xs)):
                ax.bar(econloss_xs[i], means[i], yerr=cis[i], capsize=6, color=colors_list[i], width=0.16, alpha=0.8, error_kw={'ecolor': colors_list[i]})
            ax.set_xlim([0.5, 1.5])
            if col == 1:
                ax.set_xticks([1])
                ax.set_xticklabels(['Policy'], fontsize=20)
            else:
                ax.set_xticks([1])
                ax.set_xticklabels([''], fontsize=20)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: '%d' % x))
        elif metric['fig_name'] == 'Summary_PopImp_6panel':
            bar_positions = [0, 0.18]
            means = []
            cis = []
            colors_list = []
            for p_idx, policy in enumerate(active_policies):
                base_row = stats[(stats['Policy'] == 'Baseline') & (stats['Hazard'] == hazard) & (stats['Metric'] == 'Population_Impacted')]
                pol_row = stats[(stats['Policy'] == policy) & (stats['Hazard'] == hazard) & (stats['Metric'] == 'Population_Impacted')]
                position = bar_positions[p_idx]
                colors_list.append(colors[policy])
                if not base_row.empty and not pol_row.empty:
                    base_mean = base_row['Mean'].values[0]
                    pol_mean = pol_row['Mean'].values[0]
                    base_std = base_row['Std'].values[0]
                    pol_std = pol_row['Std'].values[0]
                    if base_mean != 0:
                        pct_change = 100 * (pol_mean - base_mean) / base_mean
                        pct_std = 100 * np.sqrt((pol_std / base_mean) ** 2 + (pol_mean * base_std / base_mean ** 2) ** 2)
                    else:
                        pct_change = 0
                        pct_std = 0
                    ci = 1.96 * pct_std / np.sqrt(N_ITER)
                    means.append(pct_change)
                    cis.append(ci)
                else:
                    means.append(0)
                    cis.append(0)
            ax.bar(bar_positions, means, yerr=cis, capsize=6, color=colors_list, width=0.12, alpha=0.8)
            if col == 1:
                ax.set_xticks([0, 0.18])
                ax.set_xticklabels(['Population Impacted by Damage', ''], fontsize=20)
            else:
                ax.set_xticks([0, 0.18])
                ax.set_xticklabels(['', ''])
    legend_elements = [
        Patch(facecolor=colors['Protect'], alpha=0.6, label='Protect vs Baseline'),
        Patch(facecolor=colors['Realign'], alpha=0.6, label='Realign vs Baseline')
    ]
    # Move legend for Summary_LifeSafety_6panel from panel (e) (axes[1,1]) to panel (d) (axes[1,0]) at bottom left
    if metric['fig_name'] == 'Summary_Damage_6panel':
        axes[1, 1].legend(handles=legend_elements, fontsize=18, loc='lower left', bbox_to_anchor=(0, 0), frameon=False, ncol=1)
    elif metric['fig_name'] == 'Summary_LifeSafety_6panel':
        axes[1, 0].legend(handles=legend_elements, fontsize=18, loc='lower left', bbox_to_anchor=(0, 0), frameon=False, ncol=1)
    elif metric['fig_name'] == 'Summary_EconLoss_6panel':
        axes[1, 1].legend(handles=legend_elements, fontsize=18, loc='lower left', bbox_to_anchor=(0, 0), frameon=False, ncol=1)
    else:
        axes[1, 1].legend(handles=legend_elements, fontsize=18, loc='upper center', bbox_to_anchor=(0.5, 1.05), frameon=False, ncol=1)
    if metric['fig_name'] == 'Summary_Damage_6panel':
        axes[1, 1].set_xlabel('Damage State', fontsize=20, fontweight='bold', labelpad=16)
    if metric['fig_name'] == 'Summary_LifeSafety_6panel':
        axes[1, 1].set_xlabel('Life Safety', fontsize=20, fontweight='bold', labelpad=16)
    plt.tight_layout()
    fig.savefig(output_path / f'{metric["fig_name"]}.png', dpi=300, bbox_inches='tight')
    fig.savefig(output_path / f'{metric["fig_name"]}.svg', bbox_inches='tight')
    plt.close()
    print(f'Saved: {output_path / metric["fig_name"]}.png and .svg')


def make_summary_econloss_6panel_pv():
    """Plot Baseline mean + 95% CI for total economic loss components and percent change for Protect/Realign."""
    per_sim_path = Path(f'{REPO_ROOT}/Results/EconomicAnalysis/Results_Acute_Economics_PerSim.csv')
    econ_df = pd.read_csv(per_sim_path)
    iter_cols = [c for c in econ_df.columns if c.startswith('Iter_')]
    if not iter_cols:
        raise ValueError(f'No Iter_ columns found in {per_sim_path}')
    n_iter = len(iter_cols)

    hazards = ['EQ', 'TSU', 'EQ_AND_TSU']
    categories = ['Building_Damage', 'Life_Safety', 'Building_AND_Life']
    group_labels = ['Building', 'Casualty', 'Total']
    policy_colors = {'Baseline': '#FF0000', 'Protect': '#00FF00', 'Realign': '#0000FF'}
    panel_labels = ['(a)', '(b)', '(c)', '(d)', '(e)', '(f)']
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    def get_values(policy, hazard, category, metric):
        rows = econ_df[
            (econ_df['Policy'] == policy)
            & (econ_df['Hazard'] == hazard)
            & (econ_df['Category'] == category)
            & (econ_df['Metric'] == metric)
        ]
        if not rows.empty:
            return rows.iloc[0][iter_cols].astype(float).to_numpy()
        if category == 'Building_AND_Life':
            component_values = [get_values(policy, hazard, component, metric) for component in ['Building_Damage', 'Life_Safety']]
            if all(values is not None for values in component_values):
                return component_values[0] + component_values[1]
        return None

    for col, hazard in enumerate(hazards):
        ax = axes[0, col]
        ax.text(0.03, 0.93, panel_labels[col], transform=ax.transAxes, fontsize=20, fontweight='bold', va='top', ha='left')
        ax.set_title(hazard.replace('EQ_AND_TSU', 'EQ + TSU'), fontsize=20, fontweight='bold')
        ax.set_ylabel('Loss (M$)' if col == 0 else '', fontsize=20)
        means = []
        cis = []
        for category in categories:
            values = get_values('Baseline', hazard, category, 'Economic_Loss')
            if values is None:
                means.append(0.0)
                cis.append(0.0)
                continue
            mean = values.mean()
            std = values.std(ddof=1) if len(values) > 1 else 0.0
            ci = 1.96 * std / np.sqrt(n_iter)
            means.append(mean)
            cis.append(ci)

        x = np.arange(len(categories))
        ax.bar(x, means, yerr=cis, capsize=6, color=policy_colors['Baseline'], width=0.5, alpha=0.8, error_kw={'ecolor': policy_colors['Baseline']})
        ax.set_xticks([])
        ax.tick_params(axis='x', bottom=False, labelbottom=False)
        ax.tick_params(axis='y', labelsize=18)
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_xlim(-0.5, len(categories) - 0.5)

        # bottom row growth vs baseline, using the same percent-change convention as the other summary plots
        ax2 = axes[1, col]
        ax2.text(0.03, 0.93, panel_labels[3 + col], transform=ax2.transAxes, fontsize=20, fontweight='bold', va='top', ha='left')
        ax2.set_ylabel('Loss (% change)' if col == 0 else '', fontsize=20)
        ax2.axhline(0, color='black', linewidth=1)
        ax2.grid(True, alpha=0.3, axis='y')
        positions = []
        heights = []
        errors = []
        colors_list = []
        for policy in ['Protect', 'Realign']:
            for i, category in enumerate(categories):
                base_vals = get_values('Baseline', hazard, category, 'Economic_Loss')
                pol_vals = get_values(policy, hazard, category, 'Economic_Loss_Reduction')
                if base_vals is None or pol_vals is None:
                    pct_change = 0.0
                    pct_std = 0.0
                else:
                    base_mean = base_vals.mean()
                    pol_mean = pol_vals.mean()
                    if abs(base_mean) < 1e-12:
                        pct_change = 0.0
                        pct_std = 0.0
                    else:
                        pct_change = -100.0 * pol_mean / base_mean
                        base_std = base_vals.std(ddof=1)
                        pol_std = pol_vals.std(ddof=1)
                        pct_std = 100.0 * np.sqrt((pol_std / base_mean) ** 2 + (pol_mean * base_std / base_mean ** 2) ** 2)
                ci = 1.96 * pct_std / np.sqrt(n_iter)
                positions.append(i + (0.25 * (0 if policy == 'Protect' else 1) - 0.125))
                heights.append(pct_change)
                errors.append(ci)
                colors_list.append(policy_colors[policy])

        width = 0.22
        for x_pos, height, err, color in zip(positions, heights, errors, colors_list):
            ax2.bar(x_pos, height, yerr=err, capsize=6, width=width, color=color, alpha=0.8, error_kw={'ecolor': color})

        ax2.set_xticks(np.arange(len(categories)))
        ax2.set_xticklabels(group_labels, fontsize=18)
        ax2.tick_params(axis='y', labelsize=18)
        ax2.set_xlim(-0.5, len(categories) - 0.5)

    baseline_patch = Patch(facecolor=policy_colors['Baseline'], alpha=0.8, label='Baseline')
    protect_patch = Patch(facecolor=policy_colors['Protect'], alpha=0.8, label='Protect vs Baseline')
    realign_patch = Patch(facecolor=policy_colors['Realign'], alpha=0.8, label='Realign vs Baseline')
    axes[0, 1].legend(handles=[baseline_patch], fontsize=16, loc='center left', frameon=False)
    axes[1, 1].legend(handles=[protect_patch, realign_patch], fontsize=16, loc='lower left', frameon=False)
    axes[1, 1].set_xlabel('Economic Loss', fontsize=20, fontweight='bold', labelpad=16)
    fig.tight_layout()
    fig.savefig(output_path / 'Summary_EconLoss_6panel_PV.png', dpi=300, bbox_inches='tight')
    fig.savefig(output_path / 'Summary_EconLoss_6panel_PV.svg', bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {output_path / "Summary_EconLoss_6panel_PV"}.png and .svg')


def make_summary_npv_2bar_pv():
    """Plot Protect and Realign mean NPV with 95% CI for the joint hazard."""
    per_sim_path = Path(f'{REPO_ROOT}/Results/EconomicAnalysis/Results_Acute_Economics_PerSim.csv')
    econ_df = pd.read_csv(per_sim_path)
    iter_cols = [c for c in econ_df.columns if c.startswith('Iter_')]
    if not iter_cols:
        raise ValueError(f'No Iter_ columns found in {per_sim_path}')

    means = []
    cis = []
    policies = ['Protect', 'Realign']
    colors_list = [colors['Protect'], colors['Realign']]
    for policy in policies:
        rows = econ_df[
            (econ_df['Policy'] == policy)
            & (econ_df['Hazard'] == 'EQ_AND_TSU')
            & (econ_df['Category'] == 'Building_AND_Life')
            & (econ_df['Metric'] == 'Net_Present_Value')
        ]
        if rows.empty:
            means.append(0.0)
            cis.append(0.0)
            continue
        values = rows.iloc[0][iter_cols].astype(float).to_numpy()
        means.append(values.mean())
        std = values.std(ddof=1) if len(values) > 1 else 0.0
        cis.append(1.96 * std / np.sqrt(len(values)))

    fig, ax = plt.subplots(figsize=(8, 7))
    x = np.arange(len(policies))
    for x_pos, mean, ci, color in zip(x, means, cis, colors_list):
        ax.bar(x_pos, mean, yerr=ci, capsize=7, color=color, width=0.5, alpha=0.8,
               error_kw={'ecolor': color})
    ax.set_ylabel('Net Present Value (M$)', fontsize=20)
    ax.set_xticks(x)
    ax.set_xticklabels(policies, fontsize=18)
    ax.tick_params(axis='y', labelsize=18)
    ax.grid(True, alpha=0.3, axis='y')
    ax.axhline(0, color='black', linewidth=1)
    ax.set_title('EQ + TSU', fontsize=20, fontweight='bold')
    fig.tight_layout()
    fig.savefig(output_path / 'Summary_NPV_2bar_PV.png', dpi=300, bbox_inches='tight')
    fig.savefig(output_path / 'Summary_NPV_2bar_PV.svg', bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {output_path / "Summary_NPV_2bar_PV"}.png and .svg')


make_results_report_acute_pv()
make_summary_econloss_6panel_pv()
make_summary_npv_2bar_pv()
