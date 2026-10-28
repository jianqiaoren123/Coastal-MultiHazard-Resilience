"""Plot six-panel NPV sensitivity results for acute, chronic, and combined cases."""

# Repository root; works after downloading the Code and Simulations archives into one directory.
from pathlib import Path as _RepoPath
REPO_ROOT = _RepoPath(__file__).resolve().parents[2].as_posix()

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


ECONOMICS_DIR = Path(f"{REPO_ROOT}/Results/EconomicAnalysis")
OUTPUT_BASENAME = "SI_NPV_Economic_Sensitivity"
CI_FACTOR = 1.96
PLOT_RATES = [0.01, 0.02, 0.03, 0.05, 0.07]
CHRONIC_YEARS = [2030, 2050, 2070, 2090]
COMBINED_YEARS = [2050, 2070, 2090]
OUTPUT_CSV = ECONOMICS_DIR / "NPV_Economic_Sensitivity.csv"

plt.rcParams.update({
    "axes.labelsize": 16,
    "xtick.labelsize": 18,
    "ytick.labelsize": 18,
    "legend.fontsize": 14,
})


def _rate(value):
    """Convert a percentage string or decimal rate to a decimal rate."""
    if isinstance(value, str):
        value = value.strip().replace("%", "")
        return float(value) / 100
    value = float(value)
    return value / 100 if value > 1 else value


def _simulation_columns(data):
    return [column for column in data.columns if column.startswith("Sim_")]


def _metadata(data, rate_column, rate, combination):
    """Return standardized assumption metadata for an output row."""
    rows = data[data[rate_column].map(_rate) == rate]
    if "Real_Income_Growth" in rows.columns:
        growth = rows["Real_Income_Growth"].map(_rate).iloc[0]
    else:
        growth = 0.015
    if "Mortality_Income_Elasticity" in rows.columns:
        elasticity = float(rows["Mortality_Income_Elasticity"].iloc[0])
    else:
        elasticity = 1.1
    return {
        "Assumption_Combination": combination,
        "Discount_Rate": f"{rate:.0%}",
        "Real_Income_Growth": f"{growth:.2%}",
        "Mortality_Income_Elasticity": elasticity,
    }


