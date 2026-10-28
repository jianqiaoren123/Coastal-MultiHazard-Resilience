
# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()

# Updated BothHazard_plots_PV.py in Aug 2026 to:

# Add PV figures for 2050, 2070, and 2090.
# Generate physical, social, and economic Main/SI figures.
# Calculate panel values from per-simulation absolute benefits divided by matching baseline or cumulative-cost data.
# Calculate means, standard deviations, and 95% CIs from simulation-level ratios.
# Add NPV figures for 2050, 2070, and 2090.
# Save every figure as both PNG and SVG.
# Fix simulation-column mismatches and Matplotlib color errors.
# Correct social metric mapping: Acute uses Casualty; Erosion uses PopulationImpacted.

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Constants and style dictionaries
RESULTS_DIR = f'{REPO_ROOT}/Results/Combined/'
N_ITER = 50
CI_FACTOR = 1.96

# Color and style dictionaries
COLORS = {
    'AC1': {'Low': '#FFAAAA', 'Med': '#FF4444', 'High': '#AA0000'},
    # AC3-A: purple shades
    'AC3-A': {
        'Low': '#d1b3ff',   # light purple
        'Med': '#a259e6',   # medium purple
        'High': '#5e239d'   # dark purple
    },
    # AC3: cyan shades
    'AC3': {
        'Low': '#b2ffff',   # light cyan
        'Med': '#00b7b7',   # medium cyan
        'High': '#006666'   # dark cyan
    },
    # AC3-C: orange shades
    'AC3-C': {
        'Low': '#ffd9b3',   # light orange
        'Med': '#ff9900',   # medium orange
        'High': '#b35900'   # dark orange
    },
}
LINESTYLES = {'Low': ':', 'Med': '--', 'High': '-'}
POLICY_LABELS = {'AC3-C': 'AC3-C', 'AC3': 'AC3', 'AC3-A': 'AC3-A'}

plt.rcParams.update({'axes.labelsize': 18, 'xtick.labelsize': 18, 'ytick.labelsize': 18, 'legend.fontsize': 16})


# Utility for 95% CI
def get_ci(std):
    return CI_FACTOR * std / np.sqrt(N_ITER)

# Data loading functions
def load_csv(name):
    return pd.read_csv(os.path.join(RESULTS_DIR, name))

def _plot_pv_benefit(output_name, panels, slrs, year):
    benefit = pd.read_csv(os.path.join(RESULTS_DIR, 'Statistics_Both_AbsoluteBenefit_Annual_PerSim.csv'))
    baseline = pd.read_csv(os.path.join(RESULTS_DIR, 'Statistics_Both_Metric_Annual_PerSim.csv'))
    cost = pd.read_csv(f'{REPO_ROOT}/Results/EconomicAnalysis/Results_Combined_Economics_CumulativeCost_PerSim.csv')
    policies = ['AC3-A', 'AC3', 'AC3-C']
    benefit_simulations = [column for column in benefit.columns if column.startswith('Sim_')]
    cost_simulations = [column for column in cost.columns if column.startswith('Sim_')]
    benefit_by_number = {column.split()[0]: column for column in benefit_simulations}
    cost_by_number = {column.split()[0]: column for column in cost_simulations}
    baseline_simulations = [column for column in baseline.columns if column.startswith('Sim_')]
    baseline_by_number = {column.split()[0]: column for column in baseline_simulations}
    simulation_numbers = sorted(set(benefit_by_number) & set(cost_by_number) & set(baseline_by_number))
    benefit = benefit[benefit['Year'] == year]
    baseline = baseline[baseline['Year'] == year]
    cost = cost[cost['Year'] == year]

    def scenario_row(data, policy, slr, hazard, metric, policy_column='ProactivePolicy'):
        rows = data[
            (data[policy_column] == policy)
            & (data['SLR'] == slr)
            & (data['Hazard'] == hazard)
            & (data['Metric'] == metric)
        ]
        if len(rows) != 1:
            raise ValueError(f'Expected one row for {policy}, {slr}, {hazard}, {metric}; found {len(rows)}')
        return rows.iloc[0]

    def values_and_ci(policy, slr, hazard, metric, denominator_type):
        benefit_row = scenario_row(benefit, policy, slr, hazard, metric)
        values = pd.to_numeric(
            benefit_row[[benefit_by_number[number] for number in simulation_numbers]],
            errors='coerce',
        ).to_numpy(dtype=float)
        n_simulations = np.isfinite(values).sum()
        if denominator_type:
            if denominator_type == 'baseline':
                denominator_row = scenario_row(baseline, policy, slr, hazard, metric, policy_column='Policy')
                denominator_columns = [baseline_by_number[number] for number in simulation_numbers]
            else:
                denominator_row = scenario_row(cost, policy, slr, 'Both', 'Cost_Cumulatively_Increased')
                denominator_columns = [cost_by_number[number] for number in simulation_numbers]
            denominator = pd.to_numeric(denominator_row[denominator_columns], errors='coerce').to_numpy(dtype=float)
            values = values / denominator
            values = values[np.isfinite(values)]
            if values.size == 0:
                raise ValueError(f'No valid simulations for {policy}, {slr}, {hazard}, {metric}')
            return values.mean(), CI_FACTOR * values.std(ddof=1) / np.sqrt(len(values))
        if n_simulations == 0:
            raise ValueError(f'No valid simulations for {policy}, {slr}, {hazard}, {metric}')
        return benefit_row['Mean'], CI_FACTOR * benefit_row['Std'] / np.sqrt(n_simulations)

    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for index, (label, hazard, metric, top_ylabel, bottom_ylabel) in enumerate(panels):
        ax = axes[index // 2, index % 2]
        denominator_type = 'baseline' if index < 2 else 'cost'
        means, cis, colors = [], [], []
        for policy in policies:
            for slr in slrs:
                mean, ci = values_and_ci(policy, slr, hazard, metric, denominator_type)
                means.append(mean)
                cis.append(ci)
                colors.append(COLORS[policy][slr])

        group_width = 0.45
        bar_width = group_width / len(slrs)
        group_centers = np.linspace(2.0, 2.0 + (group_width + 0.08) * (len(policies) - 1), len(policies))
        for slr_index in range(len(slrs)):
            positions = group_centers - group_width / 2 + bar_width / 2 + slr_index * bar_width
            for policy_index, position in enumerate(positions):
                value_index = policy_index * len(slrs) + slr_index
                ax.bar(
                    [position], [means[value_index]], yerr=[[cis[value_index]], [cis[value_index]]],
                    capsize=6, color=[colors[value_index]], width=bar_width,
                    ecolor=colors[value_index], label=f'SLR-{slrs[slr_index]}' if index == 0 else None,
                )
        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[policy] for policy in policies])
        ax.set_xlim(group_centers[0] - group_width / 2 - 0.2, group_centers[-1] + group_width / 2 + 0.2)
        ax.set_ylabel(bottom_ylabel if denominator_type == 'cost' else top_ylabel, fontsize=16)
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=18, fontweight='bold')
        if index == 1:
            from matplotlib.patches import Patch
            legend = [
                Patch(facecolor=COLORS[policy][slr], label=f'SLR-{slr}')
                for policy in policies for slr in slrs
            ]
            ax.legend(handles=legend, frameon=False, fontsize=14, loc='lower left')

    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'{output_name}.{ext}'), dpi=300)
    plt.close(fig)

def plot_main_physical_med_2070_pv(year=2070):
    panels = [
        ('(a)', 'Acute', 'Damaged', 'Acute Damaged Buildings (# change)', 'Acute Damaged Buildings (# change / M$)'),
        ('(b)', 'Erosion', 'Eroded', 'Eroded Buildings (# change)', 'Eroded Buildings (# change / M$)'),
        ('(c)', 'Acute', 'Damaged', 'Acute Damaged Buildings (# change)', 'Acute Damaged Buildings (# change / M$)'),
        ('(d)', 'Erosion', 'Eroded', 'Eroded Buildings (# change)', 'Eroded Buildings (# change / M$)'),
    ]
    _plot_pv_benefit(f'Main_Both_Physical_Med_{year}_PV', panels, ['Med'], year)

def plot_si_physical_lowhigh_2070_pv(year=2070):
    panels = [
        ('(a)', 'Acute', 'Damaged', 'Acute Damaged Buildings (# change)', 'Acute Damaged Buildings (# change / M$)'),
        ('(b)', 'Erosion', 'Eroded', 'Eroded Buildings (# change)', 'Eroded Buildings (# change / M$)'),
        ('(c)', 'Acute', 'Damaged', 'Acute Damaged Buildings (# change)', 'Acute Damaged Buildings (# change / M$)'),
        ('(d)', 'Erosion', 'Eroded', 'Eroded Buildings (# change)', 'Eroded Buildings (# change / M$)'),
    ]
    _plot_pv_benefit(f'SI_Both_Physical_LowHigh_{year}_PV', panels, ['Low', 'High'], year)

def plot_main_social_med_2070_pv(year=2070):
    panels = [
        ('(a)', 'Acute', 'Casualty', 'Acute Casualties (# change)', 'Acute Casualties (# change / M$)'),
        ('(b)', 'Erosion', 'PopulationImpacted', 'Eroded Impacted Population (# change)', 'Eroded Impacted Population (# change / M$)'),
        ('(c)', 'Acute', 'Casualty', 'Acute Casualties (# change)', 'Acute Casualties (# change / M$)'),
        ('(d)', 'Erosion', 'PopulationImpacted', 'Eroded Impacted Population (# change)', 'Eroded Impacted Population (# change / M$)'),
    ]
    _plot_pv_benefit(f'Main_Both_Social_Med_{year}_PV', panels, ['Med'], year)

def plot_si_social_lowhigh_2070_pv(year=2070):
    panels = [
        ('(a)', 'Acute', 'Casualty', 'Acute Casualties (# change)', 'Acute Casualties (# change / M$)'),
        ('(b)', 'Erosion', 'PopulationImpacted', 'Eroded Impacted Population (# change)', 'Eroded Impacted Population (# change / M$)'),
        ('(c)', 'Acute', 'Casualty', 'Acute Casualties (# change)', 'Acute Casualties (# change / M$)'),
        ('(d)', 'Erosion', 'PopulationImpacted', 'Eroded Impacted Population (# change)', 'Eroded Impacted Population (# change / M$)'),
    ]
    _plot_pv_benefit(f'SI_Both_Social_LowHigh_{year}_PV', panels, ['Low', 'High'], year)

def plot_main_economic_med_2070_pv(year=2070):
    panels = [
        ('(a)', 'Acute', 'EconomicLoss', 'Acute Economic Loss (M$ change)', 'Acute Economic Loss (M$ change / M$)'),
        ('(b)', 'Erosion', 'EconomicLoss', 'Erosion Economic Loss (M$ change)', 'Erosion Economic Loss (M$ change / M$)'),
        ('(c)', 'Acute', 'EconomicLoss', 'Acute Economic Loss (M$ change)', 'Acute Economic Loss (M$ change / M$)'),
        ('(d)', 'Erosion', 'EconomicLoss', 'Erosion Economic Loss (M$ change)', 'Erosion Economic Loss (M$ change / M$)'),
    ]
    _plot_pv_benefit(f'Main_Both_Economic_Med_{year}_PV', panels, ['Med'], year)

def plot_si_economic_lowhigh_2070_pv(year=2070):
    panels = [
        ('(a)', 'Acute', 'EconomicLoss', 'Acute Economic Loss (M$ change)', 'Acute Economic Loss (M$ change / M$)'),
        ('(b)', 'Erosion', 'EconomicLoss', 'Erosion Economic Loss (M$ change)', 'Erosion Economic Loss (M$ change / M$)'),
        ('(c)', 'Acute', 'EconomicLoss', 'Acute Economic Loss (M$ change)', 'Acute Economic Loss (M$ change / M$)'),
        ('(d)', 'Erosion', 'EconomicLoss', 'Erosion Economic Loss (M$ change)', 'Erosion Economic Loss (M$ change / M$)'),
    ]
    _plot_pv_benefit(f'SI_Both_Economic_LowHigh_{year}_PV', panels, ['Low', 'High'], year)


