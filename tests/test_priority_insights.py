import pandas as pd
import pytest

from waste_analytics import config as C
from waste_analytics import indicators as I
from waste_analytics import insights as INS
from waste_analytics import priority as P


def _agg(scores):
    return pd.DataFrame({C.STATE: list("ABCDEF")[:len(scores)],
                         C.CE: scores, C.TE: scores, C.RR: scores})


def test_composite_is_equal_weight_mean():
    df = pd.DataFrame({C.CE: [90.0], C.TE: [60.0], C.RR: [30.0]})
    assert P.composite_score(df).iloc[0] == pytest.approx(60.0)


def test_composite_nan_if_component_missing():
    df = pd.DataFrame({C.CE: [90.0], C.TE: [float("nan")], C.RR: [30.0]})
    assert pd.isna(P.composite_score(df).iloc[0])


def test_priority_terciles():
    out = P.classify_priority(_agg([10, 20, 30, 40, 50, 60])).set_index(C.STATE)
    assert list(out.loc[["A", "B"], "Priority"]) == ["High", "High"]
    assert list(out.loc[["C", "D"], "Priority"]) == ["Medium", "Medium"]
    assert list(out.loc[["E", "F"], "Priority"]) == ["Normal", "Normal"]
    assert set(out.attrs["cutoffs"]) == {"high", "medium"}


def test_priority_nan_is_unclassified():
    out = P.classify_priority(_agg([10, 20, float("nan"), 40]))
    assert out.loc[2, "Priority"] == "Unclassified"


def test_priority_all_nan_does_not_crash():
    out = P.classify_priority(_agg([float("nan")] * 3))
    assert len(out) == 3


def test_invalid_quantiles_rejected():
    with pytest.raises(ValueError):
        P.classify_priority(_agg([1, 2, 3]), C.PriorityConfig(0.7, 0.3))


def test_priority_by_state_year_covers_all_units(small_df):
    out = P.priority_by_state_year(small_df)
    assert len(out) == 4 and set(out["Priority"]) <= {"High", "Medium", "Normal"}
    assert out.iloc[0][C.SCORE] <= out.iloc[-1][C.SCORE]


def test_priority_by_category_is_separate(small_df):
    out = P.priority_by_category(small_df)
    assert set(out[C.WTYPE]) == {"Plastic", "Paper"}


def test_real_data_priority_flags_expected_weak_state():
    from waste_analytics import preprocessing as PP
    clean, _ = PP.validate_and_clean(PP.load_raw(C.RAW_CSV))
    out = P.priority_by_state_year(clean)
    high = out[out["Priority"] == "High"]
    assert "Uttar Pradesh" in set(high[C.STATE])
    assert len(out) == 30


def test_concern_rules_fire_below_threshold(small_df):
    t = C.InsightThresholds(low_collection=85, low_treatment=45, low_recycling=15)
    ins = INS.generate_insights(small_df, t)
    msgs = ins[ins["Scope"] == "State"]
    # 2022 State B: CE 40 < 85 -> R1; TE 50 > 45 -> no R2; RR 10 < 15 -> R3
    b = msgs[(msgs["Subject"] == "B") & msgs["Rule"].isin(["R1", "R2", "R3"])]
    assert set(b["Rule"]) == {"R1", "R3"}


def test_thresholds_are_configurable(small_df):
    strict = INS.generate_insights(small_df, C.InsightThresholds(100, 100, 100))
    lax = INS.generate_insights(small_df, C.InsightThresholds(0, 0, 0))
    assert (strict["Rule"].isin(["R1", "R2", "R3"])).sum() > 0
    assert (lax["Rule"].isin(["R1", "R2", "R3"])).sum() == 0


def test_improvement_and_deterioration(small_df):
    ins = INS.generate_insights(small_df, C.InsightThresholds(0, 0, 0, 1.0))
    a_ce = ins[(ins["Subject"] == "A") & (ins["Scope"] == "State") & ins["Insight"].str.contains("collection", case=False)]
    assert a_ce.iloc[0]["Kind"] == "Improvement"  # 70 -> 80
    b_ce = ins[(ins["Subject"] == "B") & (ins["Scope"] == "State") & ins["Insight"].str.contains("collection", case=False)]
    assert b_ce.iloc[0]["Kind"] == "Deterioration"  # 50 -> 40


def test_stable_change_raises_nothing():
    rows = [(2021, "A", "X", 100, 80, 40, 10), (2022, "A", "X", 100, 80.5, 40, 10)]
    df = pd.DataFrame(rows, columns=C.REQUIRED_COLS)
    ins = INS.generate_insights(df, C.InsightThresholds(0, 0, 0, 1.0))
    assert not ins["Rule"].isin(["R4", "R5"]).any()


def test_single_year_has_no_trend_rules():
    df = pd.DataFrame([(2021, "A", "X", 100, 80, 40, 10)], columns=C.REQUIRED_COLS)
    ins = INS.generate_insights(df)
    assert not ins["Rule"].isin(["R4", "R5"]).any()


def test_empty_input_returns_empty_table():
    empty = pd.DataFrame(columns=C.REQUIRED_COLS)
    assert INS.generate_insights(empty).empty
