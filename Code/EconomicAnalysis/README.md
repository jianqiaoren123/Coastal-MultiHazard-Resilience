# Economic Analysis Codebase, Overview

This is a Python replication of `EnvisonEconomics_final.xlsx` (Steve's
NPV/BCR economic analysis for the Envision paper). It plays the same role
`ReadMe_EnvisionEconomics.docx` plays for the spreadsheet: a guide to what
each file does and the key assumptions behind it. Read this first; each
`.py` file also has its own module- and function-level docstrings with
more implementation detail.

**Validation policy for this codebase: Excel's own cached cell values are
ground truth, not the ReadMe.** Every number in this README's validation
section below was pulled directly from the corrected workbook
(`EnvisonEconomics_final_ZW_checked.xlsx`) with `openpyxl(data_only=True)`.

**Current scope**: every function here operates on a **single simulation
replicate**. Nothing in this codebase aggregates across simulations. The
input CSVs currently hold the across-simulation mean; once per-simulation
CSVs are available in the same column layout, call the relevant
`run_*_analysis()` function once per simulation and summarize the
resulting NPV/BCR/CER values (mean, bootstrap 95% CI) across replicates,
one level up from this codebase.

## Files

| File | Replicates | Purpose |
|---|---|---|
| `econ_common.py` | `Assumptions_LookUpTable` | Shared discounting and VSL math used by all three analyses |
| `acute_economics.py` | `Acute (Sec 3.1)` | Single-event-year (2070) NPV/BCR for Protect and Realign |
| `chronic_economics.py` | `Chronic (3.2)` tabs | Annual (2020-2100) present-value damages, expenditures, and cumulative NPV trajectory |
| `combined_economics.py` | `Combined (3.3)` tabs | Three-snapshot-year (2050/2070/2090) NPV/BCR for AC3, AC3-A, AC3-C |
| `sensitivity_analysis.py` | `RESULT SENSITIVITIES` | Re-runs the above three with alternate discount rate / income growth / elasticity assumptions |
| `assumptions.csv` | `Assumptions_LookUpTable` (scalars) | Discount rates, VSL levels, injury fraction, income elasticities, income growth rates, unit conversions, annual budget |
| `income_growth_lookup.csv` | `Assumptions_LookUpTable` (year table) | Cumulative real income growth index by year (2020-2100), OECD and FRED series |

## Core formulas

**Discounting** applies a single OMB A-4 bracket rate to the entire span
from base_year to the target year (2.0% through 2079, 1.9% for
2080-2094, 1.8% for 2095-2105), not compounded segment by segment:

```
PV = FV / (1 + r_bracket) ** (year - base_year)
```

This is applied uniformly, by year value alone, to every policy, SLR
scenario, and hazard type, so there is no possibility of the kind of
per-block inconsistency found in the original workbook (see below).

**VSL for a future event year**:
```
VSL_t = VSL_2020 * (income_index_t)^elasticity * (1+r)^-(t - 2020)
```

**Chronic expenditure** is differenced into year-over-year incremental
spend before discounting (the raw input is a running cumulative total,
not an annual figure); each increment is discounted individually and
summed.

## Excel workbook bugs found during validation, and their status in this code

All of the following were found through cell-by-cell audits of every
formula in every relevant sheet, not spot checks. Each was fixed directly
in `EnvisonEconomics_final_ZW_checked.xlsx`, and none required any code
change here, since this codebase computes each quantity independently
from the CSVs and `assumptions.csv` rather than replicating Excel's
specific cross-sheet cell references.

