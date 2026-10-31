"""Waste Management Analytics Dashboard.

Run from the project root:  streamlit run app/streamlit_app.py
"""
import html
import itertools
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from waste_analytics import charts, compare, database, explain, indicators as ind  # noqa: E402
from waste_analytics import insight_cards, insight_focus, insights, preprocessing, reports  # noqa: E402
from waste_analytics import config as C  # noqa: E402
from waste_analytics import priority as prio  # noqa: E402

st.set_page_config(page_title="Waste Management Analytics", page_icon="♻️", layout="wide",
                   initial_sidebar_state="auto")

PAGES = ["Overview", "State Comparison", "Year Trends", "Waste Categories",
         "Priority", "Insights", "Reports"]
PAGE_TEXT = {
    "Overview": ("Overview", "Headline waste flow and performance indicators for the current selection."),
    "State Comparison": ("State comparison", "Rank states, compare any two head-to-head, and scan performance on a heatmap."),
    "Year Trends": ("Year trends", "How the indicators move from year to year."),
    "Waste Categories": ("Waste categories", "Distribution and performance by waste category (analysed separately from states)."),
    "Priority": ("Priority identification", "Quantile-based classification of state-year performance, with explanations."),
    "Insights": ("Rule-based insights", "Transparent IF-THEN rules applied to the selected data."),
    "Reports": ("Reports and export", "Download the filtered analytical results as CSV files or a PDF summary."),
}
PRIORITY_STYLE = {"High": "background-color:#FBEAE6;color:#B3402F;font-weight:600",
                  "Medium": "background-color:#FCF1D2;color:#8F5F00;font-weight:600",
                  "Normal": "background-color:#DDF3E8;color:#17744B;font-weight:600"}
KIND_STYLE = {"Concern": PRIORITY_STYLE["High"], "Deterioration": PRIORITY_STYLE["Medium"],
              "Improvement": PRIORITY_STYLE["Normal"]}
BETTER_STYLE = {"Tie": "color:#66736B;font-weight:600", "n/a": "color:#66736B"}
INDICATOR_VAR = {C.CE: "--ind-ce", C.TE: "--ind-te", C.RR: "--ind-rr"}   # colours defined in style.css
PILL = {"High": "p-high", "Medium": "p-med", "Normal": "p-norm"}
SETTING_DEFAULTS = {"t_ce": int(C.DEFAULT_THRESHOLDS.low_collection), "t_te": int(C.DEFAULT_THRESHOLDS.low_treatment),
                    "t_rr": int(C.DEFAULT_THRESHOLDS.low_recycling), "t_chg": C.DEFAULT_THRESHOLDS.change_tolerance,
                    "q_hi": 0.33, "q_med": 0.67}
INSIGHT_KINDS = {"Concerns": "Concern", "Declines": "Deterioration", "Improvements": "Improvement"}
INSIGHT_INDICATORS = {"Collection efficiency": C.CE, "Treatment efficiency": C.TE, "Recycling rate": C.RR}
INSIGHT_SCOPES = {"States": "State", "Waste categories": "Category", "Overall": "Overall"}
INSIGHT_PILL = {"High": "p-high", "Medium": "p-med", "Positive": "p-norm"}
INSIGHT_DEFAULT_CARDS = 5       # cards shown before "Show all findings"
# page-level "Focused analysis" selectors on the Insights page: widget key -> its "no restriction" choice
INSIGHT_FOCUS_DEFAULTS = {"ins_state": insight_focus.ALL_STATES, "ins_type": insight_focus.ALL_TYPES,
                          "ins_year": insight_focus.ALL_YEARS, "ins_ind": insight_focus.ALL_INDICATORS}


# ---------------------------------------------------------------- helpers
_card_ids = itertools.count()  # unique keys so CSS can target cards (st-key-card_*)


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    """Read cleaned records from SQLite; build the database from the CSV if absent."""
    if not C.DB_PATH.exists():
        clean, report = preprocessing.validate_and_clean(preprocessing.load_raw(C.RAW_CSV))
        database.build_database(clean, report)
    return database.load_records()


def pct(v: float) -> str:
    return "n/a" if pd.isna(v) else f"{v:.1f}%"


