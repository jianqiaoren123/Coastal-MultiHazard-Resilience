
# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()
import os

import numpy as np
import pandas as pd


base_dir = rf"{REPO_ROOT}/Simulations/Chronic/"
corner1_dir = rf"{REPO_ROOT}/Simulations/Sensitivity/Chronic_Corner1/"
save_dir = rf"{REPO_ROOT}/Results/Sensitivity/"
os.makedirs(save_dir, exist_ok=True)

baseline_totals_csv = os.path.join(save_dir, "TotalNumber_Corner1_Statistics_PerSim.csv")
if not os.path.isfile(baseline_totals_csv):
    raise FileNotFoundError(
        f"Required existing input missing: {baseline_totals_csv}. "
        "Obtain the published Results CSV; the baseline IDU DBF is not distributed."
    )

policies_dict = {
	'Baseline': ['Chronic-Baseline-Low_idx', 'Chronic-Baseline-Med_idx', 'Chronic-Baseline-High_idx'],
	'Protect': ['Untargeted-Chronic-Protect-Low_idx', 'Untargeted-Chronic-Protect-Med_idx', 'Untargeted-Chronic-Protect-High_idx'],
	'Realign': ['Untargeted-Chronic-Realign-Low_idx', 'Untargeted-Chronic-Realign-Med_idx', 'Untargeted-Chronic-Realign-High_idx']
}
policies = ['Baseline', 'Protect', 'Realign']
proactive_policies = ['Protect', 'Realign']
slr_scenarios = ['Low', 'Med', 'High']
idx_range = range(0, 50)
cb_metrics = [
	('Other Reports.Buildings damaged by Flooding (#)', 'Damaged', 'Flooding'),
	('Other Reports.Economic Loss by Flooding (M$)', 'EconomicLoss', 'Flooding'),
	('Other Reports.Population Impacted by Flooding (#)', 'PopulationImpacted', 'Flooding'),
	('Other Reports.Eroded Buildings (#)', 'Eroded', 'Erosion'),
	('Other Reports.Economic Loss by Erosion (M$)', 'EconomicLoss', 'Erosion'),
	('Other Reports.Population Impacted by Erosion (#)', 'PopulationImpacted', 'Erosion')
]

cumulative_costs = []
metric_values = []
absolute_benefits = []
relative_benefits = []
cost_benefits = []


def simulation_root(policy):
	return base_dir if policy == 'Baseline' else corner1_dir


def read_model_output(policy, slr_index, simulation_index):
	template = policies_dict[policy][slr_index]
	folder = template.replace('idx', str(simulation_index))
	run_dir = os.path.join(simulation_root(policy), folder, 'Run0')
	default_path = os.path.join(run_dir, f"ModelOutput_{template.replace('idx', '')}Run0.csv")
	indexed_path = os.path.join(run_dir, f"ModelOutput_{template.replace('idx', str(simulation_index))}_Run0.csv")
	path = default_path if os.path.exists(default_path) else indexed_path
	if not os.path.exists(path):
		return None
	try:
		return pd.read_csv(path)
	except pd.errors.EmptyDataError as exc:
		raise ValueError(
			f'Empty model-output CSV for simulation idx={simulation_index}, '
			f'policy={policy}, SLR={slr_scenarios[slr_index]}: {path}'
		) from exc


