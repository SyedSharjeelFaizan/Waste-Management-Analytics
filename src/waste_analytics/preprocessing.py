"""Module 1: load, validate and clean the waste dataset (original file is never modified)."""
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config as C


@dataclass
class QualityReport:
    """Result of validation: counts per check plus the rejected rows with reasons."""

    rows_raw: int = 0
    rows_clean: int = 0
    checks: list = field(default_factory=list)  # (check_name, issue_count, note)
    rejected: pd.DataFrame = field(default_factory=pd.DataFrame)

    def add(self, name: str, count: int, note: str = "") -> None:
        self.checks.append((name, int(count), note))

    def to_frame(self) -> pd.DataFrame:
        df = pd.DataFrame(self.checks, columns=["Check", "Issues_Found", "Note"])
        df["Status"] = df["Issues_Found"].map(lambda n: "PASS" if n == 0 else "ISSUES")
        return df


def load_raw(path: Path = C.RAW_CSV) -> pd.DataFrame:
    """Read the CSV as-is (read-only). Raises if required columns are absent."""
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in C.REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df[C.REQUIRED_COLS].copy()


def validate_and_clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, QualityReport]:
    """Validate `raw`; return (clean_df, report). `raw` is not mutated.

    A record is rejected (with a reason) if it has missing/non-numeric values, a
    negative quantity, an out-of-range year, a violated waste hierarchy
    (collected > generated, treated > collected, recycled > treated) or is a
    duplicate Year+State+Waste_Type key (first occurrence kept).
    Zero quantities are valid; zero denominators are handled in indicators.py.
    """
    rep = QualityReport(rows_raw=len(raw))
    df = raw.copy()

    # Normalise text (strip whitespace) and coerce numerics
    for c in (C.STATE, C.WTYPE):
        df[c] = df[c].astype("string").str.strip()
    df[C.YEAR] = pd.to_numeric(df[C.YEAR], errors="coerce")
    for c in C.QTY_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    reasons = pd.Series("", index=df.index, dtype="object")

    def flag(mask: pd.Series, reason: str, name: str, note: str = "") -> None:
        mask = mask.fillna(False)
        rep.add(name, mask.sum(), note)
        reasons.loc[mask] = reasons.loc[mask] + reason + "; "

    rep.add("Required columns present", 0, f"{len(C.REQUIRED_COLS)} columns")
    flag(df[C.REQUIRED_COLS].isna().any(axis=1), "missing/non-numeric value", "Missing or non-numeric values")
    flag(
        (df[C.YEAR] < C.VALID_YEAR_RANGE[0]) | (df[C.YEAR] > C.VALID_YEAR_RANGE[1]),
        "year out of range", "Year out of plausible range",
    )
    flag((df[C.QTY_COLS] < 0).any(axis=1), "negative quantity", "Negative quantities")
    flag(df[C.COL] > df[C.GEN], "collected > generated", "Collected exceeds generated")
    flag(df[C.TRT] > df[C.COL], "treated > collected", "Treated exceeds collected")
    flag(df[C.REC] > df[C.TRT], "recycled > treated", "Recycled exceeds treated")
    flag(df.duplicated(), "exact duplicate row", "Exact duplicate rows")
    # Duplicate keys that are not already flagged as exact duplicates
    flag(df.duplicated(C.KEY_COLS) & ~df.duplicated(), "duplicate key", "Duplicate Year+State+Waste_Type keys")
    rep.add("Zero-valued quantities (valid, rates guarded)", int((df[C.QTY_COLS] == 0).any(axis=1).sum()),
            "informational; zero denominators yield n/a")

    bad = reasons != ""
    rep.rejected = df.loc[bad].assign(Rejection_Reason=reasons[bad].str.rstrip("; "))
    clean = df.loc[~bad].copy()
    clean[C.YEAR] = clean[C.YEAR].astype(int)
    clean[C.STATE] = clean[C.STATE].astype(str)
    clean[C.WTYPE] = clean[C.WTYPE].astype(str)
    clean = clean.sort_values(C.KEY_COLS).reset_index(drop=True)
    rep.rows_clean = len(clean)
    return clean, rep


def coverage_summary(clean: pd.DataFrame) -> dict:
    """Coverage of years, states and categories, and whether the grid is complete."""
    n_y, n_s, n_t = (clean[c].nunique() for c in (C.YEAR, C.STATE, C.WTYPE))
    return {
        "years": sorted(clean[C.YEAR].unique().tolist()),
        "states": n_s,
        "waste_types": n_t,
        "complete_grid": len(clean) == n_y * n_s * n_t,
    }