def plot_main_physical_2070():
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cost_benefit = load_csv('Statistics_Both_CostBenefit_Annual_PerSim.csv')
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    panels = [
        ('(a)', 'Acute', 'Damaged', 'Acute Damaged Buildings (% change)', 'rel'),
        ('(b)', 'Flooding', 'Damaged', 'Flood-damaged Buildings (% change)', 'rel'),
        ('(c)', 'Acute', 'Damaged', 'Acute Damaged Buildings (% change / M$)', 'cost'),
        ('(d)', 'Flooding', 'Damaged', 'Flood-damaged Buildings (% change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, ylabel, dtype) in enumerate(panels):
        ax = axes[i // 2, i % 2]
        df = rel_benefit if dtype == 'rel' else cost_benefit
        means, cis, colors = [], [], []
        for pol in ac3_pols:
            for slr in slrs:
                dfp = df[(df['SLR'] == slr) & (df['Hazard'] == hazard) & (df['Metric'] == metric) & (df['Year'] == 2070) & (df['ProactivePolicy'] == pol)]
                if not dfp.empty:
                    means.append(dfp['Mean'].values[0])
                    cis.append(get_ci(dfp['Std'].values)[0])
                    colors.append(COLORS[pol][slr])
                else:
                    means.append(np.nan)
                    cis.append(0)
                    colors.append('#CCCCCC')

        group_width = 0.6
        bar_width = group_width / len(slrs)
        group_centers = np.linspace(2.0, 2.0 + (group_width + 0.12) * (len(ac3_pols) - 1), len(ac3_pols))
        for slr_index, slr in enumerate(slrs):
            positions = group_centers - group_width / 2 + bar_width / 2 + slr_index * bar_width
            for policy_index, position in enumerate(positions):
                value_index = policy_index * len(slrs) + slr_index
                ax.bar(
                    [position], [means[value_index]],
                    yerr=[[cis[value_index]], [cis[value_index]]],
                    capsize=6,
                    color=[colors[value_index]],
                    width=bar_width,
                    ecolor=colors[value_index],
                    label=f'SLR-{slr}' if i == 0 and policy_index == 0 else None,
                )

        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(group_centers[0] - group_width / 2 - 0.2, group_centers[-1] + group_width / 2 + 0.2)
        ax.set_ylabel(ylabel, fontsize=16)
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=18, fontweight='bold')

        if i == 1:
            from matplotlib.patches import Patch
            legend_patches = []
            for pol in ac3_pols:
                for slr in slrs:
                    legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=f'SLR-{slr}'))
            ax.legend(handles=legend_patches, frameon=False, fontsize=14, loc='lower left')

    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'Main_Both_Physical_2070.{ext}'), dpi=300)
    plt.close(fig)


def plot_main_physical_2070_pv(year=2070, output_name='Main_Both_Physical_2070_PV'):
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    absolute_benefit = load_csv('Statistics_Both_AbsoluteBenefit_Annual_PerSim.csv')
    cumulative_cost = pd.read_csv(
        f'{REPO_ROOT}/Results/EconomicAnalysis/Results_Combined_Economics_CumulativeCost_PerSim.csv'
    )
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    benefit_simulations = [column for column in absolute_benefit.columns if column.startswith('Sim_')]
    cost_simulations = [column for column in cumulative_cost.columns if column.startswith('Sim_')]
    benefit_by_number = {column.split()[0]: column for column in benefit_simulations}
    cost_by_number = {column.split()[0]: column for column in cost_simulations}
    simulation_numbers = sorted(set(benefit_by_number) & set(cost_by_number))
    panels = [
        ('(a)', 'Acute', 'Damaged', 'Acute Damaged Buildings (% change)', 'rel'),
        ('(b)', 'Flooding', 'Damaged', 'Flood-damaged Buildings (% change)', 'rel'),
        ('(c)', 'Acute', 'Damaged', 'Acute Damaged Buildings (# change / M$)', 'cost'),
        ('(d)', 'Flooding', 'Damaged', 'Flood-damaged Buildings (# change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, ylabel, dtype) in enumerate(panels):
        ax = axes[i // 2, i % 2]
        means, cis, colors = [], [], []
        for pol in ac3_pols:
            for slr in slrs:
                if dtype == 'rel':
                    rows = rel_benefit[
                        (rel_benefit['SLR'] == slr)
                        & (rel_benefit['Hazard'] == hazard)
                        & (rel_benefit['Metric'] == metric)
                        & (rel_benefit['Year'] == year)
                        & (rel_benefit['ProactivePolicy'] == pol)
                    ]
                    if len(rows) != 1:
                        raise ValueError(f'Expected one relative-benefit row for {pol}, {slr}, {hazard}, {metric}; found {len(rows)}')
                    means.append(rows.iloc[0]['Mean'])
                    cis.append(get_ci(rows.iloc[0]['Std']))
                else:
                    benefit_rows = absolute_benefit[
                        (absolute_benefit['SLR'] == slr)
                        & (absolute_benefit['Hazard'] == hazard)
                        & (absolute_benefit['Metric'] == metric)
                        & (absolute_benefit['Year'] == year)
                        & (absolute_benefit['ProactivePolicy'] == pol)
                    ]
                    cost_rows = cumulative_cost[
                        (cumulative_cost['SLR'] == slr)
                        & (cumulative_cost['Hazard'] == 'Both')
                        & (cumulative_cost['Metric'] == 'Cost_Cumulatively_Increased')
                        & (cumulative_cost['Year'] == year)
                        & (cumulative_cost['ProactivePolicy'] == pol)
                    ]
                    if len(benefit_rows) != 1 or len(cost_rows) != 1:
                        raise ValueError(
                            f'Expected one benefit and cost row for {pol}, {slr}, {hazard}, {metric}; '
                            f'found {len(benefit_rows)} and {len(cost_rows)}'
                        )
                    benefits = pd.to_numeric(
                        benefit_rows.iloc[0][[benefit_by_number[number] for number in simulation_numbers]],
                        errors='coerce',
                    ).to_numpy(dtype=float)
                    costs = pd.to_numeric(
                        cost_rows.iloc[0][[cost_by_number[number] for number in simulation_numbers]],
                        errors='coerce',
                    ).to_numpy(dtype=float)
                    ratios = benefits / costs
                    ratios = ratios[np.isfinite(ratios)]
                    if ratios.size == 0:
                        raise ValueError(f'No valid benefit-to-cost ratios for {pol}, {slr}, {hazard}, {metric}')
                    means.append(ratios.mean())
                    cis.append(CI_FACTOR * ratios.std(ddof=1) / np.sqrt(ratios.size))
                colors.append(COLORS[pol][slr])

        group_width = 0.6
        bar_width = group_width / len(slrs)
        group_centers = np.linspace(2.0, 2.0 + (group_width + 0.12) * (len(ac3_pols) - 1), len(ac3_pols))
        for slr_index, slr in enumerate(slrs):
            positions = group_centers - group_width / 2 + bar_width / 2 + slr_index * bar_width
            for policy_index, position in enumerate(positions):
                value_index = policy_index * len(slrs) + slr_index
                ax.bar(
                    [position], [means[value_index]],
                    yerr=[[cis[value_index]], [cis[value_index]]],
                    capsize=6,
                    color=[colors[value_index]],
                    width=bar_width,
                    ecolor=colors[value_index],
                    label=f'SLR-{slr}' if i == 0 and policy_index == 0 else None,
                )

        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(group_centers[0] - group_width / 2 - 0.2, group_centers[-1] + group_width / 2 + 0.2)
        ax.set_ylabel(ylabel, fontsize=16)
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=18, fontweight='bold')

        if i == 1:
            from matplotlib.patches import Patch
            legend_patches = []
            for pol in ac3_pols:
                for slr in slrs:
                    legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=f'{pol} SLR-{slr}'))
            ax.legend(handles=legend_patches, frameon=False, fontsize=11, loc='lower left')

    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'{output_name}.{ext}'), dpi=300)
    plt.close(fig)


def plot_main_social_2070_pv(year=2070, output_name='SI_Both_Social_2070_PV'):
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    absolute_benefit = load_csv('Statistics_Both_AbsoluteBenefit_Annual_PerSim.csv')
    cumulative_cost = pd.read_csv(
        f'{REPO_ROOT}/Results/EconomicAnalysis/Results_Combined_Economics_CumulativeCost_PerSim.csv'
    )
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    benefit_simulations = [column for column in absolute_benefit.columns if column.startswith('Sim_')]
    cost_simulations = [column for column in cumulative_cost.columns if column.startswith('Sim_')]
    benefit_by_number = {column.split()[0]: column for column in benefit_simulations}
    cost_by_number = {column.split()[0]: column for column in cost_simulations}
    simulation_numbers = sorted(set(benefit_by_number) & set(cost_by_number))
    panels = [
        ('(a)', 'Acute', 'Casualty', 'Acute Casualties (% change)', 'rel'),
        ('(b)', 'Flooding', 'PopulationImpacted', 'Flood-impacted Population (% change)', 'rel'),
        ('(c)', 'Acute', 'Casualty', 'Acute Casualties (# change / M$)', 'cost'),
        ('(d)', 'Flooding', 'PopulationImpacted', 'Flood-impacted Population (# change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, ylabel, dtype) in enumerate(panels):
        ax = axes[i // 2, i % 2]
        means, cis, colors = [], [], []
        for pol in ac3_pols:
            for slr in slrs:
                if dtype == 'rel':
                    rows = rel_benefit[
                        (rel_benefit['SLR'] == slr)
                        & (rel_benefit['Hazard'] == hazard)
                        & (rel_benefit['Metric'] == metric)
                        & (rel_benefit['Year'] == year)
                        & (rel_benefit['ProactivePolicy'] == pol)
                    ]
                    if len(rows) != 1:
                        raise ValueError(f'Expected one relative-benefit row for {pol}, {slr}, {hazard}, {metric}; found {len(rows)}')
                    means.append(rows.iloc[0]['Mean'])
                    cis.append(get_ci(rows.iloc[0]['Std']))
                else:
                    benefit_rows = absolute_benefit[
                        (absolute_benefit['SLR'] == slr)
                        & (absolute_benefit['Hazard'] == hazard)
                        & (absolute_benefit['Metric'] == metric)
                        & (absolute_benefit['Year'] == year)
                        & (absolute_benefit['ProactivePolicy'] == pol)
                    ]
                    cost_rows = cumulative_cost[
                        (cumulative_cost['SLR'] == slr)
                        & (cumulative_cost['Hazard'] == 'Both')
                        & (cumulative_cost['Metric'] == 'Cost_Cumulatively_Increased')
                        & (cumulative_cost['Year'] == year)
                        & (cumulative_cost['ProactivePolicy'] == pol)
                    ]
                    if len(benefit_rows) != 1 or len(cost_rows) != 1:
                        raise ValueError(
                            f'Expected one benefit and cost row for {pol}, {slr}, {hazard}, {metric}; '
                            f'found {len(benefit_rows)} and {len(cost_rows)}'
                        )
                    benefits = pd.to_numeric(
                        benefit_rows.iloc[0][[benefit_by_number[number] for number in simulation_numbers]],
                        errors='coerce',
                    ).to_numpy(dtype=float)
                    costs = pd.to_numeric(
                        cost_rows.iloc[0][[cost_by_number[number] for number in simulation_numbers]],
                        errors='coerce',
                    ).to_numpy(dtype=float)
                    ratios = benefits / costs
                    ratios = ratios[np.isfinite(ratios)]
                    if ratios.size == 0:
                        raise ValueError(f'No valid benefit-to-cost ratios for {pol}, {slr}, {hazard}, {metric}')
                    means.append(ratios.mean())
                    cis.append(CI_FACTOR * ratios.std(ddof=1) / np.sqrt(ratios.size))
                colors.append(COLORS[pol][slr])

        group_width = 0.6
        bar_width = group_width / len(slrs)
        group_centers = np.linspace(2.0, 2.0 + (group_width + 0.12) * (len(ac3_pols) - 1), len(ac3_pols))
        for slr_index, slr in enumerate(slrs):
            positions = group_centers - group_width / 2 + bar_width / 2 + slr_index * bar_width
            for policy_index, position in enumerate(positions):
                value_index = policy_index * len(slrs) + slr_index
                ax.bar(
                    [position], [means[value_index]],
                    yerr=[[cis[value_index]], [cis[value_index]]],
                    capsize=6,
                    color=[colors[value_index]],
                    width=bar_width,
                    ecolor=colors[value_index],
                    label=f'SLR-{slr}' if i == 0 and policy_index == 0 else None,
                )

        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(group_centers[0] - group_width / 2 - 0.2, group_centers[-1] + group_width / 2 + 0.2)
        ax.set_ylabel(ylabel, fontsize=16)
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=18, fontweight='bold')

        if i == 1:
            from matplotlib.patches import Patch
            legend_patches = []
            for pol in ac3_pols:
                for slr in slrs:
                    legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=f'{pol} SLR-{slr}'))
            ax.legend(handles=legend_patches, frameon=False, fontsize=11, loc='lower left')

    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'{output_name}.{ext}'), dpi=300)
    plt.close(fig)


