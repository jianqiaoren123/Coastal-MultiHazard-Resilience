
# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()
import os
import pandas as pd
import numpy as np
from dbfread import DBF

import time
start_time = time.time()

# runtime: 50 Chronic simulations x 1000 Acute iterations takes about 6 hours to run.

# --- Parameters and paths ---
# idx_range = range(0, 50) # ONLY simulations 1-9 are available for this code (running Acute in the Combined)
idx_range = range(26, 28)  # For testing with fewer simulations
policies = ['AC1', 'AC3-A', 'AC3', 'AC3-C']
proactive_policies = ['AC3-A', 'AC3', 'AC3-C']
slr_scenarios = ['Low', 'Med', 'High']
hazard_metrics = [
	("Damaged", 'Acute'),
	("Injury", 'Acute'),
	("Fatality", 'Acute'),
	("Casualty", 'Acute'),
	("EconomicLoss", 'Acute'),
	("Damaged", 'Flooding'),
	("PopulationImpacted", 'Flooding'),
	("EconomicLoss", 'Flooding')
]

# Add compound metric for buildings damaged by both Acute and Flooding in selected acute years
hazard_metrics.append(("Damaged", "AcuteAndFlooding"))
# Add Erosion metrics
hazard_metrics.extend([
    ("Eroded", "Erosion"),
    ("PopulationImpacted", "Erosion"),
    ("EconomicLoss", "Erosion")
])
year_acute = ['2050', '2070', '2090']
year_flooding = [str(year) for year in range(2020, 2101)]
n_iter_acute = 1000
# n_iter_acute = 20 # For testing with fewer iterations

# Output directory
save_dir = f"{REPO_ROOT}/Results/Combined/"
if not os.path.exists(save_dir):
	raise FileNotFoundError(f"Output directory does not exist: {save_dir}")

# Helper for error reporting
def report_error(msg):
	raise RuntimeError(msg)

PRIMARY_ROOT = f"{REPO_ROOT}/Simulations"

def resolve_existing_path(candidates, description):
	for path in candidates:
		if os.path.exists(path):
			return path
	report_error(f"{description} not found. Tried: {', '.join(candidates)}")

def resolve_scenario_file(roots, relative_directory, filenames, description):
	candidates = [
		os.path.join(root, relative_directory, filename)
		for root in roots
		for filename in filenames
	]
	return resolve_existing_path(candidates, description)

# --- Data structures to collect all simulation results ---
cumulative_costs = []
metric_values = []
absolute_benefits = []
relative_benefits = []
cost_benefits = []

# --- Helper functions ---
def read_dbf_columns(dbf_path, columns):
	if not os.path.exists(dbf_path):
		report_error(f"DBF file not found: {dbf_path}")
	data = {col: [] for col in columns}
	with DBF(dbf_path, encoding='latin1') as dbf_file:
		for rec in dbf_file:
			for col in columns:
				val = rec.get(col, None)
				try:
					val = float(val)
				except Exception:
					val = np.nan
				data[col].append(val)
	return {k: np.array(v) for k, v in data.items()}

def read_csv_columns(csv_path, columns):
	if not os.path.exists(csv_path):
		report_error(f"CSV file not found: {csv_path}")
	return pd.read_csv(csv_path, usecols=columns)

