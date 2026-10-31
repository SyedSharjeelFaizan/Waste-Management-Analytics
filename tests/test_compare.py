import math

import pandas as pd
import pytest

from waste_analytics import compare, config as C
from waste_analytics import indicators as I


def test_head_to_head_values_match_hand_calculation(small_df):
    cmp = compare.compare_states(small_df, "A", "B")
    t = cmp.table.set_index("Indicator")
    # A: generated 400, collected 300, treated 170, recycled 75 ; B: 400 / 180 / 90 / 9
    assert t.loc[C.CE, "Value_A"] == pytest.approx(300 / 400 * 100)
    assert t.loc[C.CE, "Value_B"] == pytest.approx(180 / 400 * 100)
    assert t.loc[C.TE, "Value_A"] == pytest.approx(170 / 300 * 100)
    assert t.loc[C.RR, "Value_B"] == pytest.approx(9 / 90 * 100)
    assert t.loc[C.CE, "Difference_pp"] == pytest.approx(30.0)


def test_better_state_per_indicator_and_wins(small_df):
    cmp = compare.compare_states(small_df, "A", "B")
    assert list(cmp.table["Better"]) == ["A", "A", "A", "A"]
    assert cmp.wins == {"A": 3, "B": 0, "Tie": 0}
    assert cmp.leader == "A"
    swapped = compare.compare_states(small_df, "B", "A")
    assert swapped.wins == {"B": 0, "A": 3, "Tie": 0} and swapped.leader == "A"


def test_composite_matches_priority_module(small_df):
    from waste_analytics import priority
    cmp = compare.compare_states(small_df, "A", "B")
    agg = I.aggregate(small_df, C.STATE).set_index(C.STATE)
    expected = priority.composite_score(agg)
    comp = cmp.table.set_index("Indicator").loc[C.SCORE]
    assert comp["Value_A"] == pytest.approx(expected["A"])
    assert comp["Value_B"] == pytest.approx(expected["B"])


def test_tie_when_difference_below_display_precision():
    rows = [(2021, "A", "X", 100, 80, 40, 10), (2021, "B", "X", 100, 80.01, 40, 10)]
    df = pd.DataFrame(rows, columns=C.REQUIRED_COLS)
    cmp = compare.compare_states(df, "A", "B")
    t = cmp.table.set_index("Indicator")
    assert t.loc[C.CE, "Better"] == "Tie" and t.loc[C.CE, "Lead_pp"] == 0
    assert cmp.wins["Tie"] == 3


def test_nan_values_are_not_comparable():
    rows = [(2021, "A", "X", 100, 80, 40, 10), (2021, "B", "X", 0, 0, 0, 0)]
    df = pd.DataFrame(rows, columns=C.REQUIRED_COLS)
    cmp = compare.compare_states(df, "A", "B")
    assert (cmp.table["Better"] == "n/a").all()
    assert cmp.leader == "n/a" and cmp.wins == {"A": 0, "B": 0, "Tie": 0}
    assert math.isnan(cmp.table.iloc[0]["Value_B"])


def test_same_state_rejected(small_df):
    with pytest.raises(ValueError, match="different"):
        compare.compare_states(small_df, "A", "A")


def test_unknown_state_rejected(small_df):
    with pytest.raises(ValueError, match="No records"):
        compare.compare_states(small_df, "A", "Z")


def test_quantities_and_export_table(small_df):
    cmp = compare.compare_states(small_df, "A", "B")
    assert cmp.quantities.loc[C.GEN, "A"] == 400 and cmp.quantities.loc[C.COL, "B"] == 180
    exp = compare.comparison_export(cmp)
    assert list(exp.columns)[:3] == ["Indicator", "A", "B"] and len(exp) == 4
    assert exp.iloc[0]["Indicator"] == "Collection Efficiency"


def test_real_data_kerala_vs_uttar_pradesh():
    from waste_analytics import database
    cmp = compare.compare_states(database.load_records(), "Kerala", "Uttar Pradesh")
    t = cmp.table.set_index("Indicator")
    assert round(t.loc[C.CE, "Value_A"], 1) == 90.3 and round(t.loc[C.CE, "Value_B"], 1) == 56.1
    assert cmp.wins["Kerala"] == 3 and cmp.leader == "Kerala"