def inject_css() -> None:
    css = (ROOT / "app" / "style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


@contextmanager
def card(title: str = "", sub: str = "", variant: str = ""):
    """White rounded card with an optional heading. `variant` only selects a style in style.css."""
    with st.container(border=True, key="_".join(filter(None, ["card", variant, str(next(_card_ids))]))):
        if title:
            st.markdown(f'<div class="sec-title">{title}</div>'
                        + (f'<div class="sec-sub">{sub}</div>' if sub else ""), unsafe_allow_html=True)
        yield


def note(text: str) -> None:
    st.markdown(f'<div class="note"><div class="note-t">{text}</div></div>', unsafe_allow_html=True)


def page_header(page: str) -> None:
    title, sub = PAGE_TEXT[page]
    st.markdown(f'<div class="page-title">{title}</div><div class="page-sub">{sub}</div>',
                unsafe_allow_html=True)


def style_table(df: pd.DataFrame, status_cols: dict | None = None):
    """Number formatting plus optional status-colour cells (Styler)."""
    num = [c for c in df.columns if pd.api.types.is_float_dtype(df[c])]
    qty = [c for c in num if "TPD" in c]
    sty = df.style.format("{:.1f}", subset=[c for c in num if c not in qty], na_rep="n/a")
    if qty:
        sty = sty.format("{:,.0f}", subset=qty, na_rep="n/a")
    for col, mapping in (status_cols or {}).items():
        sty = sty.map(lambda v, m=mapping: m.get(v, ""), subset=[col])
    return sty


def show_table(df: pd.DataFrame, status_cols: dict | None = None, height: int | None = None,
               **kwargs) -> None:
    h = height or min(35 * (len(df) + 1) + 6, 560)
    st.dataframe(style_table(df, status_cols), hide_index=True, width="stretch", height=h, **kwargs)


def chart(fig, key: str) -> None:
    st.plotly_chart(fig, width="stretch", key=key, config={"displayModeBar": False})


def meter(value: float, indicator: str, caption: str) -> None:
    """Thin progress bar under a headline rate (value is a percentage, drawn on a 0-100 scale)."""
    if pd.isna(value):
        return
    width = min(max(float(value), 0.0), 100.0)
    st.markdown(
        f'<div class="meter" role="img" aria-label="{width:.1f} out of 100 percent" '
        f'style="--c:var({INDICATOR_VAR[indicator]})"><span style="width:{width:.1f}%"></span></div>'
        f'<div class="meter-cap"><span>{caption}</span></div>', unsafe_allow_html=True)


def focus_choice(label: str, first: str, values, key: str) -> str:
    """Selectbox offering `first` plus the values the sidebar filters left (a stale choice falls back to `first`)."""
    options = [first] + [str(v) for v in values]
    if st.session_state.get(key) not in options:
        st.session_state[key] = first
    return st.selectbox(label, options, key=key)


def summary_html(rows, focus) -> str:
    """Compact performance summary of the focused data: one tile per indicator, with its history across the years."""
    esc = html.escape
    if not rows:
        return ""
    tiles = ""
    for r in rows:
        status = (f"{r.shortfall:.1f} pp below the {r.threshold:g}% threshold" if r.shortfall > 0
                  else f"Meets the {r.threshold:g}% threshold")
        history = ('<div class="im-h"><b>History</b>' + " · ".join(f"{y} {v:.1f}%" for y, v in r.history) + "</div>"
                   if len(r.history) >= 2 else "")
        tiles += (f'<div class="imetric{" below" if r.shortfall > 0 else ""}"><div class="im-n">{esc(r.name)}</div>'
                  f'<div class="im-v">{r.value:.1f}%</div><div class="im-c">{status}</div>{history}</div>')
    return ('<div class="isum"><div class="isum-h"><span class="sec-title">Performance summary</span>'
            f'<span class="ichip">{esc(focus.label)}</span><span class="ichip">{rows[0].year}</span></div>'
            f'<div class="imetrics">{tiles}</div></div>')


def year_span(years) -> str:
    ys = sorted(int(y) for y in years)
    return f"{ys[0]}–{ys[-1]}" if len(ys) >= 3 and ys[-1] - ys[0] == len(ys) - 1 else ", ".join(map(str, ys))


def export_summary_html(n_records: int, years, n_states: int, n_types: int) -> str:
    """One compact strip: what the exports cover right now, and why."""
    def item(value, n, one, many):
        return f'<div class="rsum-i"><b>{html.escape(str(value))}</b><span>{one if n == 1 else many}</span></div>'
    return ('<div class="rsum"><div class="rsum-items">'
            + item(n_records, n_records, "record", "records")
            + item(year_span(years), len(years), "year", "years")
            + item(n_states, n_states, "state", "states")
            + item(n_types, n_types, "waste category", "waste categories")
            + '</div><div class="rsum-n">Exports use the current dashboard filters and analysis settings.</div></div>')


def insight_card_html(c, main: bool = False) -> str:
    """HTML for one insight card (all dynamic text is escaped). `main` marks the most important finding."""
    esc = html.escape
    where = (insight_cards.SCOPE_LABEL[c.scope] if c.scope in ("Overall", "Selection")   # the headline names the subject
             else f"{insight_cards.SCOPE_LABEL[c.scope]}: {c.subject}")
    metrics = "".join(f'<div class="imetric"><div class="im-n">{esc(m.name)}</div>'
                      f'<div class="im-v">{m.value:.1f}%</div><div class="im-c">{esc(m.context)}</div></div>'
                      for m in c.metrics)
    action = (esc(c.actions[0]) if len(c.actions) == 1
              else "<ul>" + "".join(f"<li>{esc(a)}</li>" for a in c.actions) + "</ul>")
    return (f'<div class="icard sev-{c.severity.lower()}"><div class="icard-top">'
            f'<span class="legend-pill {INSIGHT_PILL[c.severity]}">{c.severity}</span>'
            + ('<span class="ichip main">Main issue</span>' if main and c.severity != "Positive" else "")
            + f'<span class="ichip">{esc(where)}</span><span class="ichip">{esc(c.year_label)}</span></div>'
            f'<div class="icard-h">{esc(c.headline)}</div><div class="icard-t">{esc(c.summary)}</div>'
            f'<div class="imetrics">{metrics}</div>'
            f'<div class="iaction"><b>Suggested action</b>{action}</div></div>')


def reset_filters() -> None:
    """Restore every filter and analysis setting to its default."""
    st.session_state["f_years"] = list(years_all)
    st.session_state["f_states"] = list(states_all)
    st.session_state["f_types"] = list(types_all)
    for key, val in {**SETTING_DEFAULTS, **INSIGHT_FOCUS_DEFAULTS}.items():
        st.session_state[key] = val


def empty_state(message: str, hint: str = "") -> None:
    st.markdown(f'<div class="empty"><div class="empty-t">{message}</div><div>{hint}</div></div>',
                unsafe_allow_html=True)


# ---------------------------------------------------------------- data + sidebar
inject_css()
try:
    data = load_data()
except Exception as exc:  # database / CSV problems: explain how to recover instead of a traceback
    st.error(f"The analytics database could not be loaded ({type(exc).__name__}: {exc}).")
    st.info("Rebuild it from the original CSV with `python scripts/build_database.py`, then reload this page.")
    st.stop()

years_all = sorted(data[C.YEAR].unique().tolist())
states_all = sorted(data[C.STATE].unique())
types_all = sorted(data[C.WTYPE].unique())
for _k, _v in {"f_years": years_all, "f_states": states_all, "f_types": types_all, **SETTING_DEFAULTS}.items():
    st.session_state.setdefault(_k, list(_v) if isinstance(_v, list) else _v)

with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="logo" aria-hidden="true"></div><div><div class="t1">Waste Management<br>Analytics</div>'
        '<div class="t2">Municipal solid-waste performance</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="side-h">Filters</div>', unsafe_allow_html=True)
    st.button("Reset filters", on_click=reset_filters, width="stretch", key="reset_btn",
              icon=":material/restart_alt:",
              help="Restore all filters, thresholds and priority quantiles to their defaults")
    sel_years = st.multiselect("Year", years_all, key="f_years")
    sel_states = st.multiselect("State", states_all, key="f_states")
    sel_types = st.multiselect("Waste category", types_all, key="f_types")

    st.markdown('<div class="side-h">Analysis settings</div>', unsafe_allow_html=True)
    with st.expander("Rule thresholds"):
        t_ce =st.slider("Low collection efficiency below (%)", 0, 100, key="t_ce")
        t_te = st.slider("Low treatment efficiency below (%)", 0, 100, key="t_te")
        t_rr = st.slider("Low recycling rate below (%)", 0, 100, key="t_rr")
        t_chg = st.slider("Stable if change within ± (pp)", 0.0, 10.0, step=0.5, key="t_chg")
    with st.expander("Priority quantiles"):
        st.caption("Relative, project-defined cut-offs on the composite score.")
        q_hi = st.slider("High priority: lowest share of units", 0.05, 0.60, step=0.01, key="q_hi")
        q_med = st.slider("Medium priority: up to", 0.10, 0.95, step=0.01, key="q_med")
        if q_hi >= q_med:
            st.error("High cut-off must be below the Medium cut-off. Defaults (0.33 / 0.67) are used.")
            q_hi, q_med = SETTING_DEFAULTS["q_hi"], SETTING_DEFAULTS["q_med"]

