"""Central configuration: paths, column names and all project-defined thresholds.

IMPORTANT: every threshold below is a PROJECT-DEFINED analytical parameter chosen for
this academic project. None of them is an official government or regulatory standard.
"""
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "Waste_Management_Analytics_300_Records.csv"
CLEAN_CSV = PROJECT_ROOT / "data" / "processed" / "waste_clean.csv"
DB_PATH = PROJECT_ROOT / "data" / "waste.db"

# Source column names
YEAR, STATE, WTYPE = "Year", "State", "Waste_Type"
GEN, COL, TRT, REC = (
    "Waste_Generated_TPD",
    "Waste_Collected_TPD",
    "Waste_Treated_TPD",
    "Waste_Recycled_TPD",
)
KEY_COLS = [YEAR, STATE, WTYPE]
QTY_COLS = [GEN, COL, TRT, REC]
REQUIRED_COLS = KEY_COLS + QTY_COLS

# Derived indicator names
CE, TE, RR = "Collection_Efficiency", "Treatment_Efficiency", "Recycling_Rate"
INDICATORS = [CE, TE, RR]
SCORE = "Composite_Score"

# Plausible year range used by validation (project-defined sanity check)
VALID_YEAR_RANGE = (2000, 2100)


@dataclass(frozen=True)
class InsightThresholds:
    """Thresholds for IF-THEN insight rules (percent / percentage points)."""

    low_collection: float = 70.0   # CE below this -> collection concern
    low_treatment: float = 60.0    # TE below this -> treatment concern
    low_recycling: float = 30.0    # RR below this -> recycling concern
    change_tolerance: float = 1.0  # |change| <= this many pp is reported as "stable"


@dataclass(frozen=True)
class PriorityConfig:
    """Quantile cut-offs applied to the composite score (mean of CE, TE, RR).

    Units whose score is at or below the `high_quantile` quantile of the compared
    units are 'High' priority, those at or below `medium_quantile` are 'Medium',
    the rest are 'Normal'. Defaults split the units into terciles.
    """

    high_quantile: float = 1 / 3
    medium_quantile: float = 2 / 3


DEFAULT_THRESHOLDS = InsightThresholds()
DEFAULT_PRIORITY = PriorityConfig()
