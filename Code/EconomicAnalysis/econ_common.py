"""
econ_common.py
================
Shared building blocks for the Acute, Chronic, and Combined economic analyses
(acute_economics.py, chronic_economics.py, combined_economics.py).

This module replicates the two pieces of arithmetic that recur in every tab
of EnvisonEconomics_final.xlsx: discounting a future dollar value back to a
present value, and escalating + discounting the Value of Statistical Life
(VSL) for a future event year. Keeping both in one place means every
downstream calculation uses an identical, single-source-of-truth formula,
matching how the original workbook reuses the same Assumptions_LookUpTable
cells across every sheet.

All dollar figures are handled in whatever units the caller passes in
(the workbook uses $M 2020 USD in the Chronic/Combined tabs and raw USD in
the Acute tab; this module is unit-agnostic and just does the math).

Discount rate handling
-----------------------
The workbook implements a declining discount rate schedule per OMB
Circular A-4 (Nov 2023), matching the ReadMe exactly: 2.0% through 2079,
1.9% for 2080-2094, and 1.8% for 2095-2105. Each formula explicitly
references the correct rate cell (Assumptions_LookUpTable!$B$4, $C$4, or
$D$4) for its column; this was confirmed by reading the actual year
value each formula uses in its own exponent (e.g. row 19 in the Chronic
Damages sheets), not a sheet's separate summary-table header row, since
different row blocks within the same sheet can have their own,
differently-offset column-to-year header.
"""

from __future__ import annotations
import pandas as pd

# ---------------------------------------------------------------------------
# Global default: whether discounting uses the flat 2% rate throughout, or
# the piecewise OMB A-4 schedule the workbook implements (switching at 2080
# and 2095, confirmed against the workbook's own formulas). Piecewise is
# the default, matching both the workbook and the ReadMe.
# ---------------------------------------------------------------------------
DEFAULT_PIECEWISE = True


def load_assumptions(path: str = "assumptions.csv") -> dict:
    """
    Load the scalar assumptions table (discount rates, VSL levels, injury
    fraction, income elasticities, income growth rates, unit conversions,
    annual budget) into a flat dict keyed by parameter name.

    Parameters
    ----------
    path : str
        Path to assumptions.csv (parameter, value, description columns).

    Returns
    -------
    dict
        {parameter_name: value}, values coerced to float.
    """
    df = pd.read_csv(path)
    return {row["parameter"]: float(row["value"]) for _, row in df.iterrows()}


def load_income_growth_lookup(path: str = "income_growth_lookup.csv") -> pd.DataFrame:
    """
    Load the year-by-year cumulative real income growth index (2020-2100),
    used to escalate VSL to a future event year before discounting it back.

    Parameters
    ----------
    path : str
        Path to income_growth_lookup.csv (year, income_index_oecd,
        income_index_fred columns).

    Returns
    -------
    pd.DataFrame
        Indexed by year, columns "income_index_oecd" and
        "income_index_fred". Each index value is the cumulative growth
        multiplier relative to the base year (2020 = 1.0).
    """
    df = pd.read_csv(path)
    return df.set_index("year")


