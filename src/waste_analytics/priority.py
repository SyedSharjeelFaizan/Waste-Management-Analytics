"""Module 3: composite score and quantile-based priority classification.

Composite score = (CE + TE + RR) / 3   (equal weights, percentage points).
Computed on aggregates (ratio of sums); NaN if any component is NaN.

Priority (applied to a set of comparable units, e.g. the state-year aggregates):
  score <= Q(high_quantile)    -> High    (lowest-performing group)
  score <= Q(medium_quantile)  -> Medium
  otherwise                    -> Normal
These cut-offs are RELATIVE (they depend on the units being compared) and are
project-defined, not official standards.
"""
import pandas as pd

from . import config as C
from .indicators import aggregate


def composite_score(df: pd.DataFrame) -> pd.Series:
    """Equal-weight mean of the three indicators; NaN if any is missing."""
    return df[C.INDICATORS].mean(axis=1, skipna=False)


def classify_priority(agg: pd.DataFrame, cfg: C.PriorityConfig = C.DEFAULT_PRIORITY) -> pd.DataFrame:
    """Add Composite_Score, Priority and the cut-offs used to an aggregate frame."""
    if not 0 < cfg.high_quantile < cfg.medium_quantile < 1:
        raise ValueError("Require 0 < high_quantile < medium_quantile < 1")
    out = agg.copy()
    out[C.SCORE] = composite_score(out)
    scores = out[C.SCORE].dropna()
    if scores.empty:
        out["Priority"] = pd.Series(pd.NA, index=out.index, dtype="object")
        return out
    hi_cut = scores.quantile(cfg.high_quantile)
    med_cut = scores.quantile(cfg.medium_quantile)

    def label(s):
        if pd.isna(s):
            return "Unclassified"
        if s <= hi_cut:
            return "High"
        if s <= med_cut:
            return "Medium"
        return "Normal"

    out["Priority"] = out[C.SCORE].map(label)
    out.attrs["cutoffs"] = {"high": float(hi_cut), "medium": float(med_cut)}
    return out


def priority_by_state_year(df: pd.DataFrame, cfg: C.PriorityConfig = C.DEFAULT_PRIORITY) -> pd.DataFrame:
    """Priority for every State-Year aggregate (all categories combined)."""
    return classify_priority(aggregate(df, [C.STATE, C.YEAR]), cfg).sort_values(C.SCORE)


def priority_by_category(df: pd.DataFrame, cfg: C.PriorityConfig = C.DEFAULT_PRIORITY) -> pd.DataFrame:
    """Priority for each waste category (separate from state priority)."""
    return classify_priority(aggregate(df, [C.WTYPE]), cfg).sort_values(C.SCORE)