thresholds = C.InsightThresholds(t_ce, t_te, t_rr, t_chg)
pcfg = C.PriorityConfig(q_hi, q_med)
df = data[data[C.YEAR].isin(sel_years) & data[C.STATE].isin(sel_states) & data[C.WTYPE].isin(sel_types)]
# Head-to-head uses the year and category filters but may pick any state
df_h2h = data[data[C.YEAR].isin(sel_years) & data[C.WTYPE].isin(sel_types)]

# ---------------------------------------------------------------- header + navigation
st.markdown(
    '<div class="hero"><div class="hero-eyebrow">Environmental analytics</div>'
    '<h1>Waste Management Analytics System</h1>'
    '<p>A decision-support dashboard that validates municipal solid-waste data, measures collection, treatment '
    'and recycling performance across Indian states, years and waste categories, and highlights priority '
    'areas with explainable rules.</p>'
    '<span class="chip">Units: TPD (tonnes per day)</span></div>',
    unsafe_allow_html=True)

with st.container(key="nav"):
    page = st.radio("Page", PAGES, horizontal=True, label_visibility="collapsed", key="page")

page_header(page)

if df.empty:
    with card():
        empty_state("No records match the current filters",
                    "Select at least one year, one state and one waste category, or reset the filters.")
        st.button("Reset filters", on_click=reset_filters, key="reset_main", icon=":material/restart_alt:")
    st.stop()


