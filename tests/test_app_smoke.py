"""Headless dashboard tests: every page renders and the interactive features behave."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
PAGES = ["Overview", "State Comparison", "Year Trends", "Waste Categories",
         "Priority", "Insights", "Reports"]
ALL_STATES = ["Gujarat", "Karnataka", "Kerala", "Maharashtra", "Odisha", "Rajasthan", "Tamil Nadu",
              "Telangana", "Uttar Pradesh", "West Bengal"]


def _app(page=None):
    at = AppTest.from_file(APP, default_timeout=90).run()
    if page:
        at.main.radio[0].set_value(page).run()
    return at


def _texts(at):
    return " ".join([m.value for m in at.markdown] + [w.value for w in at.warning] + [i.value for i in at.info])


def test_app_runs_and_offers_all_pages():
    at = _app()
    assert not at.exception, at.exception
    assert list(at.main.radio[0].options) == PAGES
    assert len(at.metric) >= 7  # overview KPI cards


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders(page):
    at = _app(page)
    assert not at.exception, at.exception


def test_empty_filter_shows_friendly_empty_state():
    at = _app()
    at.sidebar.multiselect[0].set_value([]).run()
    assert not at.exception
    assert "No records match the current filters" in _texts(at)
    assert any(b.label.endswith("Reset filters") for b in at.button)


@pytest.mark.parametrize("page", ["Overview", "Year Trends", "Insights", "Priority", "Reports", "State Comparison"])
def test_single_year_runs(page):
    at = _app(page)
    at.sidebar.multiselect[0].set_value([2022]).run()
    assert not at.exception, at.exception


# ---------------------------------------------------------------- reset filters
def test_reset_filters_restores_filters_and_settings():
    at = _app()
    at.sidebar.multiselect[0].set_value([2022])
    at.sidebar.multiselect[1].set_value(["Kerala"])
    at.sidebar.multiselect[2].set_value(["Plastic"]).run()
    at.sidebar.expander[0].slider[0].set_value(55).run()
    assert at.sidebar.multiselect[1].value == ["Kerala"]
    next(b for b in at.sidebar.button if b.key == "reset_btn").click().run()
    assert not at.exception
    assert at.sidebar.multiselect[0].value == [2020, 2021, 2022]
    assert at.sidebar.multiselect[1].value == ALL_STATES
    assert len(at.sidebar.multiselect[2].value) == 10
    assert at.sidebar.expander[0].slider[0].value == 70


def test_reset_button_in_empty_state_works():
    at = _app()
    at.sidebar.multiselect[1].set_value([]).run()
    next(b for b in at.main.button if b.key == "reset_main").click().run()
    assert at.sidebar.multiselect[1].value == ALL_STATES
    assert "No records match" not in _texts(at)


# ---------------------------------------------------------------- head-to-head
def test_head_to_head_default_and_selection():
    at = _app("State Comparison")
    assert (at.selectbox(key="h2h_a").value, at.selectbox(key="h2h_b").value) == ("Kerala", "Uttar Pradesh")
    assert "Better:" in _texts(at)
    at.selectbox(key="h2h_a").set_value("Gujarat").run()
    at.selectbox(key="h2h_b").set_value("Rajasthan").run()
    assert not at.exception
    assert at.selectbox(key="h2h_a").value == "Gujarat" and at.selectbox(key="h2h_b").value == "Rajasthan"
    text = _texts(at)
    assert "Gujarat" in text and "Rajasthan" in text and "has the higher composite score" in text


def test_head_to_head_same_state_shows_message():
    at = _app("State Comparison")
    at.selectbox(key="h2h_b").set_value("Kerala").run()
    assert not at.exception
    assert "Choose two different states" in _texts(at)


def test_head_to_head_ignores_state_filter_but_respects_year_filter():
    at = _app("State Comparison")
    at.sidebar.multiselect[1].set_value(["Odisha"]).run()          # State filter must not break the comparison
    assert not at.exception and "Choose two different states" not in _texts(at)
    at.sidebar.multiselect[0].set_value([2021]).run()
    assert not at.exception


def test_heatmap_controls():
    at = _app("State Comparison")
    for rows in ("States", "Waste categories"):
        at.radio(key="hm_rows").set_value(rows).run()
        assert not at.exception
    at.radio(key="hm_mode").set_value("Relative (within each indicator)").run()
    assert not at.exception
    for opt in list(at.selectbox(key="hm_sort").options):
        at.selectbox(key="hm_sort").set_value(opt).run()
        assert not at.exception


# ---------------------------------------------------------------- explainable priority
def test_priority_explanation_defaults_to_highest_concern_unit():
    at = _app("Priority")
    text = _texts(at)
    assert "Why this priority?" in text
    assert "High priority" in text and "Uttar Pradesh" in text


def test_priority_explanation_for_every_unit():
    at = _app("Priority")
    n_units = len(at.selectbox(key="ex_unit_sy").options)
    assert n_units == 30
    for i in range(0, n_units, 5):
        at.selectbox(key="ex_unit_sy").select_index(i).run()
        assert not at.exception
    at.selectbox(key="ex_unit_sy").select_index(29).run()      # a high index, then switch kind
    at.radio(key="ex_kind").set_value("Waste category").run()
    assert not at.exception
    n_cat = len(at.selectbox(key="ex_unit_cat").options)
    assert n_cat == 10
    for i in range(n_cat):
        at.selectbox(key="ex_unit_cat").select_index(i).run()
        assert not at.exception
    assert any("not official guidance" in c.value for c in at.caption)


def test_priority_page_with_few_units_warns_instead_of_crashing():
    at = _app("Priority")
    at.sidebar.multiselect[0].set_value([2022]).run()
    at.sidebar.multiselect[1].set_value(["Kerala"]).run()
    assert not at.exception
    assert any("Fewer than 3" in w.value for w in at.warning)


# ---------------------------------------------------------------- reports and methodology
def _summary_strip(at):
    """The text of the compact export summary on the Reports page."""
    strips = [m.value for m in at.markdown if 'class="rsum"' in m.value]
    assert len(strips) == 1
    return strips[0]


def test_reports_page_builds_exports():
    at = _app("Reports")
    assert not at.exception and not at.error
    strip = _summary_strip(at)
    for part in ("<b>300</b><span>records", "<b>2020–2022</b><span>years", "<b>10</b><span>states",
                 "<b>10</b><span>waste categories",
                 "Exports use the current dashboard filters and analysis settings."):
        assert part in strip, part
    assert not at.metric                                           # the large Report scope section is gone
    text = _texts(at)
    assert "Report scope" not in text and "State comparison included" not in text
    assert "Kerala" not in strip and "Uttar Pradesh" not in strip and " vs " not in strip


def test_reports_page_updates_with_filters():
    at = _app("Reports")
    at.sidebar.multiselect[0].set_value([2022]).run()
    at.sidebar.multiselect[1].set_value(["Kerala", "Gujarat"]).run()
    assert not at.exception and not at.error
    strip = _summary_strip(at)
    assert "<b>20</b><span>records" in strip and "<b>2022</b><span>year<" in strip
    assert "<b>2</b><span>states" in strip and "<b>10</b><span>waste categories" in strip
    at.sidebar.multiselect[0].set_value([2020, 2022]).run()        # not contiguous: listed, not a range
    assert "<b>2020, 2022</b><span>years" in _summary_strip(at)
    at.sidebar.multiselect[1].set_value(["Kerala"]).run()
    assert "<b>1</b><span>state<" in _summary_strip(at)
