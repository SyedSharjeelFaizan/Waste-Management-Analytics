"""Focused analysis: narrowing the data, running the unchanged rules, removing repeats, the summary values."""
import itertools

import pandas as pd
import pytest

from waste_analytics import config as C
from waste_analytics import database, insight_cards as IC, insight_focus as F, insights
from waste_analytics.indicators import aggregate

STATES = ["Gujarat", "Karnataka", "Kerala", "Maharashtra", "Odisha", "Rajasthan", "Tamil Nadu", "Telangana",
          "Uttar Pradesh", "West Bengal"]


@pytest.fixture(scope="module")
def data():
    return database.load_records()


def _key(r):
    return (r.rule, r.kind, r.indicator, r.year, round(r.value, 9), r.prev_year, r.change_pp)


# ---------------------------------------------------------------- the rules are untouched
def test_no_focus_is_exactly_the_existing_rules(data):
    frame, records = F.run_focus(data, F.Focus())
    assert frame.equals(data)
    assert records == insights.generate_insight_records(data)             # same findings, same order, same numbers
    assert len(records) == 41


def test_focus_never_changes_rule_numbers(data):
    """Every finding of a focused run equals the finding the rules produce for the same narrowed frame."""
    for focus in (F.Focus(state="Kerala"), F.Focus(wtype="Plastic"), F.Focus(state="Uttar Pradesh", wtype="Plastic"),
                  F.Focus(year=2021)):
        frame, records = F.run_focus(data, focus)
        reference = {_key(r) for r in insights.generate_insight_records(frame)}
        assert records and {_key(r) for r in records} <= reference


# ---------------------------------------------------------------- narrowing
def test_focus_frame_narrows_and_never_widens(data):
    sidebar = data[data[C.STATE].isin(["Kerala", "Gujarat"]) & data[C.YEAR].isin([2021, 2022])]
    assert len(F.focus_frame(sidebar, F.Focus())) == len(sidebar)
    kerala = F.focus_frame(sidebar, F.Focus(state="Kerala"))
    assert set(kerala[C.STATE]) == {"Kerala"} and set(kerala[C.YEAR]) == {2021, 2022}
    assert F.focus_frame(sidebar, F.Focus(state="Uttar Pradesh")).empty    # not in the sidebar selection: no records
    assert set(F.focus_frame(sidebar, F.Focus(year=2021))[C.YEAR]) == {2021}
    combo = F.focus_frame(sidebar, F.Focus(state="Kerala", wtype="Glass"))
    assert len(combo) == 2 and set(combo[C.WTYPE]) == {"Glass"}


def test_a_year_means_as_of_that_year(data):
    frame, records = F.run_focus(data, F.Focus(year=2021))
    assert frame[C.YEAR].max() == 2021
    assert {r.year for r in records} == {2021}
    assert any(r.prev_year == 2020 for r in records)                        # compared with the previous year
    first, records = F.run_focus(data, F.Focus(year=2020))
    assert records and all(r.kind == "Concern" and r.year == 2020 for r in records)   # nothing earlier to compare


def test_empty_frame_gives_no_findings(data):
    frame, records = F.run_focus(data.iloc[0:0], F.Focus(state="Kerala"))
    assert frame.empty and records == [] and F.performance_summary(frame, F.Focus()) == []
    frame, records = F.run_focus(data[data[C.STATE] == "Gujarat"], F.Focus(state="Kerala"))
    assert frame.empty and records == []


# ---------------------------------------------------------------- repeats are removed
def test_one_state_and_waste_type_is_one_subject(data):
    plain = insights.generate_insight_records(F.focus_frame(data, F.Focus(state="Uttar Pradesh", wtype="Plastic")))
    scope = {s: {_key(r) for r in plain if r.scope == s} for s in ("State", "Category", "Overall")}
    assert len(plain) == 13 and scope["State"] == scope["Category"]         # the rules report the same numbers ...
    assert scope["Overall"] <= scope["State"]                               # ... as State, Category and Overall
    _, records = F.run_focus(data, F.Focus(state="Uttar Pradesh", wtype="Plastic"))
    assert {_key(r) for r in records} == scope["State"] and len(records) == 5
    assert {r.scope for r in records} == {F.SELECTION} and {r.subject for r in records} == {"Uttar Pradesh · Plastic"}
    assert all(r.message.startswith("Uttar Pradesh · Plastic: ") for r in records)
    keys = [(r.rule, r.indicator) for r in records]
    assert len(keys) == len(set(keys))


