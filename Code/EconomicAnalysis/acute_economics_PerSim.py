"""
acute_economics_PerSim.py
========================
Replicates the "Acute (Sec 3.1)" tab of EnvisionEconomics_final.xlsx for
multiple simulation replicates.

The detailed calculation computes present-value life-safety benefits,
present-value building-damage benefits, present-value investment cost,
Net Present Value (NPV), and Benefit-Cost Ratio (BCR) for the Protect and
Realign strategies relative to Baseline, for an acute earthquake+tsunami
event in the specified event year.

Input:
    Results_Acute/Results_report_Acute_PerSim.csv

The input contains the identifying columns
    Category, Policy, Hazard, Metric
and one repeated group of columns for each simulation, for example:
    Percentage_Change_Iter0, Baseline_Value_Iter0,
    Policy_Value_Iter0, Absolute_Change_Iter0

`run_acute_analysis_detailed()` calculates one simulation at a time using
the selected `*_IterN` columns. `run_acute_analysis_per_sim()` calculates
all simulations and returns the detailed results in million dollars with
columns `Iter_0 (M$)`, `Iter_1 (M$)`, ..., `Mean (M$)`, `Std (M$)`, and
`CoV`. `Std` is the sample standard deviation and `CoV` is calculated as
`Std / Mean / sqrt(n)`.

When run as a script, the results are saved to:
    Results_EconomicAnalysis/Results_Acute_Economics_PerSim.csv
"""

# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()

import math
import re
from pathlib import Path
from typing import Optional
import pandas as pd
from econ_common import (
    load_assumptions,
    load_income_growth_lookup,
    present_value,
    vsl_at_year,
    vsl_injury,
    DEFAULT_PIECEWISE,
)


def _parse_value(x) -> float:
    """
    Coerce a Results_report_Acute.csv value cell to float.

    Life Safety and Damage States rows hold plain numbers (e.g. "51.8").
    Economic Loss rows hold dollar-formatted strings (e.g. "$212.9M"),
    which forces pandas to read the whole Baseline_Value/Policy_Value
    column as text. This function handles both: plain numeric strings
    pass through via float(); "$X.XM" strings are stripped of "$" and
    "M" and multiplied by 1e6 to return raw USD.

    Parameters
    ----------
    x : str or float
        A single cell value from Baseline_Value or Policy_Value.

    Returns
    -------
    float
        Parsed numeric value (raw USD for dollar-formatted cells, the
        plain number otherwise).
    """
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    match = re.match(r"^\$?([\d,.]+)\s*([MK]?)$", s)
    if not match:
        raise ValueError(f"Could not parse value cell: {x!r}")
    number = float(match.group(1).replace(",", ""))
    suffix = match.group(2)
    if suffix == "M":
        number *= 1_000_000
    elif suffix == "K":
        number *= 1_000
    return number


def _life_safety_benefit(
    df: pd.DataFrame,
    policy: str,
    hazard: str,
    vsl_fatality: float,
    vsl_inj: float,
) -> float:
    """
    Present-value life-safety benefit for one policy and one hazard
    (EQ or TSU), summing fatality and injury components.

    Matches Acute (Sec 3.1) rows 22-39: for each of Fatality and Injury,
    benefit = (Baseline_Value - Policy_Value) * VSL, then the two are
    summed. This is algebraically identical to the workbook's
    "Baseline_Monetized - Policy_Monetized" columns (H-I), since VSL is
    constant across baseline and policy within a single event year.

    Parameters
    ----------
    df : pd.DataFrame
        Results_report_Acute.csv, filtered to Category == "Life Safety".
    policy : str
        "Protect" or "Realign".
    hazard : str
        "EQ" or "TSU".
    vsl_fatality, vsl_inj : float
        Present-value VSL for a fatality and for a (Serious) injury,
        from vsl_at_year() / vsl_injury().

    Returns
    -------
    float
        Present-value life-safety benefit (avoided monetized loss), USD.
    """
    sub = df[(df["Policy"] == policy) & (df["Hazard"] == hazard)]

    fat_row = sub[sub["Metric"] == "Fatality"].iloc[0]
    inj_row = sub[sub["Metric"] == "Injury"].iloc[0]

    fatality_benefit = (fat_row["Baseline_Value"] - fat_row["Policy_Value"]) * vsl_fatality
    injury_benefit = (inj_row["Baseline_Value"] - inj_row["Policy_Value"]) * vsl_inj

    return fatality_benefit + injury_benefit