def plot_main_economic_2070_pv(year=2070, output_name='SI_Both_Economic_2070_PV'):
    economics_dir = f'{REPO_ROOT}/Results/EconomicAnalysis'
    baseline = pd.read_csv(os.path.join(economics_dir, 'Results_Combined_Economics_Baseline_PerSim.csv'))
    proactive = pd.read_csv(os.path.join(economics_dir, 'Results_Combined_Economics_Proactive_PerSim.csv'))
    cumulative_cost = pd.read_csv(os.path.join(economics_dir, 'Results_Combined_Economics_CumulativeCost_PerSim.csv'))
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    proactive_simulations = [column for column in proactive.columns if column.startswith('Sim_')]
    baseline_simulations = [column for column in baseline.columns if column.startswith('Sim_')]
    cost_simulations = [column for column in cumulative_cost.columns if column.startswith('Sim_')]
    proactive_by_number = {column.split()[0]: column for column in proactive_simulations}
    baseline_by_number = {column.split()[0]: column for column in baseline_simulations}
    cost_by_number = {column.split()[0]: column for column in cost_simulations}
    simulation_numbers = sorted(set(proactive_by_number) & set(baseline_by_number) & set(cost_by_number))
    panels = [
        ('(a)', 'Acute', 'Acute Economic Loss (% change)', 'baseline'),
        ('(b)', 'Chronic', 'Chronic Economic Loss (% change)', 'baseline'),
        ('(c)', 'Acute', 'Acute Benefit-cost Ratio (BCR)', 'cost'),
        ('(d)', 'Chronic', 'Chronic Benefit-cost Ratio (BCR)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, ylabel, denominator_type) in enumerate(panels):
        ax = axes[i // 2, i % 2]
        means, cis, colors = [], [], []
        for pol in ac3_pols:
            for slr in slrs:
                proactive_rows = proactive[
                    (proactive['SLR'] == slr)
                    & (proactive['Hazard'] == hazard)
                    & (proactive['Metric'] == 'Economic_Loss_Reduction')
                    & (proactive['Year'] == year)
                    & (proactive['ProactivePolicy'] == pol)
                ]
                if denominator_type == 'baseline':
                    denominator_rows = baseline[
                        (baseline['SLR'] == slr)
                        & (baseline['Hazard'] == hazard)
                        & (baseline['Metric'] == 'Economic_Loss')
                        & (baseline['Year'] == year)
                        & (baseline['Policy'] == 'Baseline')
                    ]
                    denominator_columns = [baseline_by_number[number] for number in simulation_numbers]
                    multiplier = 100
                else:
                    denominator_rows = cumulative_cost[
                        (cumulative_cost['SLR'] == slr)
                        & (cumulative_cost['Hazard'] == 'Both')
                        & (cumulative_cost['Metric'] == 'Cost_Cumulatively_Increased')
                        & (cumulative_cost['Year'] == year)
                        & (cumulative_cost['ProactivePolicy'] == pol)
                    ]
                    denominator_columns = [cost_by_number[number] for number in simulation_numbers]
                    multiplier = 1
                if len(proactive_rows) != 1 or len(denominator_rows) != 1:
                    raise ValueError(
                        f'Expected one proactive and denominator row for {pol}, {slr}, {hazard}; '
                        f'found {len(proactive_rows)} and {len(denominator_rows)}'
                    )
                proactive_values = pd.to_numeric(
                    proactive_rows.iloc[0][[proactive_by_number[number] for number in simulation_numbers]],
                    errors='coerce',
                ).to_numpy(dtype=float)
                denominator_values = pd.to_numeric(
                    denominator_rows.iloc[0][denominator_columns],
                    errors='coerce',
                ).to_numpy(dtype=float)
                values = -proactive_values / denominator_values * multiplier
                values = values[np.isfinite(values)]
                if values.size == 0:
                    raise ValueError(f'No valid economic ratios for {pol}, {slr}, {hazard}')
                means.append(values.mean())
                cis.append(CI_FACTOR * values.std(ddof=1) / np.sqrt(values.size))
                colors.append(COLORS[pol][slr])

        group_width = 0.6
        bar_width = group_width / len(slrs)
        group_centers = np.linspace(2.0, 2.0 + (group_width + 0.12) * (len(ac3_pols) - 1), len(ac3_pols))
        for slr_index, slr in enumerate(slrs):
            positions = group_centers - group_width / 2 + bar_width / 2 + slr_index * bar_width
            for policy_index, position in enumerate(positions):
                value_index = policy_index * len(slrs) + slr_index
                ax.bar(
                    [position], [means[value_index]],
                    yerr=[[cis[value_index]], [cis[value_index]]],
                    capsize=6,
                    color=[colors[value_index]],
                    width=bar_width,
                    ecolor=colors[value_index],
                    label=f'SLR-{slr}' if i == 0 and policy_index == 0 else None,
                )
        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(group_centers[0] - group_width / 2 - 0.2, group_centers[-1] + group_width / 2 + 0.2)
        ax.set_ylabel(ylabel, fontsize=16)
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=18, fontweight='bold')
        if i == 1:
            from matplotlib.patches import Patch
            legend_patches = []
            for pol in ac3_pols:
                for slr in slrs:
                    legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=f'{pol} SLR-{slr}'))
            ax.legend(handles=legend_patches, frameon=False, fontsize=11, loc='lower left')

    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'{output_name}.{ext}'), dpi=300)
    plt.close(fig)

# Main Figure 1: Physical (Relative Benefit & Cost-Benefit, SLR-Med, 2070)
def plot_main_physical_med():
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cost_benefit = load_csv('Statistics_Both_CostBenefit_Annual_PerSim.csv')
    
    # Filter for SLR=Med, Year=2070, relevant policies, metrics
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']  # order: AC3-A, AC3, AC3-C
    panels = [
        # (Hazard, Metric, ylabel, data_type)
        ('Acute', 'Damaged', 'Acute Damaged Buildings (% change)', 'rel'),
        ('Flooding', 'Damaged', 'Flood-damaged Buildings (% change)', 'rel'),
        ('Acute', 'Damaged', 'Acute Damaged Buildings (% change / M$)', 'cost'),
        ('Flooding', 'Damaged', 'Flood-damaged Buildings (% change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    panel_labels = ['(a)', '(b)', '(c)', '(d)']
    for i, (hazard, metric, ylabel, dtype) in enumerate(panels):
        ax = axes[i//2, i%2]
        if dtype == 'rel':
            df = rel_benefit
        else:
            df = cost_benefit
        # Filter
        dfp = df[(df['SLR']=='Med') & (df['Hazard']==hazard) & (df['Metric']==metric) & (df['Year']==2070) & (df['ProactivePolicy'].isin(ac3_pols))]
        # Ensure order
        dfp = dfp.set_index('ProactivePolicy').loc[ac3_pols]
        means = dfp['Mean'].values
        cis = get_ci(dfp['Std'].values)
        # Use same bar width and positions as Main_Both_Social_Med
        bar_width = 0.5 * 0.8
        n_bars = 3
        margin = 2.0
        spacing = 0.6
        bar_positions = np.linspace(margin, margin + spacing * (n_bars - 1), n_bars)
        bar_colors = [COLORS[p]["Med"] for p in ac3_pols]
        for pos, mean, ci, color in zip(bar_positions, means, cis, bar_colors):
            ax.bar([pos], [mean], yerr=[[ci], [ci]], capsize=6, color=[color], width=bar_width, ecolor=color)
        ax.set_xticks(bar_positions)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(bar_positions[0] - bar_width/2 - 0.2, bar_positions[-1] + bar_width/2 + 0.2)
        ax.set_ylabel(ylabel, fontsize=17)
        # Consistent y-tick labeling for (d) panel
        if i == 3:
            yticks = np.arange(0.0, -0.41, -0.1)
            ax.set_yticks(yticks)
            ax.set_yticklabels([f"{y:.1f}" for y in yticks])
        ax.grid(True, alpha=0.3)
        # Add panel label (a)-(d)
        ax.text(0.03, 0.93, panel_labels[i], transform=ax.transAxes, ha='left', va='top', fontsize=18, fontweight='bold')
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'Main_Both_Physical_Med_2070.{ext}'), dpi=300)
    plt.close(fig)

def plot_main_social_med():
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cost_benefit = load_csv('Statistics_Both_CostBenefit_Annual_PerSim.csv')
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    panels = [
        ('(a)', 'Acute', 'Casualty', 'Acute Casualties (% change)', 'rel'),
        ('(b)', 'Flooding', 'PopulationImpacted', 'Flood-impacted Population (% change)', 'rel'),
        ('(c)', 'Acute', 'Casualty', 'Acute Casualties (% change / M$)', 'cost'),
        ('(d)', 'Flooding', 'PopulationImpacted', 'Flood-impacted Population (% change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, ylabel, dtype) in enumerate(panels):
        ax = axes[i//2, i%2]
        df = rel_benefit if dtype == 'rel' else cost_benefit
        dfp = df[(df['SLR']=='Med') & (df['Hazard']==hazard) & (df['Metric']==metric) & (df['Year']==2070) & (df['ProactivePolicy'].isin(ac3_pols))]
        dfp = dfp.set_index('ProactivePolicy').loc[ac3_pols]
        means = dfp['Mean'].values
        cis = get_ci(dfp['Std'].values)
        bar_width = 0.5 * 0.8
        n_bars = 3
        margin = 2.0
        spacing = 0.6
        bar_positions = np.linspace(margin, margin + spacing * (n_bars - 1), n_bars)
        bar_colors = [COLORS[p]["Med"] for p in ac3_pols]
        for pos, mean, ci, color in zip(bar_positions, means, cis, bar_colors):
            ax.bar([pos], [mean], yerr=[[ci], [ci]], capsize=6, color=[color], width=bar_width, ecolor=color)
        ax.set_xticks(bar_positions)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(bar_positions[0] - bar_width/2 - 0.2, bar_positions[-1] + bar_width/2 + 0.2)
        ax.set_ylabel(ylabel, fontsize=16)
        if i == 3:
            yticks = np.arange(0.0, -0.41, -0.1)
            ax.set_yticks(yticks)
            ax.set_yticklabels([f"{y:.1f}" for y in yticks])
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=18, fontweight='bold')
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'Main_Both_Social_Med_2070.{ext}'), dpi=300)
    plt.close(fig)

def plot_main_economic_med():
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cost_benefit = load_csv('Statistics_Both_CostBenefit_Annual_PerSim.csv')
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    panels = [
        ('(a)', 'Acute', 'EconomicLoss', 'Acute Economic Loss (% change)', 'rel'),
        ('(b)', 'Flooding', 'EconomicLoss', 'Flood Economic Loss (% change)', 'rel'),
        ('(c)', 'Acute', 'EconomicLoss', 'Acute Economic Loss (% change / M$)', 'cost'),
        ('(d)', 'Flooding', 'EconomicLoss', 'Flood Economic Loss (% change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, ylabel, dtype) in enumerate(panels):
        ax = axes[i//2, i%2]
        df = rel_benefit if dtype == 'rel' else cost_benefit
        dfp = df[(df['SLR']=='Med') & (df['Hazard']==hazard) & (df['Metric']==metric) & (df['Year']==2070) & (df['ProactivePolicy'].isin(ac3_pols))]
        dfp = dfp.set_index('ProactivePolicy').loc[ac3_pols]
        means = dfp['Mean'].values
        cis = get_ci(dfp['Std'].values)
        bar_width = 0.5 * 0.8
        n_bars = 3
        margin = 2.0
        spacing = 0.6
        bar_positions = np.linspace(margin, margin + spacing * (n_bars - 1), n_bars)
        bar_colors = [COLORS[p]["Med"] for p in ac3_pols]
        for pos, mean, ci, color in zip(bar_positions, means, cis, bar_colors):
            ax.bar([pos], [mean], yerr=[[ci], [ci]], capsize=6, color=[color], width=bar_width, ecolor=color)
        ax.set_xticks(bar_positions)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(bar_positions[0] - bar_width/2 - 0.2, bar_positions[-1] + bar_width/2 + 0.2)
        ax.set_ylabel(ylabel)
        if i == 3:
            yticks = np.arange(0.0, -0.41, -0.1)
            ax.set_yticks(yticks)
            ax.set_yticklabels([f"{y:.1f}" for y in yticks])
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=16, fontweight='bold')
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'Main_Both_Economic_Med_2070.{ext}'), dpi=300)
    plt.close(fig)

def plot_main_cumulative_cost_acute_year():
    df = pd.read_csv(f'{REPO_ROOT}/Results/EconomicAnalysis/Results_Combined_Economics_CumulativeCost_PerSim.csv')
    years = [2050, 2070, 2090]
    slrs = ['Low', 'Med', 'High']
    policies = ['AC3-A', 'AC3', 'AC3-C']
    simulation_columns = [column for column in df.columns if column.startswith('Sim_')]

    df = df[
        (df['Hazard'] == 'Both')
        & (df['Metric'] == 'Cost_Cumulatively_Increased')
        & (df['Year'].isin(years))
        & (df['ProactivePolicy'].isin(policies))
    ].copy()
    df['n_simulations'] = df[simulation_columns].notna().sum(axis=1)
    df['CI95'] = CI_FACTOR * df['Std (M$)'] / np.sqrt(df['n_simulations'])

    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    panel_labels = ['(a)', '(b)', '(c)']
    width = 0.07 * 1.2
    slr_gap = 0.04
    group_gap = 0.12

    for panel_index, year in enumerate(years):
        ax = axes[panel_index]
        df_year = df[df['Year'] == year]

        ac3a = df_year[
            (df_year['ProactivePolicy'] == 'AC3-A')
            & (df_year['SLR'] == 'Med')
        ].iloc[0]
        ac3 = [df_year[(df_year['ProactivePolicy'] == 'AC3') & (df_year['SLR'] == slr)].iloc[0] for slr in slrs]
        ac3c = [df_year[(df_year['ProactivePolicy'] == 'AC3-C') & (df_year['SLR'] == slr)].iloc[0] for slr in slrs]

        pos_ac3a = np.array([0.0])
        pos_ac3 = pos_ac3a[-1] + width + group_gap + np.arange(3) * (width + slr_gap)
        pos_ac3c = pos_ac3[-1] + width + group_gap + np.arange(3) * (width + slr_gap)

        ax.bar(
            pos_ac3a, [ac3a['Mean (M$)']], yerr=[[ac3a['CI95']], [ac3a['CI95']]],
            capsize=6, color=[COLORS['AC3-A']['Med']], width=width,
            ecolor=COLORS['AC3-A']['Med'], label='AC3-A' if panel_index == 0 else None,
        )
        for positions, rows, policy in [(pos_ac3, ac3, 'AC3'), (pos_ac3c, ac3c, 'AC3-C')]:
            for position, row, slr in zip(positions, rows, slrs):
                color = COLORS[policy][slr]
                ax.bar(
                    [position], [row['Mean (M$)']], yerr=[[row['CI95']], [row['CI95']]],
                    capsize=6, color=[color], width=width, ecolor=color,
                    label=policy if panel_index == 0 and slr == slrs[0] else None,
                )

        ax.set_xticks([pos_ac3a.mean(), pos_ac3.mean(), pos_ac3c.mean()])
        ax.set_xticklabels(['AC3-A', 'AC3', 'AC3-C'], fontsize=20)
        ax.set_title(str(year), fontsize=20)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='y', labelsize=20)
        ax.text(0.97, 0.93, panel_labels[panel_index], transform=ax.transAxes,
                ha='right', va='top', fontsize=20, fontweight='bold')
        if panel_index == 0:
            ax.set_ylabel('Cumulative Cost Increase (M$)', fontsize=20)
            from matplotlib.patches import Patch
            legend_elements = [Patch(facecolor=COLORS['AC3-A']['Med'], label='AC3-A SLR-Low/Med/High')]
            for policy in ['AC3', 'AC3-C']:
                legend_elements.extend(
                    Patch(facecolor=COLORS[policy][slr], label=f'{policy} SLR-{slr}')
                    for slr in slrs
                )
            ax.legend(handles=legend_elements, frameon=False, loc='upper left', fontsize=16)

    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'SI_Both_CumulativeCost_PV.{ext}'), dpi=300)
    plt.close(fig)

