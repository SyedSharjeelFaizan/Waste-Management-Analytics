"""Plotly figure builders for the dashboard (forest-green analytics theme)."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import config as C

LABELS = {C.CE: "Collection efficiency (%)", C.TE: "Treatment efficiency (%)",
          C.RR: "Recycling rate (%)", C.SCORE: "Composite score",
          C.GEN: "Generated (TPD)", C.COL: "Collected (TPD)",
          C.TRT: "Treated (TPD)", C.REC: "Recycled (TPD)",
          C.STATE: "State", C.YEAR: "Year", C.WTYPE: "Waste category"}

SHORT = {k: v.replace(" (%)", "").replace(" (TPD)", "") for k, v in LABELS.items()}   # tick / legend text

# One colour per indicator, reused in every chart (same values as --ind-* in app/style.css)
INDICATOR_COLORS = {C.CE: "#0F4D35", C.TE: "#2FAF7F", C.RR: "#D8A431"}
PRIORITY_COLORS = {"High": "#C8483A", "Medium": "#E3A82B", "Normal": "#2E8B57",
                   "Unclassified": "#9AA5A0"}
FLOW_COLORS = ["#0F3D2A", "#1B6B49", "#3DB88A", "#A9DCC3"]
CATEGORICAL = ["#0F4D35", "#D8A431", "#3F7CAC", "#C8483A", "#7A5C9E",
               "#2AA198", "#8C6D46", "#E07B39", "#6B8E23", "#5F6B66"]
GREEN_SEQ = [[0, "#E3F1E8"], [1, "#0F3D2A"]]
HEAT_SCALE = [[0, "#D98A7C"], [0.5, "#F4EBC7"], [1, "#3E9E72"]]
INK, MUTED, GRID = "#15261D", "#66736B", "#ECE8DB"
FONT = "Source Sans, Segoe UI, system-ui, sans-serif"   # Source Sans ships with Streamlit
BAR_RADIUS = 6


def _style(fig: go.Figure, height: int = 400, legend: bool = True, grid: str = "y") -> go.Figure:
    """Shared look. `grid` is the axis whose gridlines are drawn ("x", "y" or "") so the value axis is
    guided and the category axis stays clean."""
    fig.update_layout(
        template="plotly_white", height=height, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=8, r=20, t=18, b=8),
        font=dict(family=FONT, size=13, color=INK),
        colorway=CATEGORICAL, showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0, title_text="",
                    font=dict(size=12, color=INK), itemsizing="constant"),
        hoverlabel=dict(bgcolor="white", bordercolor="#D6D1C0", font=dict(family=FONT, size=13, color=INK)),
        title=None,
    )
    axis = dict(zeroline=False, showline=False, ticks="", tickfont=dict(size=12, color=MUTED),
                title_font=dict(size=12, color=MUTED), title_standoff=10)
    fig.update_xaxes(showgrid="x" in grid, gridcolor=GRID, gridwidth=1, **axis)
    fig.update_yaxes(showgrid="y" in grid, gridcolor=GRID, gridwidth=1, **axis)
    fig.update_traces(marker_cornerradius=BAR_RADIUS, selector=dict(type="bar"))
    return fig


def _fmt(v) -> str:
    return "n/a" if pd.isna(v) else f"{v:.1f}"


def indicator_bar(agg: pd.DataFrame, name_col: str, indicator: str,
                  threshold: float | None = None) -> go.Figure:
    """Horizontal ranking bars for one indicator, optional project-threshold line."""
    d = agg.sort_values(indicator)
    fig = go.Figure(go.Bar(
        x=d[indicator], y=d[name_col], orientation="h", marker_color=INDICATOR_COLORS[indicator],
        text=[_fmt(v) + ("" if pd.isna(v) else "%") for v in d[indicator]], textposition="outside",
        cliponaxis=False, hovertemplate="<b>%{y}</b><br>" + LABELS[indicator] + ": %{x:.1f}%<extra></extra>"))
    if threshold is not None:
        fig.add_vline(x=threshold, line_dash="dash", line_color="#C8483A", line_width=1.5,
                      annotation_text=f"Project threshold {threshold:g}%", annotation_position="top",
                      annotation_font=dict(size=10, color="#C8483A"))
    fig.update_xaxes(range=[0, 108], title=LABELS[indicator])
    fig.update_yaxes(title="")
    return _style(fig, max(320, 34 * len(d) + 70), legend=False, grid="x")


def trend_lines(agg: pd.DataFrame) -> go.Figure:
    """Year-wise overall indicators from a frame with Year + indicator columns."""
    fig = go.Figure()
    label_pos = {C.CE: "top center", C.TE: "bottom center", C.RR: "top center"}
    for ind in C.INDICATORS:
        fig.add_trace(go.Scatter(
            x=agg[C.YEAR], y=agg[ind], name=SHORT[ind], mode="lines+markers+text",
            line=dict(color=INDICATOR_COLORS[ind], width=3), marker=dict(size=9),
            text=[_fmt(v) for v in agg[ind]], textposition=label_pos[ind], textfont=dict(size=11),
            hovertemplate="Year %{x}<br>" + LABELS[ind] + ": %{y:.1f}%<extra></extra>"))
    fig.update_xaxes(dtick=1, title="Year")
    fig.update_yaxes(range=[0, 100], title="Percent (%)")
    return _style(fig, 380)


def state_year_lines(agg: pd.DataFrame, indicator: str) -> go.Figure:
    fig = px.line(agg, x=C.YEAR, y=indicator, color=C.STATE, markers=True, labels=LABELS,
                  color_discrete_sequence=CATEGORICAL)
    fig.update_traces(line=dict(width=2.4), marker=dict(size=7),
                      hovertemplate="<b>%{fullData.name}</b><br>Year %{x}<br>%{y:.1f}%<extra></extra>")
    fig.update_xaxes(dtick=1, title="Year")
    fig.update_yaxes(title=LABELS[indicator])
    return _style(fig, 430)


def category_share_bar(agg: pd.DataFrame, qty: str = C.GEN) -> go.Figure:
    """Share (%) of a quantity by waste category, sorted; one colour keeps it uncluttered."""
    d = agg[[C.WTYPE, qty]].copy()
    total = d[qty].sum()
    d["Share"] = d[qty] / total * 100 if total > 0 else float("nan")
    d = d.sort_values("Share")
    fig = go.Figure(go.Bar(
        x=d["Share"], y=d[C.WTYPE], orientation="h", marker_color="#2E8B57",
        text=[f"{v:.1f}%" for v in d["Share"]], textposition="outside", cliponaxis=False,
        customdata=d[qty], hovertemplate="<b>%{y}</b><br>Share: %{x:.1f}%<br>"
        + LABELS[qty] + " (summed): %{customdata:,.0f}<extra></extra>"))
    fig.update_xaxes(title=f"Share of {LABELS[qty].replace(' (TPD)', '').lower()} waste (%)", range=[0, max(d["Share"].max() * 1.18, 5)])
    fig.update_yaxes(title="")
    return _style(fig, 380, legend=False, grid="x")


def flow_bars(totals: dict) -> go.Figure:
    """Waste-flow funnel of summed daily rates: generated -> collected -> treated -> recycled."""
    names = [SHORT[c] for c in C.QTY_COLS]
    vals = [totals[c] for c in C.QTY_COLS]
    fig = go.Figure(go.Bar(
        x=names, y=vals, marker_color=FLOW_COLORS, text=[f"{v:,.0f}" for v in vals],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>%{y:,.0f} TPD (summed)<extra></extra>"))
    fig.update_yaxes(title="TPD (sum of daily rates)", range=[0, max(vals) * 1.15])
    fig.update_xaxes(title="")
    return _style(fig, 380, legend=False)


def grouped_indicator_bars(agg: pd.DataFrame, name_col: str) -> go.Figure:
    fig = go.Figure()
    for ind in C.INDICATORS:
        fig.add_trace(go.Bar(
            x=agg[name_col], y=agg[ind], name=SHORT[ind], marker_color=INDICATOR_COLORS[ind],
            hovertemplate="<b>%{x}</b><br>" + LABELS[ind] + ": %{y:.1f}%<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.25)
    fig.update_yaxes(range=[0, 100], title="Percent (%)")
    fig.update_xaxes(title="", tickangle=-30 if len(agg) > 6 else 0)
    return _style(fig, 400)


def priority_heatmap(prio: pd.DataFrame) -> go.Figure:
    """State x Year composite score heatmap (lower score = higher priority)."""
    pv = prio.pivot(index=C.STATE, columns=C.YEAR, values=C.SCORE)
    pv = pv.loc[pv.mean(axis=1).sort_values(ascending=False).index]
    fig = go.Figure(go.Heatmap(
        z=pv.values, x=[str(c) for c in pv.columns], y=pv.index, colorscale=HEAT_SCALE,
        text=pv.round(1).values, texttemplate="%{text}", textfont=dict(size=12, color=INK),
        xgap=3, ygap=3, colorbar=dict(title="Score", thickness=12, len=0.9),
        hovertemplate="<b>%{y}</b> (%{x})<br>Composite score: %{z:.1f}<extra></extra>"))
    fig.update_xaxes(title="Year", side="bottom")
    fig.update_yaxes(title="")
    return _style(fig, max(340, 38 * len(pv) + 80), legend=False, grid="")


def priority_bar(prio: pd.DataFrame, label_col: str) -> go.Figure:
    """Composite score per unit, coloured by priority status."""
    d = prio.sort_values(C.SCORE, ascending=False)
    fig = go.Figure()
    for level in ("High", "Medium", "Normal"):
        s = d[d["Priority"] == level]
        if s.empty:
            continue
        fig.add_trace(go.Bar(
            x=s[C.SCORE], y=s[label_col], orientation="h", name=level,
            marker_color=PRIORITY_COLORS[level], text=[f"{v:.1f}" for v in s[C.SCORE]],
            textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Composite score: %{x:.1f}<br>Priority: " + level + "<extra></extra>"))
    fig.update_xaxes(title="Composite score (mean of CE, TE, RR)", range=[0, 100])
    fig.update_yaxes(title="", categoryorder="array", categoryarray=list(d[label_col]))
    return _style(fig, max(320, 32 * len(d) + 80), grid="x")


# ---------------------------------------------------------------- head-to-head, heatmap, explainer
STATE_A_COLOR, STATE_B_COLOR = "#14532D", "#3F7CAC"


def head_to_head_bars(table: pd.DataFrame, a: str, b: str) -> go.Figure:
    """Grouped bars for two states over the three indicators (values from compare.compare_states)."""
    t = table[table["Indicator"].isin(C.INDICATORS)]
    labels = [SHORT[k] for k in t["Indicator"]]
    fig = go.Figure()
    for name, col, color in (("Value_A", a, STATE_A_COLOR), ("Value_B", b, STATE_B_COLOR)):
        fig.add_trace(go.Bar(
            x=labels, y=t[name], name=col, marker_color=color,
            text=[_fmt(v) + ("" if pd.isna(v) else "%") for v in t[name]], textposition="outside",
            cliponaxis=False, hovertemplate="<b>" + col + "</b><br>%{x}: %{y:.1f}%<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.3)
    fig.update_yaxes(range=[0, 110], title="Percent (%)")
    fig.update_xaxes(title="")
    return _style(fig, 380)


def head_to_head_trend(df: pd.DataFrame, a: str, b: str, indicator: str) -> go.Figure:
    """Year-wise trend of one indicator for two states (aggregate of summed quantities)."""
    from .indicators import aggregate
    fig = go.Figure()
    for name, color in ((a, STATE_A_COLOR), (b, STATE_B_COLOR)):
        agg = aggregate(df[df[C.STATE] == name], C.YEAR).sort_values(C.YEAR)
        fig.add_trace(go.Scatter(
            x=agg[C.YEAR], y=agg[indicator], name=name, mode="lines+markers+text",
            line=dict(color=color, width=3), marker=dict(size=9),
            text=[_fmt(v) for v in agg[indicator]], textposition="top center", textfont=dict(size=10),
            hovertemplate="<b>" + name + "</b><br>Year %{x}: %{y:.1f}%<extra></extra>"))
    fig.update_xaxes(dtick=1, title="Year")
    fig.update_yaxes(title=LABELS[indicator])
    return _style(fig, 340)


def performance_heatmap(agg: pd.DataFrame, name_col: str, mode: str = "absolute") -> go.Figure:
    """Rows (states or categories, in the order given) x the three indicators.

    mode="absolute": one 0-100 colour scale shared by all cells (values comparable across columns).
    mode="relative": each indicator column is scaled between its own min and max, to show the
    spread within a column; cell labels always show the real percentage.
    """
    names = list(agg[name_col])
    vals = agg[C.INDICATORS].to_numpy(dtype=float)
    if mode == "relative":
        z = vals.copy()
        for j in range(z.shape[1]):
            lo, hi = pd.Series(z[:, j]).min(), pd.Series(z[:, j]).max()
            z[:, j] = 0.5 if hi == lo else (z[:, j] - lo) / (hi - lo)
        zmin, zmax, bar = 0, 1, dict(title=dict(text="Within column", side="top"), tickvals=[0, 1], ticktext=["lowest", "highest"])
    else:
        z, zmin, zmax, bar = vals, 0, 100, dict(title=dict(text="Percent", side="top"), ticksuffix="%")
    text = [[_fmt(v) + ("" if pd.isna(v) else "%") for v in row] for row in vals]
    fig = go.Figure(go.Heatmap(
        z=z, x=[SHORT[k] for k in C.INDICATORS], y=names, colorscale=HEAT_SCALE, zmin=zmin, zmax=zmax,
        text=text, texttemplate="%{text}", textfont=dict(size=12, color=INK), xgap=3, ygap=3,
        customdata=vals, colorbar=dict(thickness=12, len=0.85, **bar),
        hovertemplate="<b>%{y}</b><br>%{x}: %{customdata:.1f}%<extra></extra>"))
    fig.update_xaxes(side="top", title="")
    fig.update_yaxes(title="", autorange="reversed")
    return _style(fig, max(340, 38 * len(names) + 90), legend=False, grid="")


def priority_position(labels, scores, selected: str, cutoffs: dict) -> go.Figure:
    """All compared units by composite score; the selected unit is highlighted, cut-offs are lines."""
    d = pd.DataFrame({"label": list(labels), "score": list(scores)}).sort_values("score", ascending=False)
    hi, med = cutoffs["high"], cutoffs["medium"]

    def color(s):
        return PRIORITY_COLORS["High"] if s <= hi else PRIORITY_COLORS["Medium"] if s <= med else PRIORITY_COLORS["Normal"]

    fig = go.Figure(go.Bar(
        x=d["score"], y=d["label"], orientation="h",
        marker=dict(color=[color(s) for s in d["score"]],
                    opacity=[1.0 if lbl == selected else 0.35 for lbl in d["label"]],
                    line=dict(color=INK, width=[2 if lbl == selected else 0 for lbl in d["label"]])),
        hovertemplate="<b>%{y}</b><br>Composite score: %{x:.1f}<extra></extra>"))
    for x, name, side in ((hi, f"High cut-off {hi:.1f}", "right"), (med, f"Medium cut-off {med:.1f}", "left")):
        fig.add_vline(x=x, line_dash="dash", line_color=MUTED, line_width=1.2)
        # label sits above the plot area, beside its line, so it never overlaps a bar
        fig.add_annotation(x=x, y=1, yref="paper", yanchor="bottom", xanchor=side, showarrow=False,
                           text=name, xshift=-6 if side == "right" else 6, font=dict(size=11, color=MUTED))
    fig.update_xaxes(title="Composite score (mean of CE, TE, RR)", range=[min(d["score"].min() - 5, hi - 5), 100])
    fig.update_yaxes(title="", categoryorder="array", categoryarray=list(d["label"]))
    fig = _style(fig, max(320, 22 * len(d) + 90), legend=False, grid="x")
    fig.update_layout(margin=dict(t=40))          # room for the cut-off labels above the bars
    return fig


def indicator_vs_peers(components: dict, medians: dict, unit: str) -> go.Figure:
    """The unit's three indicators next to the median of all compared units."""
    labels = [SHORT[k] for k in C.INDICATORS]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=[components[k] for k in C.INDICATORS], name=unit, marker_color=STATE_A_COLOR,
                         text=[f"{components[k]:.1f}%" for k in C.INDICATORS], textposition="outside", cliponaxis=False))
    fig.add_trace(go.Bar(x=labels, y=[medians[k] for k in C.INDICATORS], name="Median of compared units",
                         marker_color="#B5C2BB", text=[f"{medians[k]:.1f}%" for k in C.INDICATORS],
                         textposition="outside", cliponaxis=False))
    fig.update_layout(barmode="group", bargap=0.3)
    fig.update_yaxes(range=[0, 110], title="Percent (%)")
    fig.update_xaxes(title="")
    return _style(fig, 320)
