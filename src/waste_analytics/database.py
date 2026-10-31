"""SQLite storage for the cleaned dataset and the data-quality log."""
import sqlite3
from pathlib import Path

import pandas as pd

from . import config as C
from .preprocessing import QualityReport

SCHEMA = """
DROP TABLE IF EXISTS waste_records;
DROP TABLE IF EXISTS data_quality_log;
DROP TABLE IF EXISTS rejected_records;
CREATE TABLE waste_records (
    Year INTEGER NOT NULL,
    State TEXT NOT NULL,
    Waste_Type TEXT NOT NULL,
    Waste_Generated_TPD REAL NOT NULL CHECK (Waste_Generated_TPD >= 0),
    Waste_Collected_TPD REAL NOT NULL CHECK (Waste_Collected_TPD >= 0),
    Waste_Treated_TPD   REAL NOT NULL CHECK (Waste_Treated_TPD >= 0),
    Waste_Recycled_TPD  REAL NOT NULL CHECK (Waste_Recycled_TPD >= 0),
    PRIMARY KEY (Year, State, Waste_Type)
);
CREATE TABLE data_quality_log (
    Check_Name TEXT, Issues_Found INTEGER, Note TEXT, Status TEXT
);
CREATE TABLE rejected_records (
    Year, State, Waste_Type, Waste_Generated_TPD, Waste_Collected_TPD,
    Waste_Treated_TPD, Waste_Recycled_TPD, Rejection_Reason TEXT
);
"""


def connect(db_path: Path = C.DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def build_database(clean: pd.DataFrame, report: QualityReport, db_path: Path = C.DB_PATH) -> None:
    """(Re)create the database tables from the cleaned data and quality report."""
    with connect(db_path) as con:
        con.executescript(SCHEMA)
        clean.to_sql("waste_records", con, if_exists="append", index=False)
        log = report.to_frame().rename(columns={"Check": "Check_Name"})
        log[["Check_Name", "Issues_Found", "Note", "Status"]].to_sql(
            "data_quality_log", con, if_exists="append", index=False)
        if len(report.rejected):
            report.rejected.to_sql("rejected_records", con, if_exists="append", index=False)


def load_records(db_path: Path = C.DB_PATH) -> pd.DataFrame:
    with connect(db_path) as con:
        return pd.read_sql_query(
            "SELECT * FROM waste_records ORDER BY Year, State, Waste_Type", con)


def load_quality_log(db_path: Path = C.DB_PATH) -> pd.DataFrame:
    with connect(db_path) as con:
        return pd.read_sql_query("SELECT * FROM data_quality_log", con)


def load_rejected(db_path: Path = C.DB_PATH) -> pd.DataFrame:
    with connect(db_path) as con:
        return pd.read_sql_query("SELECT * FROM rejected_records", con)


def schema_sql(db_path: Path = C.DB_PATH) -> str:
    """CREATE statements of the stored tables (read live from sqlite_master)."""
    with connect(db_path) as con:
        rows = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL "
                           "ORDER BY name").fetchall()
    return ";\n\n".join(r[0] for r in rows) + ";"


def table_counts(db_path: Path = C.DB_PATH) -> pd.DataFrame:
    """Row count of every table in the database."""
    with connect(db_path) as con:
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = [con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names]
    return pd.DataFrame({"Table": names, "Rows": counts})
