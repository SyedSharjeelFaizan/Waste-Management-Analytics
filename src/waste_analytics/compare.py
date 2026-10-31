"""Head-to-head comparison of two states (uses the existing indicator and priority logic).

Aggregate rates come from `indicators.aggregate` (ratio of summed quantities); the composite
score is the equal-weight mean of the three indicators, exactly as in `priority.py`.
"""
from dataclasses import dataclass

import pandas as pd

from . import config as C
from .indicators import aggregate
from .priority import composite_score

TIE_TOLERANCE_PP = 0.05  # differences below the displayed precision (0.1) are reported as a tie

ROWS = C.INDICATORS + [C.SCORE]


@dataclass
class Comparison:
    state_a: str
    state_b: str
    table: pd.DataFrame            # one row per indicator (+ composite)
    wins: dict                     # {state_a: n, state_b: n, "Tie": n} over the three indicators
    leader: str                    # state with the higher composite score, or "Tie" / "n/a"
    quantities: pd.DataFrame       # summed TPD quantities for both states


def _profile(df: pd.DataFrame, state: str) -> pd.Series:
    sub = df[df[C.STATE] == state]
    if sub.empty:
        raise ValueError(f"No records for state '{state}' in the current selection")
    row = aggregate(sub).iloc[0]
    row[C.SCORE] = composite_score(pd.DataFrame([row[C.INDICATORS]])).iloc[0]
    return row


def _better(a_name: str, b_name: str, a: float, b: float) -> tuple[str, float]:
    if pd.isna(a) or pd.isna(b):
        return "n/a", float("nan")
    diff = a - b
    if abs(diff) < TIE_TOLERANCE_PP:
        return "Tie", 0.0
    return (a_name if diff > 0 else b_name), abs(diff)


def compare_states(df: pd.DataFrame, state_a: str, state_b: str) -> Comparison:
    """Compare two different states on CE, TE, RR and the composite score (higher is better)."""
    if state_a == state_b:
        raise ValueError("Choose two different states to compare")
    pa, pb = _profile(df, state_a), _profile(df, state_b)
    rows = []
    for key in ROWS:
        better, lead = _better(state_a, state_b, pa[key], pb[key])
        rows.append({"Indicator": key, "Value_A": pa[key], "Value_B": pb[key],
                     "Difference_pp": pa[key] - pb[key], "Better": better, "Lead_pp": lead})
    table = pd.DataFrame(rows)
    ind_rows = table[table["Indicator"].isin(C.INDICATORS)]
    wins = {state_a: int((ind_rows["Better"] == state_a).sum()),
            state_b: int((ind_rows["Better"] == state_b).sum()),
            "Tie": int((ind_rows["Better"] == "Tie").sum())}
    leader = table.loc[table["Indicator"] == C.SCORE, "Better"].iloc[0]
    qty = pd.DataFrame({state_a: pa[C.QTY_COLS], state_b: pb[C.QTY_COLS]})
    return Comparison(state_a, state_b, table, wins, leader, qty)


def comparison_export(cmp: Comparison) -> pd.DataFrame:
    """Flat table with state names as column headers, for CSV / PDF export."""
    t = cmp.table
    return pd.DataFrame({
        "Indicator": t["Indicator"].str.replace("_", " "),
        cmp.state_a: t["Value_A"], cmp.state_b: t["Value_B"],
        f"Difference ({cmp.state_a} - {cmp.state_b}, pp)": t["Difference_pp"],
        "Better": t["Better"]})
