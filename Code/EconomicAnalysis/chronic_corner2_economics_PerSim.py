"""
chronic_economics.py
======================
Replicates the four "Chronic (3.2)" tabs of EnvisonEconomics_final.xlsx:
Damages Baseline, Damages Policy, Expenditures, and NetPresentValues.

Unlike Acute, Chronic damages and costs accrue every simulation year
(2020-2100), not at a single event year. Computes, for a single
simulation replicate, the annual present-value net benefit
[(baseline damage - policy damage) - expenditure] for each policy x SLR
scenario, and the cumulative NPV trajectory (running sum of annual net
benefit through each year), matching the "NPV for Policy" rows in the
workbook's NetPresentValues tab and the shape of the NPV trajectory
charts (cumulative value rising, sometimes negative in early years).

Inputs
------
Statistics_Chronic_Metric.csv
    columns: Policy, SLR, Hazard, Metric, Year, Mean, Std, CoV
    Policy in {Baseline, Protect, Realign}; Hazard in {Erosion, Flooding};
    only Metric == "EconomicLoss" rows are used here (Eroded, Damaged,
    PopulationImpacted are the physical/social metrics, handled
    elsewhere).
Statistics_Chronic_CumulativeCost.csv
    columns: ProactivePolicy, SLR, Year, Mean, Std, CoV
    ProactivePolicy in {Protect, Realign}.

This module assumes both input CSVs hold ONE simulation's values
(currently the across-simulation mean; later, per-simulation raw values
in the same column layout). Nothing here aggregates across simulations,
call run_chronic_analysis() once per replicate and summarize the
resulting NPV values across replicates one level up.
"""

from __future__ import annotations

# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()
import os
import pandas as pd
from econ_common import load_assumptions, present_value, DEFAULT_PIECEWISE

SLR_SCENARIOS = ["High", "Med", "Low"]
POLICIES = ["Protect", "Realign"]
DEFAULT_ASSUMPTIONS_CSV = os.path.join(os.path.dirname(__file__), "assumptions.csv")


def _annual_damage_pv(
    df: pd.DataFrame,
    policy: str,
    slr: str,
    assumptions: dict,
    rate_override: float | None,
    piecewise: bool,
    value_column: str = "Mean",
) -> pd.Series:
    """
    Present value of total (Erosion + Flooding) economic loss for one
    policy x SLR scenario, one value per simulation year.

    Matches the "Net Present Value[s] of Erosion/Flooding Damages" rows
    and their sum ("NPV of Total Damages") in the Chronic Damages
    Baseline/Policy tabs: each year's mean raw dollar loss is discounted
    to present value individually (not cumulatively), then Erosion and
    Flooding are summed.

    Parameters
    ----------
    df : pd.DataFrame
        Statistics_Chronic_Metric.csv, filtered to Metric == "EconomicLoss".
    policy : str
        "Baseline", "Protect", or "Realign".
    slr : str
        "High", "Med", or "Low".
    assumptions : dict
        Output of load_assumptions().
    rate_override, piecewise :
        Passed through to present_value().

    Returns
    -------
    pd.Series
        Indexed by Year, present-value total damage for that year.
    """
    sub = df[(df["Policy"] == policy) & (df["SLR"] == slr)]

    total_pv = None
    for hazard in ["Erosion", "Flooding"]:
        hz = sub[sub["Hazard"] == hazard].set_index("Year")[value_column].sort_index()
        pv = pd.Series(
            {year: present_value(val, int(year), assumptions, rate_override=rate_override, piecewise=piecewise)
             for year, val in hz.items()}
        )
        total_pv = pv if total_pv is None else total_pv.add(pv, fill_value=0.0)

    return total_pv.sort_index()