def plot_si_both_npv():
    df = pd.read_csv(
        f'{REPO_ROOT}/Results/EconomicAnalysis/Results_Combined_Economics_NPV_PerSim.csv'
    )
    policies = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    years = [2050, 2070, 2090]
    simulation_columns = [column for column in df.columns if column.startswith('Sim_')]
    df = df[
        (df['Hazard'] == 'Both')
        & (df['Metric'] == 'Net_Present_Value')
        & (df['Year'].isin(years))
        & (df['ProactivePolicy'].isin(policies))
        & (df['SLR'].isin(slrs))
    ].copy()
    df['n_simulations'] = df[simulation_columns].notna().sum(axis=1)
    df['CI95'] = CI_FACTOR * df['Std (M$)'] / np.sqrt(df['n_simulations'])

    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    group_width = 0.6
    bar_width = group_width / len(slrs)
    group_centers = np.arange(len(policies)) * (group_width + 0.25)
    for panel_index, year in enumerate(years):
        ax = axes[panel_index]
        df_year = df[df['Year'] == year]
        for slr_index, slr in enumerate(slrs):
            positions = group_centers - group_width / 2 + bar_width / 2 + slr_index * bar_width
            for policy_index, policy in enumerate(policies):
                rows = df_year[(df_year['ProactivePolicy'] == policy) & (df_year['SLR'] == slr)]
                if len(rows) != 1:
                    raise ValueError(f'Expected one NPV row for {policy}, {slr}, {year}; found {len(rows)}')
                row = rows.iloc[0]
                ax.bar(
                    [positions[policy_index]], [row['Mean (M$)']],
                    yerr=[[row['CI95']], [row['CI95']]], capsize=6,
                    color=[COLORS[policy][slr]], width=bar_width,
                    ecolor=COLORS[policy][slr],
                )
        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[policy] for policy in policies], fontsize=18)
        ax.set_title(str(year), fontsize=18)
        ax.grid(True, axis='y', alpha=0.3)
        ax.tick_params(axis='y', labelsize=16)
        ax.text(0.03, 0.93, f'({chr(ord("a") + panel_index)})', transform=ax.transAxes,
                ha='left', va='top', fontsize=18, fontweight='bold')
        if panel_index == 0:
            ax.set_ylabel('Net Present Value (M$)', fontsize=18)
            from matplotlib.patches import Patch
            legend_patches = [
                Patch(facecolor=COLORS[policy][slr], label=f'{policy} SLR-{slr}')
                for policy in policies
                for slr in slrs
            ]
            ax.legend(handles=legend_patches, frameon=False, fontsize=13, loc='upper left')

    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'SI_Both_NPV.{ext}'), dpi=300)
    plt.close(fig)

def plot_si_physical_lowhigh_2070():
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cost_benefit = load_csv('Statistics_Both_CostBenefit_Annual_PerSim.csv')
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'High']
    panels = [
        ('(a)', 'Acute', 'Damaged', 'Acute Damaged Buildings (% change)', 'rel'),
        ('(b)', 'Flooding', 'Damaged', 'Flood-damaged Buildings (% change)', 'rel'),
        ('(c)', 'Acute', 'Damaged', 'Acute Damaged Buildings (% change / M$)', 'cost'),
        ('(d)', 'Flooding', 'Damaged', 'Flood-damaged Buildings (% change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, ylabel, dtype) in enumerate(panels):
        ax = axes[i//2, i%2]
        df = rel_benefit if dtype == 'rel' else cost_benefit
        bar_means = []
        bar_cis = []
        bar_colors = []
        for pol in ac3_pols:
            means = []
            cis = []
            colors = []
            for slr in slrs:
                dfp = df[(df['SLR']==slr) & (df['Hazard']==hazard) & (df['Metric']==metric) & (df['Year']==2070) & (df['ProactivePolicy']==pol)]
                if not dfp.empty:
                    means.append(dfp['Mean'].values[0])
                    cis.append(get_ci(dfp['Std'].values)[0])
                    colors.append(COLORS[pol][slr])
                else:
                    means.append(np.nan)
                    cis.append(0)
                    colors.append('#CCCCCC')
            bar_means.append(means)
            bar_cis.append(cis)
            bar_colors.append(colors)
        n_groups = len(ac3_pols)
        n_bars = len(slrs)
        group_width = 0.45
        bar_width = group_width / n_bars
        margin = 2.0
        group_spacing = group_width + 0.08
        group_centers = np.linspace(margin, margin + group_spacing * (n_groups - 1), n_groups)
        for j, slr in enumerate(slrs):
            pos = group_centers - group_width/2 + bar_width/2 + j*bar_width
            vals = [bar_means[k][j] for k in range(n_groups)]
            errs = [bar_cis[k][j] for k in range(n_groups)]
            cols = [bar_colors[k][j] for k in range(n_groups)]
            for p, v, e, c in zip(pos, vals, errs, cols):
                ax.bar([p], [v], yerr=[[e], [e]], capsize=6, color=[c], width=bar_width, ecolor=c, label=f'SLR-{slr}' if i==0 else None)
        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(group_centers[0] - group_width/2 - 0.2, group_centers[-1] + group_width/2 + 0.2)
        ax.set_ylabel(ylabel, fontsize=16)
        if i == 3:
            yticks = np.arange(0.0, -0.41, -0.1)
            ax.set_yticks(yticks)
            ax.set_yticklabels([f"{y:.1f}" for y in yticks])
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=16, fontweight='bold')
        if i==0:
            from matplotlib.patches import Patch
            legend_patches = []
            legend_order = [
                ('AC3-A', 'Low'), ('AC3-A', 'High'),
                ('AC3', 'Low'), ('AC3', 'High'),
                ('AC3-C', 'Low'), ('AC3-C', 'High')
            ]
            legend_labels = [
                'SLR-Low', 'SLR-High',
                'SLR-Low', 'SLR-High',
                'SLR-Low', 'SLR-High'
            ]
            for (pol, slr), label in zip(legend_order, legend_labels):
                legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=label))
            # Do not add legend to panel (a)
        if i==1 and 'legend_patches' in locals():
            ax.legend(handles=legend_patches, frameon=False, fontsize=16, loc='lower left')
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'SI_Both_Physical_LowHigh_2070.{ext}'), dpi=300)
    plt.close(fig)