def read_chronic_annual_metrics(model_output_csv, years):
	columns = [
		'Year',
		'Other Reports.Buildings damaged by Flooding (#)',
		'Other Reports.Economic Loss by Flooding (M$)',
		'Other Reports.Population Impacted by Flooding (#)',
		'Other Reports.Eroded Buildings (#)',
		'Other Reports.Population Impacted by Erosion (#)',
		'Other Reports.Economic Loss by Erosion (M$)'
	]
	df = read_csv_columns(model_output_csv, columns).copy()
	df['Year'] = pd.to_numeric(df['Year'], errors='raise').astype(int)

	column_map = {
		('Damaged', 'Flooding'): 'Other Reports.Buildings damaged by Flooding (#)',
		('PopulationImpacted', 'Flooding'): 'Other Reports.Population Impacted by Flooding (#)',
		('EconomicLoss', 'Flooding'): 'Other Reports.Economic Loss by Flooding (M$)',
		('Eroded', 'Erosion'): 'Other Reports.Eroded Buildings (#)',
		('PopulationImpacted', 'Erosion'): 'Other Reports.Population Impacted by Erosion (#)',
		('EconomicLoss', 'Erosion'): 'Other Reports.Economic Loss by Erosion (M$)'
	}

	metrics = {}
	for year in years:
		year_int = int(year)
		year_rows = df[df['Year'] == year_int]
		if year_rows.empty:
			report_error(f"Missing year {year} in {model_output_csv}")
		if len(year_rows) > 1:
			report_error(f"Duplicate year {year} in {model_output_csv}")
		row = year_rows.iloc[0]
		for (metric, hazard), col in column_map.items():
			metrics[(metric, hazard, year)] = float(row[col])

	return metrics

def agg_and_save(df, group_cols, value_col, out_csv, rename_cols=None):
		def safe_cov(x):
			mean = np.nanmean(x)
			std = np.nanstd(x, ddof=1)
			n = len(x)
			if mean == 0 or n == 0:
				# Print the group combination and values for debugging
				print(f"[DEBUG] Zero mean or empty group in CoV calculation for group: {getattr(x, 'name', None)} | values: {x.values}")
				return np.nan
			return std / mean / np.sqrt(n)
		agg = df.groupby(group_cols)[value_col].agg(['mean', 'std', safe_cov]).reset_index()
		agg.columns = group_cols + ['Mean', 'Std', 'CoV']
		if 'Sim' in df.columns:
			sim_order = sorted(df['Sim'].dropna().unique().tolist())
			sim_pivot = df.pivot_table(index=group_cols, columns='Sim', values=value_col, aggfunc='first').reset_index()
			sim_cols = [f'Sim_{sim}' for sim in sim_order]
			for sim in sim_order:
				sim_pivot[f'Sim_{sim}'] = sim_pivot.get(sim, np.nan)
			sim_pivot = sim_pivot[group_cols + sim_cols]
			result = sim_pivot.merge(agg, on=group_cols, how='left')
			result = result[group_cols + sim_cols + ['Mean', 'Std', 'CoV']]
		else:
			result = agg
		if rename_cols:
			result.rename(columns=rename_cols, inplace=True)
		result.to_csv(os.path.join(save_dir, out_csv), index=False)

# --- Main simulation loop ---

