"""
combined_economics_PerSim.py
=============================
Replicates the three "Combined (3.3)" tabs of EnvisonEconomics_final.xlsx:
Damages Policy, Expenditures, and NetPresentValues, for multiple
simulation replicates.

Unlike Chronic, Combined is evaluated only at three snapshot years (2050,
2070, 2090, tied to the acute event timing), not cumulatively across every
simulation year. At each snapshot year, NPV is a direct point-in-time
comparison:

    NPV(year) = [Baseline total damage(year) - Policy total damage(year)]
                - cumulative expenditure(year)

where "total damage" combines a monetized Acute component (building
damage + life safety, discounted/escalated to that snapshot year exactly
as in acute_economics.py) and a Chronic component (Erosion + Flooding
building damage, discounted to that snapshot year, single-year values,
not summed across years the way chronic_economics.py's cumulative_npv
is).

Inputs
------
Statistics_Both_Metric_Annual_PerSim.csv
    columns: Policy, SLR, Hazard, Metric, Year, Sim_1, Sim_2, ...,
    Sim_n, Mean, Std, CoV
    Policy in {AC1 (baseline), AC3, AC3-A, AC3-C}
    Hazard in {Acute, Erosion, Flooding, AcuteAndFlooding}
    Metric in {Casualty, Damaged, EconomicLoss, Fatality, Injury, Eroded,
    PopulationImpacted}; this module uses EconomicLoss (Erosion,
    Flooding), and Fatality/Injury/EconomicLoss (Acute) at Year in
    {2050, 2070, 2090}.
Statistics_Both_CumulativeCost_Annual_PerSim.csv
    columns: ProactivePolicy, SLR, Year, Sim_1, Sim_2, ..., Sim_n, Mean,
    Std, CoV
    ProactivePolicy in {AC3, AC3-A, AC3-C}. Each Sim_* column is already
    a running cumulative cost from that simulation itself.

Each `Sim_*` column is treated as one independent simulation replicate:
the full analysis is run once per `Sim_*` column, and the resulting
per-simulation values are combined into a single output row per
(policy/hazard/metric/year) with columns `Sim_1 (M$)`, ..., `Sim_n (M$)`,
`Mean (M$)`, `Std (M$)`, and `CoV`. `Std` is the sample standard
deviation and `CoV` is `Std / Mean / sqrt(n)`, where `n` is the number
of `Sim_*` columns found in the input CSV.

When run as a script, the results are saved to:
    Results_EconomicAnalysis/Results_Combined_Economics_{Baseline,Proactive,CumulativeCost,NPV}_PerSim.csv
"""

from __future__ import annotations

# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()
import os
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import pandas as pd
from econ_common import (
    load_assumptions,
    load_income_growth_lookup,
    present_value,
    vsl_at_year,
    vsl_injury,
    DEFAULT_PIECEWISE,
)

SLR_SCENARIOS = ["High", "Med", "Low"]
POLICIES = ["AC3", "AC3-A", "AC3-C"]
BASELINE_POLICY = "AC1"
SNAPSHOT_YEARS = [2050, 2070, 2090]
DEFAULT_ASSUMPTIONS_CSV = os.path.join(os.path.dirname(__file__), "assumptions.csv")


