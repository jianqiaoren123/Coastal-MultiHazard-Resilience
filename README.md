# Code and data for *A Coupled Framework for Assessing Multi-Hazard Coastal Resilience and Adaptation Pathways*

This repository accompanies the manuscript *A Coupled Framework for Assessing Multi-Hazard Coastal Resilience and Adaptation Pathways* (Nature Communications, manuscript NCOMMS-26-080255). It documents the integrated coastal-resilience modeling framework, identifies upstream model and data sources, and provides Python analysis code and processed results used to produce the manuscript's findings.

## Overview

The research workflow has three connected components:

1. **Upstream forcing and hazard data:** stochastic coastal total water levels, observed shoreline-change rates, and Cascadia Subduction Zone (CSZ) earthquake and tsunami hazard inputs.
2. **Integrated Envision/OrCoast simulations:** the Tillamook application combines coastal hazards, exposure, adaptation policies, and physical, social, and economic outcomes. SFINCS is an inundation submodel within this application.
3. **Python analysis and reporting:** hazard-specific scripts process Envision outputs; shared economic scripts calculate present-value outcomes; reporting scripts generate ensemble summaries and manuscript figures and tables.

The GitHub repository contains the analysis code and processed results. A separate Zenodo dataset contains a representative subset of raw Envision outputs. The upstream models and the study-specific OrCoast application are identified below rather than duplicated in this analysis repository.

## Model and data sources

