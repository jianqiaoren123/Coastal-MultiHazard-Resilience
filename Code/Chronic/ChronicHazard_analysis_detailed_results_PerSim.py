
# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()
# --- Analyze simulations, plot DETAILED figures, and save DETAILED RESULTS for plots and reporting ---
import os
import pandas as pd
import numpy as np
import struct
import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy.stats import t
from dbfread import DBF
import glob

# --- Parameters and paths ---
base_dir = rf"{REPO_ROOT}/Simulations/Chronic/"
idu_path = rf"{REPO_ROOT}/Simulations/IDU/idu.dbf"
save_dir = rf"{REPO_ROOT}/Results/Chronic/"
os.makedirs(save_dir, exist_ok=True)

# --- Data Preparation: Calculate and save total numbers (no simulation loop) ---
# Read IDU dbf, calculate Total_Buildings, Total_Population, Total_Property_Value
# Save to TotalNumber_Statistics.csv

needed_fields = ['impr_value', 'TotalPop', 'BLDGVALUE']
field_types = {}
field_offsets = {}
field_lengths = {}

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
            try:
                val = rec[start:end].decode('latin1', errors='ignore').strip()
                if val == '' or val is None:
                    data[k].append(np.nan)
                else:
                    data[k].append(float(val))
            except Exception:
                data[k].append(np.nan)
idf = pd.DataFrame(data)
idf = idf.dropna(subset=needed_fields)
building_mask = idf['impr_value'] > 10000
total_buildings = len(idf[building_mask])
total_population = idf['TotalPop'].sum()
total_property_value = idf[building_mask]['BLDGVALUE'].sum()

stats = pd.DataFrame([
    {'Metric': 'Total_Buildings', 'Value': total_buildings, 'Unit': 'count'},
    {'Metric': 'Total_Population', 'Value': total_population, 'Unit': 'people'},
    {'Metric': 'Total_Property_Value', 'Value': total_property_value / 1e6, 'Unit': 'million $'}
])
stats.to_csv(os.path.join(save_dir, 'TotalNumber_Statistics.csv'), index=False)

# --- Simulation Loop: Read, calculate, and store all results ---
# Update these paths as needed
policies_dict = {
    'Baseline': ["Chronic-Baseline-Low_idx", "Chronic-Baseline-Med_idx", "Chronic-Baseline-High_idx"],
    'Protect': ["Untargeted-Chronic-Protect-Low_idx", "Untargeted-Chronic-Protect-Med_idx", "Untargeted-Chronic-Protect-High_idx"],
    'Realign': ["Untargeted-Chronic-Realign-Low_idx", "Untargeted-Chronic-Realign-Med_idx", "Untargeted-Chronic-Realign-High_idx"]
}

# Define policies, SLRs, metrics, hazards, and simulation indices
policies = ['Baseline', 'Protect', 'Realign']
proactive_policies = ['Protect', 'Realign']
slr_scenarios = ['Low', 'Med', 'High']
idx_range = range(0, 50)  # n-1 simulations: 0,1,.., n-1 if range(0, n) is used
cb_metrics = [
    ("Other Reports.Buildings damaged by Flooding (#)", "Damaged", 'Flooding'),
    ("Other Reports.Economic Loss by Flooding (M$)", "EconomicLoss", 'Flooding'),
    ("Other Reports.Population Impacted by Flooding (#)", "PopulationImpacted", 'Flooding'),
    ("Other Reports.Eroded Buildings (#)", "Eroded", 'Erosion'),
    ("Other Reports.Economic Loss by Erosion (M$)", "EconomicLoss", 'Erosion'),
    ("Other Reports.Population Impacted by Erosion (#)", "PopulationImpacted", 'Erosion')
]

# Data structures to collect all simulation results
cumulative_costs = []  # For Cumulative_Cost_Change
metric_values = []     # For each metric
absolute_benefits = [] # For Absolute_Change
relative_benefits = [] # For Percent_Change
cost_benefits = []     # For Percent_Change_PerMUSD

# For each simulation, for each policy, SLR, year, hazard, metric, store the required values in the above lists.

