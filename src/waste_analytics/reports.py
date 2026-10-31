"""Analytical report export: CSV tables, a ZIP bundle and a PDF summary.

Every number comes from the same functions the dashboard uses (indicators, priority,
insights, compare), so exported figures match what is shown on screen.
CSV rates and scores are exported UNROUNDED and TPD quantities to 2 decimals (the precision of the source data), so
rounding any exported rate to the dashboard's 1 decimal reproduces the dashboard exactly. The PDF formats the
unrounded values itself, exactly as the dashboard does. (Pre-rounding rates, even to 4 decimals, can flip the
1-decimal display of a value such as 58.349968 to 58.4.)
"""
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from . import config as C
from . import pdf_report as P
from .compare import Comparison, comparison_export
from .indicators import add_indicators, aggregate, overall_summary, year_over_year
from .insights import generate_insights
from .priority import priority_by_category, priority_by_state_year

TITLE = "Waste Management Analytics System - Summary Report"
NOTES = [
    "Quantities are in TPD (tonnes per day); summed values are summed daily rates, not annual tonnage.",
    "Dataset provenance is unverified (it appears synthetic); it is not official government data.",
    "All thresholds and priority cut-offs are project-defined analytical parameters, not official standards.",
    "Collection efficiency = Collected / Generated x 100; treatment efficiency = Treated / Collected x 100; "
    "recycling rate = Recycled / Treated x 100. Aggregates use ratios of summed quantities.",
]
LABEL = {C.CE: "Collection efficiency (%)", C.TE: "Treatment efficiency (%)", C.RR: "Recycling rate (%)",
         C.SCORE: "Composite score"}


@dataclass
class ReportData:
    """Everything the exports need, computed once from the filtered data."""
    filters: dict
    kpis: dict
    tables: dict            # name -> DataFrame for CSV export (rates unrounded, TPD quantities at 2 decimals)
    full: dict              # same tables, unrounded: the PDF formats from these, exactly like the dashboard
    comparison: Comparison | None
    cutoffs: dict
    thresholds: C.InsightThresholds
    priority_config: C.PriorityConfig


def describe_filters(sel_years, sel_states, sel_types, all_years, all_states, all_types) -> dict:
    def fmt(sel, allv):
        return "All (%d)" % len(allv) if set(sel) == set(allv) else ", ".join(map(str, sorted(sel)))
    return {"Years": fmt(sel_years, all_years), "States": fmt(sel_states, all_states),
            "Waste categories": fmt(sel_types, all_types)}


def _round(df: pd.DataFrame) -> pd.DataFrame:
    """Round only TPD quantity columns (2 dp, exact for the source data); never round rates or scores."""
    return df.round({c: 2 for c in df.columns if "TPD" in str(c)})


def build_report_data(df: pd.DataFrame, filters: dict, thresholds: C.InsightThresholds,
                      pcfg: C.PriorityConfig, comparison: Comparison | None = None) -> ReportData:
    """Compute all exported tables from the filtered frame `df` (non-empty)."""
    if df.empty:
        raise ValueError("There are no records to export for the current filters")
    kpis = overall_summary(df)

    sy = priority_by_state_year(df, pcfg)
    cp = priority_by_category(df, pcfg)
    states = aggregate(df, C.STATE)
    states[C.SCORE] = states[C.INDICATORS].mean(axis=1, skipna=False)
    states["Rank_by_Composite"] = states[C.SCORE].rank(ascending=False, method="min")
    states = states.sort_values("Rank_by_Composite")
    years = aggregate(df, C.YEAR)
    yoy = year_over_year(df, C.STATE)
    ins = generate_insights(df, thresholds)

    kpi_rows = [("Records selected", len(df))]
    kpi_rows += [(k.replace("_", " "), round(float(kpis[k]), 2)) for k in C.QTY_COLS + C.INDICATORS]
    tables = {
        "kpi_summary": pd.DataFrame({"Metric": [r[0] for r in kpi_rows], "Value": pd.Series([r[1] for r in kpi_rows], dtype=object)}),
        "state_summary": states,
        "year_summary": years,
        "category_summary_priority": cp,
        "state_year_priority": sy,
        "state_year_trend": yoy,
        "insights": ins,
        "records_with_indicators": add_indicators(df),
    }
    if comparison is not None:
        tables["state_comparison"] = comparison_export(comparison)
    rounded = {k: _round(v) if k != "insights" else v for k, v in tables.items()}
    return ReportData(filters, kpis, rounded, tables, comparison, sy.attrs.get("cutoffs", {}), thresholds, pcfg)


