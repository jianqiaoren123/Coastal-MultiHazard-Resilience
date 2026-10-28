Steps for result analysis:
-1. Analyze simulations and save DETAILED RESULTS (per-simulation and average) for plots and reporting to xx.csv by running:

ChronicHazard_analysis_detailed_results_PerSim.py

Outputs:
Statistics_Chronic_CumulativeCost_PerSim.csv
Statistics_Chronic_Metric_PerSim.csv
Statistics_Chronic_AbsoluteBenefit_PerSim.csv
Statistics_Chronic_RelativeBenefit_PerSim.csv
Statistics_Chronic_CostBenefit_PerSim.csv

-2. Calculate present value (PV) and net present value (NPV) (i.e., economic analysis) by running 
Coastal-MultiHazard-Resilience/Code/EconomicAnalysis/chronic_economics_PerSim.py

Output:
Coastal-MultiHazard-Resilience/Results/EconomicAnalysis/
Results_Chronic_Economics_CumulativeCost_PerSim.csv
Results_Chronic_Economics_Baseline_PerSim.csv
Results_Chronic_Economics_Proactive_PerSim.csv
Results_Chronic_Economics_NPV_PerSim.csv

Note: To test Sensitivity of Results to Economic Assumptions, run
Coastal-MultiHazard-Resilience/Code/EconomicAnalysis/chronic_economics_sensitivity_PerSim.py, with inputs files
AND different Economic Assumptions
Output:
Coastal-MultiHazard-Resilience/Results/EconomicAnalysis/
Results_Chronic_Economics_CumulativeCost_Sensitivity_PerSim.csv
Results_Chronic_Economics_Baseline_Sensitivity_PerSim.csv
Results_Chronic_Economics_Proactive_Sensitivity_PerSim.csv
Results_Chronic_Economics_NPV_Sensitivity_PerSim.csv
Later, will plot the averaged NPVs over simulations and SLRs for Protect, Realign in selected years (e.g., 2030,2050,2070,2090) under selected assumptions,
see Coastal-MultiHazard-Resilience/Code/EconomicAnalysis/Plot_economic_sensitivity.py

-3. Plot DETAILED, SUMMARY (check), and COMBINED (manuscript) FIGURES and save key data for Main figures by running:
ChronicHazard_plots_PV.py

Outputs:
Figures that would be included in manuscript:
Main_CumulativeCost_PV
Main_Physical_3x2_PV
Main_Social_3x2_PV
Main_Economic_3x2_PV
Main_NPV

Key data that are used for/in figures:
Results_report_Chronic_PV_1.csv
Results_report_Chronic_PV_2.csv