def plot_si_physical_allslr_2030_2050():
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cost_benefit = load_csv('Statistics_Both_CostBenefit_Annual_PerSim.csv')
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    years = [2030, 2050]
    panels = [
        ('(a)', 'Flooding', 'Damaged', years[0], 'Flood-damaged Buildings (% change)', 'rel'),
        ('(b)', 'Flooding', 'Damaged', years[1], 'Flood-damaged Buildings (% change)', 'rel'),
        ('(c)', 'Flooding', 'Damaged', years[0], 'Flood-damaged Buildings (% change / M$)', 'cost'),
        ('(d)', 'Flooding', 'Damaged', years[1], 'Flood-damaged Buildings (% change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, year, ylabel, dtype) in enumerate(panels):
        ax = axes[i//2, i%2]
        df = rel_benefit if dtype == 'rel' else cost_benefit
        bar_means = []
        bar_cis = []
        bar_colors = []
        for pol in ac3_pols:
            means = []
            cis = []
            colors = []
            for slr in slrs:
                dfp = df[(df['SLR']==slr) & (df['Hazard']==hazard) & (df['Metric']==metric) & (df['Year']==year) & (df['ProactivePolicy']==pol)]
                if not dfp.empty:
                    means.append(dfp['Mean'].values[0])
                    cis.append(get_ci(dfp['Std'].values)[0])
                    colors.append(COLORS[pol][slr])
                else:
                    means.append(np.nan)
                    cis.append(0)
                    colors.append('#CCCCCC')
            bar_means.append(means)
            bar_cis.append(cis)
            bar_colors.append(colors)
        group_width = 0.45
        n_groups = len(ac3_pols)
        n_bars = len(slrs)
        bar_width = group_width / n_bars
        margin = 1.8
        group_spacing = group_width + 0.08
        group_centers = np.linspace(margin, margin + group_spacing * (n_groups - 1), n_groups)
        for j, slr in enumerate(slrs):
            pos = group_centers - group_width/2 + bar_width/2 + j*bar_width
            vals = [bar_means[k][j] for k in range(n_groups)]
            errs = [bar_cis[k][j] for k in range(n_groups)]
            cols = [bar_colors[k][j] for k in range(n_groups)]
            for p, v, e, c in zip(pos, vals, errs, cols):
                ax.bar([p], [v], yerr=[[e], [e]], capsize=6, color=[c], width=bar_width, ecolor=c, label=f'SLR-{slr}' if i==0 else None)
        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(group_centers[0] - group_width/2 - 0.2, group_centers[-1] + group_width/2 + 0.2)
        # Only left panels get y-label
        if i % 2 == 0:
            ax.set_ylabel(ylabel, fontsize=16)
        else:
            ax.set_ylabel("")
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=16, fontweight='bold')
        if i == 0:
            # Label 2030 above top left (closer to panel)
            ax.text(0.5, 1.02, '2030', transform=ax.transAxes, ha='center', va='bottom', fontsize=18, fontweight='bold')
            from matplotlib.patches import Patch
            legend_patches = []
            legend_order = [
                ('AC3-A', 'Low'), ('AC3-A', 'Med'), ('AC3-A', 'High'),
                ('AC3', 'Low'), ('AC3', 'Med'), ('AC3', 'High'),
                ('AC3-C', 'Low'), ('AC3-C', 'Med'), ('AC3-C', 'High')
            ]
            legend_labels = [
                'SLR-Low', 'SLR-Med', 'SLR-High',
                'SLR-Low', 'SLR-Med', 'SLR-High',
                'SLR-Low', 'SLR-Med', 'SLR-High'
            ]
            for (pol, slr), label in zip(legend_order, legend_labels):
                legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=f'SLR-{slr}'))
            # Do not add legend to panel (a)
        if i == 2:
            from matplotlib.patches import Patch
            legend_patches = []
            legend_order = [
                ('AC3-A', 'Low'), ('AC3-A', 'Med'), ('AC3-A', 'High'),
                ('AC3', 'Low'), ('AC3', 'Med'), ('AC3', 'High'),
                ('AC3-C', 'Low'), ('AC3-C', 'Med'), ('AC3-C', 'High')
            ]
            legend_labels = [
                'SLR-Low', 'SLR-Med', 'SLR-High',
                'SLR-Low', 'SLR-Med', 'SLR-High',
                'SLR-Low', 'SLR-Med', 'SLR-High'
            ]
            for (pol, slr), label in zip(legend_order, legend_labels):
                legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=label))
            ax.legend(handles=legend_patches, frameon=False, fontsize=14, loc='lower left')
        if i == 1:
            # Label 2050 above top right (closer to panel)
            ax.text(0.5, 1.02, '2050', transform=ax.transAxes, ha='center', va='bottom', fontsize=18, fontweight='bold')
            # Remove legend if present
            if hasattr(ax, 'legend_') and ax.legend_:
                ax.legend_.remove()
            # Remove legend if present
            ax.legend_.remove() if hasattr(ax, 'legend_') and ax.legend_ else None
            from matplotlib.patches import Patch
            legend_patches = []
            for pol in ac3_pols:
                for slr in slrs:
                    legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=f'{pol} SLR-{slr}'))
            ax.legend(handles=legend_patches, frameon=False, fontsize=16, loc='lower left')
    # Explicitly remove legend from upper right panel (panel (b), axes[0,1])
    if hasattr(axes[0,1], 'legend_') and axes[0,1].legend_:
        axes[0,1].legend_.remove()
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'SI_Both_Physical_AllSLR_2030_2050.{ext}'), dpi=300)
    plt.close(fig)

def plot_si_both_compound():
    """
    SI figure for compound metric (AcuteAndFlooding, Damaged, 2070) relative benefit.
    Reads from Statistics_Both_RelativeBenefit_Annual_PerSim.csv and saves Main_Both_Compound_2070.png/svg.
    """
    import matplotlib.patches as mpatches
    df = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    # Filter for compound metric
    df = df[(df['Hazard'] == 'AcuteAndFlooding') & (df['Metric'] == 'Damaged') & (df['Year'] == 2070)]
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    # Use consistent color scheme as other figures
    bar_colors = {
        'AC3-A': {'Low': COLORS['AC3-A']['Low'], 'Med': COLORS['AC3-A']['Med'], 'High': COLORS['AC3-A']['High']},
        'AC3': {'Low': COLORS['AC3']['Low'], 'Med': COLORS['AC3']['Med'], 'High': COLORS['AC3']['High']},
        'AC3-C': {'Low': COLORS['AC3-C']['Low'], 'Med': COLORS['AC3-C']['Med'], 'High': COLORS['AC3-C']['High']}
    }
    # Prepare data
    means = np.full((3, 3), np.nan)
    stds = np.full((3, 3), np.nan)
    for i, pol in enumerate(ac3_pols):
        for j, slr in enumerate(slrs):
            row = df[(df['ProactivePolicy'] == pol) & (df['SLR'] == slr)]
            if not row.empty:
                means[i, j] = row['Mean'].values[0]
                stds[i, j] = row['Std'].values[0]
    # Compute CI
    ci = 1.96 * stds / np.sqrt(N_ITER)
    # Bar plot layout
    fig, ax = plt.subplots(figsize=(7, 5))
    width = 0.2 * 0.8 * 0.8
    group_gap = 0.8
    x = np.arange(len(ac3_pols)) * group_gap
    for j, slr in enumerate(slrs):
        pos = x + (j - 1) * width
        vals = means[:, j]
        errs = ci[:, j]
        # Use the consistent color for each policy/SLR
        colors = [bar_colors[ac3_pols[k]][slr] for k in range(len(ac3_pols))]
        for p, v, e, c in zip(pos, vals, errs, colors):
            ax.bar([p], [v], yerr=[[e], [e]], capsize=4, color=[c], width=width, ecolor=c, label=f'SLR-{slr}')
    # X-axis
    ax.set_xticks(x)
    ax.set_xticklabels(ac3_pols, fontsize=14)
    ax.set_ylabel('Buildings Damaged by Both Hazards (% change)', fontsize=14)
    # Grid, legend, style
    ax.grid(True, axis='y', alpha=0.3)
    ax.tick_params(axis='y', labelsize=14)
    from matplotlib.patches import Patch
    # 9-entry legend: SLR-Low/Med/High for each policy, ordered: AC3-A (purple), AC3 (cyan), AC3-C (orange)
    legend_patches = []
    legend_order = [
        ('AC3-A', 'Low'), ('AC3-A', 'Med'), ('AC3-A', 'High'),
        ('AC3', 'Low'), ('AC3', 'Med'), ('AC3', 'High'),
        ('AC3-C', 'Low'), ('AC3-C', 'Med'), ('AC3-C', 'High')
    ]
    legend_labels = [
        'SLR-Low', 'SLR-Med', 'SLR-High',
        'SLR-Low', 'SLR-Med', 'SLR-High',
        'SLR-Low', 'SLR-Med', 'SLR-High'
    ]
    for (pol, slr), label in zip(legend_order, legend_labels):
        legend_patches.append(Patch(facecolor=bar_colors[pol][slr], label=label))
    ax.legend(handles=legend_patches, frameon=False, fontsize=13, loc='lower left')
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'Main_Both_Compound_2070.{ext}'), dpi=300, bbox_inches='tight')
    plt.close(fig)


def plot_si_both_compound_2050_2090():
    df = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    policies = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    years = [2050, 2090]
    df = df[
        (df['Hazard'] == 'AcuteAndFlooding')
        & (df['Metric'] == 'Damaged')
        & (df['Year'].isin(years))
        & (df['ProactivePolicy'].isin(policies))
        & (df['SLR'].isin(slrs))
    ]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    group_width = 0.6
    bar_width = group_width / len(slrs)
    group_centers = np.arange(len(policies)) * (group_width + 0.25)
    for panel_index, year in enumerate(years):
        ax = axes[panel_index]
        df_year = df[df['Year'] == year]
        for slr_index, slr in enumerate(slrs):
            positions = group_centers - group_width / 2 + bar_width / 2 + slr_index * bar_width
            for policy_index, policy in enumerate(policies):
                rows = df_year[(df_year['ProactivePolicy'] == policy) & (df_year['SLR'] == slr)]
                if len(rows) != 1:
                    raise ValueError(f'Expected one compound-benefit row for {policy}, {slr}, {year}; found {len(rows)}')
                row = rows.iloc[0]
                ci = get_ci(row['Std'])
                ax.bar(
                    [positions[policy_index]], [row['Mean']], yerr=[[ci], [ci]],
                    capsize=4, color=[COLORS[policy][slr]], width=bar_width,
                    ecolor=COLORS[policy][slr],
                )
        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[policy] for policy in policies], fontsize=14)
        ax.set_title(str(year), fontsize=16)
        ax.grid(True, axis='y', alpha=0.3)
        ax.tick_params(axis='y', labelsize=14)
        ax.text(0.03, 0.93, f'({chr(ord("a") + panel_index)})', transform=ax.transAxes,
                ha='left', va='top', fontsize=16, fontweight='bold')
        if panel_index == 0:
            ax.set_ylabel('Buildings Damaged by Both Hazards (% change)', fontsize=14)
            from matplotlib.patches import Patch
            legend_patches = [
                Patch(facecolor=COLORS[policy][slr], label=f'{policy} SLR-{slr}')
                for policy in policies
                for slr in slrs
            ]
            ax.legend(handles=legend_patches, frameon=False, fontsize=13, loc='lower left')

    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'SI_Both_Compound_2050_2090.{ext}'), dpi=300, bbox_inches='tight')
    plt.close(fig)

def plot_si_social_lowhigh_2070():
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cost_benefit = load_csv('Statistics_Both_CostBenefit_Annual_PerSim.csv')
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'High']
    panels = [
        ('(a)', 'Acute', 'Casualty', 'Acute Casualties (% change)', 'rel'),
        ('(b)', 'Flooding', 'PopulationImpacted', 'Flood-impacted Population (% change)', 'rel'),
        ('(c)', 'Acute', 'Casualty', 'Acute Casualties (% change / M$)', 'cost'),
        ('(d)', 'Flooding', 'PopulationImpacted', 'Flood-impacted Population (% change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, ylabel, dtype) in enumerate(panels):
        ax = axes[i//2, i%2]
        df = rel_benefit if dtype == 'rel' else cost_benefit
        bar_means, bar_cis, bar_colors = [], [], []
        for pol in ac3_pols:
            means, cis, colors = [], [], []
            for slr in slrs:
                dfp = df[(df['SLR']==slr) & (df['Hazard']==hazard) & (df['Metric']==metric) & (df['Year']==2070) & (df['ProactivePolicy']==pol)]
                if not dfp.empty:
                    means.append(dfp['Mean'].values[0])
                    cis.append(get_ci(dfp['Std'].values)[0])
                    colors.append(COLORS[pol][slr])
                else:
                    means.append(np.nan)
                    cis.append(0)
                    colors.append('#CCCCCC')
            bar_means.append(means)
            bar_cis.append(cis)
            bar_colors.append(colors)
        n_groups = len(ac3_pols)
        n_bars = len(slrs)
        group_width = 0.45
        bar_width = group_width / n_bars
        margin = 2.0
        group_spacing = group_width + 0.08
        group_centers = np.linspace(margin, margin + group_spacing * (n_groups - 1), n_groups)
        for j, slr in enumerate(slrs):
            pos = group_centers - group_width/2 + bar_width/2 + j*bar_width
            vals = [bar_means[k][j] for k in range(n_groups)]
            errs = [bar_cis[k][j] for k in range(n_groups)]
            cols = [bar_colors[k][j] for k in range(n_groups)]
            for p, v, e, c in zip(pos, vals, errs, cols):
                ax.bar([p], [v], yerr=[[e], [e]], capsize=6, color=[c], width=bar_width, ecolor=c, label=f'SLR-{slr}' if i==0 else None)
        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(group_centers[0] - group_width/2 - 0.2, group_centers[-1] + group_width/2 + 0.2)
        ax.set_ylabel(ylabel, fontsize=16)
        if i == 3:
            yticks = np.arange(0.0, -0.41, -0.1)
            ax.set_yticks(yticks)
            ax.set_yticklabels([f"{y:.1f}" for y in yticks])
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=16, fontweight='bold')
        if i==1:
            from matplotlib.patches import Patch
            legend_patches = []
            for pol in ac3_pols:
                for slr in slrs:
                    legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=f'SLR-{slr}'))
            ax.legend(handles=legend_patches, frameon=False, fontsize=16, loc='lower left')
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'SI_Both_Social_LowHigh_2070.{ext}'), dpi=300)
    plt.close(fig)

