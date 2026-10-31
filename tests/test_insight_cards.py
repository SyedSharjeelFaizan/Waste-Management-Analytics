"""Insight cards: built only from the existing rule results; numbers must match the calculations."""
import csv

import pandas as pd
import pytest

from waste_analytics import config as C
from waste_analytics import database, explain, insight_cards as IC, insights
from waste_analytics.insights import Insight


@pytest.fixture(scope="module")
def data():
    return database.load_records()


@pytest.fixture(scope="module")
def records(data):
    return insights.generate_insight_records(data)


def concern(subject="X", ind=C.CE, value=60.0, thr=70.0, scope="State", year=2022):
    rule = {C.CE: "R1", C.TE: "R2", C.RR: "R3"}[ind]
    return Insight(rule, "Concern", scope, subject, "msg", indicator=ind, year=year, value=value, threshold=thr)


def trend(kind, change, subject="X", ind=C.CE, scope="State", prev=70.0):
    return Insight("R4" if kind == "Improvement" else "R5", kind, scope, subject, "msg", indicator=ind, year=2022,
                   value=prev + change, prev_year=2021, prev_value=prev, change_pp=change)


# ---------------------------------------------------------------- the existing rules are unchanged
def test_rule_table_is_unchanged(data):
    t = insights.generate_insights(data)
    assert list(t.columns) == ["Rule", "Kind", "Scope", "Subject", "Insight"]
    assert t["Rule"].value_counts().sort_index().to_dict() == {"R1": 4, "R2": 3, "R3": 3, "R4": 27, "R5": 4}
    assert "Uttar Pradesh: collection-performance concern in 2022 - collection efficiency is 57.3%, below the " \
           "project threshold of 70%." in set(t["Insight"])


def test_records_carry_the_numbers_behind_each_message(records):
    assert len(records) == 41
    for r in records:
        assert r.indicator in C.INDICATORS and r.year == 2022 and r.value is not None
        assert f"{r.value:.1f}%" in r.message
        if r.kind == "Concern":
            assert r.value < r.threshold and f"{r.threshold:g}%" in r.message
        else:
            assert r.prev_year == 2021
            assert r.value - r.prev_value == pytest.approx(r.change_pp)
            assert f"{r.change_pp:+.1f} pp" in r.message


def test_record_values_equal_an_independent_raw_csv_calculation(records):
    with open(C.RAW_CSV, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["State"] == "Uttar Pradesh" and r["Year"] == "2022"]
    ce = sum(float(r[C.COL]) for r in rows) / sum(float(r[C.GEN]) for r in rows) * 100
    te = sum(float(r[C.TRT]) for r in rows) / sum(float(r[C.COL]) for r in rows) * 100
    up = {r.indicator: r for r in records if r.kind == "Concern" and r.subject == "Uttar Pradesh"}
    assert up[C.CE].value == pytest.approx(ce) and up[C.TE].value == pytest.approx(te)


# ---------------------------------------------------------------- cards
def test_cards_from_real_data(records):
    cards = IC.build_cards(records)
    assert len(cards) == 32
    assert IC.severity_counts(cards) == {"High": 3, "Medium": 8, "Positive": 21}
    assert sum(len(c.metrics) for c in cards) == len(records)          # merging loses no finding


def test_no_repeated_cards_for_the_same_subject_and_kind(records):
    cards = IC.build_cards(records)
    keys = [(c.kind, c.scope, c.subject) for c in cards]
    assert len(keys) == len(set(keys))
    up = next(c for c in cards if c.subject == "Uttar Pradesh" and c.kind == "Concern")
    assert up.headline == "Uttar Pradesh: collection and treatment are below threshold"
    assert [round(m.value, 1) for m in up.metrics] == [57.3, 54.5] and up.severity == "High"
    assert up.rules == ["R1", "R2"] and up.year_label == "2022"


def test_most_important_findings_come_first(records):
    cards = IC.build_cards(records)
    order = [IC.SEVERITY_ORDER[c.severity] for c in cards]
    assert order == sorted(order)
    for sev in ("High", "Medium", "Positive"):
        sizes = [c.size for c in cards if c.severity == sev]
        assert sizes == sorted(sizes, reverse=True)
    assert cards[0].severity == "High" and cards[-1].severity == "Positive"


