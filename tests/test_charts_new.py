import numpy as np
import pandas as pd
import pytest

from waste_analytics import charts, compare, config as C
from waste_analytics import database, indicators, priority


@pytest.fixture(scope="module")
def data():
    return database.load_records()


def test_heatmap_absolute_uses_real_values_and_shared_scale(data):
    agg = indicators.aggregate(data, C.STATE)
    fig = charts.performance_heatmap(agg, C.STATE, "absolute")
    h = fig.data[0]
    assert list(h.y) == list(agg[C.STATE]) and len(h.x) == 3
    assert np.allclose(np.array(h.z, dtype=float), agg[C.INDICATORS].to_numpy())
    assert (h.zmin, h.zmax) == (0, 100)
    assert h.text[0][0] == f"{agg.iloc[0][C.CE]:.1f}%"


def test_heatmap_relative_scales_each_column_but_labels_real_values(data):
    agg = indicators.aggregate(data, C.STATE)
    fig = charts.performance_heatmap(agg, C.STATE, "relative")
    h = fig.data[0]
    z = np.array(h.z, dtype=float)
    assert np.allclose(z.min(axis=0), 0) and np.allclose(z.max(axis=0), 1)
    assert np.allclose(np.array(h.customdata, dtype=float), agg[C.INDICATORS].to_numpy())
    assert h.text[0][1] == f"{agg.iloc[0][C.TE]:.1f}%"


def test_heatmap_handles_nan_and_constant_columns():
    agg = pd.DataFrame({C.STATE: ["A", "B"], C.CE: [50.0, 50.0], C.TE: [float("nan"), 60.0], C.RR: [10.0, 20.0]})
    fig = charts.performance_heatmap(agg, C.STATE, "relative")
    assert np.allclose(np.array(fig.data[0].z, dtype=float)[:, 0], 0.5)
    assert fig.data[0].text[0][1] == "n/a"


def test_heatmap_works_for_categories(data):
    agg = indicators.aggregate(data, C.WTYPE)
    assert len(charts.performance_heatmap(agg, C.WTYPE).data[0].y) == 10


def test_head_to_head_bars_carry_both_states(data):
    cmp = compare.compare_states(data, "Kerala", "Odisha")
    fig = charts.head_to_head_bars(cmp.table, "Kerala", "Odisha")
    assert [t.name for t in fig.data] == ["Kerala", "Odisha"]
    t = cmp.table[cmp.table["Indicator"].isin(C.INDICATORS)]
    assert np.allclose(fig.data[0].y, t["Value_A"]) and np.allclose(fig.data[1].y, t["Value_B"])


def test_head_to_head_trend_has_a_point_per_year(data):
    fig = charts.head_to_head_trend(data, "Kerala", "Odisha", C.CE)
    assert [t.name for t in fig.data] == ["Kerala", "Odisha"]
    assert list(fig.data[0].x) == [2020, 2021, 2022]
    exp = indicators.aggregate(data[data[C.STATE] == "Kerala"], C.YEAR).sort_values(C.YEAR)[C.CE]
    assert np.allclose(fig.data[0].y, exp)


def test_priority_position_highlights_selected_unit(data):
    sy = priority.priority_by_state_year(data)
    labels = [f"{r[C.STATE]} {int(r[C.YEAR])}" for _, r in sy.iterrows()]
    fig = charts.priority_position(labels, sy[C.SCORE], labels[0], sy.attrs["cutoffs"])
    bar = fig.data[0]
    opac = dict(zip(bar.y, bar.marker.opacity))
    assert opac[labels[0]] == 1.0 and sum(o == 1.0 for o in bar.marker.opacity) == 1
    assert len(fig.layout.shapes) == 2             # the two cut-off lines
    assert len(bar.y) == 30


def test_indicator_vs_peers_values():
    fig = charts.indicator_vs_peers({C.CE: 50, C.TE: 60, C.RR: 40}, {C.CE: 70, C.TE: 65, C.RR: 41}, "X")
    assert list(fig.data[0].y) == [50, 60, 40] and list(fig.data[1].y) == [70, 65, 41]
