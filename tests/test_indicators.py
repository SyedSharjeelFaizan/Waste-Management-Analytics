import math

import pandas as pd
import pytest

from waste_analytics import config as C
from waste_analytics import indicators as I


def test_safe_ratio_scalar():
    assert I.safe_ratio(50, 200) == 25.0
    assert math.isnan(I.safe_ratio(5, 0))
    assert math.isnan(I.safe_ratio(5, -1))
    assert math.isnan(I.safe_ratio(5, float("nan")))
    assert I.safe_ratio(0, 10) == 0.0


def test_safe_ratio_series_zero_denominator():
    r = I.safe_ratio(pd.Series([1.0, 2.0, 3.0]), pd.Series([2.0, 0.0, float("nan")]))
    assert r.iloc[0] == 50.0 and r.iloc[1:].isna().all()
    assert not (r == float("inf")).any()


def test_row_indicators(small_df):
    d = I.add_indicators(small_df)
    first = d.iloc[0]
    assert first[C.CE] == 80.0 and first[C.TE] == 50.0 and first[C.RR] == 25.0


def test_zero_rows_give_nan_not_error():
    df = pd.DataFrame([(2021, "A", "X", 0, 0, 0, 0)], columns=C.REQUIRED_COLS)
    d = I.add_indicators(df)
    assert d[C.INDICATORS].isna().all(axis=None)


def test_aggregate_is_ratio_of_sums_not_mean_of_ratios(small_df):
    y21 = small_df[small_df[C.YEAR] == 2021]
    agg = I.aggregate(y21, C.STATE).set_index(C.STATE)
    # State A 2021: collected 140 / generated 200 = 70%; mean of row CEs would be 70 too,
    # so use state-level over both years for a distinguishing case below.
    assert agg.loc["A", C.CE] == pytest.approx(70.0)
    allyears = I.aggregate(small_df, C.STATE).set_index(C.STATE)
    # State B: (100+80)/(200+200)=45%
    assert allyears.loc["B", C.CE] == pytest.approx(45.0)
    # Unequal sizes: ratio-of-sums differs from mean-of-ratios
    skew = pd.DataFrame([(2021, "A", "X", 10, 10, 5, 1), (2021, "A", "Y", 1000, 500, 250, 50)],
                        columns=C.REQUIRED_COLS)
    ce = I.aggregate(skew)[C.CE].iloc[0]
    assert ce == pytest.approx(510 / 1010 * 100)
    assert ce != pytest.approx((100 + 50) / 2)


def test_overall_summary_values(small_df):
    s = I.overall_summary(small_df)
    assert s[C.GEN] == 800 and s[C.COL] == 480
    assert s[C.CE] == pytest.approx(60.0)


def test_year_over_year_change(small_df):
    yoy = I.year_over_year(small_df, C.STATE).set_index([C.STATE, C.YEAR])
    assert math.isnan(yoy.loc[("A", 2021), f"{C.CE}_Change_pp"])
    # A: 2021 CE 70 -> 2022 CE 80
    assert yoy.loc[("A", 2022), f"{C.CE}_Change_pp"] == pytest.approx(10.0)


def test_rank_table_best_is_rank_one(small_df):
    agg = I.aggregate(small_df, C.STATE)
    ranked = I.rank_table(agg, C.CE)
    assert ranked.iloc[0][C.STATE] == "A"