def _building_damage_benefit(
    df: pd.DataFrame,
    policy: str,
    hazard: str,
    event_year: int,
    assumptions: dict,
    rate_override: Optional[float],
    piecewise: bool,
) -> float:
    """
    Present-value building-damage benefit for one policy and one hazard.

    Matches Acute (Sec 3.1) rows 43-48: baseline and policy raw dollar
    losses are each discounted to present value (as if the loss occurs
    entirely in event_year), then differenced.

    Parameters
    ----------
    df : pd.DataFrame
        Results_report_Acute.csv, filtered to Category == "Economic Loss".
    policy : str
        "Protect" or "Realign".
    hazard : str
        "EQ" or "TSU".
    event_year : int
        Year the acute event occurs (e.g., 2070).
    assumptions : dict
        Output of load_assumptions().
    rate_override, piecewise :
        Passed through to present_value().

    Returns
    -------
    float
        Present-value avoided building damage, USD.
    """
    sub = df[(df["Policy"] == policy) & (df["Hazard"] == hazard) & (df["Metric"].isin(["Economic_Loss", "Economic_Loss_Abs"]))]
    row = sub.iloc[0]

    baseline_pv = present_value(row["Baseline_Value"], event_year, assumptions, rate_override=rate_override, piecewise=piecewise)
    policy_pv = present_value(row["Policy_Value"], event_year, assumptions, rate_override=rate_override, piecewise=piecewise)

    return baseline_pv - policy_pv


def _investment_cost_pv(
    event_year: int,
    assumptions: dict,
    rate_override: Optional[float],
    piecewise: bool,
) -> float:
    """
    Present value of the annual adaptation budget, matching the
    workbook's SUM(B64:B112) exactly.

    The workbook's investment-cost rows have a confirmed one-year
    offset between each row's LABEL and what its FORMULA actually
    computes: the row labeled `label_year` uses exponent
    `(label_year - 1) - base_year` rather than `label_year - base_year`.
    Combined with the SUM range starting at the row labeled base_year+2
    (skipping a broken row for base_year+1), the workbook's total
    investment cost is the sum of `budget / (1+rate)^k` for
    k = 1 .. (event_year - base_year - 1), i.e. 49 terms for a 2070
    event year with base_year 2020, NOT 50 terms as a literal "$5M a
    year from 2021 through 2070" description would suggest.

    This function replicates the workbook's actual computed total
    exactly (validated to 8 significant figures against the workbook's
    cached B10 value), per direction to match Excel rather than a
    theoretically "corrected" 50-year version.

    Parameters
    ----------
    event_year : int
        The acute event year (e.g., 2070).
    assumptions : dict
        Output of load_assumptions(). Must contain "annual_budget_usd"
        and "base_year".
    rate_override, piecewise :
        Passed through to present_value(), applied per-term below.

    Returns
    -------
    float
        Present value of cumulative investment cost, USD, matching the
        workbook's SUM(B64:B112) exactly.
    """
    base_year = int(assumptions["base_year"])
    budget = assumptions["annual_budget_usd"]

    n_terms = event_year - base_year - 1
    total = 0.0
    for k in range(1, n_terms + 1):
        # present_value() expects a target year; construct one that
        # yields exactly exponent k via base_year + k, since the
        # workbook's rate-bracket logic in discount_factor() depends on
        # the actual year for piecewise mode.
        total += present_value(budget, base_year + k, assumptions, rate_override=rate_override, piecewise=piecewise)
    return total