# --- Simulation reading and calculations for A-E ---
# This block reads all simulation results, calculates all required metrics, and saves the five required CSVs.
for idx in idx_range:
    for slr_i, slr in enumerate(slr_scenarios):
        # --- Read cost CSVs for all policies ---
        dfs = {}
        for policy in policies:
            folder = policies_dict[policy][slr_i].replace('idx', f'{idx}')
            policy_template = policies_dict[policy][slr_i]
            default_filename = f"ModelOutput_{policy_template.replace('idx', '')}Run0.csv"
            indexed_filename = f"ModelOutput_{policy_template.replace('idx', str(idx))}_Run0.csv"
            path = os.path.join(base_dir, folder, "Run0", default_filename)
            if not os.path.exists(path):
                path = os.path.join(base_dir, folder, "Run0", indexed_filename)
            if not os.path.exists(path):
                dfs[policy] = None
                continue
            try:
                dfs[policy] = pd.read_csv(path)
            except pd.errors.EmptyDataError as exc:
                raise ValueError(
                    f"Empty model-output CSV for simulation idx={idx}, "
                    f"policy={policy}, SLR={slr}: {path}"
                ) from exc
        # Realign relocation cost
        real_folder = policies_dict['Realign'][slr_i].replace('idx', f'{idx}')
        real_folder_base = real_folder
        for suffix in ['-Low', '-Med', '-High']:
            if real_folder_base.endswith(suffix + f'_{idx}'):
                real_folder_base = real_folder_base.replace(f'{suffix}_{idx}', suffix)
        relocate_csv = os.path.join(base_dir, real_folder, "Run0", f"Global_Constraints_Summary_{real_folder_base}_Run0.csv")
        if not os.path.exists(relocate_csv):
            indexed_relocate_csv = os.path.join(
                base_dir, real_folder, "Run0",
                f"Global_Constraints_Summary_{real_folder_base}_{idx}_Run0.csv"
            )
            if os.path.exists(indexed_relocate_csv):
                relocate_csv = indexed_relocate_csv
        # --- Skip if any policy missing ---
        if any(dfs[p] is None for p in ['Baseline', 'Protect', 'Realign']):
            continue
        df_base, df_prot, df_real = dfs['Baseline'], dfs['Protect'], dfs['Realign']
        # Only keep years between 2020 and 2100 (inclusive)
        year_mask = (df_base['Year'] >= 2020) & (df_base['Year'] <= 2100)
        df_base = df_base.loc[year_mask].reset_index(drop=True)
        df_prot = df_prot.loc[year_mask].reset_index(drop=True)
        df_real = df_real.loc[year_mask].reset_index(drop=True)
        years_all = df_base['Year'].values
        # --- Annual cost arrays ---
        base_annual = df_base["Chronic Hazards.BPS Total Maintenance Cost ($)"].values / 1e6
        prot_annual = (
            df_prot["Chronic Hazards.BPS Construction Cost ($)"].values +
            df_prot["Chronic Hazards.BPS Total Maintenance Cost ($)"].values +
            df_prot["Chronic Hazards.Raise Buildings Cost ($)"].values
        ) / 1e6
        real_annual_1 = df_real["Chronic Hazards.BPS Total Maintenance Cost ($)"].values / 1e6
        real_annual_2 = np.zeros_like(real_annual_1)
        if os.path.exists(relocate_csv):
            try:
                df_sum = pd.read_csv(relocate_csv)
            except pd.errors.EmptyDataError as exc:
                raise ValueError(
                    f"Empty relocation summary CSV for simulation idx={idx}, "
                    f"policy=Realign, SLR={slr}: {relocate_csv}"
                ) from exc
            year_col = 'Time (years)' if 'Time (years)' in df_sum.columns else ('Time (year)' if 'Time (year)' in df_sum.columns else ('Year' if 'Year' in df_sum.columns else None))
            if "Relocate Buildings: Total Costs" in df_sum.columns and year_col is not None:
                df_sum[year_col] = df_sum[year_col].astype(int)
                for yidx, yval in enumerate(years_all):
                    yval_int = int(yval)
                    match = df_sum.loc[df_sum[year_col] == yval_int, "Relocate Buildings: Total Costs"]
                    if not match.empty:
                        real_annual_2[yidx] = match.values[0]
        real_annual = real_annual_1 + real_annual_2
        
        # --- (A) Cumulative Cost Change ---
        for policy, annual in zip(proactive_policies, [prot_annual, real_annual]):
            cost_diff = annual - base_annual
            cum_cost_diff = np.cumsum(cost_diff)
            for yidx, year in enumerate(years_all):
                cumulative_costs.append({
                    'ProactivePolicy': policy, 'SLR': slr, 'Sim': idx, 'Year': year, 'Cumulative_Cost_Change': cum_cost_diff[yidx]
                })
        # --- (B-E) Metric calculations ---
        for metric_col, metric_label, hazard in cb_metrics:
            base_vals = df_base[metric_col].values
            prot_vals = df_prot[metric_col].values
            real_vals = df_real[metric_col].values
            # (B) Raw metric values for all policies
            for policy, vals in zip(policies, [base_vals, prot_vals, real_vals]):
                for yidx, year in enumerate(years_all):
                    metric_values.append({
                        'Policy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric_label, 'Sim': idx, 'Year': year, 'Value': vals[yidx]
                    })
            # (C) Absolute Benefit, (D) Relative Benefit, (E) Cost-Benefit for proactive policies only
            for policy, vals in zip(proactive_policies, [prot_vals, real_vals]):
                # (C) Absolute Benefit
                abs_change = vals - base_vals
                for yidx, year in enumerate(years_all):
                    absolute_benefits.append({
                        'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric_label, 'Sim': idx, 'Year': year, 'Absolute_Change': abs_change[yidx]
                    })
                # (D) Relative Benefit
                with np.errstate(divide='ignore', invalid='ignore'):
                    rel_change = np.where(base_vals != 0, (vals - base_vals) / base_vals * 100, np.nan)
                for yidx, year in enumerate(years_all):
                    relative_benefits.append({
                        'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric_label, 'Sim': idx, 'Year': year, 'Percent_Change': rel_change[yidx]
                    })
                # (E) Cost-Benefit
                # Find cumulative cost change for this policy/SLR/sim/year
                cost_map = {(d['ProactivePolicy'], d['SLR'], d['Sim'], d['Year']): d['Cumulative_Cost_Change'] for d in cumulative_costs}
                for yidx, year in enumerate(years_all):
                    cost = cost_map.get((policy, slr, idx, year), np.nan)
                    if cost != 0 and not np.isnan(cost):
                        cb_val = rel_change[yidx] / cost
                    else:
                        cb_val = np.nan
                    cost_benefits.append({
                        'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric_label, 'Sim': idx, 'Year': year, 'Percent_Change_PerMUSD': cb_val
                    })