def plot_si_social_allslr_2030_2050():
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cost_benefit = load_csv('Statistics_Both_CostBenefit_Annual_PerSim.csv')
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    years = [2030, 2050]
    panels = [
        ('(a)', 'Flooding', 'PopulationImpacted', years[0], 'Flood-impacted Population (% change)', 'rel'),
        ('(b)', 'Flooding', 'PopulationImpacted', years[1], 'Flood-impacted Population (% change)', 'rel'),
        ('(c)', 'Flooding', 'PopulationImpacted', years[0], 'Flood-impacted Population (% change / M$)', 'cost'),
        ('(d)', 'Flooding', 'PopulationImpacted', years[1], 'Flood-impacted Population (% change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, year, ylabel, dtype) in enumerate(panels):
        ax = axes[i//2, i%2]
        df = rel_benefit if dtype == 'rel' else cost_benefit
        bar_means, bar_cis, bar_colors = [], [], []
        for pol in ac3_pols:
            means, cis, colors = [], [], []
            for slr in slrs:
                dfp = df[(df['SLR']==slr) & (df['Hazard']==hazard) & (df['Metric']==metric) & (df['Year']==year) & (df['ProactivePolicy']==pol)]
                if not dfp.empty:
                    means.append(dfp['Mean'].values[0])
                    cis.append(get_ci(dfp['Std'].values)[0])
                    colors.append(COLORS[pol][slr])
                else:
                    means.append(np.nan)
                    cis.append(0)
                    colors.append('#CCCCCC')
            bar_means.append(means)
            bar_cis.append(cis)
            bar_colors.append(colors)
        group_width = 0.45
        n_groups = len(ac3_pols)
        n_bars = len(slrs)
        bar_width = group_width / n_bars
        margin = 1.8
        group_spacing = group_width + 0.08
        group_centers = np.linspace(margin, margin + group_spacing * (n_groups - 1), n_groups)
        for j, slr in enumerate(slrs):
            pos = group_centers - group_width/2 + bar_width/2 + j*bar_width
            vals = [bar_means[k][j] for k in range(n_groups)]
            errs = [bar_cis[k][j] for k in range(n_groups)]
            cols = [bar_colors[k][j] for k in range(n_groups)]
            for p, v, e, c in zip(pos, vals, errs, cols):
                ax.bar([p], [v], yerr=[[e], [e]], capsize=6, color=[c], width=bar_width, ecolor=c, label=f'SLR-{slr}' if i==0 else None)
        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(group_centers[0] - group_width/2 - 0.2, group_centers[-1] + group_width/2 + 0.2)
        # Only left panels get y-label
        if i % 2 == 0:
            ax.set_ylabel(ylabel, fontsize=17)
        else:
            ax.set_ylabel("")
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=16, fontweight='bold')
        if i == 0:
            # Label 2030 above top left (closer to panel)
            ax.text(0.5, 1.02, '2030', transform=ax.transAxes, ha='center', va='bottom', fontsize=16, fontweight='bold')
            from matplotlib.patches import Patch
            legend_patches = []
            legend_order = [
                ('AC3-A', 'Low'), ('AC3-A', 'Med'), ('AC3-A', 'High'),
                ('AC3', 'Low'), ('AC3', 'Med'), ('AC3', 'High'),
                ('AC3-C', 'Low'), ('AC3-C', 'Med'), ('AC3-C', 'High')
            ]
            legend_labels = [
                'SLR-Low', 'SLR-Med', 'SLR-High',
                'SLR-Low', 'SLR-Med', 'SLR-High',
                'SLR-Low', 'SLR-Med', 'SLR-High'
            ]
            for (pol, slr), label in zip(legend_order, legend_labels):
                legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=label))
            # Do not add legend to panel (a)
        if i == 2 and 'legend_patches' in locals():
            ax.legend(handles=legend_patches, frameon=False, fontsize=14, loc='lower left')
        if i == 1:
            # Label 2050 above top right (closer to panel)
            ax.text(0.5, 1.02, '2050', transform=ax.transAxes, ha='center', va='bottom', fontsize=16, fontweight='bold')
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'SI_Both_Social_AllSLR_2030_2050.{ext}'), dpi=300)
    plt.close(fig)

def plot_si_economic_lowhigh_2070():
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cost_benefit = load_csv('Statistics_Both_CostBenefit_Annual_PerSim.csv')
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'High']
    panels = [
        ('(a)', 'Acute', 'EconomicLoss', 'Acute Economic Loss (% change)', 'rel'),
        ('(b)', 'Flooding', 'EconomicLoss', 'Flood Economic Loss (% change)', 'rel'),
        ('(c)', 'Acute', 'EconomicLoss', 'Acute Economic Loss (% change / M$)', 'cost'),
        ('(d)', 'Flooding', 'EconomicLoss', 'Flood Economic Loss (% change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, ylabel, dtype) in enumerate(panels):
        ax = axes[i//2, i%2]
        df = rel_benefit if dtype == 'rel' else cost_benefit
        bar_means, bar_cis, bar_colors = [], [], []
        for pol in ac3_pols:
            means, cis, colors = [], [], []
            for slr in slrs:
                dfp = df[(df['SLR']==slr) & (df['Hazard']==hazard) & (df['Metric']==metric) & (df['Year']==2070) & (df['ProactivePolicy']==pol)]
                if not dfp.empty:
                    means.append(dfp['Mean'].values[0])
                    cis.append(get_ci(dfp['Std'].values)[0])
                    colors.append(COLORS[pol][slr])
                else:
                    means.append(np.nan)
                    cis.append(0)
                    colors.append('#CCCCCC')
            bar_means.append(means)
            bar_cis.append(cis)
            bar_colors.append(colors)
        n_groups = len(ac3_pols)
        n_bars = len(slrs)
        group_width = 0.45
        bar_width = group_width / n_bars
        margin = 2.0
        group_spacing = group_width + 0.08
        group_centers = np.linspace(margin, margin + group_spacing * (n_groups - 1), n_groups)
        for j, slr in enumerate(slrs):
            pos = group_centers - group_width/2 + bar_width/2 + j*bar_width
            vals = [bar_means[k][j] for k in range(n_groups)]
            errs = [bar_cis[k][j] for k in range(n_groups)]
            cols = [bar_colors[k][j] for k in range(n_groups)]
            for p, v, e, c in zip(pos, vals, errs, cols):
                ax.bar([p], [v], yerr=[[e], [e]], capsize=6, color=[c], width=bar_width, ecolor=c, label=f'SLR-{slr}' if i==0 else None)
        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(group_centers[0] - group_width/2 - 0.2, group_centers[-1] + group_width/2 + 0.2)
        ax.set_ylabel(ylabel)
        if i == 3:
            yticks = np.arange(0.0, -0.41, -0.1)
            ax.set_yticks(yticks)
            ax.set_yticklabels([f"{y:.1f}" for y in yticks])
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=16, fontweight='bold')
        if i==0:
            if hasattr(ax, 'legend_') and ax.legend_:
                ax.legend_.remove()
        if i==1:
            from matplotlib.patches import Patch
            legend_patches = []
            for pol in ac3_pols:
                for slr in slrs:
                    legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=f'SLR-{slr}'))
            ax.legend(handles=legend_patches, frameon=False, fontsize=16, loc='lower left')
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'SI_Both_Economic_LowHigh_2070.{ext}'), dpi=300)
    plt.close(fig)

def plot_si_economic_allslr_2030_2050():
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cost_benefit = load_csv('Statistics_Both_CostBenefit_Annual_PerSim.csv')
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    years = [2030, 2050]
    panels = [
        ('(a)', 'Flooding', 'EconomicLoss', years[0], 'Flood Economic Loss (% change)', 'rel'),
        ('(b)', 'Flooding', 'EconomicLoss', years[1], 'Flood Economic Loss (% change)', 'rel'),
        ('(c)', 'Flooding', 'EconomicLoss', years[0], 'Flood Economic Loss (% change / M$)', 'cost'),
        ('(d)', 'Flooding', 'EconomicLoss', years[1], 'Flood Economic Loss (% change / M$)', 'cost'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    for i, (label, hazard, metric, year, ylabel, dtype) in enumerate(panels):
        ax = axes[i//2, i%2]
        df = rel_benefit if dtype == 'rel' else cost_benefit
        bar_means, bar_cis, bar_colors = [], [], []
        for pol in ac3_pols:
            means, cis, colors = [], [], []
            for slr in slrs:
                dfp = df[(df['SLR']==slr) & (df['Hazard']==hazard) & (df['Metric']==metric) & (df['Year']==year) & (df['ProactivePolicy']==pol)]
                if not dfp.empty:
                    means.append(dfp['Mean'].values[0])
                    cis.append(get_ci(dfp['Std'].values)[0])
                    colors.append(COLORS[pol][slr])
                else:
                    means.append(np.nan)
                    cis.append(0)
                    colors.append('#CCCCCC')
            bar_means.append(means)
            bar_cis.append(cis)
            bar_colors.append(colors)
        group_width = 0.45
        n_groups = len(ac3_pols)
        n_bars = len(slrs)
        bar_width = group_width / n_bars
        margin = 1.8
        group_spacing = group_width + 0.08
        group_centers = np.linspace(margin, margin + group_spacing * (n_groups - 1), n_groups)
        for j, slr in enumerate(slrs):
            pos = group_centers - group_width/2 + bar_width/2 + j*bar_width
            vals = [bar_means[k][j] for k in range(n_groups)]
            errs = [bar_cis[k][j] for k in range(n_groups)]
            cols = [bar_colors[k][j] for k in range(n_groups)]
            for p, v, e, c in zip(pos, vals, errs, cols):
                ax.bar([p], [v], yerr=[[e], [e]], capsize=6, color=[c], width=bar_width, ecolor=c, label=f'SLR-{slr}' if i==0 else None)
        ax.set_xticks(group_centers)
        ax.set_xticklabels([POLICY_LABELS[p] for p in ac3_pols])
        ax.set_xlim(group_centers[0] - group_width/2 - 0.2, group_centers[-1] + group_width/2 + 0.2)
        # Only left panels get y-label
        if i % 2 == 0:
            ax.set_ylabel(ylabel)
        else:
            ax.set_ylabel("")
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.93, label, transform=ax.transAxes, ha='left', va='top', fontsize=16, fontweight='bold')
        if i == 0:
            # Label 2030 above top left (closer to panel)
            ax.text(0.5, 1.02, '2030', transform=ax.transAxes, ha='center', va='bottom', fontsize=16, fontweight='bold')
            from matplotlib.patches import Patch
            legend_patches = []
            legend_order = [
                ('AC3-A', 'Low'), ('AC3-A', 'Med'), ('AC3-A', 'High'),
                ('AC3', 'Low'), ('AC3', 'Med'), ('AC3', 'High'),
                ('AC3-C', 'Low'), ('AC3-C', 'Med'), ('AC3-C', 'High')
            ]
            legend_labels = [
                'SLR-Low', 'SLR-Med', 'SLR-High',
                'SLR-Low', 'SLR-Med', 'SLR-High',
                'SLR-Low', 'SLR-Med', 'SLR-High'
            ]
            for (pol, slr), label in zip(legend_order, legend_labels):
                legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=label))
            # Do not add legend to panel (a)
        if i == 2 and 'legend_patches' in locals():
            ax.legend(handles=legend_patches, frameon=False, fontsize=14, loc='lower left')
        if i == 1:
            # Label 2050 above top right (closer to panel)
            ax.text(0.5, 1.02, '2050', transform=ax.transAxes, ha='center', va='bottom', fontsize=16, fontweight='bold')
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'SI_Both_Economic_AllSLR_2030_2050.{ext}'), dpi=300)
    plt.close(fig)
    
