import pandas as pd
import pytest

from waste_analytics import config as C
from waste_analytics import database, explain, priority


def _frame(scores, ce=None, te=None, rr=None):
    n = len(scores)
    df = pd.DataFrame({C.STATE: list("ABCDEF")[:n], C.CE: ce or scores, C.TE: te or scores, C.RR: rr or scores})
    return priority.classify_priority(df)


def test_high_priority_explanation():
    prio = _frame([10, 20, 30, 40, 50, 60])
    ex = explain.explain_unit(prio, 0, "A")
    assert ex.level == "High" and ex.rank == 1 and ex.n_units == 6
    assert ex.composite == pytest.approx(10)
    text = " ".join(ex.reasons)
    assert "High cut-off" in text and "classified High priority" in text
    assert "to leave High" in text
    assert ex.high_cut == pytest.approx(prio.attrs["cutoffs"]["high"])


def test_medium_and_normal_explanations():
    prio = _frame([10, 20, 30, 40, 50, 60])
    med = explain.explain_unit(prio, 2, "C")
    nor = explain.explain_unit(prio, 5, "F")
    assert med.level == "Medium" and "classified Medium priority" in " ".join(med.reasons)
    assert nor.level == "Normal" and "classified Normal priority" in " ".join(nor.reasons)
    assert nor.rank == 6


def test_components_and_composite_are_consistent():
    prio = _frame([50, 60, 70], ce=[90, 60, 30], te=[60, 60, 60], rr=[0, 60, 120])
    ex = explain.explain_unit(prio, 0, "A")
    assert ex.components == {C.CE: 90, C.TE: 60, C.RR: 0}
    assert ex.composite == pytest.approx(50.0)
    assert ex.gap_vs_median[C.CE] == pytest.approx(30)      # median CE is 60
    assert ex.main_driver == C.RR                            # 0 versus median 60


def test_suggestions_follow_threshold_rules():
    prio = _frame([10, 20, 30, 40, 50, 60], ce=[60, 80, 80, 80, 80, 80], te=[50, 70, 70, 70, 70, 70],
                  rr=[10, 40, 40, 40, 40, 40])
    t = C.InsightThresholds(low_collection=70, low_treatment=60, low_recycling=30)
    ex = explain.explain_unit(prio, 0, "A", thresholds=t)
    joined = " ".join(ex.suggestions)
    assert ex.below_threshold == [C.CE, C.TE, C.RR]
    assert "Collection:" in joined and "Treatment:" in joined and "Recycling:" in joined
    lax = explain.explain_unit(prio, 0, "A", thresholds=C.InsightThresholds(0, 0, 0))
    assert lax.below_threshold == []
    assert "Collection:" not in " ".join(lax.suggestions)


def test_normal_unit_without_issues_gets_maintain_suggestion():
    prio = _frame([10, 20, 30, 40, 50, 90])
    ex = explain.explain_unit(prio, 5, "F", thresholds=C.InsightThresholds(0, 0, 0))
    assert ex.level == "Normal" and "maintain current practice" in ex.suggestions[0]


def test_trend_decline_adds_suggestion():
    prio = _frame([10, 20, 30, 40, 50, 60])
    ex = explain.explain_unit(prio, 0, "A", thresholds=C.InsightThresholds(0, 0, 0),
                              trend={C.CE: -4.0, C.TE: 0.5, C.RR: 2.0, "year": 2022})
    assert any("decline in collection efficiency" in s for s in ex.suggestions)
    assert not any("decline in treatment" in s for s in ex.suggestions)


def test_wording_never_presents_thresholds_as_official():
    prio = _frame([10, 20, 30, 40, 50, 60])
    ex = explain.explain_unit(prio, 0, "A")
    assert "not official" in explain.DISCLAIMER and "official guidance" in explain.DISCLAIMER
    for line in ex.reasons + ex.suggestions:
        assert "official" not in line.lower()


def test_few_units_gives_caution_and_nan_unit_raises():
    prio = _frame([10, 20])
    assert explain.explain_unit(prio, 0, "A").caution is not None
    nan_prio = _frame([10, 20, float("nan"), 40])
    with pytest.raises(ValueError):
        explain.explain_unit(nan_prio, 2, "C")


def test_trend_changes_helper(small_df):
    t = explain.trend_changes(small_df, C.STATE, "A", 2022)
    assert t[C.CE] == pytest.approx(10.0) and t["year"] == 2022   # A: 70 -> 80
    assert explain.trend_changes(small_df[small_df[C.YEAR] == 2021], C.STATE, "A") == {}


def test_real_data_uttar_pradesh_is_high_with_collection_suggestion():
    d = database.load_records()
    sy = priority.priority_by_state_year(d)
    idx = sy[(sy[C.STATE] == "Uttar Pradesh") & (sy[C.YEAR] == 2022)].index[0]
    ex = explain.explain_unit(sy, idx, "Uttar Pradesh 2022", thresholds=C.DEFAULT_THRESHOLDS,
                              trend=explain.trend_changes(d, C.STATE, "Uttar Pradesh", 2022))
    assert ex.level == "High" and ex.n_units == 30
    assert C.CE in ex.below_threshold and any("Collection:" in s for s in ex.suggestions)
