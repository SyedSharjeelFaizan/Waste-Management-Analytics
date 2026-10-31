"""Rule-based insights: transparent IF-THEN rules with configurable thresholds.

Rules (T = thresholds in config.InsightThresholds, all project-defined):
  R1  IF CE < T.low_collection  THEN collection-performance concern
  R2  IF TE < T.low_treatment   THEN treatment-performance concern
  R3  IF RR < T.low_recycling   THEN recycling-performance concern
  R4  IF indicator change vs previous year >  T.change_tolerance THEN improvement
  R5  IF indicator change vs previous year < -T.change_tolerance THEN deterioration
      (otherwise the indicator is reported as stable and no insight is raised)
R1-R3 are evaluated per state and per waste category (reported separately) for the
latest year in the data passed in; R4-R5 compare that year with the previous one.
"""
from dataclasses import dataclass

import pandas as pd

from . import config as C
from .indicators import aggregate

_NAMES = {C.CE: "Collection efficiency", C.TE: "Treatment efficiency", C.RR: "Recycling rate"}
_CONCERN_RULE = {C.CE: ("R1", "collection"), C.TE: ("R2", "treatment"), C.RR: ("R3", "recycling")}


@dataclass(frozen=True)
class Insight:
    rule: str
    kind: str      # Concern | Improvement | Deterioration
    scope: str     # State | Category | Overall
    subject: str
    message: str
    # The numbers behind the message (used to present the finding; they are not new calculations)
    indicator: str | None = None       # C.CE / C.TE / C.RR
    year: int | None = None            # year the value refers to
    value: float | None = None         # calculated indicator value (%)
    threshold: float | None = None     # concern rules: the project threshold that was crossed
    prev_year: int | None = None       # trend rules: the previous year compared
    prev_value: float | None = None
    change_pp: float | None = None


def _low_value_rules(agg: pd.DataFrame, scope: str, name_col: str, year: int,
                     t: C.InsightThresholds) -> list[Insight]:
    limits = {C.CE: t.low_collection, C.TE: t.low_treatment, C.RR: t.low_recycling}
    out = []
    for _, r in agg.iterrows():
        for ind, limit in limits.items():
            v = r[ind]
            if pd.notna(v) and v < limit:
                rule, topic = _CONCERN_RULE[ind]
                out.append(Insight(
                    rule, "Concern", scope, r[name_col],
                    f"{r[name_col]}: {topic}-performance concern in {year} - "
                    f"{_NAMES[ind].lower()} is {v:.1f}%, below the project threshold of {limit:g}%.",
                    indicator=ind, year=int(year), value=float(v), threshold=float(limit)))
    return out


def _trend_rules(df: pd.DataFrame, by: str, scope: str, years: list[int],
                 t: C.InsightThresholds) -> list[Insight]:
    prev, cur = years[-2], years[-1]
    agg = aggregate(df[df[C.YEAR].isin([prev, cur])], [by, C.YEAR])
    out = []
    for subject, g in agg.groupby(by):
        g = g.set_index(C.YEAR)
        if prev not in g.index or cur not in g.index:
            continue
        for ind in C.INDICATORS:
            a, b = g.loc[prev, ind], g.loc[cur, ind]
            if pd.isna(a) or pd.isna(b):
                continue
            d = b - a
            trend = dict(indicator=ind, year=int(cur), value=float(b), prev_year=int(prev),
                         prev_value=float(a), change_pp=float(d))
            if d > t.change_tolerance:
                out.append(Insight("R4", "Improvement", scope, subject,
                    f"{subject}: {_NAMES[ind].lower()} improved from {a:.1f}% in {prev} to {b:.1f}% in {cur} ({d:+.1f} pp).",
                    **trend))
            elif d < -t.change_tolerance:
                out.append(Insight("R5", "Deterioration", scope, subject,
                    f"{subject}: {_NAMES[ind].lower()} deteriorated from {a:.1f}% in {prev} to {b:.1f}% in {cur} ({d:+.1f} pp).",
                    **trend))
    return out


def generate_insights(df: pd.DataFrame, t: C.InsightThresholds = C.DEFAULT_THRESHOLDS) -> pd.DataFrame:
    """Apply all rules to `df` (already filtered by the user) and return a table of insights."""
    if df.empty:
        return pd.DataFrame(columns=["Rule", "Kind", "Scope", "Subject", "Insight"])
    items = generate_insight_records(df, t)
    out = pd.DataFrame([i.__dict__ for i in items],
                       columns=["rule", "kind", "scope", "subject", "message"])
    out.columns = ["Rule", "Kind", "Scope", "Subject", "Insight"]
    return out


def generate_insight_records(df: pd.DataFrame, t: C.InsightThresholds = C.DEFAULT_THRESHOLDS) -> list[Insight]:
    """Apply all rules to `df` and return the fired insights as records (with their numbers)."""
    if df.empty:
        return []
    years = sorted(df[C.YEAR].unique().tolist())
    latest = years[-1]
    last = df[df[C.YEAR] == latest]
    items: list[Insight] = []
    items += _low_value_rules(aggregate(last, C.STATE), "State", C.STATE, latest, t)
    items += _low_value_rules(aggregate(last, C.WTYPE), "Category", C.WTYPE, latest, t)
    if len(years) >= 2:
        for by, scope in ((C.STATE, "State"), (C.WTYPE, "Category")):
            items += _trend_rules(df, by, scope, years, t)
        overall = df.assign(Overall="All data")
        items += _trend_rules(overall, "Overall", "Overall", years, t)
    return items
