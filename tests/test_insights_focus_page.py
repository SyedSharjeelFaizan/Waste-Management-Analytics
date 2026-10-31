"""Insights page: Focused analysis (page-level State / Waste type / Year / Indicator selectors)."""
import csv
import re
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from waste_analytics import config as C  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
ALL_STATES = ["Gujarat", "Karnataka", "Kerala", "Maharashtra", "Odisha", "Rajasthan", "Tamil Nadu",
              "Telangana", "Uttar Pradesh", "West Bengal"]


def _app():
    at = AppTest.from_file(APP, default_timeout=90).run()
    at.main.radio[0].set_value("Insights").run()
    return at


def _cards(at):
    out = []
    for m in at.markdown:
        if 'class="igrid"' in m.value:
            out += ['<div class="icard ' + part for part in m.value.split('<div class="icard ')[1:]]
    return out


def _headlines(at):
    return [re.search(r'class="icard-h">([^<]*)<', c).group(1) for c in _cards(at)]


def _all_text(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [e.label for e in at.expander]
    return "\n".join(parts)


def _summary(at):
    """(High, Medium, Positive) counts from the summary pills."""
    html = " ".join(m.value for m in at.markdown)
    return tuple(int(re.search(rf"{s} · (\d+)", html).group(1)) for s in ("High", "Medium", "Positive"))


def _total(at):
    return int(re.search(r"Showing \d+ of (\d+) findings", _all_text(at)).group(1))


def _tiles(at):
    """({indicator name: value text}, html) of the performance summary."""
    strip = next(m.value for m in at.markdown if 'class="isum"' in m.value)
    return dict(re.findall(r'class="im-n">([^<]*)</div><div class="im-v">([\d.]+%)<', strip)), strip


def _raw_rate(num, den, state, wtype, year):
    """An indicator for one state, waste type and year, straight from the raw CSV."""
    with open(C.RAW_CSV, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if r["State"] == state and r["Waste_Type"] == wtype and r["Year"] == str(year)]
    return sum(float(r[num]) for r in rows) / sum(float(r[den]) for r in rows) * 100


# ---------------------------------------------------------------- selectors and the sidebar
def test_selectors_default_to_everything_and_list_the_sidebar_values():
    at = _app()
    assert not at.exception
    assert at.selectbox(key="ins_state").options == ["All states"] + ALL_STATES
    assert at.selectbox(key="ins_type").options[0] == "All types" and len(at.selectbox(key="ins_type").options) == 11
    assert at.selectbox(key="ins_year").options == ["All years", "2020", "2021", "2022"]
    assert at.selectbox(key="ins_ind").options == ["All indicators", "Collection efficiency",
                                                  "Treatment efficiency", "Recycling rate"]
    assert [at.selectbox(key=k).value for k in ("ins_state", "ins_type", "ins_year", "ins_ind")] == \
        ["All states", "All types", "All years", "All indicators"]


def test_selectors_only_offer_what_the_sidebar_filters_left():
    at = _app()
    at.sidebar.multiselect[0].set_value([2021, 2022])
    at.sidebar.multiselect[1].set_value(["Kerala", "Gujarat"])
    at.sidebar.multiselect[2].set_value(["Glass", "Metal"]).run()
    assert not at.exception
    assert at.selectbox(key="ins_state").options == ["All states", "Gujarat", "Kerala"]
    assert at.selectbox(key="ins_type").options == ["All types", "Glass", "Metal"]
    assert at.selectbox(key="ins_year").options == ["All years", "2021", "2022"]
    text = " ".join(_cards(at))
    assert "Uttar Pradesh" not in text and "Plastic" not in text
    assert "2020" not in _tiles(at)[1]                        # the history uses only the sidebar-selected years


def test_a_selection_that_the_sidebar_removes_falls_back_to_all():
    at = _app()
    at.selectbox(key="ins_state").set_value("Kerala").run()
    assert at.selectbox(key="ins_state").value == "Kerala"
    at.sidebar.multiselect[1].set_value(["Gujarat"]).run()
    assert not at.exception and at.selectbox(key="ins_state").value == "All states"
    assert all("Kerala" not in h for h in _headlines(at))


def test_reset_filters_also_resets_the_focus():
    at = _app()
    at.selectbox(key="ins_state").set_value("Kerala").run()
    at.selectbox(key="ins_ind").set_value("Recycling rate").run()
    at.button(key="reset_btn").click().run()
    assert not at.exception
    assert at.selectbox(key="ins_state").value == "All states" and at.selectbox(key="ins_ind").value == "All indicators"
    assert _total(at) == 32


# ---------------------------------------------------------------- focus on a state, a waste type or both
def test_one_state_shows_that_state_and_its_waste_categories_without_repeats():
    at = _app()
    at.selectbox(key="ins_state").set_value("Kerala").run()
    at.toggle(key="ins_all").set_value(True).run()
    assert not at.exception
    heads = _headlines(at)
    assert heads and len(heads) == len(set(heads))             # nothing is repeated
    assert all(h.startswith("Kerala:") or "(Kerala)" in h.split(":")[0] for h in heads)
    assert not any(h.startswith("Overall") for h in heads)     # Overall would repeat the state's own finding
    assert "Uttar Pradesh" not in " ".join(_cards(at))


def test_one_waste_type_shows_that_type_and_its_states_without_repeats():
    at = _app()
    at.selectbox(key="ins_type").set_value("Plastic").run()
    at.toggle(key="ins_all").set_value(True).run()
    heads = _headlines(at)
    assert heads and len(heads) == len(set(heads))
    assert not any(h.startswith("Overall") for h in heads)
    assert any(h.startswith("Plastic:") for h in heads)
    assert all(h.startswith("Plastic:") or "(Plastic)" in h.split(":")[0] for h in heads)


def test_one_state_and_one_waste_type_give_findings_specific_to_that_combination():
    at = _app()
    at.selectbox(key="ins_state").set_value("Uttar Pradesh").run()
    at.selectbox(key="ins_type").set_value("Plastic").run()
    assert not at.exception
    assert _headlines(at) == ["Uttar Pradesh · Plastic: collection and treatment are below threshold",
                              "Uttar Pradesh · Plastic: treatment is slipping",
                              "Uttar Pradesh · Plastic: collection and recycling are improving"]
    first = _cards(at)[0]
    assert "sev-high" in first and "Main issue" in first and '>State and waste type<' in first
    assert "Suggested action" in first and "Threshold 70%" in first and "Threshold 60%" in first
    ce = _raw_rate(C.COL, C.GEN, "Uttar Pradesh", "Plastic", 2022)
    te = _raw_rate(C.TRT, C.COL, "Uttar Pradesh", "Plastic", 2022)
    assert f"{ce:.1f}%" in first and f"{te:.1f}%" in first                 # the actual indicator values
    assert sum("Main issue" in c for c in _cards(at)) == 1                 # only the first card is the main issue
    assert at.multiselect(key="ins_scopes").disabled                       # one subject: nothing to choose
    rule_table = next(d.value for d in at.dataframe if "Insight" in d.value.columns)
    assert set(rule_table["Scope"]) == {"Selection"}
    assert all(m.startswith("Uttar Pradesh · Plastic:") for m in rule_table["Insight"])


def test_performance_summary_shows_the_focused_values_and_their_history():
    at = _app()
    at.selectbox(key="ins_state").set_value("Uttar Pradesh").run()
    at.selectbox(key="ins_type").set_value("Plastic").run()
    tiles, strip = _tiles(at)
    assert tiles == {
        "Collection efficiency": f"{_raw_rate(C.COL, C.GEN, 'Uttar Pradesh', 'Plastic', 2022):.1f}%",
        "Treatment efficiency": f"{_raw_rate(C.TRT, C.COL, 'Uttar Pradesh', 'Plastic', 2022):.1f}%",
        "Recycling rate": f"{_raw_rate(C.REC, C.TRT, 'Uttar Pradesh', 'Plastic', 2022):.1f}%"}
    for year in (2020, 2021, 2022):                                         # history across every available year
        assert f"{year} {_raw_rate(C.COL, C.GEN, 'Uttar Pradesh', 'Plastic', year):.1f}%" in strip
    assert "11.1 pp below the 70% threshold" in strip and "Meets the 30% threshold" in strip


# ---------------------------------------------------------------- year and indicator
def test_year_focus_checks_that_year_and_compares_it_with_the_previous_one():
    at = _app()
    at.selectbox(key="ins_year").set_value("2021").run()
    at.toggle(key="ins_all").set_value(True).run()                          # the top five are all threshold concerns
    assert not at.exception
    text = " ".join(_cards(at))
    assert "2022" not in text and "2020 → 2021" in text
    assert "Findings are for 2021; changes compare 2020 with 2021" in _all_text(at)
    at.selectbox(key="ins_year").set_value("2020").run()                    # earliest year: nothing to compare with
    assert not at.exception and _cards(at) and "→" not in " ".join(_cards(at)) and _summary(at)[2] == 0


def test_indicator_focus_keeps_only_that_indicator_everywhere():
    at = _app()
    at.selectbox(key="ins_ind").set_value("Treatment efficiency").run()
    at.toggle(key="ins_all").set_value(True).run()
    assert not at.exception
    names = {n for c in _cards(at) for n in re.findall(r'class="im-n">([^<]*)<', c)}
    assert names == {"Treatment efficiency"}
    assert list(_tiles(at)[0]) == ["Treatment efficiency"]                 # the summary follows the indicator too
    assert sum(_summary(at)) == _total(at)


def test_selectors_work_together_with_the_show_filter_and_the_thresholds():
    at = _app()
    at.selectbox(key="ins_state").set_value("Uttar Pradesh").run()
    before = _summary(at)
    at.multiselect(key="ins_kinds").set_value(["Concerns"]).run()
    assert _cards(at) and all("sev-positive" not in c for c in _cards(at))
    at.sidebar.expander[0].slider[0].set_value(100).run()                  # low-collection threshold -> 100
    after = _summary(at)
    assert not at.exception and after[0] + after[1] >= before[0] + before[1]


# ---------------------------------------------------------------- empty states and the default view
def test_helpful_empty_state_when_the_focus_has_no_findings():
    at = _app()
    at.selectbox(key="ins_state").set_value("Kerala").run()
    at.selectbox(key="ins_type").set_value("Plastic").run()
    at.selectbox(key="ins_year").set_value("2020").run()
    assert not at.exception and _cards(at) == []
    text = _all_text(at)
    assert "No significant insight identified for this selection" in text
    assert "for Kerala · Plastic" in text and "earliest selected year" in text and "Try All states" in text
    assert any('class="isum"' in m.value for m in at.markdown)              # the summary still tells the story


def test_empty_state_when_only_the_chosen_indicator_has_no_findings():
    at = _app()
    at.selectbox(key="ins_state").set_value("Kerala").run()
    at.selectbox(key="ins_type").set_value("Plastic").run()
    assert _total(at) == 1 and all("Main issue" not in c for c in _cards(at))   # improvements only: no main issue
    at.selectbox(key="ins_ind").set_value("Collection efficiency").run()
    assert not at.exception and _cards(at) == []
    assert "No collection efficiency findings for this selection" in _all_text(at)
    assert "Choose All indicators" in _all_text(at)


def test_default_shows_five_most_important_and_all_on_request():
    at = _app()
    sev = [re.search(r"sev-(\w+)", c).group(1) for c in _cards(at)]
    assert len(sev) == 5 and sev == sorted(sev, key=["high", "medium", "positive"].index)
    assert "Main issue" in _cards(at)[0] and "Main issue" not in " ".join(_cards(at)[1:])
    toggle = at.toggle(key="ins_all")
    assert toggle.label == "Show all findings (32)"
    toggle.set_value(True).run()
    assert len(_cards(at)) == 32
