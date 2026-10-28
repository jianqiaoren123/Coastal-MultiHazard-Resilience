The detailed analysis uses the `impr_value > 10000` building selection from the Acute Baseline scenario IDU (earliest `idu_Year*_Acute-Baseline_Run0.dbf` in `Simulations/Acute/Acute-Baseline/Run0/`) and the `REMOVED` field from the Realign scenario IDU. The scenario IDU must retain the same record order as the building-damage CSVs. `Results/Acute/TotalNumber_Statistics.csv` supplies the reference building, population, and property-value totals.

Steps:

-1. Analyze simulations, plot DETAILED figures for checking, and save DETAILED RESULTS (per-simulation and averaged results) for plots by running:
AcuteHazard_analysis_detailed_results_PerSim.py

Outputs:
Statistics_Acute_PerSim.csv (per-simulation and averaged)

-2. Generate RESULTS for reporting in manuscript (physical and social) and calculating present value (PV) and net present value (NPV) results for economic analysis by running:
AcuteHazard_reporting_discussion_PerSim.py

Outputs:
Results_report_Acute_PerSim.csv

-3. Calculate present value (PV) and net present value (NPV) (i.e., economic analysis) by running
Coastal-MultiHazard-Resilience/Code/EconomicAnalysis/acute_economics_PerSim.py, with inputs Results_report_Acute_PerSim.csv
 
Outputs:
Coastal-MultiHazard-Resilience/Results/EconomicAnalysis/Results_Acute_Economics_PerSim.csv (per-simulation and averaged)

Note: To test Sensitivity of Results to Economic Assumptions, run
Coastal-MultiHazard-Resilience/Code/EconomicAnalysis/acute_economics_sensitivity_PerSim.py, with inputs Results_report_Acute_PerSim.csv
AND different Economic Assumptions
Outputs:
Coastal-MultiHazard-Resilience/Results/EconomicAnalysis/Results_Acute_Economics_Sensitivity_PerSim.csv (per-simulation and averaged)
Later, will plot the averaged NPVs over simulations for Protect, Realign under selected assumptions, see Coastal-MultiHazard-Resilience/Code/EconomicAnalysis/Plot_economic_sensitivity.py

-4. Plot SUMMARY FIGURES for manuscript (physical, social, and present value (PV)-based economic loss figure) and save summary results for manuscript Results and Discussions by running 
AcuteHazard_summary_plots_PV.py,

Outputs:
Figs reported in manuscript: 
Summary_Damage_6panel.png/.svg
Summary_LifeSafety_6panel.png/.svg
Summary_EconLoss_6panel_PV.png/.svg
and not reported
Summary_PopImp_6panel.png/.svg
Summary_NPV_2bar_PV.png/.svg

Results_report_Acute_PV.csv, which includes all the mean, std, CoV, and 95%CI that are used for plotting the summary figures and NPV, and manuscript writing. 