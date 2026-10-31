import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from waste_analytics import config as C  # noqa: E402


@pytest.fixture
def small_df():
    """Tiny hand-checkable dataset: 2 states x 2 years x 1 category."""
    rows = [
        (2021, "A", "Plastic", 100, 80, 40, 10),
        (2021, "A", "Paper", 100, 60, 30, 15),
        (2021, "B", "Plastic", 200, 100, 50, 5),
        (2022, "A", "Plastic", 100, 90, 60, 30),
        (2022, "A", "Paper", 100, 70, 40, 20),
        (2022, "B", "Plastic", 200, 80, 40, 4),
    ]
    return pd.DataFrame(rows, columns=C.REQUIRED_COLS)