def _annual_expenditure_pv(
    df: pd.DataFrame,
    policy: str,
    slr: str,
    assumptions: dict,
    rate_override: float | None,
    piecewise: bool,
    value_column: str = "Mean",
) -> pd.Series:
    """
    Present value of year-over-year incremental adaptation expenditure
    for one policy x SLR scenario, one value per simulation year.

    Matches the Chronic Expenditures tab rows 17/20/21: the input Mean
    column is a running CUMULATIVE cost-to-date, which must first be
    differenced year-over-year to get each year's actual incremental
    spend (row 20, "Annual Real Expenditures" = this year's cumulative
    minus last year's), and only that incremental figure is discounted
    (row 21). Discounting the raw cumulative figure directly (skipping
    the differencing step) roughly doubles the apparent cost in early
    years and compounds into a much larger error in later years, since
    the annual_net_benefit series in run_chronic_analysis() is itself
    cumulatively summed over time.

    Parameters
    ----------
    df : pd.DataFrame
        Statistics_Chronic_CumulativeCost.csv.
    policy : str
        "Protect" or "Realign".
    slr : str
        "High", "Med", or "Low".
    assumptions, rate_override, piecewise :
        See _annual_damage_pv().

    Returns
    -------
    pd.Series
        Indexed by Year, present-value INCREMENTAL expenditure for that
        year (not cumulative).
    """
    cumulative = df[(df["ProactivePolicy"] == policy) & (df["SLR"] == slr)].set_index("Year")[value_column].sort_index()
    incremental = cumulative.diff().fillna(cumulative.iloc[0])  # first year's incremental = its own cumulative value (prior year assumed 0)

    pv = pd.Series(
        {year: present_value(val, int(year), assumptions, rate_override=rate_override, piecewise=piecewise)
         for year, val in incremental.items()}
    )
    return pv.sort_index()


def run_chronic_analysis(
    damages_baseline_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Statistics_Chronic_Metric.csv",
    damages_policy_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Statistics_Chronic_Metric.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Statistics_Chronic_CumulativeCost.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
    value_column: str = "Mean",
) -> pd.DataFrame:
    """
    Run the full Chronic (Sec 3.2) economic analysis for a single
    simulation replicate, all policies (Protect, Realign) and all SLR
    scenarios (High, Med, Low).

    Note: damages_baseline_csv and damages_policy_csv are the same file
    (Statistics_Chronic_Metric.csv contains both Baseline and Protect/
    Realign rows, unlike the Excel workbook which splits these into two
    tabs); both parameters are kept so the file split can be reintroduced
    later without changing the function signature.

    Parameters
    ----------
    damages_baseline_csv, damages_policy_csv : str
        Path(s) to Statistics_Chronic_Metric.csv.
    expenditures_csv : str
        Path to Statistics_Chronic_CumulativeCost.csv.
    assumptions_csv : str
        Path to assumptions.csv.
    rate_override, piecewise :
        Passed through to present_value(). Used by the sensitivity
        analysis to re-run with alternate discount rates.

    Returns
    -------
    pd.DataFrame
        One row per (policy, SLR, year), columns:
        pv_baseline_damage, pv_policy_damage, pv_expenditure,
        annual_net_benefit, cumulative_npv
        cumulative_npv is the running sum of annual_net_benefit from
        the first simulation year through that row's year, matching the
        workbook's "NPV for Policy" trajectory and Steve's NPV charts.
    """
    assumptions = assumptions_csv if isinstance(assumptions_csv, dict) else load_assumptions(assumptions_csv)

    damages_raw = damages_baseline_csv if isinstance(damages_baseline_csv, pd.DataFrame) else pd.read_csv(damages_baseline_csv)
    damages = damages_raw[damages_raw["Metric"] == "EconomicLoss"]
    expenditures = expenditures_csv if isinstance(expenditures_csv, pd.DataFrame) else pd.read_csv(expenditures_csv)

    all_records = []
    for policy in POLICIES:
        for slr in SLR_SCENARIOS:
            baseline_pv = _annual_damage_pv(damages, "Baseline", slr, assumptions, rate_override, piecewise, value_column)
            policy_pv = _annual_damage_pv(damages, policy, slr, assumptions, rate_override, piecewise, value_column)
            expenditure_pv = _annual_expenditure_pv(expenditures, policy, slr, assumptions, rate_override, piecewise, value_column)

            years = sorted(set(baseline_pv.index) & set(policy_pv.index) & set(expenditure_pv.index))
            annual_net_benefit = pd.Series(
                {y: (baseline_pv[y] - policy_pv[y]) - expenditure_pv[y] for y in years}
            ).sort_index()
            cumulative_npv = annual_net_benefit.cumsum()

            for y in years:
                all_records.append({
                    "policy": policy,
                    "slr": slr,
                    "year": y,
                    "pv_baseline_damage": baseline_pv[y],
                    "pv_policy_damage": policy_pv[y],
                    "pv_expenditure": expenditure_pv[y],
                    "annual_net_benefit": annual_net_benefit[y],
                    "cumulative_npv": cumulative_npv[y],
                })

    return pd.DataFrame(all_records)