# ---------------------------------------------------------------- shared computations
def kpi_deltas() -> dict:
    """Latest-vs-previous selected year change (pp) for the three indicators, if >= 2 years."""
    yrs = sorted(df[C.YEAR].unique())
    if len(yrs) < 2:
        return {}
    by_year = ind.aggregate(df, C.YEAR).set_index(C.YEAR)
    out = {k: by_year.loc[yrs[-1], k] - by_year.loc[yrs[-2], k] for k in C.INDICATORS}
    out["span"] = (yrs[-2], yrs[-1])
    return out


def default_pair() -> tuple[str, str]:
    """Best and weakest state by composite score over the whole dataset (default comparison)."""
    agg = ind.aggregate(data, C.STATE)
    agg[C.SCORE] = prio.composite_score(agg)
    agg = agg.sort_values(C.SCORE, ascending=False)
    return agg[C.STATE].iloc[0], agg[C.STATE].iloc[-1]


def saved_pair() -> tuple[str, str]:
    a, b = st.session_state.get("h2h_saved", default_pair())
    return (a if a in states_all else default_pair()[0]), (b if b in states_all else default_pair()[1])


def current_comparison():
    a, b = saved_pair()
    if a == b or not {a, b} <= set(df_h2h[C.STATE]):
        return None
    return compare.compare_states(df_h2h, a, b)


def compare_card(label: str, a: str, b: str, va: float, vb: float, better: str, lead: float,
                 is_score: bool = False) -> None:
    fmt = (lambda v: "n/a" if pd.isna(v) else (f"{v:.1f}" if is_score else f"{v:.1f}%"))
    ea, eb = html.escape(a), html.escape(b)
    if better in (a, b):
        badge = f'<span class="badge win">Better: {html.escape(better)} · +{lead:.1f} pp</span>'
    else:
        badge = f'<span class="badge tie">{"Tie" if better == "Tie" else "Not comparable"}</span>'
    st.markdown(
        f'<div class="cmp"><div class="cmp-h">{label}</div><div class="cmp-row">'
        f'<div class="cmp-side{" win" if better == a else ""}"><span class="cmp-n">{ea}</span>'
        f'<span class="cmp-v">{fmt(va)}</span></div><div class="cmp-vs">vs</div>'
        f'<div class="cmp-side b{" win" if better == b else ""}"><span class="cmp-n">{eb}</span>'
        f'<span class="cmp-v">{fmt(vb)}</span></div></div><div class="cmp-foot">{badge}</div></div>',
        unsafe_allow_html=True)


# ---------------------------------------------------------------- pages
if page == "Overview":
    totals = ind.overall_summary(df)
    deltas = kpi_deltas()
    with card(variant="flow"):          # generated > collected > treated > recycled, one strip
        cols = st.columns(4)
        for col, key, label in zip(cols, C.QTY_COLS, ["Generated", "Collected", "Treated", "Recycled"]):
            with col:
                st.metric(f"{label} (TPD, summed)", f"{totals[key]:,.0f}")
    cols = st.columns(3)
    helps = {C.CE: "Collected / Generated × 100", C.TE: "Treated / Collected × 100",
             C.RR: "Recycled / Treated × 100"}
    captions = {C.CE: "Collected ÷ Generated × 100", C.TE: "Treated ÷ Collected × 100",
                C.RR: "Recycled ÷ Treated × 100"}
    names = {C.CE: "Collection efficiency", C.TE: "Treatment efficiency", C.RR: "Recycling rate"}
    for col, k in zip(cols, C.INDICATORS):
        with col, card(variant="ind"):
            d = deltas.get(k)
            st.metric(names[k], pct(totals[k]), help=helps[k],
                      delta=None if d is None or pd.isna(d) else f"{d:+.1f} pp vs {deltas['span'][0]}")
            meter(totals[k], k, captions[k])
    note(f"{len(df)} records selected. Rates are computed from summed quantities, not averaged percentages. "
         + (f"Deltas compare {deltas['span'][1]} with {deltas['span'][0]}." if deltas else ""))
    left, right = st.columns(2)
    with left, card("Waste flow", "Generated → collected → treated → recycled (sum of daily rates, TPD)"):
        chart(charts.flow_bars(totals), "ov_flow")
    with right, card("Share by waste category", "Share of generated waste (TPD, summed)"):
        chart(charts.category_share_bar(ind.aggregate(df, C.WTYPE)), "ov_share")