def _summary_statistics(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 2:
        raise ValueError("At least two finite simulation values are required")
    mean = values.mean()
    std = values.std(ddof=1)
    ci = CI_FACTOR * std / np.sqrt(values.size)
    return {
        "Mean": mean,
        "Std": std,
        "CoV": std / mean / np.sqrt(values.size) if mean != 0 else np.nan,
        "95CI_LB": mean - ci,
        "95CI_UB": mean + ci,
    }


def _pooled_values(data, policy_column, policy, rate, year, rate_column=True, assumption_columns=True):
    rows = data[
        (data["Metric"] == "Net_Present_Value")
        & (data[policy_column] == policy)
        & (data["Year"] == year)
    ]
    if rate_column:
        rows = rows[rows["Discount_Rate_through_2079"].map(_rate) == rate]
    if assumption_columns and "Real_Income_Growth" in rows.columns:
        rows = rows[rows["Real_Income_Growth"].map(_rate) == 0.015]
    if assumption_columns and "Mortality_Income_Elasticity" in rows.columns:
        rows = rows[rows["Mortality_Income_Elasticity"].astype(float) == 1.1]
    if rows.empty:
        raise ValueError(f"No rows found for {policy}, {rate}, {year}")
    values = pd.to_numeric(rows[_simulation_columns(data)].stack(), errors="coerce")
    return rows, values.to_numpy(dtype=float)


def save_npv_sensitivity_csv(acute, chronic, combined, output_csv=OUTPUT_CSV):
    """Save the exact summary data represented by panels (a)-(f)."""
    output_rows = []

    # Panel (a): all nine acute combinations, two policies.
    for combination in range(1, 10):
        acute_rows = acute[acute["Assumption_Combination"] == combination]
        rate = _rate(acute_rows["Discount_Rate"].iloc[0])
        for policy in ["Protect", "Realign"]:
            row = acute_rows[
                (acute_rows["Metric"] == "Net_Present_Value")
                & (acute_rows["Policy"] == policy)
            ].iloc[0]
            stats = {
                "Mean": float(row["Mean (M$)"]),
                "Std": float(row["Std (M$)"]),
                "CoV": float(row["CoV"]),
                "95CI_LB": float(row["Mean (M$)"]) - CI_FACTOR * float(row["Std (M$)"]) / np.sqrt(1000),
                "95CI_UB": float(row["Mean (M$)"]) + CI_FACTOR * float(row["Std (M$)"]) / np.sqrt(1000),
            }
            output_rows.append({
                **_metadata(acute_rows, "Discount_Rate", rate, combination),
                "Policy": policy, "SLR": "None", "Hazard": "Acute",
                "Metric": "Net_Present_Value", "Year": 2070, **stats,
            })

    # Panels (b) and (c): six discount-rate combinations, pooled over SLR and simulations.
    for combination, rate in [(1, 0.02), (2, 0.01), (3, 0.03), (4, 0.05), (5, 0.07), (6, 0.10)]:
        chronic_rate_rows = chronic[chronic["Assumption_Combination"] == combination]
        for policy in ["Protect", "Realign"]:
            for year in CHRONIC_YEARS:
                rows, values = _pooled_values(
                    chronic_rate_rows, "ProactivePolicy", policy, rate, year,
                    rate_column=False, assumption_columns=False,
                )
                output_rows.append({
                    **_metadata(chronic_rate_rows, "Discount_Rate_through_2079", rate, combination),
                    "Policy": policy, "SLR": "Averaged", "Hazard": "Chronic",
                    "Metric": "Net_Present_Value", "Year": year,
                    **_summary_statistics(values),
                })

    # Panels (d)-(f): all nine combined combinations, pooled over SLR and simulations.
    for year in COMBINED_YEARS:
        for combination in range(1, 10):
            combined_rate_rows = combined[combined["Assumption_Combination"] == combination]
            rate = _rate(combined_rate_rows["Discount_Rate_through_2079"].iloc[0])
            for policy in ["AC3-A", "AC3", "AC3-C"]:
                rows, values = _pooled_values(
                    combined_rate_rows, "ProactivePolicy", policy, rate, year,
                    rate_column=False, assumption_columns=False,
                )
                output_rows.append({
                    **_metadata(combined_rate_rows, "Discount_Rate_through_2079", rate, combination),
                    "Policy": policy, "SLR": "Averaged", "Hazard": "Both",
                    "Metric": "Net_Present_Value", "Year": year,
                    **_summary_statistics(values),
                })

    output = pd.DataFrame(output_rows, columns=[
        "Assumption_Combination", "Discount_Rate", "Real_Income_Growth",
        "Mortality_Income_Elasticity", "Policy", "SLR", "Hazard", "Metric",
        "Year", "Mean", "Std", "CoV", "95CI_LB", "95CI_UB",
    ])
    if len(output) != 147:
        raise ValueError(f"Expected 147 sensitivity summary rows, found {len(output)}")
    output.to_csv(output_csv, index=False)
    return output


def _acute_summary(data, policy, rate):
    rows = data[
        (data["Metric"] == "Net_Present_Value")
        & (data["Policy"] == policy)
        & (data["Real_Income_Growth"].map(_rate) == 0.015)
        & (data["Mortality_Income_Elasticity"].astype(float) == 1.1)
        & (data["Discount_Rate"].map(_rate) == rate)
    ]
    if len(rows) != 1:
        raise ValueError(f"Expected one acute row for {policy}, {rate}; found {len(rows)}")
    row = rows.iloc[0]
    mean = float(row["Mean (M$)"])
    std = float(row["Std (M$)"])
    return mean, CI_FACTOR * std / np.sqrt(1000)


def _pooled_summary(data, policy_column, policy, rate, year, slr=None):
    rows = data[
        (data["Metric"] == "Net_Present_Value")
        & (data[policy_column] == policy)
        & (data["Year"] == year)
        & (data["Discount_Rate_through_2079"].map(_rate) == rate)
    ]
    if "Real_Income_Growth" in rows.columns:
        rows = rows[rows["Real_Income_Growth"].map(_rate) == 0.015]
    if "Mortality_Income_Elasticity" in rows.columns:
        rows = rows[rows["Mortality_Income_Elasticity"].astype(float) == 1.1]
    if slr is not None:
        rows = rows[rows["SLR"] == slr]
    if rows.empty:
        description = f"{policy}, {rate}, {year}" if slr is None else f"{policy}, {slr}, {rate}, {year}"
        raise ValueError(f"No NPV rows found for {description}")

    simulation_columns = _simulation_columns(data)
    values = pd.to_numeric(rows[simulation_columns].stack(), errors="coerce").to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 2:
        raise ValueError(f"Fewer than two valid simulation values for {policy}, {rate}, {year}")
    mean = values.mean()
    std = values.std(ddof=1)
    return mean, CI_FACTOR * std / np.sqrt(values.size)


def _bar_groups(ax, group_centers, group_values, group_errors, colors, n_bars, width=0.16):
    offsets = (np.arange(n_bars) - (n_bars - 1) / 2) * width
    for index in range(n_bars):
        positions = group_centers + offsets[index]
        ax.bar(
            positions,
            [values[index] for values in group_values],
            width=width,
            yerr=[errors[index] for errors in group_errors],
            capsize=4,
            color=colors[index],
            ecolor=colors[index],
            linewidth=0,
        )


def _style_axis(ax, label, ylabel, xlabel=None):
    ax.text(0.03, 0.95, label, transform=ax.transAxes, ha="left", va="top", fontsize=16, fontweight="bold")
    ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_axisbelow(True)


def plot_npv_sensitivity(output_basename=OUTPUT_BASENAME):
    acute = pd.read_csv(ECONOMICS_DIR / "Results_Acute_Economics_Sensitivity_PerSim.csv")
    chronic = pd.read_csv(ECONOMICS_DIR / "Results_Chronic_Economics_NPV_Sensitivity_PerSim.csv")
    combined = pd.read_csv(ECONOMICS_DIR / "Results_Combined_Economics_NPV_Sensitivity_PerSim.csv")
    save_npv_sensitivity_csv(acute, chronic, combined)

    fig, axes = plt.subplots(3, 2, figsize=(14, 15))
    group_centers = np.arange(len(PLOT_RATES))
    rate_labels = ["1%", "2%", "3%", "5%", "7%"]

    ax = axes[0, 0]
    values, errors = [], []
    for rate in PLOT_RATES:
        group_values, group_errors = [], []
        for policy in ["Protect", "Realign"]:
            mean, ci = _acute_summary(acute, policy, rate)
            group_values.append(mean)
            group_errors.append(ci)
        values.append(group_values)
        errors.append(group_errors)
    _bar_groups(ax, group_centers, values, errors, ["#4daf4a", "#377eb8"], 2)
    ax.set_xticks(group_centers, rate_labels)
    _style_axis(ax, "(a)", "Net Present Value (M$)")
    ax.legend(handles=[Patch(color="#4daf4a", label="Protect"), Patch(color="#377eb8", label="Realign")], frameon=False)

    for ax, label, policy, colors in [
        (axes[0, 1], "(b)", "Protect", ["#c7e9c0", "#74c476", "#31a354", "#006d2c"]),
        (axes[1, 0], "(c)", "Realign", ["#c6dbef", "#6baed6", "#2171b5", "#084594"]),
    ]:
        values, errors = [], []
        for rate in PLOT_RATES:
            group_values, group_errors = [], []
            for year in CHRONIC_YEARS:
                mean, ci = _pooled_summary(chronic, "ProactivePolicy", policy, rate, year)
                group_values.append(mean)
                group_errors.append(ci)
            values.append(group_values)
            errors.append(group_errors)
        _bar_groups(ax, group_centers, values, errors, colors, 4)
        ax.set_xticks(group_centers, rate_labels)
        _style_axis(ax, label, "Net Present Value (M$)" if label == "(c)" else "")
        ax.legend(handles=[Patch(color=color, label=str(year)) for color, year in zip(colors, CHRONIC_YEARS)], frameon=False)

    combined_colors = ["#9b59b6", "#00a6a6", "#f39c12"]
    for axis, year, label, title in zip(
        [axes[1, 1], axes[2, 0], axes[2, 1]],
        COMBINED_YEARS,
        ["(d)", "(e)", "(f)"],
        ["Combined-2050 CSZ Event", "Combined-2070 CSZ Event", "Combined-2090 CSZ Event"],
    ):
        values, errors = [], []
        for rate in PLOT_RATES:
            group_values, group_errors = [], []
            for policy in ["AC3-A", "AC3", "AC3-C"]:
                mean, ci = _pooled_summary(combined, "ProactivePolicy", policy, rate, year)
                group_values.append(mean)
                group_errors.append(ci)
            values.append(group_values)
            errors.append(group_errors)
        _bar_groups(axis, group_centers, values, errors, combined_colors, 3)
        axis.set_xticks(group_centers, rate_labels)
        _style_axis(axis, label, "Net Present Value (M$)" if label == "(e)" else "", "Discount Rate" if label in ["(e)", "(f)"] else None)
        axis.legend(handles=[Patch(color=color, label=policy) for color, policy in zip(combined_colors, ["AC3-A", "AC3", "AC3-C"])], frameon=False)

    fig.tight_layout()
    for extension in ["png", "svg"]:
        fig.savefig(ECONOMICS_DIR / f"{output_basename}.{extension}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    plot_npv_sensitivity()
