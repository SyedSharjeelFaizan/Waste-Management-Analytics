"""Export tests. Expected values are computed independently from the RAW CSV with the csv module
(no pandas, no project code), then compared with the CSV tables and the PDF text."""
import csv
import io
import re
import zipfile

import pandas as pd
import pytest

from waste_analytics import compare, config as C
from waste_analytics import database, pdf_report, reports


# ------------------------------------------------------------------ independent reference
def raw_rows(years=None, states=None, types=None):
    with open(C.RAW_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows
            if (years is None or int(r["Year"]) in years) and (states is None or r["State"] in states)
            and (types is None or r["Waste_Type"] in types)]


def rates(rows):
    g, c, t, r = (sum(float(x[k]) for x in rows) for k in C.QTY_COLS)
    return {"gen": g, "col": c, "trt": t, "rec": r, "ce": c / g * 100, "te": t / c * 100, "rr": r / t * 100}


def group_rates(rows, key):
    out = {}
    for name in sorted({r[key] for r in rows}):
        out[name] = rates([r for r in rows if r[key] == name])
    return out


def pdf_text(pdf: bytes) -> str:
    """All text drawn with the Tj operator, unescaped."""
    body = pdf.decode("latin-1")
    parts = re.findall(r"\(((?:\\.|[^\\)])*)\) Tj", body)
    return "\n".join(p.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\") for p in parts)


def make(df, years=None, states=None, types=None, pair=None):
    data = database.load_records()
    all_y, all_s, all_t = sorted(data[C.YEAR].unique()), sorted(data[C.STATE].unique()), sorted(data[C.WTYPE].unique())
    sel = data[data[C.YEAR].isin(years or all_y) & data[C.STATE].isin(states or all_s) & data[C.WTYPE].isin(types or all_t)]
    filt = reports.describe_filters(years or all_y, states or all_s, types or all_t, all_y, all_s, all_t)
    cmp = compare.compare_states(data[data[C.YEAR].isin(years or all_y) & data[C.WTYPE].isin(types or all_t)], *pair) if pair else None
    return reports.build_report_data(sel, filt, C.DEFAULT_THRESHOLDS, C.DEFAULT_PRIORITY, cmp)


@pytest.fixture(scope="module")
def full():
    return make(None, pair=("Kerala", "Uttar Pradesh"))


# ------------------------------------------------------------------ CSV tables
def test_kpi_table_matches_raw_dataset(full):
    ref = rates(raw_rows())
    kpi = dict(zip(full.tables["kpi_summary"]["Metric"], full.tables["kpi_summary"]["Value"]))
    assert kpi["Records selected"] == 300
    assert kpi["Waste Generated TPD"] == pytest.approx(ref["gen"], abs=0.01)
    assert kpi["Collection Efficiency"] == pytest.approx(ref["ce"], abs=0.006)
    assert kpi["Treatment Efficiency"] == pytest.approx(ref["te"], abs=0.006)
    assert kpi["Recycling Rate"] == pytest.approx(ref["rr"], abs=0.006)


def test_state_summary_matches_raw_dataset(full):
    ref = group_rates(raw_rows(), "State")
    t = full.tables["state_summary"].set_index(C.STATE)
    assert set(t.index) == set(ref)
    for state, r in ref.items():
        assert t.loc[state, C.CE] == pytest.approx(r["ce"], abs=0.006)
        assert t.loc[state, C.TE] == pytest.approx(r["te"], abs=0.006)
        assert t.loc[state, C.RR] == pytest.approx(r["rr"], abs=0.006)
        assert t.loc[state, C.SCORE] == pytest.approx((r["ce"] + r["te"] + r["rr"]) / 3, abs=0.006)
    assert t["Rank_by_Composite"].min() == 1 and t["Rank_by_Composite"].max() == 10


def test_category_year_and_priority_tables_match_raw_dataset(full):
    for name, key, col in (("category_summary_priority", "Waste_Type", C.WTYPE), ("year_summary", "Year", C.YEAR)):
        ref = group_rates(raw_rows(), key)
        t = full.tables[name].set_index(col)
        for k, r in ref.items():
            assert t.loc[type(t.index[0])(k), C.CE] == pytest.approx(r["ce"], abs=0.006)
            assert t.loc[type(t.index[0])(k), C.RR] == pytest.approx(r["rr"], abs=0.006)
    sy = full.tables["state_year_priority"]
    assert len(sy) == 30 and set(sy["Priority"]) == {"High", "Medium", "Normal"}
    r = rates(raw_rows(years={2022}, states={"Uttar Pradesh"}))
    up = sy[(sy[C.STATE] == "Uttar Pradesh") & (sy[C.YEAR] == 2022)].iloc[0]
    assert up[C.CE] == pytest.approx(r["ce"], abs=0.006) and up["Priority"] == "High"


def test_records_table_has_row_level_indicators(full):
    rec = full.tables["records_with_indicators"]
    raw = raw_rows()
    assert len(rec) == len(raw) == 300
    first = rec.iloc[0]
    src = next(x for x in raw if int(x["Year"]) == first[C.YEAR] and x["State"] == first[C.STATE]
               and x["Waste_Type"] == first[C.WTYPE])
    assert first[C.CE] == pytest.approx(float(src[C.COL]) / float(src[C.GEN]) * 100, abs=0.006)


def test_filtered_export_matches_filtered_raw_dataset():
    rd = make(None, years=[2022], states=["Kerala", "Gujarat"], types=["Plastic", "Paper", "Glass"])
    ref = rates(raw_rows({2022}, {"Kerala", "Gujarat"}, {"Plastic", "Paper", "Glass"}))
    kpi = dict(zip(rd.tables["kpi_summary"]["Metric"], rd.tables["kpi_summary"]["Value"]))
    assert kpi["Records selected"] == 6
    assert kpi["Collection Efficiency"] == pytest.approx(ref["ce"], abs=0.006)
    assert len(rd.tables["records_with_indicators"]) == 6
    assert set(rd.tables["state_summary"][C.STATE]) == {"Kerala", "Gujarat"}


def test_comparison_table_matches_raw_dataset(full):
    k, u = rates(raw_rows(states={"Kerala"})), rates(raw_rows(states={"Uttar Pradesh"}))
    t = full.tables["state_comparison"].set_index("Indicator")
    assert t.loc["Collection Efficiency", "Kerala"] == pytest.approx(k["ce"], abs=0.006)
    assert t.loc["Recycling Rate", "Uttar Pradesh"] == pytest.approx(u["rr"], abs=0.006)
    assert (t["Better"] == "Kerala").all()


def test_csv_bytes_round_trip_equals_table(full):
    t = full.tables["state_summary"]
    back = pd.read_csv(io.BytesIO(reports.csv_bytes(t)))
    pd.testing.assert_frame_equal(back, t.reset_index(drop=True), check_dtype=False)


def test_exports_match_dashboard_figures_to_one_decimal(full):
    """The dashboard shows 1 decimal; exported 2-decimal values must round to the same text."""
    from waste_analytics import indicators
    agg = indicators.aggregate(database.load_records(), C.STATE).set_index(C.STATE)
    t = full.tables["state_summary"].set_index(C.STATE)
    for s in agg.index:
        assert f"{t.loc[s, C.CE]:.1f}" == f"{agg.loc[s, C.CE]:.1f}"


def test_zip_contains_readme_and_every_table(full):
    z = zipfile.ZipFile(io.BytesIO(reports.zip_bytes(full)))
    names = set(z.namelist())
    assert "README.txt" in names and {f"{n}.csv" for n in full.tables} <= names
    readme = z.read("README.txt").decode()
    assert "not official standards" in readme and "Years: All (3)" in readme and "TPD" in readme
    assert len(pd.read_csv(io.BytesIO(z.read("state_summary.csv")))) == 10


def test_describe_filters():
    f = reports.describe_filters([2022], ["Kerala", "Goa"], [1], [2020, 2022], ["Kerala", "Goa", "X"], [1, 2])
    assert f == {"Years": "2022", "States": "Goa, Kerala", "Waste categories": "1"}


def test_empty_selection_is_rejected():
    empty = database.load_records().iloc[0:0]
    with pytest.raises(ValueError, match="no records"):
        reports.build_report_data(empty, {}, C.DEFAULT_THRESHOLDS, C.DEFAULT_PRIORITY)


# ------------------------------------------------------------------ PDF
def test_pdf_is_structurally_valid(full):
    pdf = reports.build_pdf(full)
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    start = int(re.search(rb"startxref\n(\d+)\n", pdf).group(1))
    assert pdf[start:start + 4] == b"xref"
    n_obj = int(re.search(rb"xref\n0 (\d+)\n", pdf).group(1))
    entries = re.findall(rb"(\d{10}) 00000 n ", pdf[start:])
    assert len(entries) == n_obj - 1
    for num, off in enumerate(entries, 1):                       # every xref offset points at "<n> 0 obj"
        assert pdf[int(off):].startswith(b"%d 0 obj" % num)
    pages = int(re.search(rb"/Count (\d+)", pdf).group(1))
    assert pages >= 2 and len(re.findall(rb"/Type /Page ", pdf)) == pages


def test_pdf_contains_title_filters_and_sections(full):
    text = pdf_text(reports.build_pdf(full))
    for needle in ("Waste Management Analytics System", "Years: All (3)", "States: All (10)",
                   "Waste categories: All (10)", "Key performance indicators", "State performance",
                   "State comparison: Kerala vs Uttar Pradesh", "Priority findings", "Rule-based insights",
                   "not official standards", "TPD (tonnes per day)", "unverified"):
        assert needle in text, needle


def test_pdf_numbers_match_raw_dataset(full):
    text = pdf_text(reports.build_pdf(full))
    ref = rates(raw_rows())
    assert f"{ref['gen']:,.0f}" in text and f"{ref['rec']:,.0f}" in text
    for key in ("ce", "te", "rr"):
        assert f"{ref[key]:.1f}%" in text
    kerala = rates(raw_rows(states={"Kerala"}))
    row = next(ln for ln in text.splitlines() if ln == "Kerala")
    assert row == "Kerala"
    assert f"{kerala['ce']:.1f}" in text and f"{kerala['te']:.1f}" in text
    up = rates(raw_rows(states={"Uttar Pradesh"}))
    assert f"{up['ce']:.1f}" in text


def test_pdf_reflects_the_filters():
    rd = make(None, years=[2022], states=["Kerala", "Gujarat"], types=["Plastic", "Paper"])
    text = pdf_text(reports.build_pdf(rd))
    ref = rates(raw_rows({2022}, {"Kerala", "Gujarat"}, {"Plastic", "Paper"}))
    assert "Years: 2022" in text and "States: Gujarat, Kerala" in text and "Waste categories: Paper, Plastic" in text
    assert "Records analysed: 4" in text and f"{ref['ce']:.1f}%" in text
    assert "Uttar Pradesh" not in text
    assert "State comparison" not in text           # no comparison was supplied


def test_pdf_footer_numbers_pages(full):
    pdf = reports.build_pdf(full)
    n = int(re.search(rb"/Count (\d+)", pdf).group(1))
    text = pdf_text(pdf)
    assert f"Page 1 of {n}" in text and f"Page {n} of {n}" in text


def test_pdf_writer_pagination_and_special_characters():
    doc = pdf_report.PDFDocument("T", "footer")
    doc.table(["A", "B"], [(f"row {i}", f"{i} ≤ 5 → (x) \\ ±") for i in range(120)], [200, 200])
    pdf = doc.to_bytes()
    n = int(re.search(rb"/Count (\d+)", pdf).group(1))
    assert n >= 3
    text = pdf_text(pdf)
    assert "row 119" in text and "<= 5 -> (x) \\ +/-" in text


def test_pdf_text_helpers():
    assert pdf_report.text_width("Hello", 10) > 0
    assert pdf_report.text_width("Hello", 10, bold=True) > pdf_report.text_width("Hello", 10)
    assert pdf_report.fit("a" * 200, 10, 50).endswith("...")
    assert all(pdf_report.text_width(ln, 10) <= 100 or " " not in ln for ln in pdf_report.wrap("word " * 40, 10, 100))
    assert pdf_report.clean("≤ → –") == "<= -> -"


# ------------------------------------------------------------------ exported figures == dashboard figures
def _display(v):
    return "n/a" if pd.isna(v) else f"{v:.1f}"


@pytest.mark.parametrize("years,states,types", [
    (None, None, None),
    ([2022], ["Kerala", "Gujarat", "Odisha"], None),
    ([2020, 2021], None, ["Plastic", "Paper", "Glass", "Metal"]),
])
def test_every_exported_value_displays_like_the_dashboard(years, states, types):
    """No row of any exported table may differ from the dashboard's 1-decimal display (no double rounding)."""
    rd = make(None, years=years, states=states, types=types)
    pdf = reports.build_pdf(rd)
    for name in ("state_summary", "category_summary_priority", "year_summary", "state_year_priority",
                 "records_with_indicators"):
        full, csv_table = rd.full[name], rd.tables[name]
        for col in C.INDICATORS + [C.SCORE]:
            if col in full.columns:
                same = [_display(a) == _display(b) for a, b in zip(full[col], csv_table[col])]
                assert all(same), f"{name}.{col}: CSV rounding changes the 1-decimal display"
    # the PDF cells equal the dashboard formatting, row by row
    text = pdf_text(pdf)
    for _, r in rd.full["state_year_priority"][lambda d: d["Priority"] == "High"].iterrows():
        cells = "\n".join([r[C.STATE], str(int(r[C.YEAR])), _display(r[C.CE]), _display(r[C.TE]),
                           _display(r[C.RR]), _display(r[C.SCORE])])
        assert cells in text, cells
    for _, r in rd.full["state_summary"].iterrows():
        cells = "\n".join([r[C.STATE], _display(r[C.CE]), _display(r[C.TE]), _display(r[C.RR]), _display(r[C.SCORE])])
        assert cells in text, cells
    for _, r in rd.full["category_summary_priority"].iterrows():
        cells = "\n".join([r[C.WTYPE], _display(r[C.CE]), _display(r[C.TE]), _display(r[C.RR]),
                           _display(r[C.SCORE]), r["Priority"]])
        assert cells in text, cells


def test_pdf_state_year_values_equal_the_priority_page_formatting():
    """West Bengal 2020 collection efficiency is 69.649...: the dashboard and the PDF must both show 69.6."""
    from waste_analytics import priority
    data = database.load_records()
    sy = priority.priority_by_state_year(data)
    row = sy[(sy[C.STATE] == "West Bengal") & (sy[C.YEAR] == 2020)].iloc[0]
    rd = make(None)
    text = pdf_text(reports.build_pdf(rd))
    assert f"{row[C.CE]:.1f}" == "69.6"
    assert "West Bengal\n2020\n69.6\n" in text


def test_csv_rates_are_unrounded_and_quantities_have_two_decimals(full):
    t = full.tables["state_summary"]
    f = full.full["state_summary"]
    assert (t[C.CE] == f[C.CE]).all() and (t[C.SCORE] == f[C.SCORE]).all()       # rates untouched
    assert (t[C.GEN] == f[C.GEN].round(2)).all()                                  # TPD quantities at 2 dp
    csv_back = pd.read_csv(io.BytesIO(reports.csv_bytes(t)))
    assert all(f"{a:.1f}" == f"{b:.1f}" for a, b in zip(csv_back[C.CE], f[C.CE]))