elif page == "State Comparison":
    t_rank, t_h2h, t_heat = st.tabs(["Ranking", "Head-to-Head", "Performance Heatmap"])

    with t_rank:
        sagg = ind.aggregate(df, C.STATE)
        metric = st.radio("Indicator", C.INDICATORS, format_func=lambda k: charts.LABELS[k], horizontal=True)
        limit = {C.CE: t_ce, C.TE: t_te, C.RR: t_rr}[metric]
        with card("State ranking", f"{charts.LABELS[metric]}; the dashed line is the project threshold from the sidebar"):
            chart(charts.indicator_bar(sagg, C.STATE, metric, limit), "st_bar")
        with card("All indicators by state"):
            chart(charts.grouped_indicator_bars(sagg, C.STATE), "st_group")
        with card("Performance ranking", f"Rank 1 = best on {charts.LABELS[metric].lower()}"):
            rk = ind.rank_table(sagg, metric)[["Rank", C.STATE, *C.INDICATORS]].astype({"Rank": int})
            show_table(rk.rename(columns=charts.LABELS))

    with t_h2h:
        note("Pick any two states. The comparison uses the <b>Year</b> and <b>Waste category</b> filters; the State "
             "filter does not limit this choice. Higher percentages are better.")
        da, db = saved_pair()
        c1, c2 = st.columns(2)
        sa = c1.selectbox("State A", states_all, index=states_all.index(da), key="h2h_a")
        sb = c2.selectbox("State B", states_all, index=states_all.index(db), key="h2h_b")
        st.session_state["h2h_saved"] = (sa, sb)
        if sa == sb:
            with card():
                empty_state("Choose two different states", "State A and State B are the same.")
        elif not {sa, sb} <= set(df_h2h[C.STATE]):
            with card():
                empty_state("No data for one of the states", "Widen the Year or Waste category filters.")
        else:
            cmp = compare.compare_states(df_h2h, sa, sb)
            cols = st.columns(4)
            for col, (_, r) in zip(cols, cmp.table.iterrows()):
                with col:
                    compare_card(charts.LABELS.get(r["Indicator"], r["Indicator"]), sa, sb, r["Value_A"],
                                 r["Value_B"], r["Better"], r["Lead_pp"], is_score=r["Indicator"] == C.SCORE)
            wins = cmp.wins
            if cmp.leader in (sa, sb):
                other = sb if cmp.leader == sa else sa
                summary = (f"<b>{html.escape(cmp.leader)}</b> has the higher composite score "
                           f"(+{cmp.table.iloc[-1]['Lead_pp']:.1f} over {html.escape(other)}) and leads on "
                           f"{wins[cmp.leader]} of 3 indicators; {html.escape(other)} leads on {wins[other]}"
                           f"{', with ' + str(wins['Tie']) + ' tied' if wins['Tie'] else ''}.")
            else:
                summary = "The two states have the same composite score."
            note(summary)
            left, right = st.columns(2)
            with left, card("Indicators side by side", "Aggregate of summed quantities for the selected years and categories"):
                chart(charts.head_to_head_bars(cmp.table, sa, sb), "h2h_bars")
            with right, card("Trend over the selected years"):
                m3 = st.selectbox("Indicator", C.INDICATORS, format_func=lambda k: charts.LABELS[k], key="h2h_ind")
                chart(charts.head_to_head_trend(df_h2h, sa, sb, m3), "h2h_trend")
            with card("Comparison table"):
                tbl = compare.comparison_export(cmp)
                show_table(tbl, {"Better": {sa: "background-color:#DDF1E5;color:#14532D;font-weight:600",
                                            sb: "background-color:#E3EEF7;color:#2C5F8A;font-weight:600",
                                            **BETTER_STYLE}}, height=35 * 5 + 6)
                q = cmp.quantities.rename(index=charts.LABELS).reset_index(names="Quantity (TPD, summed)")
                st.dataframe(q.style.format("{:,.0f}", subset=[sa, sb]), hide_index=True, width="stretch",
                             height=35 * 5 + 6)

    with t_heat:
        c1, c2, c3 = st.columns(3)
        rows_by = c1.radio("Rows", ["States", "Waste categories"], horizontal=True, key="hm_rows")
        mode = c2.radio("Colour scale", ["Absolute (0–100%)", "Relative (within each indicator)"],
                        key="hm_mode")
        sort_opts = {"Composite score": C.SCORE, **{charts.LABELS[k]: k for k in C.INDICATORS}, "Name": "name"}
        sort_label = c3.selectbox("Sort by", list(sort_opts), key="hm_sort")
        by = C.STATE if rows_by == "States" else C.WTYPE
        hagg = ind.aggregate(df, by)
        hagg[C.SCORE] = prio.composite_score(hagg)
        key = sort_opts[sort_label]
        hagg = hagg.sort_values(by if key == "name" else key, ascending=key == "name")
        with card(f"Performance heatmap: {rows_by.lower()} × indicator",
                  "Cell labels show the real percentage. Hover for details."):
            chart(charts.performance_heatmap(hagg, by, "relative" if mode.startswith("Relative") else "absolute"),
                  "hm_chart")
        note("<b>Absolute</b> colours every cell on one 0–100% scale, so columns can be compared with each other. "
             "<b>Relative</b> rescales each indicator between its own lowest and highest value to show spread "
             "within that indicator. Green = higher, red = lower.")
        with st.expander("Heatmap data"):
            show_table(hagg[[by, *C.INDICATORS, C.SCORE]].rename(columns=charts.LABELS))

elif page == "Year Trends":
    if len(sel_years) < 2:
        note("Select two or more years in the sidebar to see trends.")
    yagg = ind.aggregate(df, C.YEAR)
    with card("Overall trend", "Aggregate indicators by year (ratio of summed quantities)"):
        chart(charts.trend_lines(yagg), "yr_trend")
    yoy = ind.year_over_year(df, C.STATE)
    with card("State-wise trend"):
        m2 = st.selectbox("Indicator", C.INDICATORS, format_func=lambda k: charts.LABELS[k])
        chart(charts.state_year_lines(yoy, m2), "yr_state")
    with card("Year-wise table"):
        show_table(yagg.rename(columns=charts.LABELS))

