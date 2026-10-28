Steps:
-1. Analyze simulations and save DETAILED RESULTS for plots and reporting to xx.csv by running:
BothHazard_analysis_detailed_results_PerSim.py

Outputs:
Statistics_Both_CumulativeCost_Annual_PerSim.csv
Statistics_Both_Metric_Annual_PerSim.csv
Statistics_Both_AbsoluteBenefit_Annual_PerSim.csv
Statistics_Both_RelativeBenefit_Annual_PerSim.csv
Statistics_Both_CostBenefit_Annual_PerSim.csv

-2. Calculate present value (PV) and net present value (NPV) (i.e., economic analysis) by running 
Coastal-MultiHazard-Resilience/Code/EconomicAnalysis/combined_economics_PerSim.py

Output:
Coastal-MultiHazard-Resilience/Results/EconomicAnalysis/
Results_Combined_Economics_CumulativeCost_PerSim.csv
Results_Combined_Economics_Baseline_PerSim.csv
Results_Combined_Economics_Proactive_PerSim.csv
Results_Combined_Economics_NPV_PerSim.csv

Note: To test Sensitivity of Results to Economic Assumptions, run
Coastal-MultiHazard-Resilience/Code/EconomicAnalysis/combined_economics_sensitivity_PerSim.py, with inputs files
AND different Economic Assumptions
Output:
Coastal-MultiHazard-Resilience/Results/EconomicAnalysis/
Results_Combined_Economics_CumulativeCost_Sensitivity_PerSim.csv
Results_Combined_Economics_Baseline_Sensitivity_PerSim.csv
Results_Combined_Economics_Proactive_Sensitivity_PerSim.csv
Results_Combined_Economics_NPV_Sensitivity_PerSim.csv
Later, will plot the averaged NPVs over simulations and SLRs for different policies in acute event years (i.e.,2050,2070,2090) under selected assumptions,
see Coastal-MultiHazard-Resilience/Code/EconomicAnalysis/Plot_economic_sensitivity.py

-3. Plot COMBINED (manuscript) FIGURES and save summary results for manuscript writing by running:
BothHazard_plots_PV.py

Outputs:
Figures (Main body and SI)---need plot new figures and keep codes for old figures such as compound and erosion co-benefits!
Figures that would be included in manuscript:

Key data that are used for/in figures:
Results_report_Both_PV_1.csv
Results_report_Both_PV_2.csv

Note: For Supplementary Table~/ref{tab:SI_AC1_baseline},
Total economic loss ($M): use Results_Combined_Economics_Baseline_PerSim.csv
Flood economic loss ($M): use Results_report_Chronic_PV_1.csv