def _annual_damage_pv_single_hazard(
    df: pd.DataFrame,
    policy: str,
    slr: str,
    hazard: str,
    assumptions: dict,
    rate_override: float | None,
    piecewise: bool,
    value_column: str = "Mean",
) -> pd.Series:
    """
    Present value of economic loss for one policy x SLR x SINGLE hazard
    (Erosion or Flooding alone, not summed), one value per year.

    Same discounting logic as _annual_damage_pv(), but for a single
    hazard rather than the Erosion+Flooding total. Matches the
    standalone "NPV Erosion Damage" or "NPV Flooding Damage" row for a
    given policy/SLR block (not the "NPV of Total Damages" row).

    Parameters
    ----------
    df : pd.DataFrame
        Statistics_Chronic_Metric.csv, filtered to Metric == "EconomicLoss".
    policy : str
        "Baseline", "Protect", or "Realign".
    slr : str
        "High", "Med", or "Low".
    hazard : str
        "Erosion" or "Flooding".
    assumptions, rate_override, piecewise :
        See _annual_damage_pv().

    Returns
    -------
    pd.Series
        Indexed by Year, present-value damage for that single hazard.
    """
    sub = df[(df["Policy"] == policy) & (df["SLR"] == slr) & (df["Hazard"] == hazard)]
    hz = sub.set_index("Year")[value_column].sort_index()
    return pd.Series(
        {int(year): present_value(val, int(year), assumptions, rate_override=rate_override, piecewise=piecewise)
         for year, val in hz.items()}
    ).sort_index()


def _simulation_columns(df: pd.DataFrame) -> list[str]:
    columns = [column for column in df.columns if column.startswith("Sim_")]
    if not columns:
        raise ValueError("Input CSV must contain at least one Sim_* column")
    return columns


def _summarize_simulation_rows(
    rows_by_simulation: dict[str, pd.DataFrame],
    key_columns: list[str],
    simulation_columns: list[str],
) -> pd.DataFrame:
    merged = None
    for simulation_column, rows in rows_by_simulation.items():
        values = rows[key_columns + ["Value"]].rename(columns={"Value": simulation_column})
        merged = values if merged is None else merged.merge(values, on=key_columns, how="outer", validate="one_to_one")

    raw_values = merged[simulation_columns]
    mean = raw_values.mean(axis=1)
    std = raw_values.std(axis=1, ddof=1)
    output = merged[key_columns].copy()
    output[[f"{column} (M$)" for column in simulation_columns]] = raw_values.to_numpy()
    output["Mean (M$)"] = mean
    output["Std (M$)"] = std
    output["CoV"] = std.where(mean != 0, pd.NA) / mean.where(mean != 0, pd.NA) / (len(simulation_columns) ** 0.5)
    return output