| Component | Role | Source and availability |
|---|---|---|
| MUSCLE / TESLA | Stochastic coastal total-water-level forcing | [Leung et al. (2024), DesignSafe](https://doi.org/10.17603/ds2-mr46-5g54); see details below |
| Satellite-derived shoreline observations and change rates | Spatially varying historical shoreline-change inputs | [Taherkhani et al. (2025), DesignSafe, version 2](https://doi.org/10.17603/ds2-59cy-n043); study inputs incorporated in OrCoast |
| CSZ earthquake and tsunami hazard data | Precomputed acute-hazard layers | OSSPAC (2013); Madin et al. (2013); Priest et al. (2013); study inputs incorporated in OrCoast |
| Envision | Agent-based simulation framework | [Envision source code](https://github.com/boltej/Envision) |
| OrCoast / Tillamook application | Integrated hazard, adaptation, and scenario implementation | Existing repository: http://envweb.bee.oregonstate.edu/GitServer/OrCoast.git ; reviewer access is **pending confirmation** from its maintainer |
| SFINCS | Coastal inundation submodel | [Deltares SFINCS](https://github.com/Deltares/SFINCS); study configuration within OrCoast; Dollerup v2.1.1 executable and `hydromt-sfincs==1.1.0` |
| Python analysis and processed results | Per-run metrics, economic analysis, and manuscript reporting | [Coastal-MultiHazard-Resilience GitHub repository](https://github.com/jianqiaoren123/Coastal-MultiHazard-Resilience) |
| Representative Envision outputs | Example raw data for inspection and per-run processing | Zenodo `Simulations.zip` ([DOI: 10.5281/zenodo.23720608](https://doi.org/10.5281/zenodo.23720608)) |

### MUSCLE/TESLA forcing

The MUSCLE model used to generate coastal total water level forcing in this study was derived from the previously developed TESLA framework. The TESLA model code, Jupyter notebooks, and associated Cascadia-region datasets are archived on DesignSafe (Leung et al., 2024; https://doi.org/10.17603/ds2-mr46-5g54). For this application, we used offshore wave and water level forcings associated with the Astoria (`CASC_As`) sub-region. The forcing data used in the Envision simulations are included in the manuscript-specific OrCoast model inputs. Minor differences from the archived dataset may occur due to storm-surge and significant-wave-height bias corrections.

### Acute-hazard references

- Oregon Seismic Safety Policy Advisory Commission (OSSPAC). (2013). *The Oregon Resilience Plan: Reducing Risk and Improving Recovery for the Next Cascadia Earthquake and Tsunami.*
- Madin, I., Burns, W. J., & McConnell, V. S. (2013). *Ground Motion, Ground Deformation, Tsunami Inundation, Coseismic Subsidence, and Damage Potential Maps for the 2012 Oregon Resilience Plan for Cascadia Subduction Zone Earthquakes.* Oregon Department of Geology and Mineral Industries.
- Priest, G. R., et al. (2013). *Tsunami Inundation Scenarios for Oregon.* Oregon Department of Geology and Mineral Industries, Open-File Report O-13-19.

## Repository layout

After downloading the GitHub repository and extracting the Zenodo archive into its root, the directory layout is:

```text
Coastal-MultiHazard-Resilience/
├── README.md
├── requirements.txt
├── .gitignore
├── Code/
│   ├── Acute/
│   ├── Chronic/
│   ├── Combined/
│   ├── Sensitivity/
│   └── EconomicAnalysis/
├── Results/
│   ├── Acute/
│   ├── Chronic/
│   ├── Combined/
│   ├── Sensitivity/
│   └── EconomicAnalysis/
└── Simulations/                 # Extracted from Zenodo Simulations.zip
    ├── Acute/
    ├── Chronic/
    ├── Combined/
    ├── Sensitivity/
    │   ├── Chronic_Corner1/
    │   └── Chronic_Corner2/
    └── IDU/
        └── idu.dbf
```

`Code/`, `Results/`, and this README are distributed through GitHub. `Simulations/` is distributed through **one** Zenodo archive named `Simulations.zip`, which contains the `Simulations/` directory and its existing subdirectories. No scenario or individual file names should be changed during extraction. The scripts use paths anchored to the project directory rather than author-specific server locations.

## Integrated OrCoast model and scenario design

The Envision/OrCoast application integrates chronic coastal flooding and erosion, CSZ earthquake and tsunami impacts, adaptation policies, and community and asset outcomes. Its study-specific inputs and configurations are part of the OrCoast application. SFINCS provides inundation modeling within the integrated framework.

The manuscript examines:

- **Acute hazards:** earthquake and tsunami scenarios, with Baseline, Protect, and Realign policies; the primary acute event year is 2070.
- **Chronic hazards:** flooding and erosion over 2020–2100 under sea-level-rise and adaptation scenarios.
- **Combined hazards:** chronic hazards together with acute-event timing, including 2050, 2070, and 2090 sensitivity cases.
- **Chronic cost sensitivity:** four parameter corners; only `Chronic_Corner1` and `Chronic_Corner2` require distinct simulation datasets, while Corners 3 and 4 reuse those simulations for alternative cost calculations.

Physical, social, and economic outcomes are analyzed across simulations. Economic results are expressed in 2020 present-value terms using the study's documented assumptions.

## Analysis workflows

The main execution sequence is **hazard-specific per-simulation processing → economic analysis → hazard-specific reporting and plotting**. Economic analysis is an intermediate step for reports that use present-value results. See the `README.md` in each `Code/` subdirectory for workflow-specific instructions and output filenames.

| Workflow | Per-simulation processing | Economic analysis | Reporting |
|---|---|---|---|
| Acute | `Code/Acute/AcuteHazard_analysis_detailed_results_PerSim.py` and `AcuteHazard_reporting_discussion_PerSim.py` | `Code/EconomicAnalysis/acute_economics_PerSim.py` | `Code/Acute/AcuteHazard_summary_plots_PV.py` |
| Chronic | `Code/Chronic/ChronicHazard_analysis_detailed_results_PerSim.py` | `Code/EconomicAnalysis/chronic_economics_PerSim.py` | `Code/Chronic/ChronicHazard_plots_PV.py` |
| Combined | `Code/Combined/BothHazard_analysis_detailed_results_PerSim.py` | `Code/EconomicAnalysis/combined_economics_PerSim.py` | `Code/Combined/BothHazard_plots_PV.py` |
| Chronic cost sensitivity | `Code/Sensitivity/ChronicHazard_Corner[1–4]_analysis_detailed_results_PerSim.py` | `Code/EconomicAnalysis/chronic_corner[1–4]_economics_PerSim.py` | `Code/Sensitivity/ChronicHazard_Corner[1–4]_plots_PV.py` |

The shared economic module includes `econ_common.py`, `assumptions.csv`, and `income_growth_lookup.csv`. Economic-assumption sensitivity scripts are also included in `Code/EconomicAnalysis/`.

## Simulation archive and reproducibility scope

The **Zenodo `Simulations.zip` archive contains one representative simulation index for each required scenario**, including Acute, Chronic, Combined, and the two distinct Chronic cost-sensitivity simulation sets. It also includes the IDU/DBF inputs required for processing the selected examples. This archive is a **subset of raw Envision simulation outputs**, not the complete Monte Carlo ensemble.

The original Acute scenarios contain 1,000 internal Monte Carlo iterations per scenario. The Chronic and Combined analyses use separate simulation/run folders representing Monte Carlo realizations. The released raw examples are intended to document the input structure and permit examination or selected per-run processing; they **cannot by themselves reproduce the complete ensemble**.

The GitHub `Results/` directory contains the **full processed per-run and summary CSV datasets used in the manuscript analyses**. These files, together with the reporting scripts, are intended to support reproduction of ensemble summaries, uncertainty statistics, figures, and tables **without downloading all raw Envision simulation folders**. The scripts retain their original full-ensemble configurations; they have not been rewritten solely to execute automatically against the representative subset. Running a selected per-run analysis on the sample may require selecting the corresponding index in the script. No full end-to-end validation of the redistributed package is claimed here.

To assemble the data, download the GitHub repository, download `Simulations.zip` from Zenodo, and extract it into the GitHub repository root so that `Simulations/`, `Code/`, and `Results/` are siblings. The archive's contents should be checked after extraction. Do not rename simulation folders, run directories, or input files.

## Software environment and execution

The reported Python environment is:

```text
Python 3.13.12
pandas 3.0.2
numpy 2.4.4
matplotlib 3.10.8
scipy 1.17.1
seaborn 0.13.2
dbfread 2.0.7
```

The Python postprocessing and economic analysis were performed on the OSU `oysterville` server running **Rocky Linux 8.10 (Green Obsidian), x86-64**. The host has **two Intel Xeon Gold 6338 processors (2.00 GHz; 32 physical cores each, 64 physical cores / 128 logical CPUs total)** and **250 GiB of installed RAM**. These are host specifications, **not verified minimum requirements** for running the Python scripts. The number of CPU cores and peak memory actually used by each script have not been measured.

The installed versions above were reported from the authors' working environment. The pinned package versions are provided in `requirements.txt`. The scripts have undergone path updates and Python syntax checks, but **a complete execution test against the redistributed datasets has not yet been documented**. Installation time, example commands, and verified expected outputs remain to be documented.

### Estimated Python analysis runtime

The complete manuscript analysis used approximately **27 Python scripts**: Acute (3), Chronic (2), Combined (2), EconomicAnalysis (12), and Sensitivity (8). Based on the authors' experience, **26 scripts typically required approximately 3–5 minutes each**, while **one computationally intensive Combined analysis script required approximately 6 hours** to process the full ensemble. Assuming **uninterrupted, sequential execution** with no pauses or failures, the estimated total is **438–490 minutes (approximately 7 hours 18 minutes to 8 hours 10 minutes)**. These are retrospective estimates, **not independently measured benchmarks**, and exclude all upstream forcing generation and Envision/OrCoast/SFINCS simulations. They also do not establish minimum CPU or RAM requirements.

The representative Zenodo archive contains one selected simulation index per required scenario, while the Acute demonstration retains the three scenario outputs with their internal 1,000 Monte Carlo iterations. The existing Python scripts retain their full-ensemble configuration. **Execution time for a selected-index demonstration has not yet been benchmarked**; no proportional speedup is claimed. A future test may refine these estimates and document any index selection needed to process the reduced raw archive.

## Code and data availability

- **Python code and full processed results:** https://github.com/jianqiaoren123/Coastal-MultiHazard-Resilience.
- **Representative raw Envision simulations:** Zenodo `Simulations.zip` (DOI: https://doi.org/10.5281/zenodo.23720608; reserved, pending publication). The archive contains representative simulation outputs and required input DBF files. The complete processed ensemble results supporting the manuscript are provided in the GitHub repository.
- **Envision source:** https://github.com/boltej/Envision.
- **OrCoast source:** http://envweb.bee.oregonstate.edu/GitServer/OrCoast.git. This is the existing repository address; **access by editors/reviewers has not yet been verified**. A reviewer-accessible or archived manuscript-specific version is being coordinated with its maintainer.
- **MUSCLE/TESLA code and forcing dataset:** https://doi.org/10.17603/ds2-mr46-5g54.
- **Shoreline observations and rates:** https://doi.org/10.17603/ds2-59cy-n043.
- **SFINCS source:** https://github.com/Deltares/SFINCS.

The code and datasets are provided to document and support reproduction of the analyses presented in the manuscript. The representative raw simulation archive does not contain the full simulation ensemble. Copyright and licensing terms for this repository and the OrCoast application must be confirmed with the relevant rights holders before public release.
