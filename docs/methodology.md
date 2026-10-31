# Methodology

## 1. Dataset
`Waste_Management_Analytics_300_Records.csv`: 300 rows × 7 columns (Year, State, Waste_Type and four TPD quantities); 3 years (2020–2022), 10 states, 10 waste categories, a complete grid (10 × 3 × 10).

**Provenance is unverified.** The file contains no source information, and its very uniform state recycling rates (about 41–42%) suggest synthetic data. It is not described as official government data, and results show how the method behaves, not real-world performance of the named states.

**Units.** TPD = tonnes per day. Summing TPD across rows gives a summed daily rate, not annual tonnage.

## 2. Validation (Module 1)
A record is rejected, with a reason stored in `rejected_records`, if it has: missing or non-numeric values; a negative quantity; a year outside 2000–2100 (sanity check); collected > generated; treated > collected; recycled > treated; or an exact or key duplicate (Year+State+Waste_Type; first kept). Text fields are whitespace-trimmed. Zero quantities are valid. Result on the provided file: 0 issues, 300 records retained.

## 3. Indicators (Module 2)
- Collection efficiency (CE) = Collected / Generated × 100
- Treatment efficiency (TE) = Treated / Collected × 100
- Recycling rate (RR) = Recycled / Treated × 100 (denominator is *treated* waste, as specified for this project; note that other sources define recycling against generated waste)

Aggregates are **ratios of summed quantities**, never averages of row percentages. A denominator that is zero, negative or missing gives NaN (shown as "n/a"), never 0% or infinity.

## 4. Priority classification (Module 3)
1. For each State-Year aggregate (all categories combined), compute CE, TE, RR from the sums.
2. Composite score = (CE + TE + RR) / 3, with equal weights. It is NaN if any component is NaN.
3. Take the quantiles of the composite scores of the compared units (30 state-year units in the default view). Score ≤ Q(1/3) → **High**; ≤ Q(2/3) → **Medium**; otherwise **Normal**.

The cut-offs are *relative* (they depend on the units compared) and are **project-defined, not official standards**. They are adjustable in the sidebar. Waste categories are ranked and prioritised separately with the same method, so state-level and category-level conclusions are never mixed.

On the provided data (default cut-offs: High ≤ 59.0, Medium ≤ 66.7): Uttar Pradesh, Rajasthan and Odisha (all three years) plus West Bengal 2020 fall in High. By category, Construction, Other, Textile and Biomedical are High, mostly because of low recycling rates.

## 5. Rule-based insights
Defaults are project-defined and editable in the sidebar (`config.InsightThresholds`):

| Rule | IF | THEN |
|---|---|---|
| R1 | CE < 70% | collection-performance concern |
| R2 | TE < 60% | treatment-performance concern |
| R3 | RR < 30% | recycling-performance concern |
| R4 | indicator rose by more than 1 pp vs the previous year | improvement |
| R5 | indicator fell by more than 1 pp vs the previous year | deterioration |

Concern rules (R1–R3) are evaluated per state and per category for the latest selected year; R4/R5 compare the latest two selected years (state, category and overall). Changes within ±1 pp are treated as stable and produce no insight. The thresholds are not official standards; they are analytical parameters chosen for this project.

**Focused analysis (Insights page).** The page-level selectors (state, waste type, year, indicator) only narrow the data that the sidebar filters already selected; the rules above then run unchanged on that narrowed data, so every finding is calculated from the filtered dataset. Choosing a year means "as of that year": that year is checked against the thresholds and compared with the previous selected year. When a single state and/or waste type is chosen, the rules would report the same numbers as a State, a Category and an Overall finding, so only one of them is shown, labelled with its context. The performance summary shows the indicator values of the focused data (computed as in section 3) with their values in every selected year. The page shows the five most important findings (ordered High, Medium, Positive, then by size) unless "Show all findings" is switched on.

## 6. Limitations
- Unverified, probably synthetic data; three years only.
- Relative priority: a "High" unit is the lowest third of the compared units, not necessarily poor in absolute terms.
- Equal weighting of three indicators is a simplifying choice.
- Year-on-year differences are descriptive; no causal claims are made.

## 7. Head-to-head state comparison
Any two different states can be compared on the Year and Waste-category filters currently selected (the State filter does not restrict the choice). For each state the three indicators are computed from the **summed** quantities of its selected records, and the composite score is the same equal-weight mean used for priority. For each indicator the state with the higher percentage is reported as *better*; differences smaller than 0.05 percentage points (below the displayed precision of 0.1) are reported as a *tie*, and an indicator that cannot be computed (zero denominator) is reported as *n/a*. The state with the higher composite score is the overall leader. Nothing here changes the indicator formulas.

## 8. Performance heatmap
Rows are states or waste categories (computed from the filtered records), columns are the three indicators. *Absolute* colours every cell on a single 0–100% scale so columns can be compared with each other. *Relative* rescales each indicator between its own minimum and maximum to show the spread within that indicator; labels always show the real percentage.

## 9. Explainable priority
The explanation does not alter the classification; it reads the output of the existing quantile method and states why a unit received its level:
1. the unit's composite score and the three indicators it is made from;
2. its rank among the compared units (1 = lowest score);
3. the High and Medium cut-offs (the configured quantiles of the scores) and which side of them the score falls on, with the margin to the next level;
4. the indicator with the largest shortfall against the median of the compared units;
5. which indicators are below the project thresholds.

**Suggestions** are produced by simple IF-THEN rules (IF an indicator is below its project threshold THEN a generic improvement action for collection, treatment or recycling; IF an indicator fell by more than the change tolerance THEN suggest investigating the decline; IF High/Medium and the weakest indicator is not below a threshold THEN point to the relative gap; IF nothing applies THEN maintain and monitor). They are indicative only. Thresholds and cut-offs are project-defined, relative and **not official standards**, and the suggestions are not official guidance.

## 10. Exports
CSV tables (KPI summary, state, year and category summaries with composite and priority, state-year priority and trend, insights, row-level records with indicators, and the selected state comparison) are written from the same functions the dashboard uses, for the current filters. Rates and scores are exported unrounded and TPD quantities at 2 decimals (the precision of the source data); the PDF formats the unrounded values to one decimal exactly as the dashboard does. This avoids double rounding: for example a collection efficiency of 69.649... shows 69.6 on the dashboard and in the PDF, and pre-rounding it to 69.65 would make a reader's rounding show 69.7. The ZIP adds a README with the title, filters, thresholds and notes. The PDF contains the title, filters, KPIs, state performance table and chart, the state comparison, category priority, priority findings, rule-based insights and notes. The PDF is produced by a small pure-Python writer (no extra library), because the project is restricted to Python, pandas, SQLite, Streamlit and Plotly.

## 11. Additional limitations
- The PDF uses the standard Helvetica font, so characters outside Latin-1 are replaced (for example ≤ becomes <=).
- Suggestions are generic rule-based text; they do not use local operational data and are not recommendations from an authority.
- Priority levels depend on which units are compared: changing filters can change a unit's level.