def _acute_damage_pv(
    df: pd.DataFrame,
    policy: str,
    slr: str,
    year: int,
    assumptions: dict,
    income_growth: pd.DataFrame,
    growth_series: str,
    elasticity_override: float | None,
    rate_override: float | None,
    piecewise: bool,
    value_column: str = "Mean",
    vsl_pair: tuple[float, float] | None = None,
) -> float:
    """
    Present value of total acute damage (building damage + life safety)
    for one policy, SLR scenario, and snapshot year.

    Matches Combined Damages Policy rows "NPV Acute Building Damage" +
    "NPV Acute Life Safety" = "NPV Total Acute Damages".

    Fatality and Injury counts are monetized using VSL escalated and
    discounted to `year` (same mechanism as acute_economics.py);
    EconomicLoss (building damage, already in $M) is simply discounted
    to `year`.

    Parameters
    ----------
    df : pd.DataFrame
        Statistics_Both_Metric_Annual(_PerSim).csv, filtered to
        Hazard == "Acute".
    policy : str
        "AC1", "AC3", "AC3-A", or "AC3-C".
    slr : str
        "High", "Med", or "Low".
    year : int
        Snapshot year (2050, 2070, or 2090).
    assumptions, income_growth, growth_series, elasticity_override,
    rate_override, piecewise :
        See vsl_at_year() / present_value().
    value_column : str
        Which column to treat as each metric's value, e.g. "Mean" or a
        specific "Sim_N" simulation column.
    vsl_pair : tuple[float, float], optional
        Precomputed (vsl_fatality, vsl_injury) for `year`, to skip
        recomputing VSL when the caller already has it cached (VSL only
        depends on `year`, not on `policy`/`slr`).

    Returns
    -------
    float
        Present-value total acute damage (building damage + monetized
        life safety) at `year`, in $M 2020 USD.
    """
    sub = df[(df["Policy"] == policy) & (df["SLR"] == slr) & (df["Year"] == year)]

    fatalities = sub[sub["Metric"] == "Fatality"][value_column].iloc[0]
    injuries = sub[sub["Metric"] == "Injury"][value_column].iloc[0]
    building_loss = sub[sub["Metric"] == "EconomicLoss"][value_column].iloc[0]

    if vsl_pair is not None:
        vsl_fatality, vsl_inj = vsl_pair
    else:
        vsl_fatality = vsl_at_year(
            year, assumptions, income_growth,
            growth_series=growth_series,
            elasticity_override=elasticity_override,
            rate_override=rate_override,
            piecewise=piecewise,
        )
        vsl_inj = vsl_injury(vsl_fatality, assumptions)

    # Fatality/Injury counts are already the metric at `year`; VSL here
    # is per-person in $, while building_loss is in $M, so life-safety
    # value is converted to $M to match units before summing.
    life_safety_value_usd = fatalities * vsl_fatality + injuries * vsl_inj
    life_safety_value_millions = life_safety_value_usd / 1_000_000

    building_loss_pv = present_value(building_loss, year, assumptions, rate_override=rate_override, piecewise=piecewise)

    return life_safety_value_millions + building_loss_pv


def _chronic_damage_pv(
    df: pd.DataFrame,
    policy: str,
    slr: str,
    year: int,
    assumptions: dict,
    rate_override: float | None,
    piecewise: bool,
    value_column: str = "Mean",
) -> float:
    """
    Total chronic damage (Erosion + Flooding) for one policy, SLR
    scenario, and snapshot year, accumulated from the base year through
    `year`: each year's raw value is individually discounted to present
    value, and the discounted values are summed.

    Matches Combined Damages Policy rows "NPV Erosion Damage" + "NPV
    Flooding Damage" = "NPV Total Chronic Damages".

    Parameters
    ----------
    df : pd.DataFrame
        Statistics_Both_Metric_Annual(_PerSim).csv, filtered to Hazard
        in {"Erosion", "Flooding"}.
    policy : str
        "AC1" (baseline), "AC3", "AC3-A", or "AC3-C".
    slr : str
        "High", "Med", or "Low".
    year : int
        Snapshot year (2050, 2070, or 2090); all years from the earliest
        available year through this one are included.
    assumptions, rate_override, piecewise :
        Passed to present_value().
    value_column : str
        Which column to treat as each row's value, e.g. "Mean" or a
        specific "Sim_N" simulation column.

    Returns
    -------
    float
        Cumulative total chronic damage through `year`, in $M 2020 USD,
        each year's value individually discounted before summing.
    """
    sub = df[(df["Policy"] == policy) & (df["SLR"] == slr) & (df["Year"] <= year)]

    total = 0.0
    for hazard in ["Erosion", "Flooding"]:
        rows = sub[(sub["Hazard"] == hazard) & (sub["Metric"] == "EconomicLoss")]
        for _, row in rows.iterrows():
            total += present_value(row[value_column], int(row["Year"]), assumptions, rate_override=rate_override, piecewise=piecewise)
    return total