def run_acute_analysis(
    results_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Results_report_Acute.csv",
    assumptions_csv: str = "assumptions.csv",
    income_growth_csv: str = "income_growth_lookup.csv",
    event_year: int = 2070,
    growth_series: str = "income_index_oecd",
    elasticity_override: Optional[float] = None,
    rate_override: Optional[float] = None,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> pd.DataFrame:
    """
    Run the full Acute (Sec 3.1) economic analysis for a single simulation
    replicate and both policies (Protect, Realign).

    Parameters
    ----------
    results_csv : str
        Path to Results_report_Acute.csv (one simulation's raw values).
    assumptions_csv, income_growth_csv : str
        Paths to the assumptions and income-growth lookup tables.
    event_year : int
        Year the acute earthquake+tsunami event occurs. Default 2070,
        matching the paper's primary analysis.
    growth_series : str
        "income_index_oecd" (default) or "income_index_fred", passed to
        vsl_at_year(). Used by the sensitivity analysis.
    elasticity_override, rate_override, piecewise :
        Passed through to vsl_at_year() / present_value(). Used by the
        sensitivity analysis to re-run with alternate assumptions.

    Returns
    -------
    pd.DataFrame
        One row per policy (Protect, Realign), columns:
        pv_life_safety_benefit, pv_building_damage_benefit,
        pv_investment_cost, npv, bcr
        (each PV benefit component summed across EQ and TSU hazards).
    """
    assumptions = load_assumptions(assumptions_csv)
    income_growth = load_income_growth_lookup(income_growth_csv)
    df = pd.read_csv(results_csv)
    df["Baseline_Value"] = df["Baseline_Value"].apply(_parse_value)
    df["Policy_Value"] = df["Policy_Value"].apply(_parse_value)

    life_safety_df = df[df["Category"] == "Life Safety"]
    econ_loss_df = df[df["Category"] == "Economic Loss"]

    vsl_fatality = vsl_at_year(
        event_year, assumptions, income_growth,
        growth_series=growth_series,
        elasticity_override=elasticity_override,
        rate_override=rate_override,
        piecewise=piecewise,
    )
    vsl_inj = vsl_injury(vsl_fatality, assumptions)

    records = []
    for policy in ["Protect", "Realign"]:
        # EQ and TSU are not additive (correlated damage); use the CSV's
        # own "Cumulative" hazard row rather than summing EQ + TSU.
        life_safety_benefit = _life_safety_benefit(life_safety_df, policy, "Cumulative", vsl_fatality, vsl_inj)
        building_damage_benefit = _building_damage_benefit(
            econ_loss_df, policy, "Cumulative", event_year, assumptions, rate_override, piecewise
        )
        investment_cost_pv = _investment_cost_pv(event_year, assumptions, rate_override, piecewise)

        total_benefit = life_safety_benefit + building_damage_benefit
        npv = total_benefit - investment_cost_pv
        bcr = total_benefit / investment_cost_pv if investment_cost_pv != 0 else float("nan")

        records.append({
            "policy": policy,
            "event_year": event_year,
            "pv_life_safety_benefit": life_safety_benefit,
            "pv_building_damage_benefit": building_damage_benefit,
            "pv_investment_cost": investment_cost_pv,
            "npv": npv,
            "bcr": bcr,
        })

    return pd.DataFrame(records)


def _baseline_life_safety_pv(
    df: pd.DataFrame,
    hazard: str,
    vsl_fatality: float,
    vsl_inj: float,
) -> float:
    """
    Present-value monetized baseline life-safety loss for one hazard
    (EQ or TSU), using only the Baseline_Value column (no policy
    comparison).

    Matches Acute (Sec 3.1) rows 28-29, "Baseline Monetized Damages"
    (column H): baseline fatalities * VSL + baseline injuries * VSL_inj.
    This is the raw baseline loss, not a benefit/reduction.

    Parameters
    ----------
    df : pd.DataFrame
        Results_report_Acute.csv, filtered to Category == "Life Safety".
    hazard : str
        "EQ" or "TSU".
    vsl_fatality, vsl_inj : float
        Present-value VSL for a fatality and for a (Serious) injury.

    Returns
    -------
    float
        Present-value monetized baseline life-safety loss, USD.
    """
    sub = df[df["Hazard"] == hazard]
    fat_row = sub[sub["Metric"] == "Fatality"].iloc[0]
    inj_row = sub[sub["Metric"] == "Injury"].iloc[0]
    return fat_row["Baseline_Value"] * vsl_fatality + inj_row["Baseline_Value"] * vsl_inj


def run_acute_analysis_detailed(
    results_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Results_report_Acute.csv",
    assumptions_csv: str = "assumptions.csv",
    income_growth_csv: str = "income_growth_lookup.csv",
    event_year: int = 2070,
    growth_series: str = "income_index_oecd",
    elasticity_override: Optional[float] = None,
    rate_override: Optional[float] = None,
    piecewise: bool = DEFAULT_PIECEWISE,
    iteration: Optional[int] = None,
    results_df: Optional[pd.DataFrame] = None,
    assumptions: Optional[dict] = None,
    income_growth: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Run the Acute analysis and return every intermediate value broken
    out individually (per hazard, per policy), rather than the summary
    totals returned by run_acute_analysis().

    Matches the specific cell layout of Acute (Sec 3.1): baseline
    building damage and baseline monetized life safety per hazard
    (EQ, TSU, and their EQ_AND_TSU sum, rows 43-45 and 28-30), building
    damage avoided, life safety benefit, and combined benefit per policy
    and hazard (rows 53-58), and the shared investment cost and final
    NPV per policy (rows 6-18).

    Parameters
    ----------
    Same as run_acute_analysis().
    iteration : int or None
        If provided, read the matching ``*_IterN`` columns from a
        per-simulation input CSV as the single-simulation value columns.

    Returns
    -------
    pd.DataFrame
        Long-format table with columns: Category, Policy, Hazard,
        Metric, Value. One row per (Category, Policy, Hazard, Metric)
        combination, 27 rows total.
    """
    if assumptions is None:
        assumptions = load_assumptions(assumptions_csv)
    if income_growth is None:
        income_growth = load_income_growth_lookup(income_growth_csv)
    df = results_df if results_df is not None else pd.read_csv(results_csv)
    if iteration is not None:
        iteration_fields = {
            field: f"{field}_Iter{iteration}"
            for field in ["Baseline_Value", "Policy_Value"]
        }
        missing_fields = [
            iteration_field
            for iteration_field in iteration_fields.values()
            if iteration_field not in df.columns
        ]
        if missing_fields:
            raise ValueError(f"Missing required input columns: {', '.join(missing_fields)}")
        df[["Baseline_Value", "Policy_Value"]] = df[
            [iteration_fields["Baseline_Value"], iteration_fields["Policy_Value"]]
        ].to_numpy()
    df["Baseline_Value"] = df["Baseline_Value"].apply(_parse_value)
    df["Policy_Value"] = df["Policy_Value"].apply(_parse_value)

    life_safety_df = df[df["Category"] == "Life Safety"]
    econ_loss_df = df[df["Category"] == "Economic Loss"]

    vsl_fatality = vsl_at_year(
        event_year, assumptions, income_growth,
        growth_series=growth_series,
        elasticity_override=elasticity_override,
        rate_override=rate_override,
        piecewise=piecewise,
    )
    vsl_inj = vsl_injury(vsl_fatality, assumptions)

    rows = []

    # --- Baseline building damage (per hazard), Excel G43/G44/G45 ---
    baseline_bldg = {}
    for hazard in ["EQ", "TSU"]:
        sub = econ_loss_df[(econ_loss_df["Policy"] == "Protect") & (econ_loss_df["Hazard"] == hazard) & (econ_loss_df["Metric"].isin(["Economic_Loss", "Economic_Loss_Abs"]))]
        baseline_val = sub.iloc[0]["Baseline_Value"]
        pv = present_value(baseline_val, event_year, assumptions, rate_override=rate_override, piecewise=piecewise)
        baseline_bldg[hazard] = pv
        rows.append(["Building_Damage", "Baseline", hazard, "Economic_Loss", pv])
    # EQ and TSU damage are correlated, not additive; use the CSV's own
    # "Cumulative" hazard row for the combined value instead of EQ + TSU.
    cumulative_bldg_sub = econ_loss_df[(econ_loss_df["Policy"] == "Protect") & (econ_loss_df["Hazard"] == "Cumulative") & (econ_loss_df["Metric"].isin(["Economic_Loss", "Economic_Loss_Abs"]))]
    cumulative_bldg_val = present_value(cumulative_bldg_sub.iloc[0]["Baseline_Value"], event_year, assumptions, rate_override=rate_override, piecewise=piecewise)
    rows.append(["Building_Damage", "Baseline", "EQ_AND_TSU", "Economic_Loss", cumulative_bldg_val])

    # --- Baseline monetized life safety (per hazard), Excel H28/H29/H30 ---
    baseline_life = {}
    for hazard in ["EQ", "TSU"]:
        pv = _baseline_life_safety_pv(life_safety_df, hazard, vsl_fatality, vsl_inj)
        baseline_life[hazard] = pv
        rows.append(["Life_Safety", "Baseline", hazard, "Economic_Loss", pv])
    rows.append(["Life_Safety", "Baseline", "EQ_AND_TSU", "Economic_Loss",
                 _baseline_life_safety_pv(life_safety_df, "Cumulative", vsl_fatality, vsl_inj)])

    # --- Per-policy benefit rows (building, life safety, combined), Excel rows 53-58 ---
    for policy in ["Protect", "Realign"]:
        bldg = {}
        life = {}
        for hazard in ["EQ", "TSU", "Cumulative"]:
            bldg[hazard] = _building_damage_benefit(econ_loss_df, policy, hazard, event_year, assumptions, rate_override, piecewise)
            life[hazard] = _life_safety_benefit(life_safety_df, policy, hazard, vsl_fatality, vsl_inj)

        for hazard in ["EQ", "TSU"]:
            rows.append(["Building_Damage", policy, hazard, "Economic_Loss_Reduction", bldg[hazard]])
        rows.append(["Building_Damage", policy, "EQ_AND_TSU", "Economic_Loss_Reduction", bldg["Cumulative"]])

        for hazard in ["EQ", "TSU"]:
            rows.append(["Life_Safety", policy, hazard, "Economic_Loss_Reduction", life[hazard]])
        rows.append(["Life_Safety", policy, "EQ_AND_TSU", "Economic_Loss_Reduction", life["Cumulative"]])

        for hazard in ["EQ", "TSU"]:
            rows.append(["Building_AND_Life", policy, hazard, "Economic_Loss_Reduction", bldg[hazard] + life[hazard]])
        rows.append(["Building_AND_Life", policy, "EQ_AND_TSU", "Economic_Loss_Reduction",
                     bldg["Cumulative"] + life["Cumulative"]])

    # --- Investment cost and NPV (shared cost, per-policy NPV), Excel rows 10/11/17/18 ---
    investment_cost_pv = _investment_cost_pv(event_year, assumptions, rate_override, piecewise)
    for policy in ["Protect", "Realign"]:
        bldg_total = _building_damage_benefit(econ_loss_df, policy, "Cumulative", event_year, assumptions, rate_override, piecewise)
        life_total = _life_safety_benefit(life_safety_df, policy, "Cumulative", vsl_fatality, vsl_inj)
        npv = (bldg_total + life_total) - investment_cost_pv
        rows.append(["Building_AND_Life", policy, "EQ_AND_TSU", "Cost_Cumulatively_Increased", investment_cost_pv])
        rows.append(["Building_AND_Life", policy, "EQ_AND_TSU", "Net_Present_Value", npv])

    return pd.DataFrame(rows, columns=["Category", "Policy", "Hazard", "Metric", "Value"])


def run_acute_analysis_per_sim(
    results_csv: str = str(Path(__file__).resolve().parents[2] / "Results" / "Acute" / "Results_report_Acute_PerSim.csv"),
    assumptions_csv: str = "assumptions.csv",
    income_growth_csv: str = "income_growth_lookup.csv",
    event_year: int = 2070,
    growth_series: str = "income_index_oecd",
    elasticity_override: Optional[float] = None,
    rate_override: Optional[float] = None,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> pd.DataFrame:
    """Run the detailed Acute analysis for every input simulation.

    The returned table keeps the detailed metric rows and contains one
    ``Iter_N`` column per simulation, followed by ``Mean``, sample ``Std``,
    and the requested ``CoV = Std / Mean / sqrt(n)``.
    """
    input_df = pd.read_csv(results_csv, nrows=0)
    iteration_numbers = []
    for column in input_df.columns:
        match = re.fullmatch(r"Baseline_Value_Iter(\d+)", column)
        if match:
            iteration_numbers.append(int(match.group(1)))
    iteration_numbers = sorted(iteration_numbers)
    if not iteration_numbers:
        raise ValueError("No Baseline_Value_IterN columns found in input CSV")

    results_df = pd.read_csv(results_csv)
    assumptions = load_assumptions(assumptions_csv)
    income_growth = load_income_growth_lookup(income_growth_csv)
    iteration_results = []
    for iteration in iteration_numbers:
        result = run_acute_analysis_detailed(
            results_csv=results_csv,
            assumptions_csv=assumptions_csv,
            income_growth_csv=income_growth_csv,
            event_year=event_year,
            growth_series=growth_series,
            elasticity_override=elasticity_override,
            rate_override=rate_override,
            piecewise=piecewise,
            iteration=iteration,
            results_df=results_df,
            assumptions=assumptions,
            income_growth=income_growth,
        )
        iteration_results.append(result["Value"] / 1_000_000)

    values = pd.concat(iteration_results, axis=1)
    values.columns = [f"Iter_{iteration} (M$)" for iteration in iteration_numbers]
    output = result[["Category", "Policy", "Hazard", "Metric"]].reset_index(drop=True)
    output[values.columns] = values.to_numpy()
    output["Mean (M$)"] = values.mean(axis=1)
    output["Std (M$)"] = values.std(axis=1, ddof=1)
    output["CoV"] = output["Std (M$)"] / output["Mean (M$)"] / math.sqrt(len(iteration_numbers))
    return output


if __name__ == "__main__":
    import os

    project_dir = Path(__file__).resolve().parents[2]
    input_csv = project_dir / "Results" / "Acute" / "Results_report_Acute_PerSim.csv"
    output_dir = project_dir / "Results" / "EconomicAnalysis"
    os.makedirs(output_dir, exist_ok=True)

    per_sim = run_acute_analysis_per_sim(results_csv=input_csv)
    print(per_sim.to_string(index=False))
    per_sim.to_csv(os.path.join(output_dir, "Results_Acute_Economics_PerSim.csv"), index=False)