elif page == "Waste Categories":
    cagg = ind.aggregate(df, C.WTYPE)
    l, r = st.columns(2)
    with l, card("Distribution"):
        qty = st.selectbox("Quantity", C.QTY_COLS, format_func=lambda k: charts.LABELS[k])
        chart(charts.category_share_bar(cagg, qty), "ct_share")
    with r, card("Indicators by category"):
        chart(charts.grouped_indicator_bars(cagg, C.WTYPE), "ct_group")
    cp = prio.priority_by_category(df, pcfg)
    with card("Category priority", "Separate from state priority; composite score of aggregated indicators"):
        if len(cp) < 3:
            note("Fewer than 3 categories are selected, so quantile-based priority levels are not meaningful.")
        chart(charts.priority_bar(cp, C.WTYPE), "ct_prio")
        show_table(cp[[C.WTYPE, *C.INDICATORS, C.SCORE, "Priority"]].rename(columns=charts.LABELS),
                   {"Priority": PRIORITY_STYLE})

elif page == "Priority":
    sy = prio.priority_by_state_year(df, pcfg)
    cp = prio.priority_by_category(df, pcfg)
    cut = sy.attrs.get("cutoffs", {})
    note("<b>Method.</b> Composite score = (CE + TE + RR) / 3, computed from aggregated quantities for each "
         "state-year. Units are ranked and split by quantile: the lowest scores are <b>High</b> priority. "
         "Cut-offs are <i>relative</i> to the units being compared.")
    if len(sy) < 3:
        st.warning("Fewer than 3 state-year units are selected, so quantile-based priority levels are not "
                   "meaningful. Widen the filters.")
    if cut:
        st.markdown(
            f'<span class="legend-pill p-high">High ≤ {cut["high"]:.1f}</span>'
            f'<span class="legend-pill p-med">Medium ≤ {cut["medium"]:.1f}</span>'
            f'<span class="legend-pill p-norm">Normal above</span>', unsafe_allow_html=True)
        st.write("")
    counts = sy["Priority"].value_counts()
    c = st.columns(3)
    for col, lvl in zip(c, ["High", "Medium", "Normal"]):
        with col, card(variant=f"lvl_{lvl.lower()}"):
            st.metric(f"{lvl} priority units", int(counts.get(lvl, 0)))
    with card("Composite score by state and year", "Lower score = higher priority"):
        chart(charts.priority_heatmap(sy), "pr_heat")
    with card("Priority table"):
        pick = st.multiselect("Show priority levels", ["High", "Medium", "Normal"],
                              default=["High", "Medium", "Normal"])
        view_p = sy[[C.STATE, C.YEAR, *C.INDICATORS, C.SCORE, "Priority"]]
        show_table(view_p[view_p["Priority"].isin(pick)].rename(columns=charts.LABELS), {"Priority": PRIORITY_STYLE})

    # ---- explainable priority
    st.markdown('<div class="sec-title" style="margin-top:10px">Why this priority?</div>'
                '<div class="sec-sub">Pick a state-year or a waste category to see how its level was decided '
                'and what the rules suggest.</div>', unsafe_allow_html=True)
    kind = st.radio("Explain a", ["State-year", "Waste category"], horizontal=True, key="ex_kind")
    if kind == "State-year":
        frame, by = sy, C.STATE
        labels = {i: f"{r[C.STATE]} · {int(r[C.YEAR])}" for i, r in sy.iterrows()}
    else:
        frame, by = cp, C.WTYPE
        labels = {i: r[C.WTYPE] for i, r in cp.iterrows()}
    valid = [i for i in frame.index if pd.notna(frame.loc[i, C.SCORE])]
    if not valid:
        with card():
            empty_state("Nothing to explain", "The current selection has no unit with a complete composite score.")
    else:
        uid = st.selectbox("Unit (lowest composite score first)", valid, format_func=lambda i: labels.get(i, str(i)),
                           key="ex_unit_sy" if kind == "State-year" else "ex_unit_cat")
        name = labels[uid]
        row = frame.loc[uid]
        trend = (explain.trend_changes(df, C.STATE, row[C.STATE], int(row[C.YEAR])) if kind == "State-year"
                 else explain.trend_changes(df, C.WTYPE, row[C.WTYPE]))
        ex = explain.explain_unit(frame, uid, name, pcfg, thresholds, trend)
        with card(variant="explain"):
            st.markdown(f'<div class="xhead"><span class="legend-pill {PILL[ex.level]}">{ex.level} priority</span>'
                        f'<span class="xname">{html.escape(name)}</span>'
                        f'<span class="xmeta">Composite score <b>{ex.composite:.1f}</b></span>'
                        f'<span class="xmeta">Rank <b>{ex.rank}</b> of {ex.n_units} (1 = lowest)</span></div>',
                        unsafe_allow_html=True)
            mc = st.columns(4)
            mc[0].metric("Composite score", f"{ex.composite:.1f}")
            for col, k in zip(mc[1:], C.INDICATORS):
                col.metric(charts.LABELS[k].replace(" (%)", ""), pct(ex.components[k]),
                           delta=f"{ex.gap_vs_median[k]:+.1f} pp vs median", help="Difference from the median of "
                           "all compared units")
            if ex.caution:
                st.warning(ex.caution)
        left, right = st.columns(2)
        with left, card("Why this level"):
            st.markdown("\n".join(f"- {r}" for r in ex.reasons))
        with right, card("Suggestions (rule-based)"):
            st.markdown("\n".join(f"- {s}" for s in ex.suggestions))
            st.caption(explain.DISCLAIMER)
        left, right = st.columns(2)
        with left, card("Where it sits among compared units", "Dashed lines are the High and Medium cut-offs"):
            chart(charts.priority_position([labels[i] for i in valid], [frame.loc[i, C.SCORE] for i in valid],
                                           name, {"high": ex.high_cut, "medium": ex.medium_cut}), "ex_pos")
        with right, card("Indicators versus the median", "Median of all units being compared"):
            chart(charts.indicator_vs_peers(ex.components, ex.peer_median, name), "ex_peers")
        with st.expander("How the classification works"):
            st.markdown(
                f"1. For every unit, collection, treatment and recycling are computed from **summed** quantities.\n"
                f"2. The **composite score** is their equal-weight mean: (CE + TE + RR) / 3.\n"
                f"3. Across the {ex.n_units} compared units, the High cut-off is the {pcfg.high_quantile:.0%} quantile "
                f"of the scores (**{ex.high_cut:.1f}**) and the Medium cut-off is the {pcfg.medium_quantile:.0%} "
                f"quantile (**{ex.medium_cut:.1f}**).\n"
                f"4. Score ≤ {ex.high_cut:.1f} → **High**; ≤ {ex.medium_cut:.1f} → **Medium**; otherwise **Normal**.\n\n"
                "These cut-offs are *relative* to the units being compared (change the filters and they move). "
                "The suggestions use the rule thresholds from the sidebar.")

