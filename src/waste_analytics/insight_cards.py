"""Insight cards: a readable presentation of the rule-based insights.

No new rules live here. Every card is built from records produced by
`insights.generate_insight_records` (the existing IF-THEN rules R1-R5), so each number on a card is the
calculated value behind a fired rule. This module only:
  * groups findings about the same subject (state, category or overall) and kind into one card, so the
    same subject is not repeated once per indicator;
  * rates each card High / Medium / Positive with a simple, documented rule;
  * writes a headline, an explanation and a suggested action from the numbers;
  * orders cards so the most important findings come first.
The suggested actions reuse the rule-based text of `explain.SUGGESTION_RULES`. They are indicative only.
"""
from dataclasses import dataclass, field

from . import config as C
from .explain import SUGGESTION_RULES
from .insights import Insight

# Severity rule (presentation only): how far below its threshold an indicator is, or how far it fell.
SEVERE_SHORTFALL_PP = 10.0   # concern: at least this many points below the threshold -> High, otherwise Medium
SEVERE_DECLINE_PP = 5.0      # deterioration: a fall of at least this many points -> High, otherwise Medium
SEVERITY_ORDER = {"High": 0, "Medium": 1, "Positive": 2}
SEVERITY_NOTE = (f"High = at least {SEVERE_SHORTFALL_PP:g} pp below a threshold, or a decline of "
                 f"{SEVERE_DECLINE_PP:g} pp or more · Medium = below a threshold, or a smaller decline · "
                 "Positive = improvement")

NAME = {C.CE: "Collection efficiency", C.TE: "Treatment efficiency", C.RR: "Recycling rate"}
SHORT = {C.CE: "collection", C.TE: "treatment", C.RR: "recycling"}
SCOPE_LABEL = {"State": "State", "Category": "Waste category", "Overall": "Overall",
               "Selection": "State and waste type"}   # Selection: one state AND one waste type (insight_focus)
_CONCERN_PHRASE = {C.CE: "collection is falling behind", C.TE: "treatment is not keeping up",
                   C.RR: "recycling rate is low"}
_ACTIONS_IMPROVE = ("Keep the current approach and check whether it can be replicated in lower-performing "
                    "areas.")


@dataclass(frozen=True)
class CardMetric:
    indicator: str
    name: str
    value: float          # the calculated indicator value (%)
    context: str          # e.g. "Threshold 70% · 12.7 pp below" or "68.0% in 2021 · +2.8 pp"
    size: float           # magnitude used for rating and ordering (pp)


@dataclass
class InsightCard:
    headline: str
    summary: str
    kind: str                       # Concern | Deterioration | Improvement
    severity: str                   # High | Medium | Positive
    scope: str                      # State | Category | Overall
    subject: str
    year_label: str                 # "2022" or "2021 → 2022"
    metrics: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    rules: list = field(default_factory=list)
    size: float = 0.0


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _subject_label(rec: Insight) -> str:
    return "Overall" if rec.scope == "Overall" else rec.subject


def _concern_sentence(r: Insight) -> str:
    gap = r.threshold - r.value
    if r.indicator == C.CE:
        return (f"Only {r.value:.1f}% of generated waste was collected in {r.year}, {gap:.1f} points below the "
                f"{r.threshold:g}% threshold; about {100 - r.value:.0f}% was not collected.")
    if r.indicator == C.TE:
        return (f"Only {r.value:.1f}% of collected waste was treated in {r.year}, {gap:.1f} points below the "
                f"{r.threshold:g}% threshold; about {100 - r.value:.0f}% of it was not treated.")
    return (f"Only {r.value:.1f}% of treated waste was recycled in {r.year}, {gap:.1f} points below the "
            f"{r.threshold:g}% threshold.")


def _trend_sentence(r: Insight) -> str:
    verb = "rose" if r.kind == "Improvement" else "fell"
    return (f"{NAME[r.indicator]} {verb} from {r.prev_value:.1f}% in {r.prev_year} to {r.value:.1f}% in "
            f"{r.year} ({r.change_pp:+.1f} points).")


def _action_text(indicator: str) -> str:
    text = SUGGESTION_RULES[indicator].split(": ", 1)[-1]
    return text[0].upper() + text[1:]


def _build_card(kind: str, scope: str, subject: str, recs: list[Insight]) -> InsightCard:
    recs = sorted(recs, key=lambda r: C.INDICATORS.index(r.indicator))
    names = [SHORT[r.indicator] for r in recs]
    label = _subject_label(recs[0])
    if kind == "Concern":
        sizes = [r.threshold - r.value for r in recs]
        severity = "High" if max(sizes) >= SEVERE_SHORTFALL_PP else "Medium"
        phrase = _CONCERN_PHRASE[recs[0].indicator] if len(recs) == 1 else f"{_join(names)} are below threshold"
        metrics = [CardMetric(r.indicator, NAME[r.indicator], r.value,
                              f"Threshold {r.threshold:g}% · {s:.1f} pp below", s) for r, s in zip(recs, sizes)]
        summary = " ".join(_concern_sentence(r) for r in recs)
        actions = [_action_text(r.indicator) for r in recs]
        year_label = str(recs[0].year)
    else:
        sizes = [abs(r.change_pp) for r in recs]
        if kind == "Deterioration":
            severity = "High" if max(sizes) >= SEVERE_DECLINE_PP else "Medium"
            phrase = f"{names[0]} is slipping" if len(recs) == 1 else f"{_join(names)} are slipping"
            actions = [f"Investigate what changed in {SHORT[r.indicator]} since {r.prev_year} and whether the "
                       "decline is a one-off or a pattern." for r in recs]
        else:
            severity = "Positive"
            phrase = f"{names[0]} is improving" if len(recs) == 1 else f"{_join(names)} are improving"
            actions = [_ACTIONS_IMPROVE]
        metrics = [CardMetric(r.indicator, NAME[r.indicator], r.value,
                              f"{r.prev_value:.1f}% in {r.prev_year} · {r.change_pp:+.1f} pp", s)
                   for r, s in zip(recs, sizes)]
        summary = " ".join(_trend_sentence(r) for r in recs)
        year_label = f"{recs[0].prev_year} → {recs[0].year}"
    return InsightCard(headline=f"{label}: {phrase}", summary=summary, kind=kind, severity=severity, scope=scope,
                       subject=label, year_label=year_label, metrics=metrics, actions=actions,
                       rules=sorted({r.rule for r in recs}), size=max(sizes))


def build_cards(records: list[Insight]) -> list[InsightCard]:
    """One card per (kind, scope, subject), most important first (severity, then size, then name)."""
    groups: dict[tuple, list[Insight]] = {}
    for r in records:
        if r.indicator is None:
            continue
        groups.setdefault((r.kind, r.scope, r.subject), []).append(r)
    cards = [_build_card(kind, scope, subject, recs) for (kind, scope, subject), recs in groups.items()]
    return sorted(cards, key=lambda c: (SEVERITY_ORDER[c.severity], -c.size, c.subject))


def filter_records(records: list[Insight], kinds=None, indicators=None, scopes=None) -> list[Insight]:
    """Keep only the findings matching the chosen kinds, indicators and scopes (None = no restriction)."""
    return [r for r in records
            if (kinds is None or r.kind in kinds)
            and (indicators is None or r.indicator in indicators)
            and (scopes is None or r.scope in scopes)]


def severity_counts(cards: list[InsightCard]) -> dict:
    return {s: sum(c.severity == s for c in cards) for s in SEVERITY_ORDER}