def _single_simulation_exports(
    damages: pd.DataFrame,
    expenditures: pd.DataFrame,
    simulation_column: str,
    assumptions: dict,
    rate_override: float | None,
    piecewise: bool,
) -> dict[str, pd.DataFrame]:
    baseline_rows = []
    for slr in SLR_SCENARIOS:
        for hazard in ["Erosion", "Flooding"]:
            pv = _annual_damage_pv_single_hazard(damages, "Baseline", slr, hazard, assumptions, rate_override, piecewise, simulation_column)
            for year, value in pv.items():
                if 2021 <= year <= 2100:
                    baseline_rows.append(["Baseline", slr, hazard, "Economic_Loss", year, value])

    proactive_rows = []
    for policy in POLICIES:
        for slr in SLR_SCENARIOS:
            for hazard in ["Erosion", "Flooding"]:
                baseline_pv = _annual_damage_pv_single_hazard(damages, "Baseline", slr, hazard, assumptions, rate_override, piecewise, simulation_column)
                policy_pv = _annual_damage_pv_single_hazard(damages, policy, slr, hazard, assumptions, rate_override, piecewise, simulation_column)
                for year in sorted(set(baseline_pv.index) & set(policy_pv.index)):
                    if 2021 <= year <= 2100:
                        proactive_rows.append([policy, slr, hazard, "Economic_Loss_Reduction", year, baseline_pv[year] - policy_pv[year]])

    cost_rows = []
    for policy in POLICIES:
        for slr in SLR_SCENARIOS:
            annual_pv = _annual_expenditure_pv(expenditures, policy, slr, assumptions, rate_override, piecewise, simulation_column)
            for year, value in annual_pv.sort_index().cumsum().items():
                if 2021 <= year <= 2100:
                    cost_rows.append([policy, slr, "Chronic", "Cost_Cumulatively_Increased", year, value])

    npv_result = run_chronic_analysis(
        damages_baseline_csv=damages,
        damages_policy_csv=damages,
        expenditures_csv=expenditures,
        assumptions_csv=assumptions,
        rate_override=rate_override,
        piecewise=piecewise,
        value_column=simulation_column,
    )
    npv_result = npv_result[(npv_result["year"] >= 2021) & (npv_result["year"] <= 2100)]
    npv_rows = npv_result[["policy", "slr", "year", "cumulative_npv"]].rename(
        columns={"policy": "ProactivePolicy", "slr": "SLR", "year": "Year", "cumulative_npv": "Value"}
    )
    npv_rows["Hazard"] = "Chronic"
    npv_rows["Metric"] = "Net_Present_Value"

    return {
        "baseline": pd.DataFrame(baseline_rows, columns=["Policy", "SLR", "Hazard", "Metric", "Year", "Value"]),
        "proactive": pd.DataFrame(proactive_rows, columns=["ProactivePolicy", "SLR", "Hazard", "Metric", "Year", "Value"]),
        "cumulativecost": pd.DataFrame(cost_rows, columns=["ProactivePolicy", "SLR", "Hazard", "Metric", "Year", "Value"]),
        "npv": npv_rows[["ProactivePolicy", "SLR", "Hazard", "Metric", "Year", "Value"]],
    }


def _export_per_simulation_csv(
    output_csv: str,
    export_name: str,
    damages_csv: str,
    expenditures_csv: str,
    assumptions_csv: str,
    rate_override: float | None,
    piecewise: bool,
) -> pd.DataFrame:
    assumptions = load_assumptions(assumptions_csv)
    damages = pd.read_csv(damages_csv)
    expenditures = pd.read_csv(expenditures_csv)
    damages = damages[damages["Metric"] == "EconomicLoss"]
    simulation_columns = _simulation_columns(damages)
    expenditure_simulation_columns = _simulation_columns(expenditures)
    if simulation_columns != expenditure_simulation_columns:
        raise ValueError("Metric and cumulative-cost inputs must have the same Sim_* columns")

    rows_by_simulation = {column: {} for column in simulation_columns}
    for column in simulation_columns:
        rows_by_simulation[column] = _single_simulation_exports(
            damages, expenditures, column, assumptions, rate_override, piecewise
        )[export_name]

    key_columns = {
        "baseline": ["Policy", "SLR", "Hazard", "Metric", "Year"],
        "proactive": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
        "cumulativecost": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
        "npv": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
    }[export_name]
    out = _summarize_simulation_rows(rows_by_simulation, key_columns, simulation_columns)
    out.to_csv(output_csv, index=False)
    return out