for simulation_index in idx_range:
	for slr_index, slr in enumerate(slr_scenarios):
		dfs = {policy: read_model_output(policy, slr_index, simulation_index) for policy in policies}
		real_folder = policies_dict['Realign'][slr_index].replace('idx', str(simulation_index))
		real_folder_base = real_folder
		for suffix in ['-Low', '-Med', '-High']:
			if real_folder_base.endswith(f'{suffix}_{simulation_index}'):
				real_folder_base = real_folder_base.replace(f'{suffix}_{simulation_index}', suffix)
		relocation_dir = os.path.join(corner1_dir, real_folder, 'Run0')
		relocation_path = os.path.join(relocation_dir, f'Global_Constraints_Summary_{real_folder_base}_Run0.csv')
		if not os.path.exists(relocation_path):
			relocation_path = os.path.join(relocation_dir, f'Global_Constraints_Summary_{real_folder_base}_{simulation_index}_Run0.csv')
		if any(dfs[policy] is None for policy in policies):
			continue

		df_base, df_prot, df_real = (dfs[policy] for policy in policies)
		year_mask = (df_base['Year'] >= 2020) & (df_base['Year'] <= 2100)
		df_base = df_base.loc[year_mask].reset_index(drop=True)
		df_prot = df_prot.loc[year_mask].reset_index(drop=True)
		df_real = df_real.loc[year_mask].reset_index(drop=True)
		years_all = df_base['Year'].values

		base_annual = df_base['Chronic Hazards.BPS Total Maintenance Cost ($)'].values / 1e6
		base_annual = np.minimum(base_annual * 0.5, 5)
		prot_annual = (
			df_prot['Chronic Hazards.BPS Construction Cost ($)'].values
			+ df_prot['Chronic Hazards.BPS Total Maintenance Cost ($)'].values
			+ df_prot['Chronic Hazards.Raise Buildings Cost ($)'].values
		) / 1e6
		real_annual_1 = df_real['Chronic Hazards.BPS Total Maintenance Cost ($)'].values / 1e6
		real_annual_2 = np.zeros_like(real_annual_1)
		if os.path.exists(relocation_path):
			try:
				df_sum = pd.read_csv(relocation_path)
			except pd.errors.EmptyDataError as exc:
				raise ValueError(
					f'Empty relocation summary CSV for simulation idx={simulation_index}, '
					f'policy=Realign, SLR={slr}: {relocation_path}'
				) from exc
			year_col = next((column for column in ['Time (years)', 'Time (year)', 'Year'] if column in df_sum.columns), None)
			if 'Relocate Buildings: Total Costs' in df_sum.columns and year_col is not None:
				df_sum[year_col] = df_sum[year_col].astype(int)
				for year_index, year in enumerate(years_all):
					match = df_sum.loc[df_sum[year_col] == int(year), 'Relocate Buildings: Total Costs']
					if not match.empty:
						real_annual_2[year_index] = match.values[0]
		real_annual = real_annual_1 + real_annual_2

		for policy, annual in zip(proactive_policies, [prot_annual, real_annual]):
			cumulative_cost = np.cumsum(annual - base_annual)
			for year_index, year in enumerate(years_all):
				cumulative_costs.append({
					'ProactivePolicy': policy, 'SLR': slr, 'Sim': simulation_index,
					'Year': year, 'Cumulative_Cost_Change': cumulative_cost[year_index]
				})

		for metric_col, metric_label, hazard in cb_metrics:
			base_values = df_base[metric_col].values
			prot_values = df_prot[metric_col].values
			real_values = df_real[metric_col].values
			for policy, values in zip(policies, [base_values, prot_values, real_values]):
				for year_index, year in enumerate(years_all):
					metric_values.append({
						'Policy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric_label,
						'Sim': simulation_index, 'Year': year, 'Value': values[year_index]
					})
			cost_map = {(row['ProactivePolicy'], row['SLR'], row['Sim'], row['Year']): row['Cumulative_Cost_Change'] for row in cumulative_costs}
			for policy, values in zip(proactive_policies, [prot_values, real_values]):
				absolute_change = values - base_values
				with np.errstate(divide='ignore', invalid='ignore'):
					relative_change = np.where(base_values != 0, absolute_change / base_values * 100, np.nan)
				for year_index, year in enumerate(years_all):
					absolute_benefits.append({
						'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric_label,
						'Sim': simulation_index, 'Year': year, 'Absolute_Change': absolute_change[year_index]
					})
					relative_benefits.append({
						'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric_label,
						'Sim': simulation_index, 'Year': year, 'Percent_Change': relative_change[year_index]
					})
					cost = cost_map.get((policy, slr, simulation_index, year), np.nan)
					cost_benefits.append({
						'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric_label,
						'Sim': simulation_index, 'Year': year,
						'Percent_Change_PerMUSD': relative_change[year_index] / cost if cost != 0 and not np.isnan(cost) else np.nan
					})


def agg_and_save(df, group_cols, value_col, out_csv):
	simulation_columns = [f'Sim_{simulation_index}' for simulation_index in idx_range]
	per_simulation = (df.pivot_table(index=group_cols, columns='Sim', values=value_col, aggfunc='first')
		.reindex(columns=idx_range).rename(columns=lambda index: f'Sim_{index}').reset_index()
		.reindex(columns=group_cols + simulation_columns))
	agg = df.groupby(group_cols)[value_col].agg([
		'mean', 'std',
		lambda values: np.nan if np.nanmean(values) == 0 else np.nanstd(values, ddof=1) / np.nanmean(values) / np.sqrt(len(values))
	]).reset_index()
	agg.columns = group_cols + ['Mean', 'Std', 'CoV']
	per_simulation.merge(agg, on=group_cols, how='left').to_csv(os.path.join(save_dir, out_csv), index=False)


def cov_for_simulation_ranges(df, group_cols, value_col, simulation_counts):
	rows = []
	for group_values, group_df in df.groupby(group_cols, dropna=False):
		group_values = group_values if isinstance(group_values, tuple) else (group_values,)
		row = list(group_values)
		for count in simulation_counts:
			values = group_df.loc[group_df['Sim'] < count, value_col]
			mean_value = np.nanmean(values)
			cov = np.nan if mean_value == 0 else np.nanstd(values, ddof=1) / mean_value / np.sqrt(len(values))
			row.extend([count, cov])
		rows.append(row)
	return pd.DataFrame(rows, columns=group_cols + ['Simulation_Count', 'CoV'] * len(simulation_counts))


frames = [
	(pd.DataFrame(cumulative_costs), ['ProactivePolicy', 'SLR', 'Year'], 'Cumulative_Cost_Change', 'Statistics_Chronic_Corner1_CumulativeCost_PerSim.csv'),
	(pd.DataFrame(metric_values), ['Policy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Value', 'Statistics_Chronic_Corner1_Metric_PerSim.csv'),
	(pd.DataFrame(absolute_benefits), ['ProactivePolicy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Absolute_Change', 'Statistics_Chronic_Corner1_AbsoluteBenefit_PerSim.csv'),
	(pd.DataFrame(relative_benefits), ['ProactivePolicy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Percent_Change', 'Statistics_Chronic_Corner1_RelativeBenefit_PerSim.csv'),
	(pd.DataFrame(cost_benefits), ['ProactivePolicy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Percent_Change_PerMUSD', 'Statistics_Chronic_Corner1_CostBenefit_PerSim.csv')
]
for frame, groups, value_col, filename in frames:
	agg_and_save(frame, groups, value_col, filename)

simulation_counts = list(range(20, len(idx_range) + 1, 5))
if simulation_counts[-1] != len(idx_range):
	simulation_counts.append(len(idx_range))
cov_for_simulation_ranges(
	pd.DataFrame(metric_values), ['Policy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Value', simulation_counts
).to_csv(os.path.join(save_dir, 'Statistics_Chronic_Corner1_CoV.csv'), index=False)
