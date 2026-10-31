"""Explainable priority analysis: why a unit is High / Medium / Normal, plus rule-based suggestions.

Nothing here changes the classification. It reads the output of `priority.classify_priority`
(the existing quantile method) and explains it in words. All thresholds used for suggestions
come from `config.InsightThresholds` and are PROJECT-DEFINED, not official standards.
"""
from dataclasses import dataclass, field

import pandas as pd

from . import config as C
from .indicators import year_over_year

SHORT = {C.CE: "collection efficiency", C.TE: "treatment efficiency", C.RR: "recycling rate"}

# IF indicator is below its project threshold THEN suggest (indicative, rule-based text)
SUGGESTION_RULES = {
    C.CE: ("Collection: review collection coverage and frequency, route planning and any "
           "uncollected areas, and compare practices with higher-ranked peers."),
    C.TE: ("Treatment: check whether collected waste reaches treatment facilities, and review "
           "processing capacity, downtime and facility utilisation."),
    C.RR: ("Recycling: strengthen source segregation and material-recovery capacity, and "
           "review how much treated waste is diverted to recycling."),
}
DISCLAIMER = ("Suggestions are produced by simple project-defined rules from the indicators; they are "
              "indicative only and are not official guidance or standards.")


@dataclass
class PriorityExplanation:
    unit: str
    level: str
    composite: float
    components: dict
    rank: int                     # 1 = lowest composite score among compared units
    n_units: int
    high_cut: float
    medium_cut: float
    peer_median: dict
    gap_vs_median: dict           # unit value minus peer median, in percentage points
    main_driver: str | None       # indicator with the largest shortfall vs peer median (if any)
    below_threshold: list = field(default_factory=list)
    reasons: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    caution: str | None = None


def trend_changes(df: pd.DataFrame, by: str, name: str, year: int | None = None) -> dict:
    """Change in each indicator (pp) versus the previous year for one unit; {} if unavailable."""
    sub = df[df[by] == name]
    if sub[C.YEAR].nunique() < 2:
        return {}
    yoy = year_over_year(sub, by).set_index(C.YEAR)
    year = year if year is not None else int(yoy.index.max())
    if year not in yoy.index:
        return {}
    row = yoy.loc[year]
    out = {k: row[f"{k}_Change_pp"] for k in C.INDICATORS if pd.notna(row[f"{k}_Change_pp"])}
    if out:
        out["year"] = year
    return out


def explain_unit(prio: pd.DataFrame, row_label, unit: str,
                 cfg: C.PriorityConfig = C.DEFAULT_PRIORITY,
                 thresholds: C.InsightThresholds = C.DEFAULT_THRESHOLDS,
                 trend: dict | None = None) -> PriorityExplanation:
    """Explain the priority of one row of a classified frame (`row_label` is its index label)."""
    row = prio.loc[row_label]
    cuts = prio.attrs.get("cutoffs")
    if not cuts or pd.isna(row[C.SCORE]):
        raise ValueError("This unit has no composite score, so it cannot be classified")
    hi, med = cuts["high"], cuts["medium"]
    score = float(row[C.SCORE])
    scores = prio[C.SCORE].dropna()
    n = len(scores)
    rank = int((scores < score).sum()) + 1
    comps = {k: float(row[k]) for k in C.INDICATORS}
    medians = {k: float(prio[k].median()) for k in C.INDICATORS}
    gaps = {k: comps[k] - medians[k] for k in C.INDICATORS}
    worst = min(gaps, key=gaps.get)
    driver = worst if gaps[worst] < 0 else None
    limits = {C.CE: thresholds.low_collection, C.TE: thresholds.low_treatment, C.RR: thresholds.low_recycling}
    below = [k for k in C.INDICATORS if comps[k] < limits[k]]
    level = str(row["Priority"])

    reasons = [
        f"Composite score {score:.1f} is the equal-weight mean of collection efficiency {comps[C.CE]:.1f}%, "
        f"treatment efficiency {comps[C.TE]:.1f}% and recycling rate {comps[C.RR]:.1f}%.",
        f"Among the {n} compared units it ranks {rank} from the lowest score (1 = lowest).",
    ]
    if level == "High":
        reasons.append(
            f"{score:.1f} is at or below the High cut-off of {hi:.1f} (the {cfg.high_quantile:.0%} quantile of "
            f"the composite scores), so the unit is classified High priority.")
        reasons.append(f"It would need a composite score above {hi:.1f} (+{hi - score:.1f}) to leave High.")
    elif level == "Medium":
        reasons.append(
            f"{score:.1f} is above the High cut-off ({hi:.1f}) and at or below the Medium cut-off of {med:.1f} "
            f"(the {cfg.medium_quantile:.0%} quantile), so the unit is classified Medium priority.")
        reasons.append(f"It is {score - hi:.1f} above the High cut-off and {med - score:.1f} below the "
                       f"point where Normal begins ({med:.1f}).")
    else:
        reasons.append(
            f"{score:.1f} is above the Medium cut-off of {med:.1f} (the {cfg.medium_quantile:.0%} quantile), "
            f"so the unit is classified Normal priority ({score - med:.1f} above the cut-off).")
    if driver:
        reasons.append(f"Largest shortfall against the compared units' median: {SHORT[driver]} "
                       f"({gaps[driver]:+.1f} pp vs median {medians[driver]:.1f}%).")
    if below:
        reasons.append("Below the project threshold: " + ", ".join(
            f"{SHORT[k]} {comps[k]:.1f}% < {limits[k]:g}%" for k in below) + ".")

    sugg = [SUGGESTION_RULES[k] for k in below]
    declines = []
    if trend:
        declines = [k for k in C.INDICATORS if k in trend and trend[k] < -thresholds.change_tolerance]
        for k in declines:
            sugg.append(f"Trend: investigate the decline in {SHORT[k]} ({trend[k]:+.1f} pp vs the previous year).")
    if level in ("High", "Medium") and driver and driver not in below:
        sugg.append(f"Relative gap: {SHORT[driver]} is the weakest indicator compared with peers "
                    f"({gaps[driver]:+.1f} pp vs median); prioritise it first.")
    if not sugg:
        sugg.append("No indicator is below its project threshold and none declined beyond the tolerance: "
                    "maintain current practice and keep monitoring.")

    caution = None
    if n < 3:
        caution = ("Fewer than 3 units are being compared, so quantile-based priority levels are not "
                   "meaningful. Widen the filters.")
    return PriorityExplanation(unit, level, score, comps, rank, n, hi, med, medians, gaps, driver,
                               below, reasons, sugg, caution)