def test_card_text_uses_the_calculated_values(records):
    for c in IC.build_cards(records):
        for m in c.metrics:
            assert f"{m.value:.1f}%" in c.summary
        assert c.summary and c.actions and c.headline.startswith(c.subject)


@pytest.mark.parametrize("value,expected", [(57.3, "High"), (60.0, "High"), (60.1, "Medium"), (69.9, "Medium")])
def test_concern_severity_rule(value, expected):
    assert IC.build_cards([concern(value=value)])[0].severity == expected      # threshold 70, High at >= 10 pp


@pytest.mark.parametrize("change,expected", [(-5.0, "High"), (-4.9, "Medium"), (-1.2, "Medium")])
def test_decline_severity_rule(change, expected):
    assert IC.build_cards([trend("Deterioration", change)])[0].severity == expected


def test_improvement_is_positive():
    c = IC.build_cards([trend("Improvement", 2.8)])[0]
    assert c.severity == "Positive" and c.headline == "X: collection is improving"
    assert "+2.8" in c.summary and "70.0% in 2021" in c.summary and c.year_label == "2021 → 2022"


def test_headlines_for_one_two_and_three_indicators():
    one = IC.build_cards([concern(ind=C.RR, value=20, thr=30)])[0].headline
    two = IC.build_cards([concern(ind=C.CE), concern(ind=C.TE, value=50, thr=60)])[0].headline
    three = IC.build_cards([concern(ind=C.CE), concern(ind=C.TE, value=50, thr=60),
                            concern(ind=C.RR, value=20, thr=30)])[0].headline
    assert one == "X: recycling rate is low"
    assert two == "X: collection and treatment are below threshold"
    assert three == "X: collection, treatment and recycling are below threshold"


def test_overall_scope_is_labelled_overall():
    c = IC.build_cards([trend("Improvement", 2.0, subject="All data", scope="Overall")])[0]
    assert c.headline.startswith("Overall:") and c.scope == "Overall"


def test_suggested_actions_reuse_the_rule_text_without_claiming_authority():
    c = IC.build_cards([concern(ind=C.CE), concern(ind=C.RR, value=20, thr=30)])[0]
    rule_text = explain.SUGGESTION_RULES[C.CE].split(": ", 1)[1]
    assert c.actions[0] == rule_text[0].upper() + rule_text[1:]
    assert c.actions[0].startswith("Review collection coverage") and not c.actions[0].startswith("Collection:")
    for card in IC.build_cards(insights.generate_insight_records(database.load_records())):
        assert all("official" not in a.lower() for a in card.actions)


def test_records_without_numbers_are_ignored():
    legacy = Insight("R1", "Concern", "State", "X", "old style record")
    assert IC.build_cards([legacy]) == []


# ---------------------------------------------------------------- filtering and dynamics
def test_filter_records(records):
    assert len(IC.filter_records(records)) == 41
    only_concern = IC.filter_records(records, kinds={"Concern"})
    assert len(only_concern) == 10 and {r.kind for r in only_concern} == {"Concern"}
    recycling = IC.filter_records(records, indicators={C.RR})
    assert recycling and {r.indicator for r in recycling} == {C.RR}
    overall = IC.filter_records(records, scopes={"Overall"})
    assert {r.scope for r in overall} == {"Overall"} and len(overall) == 1   # only collection moved > 1 pp
    assert IC.filter_records(records, kinds=set()) == []


def test_cards_follow_the_filters_and_thresholds(data):
    kerala = data[data[C.STATE] == "Kerala"]
    cards = IC.build_cards(insights.generate_insight_records(kerala))
    assert not any(c.subject == "Uttar Pradesh" for c in cards)
    strict = IC.build_cards(insights.generate_insight_records(data, C.InsightThresholds(100, 100, 100, 0)))
    lax = IC.build_cards(insights.generate_insight_records(data, C.InsightThresholds(0, 0, 0, 10)))
    assert IC.severity_counts(strict)["High"] > 3
    assert lax == []                                         # nothing below threshold, no change above 10 pp


def test_single_year_gives_no_trend_cards(data):
    cards = IC.build_cards(insights.generate_insight_records(data[data[C.YEAR] == 2022]))
    assert cards and {c.kind for c in cards} == {"Concern"}


def test_empty_input_gives_no_cards():
    assert IC.build_cards(insights.generate_insight_records(pd.DataFrame(columns=C.REQUIRED_COLS))) == []