# --- Aggregation and CSV saving for A-E ---
def agg_and_save(df, group_cols, value_col, out_csv, rename_cols=None):
    simulation_columns = [f'Sim_{simulation_index}' for simulation_index in idx_range]
    per_simulation = (
        df.pivot_table(
            index=group_cols,
            columns='Sim',
            values=value_col,
            aggfunc='first'
        )
        .reindex(columns=idx_range)
        .rename(columns=lambda simulation_index: f'Sim_{simulation_index}')
        .reset_index()
    )
    per_simulation = per_simulation.reindex(
        columns=group_cols + simulation_columns
    )
    agg = df.groupby(group_cols)[value_col].agg([
        'mean',
        'std',
        lambda x: np.nan if np.nanmean(x) == 0 else np.nanstd(x, ddof=1) / np.nanmean(x) / np.sqrt(len(x))
    ]).reset_index()
    agg.columns = group_cols + ['Mean', 'Std', 'CoV']
    agg = per_simulation.merge(agg, on=group_cols, how='left')
    if rename_cols:
        agg.rename(columns=rename_cols, inplace=True)
    agg.to_csv(os.path.join(save_dir, out_csv), index=False)

def cov_for_simulation_ranges(df, group_cols, value_col, simulation_counts):
    cov_rows = []
    for group_values, group_df in df.groupby(group_cols, dropna=False):
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        row = list(group_values)
        for simulation_count in simulation_counts:
            values = group_df.loc[group_df['Sim'] < simulation_count, value_col]
            mean_value = np.nanmean(values)
            cov_value = np.nan if mean_value == 0 else np.nanstd(values, ddof=1) / mean_value / np.sqrt(len(values))
            row.extend([simulation_count, cov_value])
        cov_rows.append(row)

    cov_columns = group_cols + ['Simulation_Count', 'CoV'] * len(simulation_counts)
    return pd.DataFrame(cov_rows, columns=cov_columns)

# (A) Cumulative Cost Statistics
cumulative_costs_df = pd.DataFrame(cumulative_costs)
agg_and_save(cumulative_costs_df, ['ProactivePolicy', 'SLR', 'Year'], 'Cumulative_Cost_Change', 'Statistics_Chronic_CumulativeCost_PerSim.csv')

# (B) Metric Statistics
metric_values_df = pd.DataFrame(metric_values)
agg_and_save(metric_values_df, ['Policy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Value', 'Statistics_Chronic_Metric_PerSim.csv')

# (C) Absolute Benefit
absolute_benefits_df = pd.DataFrame(absolute_benefits)
agg_and_save(absolute_benefits_df, ['ProactivePolicy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Absolute_Change', 'Statistics_Chronic_AbsoluteBenefit_PerSim.csv')

# (D) Relative Benefit
relative_benefits_df = pd.DataFrame(relative_benefits)
agg_and_save(relative_benefits_df, ['ProactivePolicy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Percent_Change', 'Statistics_Chronic_RelativeBenefit_PerSim.csv')

# (E) Cost-Benefit
cost_benefits_df = pd.DataFrame(cost_benefits)
agg_and_save(cost_benefits_df, ['ProactivePolicy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Percent_Change_PerMUSD', 'Statistics_Chronic_CostBenefit_PerSim.csv')

# --- CoV for cumulative simulation ranges ---
cov_start_simulations = 20
cov_interval_simulations = 5
cov_total_simulations = len(idx_range)

if cov_start_simulations < 1:
    raise ValueError('cov_start_simulations must be at least 1')
if cov_interval_simulations < 1:
    raise ValueError('cov_interval_simulations must be at least 1')
if cov_total_simulations < cov_start_simulations:
    raise ValueError('cov_total_simulations must be at least cov_start_simulations')

simulation_counts = list(range(
    cov_start_simulations,
    cov_total_simulations + 1,
    cov_interval_simulations
))
if simulation_counts[-1] != cov_total_simulations:
    simulation_counts.append(cov_total_simulations)
cov_results_df = cov_for_simulation_ranges(
    metric_values_df, ['Policy', 'SLR', 'Hazard', 'Metric', 'Year'],
    'Value', simulation_counts
)
cov_results_df.to_csv(
    os.path.join(save_dir, 'Statistics_Chronic_CoV.csv'), index=False
)

# --- End of full implementation ---