for slr in slr_scenarios:
	for idx in idx_range:
		# --- File path templates ---
		acute_csv = f"{REPO_ROOT}/Simulations/Acute/Acute-Baseline/Run0/AcuteMetric/Cumulative_building_damage_detailed_Acute-Baseline_0.csv"
		chronic_directory = f"Chronic_2020_2100/Chronic-Baseline-{slr}_{idx}/Run0"
		chronic_roots = [PRIMARY_ROOT]
		chronic_dbf = lambda year: resolve_scenario_file(
			chronic_roots,
			chronic_directory,
			[
				f"idu_Year{year}_Chronic-Baseline-{slr}_{idx}_Run0.dbf",
				f"idu_Year{year}_Chronic-Baseline-{slr}_Run0.dbf"
			],
			f"AC1 DBF for year {year}")
		chronic_output_csv = resolve_scenario_file(
			chronic_roots,
			chronic_directory,
			[
				f"ModelOutput_Chronic-Baseline-{slr}_Run0.csv",
				f"ModelOutput_Chronic-Baseline-{slr}_{idx}_Run0.csv"
			],
			"AC1 chronic output CSV")
		policy_map = {
			'AC3-A': {
				'cost_csv': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Acute-{slr}_{idx}/Run0/Global_Constraints_Summary_Untargeted-AcuteAndChronic-Realign_for_Acute-{slr}_Run0.csv",
				'acute_csv': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Acute-{slr}_{idx}/Run0/AcuteMetric/Cumulative_building_damage_detailed_Untargeted-AcuteAndChronic-Realign_for_Acute-{slr}_0.csv",
				'flood_dbf': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Acute-{slr}_{idx}/Run0/idu_Year{{year}}_Untargeted-AcuteAndChronic-Realign_for_Acute-{slr}_Run0.dbf",
				'model_output_csv': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Acute-{slr}_{idx}/Run0/ModelOutput_Untargeted-AcuteAndChronic-Realign_for_Acute-{slr}_Run0.csv"
			},
			'AC3': {
				'cost_csv': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Both-{slr}_{idx}/Run0/Global_Constraints_Summary_Untargeted-AcuteAndChronic-Realign_for_Both-{slr}_Run0.csv",
				'acute_csv': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Both-{slr}_{idx}/Run0/AcuteMetric/Cumulative_building_damage_detailed_Untargeted-AcuteAndChronic-Realign_for_Both-{slr}_0.csv",
				'flood_dbf': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Both-{slr}_{idx}/Run0/idu_Year{{year}}_Untargeted-AcuteAndChronic-Realign_for_Both-{slr}_Run0.dbf",
				'model_output_csv': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Both-{slr}_{idx}/Run0/ModelOutput_Untargeted-AcuteAndChronic-Realign_for_Both-{slr}_Run0.csv"
			},
			'AC3-C': {
				'cost_csv': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Chronic-{slr}_{idx}/Run0/Global_Constraints_Summary_Untargeted-AcuteAndChronic-Realign_for_Chronic-{slr}_Run0.csv",
				'acute_csv': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Chronic-{slr}_{idx}/Run0/AcuteMetric/Cumulative_building_damage_detailed_Untargeted-AcuteAndChronic-Realign_for_Chronic-{slr}_0.csv",
				'flood_dbf': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Chronic-{slr}_{idx}/Run0/idu_Year{{year}}_Untargeted-AcuteAndChronic-Realign_for_Chronic-{slr}_Run0.dbf",
				'model_output_csv': f"{REPO_ROOT}/Simulations/Combined/Untargeted-AcuteAndChronic-Realign_for_Chronic-{slr}_{idx}/Run0/ModelOutput_Untargeted-AcuteAndChronic-Realign_for_Chronic-{slr}_Run0.csv"
			}
		}
		acute_csv = resolve_existing_path([acute_csv], "A1 acute CSV")
		scenario_specs = {
			'AC3-A': ("Both_Chronic_Acute", f"Untargeted-AcuteAndChronic-Realign_for_Acute-{slr}", "AC3-A"),
			'AC3': ("Both_Chronic_Acute", f"Untargeted-AcuteAndChronic-Realign_for_Both-{slr}", "AC3"),
			'AC3-C': ("Chronic_2020_2100", f"Untargeted-Chronic-Realign-{slr}", "AC3-C")
		}
		for policy, (scenario_parent, scenario_stem, scenario_label) in scenario_specs.items():
			scenario_directory = f"{scenario_parent}/{scenario_stem}_{idx}/Run0"
			policy_map[policy]['acute_csv'] = acute_csv
			policy_map[policy]['cost_csv'] = resolve_scenario_file(
				[PRIMARY_ROOT],
				scenario_directory,
				[
					f"Global_Constraints_Summary_{scenario_stem}_{idx}_Run0.csv",
					f"Global_Constraints_Summary_{scenario_stem}_Run0.csv"
				],
				f"{scenario_label} cost CSV")
			policy_map[policy]['model_output_csv'] = resolve_scenario_file(
				[PRIMARY_ROOT],
				scenario_directory,
				[
					f"ModelOutput_{scenario_stem}_{idx}_Run0.csv",
					f"ModelOutput_{scenario_stem}_Run0.csv"
				],
				f"{scenario_label} chronic output CSV")
			policy_map[policy]['flood_dbf'] = lambda year, roots=[PRIMARY_ROOT], directory=scenario_directory, stem=scenario_stem, label=scenario_label, idx_value=idx: resolve_scenario_file(
				roots,
				directory,
				[
					f"idu_Year{year}_{stem}_{idx_value}_Run0.dbf",
					f"idu_Year{year}_{stem}_Run0.dbf"
				],
				f"{label} DBF for year {year}")

		# --- (A) Cumulative Cost for proactive policies ---
		cost_dict = {}
		for policy in proactive_policies:
			cost_csv = policy_map[policy]['cost_csv']
			if not os.path.exists(cost_csv):
				report_error(f"Cost CSV not found: {cost_csv}")
			df_cost = pd.read_csv(cost_csv)
			if policy == 'AC3':
				if ("Relocate Buildings Acute Hazard: Total Costs" not in df_cost.columns or
					"Relocate Buildings Chronic Hazard: Total Costs" not in df_cost.columns or
					"Time (years)" not in df_cost.columns):
					report_error(f"Missing columns in {cost_csv}")
				df_cost['Cumulative'] = (df_cost["Relocate Buildings Acute Hazard: Total Costs"] +
									 df_cost["Relocate Buildings Chronic Hazard: Total Costs"])
			else:
				if ("Relocate Buildings: Total Costs" not in df_cost.columns or
					"Time (years)" not in df_cost.columns):
					report_error(f"Missing columns in {cost_csv}")
				df_cost['Cumulative'] = df_cost["Relocate Buildings: Total Costs"]
			for year in year_flooding:
				mask = df_cost["Time (years)"] <= int(year)
				if not mask.any():
					report_error(f"No data for year {year} in {cost_csv}")
				cum_cost = df_cost.loc[mask, 'Cumulative'].sum()
				cumulative_costs.append({
					'ProactivePolicy': policy, 'SLR': slr, 'Sim': idx, 'Year': year, 'Cumulative_Cost_Change': cum_cost
				})
				cost_dict[(policy, year)] = cum_cost

		# --- (B) Metric values for all policies ---
		# Baseline (AC1)
		acute_df = read_csv_columns(acute_csv, [f"DS_iter_{i}" for i in range(n_iter_acute)] + [f"ls_ftly_iter_{i}" for i in range(n_iter_acute)] + [f"ls_injy_iter_{i}" for i in range(n_iter_acute)] + [f"rep_cost_iter_{i}" for i in range(n_iter_acute)])
		dbf_2070 = chronic_dbf('2070')
		ac1_metric_dict = {}

		# --- Chronic annual metrics for AC1 (from ModelOutput CSV) ---
		ac1_chronic_metrics = read_chronic_annual_metrics(chronic_output_csv, year_flooding)
		for year in year_flooding:
			for metric in ['Damaged', 'PopulationImpacted', 'EconomicLoss']:
				value = ac1_chronic_metrics[(metric, 'Flooding', year)]
				metric_values.append({
					'Policy': 'AC1', 'SLR': slr, 'Hazard': 'Flooding', 'Metric': metric, 'Sim': idx, 'Year': year, 'Value': value
				})
				ac1_metric_dict[(metric, 'Flooding', year)] = value
			for metric in ['Eroded', 'PopulationImpacted', 'EconomicLoss']:
				value = ac1_chronic_metrics[(metric, 'Erosion', year)]
				metric_values.append({
					'Policy': 'AC1', 'SLR': slr, 'Hazard': 'Erosion', 'Metric': metric, 'Sim': idx, 'Year': year, 'Value': value
				})
				ac1_metric_dict[(metric, 'Erosion', year)] = value

		# --- Compound metric for AC1 (Damaged, AcuteAndFlooding) ---
		for acute_year in year_acute:
			dbf_year = chronic_dbf(acute_year)
			dbf_data_full = read_dbf_columns(dbf_year, ['BldgDS_Fld', 'REMOVED', 'ERODED'])
			compound_counts = []
			for i in range(n_iter_acute):
				ds_col = f"DS_iter_{i}"
				if ds_col not in acute_df.columns:
					report_error(f"Missing column {ds_col} in {acute_csv}")
				ds_vals = acute_df[ds_col].values
				bldgds_fld = dbf_data_full['BldgDS_Fld']
				removed = dbf_data_full['REMOVED']
				eroded = dbf_data_full['ERODED']
				# Compound mask: all conditions
				compound_mask = (ds_vals > 0) & (bldgds_fld > 0) & (removed <= 0) & (eroded == 0)
				compound_counts.append(np.sum(compound_mask))
			compound_mean = np.mean(compound_counts)
			metric_values.append({
				'Policy': 'AC1', 'SLR': slr, 'Hazard': 'AcuteAndFlooding', 'Metric': 'Damaged', 'Sim': idx, 'Year': acute_year, 'Value': compound_mean
			})
			ac1_metric_dict[("Damaged", "AcuteAndFlooding", acute_year)] = compound_mean
		for acute_year in year_acute:
			dbf_year = chronic_dbf(acute_year)
			dbf_data = read_dbf_columns(dbf_year, ['REMOVED', 'ERODED'])
			mask = (dbf_data['REMOVED'] <= 0) & (dbf_data['ERODED'] == 0)
			for metric in ['Damaged', 'Injury', 'Fatality', 'Casualty', 'EconomicLoss']:
				vals = []
				for i in range(n_iter_acute):
					if metric == 'Casualty':
						col_ftly = f"ls_ftly_iter_{i}"
						col_injy = f"ls_injy_iter_{i}"
						if col_ftly not in acute_df.columns or col_injy not in acute_df.columns:
							report_error(f"Missing column {col_ftly} or {col_injy} in {acute_csv}")
						arr = (acute_df[col_ftly].values + acute_df[col_injy].values)[mask]
						vals.append(np.sum(arr))
					elif metric == 'Injury':
						col = f"ls_injy_iter_{i}"
						if col not in acute_df.columns:
							report_error(f"Missing column {col} in {acute_csv}")
						arr = acute_df[col].values[mask]
						vals.append(np.sum(arr))
					elif metric == 'Fatality':
						col = f"ls_ftly_iter_{i}"
						if col not in acute_df.columns:
							report_error(f"Missing column {col} in {acute_csv}")
						arr = acute_df[col].values[mask]
						vals.append(np.sum(arr))
					else:
						col = f"DS_iter_{i}" if metric == 'Damaged' else f"rep_cost_iter_{i}"
						if col not in acute_df.columns:
							report_error(f"Missing column {col} in {acute_csv}")
						arr = acute_df[col].values[mask]
						if metric == 'Damaged':
							arr_full = acute_df[col].values
							count = np.sum((arr_full > 0) & mask)
							vals.append(count)
						elif metric == 'EconomicLoss':
							vals.append(np.sum(arr) / 1e6)
				mean_val = np.mean(vals)
				metric_values.append({
					'Policy': 'AC1', 'SLR': slr, 'Hazard': 'Acute', 'Metric': metric, 'Sim': idx, 'Year': acute_year, 'Value': mean_val
				})
				ac1_metric_dict[(metric, 'Acute', acute_year)] = mean_val

		# Proactive policies
		for policy in proactive_policies:
			acute_csv = policy_map[policy]['acute_csv']
			flood_dbf = policy_map[policy]['flood_dbf']
			model_output_csv = policy_map[policy]['model_output_csv']
			acute_df = read_csv_columns(acute_csv, [f"DS_iter_{i}" for i in range(n_iter_acute)] + [f"ls_ftly_iter_{i}" for i in range(n_iter_acute)] + [f"ls_injy_iter_{i}" for i in range(n_iter_acute)] + [f"rep_cost_iter_{i}" for i in range(n_iter_acute)])
			dbf_2070 = flood_dbf('2070')
			policy_metric_dict = {}

			# --- Chronic annual metrics for proactive policy (from ModelOutput CSV) ---
			policy_chronic_metrics = read_chronic_annual_metrics(model_output_csv, year_flooding)
			for year in year_flooding:
				for metric in ['Damaged', 'PopulationImpacted', 'EconomicLoss']:
					value = policy_chronic_metrics[(metric, 'Flooding', year)]
					metric_values.append({
						'Policy': policy, 'SLR': slr, 'Hazard': 'Flooding', 'Metric': metric, 'Sim': idx, 'Year': year, 'Value': value
					})
					policy_metric_dict[(metric, 'Flooding', year)] = value
				for metric in ['Eroded', 'PopulationImpacted', 'EconomicLoss']:
					value = policy_chronic_metrics[(metric, 'Erosion', year)]
					metric_values.append({
						'Policy': policy, 'SLR': slr, 'Hazard': 'Erosion', 'Metric': metric, 'Sim': idx, 'Year': year, 'Value': value
					})
					policy_metric_dict[(metric, 'Erosion', year)] = value

			# --- Compound metric for proactive policy (Damaged, AcuteAndFlooding) ---
			for acute_year in year_acute:
				dbf_year = flood_dbf(acute_year)
				dbf_data_full = read_dbf_columns(dbf_year, ['BldgDS_Fld', 'REMOVED', 'ERODED'])
				compound_counts = []
				for i in range(n_iter_acute):
					ds_col = f"DS_iter_{i}"
					if ds_col not in acute_df.columns:
						report_error(f"Missing column {ds_col} in {acute_csv}")
					ds_vals = acute_df[ds_col].values
					bldgds_fld = dbf_data_full['BldgDS_Fld']
					removed = dbf_data_full['REMOVED']
					eroded = dbf_data_full['ERODED']
					compound_mask = (ds_vals > 0) & (bldgds_fld > 0) & (removed <= 0) & (eroded == 0)
					compound_counts.append(np.sum(compound_mask))
				compound_mean = np.mean(compound_counts)
				metric_values.append({
					'Policy': policy, 'SLR': slr, 'Hazard': 'AcuteAndFlooding', 'Metric': 'Damaged', 'Sim': idx, 'Year': acute_year, 'Value': compound_mean
				})
				policy_metric_dict[("Damaged", "AcuteAndFlooding", acute_year)] = compound_mean
			for acute_year in year_acute:
				dbf_year = flood_dbf(acute_year)
				dbf_data = read_dbf_columns(dbf_year, ['REMOVED', 'ERODED'])
				mask = (dbf_data['REMOVED'] <= 0) & (dbf_data['ERODED'] == 0)
				for metric in ['Damaged', 'Injury', 'Fatality', 'Casualty', 'EconomicLoss']:
					vals = []
					for i in range(n_iter_acute):
						if metric == 'Casualty':
							col_ftly = f"ls_ftly_iter_{i}"
							col_injy = f"ls_injy_iter_{i}"
							if col_ftly not in acute_df.columns or col_injy not in acute_df.columns:
								report_error(f"Missing column {col_ftly} or {col_injy} in {acute_csv}")
							arr = (acute_df[col_ftly].values + acute_df[col_injy].values)[mask]
							vals.append(np.sum(arr))
						elif metric == 'Injury':
							col = f"ls_injy_iter_{i}"
							if col not in acute_df.columns:
								report_error(f"Missing column {col} in {acute_csv}")
							arr = acute_df[col].values[mask]
							vals.append(np.sum(arr))
						elif metric == 'Fatality':
							col = f"ls_ftly_iter_{i}"
							if col not in acute_df.columns:
								report_error(f"Missing column {col} in {acute_csv}")
							arr = acute_df[col].values[mask]
							vals.append(np.sum(arr))
						else:
							col = f"DS_iter_{i}" if metric == 'Damaged' else f"rep_cost_iter_{i}"
							if col not in acute_df.columns:
								report_error(f"Missing column {col} in {acute_csv}")
							arr = acute_df[col].values[mask]
							if metric == 'Damaged':
								arr_full = acute_df[col].values
								count = np.sum((arr_full > 0) & mask)
								vals.append(count)
							elif metric == 'EconomicLoss':
								vals.append(np.sum(arr) / 1e6)
					mean_val = np.mean(vals)
					metric_values.append({
						'Policy': policy, 'SLR': slr, 'Hazard': 'Acute', 'Metric': metric, 'Sim': idx, 'Year': acute_year, 'Value': mean_val
					})
					policy_metric_dict[(metric, 'Acute', acute_year)] = mean_val

			# --- (C-E) Calculate Absolute, Relative, and Cost-Benefit statistics for this simulation ---
			for hazard, metric in [(h, m) for m, h in hazard_metrics]:
				years = year_acute if hazard in ['Acute', 'AcuteAndFlooding'] else year_flooding
				for year in years:
					base_val = ac1_metric_dict.get((metric, hazard, year), np.nan)
					pol_val = policy_metric_dict.get((metric, hazard, year), np.nan)
					abs_change = pol_val - base_val
					rel_change = ((pol_val - base_val) / base_val * 100) if base_val != 0 else np.nan
					cost = cost_dict.get((policy, year), np.nan)
					cb_val = (rel_change / cost) if (cost != 0 and not np.isnan(cost)) else np.nan
					absolute_benefits.append({
						'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric, 'Sim': idx, 'Year': year, 'Absolute_Change': abs_change
					})
					relative_benefits.append({
						'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric, 'Sim': idx, 'Year': year, 'Percent_Change': rel_change
					})
					cost_benefits.append({
						'ProactivePolicy': policy, 'SLR': slr, 'Hazard': hazard, 'Metric': metric, 'Sim': idx, 'Year': year, 'Percent_Change_PerMUSD': cb_val
					})




