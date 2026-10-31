"""Run the pipeline: CSV -> validate/clean -> processed CSV + SQLite database.

Usage (from project root):  python scripts/build_database.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from waste_analytics import config as C  # noqa: E402
from waste_analytics import database, preprocessing  # noqa: E402


def main() -> None:
    raw = preprocessing.load_raw(C.RAW_CSV)
    clean, report = preprocessing.validate_and_clean(raw)
    C.CLEAN_CSV.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(C.CLEAN_CSV, index=False)
    database.build_database(clean, report)
    print(f"Raw rows: {report.rows_raw} | Clean rows: {report.rows_clean} | "
          f"Rejected: {len(report.rejected)}")
    print(report.to_frame().to_string(index=False))
    print("Coverage:", preprocessing.coverage_summary(clean))
    print(f"Database written to {C.DB_PATH}")


if __name__ == "__main__":
    main()
