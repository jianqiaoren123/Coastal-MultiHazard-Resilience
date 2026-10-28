"""
sensitivity_analysis.py
=========================
Replicates the "RESULT SENSITIVITIES" tab of EnvisonEconomics_final.xlsx.

This tab does not introduce any new calculation logic, it re-runs the
Acute, Chronic, and Combined analyses (acute_economics.py,
chronic_economics.py, combined_economics.py) with alternate assumption
values, and tabulates the resulting NPV/BCR figures side by side with the
central-case results. The workbook's own tab was built by hand-editing
the Assumptions_LookUpTable values and pasting the resulting outputs;
this script does the same thing programmatically, by passing
rate_override / elasticity_override / growth_series arguments into the
existing analysis functions rather than editing assumptions.csv itself.

Sensitivity cases (per the ReadMe and the workbook's own "Preferred
Assumptions" label):
    Discount rate: 1%, 2% (central), 3%, 5%, 7%, 10%
    Income growth: OECD 1.5% (central), FRED 30-yr average 2.9%
    Mortality risk income elasticity: 0.6 (low), 1.1 (central), 1.7 (high)

Only one assumption is varied at a time relative to the central case,
matching the workbook's approach (e.g., the "2%, 2.9%, 1.1" column varies
only income growth, holding discount rate and elasticity at central).
"""

from __future__ import annotations
import pandas as pd
from econ_common import load_assumptions, DEFAULT_PIECEWISE
from acute_economics import run_acute_analysis
from chronic_economics import run_chronic_analysis
from combined_economics import run_combined_analysis

# Each tuple: (label, rate_override, growth_series, elasticity_override)
# None means "use the central-case value from assumptions.csv".
SENSITIVITY_CASES = [
    ("central (2%, OECD 1.5%, elast 1.1)", None, "income_index_oecd", None),
    ("discount rate 1%", 0.01, "income_index_oecd", None),
    ("discount rate 3%", 0.03, "income_index_oecd", None),
    ("discount rate 5%", 0.05, "income_index_oecd", None),
    ("discount rate 7%", 0.07, "income_index_oecd", None),
    ("discount rate 10%", 0.10, "income_index_oecd", None),
    ("income growth FRED 2.9%", None, "income_index_fred", None),
    ("elasticity low 0.6", None, "income_index_oecd", 0.6),
    ("elasticity high 1.7", None, "income_index_oecd", 1.7),
]


def run_acute_sensitivity(
    results_csv: str = "Results_report_Acute.csv",
    assumptions_csv: str = "assumptions.csv",
    income_growth_csv: str = "income_growth_lookup.csv",
    event_year: int = 2070,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> pd.DataFrame:
    """
    Run run_acute_analysis() once per sensitivity case in SENSITIVITY_CASES.

    Parameters
    ----------
    results_csv, assumptions_csv, income_growth_csv, event_year, piecewise :
        See acute_economics.run_acute_analysis().

    Returns
    -------
    pd.DataFrame
        Concatenation of run_acute_analysis() output across all
        sensitivity cases, with an added "case" column identifying which
        assumption variant produced each row.
    """
    frames = []
    for label, rate_override, growth_series, elasticity_override in SENSITIVITY_CASES:
        result = run_acute_analysis(
            results_csv=results_csv,
            assumptions_csv=assumptions_csv,
            income_growth_csv=income_growth_csv,
            event_year=event_year,
            growth_series=growth_series,
            elasticity_override=elasticity_override,
            rate_override=rate_override,
            piecewise=piecewise,
        )
        result.insert(0, "case", label)
        frames.append(result)
    return pd.concat(frames, ignore_index=True)


def run_chronic_sensitivity(
    damages_csv: str = "Statistics_Chronic_Metric.csv",
    expenditures_csv: str = "Statistics_Chronic_CumulativeCost.csv",
    assumptions_csv: str = "assumptions.csv",
    piecewise: bool = DEFAULT_PIECEWISE,
) -> pd.DataFrame:
    """
    Run run_chronic_analysis() once per discount-rate sensitivity case.

    Chronic damages have no VSL/life-safety component (per the ReadMe:
    "VSL not a factor" for Chronic), so only the discount-rate cases are
    relevant here; income growth and elasticity cases are skipped.

    Parameters
    ----------
    damages_csv, expenditures_csv, assumptions_csv, piecewise :
        See chronic_economics.run_chronic_analysis().

    Returns
    -------
    pd.DataFrame
        Concatenation of run_chronic_analysis() output across all
        discount-rate cases, with an added "case" column.
    """
    rate_cases = [
        ("central (2%)", None),
        ("discount rate 1%", 0.01),
        ("discount rate 3%", 0.03),
        ("discount rate 5%", 0.05),
        ("discount rate 7%", 0.07),
        ("discount rate 10%", 0.10),
    ]
    frames = []
    for label, rate_override in rate_cases:
        result = run_chronic_analysis(
            damages_baseline_csv=damages_csv,
            damages_policy_csv=damages_csv,
            expenditures_csv=expenditures_csv,
            assumptions_csv=assumptions_csv,
            rate_override=rate_override,
            piecewise=piecewise,
        )
        result.insert(0, "case", label)
        frames.append(result)
    return pd.concat(frames, ignore_index=True)


def run_combined_sensitivity(
    damages_csv: str = "Statistics_Both_Metric_Annual.csv",
    expenditures_csv: str = "Statistics_Both_CumulativeCost_Annual.csv",
    assumptions_csv: str = "assumptions.csv",
    income_growth_csv: str = "income_growth_lookup.csv",
    piecewise: bool = DEFAULT_PIECEWISE,
) -> pd.DataFrame:
    """
    Run run_combined_analysis() once per sensitivity case in
    SENSITIVITY_CASES.

    Parameters
    ----------
    damages_csv, expenditures_csv, assumptions_csv, income_growth_csv,
    piecewise :
        See combined_economics.run_combined_analysis().

    Returns
    -------
    pd.DataFrame
        Concatenation of run_combined_analysis() output across all
        sensitivity cases, with an added "case" column.
    """
    frames = []
    for label, rate_override, growth_series, elasticity_override in SENSITIVITY_CASES:
        result = run_combined_analysis(
            damages_csv=damages_csv,
            expenditures_csv=expenditures_csv,
            assumptions_csv=assumptions_csv,
            income_growth_csv=income_growth_csv,
            growth_series=growth_series,
            elasticity_override=elasticity_override,
            rate_override=rate_override,
            piecewise=piecewise,
        )
        result.insert(0, "case", label)
        frames.append(result)
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    print("=== Acute sensitivity (final NPV/BCR per case) ===")
    print(run_acute_sensitivity().to_string(index=False))

    print("\n=== Chronic sensitivity (year 2100 cumulative NPV per case) ===")
    chronic_sens = run_chronic_sensitivity()
    print(chronic_sens[chronic_sens["year"] == chronic_sens["year"].max()].to_string(index=False))

    print("\n=== Combined sensitivity ===")
    print(run_combined_sensitivity().to_string(index=False))