def _expenditure_pv(
    df: pd.DataFrame,
    policy: str,
    slr: str,
    year: int,
    assumptions: dict,
    rate_override: float | None,
    piecewise: bool,
    value_column: str = "Mean",
) -> float:
    """
    Present value of cumulative expenditure through a snapshot year.

    The input value column is a running CUMULATIVE cost, which must
    first be differenced year-over-year to get each year's incremental
    spend, each increment discounted individually, and the discounted
    increments summed from the base year through `year`. This is the
    same treatment as chronic_economics.py's _annual_expenditure_pv(),
    applied here across a cumulative range rather than returning a
    per-year series.

    Parameters
    ----------
    df : pd.DataFrame
        Statistics_Both_CumulativeCost_Annual(_PerSim).csv.
    policy : str
        "AC3", "AC3-A", or "AC3-C".
    slr : str
        "High", "Med", or "Low".
    year : int
        Snapshot year (2050, 2070, or 2090); all years from the earliest
        available year through this one are discounted and summed.
    assumptions, rate_override, piecewise :
        See present_value().
    value_column : str
        Which column holds the running cumulative cost, e.g. "Mean" or
        a specific "Sim_N" simulation column.

    Returns
    -------
    float
        Present-value cumulative expenditure through `year`, in $M 2020
        USD.
    """
    cumulative = df[(df["ProactivePolicy"] == policy) & (df["SLR"] == slr) & (df["Year"] <= year)].set_index("Year")[value_column].sort_index()
    incremental = cumulative.diff().fillna(cumulative.iloc[0])

    total_pv = sum(
        present_value(val, int(yr), assumptions, rate_override=rate_override, piecewise=piecewise)
        for yr, val in incremental.items()
    )
    return total_pv


def _chronic_cumulative_pv_series(
    df: pd.DataFrame,
    policy: str,
    slr: str,
    assumptions: dict,
    rate_override: float | None,
    piecewise: bool,
    value_column: str,
) -> pd.Series:
    """
    Running cumulative present value of chronic (Erosion + Flooding)
    damage for one policy x SLR, indexed by year, computed once instead
    of re-summing the whole year range for every snapshot year (as
    `_chronic_damage_pv` does when called per snapshot year).

    `_chronic_damage_pv(..., year)` is equivalent to this series' value
    at the largest index <= `year`.
    """
    sub = df[(df["Policy"] == policy) & (df["SLR"] == slr)]

    per_year_pv = None
    for hazard in ["Erosion", "Flooding"]:
        rows = sub[(sub["Hazard"] == hazard) & (sub["Metric"] == "EconomicLoss")].set_index("Year")[value_column].sort_index()
        pv = pd.Series(
            {int(year): present_value(val, int(year), assumptions, rate_override=rate_override, piecewise=piecewise)
             for year, val in rows.items()}
        )
        per_year_pv = pv if per_year_pv is None else per_year_pv.add(pv, fill_value=0.0)

    return per_year_pv.sort_index().cumsum()


def _expenditure_cumulative_pv_series(
    df: pd.DataFrame,
    policy: str,
    slr: str,
    assumptions: dict,
    rate_override: float | None,
    piecewise: bool,
    value_column: str,
) -> pd.Series:
    """
    Running cumulative present value of expenditure for one policy x
    SLR, indexed by year, computed once instead of re-summing the whole
    year range for every snapshot year (as `_expenditure_pv` does when
    called per snapshot year).

    `_expenditure_pv(..., year)` is equivalent to this series' value at
    the largest index <= `year`.
    """
    cumulative = df[(df["ProactivePolicy"] == policy) & (df["SLR"] == slr)].set_index("Year")[value_column].sort_index()
    incremental = cumulative.diff().fillna(cumulative.iloc[0])

    pv = pd.Series(
        {int(yr): present_value(val, int(yr), assumptions, rate_override=rate_override, piecewise=piecewise)
         for yr, val in incremental.items()}
    )
    return pv.sort_index().cumsum()


