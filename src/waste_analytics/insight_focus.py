"""Focused analysis for the Insights page.

The page-level selectors (state, waste type, year, indicator) only ever NARROW the data that the sidebar filters have
already selected. The existing rules R1-R5 (`insights.generate_insight_records`) then run, unchanged, on that narrowed
frame, so every finding is calculated from the filtered dataset. This module adds no rule, threshold or performance
value. It only:
  * narrows the frame (a chosen year means "as of that year": that year is the one checked against the thresholds and
    it is compared with the previous selected year, exactly as the rules treat the latest year of any frame);
  * removes findings that would repeat each other: for one state and/or waste type the rules report the same numbers
    as a State, a Category and an Overall finding, so only one of them is kept, labelled with its context;
  * collects the indicator values (and their history across the years) for the compact performance summary.
"""
from dataclasses import dataclass, replace

import pandas as pd

from . import config as C
from .indicators import aggregate
from .insights import Insight, generate_insight_records

ALL_STATES, ALL_TYPES, ALL_YEARS, ALL_INDICATORS = "All states", "All types", "All years", "All indicators"
SELECTION = "Selection"          # scope of findings about one state AND one waste type
INDICATOR_NAME = {C.CE: "Collection efficiency", C.TE: "Treatment efficiency", C.RR: "Recycling rate"}


@dataclass(frozen=True)
class Focus:
    """What the page-level selectors ask for (None = no restriction)."""
    state: str | None = None
    wtype: str | None = None
    year: int | None = None
    indicator: str | None = None        # C.CE / C.TE / C.RR

    @property
    def is_combination(self) -> bool:
        return bool(self.state and self.wtype)

    @property
    def label(self) -> str:
        return f"{self.state or ALL_STATES} · {self.wtype or ALL_TYPES}"

    @property
    def indicators(self) -> list[str]:
        return [self.indicator] if self.indicator else list(C.INDICATORS)


def focus_frame(df: pd.DataFrame, focus: Focus) -> pd.DataFrame:
    """Narrow the (already sidebar-filtered) records to the chosen state, waste type and year."""
    out = df
    if focus.state:
        out = out[out[C.STATE] == focus.state]
    if focus.wtype:
        out = out[out[C.WTYPE] == focus.wtype]
    if focus.year is not None:
        out = out[out[C.YEAR] <= focus.year]
    return out


def _with_subject(rec: Insight, subject: str, scope: str | None = None) -> Insight:
    message = subject + rec.message[len(rec.subject):] if rec.message.startswith(rec.subject) else rec.message
    return replace(rec, subject=subject, message=message, scope=scope or rec.scope)


def tidy_records(records: list[Insight], focus: Focus) -> list[Insight]:
    """Drop repeated findings and name the context of the remaining ones (no rule or number is changed)."""
    if focus.is_combination:
        # one state and one waste type is a single subject: State, Category and Overall describe the same numbers
        label = f"{focus.state} · {focus.wtype}"
        return [_with_subject(r, label, SELECTION) for r in records if r.scope == "State"]
    if focus.state:
        # Overall repeats the state; the categories are those of this state
        return [_with_subject(r, f"{r.subject} ({focus.state})") if r.scope == "Category" else r
                for r in records if r.scope != "Overall"]
    if focus.wtype:
        # Overall repeats the waste category; the states are those for this waste type
        return [_with_subject(r, f"{r.subject} ({focus.wtype})") if r.scope == "State" else r
                for r in records if r.scope != "Overall"]
    return list(records)


def run_focus(df: pd.DataFrame, focus: Focus, thresholds: C.InsightThresholds = C.DEFAULT_THRESHOLDS
              ) -> tuple[pd.DataFrame, list[Insight]]:
    """The focused frame and the existing rules' findings for it (empty frame -> no findings)."""
    frame = focus_frame(df, focus)
    return frame, tidy_records(generate_insight_records(frame, thresholds), focus)


@dataclass(frozen=True)
class SummaryRow:
    indicator: str
    name: str
    value: float                    # calculated indicator value (%) in `year`
    year: int
    threshold: float                # the rule threshold the value is compared with
    shortfall: float                # points below the threshold (0 when it is met)
    history: tuple                  # ((year, value), ...) for every year in the frame


def performance_summary(frame: pd.DataFrame, focus: Focus,
                        thresholds: C.InsightThresholds = C.DEFAULT_THRESHOLDS) -> list[SummaryRow]:
    """Indicator values of the focused frame for its latest year, with the value in every earlier year."""
    if frame.empty:
        return []
    by_year = aggregate(frame, C.YEAR).set_index(C.YEAR).sort_index()
    limits = {C.CE: thresholds.low_collection, C.TE: thresholds.low_treatment, C.RR: thresholds.low_recycling}
    latest = int(by_year.index[-1])
    rows = []
    for ind in focus.indicators:
        value = by_year.loc[latest, ind]
        if pd.isna(value):
            continue
        history = tuple((int(y), float(v)) for y, v in by_year[ind].dropna().items())
        rows.append(SummaryRow(ind, INDICATOR_NAME[ind], float(value), latest, float(limits[ind]),
                               max(float(limits[ind] - value), 0.0), history))
    return rows