def plot_si_both_erosion(years=(2030, 2050, 2070), output_name='SI_Both_Erosion_2070'):
    """
    Generate SI_Both_Erosion_2070.png/svg: 2x3 layout, top row relative benefit, bottom row cost-benefit, for Erosion metrics.
    """
    import matplotlib.patches as mpatches
    rel_benefit = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    absolute_benefit = load_csv('Statistics_Both_AbsoluteBenefit_Annual_PerSim.csv')
    cumulative_cost = pd.read_csv(
        f'{REPO_ROOT}/Results/EconomicAnalysis/Results_Combined_Economics_CumulativeCost_PerSim.csv'
    )
    ac3_pols = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    benefit_simulations = [column for column in absolute_benefit.columns if column.startswith('Sim_')]
    cost_simulations = [column for column in cumulative_cost.columns if column.startswith('Sim_')]
    benefit_by_number = {column.split()[0]: column for column in benefit_simulations}
    cost_by_number = {column.split()[0]: column for column in cost_simulations}
    simulation_numbers = sorted(set(benefit_by_number) & set(cost_by_number))
    cost_display_multiplier = 5 if output_name == 'SI_Both_Erosion' else 1
    # Try both 'Erosion' and 'Eroded' for Hazard/Metric
    hazard_label = None
    for h in ['Erosion', 'Eroded']:
        if h in rel_benefit['Hazard'].unique():
            hazard_label = h
            break
    if hazard_label is None:
        raise ValueError("Neither 'Erosion' nor 'Eroded' found in Hazard column.")
    metric_label = None
    for m in ['Eroded', 'Erosion']:
        if m in rel_benefit['Metric'].unique():
            metric_label = m
            break
    if metric_label is None:
        raise ValueError("Neither 'Eroded' nor 'Erosion' found in Metric column.")
    # Panel setup
    fig, axes = plt.subplots(2, 3, figsize=(18, 10), sharex=False)
    panel_labels = ['(a)', '(b)', '(c)', '(d)', '(e)', '(f)']
    # Bar layout (refer to Main_Both_CumulativeCost)
    # Use grouped bar logic consistent with other SI figures
    group_width = 0.45
    n_groups = 3
    n_bars = 3
    bar_width = group_width / n_bars
    margin = 1.8
    group_spacing = group_width + 0.08
    group_labels = ['AC3-A', 'AC3', 'AC3-C']
    hatches = [None, None, None]
    slr_colors = [COLORS['AC3-A']['Low'], COLORS['AC3-A']['Med'], COLORS['AC3-A']['High']]
    # Top row: relative benefit
    legend_patches = None
    for col, year in enumerate(years):
        ax = axes[0, col]
        # Data: filter for Hazard, Metric, Year, Policy, SLR
        bar_means = []
        bar_cis = []
        bar_cols = []
        for pi, pol in enumerate(ac3_pols):
            means, cis, cols = [], [], []
            for si, slr in enumerate(slrs):
                dfp = rel_benefit[(rel_benefit['Hazard']==hazard_label) & (rel_benefit['Metric']==metric_label) & (rel_benefit['Year']==year) & (rel_benefit['ProactivePolicy']==pol) & (rel_benefit['SLR']==slr)]
                if not dfp.empty:
                    means.append(dfp['Mean'].values[0])
                    cis.append(1.96 * dfp['Std'].values[0] / np.sqrt(N_ITER))
                    cols.append(COLORS[pol][slr])
                else:
                    means.append(np.nan)
                    cis.append(0)
                    cols.append('#CCCCCC')
            bar_means.append(means)
            bar_cis.append(cis)
            bar_cols.append(cols)
        # Grouped bar positions (no space between bars in group, consistent group spacing)
        group_centers = np.linspace(margin, margin + group_spacing * (n_groups - 1), n_groups)
        for j, slr in enumerate(slrs):
            pos = group_centers - group_width/2 + bar_width/2 + j*bar_width
            vals = [bar_means[k][j] for k in range(n_groups)]
            errs = [bar_cis[k][j] for k in range(n_groups)]
            cols = [bar_cols[k][j] for k in range(n_groups)]
            for p, v, e, c in zip(pos, vals, errs, cols):
                ax.bar([p], [v], yerr=[[e], [e]], capsize=4, color=[c], width=bar_width, ecolor=c, label=None, hatch=None, linewidth=0, edgecolor=None)
        ax.set_xticks(group_centers)
        ax.set_xticklabels(group_labels, fontsize=20)
        # Set x-limits to match other SI figures
        ax.set_xlim(group_centers[0] - group_width/2 - 0.2, group_centers[-1] + group_width/2 + 0.2)
        # Remove x-ticks for (a)-(c)
        if col in [0, 1, 2]:
            ax.set_xticks([])
        # Only leftmost panel gets y-label
        if col == 0:
            ax.set_ylabel('Eroded Buildings (% change)', fontsize=20)
        else:
            ax.set_ylabel("")
        ax.set_title(str(year), fontsize=20)
        ax.tick_params(axis='y', labelsize=20)
        ax.grid(True, axis='y', alpha=0.3)
        # Panel label
        ax.text(0.03, 0.93, panel_labels[col], transform=ax.transAxes, ha='left', va='top', fontsize=20, fontweight='bold')
        # Prepare legend_patches (only once, for use in panel (e))
        if col == 0:
            from matplotlib.patches import Patch
            legend_patches = []
            for pol in ac3_pols:
                for slr in slrs:
                    legend_patches.append(Patch(facecolor=COLORS[pol][slr], label=f'SLR-{slr}'))
    # Bottom row: cost-benefit (use Mean and Std columns, as for relative benefit)
    for col, year in enumerate(years):
        ax = axes[1, col]
        bar_means = []
        bar_cis = []
        bar_cols = []
        for pi, pol in enumerate(ac3_pols):
            means, cis, cols = [], [], []
            for si, slr in enumerate(slrs):
                benefit_rows = absolute_benefit[
                    (absolute_benefit['Hazard'] == hazard_label)
                    & (absolute_benefit['Metric'] == metric_label)
                    & (absolute_benefit['Year'] == year)
                    & (absolute_benefit['ProactivePolicy'] == pol)
                    & (absolute_benefit['SLR'] == slr)
                ]
                cost_rows = cumulative_cost[
                    (cumulative_cost['Hazard'] == 'Both')
                    & (cumulative_cost['Metric'] == 'Cost_Cumulatively_Increased')
                    & (cumulative_cost['Year'] == year)
                    & (cumulative_cost['ProactivePolicy'] == pol)
                    & (cumulative_cost['SLR'] == slr)
                ]
                if len(benefit_rows) != 1 or len(cost_rows) != 1:
                    raise ValueError(
                        f'Expected one benefit and cost row for {pol}, {slr}, {year}; '
                        f'found {len(benefit_rows)} and {len(cost_rows)}'
                    )
                benefits = pd.to_numeric(
                    benefit_rows.iloc[0][[benefit_by_number[number] for number in simulation_numbers]],
                    errors='coerce',
                ).to_numpy(dtype=float)
                costs = pd.to_numeric(
                    cost_rows.iloc[0][[cost_by_number[number] for number in simulation_numbers]],
                    errors='coerce',
                ).to_numpy(dtype=float)
                ratios = benefits / costs * cost_display_multiplier
                ratios = ratios[np.isfinite(ratios)]
                if ratios.size == 0:
                    raise ValueError(f'No valid benefit-to-cost ratios for {pol}, {slr}, {year}')
                means.append(ratios.mean())
                cis.append(CI_FACTOR * ratios.std(ddof=1) / np.sqrt(ratios.size))
                cols.append(COLORS[pol][slr])
            bar_means.append(means)
            bar_cis.append(cis)
            bar_cols.append(cols)
        group_centers = np.linspace(margin, margin + group_spacing * (n_groups - 1), n_groups)
        for j, slr in enumerate(slrs):
            pos = group_centers - group_width/2 + bar_width/2 + j*bar_width
            vals = [bar_means[k][j] for k in range(n_groups)]
            errs = [bar_cis[k][j] for k in range(n_groups)]
            cols = [bar_cols[k][j] for k in range(n_groups)]
            for p, v, e, c in zip(pos, vals, errs, cols):
                ax.bar([p], [v], yerr=[[e], [e]], capsize=4, color=[c], width=bar_width, ecolor=c, label=None, hatch=None, linewidth=0, edgecolor=None)
        ax.set_xticks(group_centers)
        ax.set_xticklabels(group_labels, fontsize=20)
        # Set x-limits to match other SI figures
        ax.set_xlim(group_centers[0] - group_width/2 - 0.2, group_centers[-1] + group_width/2 + 0.2)
        # Only leftmost panel gets y-label
        if col == 0:
            cost_unit = '$5M' if cost_display_multiplier == 5 else 'M$'
            ax.set_ylabel(f'Eroded Buildings (# change / {cost_unit})', fontsize=20)
        else:
            ax.set_ylabel("")
        ax.tick_params(axis='y', labelsize=20)
        ax.grid(True, axis='y', alpha=0.3)
        ax.text(0.03, 0.93, panel_labels[3+col], transform=ax.transAxes, ha='left', va='top', fontsize=20, fontweight='bold')
        # Legend (now only in (e), i.e., col==1, axes[1,1])
        if col == 1 and legend_patches is not None:
            axes[1,1].legend(handles=legend_patches, frameon=False, fontsize=15, loc='lower left')
    bottom_ymin = min(ax.get_ylim()[0] for ax in axes[1])
    bottom_ymax = max(ax.get_ylim()[1] for ax in axes[1])
    for ax in axes[1]:
        ax.set_ylim(bottom_ymin, bottom_ymax)
    # No legend removal needed; legend is now only in panel (e)
    plt.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(os.path.join(RESULTS_DIR, f'{output_name}.{ext}'), dpi=300 if ext=='png' else None, bbox_inches='tight')
    plt.close(fig)
    