def _value_at_or_before(series: pd.Series, year: int) -> float:
    """Value of a cumulative series at the largest index <= year, or 0.0 if none."""
    eligible = series[series.index <= year]
    return float(eligible.iloc[-1]) if not eligible.empty else 0.0


def run_combined_analysis(
    damages_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_Metric_Annual_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_CumulativeCost_Annual_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    income_growth_csv: str = "income_growth_lookup.csv",
    growth_series: str = "income_index_oecd",
    elasticity_override: float | None = None,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
    value_column: str = "Mean",
) -> pd.DataFrame:
    """
    Run the full Combined (Sec 3.3) economic analysis for a single
    simulation replicate (or the across-simulation Mean), all policies
    (AC3, AC3-A, AC3-C), all SLR scenarios, and all three snapshot years
    (2050, 2070, 2090).

    Parameters
    ----------
    damages_csv : str or pd.DataFrame
        Path to (or already-loaded) Statistics_Both_Metric_Annual(_PerSim).csv.
    expenditures_csv : str or pd.DataFrame
        Path to (or already-loaded) Statistics_Both_CumulativeCost_Annual(_PerSim).csv.
    assumptions_csv, income_growth_csv : str
        Paths to the assumptions and income-growth lookup tables.
    growth_series, elasticity_override, rate_override, piecewise :
        Passed through to vsl_at_year() / present_value(). Used by the
        sensitivity analysis to re-run with alternate assumptions.
    value_column : str
        Which column to treat as each row's value, e.g. "Mean" or a
        specific "Sim_N" simulation column.

    Returns
    -------
    pd.DataFrame
        One row per (policy, SLR, year), columns:
        pv_baseline_damage, pv_policy_damage, pv_expenditure, npv,
        bcr (present-value total benefit / present-value expenditure).
    """
    assumptions = assumptions_csv if isinstance(assumptions_csv, dict) else load_assumptions(assumptions_csv)
    income_growth = load_income_growth_lookup(income_growth_csv)

    damages_raw = damages_csv if isinstance(damages_csv, pd.DataFrame) else pd.read_csv(damages_csv)
    expenditures = expenditures_csv if isinstance(expenditures_csv, pd.DataFrame) else pd.read_csv(expenditures_csv)

    acute_df = damages_raw[damages_raw["Hazard"] == "Acute"]
    chronic_df = damages_raw[damages_raw["Hazard"].isin(["Erosion", "Flooding"])]

    records = []
    for policy in POLICIES:
        for slr in SLR_SCENARIOS:
            for year in SNAPSHOT_YEARS:
                baseline_damage = (
                    _acute_damage_pv(acute_df, BASELINE_POLICY, slr, year, assumptions, income_growth,
                                      growth_series, elasticity_override, rate_override, piecewise, value_column)
                    + _chronic_damage_pv(chronic_df, BASELINE_POLICY, slr, year, assumptions, rate_override, piecewise, value_column)
                )
                policy_damage = (
                    _acute_damage_pv(acute_df, policy, slr, year, assumptions, income_growth,
                                      growth_series, elasticity_override, rate_override, piecewise, value_column)
                    + _chronic_damage_pv(chronic_df, policy, slr, year, assumptions, rate_override, piecewise, value_column)
                )
                expenditure_pv = _expenditure_pv(expenditures, policy, slr, year, assumptions, rate_override, piecewise, value_column)

                total_benefit = baseline_damage - policy_damage
                npv = total_benefit - expenditure_pv
                bcr = total_benefit / expenditure_pv if expenditure_pv != 0 else float("nan")

                records.append({
                    "policy": policy,
                    "slr": slr,
                    "year": year,
                    "pv_baseline_damage": baseline_damage,
                    "pv_policy_damage": policy_damage,
                    "pv_expenditure": expenditure_pv,
                    "npv": npv,
                    "bcr": bcr,
                })

    return pd.DataFrame(records)


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
    acute_df: pd.DataFrame,
    chronic_df: pd.DataFrame,
    expenditures: pd.DataFrame,
    simulation_column: str,
    assumptions: dict,
    income_growth: pd.DataFrame,
    growth_series: str,
    elasticity_override: float | None,
    rate_override: float | None,
    piecewise: bool,
) -> dict[str, pd.DataFrame]:
    """
    Compute all four Combined exports for a single simulation column.

    All quantities that are shared across baseline/proactive/npv (VSL
    per year, per-policy chronic damage, per-policy expenditure) are
    computed once and cached/reused, instead of being recomputed from
    scratch for every (policy, SLR, year) combination that needs them.
    """
    vsl_by_year = {}
    for year in SNAPSHOT_YEARS:
        vsl_fatality = vsl_at_year(year, assumptions, income_growth, growth_series=growth_series,
                                    elasticity_override=elasticity_override, rate_override=rate_override, piecewise=piecewise)
        vsl_by_year[year] = (vsl_fatality, vsl_injury(vsl_fatality, assumptions))

    all_policies = [BASELINE_POLICY] + POLICIES

    acute_cache: dict[tuple[str, str, int], float] = {}
    chronic_series_cache: dict[tuple[str, str], pd.Series] = {}
    expenditure_series_cache: dict[tuple[str, str], pd.Series] = {}

    def acute_pv(policy: str, slr: str, year: int) -> float:
        key = (policy, slr, year)
        if key not in acute_cache:
            acute_cache[key] = _acute_damage_pv(
                acute_df, policy, slr, year, assumptions, income_growth,
                growth_series, elasticity_override, rate_override, piecewise, simulation_column,
                vsl_pair=vsl_by_year[year],
            )
        return acute_cache[key]

    def chronic_pv(policy: str, slr: str, year: int) -> float:
        key = (policy, slr)
        if key not in chronic_series_cache:
            chronic_series_cache[key] = _chronic_cumulative_pv_series(
                chronic_df, policy, slr, assumptions, rate_override, piecewise, simulation_column
            )
        return _value_at_or_before(chronic_series_cache[key], year)

    def expenditure_pv(policy: str, slr: str, year: int) -> float:
        key = (policy, slr)
        if key not in expenditure_series_cache:
            expenditure_series_cache[key] = _expenditure_cumulative_pv_series(
                expenditures, policy, slr, assumptions, rate_override, piecewise, simulation_column
            )
        return _value_at_or_before(expenditure_series_cache[key], year)

    # Warm the caches for every policy/SLR/year combo up front (each
    # unique key is computed exactly once regardless of how many of
    # baseline/proactive/npv end up needing it).
    for policy in all_policies:
        for slr in SLR_SCENARIOS:
            for year in SNAPSHOT_YEARS:
                acute_pv(policy, slr, year)
                chronic_pv(policy, slr, year)
    for policy in POLICIES:
        for slr in SLR_SCENARIOS:
            for year in SNAPSHOT_YEARS:
                expenditure_pv(policy, slr, year)

    baseline_rows = []
    for slr in SLR_SCENARIOS:
        for year in SNAPSHOT_YEARS:
            acute = acute_pv(BASELINE_POLICY, slr, year)
            chronic = chronic_pv(BASELINE_POLICY, slr, year)
            baseline_rows.append(["Baseline", slr, "Acute", "Economic_Loss", year, acute])
            baseline_rows.append(["Baseline", slr, "Chronic", "Economic_Loss", year, chronic])
            baseline_rows.append(["Baseline", slr, "Both", "Economic_Loss", year, acute + chronic])

    proactive_rows = []
    npv_rows = []
    for policy in POLICIES:
        for slr in SLR_SCENARIOS:
            for year in SNAPSHOT_YEARS:
                base_acute = acute_pv(BASELINE_POLICY, slr, year)
                base_chronic = chronic_pv(BASELINE_POLICY, slr, year)
                pol_acute = acute_pv(policy, slr, year)
                pol_chronic = chronic_pv(policy, slr, year)

                acute_reduction = base_acute - pol_acute
                chronic_reduction = base_chronic - pol_chronic
                proactive_rows.append([policy, slr, "Acute", "Economic_Loss_Reduction", year, acute_reduction])
                proactive_rows.append([policy, slr, "Chronic", "Economic_Loss_Reduction", year, chronic_reduction])
                proactive_rows.append([policy, slr, "Both", "Economic_Loss_Reduction", year, acute_reduction + chronic_reduction])

                expenditure = expenditure_pv(policy, slr, year)
                npv = (acute_reduction + chronic_reduction) - expenditure
                npv_rows.append([policy, slr, "Both", "Net_Present_Value", year, npv])

    cost_rows = []
    for policy in POLICIES:
        for slr in SLR_SCENARIOS:
            for year in SNAPSHOT_YEARS:
                cost_rows.append([policy, slr, "Both", "Cost_Cumulatively_Increased", year, expenditure_pv(policy, slr, year)])

    return {
        "baseline": pd.DataFrame(baseline_rows, columns=["Policy", "SLR", "Hazard", "Metric", "Year", "Value"]),
        "proactive": pd.DataFrame(proactive_rows, columns=["ProactivePolicy", "SLR", "Hazard", "Metric", "Year", "Value"]),
        "cumulativecost": pd.DataFrame(cost_rows, columns=["ProactivePolicy", "SLR", "Hazard", "Metric", "Year", "Value"]),
        "npv": pd.DataFrame(npv_rows, columns=["ProactivePolicy", "SLR", "Hazard", "Metric", "Year", "Value"]),
    }