def export_all_per_simulation_csv(
    output_dir: str = f"{REPO_ROOT}/Results/EconomicAnalysis",
    damages_csv: str = f"{REPO_ROOT}/Results/Sensitivity/Statistics_Chronic_Corner2_Metric_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Sensitivity/Statistics_Chronic_Corner2_CumulativeCost_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> dict[str, pd.DataFrame]:
    """Calculate all four outputs in one pass over the simulations."""
    assumptions = load_assumptions(assumptions_csv)
    damages = pd.read_csv(damages_csv)
    expenditures = pd.read_csv(expenditures_csv)
    damages = damages[damages["Metric"] == "EconomicLoss"]
    simulation_columns = _simulation_columns(damages)
    if simulation_columns != _simulation_columns(expenditures):
        raise ValueError("Metric and cumulative-cost inputs must have the same Sim_* columns")

    rows_by_export = {name: {} for name in ["baseline", "proactive", "cumulativecost", "npv"]}
    for simulation_column in simulation_columns:
        simulation_exports = _single_simulation_exports(
            damages, expenditures, simulation_column, assumptions, rate_override, piecewise
        )
        for name in rows_by_export:
            rows_by_export[name][simulation_column] = simulation_exports[name]

    key_columns = {
        "baseline": ["Policy", "SLR", "Hazard", "Metric", "Year"],
        "proactive": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
        "cumulativecost": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
        "npv": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
    }
    output_names = {
        "baseline": "Results_Chronic_Corner2_Economics_Baseline_PerSim.csv",
        "proactive": "Results_Chronic_Corner2_Economics_Proactive_PerSim.csv",
        "cumulativecost": "Results_Chronic_Corner2_Economics_CumulativeCost_PerSim.csv",
        "npv": "Results_Chronic_Corner2_Economics_NPV_PerSim.csv",
    }
    os.makedirs(output_dir, exist_ok=True)
    outputs = {}
    for name, rows in rows_by_export.items():
        output = _summarize_simulation_rows(rows, key_columns[name], simulation_columns)
        output.to_csv(os.path.join(output_dir, output_names[name]), index=False)
        outputs[name] = output
    return outputs


def export_baseline_csv(
    output_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Results_Chronic_Corner2_Economics_Baseline_PerSim.csv",
    damages_csv: str = f"{REPO_ROOT}/Results/Chronic/Statistics_Chronic_Metric_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Chronic/Statistics_Chronic_CumulativeCost_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> pd.DataFrame:
    return _export_per_simulation_csv(output_csv, "baseline", damages_csv, expenditures_csv, assumptions_csv, rate_override, piecewise)


def export_proactive_csv(
    output_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Results_Chronic_Corner2_Economics_Proactive_PerSim.csv",
    damages_csv: str = f"{REPO_ROOT}/Results/Chronic/Statistics_Chronic_Metric_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Chronic/Statistics_Chronic_CumulativeCost_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> pd.DataFrame:
    return _export_per_simulation_csv(output_csv, "proactive", damages_csv, expenditures_csv, assumptions_csv, rate_override, piecewise)


def export_cumulativecost_csv(
    output_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Results_Chronic_Corner2_Economics_CumulativeCost_PerSim.csv",
    damages_csv: str = f"{REPO_ROOT}/Results/Chronic/Statistics_Chronic_Metric_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Chronic/Statistics_Chronic_CumulativeCost_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> pd.DataFrame:
    return _export_per_simulation_csv(output_csv, "cumulativecost", damages_csv, expenditures_csv, assumptions_csv, rate_override, piecewise)


def export_npv_csv(
    output_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Results_Chronic_Corner2_Economics_NPV_PerSim.csv",
    damages_csv: str = f"{REPO_ROOT}/Results/Chronic/Statistics_Chronic_Metric_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Chronic/Statistics_Chronic_CumulativeCost_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> pd.DataFrame:
    return _export_per_simulation_csv(output_csv, "npv", damages_csv, expenditures_csv, assumptions_csv, rate_override, piecewise)


if __name__ == "__main__":
    print("Exporting 4 detailed CSVs in one simulation pass...")
    export_all_per_simulation_csv()
    print("Done.")
