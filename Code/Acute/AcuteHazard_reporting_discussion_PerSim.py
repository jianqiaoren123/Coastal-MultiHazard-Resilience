"""
Acute Hazard Analysis Results Report Generator

What this script does:
- Reads the policy-by-hazard summary CSV generated from the Monte Carlo simulations.
- Uses the per-iteration columns (e.g., Iter_0, Iter_1, ..., Iter_999) in the
  statistics file to calculate, for each policy and hazard, the policy-vs-baseline
  values at every iteration.
- Computes percentage change, absolute change, and baseline/policy values for each
  iteration, then summarizes these with Mean, Std, and CoV across all iterations.
- Saves the final result as a single CSV report for downstream discussion and figure
  generation.

Inputs:
- TotalNumber_Statistics.csv
- Statistics_Acute_PerSim.csv (contains Iter_* columns)

Output:
- Results_report_Acute_PerSim.csv

The output file contains per-iteration columns such as:
    Percentage_Change_Iter0, Baseline_Value_Iter0, Policy_Value_Iter0, Absolute_Change_Iter0,
    ...
    Percentage_Change_Iter999, Baseline_Value_Iter999, Policy_Value_Iter999, Absolute_Change_Iter999
followed by the summary columns:
    Percentage_Change_Mean, Percentage_Change_Std, Percentage_Change_CoV,
    Baseline_Value_Mean, Baseline_Value_Std, Baseline_Value_CoV,
    Policy_Value_Mean, Policy_Value_Std, Policy_Value_CoV,
    Absolute_Change_Mean, Absolute_Change_Std, Absolute_Change_CoV

This script is intended for reporting and interpretation of climate adaptation policy
performance relative to the Baseline scenario.
"""

# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()

import pandas as pd
import numpy as np
from pathlib import Path

# File paths
baseline_candidates = [
    Path(rf"{REPO_ROOT}/Results/Acute/TotalNumber_Statistics.csv"),
]
stats_candidates = [
    Path(rf"{REPO_ROOT}/Results/Acute/Statistics_Acute_PerSim.csv"),
]
output_csv = Path(rf"{REPO_ROOT}/Results/Acute/Results_report_Acute_PerSim.csv")

baseline_file = next((p for p in baseline_candidates if p.exists()), baseline_candidates[0])
stats_file = next((p for p in stats_candidates if p.exists()), stats_candidates[0])

# Read CSV files
df_baseline = pd.read_csv(baseline_file)
df_stats = pd.read_csv(stats_file)

# Policies and hazards
policies = ['Protect', 'Realign']
hazards = ['EQ', 'TSU', 'Cumulative']

# Metric groups to report
metric_groups = {
    'DS_0': 'Damage States',
    'DS_1': 'Damage States',
    'DS_2': 'Damage States',
    'DS_3': 'Damage States',
    'DS_4': 'Damage States',
    'DS_>0': 'Damage States',
    'Population_Impacted': 'Population Impacted',
    'Fatality': 'Life Safety',
    'Injury': 'Life Safety',
    'Casualty': 'Life Safety',
    'Economic_Loss': 'Economic Loss',
}

# Extract iteration columns
def get_iter_columns(df):
    cols = [c for c in df.columns if c.startswith('Iter_')]
    return sorted(cols, key=lambda c: int(c.replace('Iter_', '')))

iter_cols = get_iter_columns(df_stats)
if len(iter_cols) == 0:
    raise ValueError(f"No iteration columns found in {stats_file}. Expected headers like 'Iter_0', 'Iter_1', ...")

# Summary stats helper
def summarize(values):
    arr = np.asarray(values, dtype=float)
    n = len(arr)
    mean = float(np.mean(arr)) if n else np.nan
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    cov = 0.0 if (mean == 0 or n == 0) else float(std / mean / np.sqrt(n))
    return mean, std, cov

# Policy-vs-baseline per-iteration calculation
def get_row_values(df, policy, hazard, metric):
    mask = (df['Policy'] == policy) & (df['Hazard'] == hazard) & (df['Metric'] == metric)
    row = df[mask]
    if row.empty:
        return None
    return row.iloc[0][iter_cols].astype(float).to_numpy()

# Build output records
def calc_metric_result(policy, hazard, metric, category):
    base_vals = get_row_values(df_stats, 'Baseline', hazard, metric)
    pol_vals = get_row_values(df_stats, policy, hazard, metric)

    if base_vals is None or pol_vals is None:
        return None

    pct_change = np.where(np.abs(base_vals) > 0, ((pol_vals - base_vals) / base_vals) * 100.0, 0.0)
    abs_change = pol_vals - base_vals

    row = {
        'Category': category,
        'Policy': policy,
        'Hazard': hazard,
        'Metric': metric,
    }

    # Save per-iteration values as requested
    for i in range(len(iter_cols)):
        row[f'Percentage_Change_Iter{i}'] = float(pct_change[i])
        row[f'Baseline_Value_Iter{i}'] = float(base_vals[i])
        row[f'Policy_Value_Iter{i}'] = float(pol_vals[i])
        row[f'Absolute_Change_Iter{i}'] = float(abs_change[i])

    # Summary statistics based on all iteration values, not the summary CSV Mean/Std/CoV
    pct_mean, pct_std, pct_cov = summarize(pct_change)
    base_mean, base_std, base_cov = summarize(base_vals)
    pol_mean, pol_std, pol_cov = summarize(pol_vals)
    abs_mean, abs_std, abs_cov = summarize(abs_change)

    row['Percentage_Change_Mean'] = pct_mean
    row['Percentage_Change_Std'] = pct_std
    row['Percentage_Change_CoV'] = pct_cov

    row['Baseline_Value_Mean'] = base_mean
    row['Baseline_Value_Std'] = base_std
    row['Baseline_Value_CoV'] = base_cov

    row['Policy_Value_Mean'] = pol_mean
    row['Policy_Value_Std'] = pol_std
    row['Policy_Value_CoV'] = pol_cov

    row['Absolute_Change_Mean'] = abs_mean
    row['Absolute_Change_Std'] = abs_std
    row['Absolute_Change_CoV'] = abs_cov

    return row

rows = []
for policy in policies:
    for hazard in hazards:
        for metric, category in metric_groups.items():
            row = calc_metric_result(policy, hazard, metric, category)
            if row is not None:
                rows.append(row)

if not rows:
    raise ValueError(f"No metric rows were generated. Check policy/hazard/metric names in {stats_file}.")

result_df = pd.DataFrame(rows)

# Keep a stable order in the output file
result_df = result_df.sort_values(['Category', 'Policy', 'Hazard', 'Metric']).reset_index(drop=True)

# Save output
result_df.to_csv(output_csv, index=False)
print(f"Saved results to: {output_csv}")
print(f"Iterations included: {len(iter_cols)}")
print(f"Rows generated: {len(result_df)}")