# ------------------------------------------------------------------ CSV / ZIP
def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def readme_text(rd: ReportData) -> str:
    lines = [TITLE, "Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M"), "", "Selected filters:"]
    lines += [f"  {k}: {v}" for k, v in rd.filters.items()]
    t = rd.thresholds
    lines += ["", "Project-defined thresholds (not official standards):",
              f"  low collection efficiency < {t.low_collection:g}%, low treatment efficiency < {t.low_treatment:g}%, "
              f"low recycling rate < {t.low_recycling:g}%, stable change within +/-{t.change_tolerance:g} pp",
              f"  priority quantiles: High <= {rd.priority_config.high_quantile:.0%}, "
              f"Medium <= {rd.priority_config.medium_quantile:.0%} of composite scores"]
    lines += [""] + NOTES + ["", "Files:"] + [f"  {name}.csv" for name in rd.tables]
    return "\n".join(lines) + "\n"


def zip_bytes(rd: ReportData) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", readme_text(rd))
        for name, table in rd.tables.items():
            z.writestr(f"{name}.csv", csv_bytes(table))
    return buf.getvalue()


# ------------------------------------------------------------------ PDF
def _f1(v) -> str:
    return "n/a" if pd.isna(v) else f"{v:.1f}"


def build_pdf(rd: ReportData) -> bytes:
    doc = P.PDFDocument(TITLE, "Waste Management Analytics System")
    doc.header_band("Waste Management Analytics System", "Analytical summary report - B.Tech CSE academic project")

    doc.heading("1. Report scope")
    for k, v in rd.filters.items():
        doc.paragraph(f"{k}: {v}")
    doc.paragraph(f"Records analysed: {int(rd.full['kpi_summary'].iloc[0]['Value'])}")
    doc.bullets(NOTES[:3])

    doc.heading("2. Key performance indicators")
    k = rd.kpis
    rows = [("Waste generated (TPD, summed)", f"{k[C.GEN]:,.0f}"), ("Waste collected (TPD, summed)", f"{k[C.COL]:,.0f}"),
            ("Waste treated (TPD, summed)", f"{k[C.TRT]:,.0f}"), ("Waste recycled (TPD, summed)", f"{k[C.REC]:,.0f}"),
            ("Collection efficiency", _f1(k[C.CE]) + "%"), ("Treatment efficiency", _f1(k[C.TE]) + "%"),
            ("Recycling rate", _f1(k[C.RR]) + "%")]
    doc.table(["Indicator", "Value"], rows, [300, 120], ["l", "r"], 9)

    doc.heading("3. State performance")
    st = rd.full["state_summary"]
    doc.table(["State", "Collection %", "Treatment %", "Recycling %", "Composite", "Rank"],
              [(r[C.STATE], _f1(r[C.CE]), _f1(r[C.TE]), _f1(r[C.RR]), _f1(r[C.SCORE]), f"{int(r['Rank_by_Composite'])}")
               for _, r in st.iterrows()], [130, 78, 78, 78, 70, 50], ["l", "r", "r", "r", "r", "r"])
    ind_col = {C.CE: P.GREEN, C.TE: (0.36, 0.70, 0.51), C.RR: (0.85, 0.63, 0.11)}
    doc.bar_chart([(r[C.STATE], [(r[c], ind_col[c]) for c in C.INDICATORS]) for _, r in st.iterrows()], 100,
                  [("Collection", ind_col[C.CE]), ("Treatment", ind_col[C.TE]), ("Recycling", ind_col[C.RR])])

    if rd.comparison is not None:
        c = rd.comparison
        doc.heading(f"4. State comparison: {c.state_a} vs {c.state_b}")
        t = c.table
        doc.table(["Indicator", c.state_a, c.state_b, "Difference (pp)", "Better"],
                  [(LABEL[r["Indicator"]], _f1(r["Value_A"]), _f1(r["Value_B"]),
                    "n/a" if pd.isna(r["Difference_pp"]) else f"{r['Difference_pp']:+.1f}", r["Better"])
                   for _, r in t.iterrows()], [150, 80, 80, 90, 100], ["l", "r", "r", "r", "l"])
        doc.paragraph(f"Indicators won (of 3): {c.state_a} {c.wins[c.state_a]}, {c.state_b} {c.wins[c.state_b]}, "
                      f"ties {c.wins['Tie']}. Higher composite score: {c.leader}.")

    n = 5 if rd.comparison is not None else 4
    doc.heading(f"{n}. Waste category performance and priority")
    cp = rd.full["category_summary_priority"]
    doc.table(["Category", "Collection %", "Treatment %", "Recycling %", "Composite", "Priority"],
              [(r[C.WTYPE], _f1(r[C.CE]), _f1(r[C.TE]), _f1(r[C.RR]), _f1(r[C.SCORE]), r["Priority"])
               for _, r in cp.iterrows()], [110, 80, 80, 80, 70, 70], ["l", "r", "r", "r", "r", "l"])

    doc.heading(f"{n + 1}. Priority findings (state-year units)")
    sy = rd.full["state_year_priority"]
    counts = sy["Priority"].value_counts()
    cut = rd.cutoffs
    doc.paragraph(
        "Method: composite score = (collection + treatment + recycling) / 3, computed from aggregated quantities for "
        "each state-year. Units are classified by quantile of the composite scores (project-defined, relative, not an "
        "official standard)." + (f" Current cut-offs: High <= {cut['high']:.1f}, Medium <= {cut['medium']:.1f}, "
                                 f"Normal above." if cut else ""))
    doc.paragraph("Units per level: " + ", ".join(f"{lvl} {int(counts.get(lvl, 0))}" for lvl in ("High", "Medium", "Normal"))
                  + f" (total {len(sy)}).", bold=True)
    high = sy[sy["Priority"] == "High"]
    if high.empty:
        doc.paragraph("No state-year unit is classified High for the current selection.")
    else:
        doc.table(["State", "Year", "Collection %", "Treatment %", "Recycling %", "Composite"],
                  [(r[C.STATE], f"{int(r[C.YEAR])}", _f1(r[C.CE]), _f1(r[C.TE]), _f1(r[C.RR]), _f1(r[C.SCORE]))
                   for _, r in high.iterrows()], [110, 50, 80, 80, 80, 70], ["l", "r", "r", "r", "r", "r"])

    doc.heading(f"{n + 2}. Rule-based insights")
    ins = rd.full["insights"]
    if ins.empty:
        doc.paragraph("No rule fired for the current selection and thresholds.")
    else:
        kc = ins["Kind"].value_counts()
        t = rd.thresholds
        doc.paragraph(f"Insights raised: Concern {int(kc.get('Concern', 0))}, Deterioration "
                      f"{int(kc.get('Deterioration', 0))}, Improvement {int(kc.get('Improvement', 0))}. "
                      f"Project thresholds: collection < {t.low_collection:g}%, treatment < {t.low_treatment:g}%, "
                      f"recycling < {t.low_recycling:g}%, stable within +/-{t.change_tolerance:g} pp.")
        doc.paragraph("Concerns", bold=True, color=P.FOREST)
        doc.bullets(ins[ins["Kind"] == "Concern"]["Insight"].tolist() or ["None."], 8.5)
        det = ins[ins["Kind"] == "Deterioration"]["Insight"].tolist()
        if det:
            doc.paragraph("Deteriorations", bold=True, color=P.FOREST)
            doc.bullets(det, 8.5)

    doc.heading(f"{n + 3}. Notes")
    doc.bullets(NOTES)
    return doc.to_bytes()