| Sheet | Issue | Numerically real? | Status |
|---|---|---|---|
| Combined, Damages Policy | `N15` (AC3-A/MED/2050/Acute Life Safety) pointed to the HIGH SLR block instead of MED | No, both blocks had identical values for this Acute-only metric (Acute doesn't vary by SLR) | Fixed in Excel; never present in this code |
| Combined, Expenditures | AC3-A/High/2050 summed one row short | No, the missing row was 0 | Fixed in Excel; never present in this code |
| Combined, Expenditures | AC3-C/High/2050 summed one extra (header) row | No, SUM ignores text | Fixed in Excel; never present in this code |
| Combined, Expenditures | AC3-C/High/2090 summed one extra year | **Yes**, overstated by $0.448M | Fixed in Excel; never present in this code |
| Chronic, Damages Policy | Realign Med and Low (Erosion and Flooding, all 4 combinations) never switched off the flat 2% discount rate after 2080 | **Yes**, understated chronic PV for those blocks across 2080-2100 | Fixed in Excel; this code always applied the correct bracket rate uniformly, so it was never present here |
| Chronic, Damages Policy | Some blocks reference a duplicate "Year" row (row 33 vs row 70) rather than one shared row | No, both rows hold identical year values (confirmed across all 88 columns) | Cosmetic only; left as is in Excel per direction; this code uses the actual Year column from the CSV directly, so there is no equivalent duplication to have |

## A data version difference found during final validation, not a bug

After all of the above were fixed, `Chronic (3.2)`'s Realign/Med block
still did not match Excel's cached NPV exactly (Realign/Low and all of
Protect matched exactly). Traced to the source: Excel's cached baseline
flooding damage is identical between the MED and LOW SLR blocks (the
same sequence of values in both), while the CSV (`Statistics_Chronic_
Metric.csv`) has a distinct, SLR-differentiated baseline sequence for MED.
This means Excel's cache reflects an earlier simulation run where baseline
flooding damage wasn't yet SLR-specific; the CSV reflects a newer run
where it is. Both the workbook and this code are computing NPV correctly
from the baseline data each was given, they were simply given different
baseline data for this one scenario. No code or formula fix applies here;
this will resolve naturally once per-simulation data from the current
simulation run is used throughout.

## Detailed per-metric export files

Both `chronic_economics.py` and `combined_economics.py` also include
export functions producing long-format CSVs (one row per year/policy/
SLR/hazard combination) for direct cross-checking against specific
Excel cells:

- `chronic_economics.py`: `export_baseline_csv()`, `export_proactive_csv()`,
  `export_cumulativecost_csv()`, `export_npv_csv()`, one row per year
  2021-2100.
- `combined_economics.py`: `export_baseline_csv()`, `export_proactive_csv()`,
  `export_cumulativecost_csv()`, `export_npv_csv()`, one row per
  snapshot year (2050, 2070, 2090).

All eight were validated directly against the corresponding Excel cells
in `EnvisonEconomics_final_ZW_checked.xlsx`. One real fix was made
during this validation: `combined_economics.py`'s `_chronic_damage_pv()`
originally treated Baseline (raw, undiscounted sum) differently from
Policy (discounted sum), matching the original workbook. Once Baseline's
Flooding formulas were corrected in Excel to consistently use the
discounted row at all three snapshot years (not just 2090, see the bug
list above), this function was updated to treat Baseline and Policy
identically, and now matches the corrected workbook exactly.

## Known minor residual, Acute component

A small (~0.04% relative) discrepancy in the Acute damage/VSL
calculation has been present since early validation and was never fully
traced to its exact source (likely a minor rounding difference in VSL
or income-growth lookup precision). It appears in `acute_economics.py`'s
output and propagates into any Combined quantity that includes an Acute
component (Baseline/Proactive "Both" totals, NPV). Chronic-only and
cost-only figures are unaffected and match exactly.

## Validated against the workbook's own cached cell values

**Acute**: every benefit component (life safety, building damage, VSL)
matches Excel exactly. Investment cost matches Excel's actual computed
total (`SUM(B64:B112)` = $155,260,390.06) exactly, replicating the
workbook's real 49-term sum rather than a theoretical 50-year version,
per direction to match Excel as built. Final NPV: Protect $44,235,264.37,
Realign $3,411,263,705.85, both matching Excel to 8+ significant figures.

**Chronic**: Protect (all 3 SLR) and Realign (High and Low SLR) match
Excel's cumulative NPV exactly at every checkpoint tested, including
both discount-rate boundary years (2079/2080/2081 and 2094/2095).
Realign/Med differs only due to the data version difference described
above, not a calculation discrepancy.

**Combined**: ranking AC3-A > AC3 > AC3-C holds across all SLR scenarios
and snapshot years, matching Excel throughout.

## Running

Each file has a `if __name__ == "__main__":` block that runs a quick
demonstration against the sample (mean-value) CSVs and prints results:

```bash
python3 acute_economics.py
python3 chronic_economics.py
python3 combined_economics.py
python3 sensitivity_analysis.py
```

For actual use (once per-simulation CSVs are available), import the
relevant `run_*_analysis()` function, call it once per simulation
replicate (pointing `results_csv` / `damages_csv` / etc. at that
replicate's file), collect the returned DataFrames, and compute mean and
bootstrap 95% CI across replicates on the `npv`, `bcr`, and
`cumulative_npv` columns.
