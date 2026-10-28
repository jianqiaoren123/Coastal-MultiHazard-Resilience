Steps for result analysis for Corner1 (other 3 tests are similar):
-1. Analyze simulations and save DETAILED RESULTS (per-simulation and average) for plots and reporting to xx.csv by running:

ChronicHazard_Corner1_analysis_detailed_results_PerSim.py

Outputs:
Statistics_Chronic_Corner1_CumulativeCost_PerSim.csv
Statistics_Chronic_Corner1_Metric_PerSim.csv
Statistics_Chronic_Corner1_AbsoluteBenefit_PerSim.csv
Statistics_Chronic_Corner1_RelativeBenefit_PerSim.csv
Statistics_Chronic_Corner1_CostBenefit_PerSim.csv

-2. Calculate present value (PV) and net present value (NPV) (i.e., economic analysis) by running 
Coastal-MultiHazard-Resilience/Code/EconomicAnalysis/chronic_corner1_economics_PerSim.py

Output:
Coastal-MultiHazard-Resilience/Results/EconomicAnalysis/
Results_Chronic_Corner1_Economics_CumulativeCost_PerSim.csv
Results_Chronic_Corner1_Economics_Baseline_PerSim.csv
Results_Chronic_Corner1_Economics_Proactive_PerSim.csv
Results_Chronic_Corner1_Economics_NPV_PerSim.csv

-3. Plot DETAILED, SUMMARY (check), and COMBINED (manuscript) FIGURES and save key data for Main figures by running:
ChronicHazard_Corner1_plots_PV.py

Outputs:
Figures that could be included in manuscript:
Main_CumulativeCost_PV_Corner1
Main_Physical_3x2_PV_Corner1
Main_Social_3x2_PV_Corner1
Main_Economic_3x2_PV_Corner1
Main_NPV_Corner1

Key data that are used for/in figures:
Results_report_Chronic_PV_1_Corner1.csv
Results_report_Chronic_PV_2_Corner1.csv


