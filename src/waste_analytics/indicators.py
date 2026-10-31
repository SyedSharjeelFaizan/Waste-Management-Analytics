"""Module 2: performance indicators.

CE = Collected / Generated x 100
TE = Treated / Collected x 100
RR = Recycled / Treated x 100

Aggregate rates are always computed from SUMMED quantities (ratio of sums), never as
the average of row-level percentages. A zero (or missing) denominator gives NaN
("n/a") rather than 0% or an infinite value.

Note: quantities are in TPD (tonnes per day). Sums of TPD are summed daily rates,
NOT annual tonnage.
"""
from typing import Iterable

import numpy as np
import pandas as pd

from . import config as C


def safe_ratio(numerator, denominator):
    """Return numerator/denominator*100; NaN where the denominator is 0, negative or NaN."""
    num = pd.Series(numerator, dtype="float64") if not np.isscalar(numerator) else None
    if num is None:  # scalar path
        if denominator is None or pd.isna(denominator) or denominator <= 0 or pd.isna(numerator):
            return float("nan")
        return float(numerator) / float(denominator) * 100.0
    den = pd.Series(denominator, dtype="float64", index=num.index)
    valid = den.notna() & (den > 0)
    out = pd.Series(np.nan, index=num.index, dtype="float64")
    out[valid] = num[valid] / den[valid] * 100.0
    return out


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add CE, TE, RR columns to a frame that already holds the four quantity columns."""
    out = df.copy()
    out[C.CE] = safe_ratio(out[C.COL], out[C.GEN])
    out[C.TE] = safe_ratio(out[C.TRT], out[C.COL])
    out[C.RR] = safe_ratio(out[C.REC], out[C.TRT])
    return out


def aggregate(df: pd.DataFrame, by: str | Iterable[str] | None = None) -> pd.DataFrame:
    """Sum quantities by `by` (or overall if None) and compute indicators from the sums."""
    if by is None:
        grouped = df[C.QTY_COLS].sum().to_frame().T
    else:
        grouped = df.groupby(by, as_index=False)[C.QTY_COLS].sum()
    return add_indicators(grouped)


def overall_summary(df: pd.DataFrame) -> dict:
    """Overall totals (summed daily rates) and aggregate indicators."""
    row = aggregate(df).iloc[0]
    return {k: float(row[k]) for k in C.QTY_COLS + C.INDICATORS}


def year_over_year(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Per-`by` indicators by year, with change (percentage points) vs the previous year."""
    agg = aggregate(df, [by, C.YEAR]).sort_values([by, C.YEAR])
    for ind in C.INDICATORS:
        agg[f"{ind}_Change_pp"] = agg.groupby(by)[ind].diff()
    return agg


def rank_table(agg: pd.DataFrame, indicator: str, ascending: bool = False) -> pd.DataFrame:
    """Rank rows by an indicator (rank 1 = best when ascending=False)."""
    out = agg.copy()
    out["Rank"] = out[indicator].rank(ascending=ascending, method="min")
    return out.sort_values("Rank")