# --- Save all statistics ---

cumulative_costs_df = pd.DataFrame(cumulative_costs)
metric_df = pd.DataFrame(metric_values)
absolute_benefits_df = pd.DataFrame(absolute_benefits)
relative_benefits_df = pd.DataFrame(relative_benefits)
cost_benefits_df = pd.DataFrame(cost_benefits)


# Only keep AcuteAndFlooding for selected acute years in benefit/cost outputs
def filter_acuteandflooding_years(df):
	mask = ~((df['Hazard'] == 'AcuteAndFlooding') & (~df['Year'].isin(year_acute)))
	return df[mask]

absolute_benefits_df = filter_acuteandflooding_years(absolute_benefits_df)
relative_benefits_df = filter_acuteandflooding_years(relative_benefits_df)
cost_benefits_df = filter_acuteandflooding_years(cost_benefits_df)

# (A) Cumulative Cost Statistics
agg_and_save(cumulative_costs_df, ['ProactivePolicy', 'SLR', 'Year'], 'Cumulative_Cost_Change', 'Statistics_Both_CumulativeCost_Annual_PerSim.csv')
# (B) Metric Statistics
agg_and_save(metric_df, ['Policy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Value', 'Statistics_Both_Metric_Annual_PerSim.csv')
# (C) Absolute Benefit
agg_and_save(absolute_benefits_df, ['ProactivePolicy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Absolute_Change', 'Statistics_Both_AbsoluteBenefit_Annual_PerSim.csv')
# (D) Relative Benefit
agg_and_save(relative_benefits_df, ['ProactivePolicy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Percent_Change', 'Statistics_Both_RelativeBenefit_Annual_PerSim.csv')
# (E) Cost-Benefit
agg_and_save(cost_benefits_df, ['ProactivePolicy', 'SLR', 'Hazard', 'Metric', 'Year'], 'Percent_Change_PerMUSD', 'Statistics_Both_CostBenefit_Annual_PerSim.csv')

print(f"Total run time: {time.time() - start_time:.2f} seconds")