elif page == "Insights":
    # Focused analysis: page-level selectors that narrow the sidebar selection further (never widen it)
    with st.container(key="ins_controls"):
        st.markdown('<div class="sec-title">Focused analysis</div><div class="sec-sub">Narrow the findings to one state, '
                    'waste type, year or indicator. The selectors work within the sidebar filters.</div>',
                    unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            pick_state = focus_choice("State", insight_focus.ALL_STATES, sorted(df[C.STATE].unique()), "ins_state")
        with c2:
            pick_type = focus_choice("Waste type", insight_focus.ALL_TYPES, sorted(df[C.WTYPE].unique()), "ins_type")
        with c3:
            pick_year = focus_choice("Year", insight_focus.ALL_YEARS, sorted(df[C.YEAR].unique()), "ins_year")
        with c4:
            pick_ind = focus_choice("Indicator", insight_focus.ALL_INDICATORS, list(INSIGHT_INDICATORS), "ins_ind")
        focus = insight_focus.Focus(
            None if pick_state == insight_focus.ALL_STATES else pick_state,
            None if pick_type == insight_focus.ALL_TYPES else pick_type,
            None if pick_year == insight_focus.ALL_YEARS else int(pick_year),
            INSIGHT_INDICATORS.get(pick_ind))
        k1, k2 = st.columns(2)
        kinds_sel = k1.multiselect("Show", list(INSIGHT_KINDS), default=list(INSIGHT_KINDS), key="ins_kinds")
        scopes_sel = k2.multiselect("Applies to", list(INSIGHT_SCOPES), default=list(INSIGHT_SCOPES), key="ins_scopes",
                                    disabled=focus.is_combination,
                                    help="A single state and waste type is one subject, so there is nothing to choose.")

    frame, found = insight_focus.run_focus(df, focus, thresholds)
    in_focus = insight_cards.filter_records(found, indicators={focus.indicator} if focus.indicator else None)
    focused = any((focus.state, focus.wtype, focus.year))
    if frame.empty:
        with card():
            empty_state(f"No records for {focus.label}",
                        "There are no records for this combination in the current filters. Choose All states, "
                        "All types or All years, or widen the sidebar filters.")
    else:
        yrs = sorted(frame[C.YEAR].unique())
        st.markdown(summary_html(insight_focus.performance_summary(frame, focus, thresholds), focus), unsafe_allow_html=True)
        if not found:
            where = f" for {focus.label}" if focus.state or focus.wtype else ""
            if len(yrs) >= 2:
                changes = f" and no change larger than ±{t_chg:g} pp was found between {yrs[-2]} and {yrs[-1]}."
            elif focus.year is not None:
                changes = f". {yrs[-1]} is the earliest selected year, so there is no earlier year to compare with."
            else:
                changes = ". Select two or more years to also check year-on-year changes."
            advice = ("Try All states, All types or All years, widen the sidebar filters, or adjust the thresholds."
                      if focused else "Widen the filters or adjust the thresholds in the sidebar.")
            with card():
                empty_state("No significant insight identified for this selection",
                            f"No indicator is below its threshold in {yrs[-1]}{where}{changes} {advice}")
        elif not in_focus:
            with card():
                empty_state(f"No {insight_focus.INDICATOR_NAME[focus.indicator].lower()} findings for this selection",
                            "Other indicators do have findings here. Choose All indicators to see them.")
        else:
            counts = insight_cards.severity_counts(insight_cards.build_cards(in_focus))
            st.markdown("".join(f'<span class="legend-pill {INSIGHT_PILL[s]}">{s} · {counts[s]}</span>'
                                for s in insight_cards.SEVERITY_ORDER), unsafe_allow_html=True)
            period = (f"Findings are for {yrs[-1]}" if focus.year is not None
                      else f"Findings use the latest selected year ({yrs[-1]})")
            st.caption(insight_cards.SEVERITY_NOTE + ". " + period
                       + (f"; changes compare {yrs[-2]} with {yrs[-1]}." if len(yrs) >= 2
                          else "; year-on-year changes need two or more years."))
            chosen = insight_cards.filter_records(
                in_focus, {INSIGHT_KINDS[k] for k in kinds_sel},
                scopes=None if focus.is_combination else {INSIGHT_SCOPES[s] for s in scopes_sel})
            cards = insight_cards.build_cards(chosen)
            if not cards:
                with card():
                    empty_state("No insights match these options", "Select at least one option in each filter.")
            else:
                n_cards = len(cards)
                show_all = False
                if n_cards > INSIGHT_DEFAULT_CARDS:
                    show_all = st.toggle(f"Show all findings ({n_cards})", key="ins_all")
                shown = cards if show_all else cards[:INSIGHT_DEFAULT_CARDS]
                st.caption(f"Showing {len(shown)} of {n_cards} findings, most important first")
                st.markdown('<div class="igrid">' + "".join(insight_card_html(c, main=i == 0)
                                                            for i, c in enumerate(shown)) + "</div>",
                            unsafe_allow_html=True)
                with st.expander("Rule details (table)"):
                    detail = pd.DataFrame([{"Rule": r.rule, "Kind": r.kind, "Scope": r.scope, "Insight": r.message}
                                           for r in chosen])
                    show_table(detail, {"Kind": KIND_STYLE}, height=min(35 * (len(detail) + 1) + 6, 520),
                               column_config={"Insight": st.column_config.TextColumn(width=900),
                                              "Rule": st.column_config.TextColumn(width=50),
                                              "Kind": st.column_config.TextColumn(width=110),
                                              "Scope": st.column_config.TextColumn(width=80)})

elif page == "Reports":
    filters = reports.describe_filters(sel_years, sel_states, sel_types, years_all, states_all, types_all)
    try:
        rd = reports.build_report_data(df, filters, thresholds, pcfg, current_comparison())
        pdf = reports.build_pdf(rd)
        zipped = reports.zip_bytes(rd)
    except Exception as exc:
        st.error(f"The report could not be generated ({type(exc).__name__}: {exc}). "
                 "Check the filters and try again.")
        st.stop()
    st.markdown(export_summary_html(len(df), sel_years, len(sel_states), len(sel_types)), unsafe_allow_html=True)
    names_list = list(rd.tables)
    pdf_col, csv_col = st.columns([2, 3])
    with pdf_col, card("PDF summary report", "One document with the main results for the current selection"):
        st.markdown('<div class="rp-label" style="margin-top:4px">Includes</div><div class="rp-meta">'
                    + "".join(f'<span class="ichip">{s}</span>' for s in
                              ("Title", "Filters", "KPIs", "State performance", "Comparison", "Priority findings",
                               "Insights")) + '</div>', unsafe_allow_html=True)
        st.download_button("Download PDF report", pdf, file_name="waste_analytics_report.pdf",
                           mime="application/pdf", key="dl_pdf", on_click="ignore", width="stretch",
                           icon=":material/download:")
        st.caption(f"{len(pdf) / 1024:.0f} KB · A4 · generated from the current selection")
    with csv_col, card("CSV exports", "Rates are exported at full precision (the dashboard shows 1 decimal); TPD quantities at 2 decimals",
                       variant="csv"):
        st.download_button("Download all tables (ZIP with README)", zipped, file_name="waste_analytics_tables.zip",
                           mime="application/zip", key="dl_zip", on_click="ignore", width="stretch",
                           icon=":material/folder_zip:")
        st.markdown('<div class="rp-label">Individual tables</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, nm in enumerate(names_list):
            with cols[i % 2]:
                st.download_button(f"{nm}.csv  ({len(rd.tables[nm])} rows)", reports.csv_bytes(rd.tables[nm]),
                                   file_name=f"{nm}.csv", mime="text/csv", key=f"dl_{nm}", width="stretch",
                                   on_click="ignore", icon=":material/table_view:")
    with card("Preview"):
        which = st.selectbox("Table", names_list, key="rp_table")
        show_table(rd.tables[which], height=360)