def discount_factor(
    year: int,
    assumptions: dict,
    base_year: int | None = None,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> float:
    """
    Compute the present-value discount factor for a single future dollar
    received in `year`, relative to `base_year`.

    Flat-rate mode (piecewise=False, the current spreadsheet's behavior):
        factor = (1 + r) ** -(year - base_year)
    using a single constant rate r for the whole horizon.

    Piecewise mode (piecewise=True, per the ReadMe's OMB A-4 description):
        The horizon from base_year to year is split at the 2079/2080 and
        2094/2095 boundaries, each segment discounted at its own rate
        (2.0% through 2079, 1.9% for 2080-2094, 1.8% for 2095-2105), and
        the segment factors are compounded together.

    Parameters
    ----------
    year : int
        The future year the dollar value is received/incurred in.
    assumptions : dict
        Output of load_assumptions(). Must contain "discount_rate_central"
        (and, for piecewise mode, "discount_rate_2080_2094" and
        "discount_rate_2095_2105").
    base_year : int, optional
        Present-value reference year. Defaults to assumptions["base_year"].
    rate_override : float, optional
        If given, use this rate through 2079 in piecewise mode, then revert
        to the original OMB schedule. In flat-rate mode, use this rate for
        the whole horizon. Used by sensitivity analysis for alternate rates
        of 1%, 3%, 5%, 7%, and 10%.
    piecewise : bool
        Whether to apply the declining OMB A-4 schedule. Defaults to
        DEFAULT_PIECEWISE.

    Returns
    -------
    float
        Discount factor in (0, 1] for year >= base_year.
    """
    if base_year is None:
        base_year = int(assumptions["base_year"])

    if year <= base_year:
        return 1.0

    if not piecewise:
        r = rate_override if rate_override is not None else assumptions["discount_rate_central"]
        return (1 + r) ** (-(year - base_year))

    # Compound each rate segment separately. Sensitivity runs replace the
    # central rate only through 2079; the original OMB rates remain active
    # for 2080-2094 and 2095 onward.
    central_rate = rate_override if rate_override is not None else assumptions["discount_rate_central"]
    first_segment_end = min(year, 2079)
    first_segment_years = max(0, first_segment_end - base_year)
    factor = (1 + central_rate) ** (-first_segment_years)

    if year > 2079:
        second_segment_end = min(year, 2094)
        second_segment_years = second_segment_end - 2079
        factor *= (1 + assumptions["discount_rate_2080_2094"]) ** (-second_segment_years)

    if year > 2094:
        third_segment_years = year - 2094
        factor *= (1 + assumptions["discount_rate_2095_2105"]) ** (-third_segment_years)

    return factor


def present_value(
    value: float,
    year: int,
    assumptions: dict,
    base_year: int | None = None,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> float:
    """
    Discount a single future dollar value to its present value.

    Equivalent to `value * discount_factor(...)`. Matches, e.g., Acute
    (Sec 3.1) cells G43/H43 (building damage PV) and the "Net Present
    Value of Erosion/Flooding Damages" rows in the Chronic Damages tabs.

    Parameters
    ----------
    value : float
        The nominal (undiscounted) dollar value occurring in `year`.
    year, assumptions, base_year, rate_override, piecewise :
        See discount_factor().

    Returns
    -------
    float
        Present value of `value`.
    """
    return value * discount_factor(year, assumptions, base_year, rate_override, piecewise)


def vsl_at_year(
    year: int,
    assumptions: dict,
    income_growth: pd.DataFrame,
    growth_series: str = "income_index_oecd",
    elasticity_override: float | None = None,
    rate_override: float | None = None,
    piecewise: bool = DEFAULT_PIECEWISE,
) -> float:
    """
    Compute the escalated-then-discounted Value of a Statistical Life for
    a future event year, matching Acute (Sec 3.1) cell B3:

        VSL_t = VSL_2020 * (income_index_t) ** elasticity * (1+r) ** -(t - 2020)

    Income is first grown forward to the event year using the cumulative
    growth index (income compounds every year up to the event), raised to
    the mortality risk income elasticity, then the whole result is
    discounted back to present value using the same discount_factor logic
    as every other dollar figure in this codebase.

    Parameters
    ----------
    year : int
        The future event year (e.g., 2070 for the primary Acute scenario).
    assumptions : dict
        Output of load_assumptions(). Must contain "vsl_central" and
        "income_elasticity_central".
    income_growth : pd.DataFrame
        Output of load_income_growth_lookup().
    growth_series : str
        Which income growth column to use: "income_index_oecd" (default,
        central case) or "income_index_fred" (sensitivity case).
    elasticity_override : float, optional
        Use this elasticity instead of assumptions["income_elasticity_
        central"]. Used by the sensitivity analysis.
    rate_override, piecewise :
        See discount_factor().

    Returns
    -------
    float
        VSL for a fatality, in present-value 2020 USD.
    """
    vsl_2020 = assumptions["vsl_central"]
    elasticity = (
        elasticity_override if elasticity_override is not None
        else assumptions["income_elasticity_central"]
    )
    income_index = income_growth.loc[year, growth_series]

    escalated = vsl_2020 * (income_index ** elasticity)
    factor = discount_factor(year, assumptions, rate_override=rate_override, piecewise=piecewise)
    return escalated * factor


def vsl_injury(vsl_fatality: float, assumptions: dict) -> float:
    """
    Convert a fatality VSL into an injury VSL using the DOT "Serious"
    injury severity fraction. Matches Acute (Sec 3.1) cell B4 = B3 *
    Assumptions_LookUpTable!B13.

    Parameters
    ----------
    vsl_fatality : float
        Output of vsl_at_year().
    assumptions : dict
        Output of load_assumptions(). Must contain
        "injury_fraction_serious".

    Returns
    -------
    float
        VSL applicable to a single injury, present-value 2020 USD.
    """
    return vsl_fatality * assumptions["injury_fraction_serious"]