def save_results_report_both_pv():
    years = [2050, 2070, 2090]
    policies = ['AC3-A', 'AC3', 'AC3-C']
    slrs = ['Low', 'Med', 'High']
    economics_dir = f'{REPO_ROOT}/Results/EconomicAnalysis'
    metric = load_csv('Statistics_Both_Metric_Annual_PerSim.csv')
    absolute = load_csv('Statistics_Both_AbsoluteBenefit_Annual_PerSim.csv')
    relative = load_csv('Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
    cumulative_cost = pd.read_csv(os.path.join(economics_dir, 'Results_Combined_Economics_CumulativeCost_PerSim.csv'))
    economic_baseline = pd.read_csv(os.path.join(economics_dir, 'Results_Combined_Economics_Baseline_PerSim.csv'))
    economic_proactive = pd.read_csv(os.path.join(economics_dir, 'Results_Combined_Economics_Proactive_PerSim.csv'))
    npv = pd.read_csv(os.path.join(economics_dir, 'Results_Combined_Economics_NPV_PerSim.csv'))
    report_rows = []

    def simulation_columns(data):
        return {column.split()[0]: column for column in data.columns if column.startswith('Sim_')}

    def add_summary(policy, slr, hazard, metric_name, year, mean, std):
        ci = CI_FACTOR * std / np.sqrt(N_ITER)
        cov = std / mean if mean != 0 else np.nan
        report_rows.append({
            'Policy': policy,
            'SLR': slr,
            'Hazard': hazard,
            'Metric': metric_name,
            'Year': year,
            'Mean': mean,
            'Std': std,
            'CoV': cov,
            '95CI_LB': mean - ci,
            '95CI_UB': mean + ci,
        })

    def add_values(policy, slr, hazard, metric_name, year, values):
        values = np.asarray(values, dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            raise ValueError(f'No valid report values for {policy}, {slr}, {hazard}, {metric_name}, {year}')
        mean = values.mean()
        std = values.std(ddof=1)
        ci = CI_FACTOR * std / np.sqrt(values.size)
        report_rows.append({
            'Policy': policy,
            'SLR': slr,
            'Hazard': hazard,
            'Metric': metric_name,
            'Year': year,
            'Mean': mean,
            'Std': std,
            'CoV': std / mean if mean != 0 else np.nan,
            '95CI_LB': mean - ci,
            '95CI_UB': mean + ci,
        })

    def one_row(data, filters, description):
        rows = data.copy()
        for column, value in filters.items():
            rows = rows[rows[column] == value]
        if len(rows) != 1:
            raise ValueError(f'Expected one {description} row; found {len(rows)}')
        return rows.iloc[0]

    absolute_simulations = simulation_columns(absolute)
    cost_simulations = simulation_columns(cumulative_cost)
    baseline_simulations = simulation_columns(economic_baseline)
    proactive_simulations = simulation_columns(economic_proactive)
    absolute_cost_sims = sorted(set(absolute_simulations) & set(cost_simulations))
    economic_sims = sorted(set(baseline_simulations) & set(proactive_simulations) & set(cost_simulations))

    # SI_Both_CumulativeCost_PV
    for year in years:
        for policy in policies:
            for slr in slrs:
                row = one_row(cumulative_cost, {
                    'ProactivePolicy': policy, 'SLR': slr, 'Year': year,
                    'Hazard': 'Both', 'Metric': 'Cost_Cumulatively_Increased',
                }, 'cumulative-cost')
                add_summary(policy, slr, 'Both', 'Cost Cumulatively Increased', year, row['Mean (M$)'], row['Std (M$)'])

    # Table S1: AC1 acute and flooding damaged-building baseline metrics.
    for year in years:
        for slr in slrs:
            for hazard in ['Acute', 'Flooding']:
                row = one_row(metric, {
                    'Policy': 'AC1', 'SLR': slr, 'Hazard': hazard,
                    'Metric': 'Damaged', 'Year': year,
                }, 'AC1 baseline metric')
                add_summary('AC1', slr, hazard, 'Damaged', year, row['Mean'], row['Std'])

    def add_physical_or_social_block(metrics):
        for year in years:
            for policy in policies:
                for slr in slrs:
                    for hazard, source_metric, report_prefix in metrics:
                        absolute_row = one_row(absolute, {
                            'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard,
                            'Metric': source_metric, 'Year': year,
                        }, 'absolute-benefit')
                        relative_row = one_row(relative, {
                            'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard,
                            'Metric': source_metric, 'Year': year,
                        }, 'relative-benefit')
                        cost_row = one_row(cumulative_cost, {
                            'ProactivePolicy': policy, 'SLR': slr, 'Hazard': 'Both',
                            'Metric': 'Cost_Cumulatively_Increased', 'Year': year,
                        }, 'cumulative-cost')
                        absolute_values = pd.to_numeric(
                            absolute_row[[absolute_simulations[number] for number in absolute_cost_sims]], errors='coerce'
                        ).to_numpy(dtype=float)
                        cost_values = pd.to_numeric(
                            cost_row[[cost_simulations[number] for number in absolute_cost_sims]], errors='coerce'
                        ).to_numpy(dtype=float)
                        add_summary(policy, slr, hazard, f'{report_prefix}_Reduction', year, absolute_row['Mean'], absolute_row['Std'])
                        add_summary(policy, slr, hazard, f'{report_prefix}_Reduction_PercentChange', year, relative_row['Mean'], relative_row['Std'])
                        add_values(policy, slr, hazard, f'{report_prefix}_CostBenefit (# change / M$)', year, absolute_values / cost_values)

    add_physical_or_social_block([
        ('Acute', 'Damaged', 'Damaged'),
        ('Flooding', 'Damaged', 'Damaged'),
    ])
    add_physical_or_social_block([
        ('Acute', 'Casualty', 'Casualty'),
        ('Flooding', 'PopulationImpacted', 'PopulationImpacted'),
    ])

    # Economic figures: percentage change and BCR use economics-only per-simulation inputs.
    for year in years:
        for policy in policies:
            for slr in slrs:
                cost_row = one_row(cumulative_cost, {
                    'ProactivePolicy': policy, 'SLR': slr, 'Hazard': 'Both',
                    'Metric': 'Cost_Cumulatively_Increased', 'Year': year,
                }, 'cumulative-cost')
                cost_values = pd.to_numeric(
                    cost_row[[cost_simulations[number] for number in economic_sims]], errors='coerce'
                ).to_numpy(dtype=float)
                for hazard in ['Acute', 'Chronic']:
                    proactive_row = one_row(economic_proactive, {
                        'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard,
                        'Metric': 'Economic_Loss_Reduction', 'Year': year,
                    }, 'economic proactive')
                    baseline_row = one_row(economic_baseline, {
                        'Policy': 'Baseline', 'SLR': slr, 'Hazard': hazard,
                        'Metric': 'Economic_Loss', 'Year': year,
                    }, 'economic baseline')
                    proactive_values = pd.to_numeric(
                        proactive_row[[proactive_simulations[number] for number in economic_sims]], errors='coerce'
                    ).to_numpy(dtype=float)
                    baseline_values = pd.to_numeric(
                        baseline_row[[baseline_simulations[number] for number in economic_sims]], errors='coerce'
                    ).to_numpy(dtype=float)
                    add_values(policy, slr, hazard, 'Economic_Loss_Reduction', year, -proactive_values)
                    add_values(policy, slr, hazard, 'Economic_Loss_Reduction_PercentChange', year, -proactive_values / baseline_values * 100)
                    add_values(policy, slr, hazard, 'Benefit-cost Ratio (BCR)', year, -proactive_values / cost_values)

    # Compound and erosion baseline, reduction, percentage-change, and benefit-cost rows.
    for hazard, source_metric, report_prefix, cost_multiplier, cost_unit in [
        ('AcuteAndFlooding', 'Damaged', 'AcuteAndFloodingDamaged', 1, 'M$'),
        ('Erosion', 'Eroded', 'Eroded', 5, '$5M'),
    ]:
        for year in years:
            for slr in slrs:
                baseline_row = one_row(metric, {
                    'Policy': 'AC1', 'SLR': slr, 'Hazard': hazard,
                    'Metric': source_metric, 'Year': year,
                }, 'AC1 baseline metric')
                add_summary('AC1', slr, hazard, source_metric, year, baseline_row['Mean'], baseline_row['Std'])
            for policy in policies:
                for slr in slrs:
                    absolute_row = one_row(absolute, {
                        'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard,
                        'Metric': source_metric, 'Year': year,
                    }, 'absolute-benefit')
                    relative_row = one_row(relative, {
                        'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard,
                        'Metric': source_metric, 'Year': year,
                    }, 'relative-benefit')
                    cost_row = one_row(cumulative_cost, {
                        'ProactivePolicy': policy, 'SLR': slr, 'Hazard': 'Both',
                        'Metric': 'Cost_Cumulatively_Increased', 'Year': year,
                    }, 'cumulative-cost')
                    absolute_values = pd.to_numeric(
                        absolute_row[[absolute_simulations[number] for number in absolute_cost_sims]], errors='coerce'
                    ).to_numpy(dtype=float)
                    cost_values = pd.to_numeric(
                        cost_row[[cost_simulations[number] for number in absolute_cost_sims]], errors='coerce'
                    ).to_numpy(dtype=float)
                    add_summary(policy, slr, hazard, f'{report_prefix}_Reduction', year, absolute_row['Mean'], absolute_row['Std'])
                    add_summary(policy, slr, hazard, f'{report_prefix}_Reduction_PercentChange', year, relative_row['Mean'], relative_row['Std'])
                    add_values(
                        policy, slr, hazard, f'{report_prefix}_CostBenefit (# change / {cost_unit})', year,
                        absolute_values / cost_values * cost_multiplier,
                    )

    # SI_Both_NPV
    npv_simulations = simulation_columns(npv)
    for year in years:
        for policy in policies:
            for slr in slrs:
                row = one_row(npv, {
                    'ProactivePolicy': policy, 'SLR': slr, 'Hazard': 'Both',
                    'Metric': 'Net_Present_Value', 'Year': year,
                }, 'NPV')
                add_summary(policy, slr, 'Both', 'Net_Present_Value', year, row['Mean (M$)'], row['Std (M$)'])

    pd.DataFrame(report_rows).to_csv(
        os.path.join(RESULTS_DIR, 'Results_report_Both_PV_1.csv'), index=False
    )


def save_results_report_both_pv_2():
    report_path = os.path.join(RESULTS_DIR, 'Results_report_Both_PV_1.csv')
    if not os.path.exists(report_path):
        save_results_report_both_pv()
    report = pd.read_csv(report_path)
    years = [2050, 2070, 2090]
    slrs = ['Low', 'Med', 'High']
    policies = ['AC3-A', 'AC3', 'AC3-C']
    report_metrics = [
        ('Both', 'Cost Cumulatively Increased', 'Cost_Cumulatively_Increased'),
        ('Acute', 'Damaged_Reduction_PercentChange', 'Damaged_Reduction_PercentChange'),
        ('Flooding', 'Damaged_Reduction_PercentChange', 'Damaged_Reduction_PercentChange'),
        ('Acute', 'Damaged_CostBenefit (# change / M$)', 'Damaged_CostBenefit'),
        ('Flooding', 'Damaged_CostBenefit (# change / M$)', 'Damaged_CostBenefit'),
        ('Acute', 'Casualty_Reduction_PercentChange', 'Casualty_Reduction_PercentChange'),
        ('Flooding', 'PopulationImpacted_Reduction_PercentChange', 'PopulationImpacted_Reduction_PercentChange'),
        ('Acute', 'Casualty_CostBenefit (# change / M$)', 'Casualty_CostBenefit'),
        ('Flooding', 'PopulationImpacted_CostBenefit (# change / M$)', 'PopulationImpacted_CostBenefit'),
        ('Acute', 'Economic_Loss_Reduction_PercentChange', 'Economic_Loss_Reduction_PercentChange'),
        ('Chronic', 'Economic_Loss_Reduction_PercentChange', 'Economic_Loss_Reduction_PercentChange'),
        ('Acute', 'Benefit-cost Ratio (BCR)', 'Benefit-cost_Ratio (BCR)'),
        ('Chronic', 'Benefit-cost Ratio (BCR)', 'Benefit-cost_Ratio (BCR)'),
        ('AcuteAndFlooding', 'AcuteAndFloodingDamaged_Reduction_PercentChange', 'Damaged_Reduction_PercentChange'),
        ('Erosion', 'Eroded_Reduction_PercentChange', 'Eroded_Reduction_PercentChange'),
        ('Erosion', 'Eroded_CostBenefit (# change / $5M)', 'Eroded_CostBenefit (# change / $5M)'),
        ('Both', 'Net_Present_Value', 'Net_Present_Value'),
    ]
    ratio_rows = []
    for hazard, source_metric, output_metric in report_metrics:
        for slr in slrs:
            for year in years:
                rows = report[
                    (report['Year'] == year)
                    & (report['SLR'] == slr)
                    & (report['Hazard'] == hazard)
                    & (report['Metric'] == source_metric)
                    & (report['Policy'].isin(policies))
                ]
                if len(rows) != len(policies):
                    raise ValueError(
                        f'Expected three policy means for {slr}, {hazard}, {source_metric}, {year}; '
                        f'found {len(rows)}'
                    )
                means = rows.set_index('Policy')['Mean']
                ratio_rows.append({
                    'SLR': slr,
                    'Hazard': hazard,
                    'Metric': output_metric,
                    'Year': year,
                    'AC3-A_AC3_ratio': means['AC3-A'] / means['AC3'],
                    'AC3-A_AC3-C_ratio': means['AC3-A'] / means['AC3-C'],
                    'AC3_AC3-A_ratio': means['AC3'] / means['AC3-A'],
                    'AC3_AC3-C_ratio': means['AC3'] / means['AC3-C'],
                    'AC3-C_AC3-A_ratio': means['AC3-C'] / means['AC3-A'],
                    'AC3-C_AC3_ratio': means['AC3-C'] / means['AC3'],
                })
    pd.DataFrame(ratio_rows).to_csv(
        os.path.join(RESULTS_DIR, 'Results_report_Both_PV_2.csv'), index=False
    )

if __name__ == '__main__':
    plot_si_both_erosion((2050, 2070, 2090), 'SI_Both_Erosion')
    plot_main_physical_2070_pv()
    plot_main_social_2070_pv()
    plot_main_economic_2070_pv()
    plot_main_physical_2070_pv(2050, 'SI_Both_Physical_2050_PV')
    plot_main_social_2070_pv(2050, 'SI_Both_Social_2050_PV')
    plot_main_economic_2070_pv(2050, 'SI_Both_Economic_2050_PV')
    plot_main_physical_2070_pv(2090, 'SI_Both_Physical_2090_PV')
    plot_main_social_2070_pv(2090, 'SI_Both_Social_2090_PV')
    plot_main_economic_2070_pv(2090, 'SI_Both_Economic_2090_PV')
    plot_main_cumulative_cost_acute_year()
    plot_si_both_npv()

    plot_si_both_compound()
    plot_si_both_compound_2050_2090()
    save_results_report_both_pv()
    save_results_report_both_pv_2()