def _load_combined_inputs(damages_csv: str, expenditures_csv: str, assumptions_csv: str):
    assumptions = load_assumptions(assumptions_csv)
    income_growth = load_income_growth_lookup("income_growth_lookup.csv")
    damages_raw = pd.read_csv(damages_csv)
    expenditures = pd.read_csv(expenditures_csv)
    acute_df = damages_raw[damages_raw["Hazard"] == "Acute"]
    chronic_df = damages_raw[damages_raw["Hazard"].isin(["Erosion", "Flooding"])]

    simulation_columns = _simulation_columns(damages_raw)
    if simulation_columns != _simulation_columns(expenditures):
        raise ValueError("Metric and cumulative-cost inputs must have the same Sim_* columns")

    return assumptions, income_growth, acute_df, chronic_df, expenditures, simulation_columns


def _run_all_simulations(
    acute_df: pd.DataFrame,
    chronic_df: pd.DataFrame,
    expenditures: pd.DataFrame,
    simulation_columns: list[str],
    assumptions: dict,
    income_growth: pd.DataFrame,
    growth_series: str,
    elasticity_override: float | None,
    rate_override: float | None,
    piecewise: bool,
    max_workers: int | None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """
    Run `_single_simulation_exports` once per simulation column. Each
    column is fully independent, so this is done in parallel worker
    processes whenever there is more than one column to compute and
    more than one CPU available (set `max_workers=1` to force serial
    execution, e.g. for debugging).
    """
    worker = partial(
        _single_simulation_exports,
        acute_df, chronic_df, expenditures,
        assumptions=assumptions, income_growth=income_growth, growth_series=growth_series,
        elasticity_override=elasticity_override, rate_override=rate_override, piecewise=piecewise,
    )

    workers = max_workers if max_workers is not None else (os.cpu_count() or 1)
    workers = min(workers, len(simulation_columns))

    if workers <= 1:
        results = [worker(column) for column in simulation_columns]
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(worker, simulation_columns))

    exports_by_name: dict[str, dict[str, pd.DataFrame]] = {name: {} for name in ["baseline", "proactive", "cumulativecost", "npv"]}
    for column, simulation_exports in zip(simulation_columns, results):
        for name in exports_by_name:
            exports_by_name[name][column] = simulation_exports[name]
    return exports_by_name


