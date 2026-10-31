"""Insights page (cards) behaviour, and the removed website text."""
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
PAGES = ["Overview", "State Comparison", "Year Trends", "Waste Categories", "Priority", "Insights", "Reports"]


def _app(page=None):
    at = AppTest.from_file(APP, default_timeout=90).run()
    if page:
        at.main.radio[0].set_value(page).run()
    return at


def _cards(at):
    """The card HTML strings (all cards are rendered in one grid element)."""
    out = []
    for m in at.markdown:
        if 'class="igrid"' in m.value:
            out += ['<div class="icard ' + part for part in m.value.split('<div class="icard ')[1:]]
    return out


def _all_text(at):
    parts = [m.value for m in at.get("markdown")] + [c.value for c in at.caption] + [e.label for e in at.expander]
    parts += [str(getattr(w, "value", "")) for w in list(at.warning) + list(at.info) + list(at.error)]
    return "\n".join(parts)


def _summary(at):
    """(High, Medium, Positive) counts from the summary pills."""
    html = " ".join(m.value for m in at.markdown)
    return tuple(int(re.search(rf"{s} · (\d+)", html).group(1)) for s in ("High", "Medium", "Positive"))


def _total(at):
    return int(re.search(r"Showing \d+ of (\d+) findings", _all_text(at)).group(1))


# ---------------------------------------------------------------- insight cards
def test_cards_are_the_main_experience():
    at = _app("Insights")
    assert not at.exception, at.exception
    cards = _cards(at)
    assert len(cards) == 5                                     # the 5 most important of 32
    first = cards[0]
    for part in ("sev-high", "Uttar Pradesh: collection and treatment are below threshold", "Suggested action",
                 "State: Uttar Pradesh", "57.3%", "54.5%", "Threshold 70%", "Collection efficiency",
                 "Treatment efficiency"):
        assert part in first, part
    assert _summary(at) == (3, 8, 21) and _total(at) == 32
    assert "Showing 5 of 32 findings, most important first" in _all_text(at)


def test_each_card_has_headline_explanation_scope_value_action_and_severity():
    at = _app("Insights")
    for c in _cards(at):
        assert re.search(r'class="legend-pill p-(high|med|norm)">(High|Medium|Positive)<', c)
        for cls in ("icard-h", "icard-t", "imetrics", "im-v", "iaction", "ichip"):
            assert f'class="{cls}' in c, cls
        assert re.search(r'class="im-v">\d+\.\d%<', c)


def test_cards_are_ordered_by_importance():
    at = _app("Insights")
    sev = [re.search(r"sev-(\w+)", c).group(1) for c in _cards(at)]
    rank = {"high": 0, "medium": 1, "positive": 2}
    assert [rank[s] for s in sev] == sorted(rank[s] for s in sev)
    assert sev[:3] == ["high"] * 3


def test_table_is_only_an_optional_collapsed_detail_view():
    at = _app("Insights")
    assert any(e.label == "Rule details (table)" for e in at.expander)
    detail = [d for d in at.dataframe if "Insight" in d.value.columns]
    assert len(detail) == 1 and len(detail[0].value) == 41      # every fired rule, with its rule id


def test_show_all_toggle_reveals_every_finding():
    at = _app("Insights")
    at.toggle(key="ins_all").set_value(True).run()
    assert not at.exception and len(_cards(at)) == 32
    assert "Showing 32 of 32" in _all_text(at)


# ---------------------------------------------------------------- dynamic with filters
def test_cards_update_with_the_sidebar_state_filter():
    at = _app("Insights")
    at.sidebar.multiselect[1].set_value(["Kerala"]).run()
    assert not at.exception
    text = " ".join(_cards(at))
    assert "Uttar Pradesh" not in text and "Rajasthan" not in text
    assert _total(at) < 32


def test_cards_update_with_the_year_filter():
    at = _app("Insights")
    at.sidebar.multiselect[0].set_value([2022]).run()          # one year: no year-on-year findings
    assert _summary(at)[2] == 0
    assert "→" not in " ".join(_cards(at))
    at.sidebar.multiselect[0].set_value([2020, 2021]).run()
    at.toggle(key="ins_all").set_value(True).run()             # the default five are all threshold concerns
    assert "High priority" not in " ".join(_cards(at)) and any("2020 → 2021" in c for c in _cards(at))


def test_cards_update_with_the_waste_category_filter():
    at = _app("Insights")
    at.sidebar.multiselect[2].set_value(["Glass", "Metal"]).run()
    assert not at.exception
    text = " ".join(_cards(at))
    assert "Construction" not in text and "Biomedical" not in text


def test_cards_update_with_the_thresholds():
    at = _app("Insights")
    before = _summary(at)
    at.sidebar.expander[0].slider[0].set_value(100).run()      # low-collection threshold -> 100
    after = _summary(at)
    assert after[0] + after[1] > before[0] + before[1]


def test_page_filters_show_and_indicator_and_scope():
    at = _app("Insights")
    at.multiselect(key="ins_kinds").set_value(["Concerns"]).run()
    assert not at.exception and _total(at) == 7
    assert all("sev-positive" not in c for c in _cards(at))
    at.selectbox(key="ins_ind").set_value("Recycling rate").run()
    assert _total(at) == 3 and all("Collection efficiency" not in c for c in _cards(at))
    at.multiselect(key="ins_kinds").set_value(["Concerns", "Declines", "Improvements"]).run()
    at.multiselect(key="ins_scopes").set_value(["Overall"]).run()
    assert not at.exception and all("Overall" in c for c in _cards(at))


def test_no_match_message_when_page_filters_leave_nothing():
    at = _app("Insights")
    at.multiselect(key="ins_kinds").set_value([]).run()
    assert not at.exception and _cards(at) == []
    assert "No insights match these options" in _all_text(at)


def test_clean_message_when_no_rule_matches():
    at = _app("Insights")
    for i in range(3):
        at.sidebar.expander[0].slider[i].set_value(0)
    at.sidebar.expander[0].slider[3].set_value(10.0).run()
    assert not at.exception and _cards(at) == []
    text = _all_text(at)
    assert "No significant insight identified for this selection" in text
    assert "no change larger than ±10 pp" in text


def test_clean_message_explains_single_year_case():
    at = _app("Insights")
    at.sidebar.multiselect[0].set_value([2022])
    at.sidebar.multiselect[1].set_value(["Kerala"])
    at.sidebar.multiselect[2].set_value(["Glass", "Metal"]).run()
    assert not at.exception and _cards(at) == []
    assert "Select two or more years" in _all_text(at)


# ---------------------------------------------------------------- removed website text
REMOVED = ["B.Tech CSE", "Semester VI", "2026–27", "MRG:", "Cloud Computing and Data Science",
           "Dataset provenance unverified", "likely synthetic",
           "Thresholds are project-defined, not official standards",
           "Project-defined values, not official standards",
           "project-defined, not official standards", "which are also project-defined",
           "academic project", "indicators are computed from aggregated TPD quantities"]


@pytest.mark.parametrize("page", PAGES)
def test_removed_text_is_gone_from_every_page(page):
    at = _app(page)
    assert not at.exception, at.exception
    text = _all_text(at)
    for phrase in REMOVED:
        assert phrase not in text, f"{phrase!r} still visible on {page}"
    assert 'side-h">About<' not in text and 'class="foot"' not in text
    assert "About" not in list(at.main.radio[0].options)