def test_one_state_or_type_drops_the_overall_repeat_and_names_the_context(data):
    _, by_state = F.run_focus(data, F.Focus(state="Kerala"))
    assert not any(r.scope == "Overall" for r in by_state)
    assert {r.subject for r in by_state if r.scope == "State"} == {"Kerala"}
    assert all(r.subject.endswith(" (Kerala)") for r in by_state if r.scope == "Category")
    assert all(r.message.startswith(r.subject + ": ") for r in by_state)
    _, by_type = F.run_focus(data, F.Focus(wtype="Plastic"))
    assert not any(r.scope == "Overall" for r in by_type)
    assert {r.subject for r in by_type if r.scope == "Category"} == {"Plastic"}
    assert all(r.subject.endswith(" (Plastic)") for r in by_type if r.scope == "State")


def test_no_card_is_repeated_for_any_state_and_waste_type(data):
    for state, wtype in itertools.product(STATES, sorted(data[C.WTYPE].unique())):
        _, records = F.run_focus(data, F.Focus(state=state, wtype=wtype))
        cards = IC.build_cards(records)
        heads = [c.headline for c in cards]
        assert len(heads) == len(set(heads)), (state, wtype)
        assert all(c.scope == F.SELECTION and c.subject == f"{state} · {wtype}" for c in cards)


# ---------------------------------------------------------------- performance summary
def test_summary_values_equal_the_indicator_calculation(data):
    focus = F.Focus(state="Uttar Pradesh", wtype="Plastic")
    frame = F.focus_frame(data, focus)
    rows = F.performance_summary(frame, focus)
    by_year = aggregate(frame, C.YEAR).set_index(C.YEAR)
    assert [r.indicator for r in rows] == C.INDICATORS
    for r in rows:
        assert r.year == 2022 and r.value == pytest.approx(by_year.loc[2022, r.indicator])
        assert [y for y, _ in r.history] == [2020, 2021, 2022]
        assert [v for _, v in r.history] == pytest.approx(list(by_year[r.indicator]))
    ce, te, rr = rows
    assert (ce.threshold, te.threshold, rr.threshold) == (70.0, 60.0, 30.0)
    assert ce.shortfall == pytest.approx(70 - ce.value) and te.shortfall == pytest.approx(60 - te.value)
    assert rr.shortfall == 0.0                                              # recycling meets its threshold


def test_summary_follows_thresholds_indicator_and_year(data):
    focus = F.Focus(indicator=C.RR, year=2021)
    rows = F.performance_summary(F.focus_frame(data, focus), focus, C.InsightThresholds(70, 60, 90, 1))
    assert [r.indicator for r in rows] == [C.RR] and rows[0].year == 2021
    assert rows[0].threshold == 90.0 and rows[0].shortfall == pytest.approx(90 - rows[0].value)
    assert [y for y, _ in rows[0].history] == [2020, 2021]                  # only the years up to the chosen one


def test_summary_skips_an_indicator_without_a_value():
    frame = pd.DataFrame({C.YEAR: [2022], C.STATE: ["X"], C.WTYPE: ["Y"], C.GEN: [10.0], C.COL: [8.0],
                          C.TRT: [0.0], C.REC: [0.0]})
    rows = F.performance_summary(frame, F.Focus())
    assert [r.indicator for r in rows] == [C.CE, C.TE]                       # recycling rate is n/a (nothing treated)
    assert rows[0].history == ((2022, 80.0),)


def test_focus_labels():
    assert F.Focus().label == "All states · All types"
    assert F.Focus(state="Kerala", wtype="Glass").label == "Kerala · Glass"
    assert F.Focus(indicator=C.TE).indicators == [C.TE] and F.Focus().indicators == C.INDICATORS
    assert F.Focus(state="Kerala", wtype="Glass").is_combination and not F.Focus(state="Kerala").is_combination