def _export_per_simulation_csv(
    output_csv: str,
    export_name: str,
    damages_csv: str,
    expenditures_csv: str,
    assumptions_csv: str,
    growth_series: str,
    elasticity_override: float | None,
    rate_override: float | None,
    piecewise: bool,
    max_workers: int | None,
) -> pd.DataFrame:
    assumptions, income_growth, acute_df, chronic_df, expenditures, simulation_columns = _load_combined_inputs(
        damages_csv, expenditures_csv, assumptions_csv
    )

    rows_by_simulation = _run_all_simulations(
        acute_df, chronic_df, expenditures, simulation_columns, assumptions, income_growth,
        growth_series, elasticity_override, rate_override, piecewise, max_workers,
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
    damages_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_Metric_Annual_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_CumulativeCost_Annual_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    growth_series: str = "income_index_oecd",
    elasticity_override: float | None = None,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
    max_workers: int | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Calculate all four Combined outputs in one pass over the
    simulations. `max_workers` controls how many simulation columns are
    processed in parallel (defaults to the number of CPUs available);
    pass `max_workers=1` to run serially.
    """
    assumptions, income_growth, acute_df, chronic_df, expenditures, simulation_columns = _load_combined_inputs(
        damages_csv, expenditures_csv, assumptions_csv
    )

    rows_by_export = _run_all_simulations(
        acute_df, chronic_df, expenditures, simulation_columns, assumptions, income_growth,
        growth_series, elasticity_override, rate_override, piecewise, max_workers,
    )

    key_columns = {
        "baseline": ["Policy", "SLR", "Hazard", "Metric", "Year"],
        "proactive": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
        "cumulativecost": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
        "npv": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
    }
    output_names = {
        "baseline": "Results_Combined_Economics_Baseline_PerSim.csv",
        "proactive": "Results_Combined_Economics_Proactive_PerSim.csv",
        "cumulativecost": "Results_Combined_Economics_CumulativeCost_PerSim.csv",
        "npv": "Results_Combined_Economics_NPV_PerSim.csv",
    }
    os.makedirs(output_dir, exist_ok=True)
    outputs = {}
    for name, rows in rows_by_export.items():
        output = _summarize_simulation_rows(rows, key_columns[name], simulation_columns)
        output.to_csv(os.path.join(output_dir, output_names[name]), index=False)
        outputs[name] = output
    return outputs


def export_baseline_csv(
    output_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Results_Combined_Economics_Baseline_PerSim.csv",
    damages_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_Metric_Annual_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_CumulativeCost_Annual_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    growth_series: str = "income_index_oecd",
    elasticity_override: float | None = None,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
    max_workers: int | None = None,
) -> pd.DataFrame:
    return _export_per_simulation_csv(
        output_csv, "baseline", damages_csv, expenditures_csv, assumptions_csv,
        growth_series, elasticity_override, rate_override, piecewise, max_workers,
    )


def export_proactive_csv(
    output_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Results_Combined_Economics_Proactive_PerSim.csv",
    damages_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_Metric_Annual_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_CumulativeCost_Annual_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    growth_series: str = "income_index_oecd",
    elasticity_override: float | None = None,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
    max_workers: int | None = None,
) -> pd.DataFrame:
    return _export_per_simulation_csv(
        output_csv, "proactive", damages_csv, expenditures_csv, assumptions_csv,
        growth_series, elasticity_override, rate_override, piecewise, max_workers,
    )


def export_cumulativecost_csv(
    output_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Results_Combined_Economics_CumulativeCost_PerSim.csv",
    damages_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_Metric_Annual_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_CumulativeCost_Annual_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    growth_series: str = "income_index_oecd",
    elasticity_override: float | None = None,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
    max_workers: int | None = None,
) -> pd.DataFrame:
    return _export_per_simulation_csv(
        output_csv, "cumulativecost", damages_csv, expenditures_csv, assumptions_csv,
        growth_series, elasticity_override, rate_override, piecewise, max_workers,
    )


def export_npv_csv(
    output_csv: str = f"{REPO_ROOT}/Results/EconomicAnalysis/Results_Combined_Economics_NPV_PerSim.csv",
    damages_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_Metric_Annual_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_CumulativeCost_Annual_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    growth_series: str = "income_index_oecd",
    elasticity_override: float | None = None,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
    max_workers: int | None = None,
) -> pd.DataFrame:
    return _export_per_simulation_csv(
        output_csv, "npv", damages_csv, expenditures_csv, assumptions_csv,
        growth_series, elasticity_override, rate_override, piecewise, max_workers,
    )


SENSITIVITY_COMBINATIONS = [
    (1, None, "income_index_oecd", None),
    (2, 0.01, "income_index_oecd", None),
    (3, 0.03, "income_index_oecd", None),
    (4, 0.05, "income_index_oecd", None),
    (5, 0.07, "income_index_oecd", None),
    (6, 0.10, "income_index_oecd", None),
    (7, None, "income_index_fred", None),
    (8, None, "income_index_oecd", 0.6),
    (9, None, "income_index_oecd", 1.7),
]


def _attach_sensitivity_columns(
    output: pd.DataFrame,
    assumption_combination: int,
    rate_override: float | None,
    growth_series: str,
    elasticity_override: float | None,
) -> pd.DataFrame:
    """Add the sensitivity metadata columns used in the final CSV exports."""
    rate = 0.02 if rate_override is None else rate_override
    income_growth = 0.015 if growth_series == "income_index_oecd" else 0.029
    elasticity = 1.1 if elasticity_override is None else elasticity_override

    output = output.copy()
    output.insert(0, "Mortality_Income_Elasticity", elasticity)
    output.insert(0, "Real_Income_Growth", f"{income_growth:.2%}")
    output.insert(0, "Discount_Rate_through_2079", f"{rate:.0%}")
    output.insert(0, "Assumption_Combination", assumption_combination)
    return output


def run_combined_sensitivity_per_sim(
    output_dir: str = f"{REPO_ROOT}/Results/EconomicAnalysis",
    damages_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_Metric_Annual_PerSim.csv",
    expenditures_csv: str = f"{REPO_ROOT}/Results/Combined/Statistics_Both_CumulativeCost_Annual_PerSim.csv",
    assumptions_csv: str = DEFAULT_ASSUMPTIONS_CSV,
    piecewise: bool = DEFAULT_PIECEWISE,
    max_workers: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Run the default combined analysis under the 9 requested assumption combinations."""
    os.makedirs(output_dir, exist_ok=True)

    assumptions, income_growth, acute_df, chronic_df, expenditures, simulation_columns = _load_combined_inputs(
        damages_csv, expenditures_csv, assumptions_csv
    )

    key_columns = {
        "baseline": ["Policy", "SLR", "Hazard", "Metric", "Year"],
        "proactive": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
        "cumulativecost": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
        "npv": ["ProactivePolicy", "SLR", "Hazard", "Metric", "Year"],
    }
    output_names = {
        "baseline": "Results_Combined_Economics_Baseline_Sensitivity_PerSim.csv",
        "proactive": "Results_Combined_Economics_Proactive_Sensitivity_PerSim.csv",
        "cumulativecost": "Results_Combined_Economics_CumulativeCost_Sensitivity_PerSim.csv",
        "npv": "Results_Combined_Economics_NPV_Sensitivity_PerSim.csv",
    }

    combined_outputs = {name: [] for name in output_names}
    for combination, rate_override, growth_series, elasticity_override in SENSITIVITY_COMBINATIONS:
        rows_by_export = _run_all_simulations(
            acute_df, chronic_df, expenditures, simulation_columns, assumptions, income_growth,
            growth_series, elasticity_override, rate_override, piecewise, max_workers
        )

        for name, rows in rows_by_export.items():
            output = _summarize_simulation_rows(rows, key_columns[name], simulation_columns)
            output = _attach_sensitivity_columns(output, combination, rate_override, growth_series, elasticity_override)
            combined_outputs[name].append(output)

    final_outputs = {}
    for name, frames in combined_outputs.items():
        combined = pd.concat(frames, ignore_index=True)
        combined.to_csv(os.path.join(output_dir, output_names[name]), index=False)
        final_outputs[name] = combined
    return final_outputs


if __name__ == "__main__":
    print("Running 9 combined sensitivity combinations...")
    run_combined_sensitivity_per_sim()
    print("Done. Final sensitivity CSVs written without changing any original input files.")
    print("Done.")
