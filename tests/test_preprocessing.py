import pandas as pd
import pytest

from waste_analytics import config as C
from waste_analytics import database, preprocessing as P


def test_original_dataset_is_clean_and_complete():
    raw = P.load_raw(C.RAW_CSV)
    clean, rep = P.validate_and_clean(raw)
    assert len(raw) == 300 and len(clean) == 300
    assert rep.rejected.empty
    cov = P.coverage_summary(clean)
    assert cov["years"] == [2020, 2021, 2022]
    assert cov["states"] == 10 and cov["waste_types"] == 10 and cov["complete_grid"]


def test_validate_does_not_mutate_input(small_df):
    before = small_df.copy()
    P.validate_and_clean(small_df)
    pd.testing.assert_frame_equal(before, small_df)


def _row(**kw):
    base = dict(zip(C.REQUIRED_COLS, (2021, "A", "Plastic", 100.0, 80.0, 40.0, 10.0)))
    base.update(kw)
    return base


@pytest.mark.parametrize("bad, reason", [
    (_row(Waste_Generated_TPD=None), "missing"),
    (_row(Waste_Collected_TPD="abc"), "non-numeric"),
    (_row(Waste_Treated_TPD=-5.0), "negative"),
    (_row(Waste_Collected_TPD=150.0), "collected > generated"),
    (_row(Waste_Treated_TPD=90.0), "treated > collected"),
    (_row(Waste_Recycled_TPD=60.0), "recycled > treated"),
    (_row(Year=1850), "year out of range"),
])
def test_invalid_records_are_rejected(bad, reason):
    good = _row(State="B")
    raw = pd.DataFrame([good, bad])
    clean, rep = P.validate_and_clean(raw)
    assert len(clean) == 1 and clean.iloc[0][C.STATE] == "B"
    assert len(rep.rejected) == 1
    assert reason.split()[0] in rep.rejected.iloc[0]["Rejection_Reason"]


def test_duplicates_rejected_first_kept():
    raw = pd.DataFrame([_row(), _row(), _row(Waste_Generated_TPD=120.0)])
    clean, rep = P.validate_and_clean(raw)
    assert len(clean) == 1
    reasons = " ".join(rep.rejected["Rejection_Reason"])
    assert "exact duplicate" in reasons and "duplicate key" in reasons


def test_whitespace_in_text_is_normalised():
    raw = pd.DataFrame([_row(State="  Kerala "), _row(State="Kerala", Waste_Type="Paper")])
    clean, _ = P.validate_and_clean(raw)
    assert set(clean[C.STATE]) == {"Kerala"}


def test_zero_values_are_valid_but_not_rejected():
    raw = pd.DataFrame([_row(Waste_Generated_TPD=0.0, Waste_Collected_TPD=0.0,
                             Waste_Treated_TPD=0.0, Waste_Recycled_TPD=0.0)])
    clean, rep = P.validate_and_clean(raw)
    assert len(clean) == 1 and rep.rejected.empty


def test_missing_required_column_raises(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("Year,State\n2020,X\n")
    with pytest.raises(ValueError):
        P.load_raw(p)


def test_database_roundtrip(tmp_path, small_df):
    clean, rep = P.validate_and_clean(small_df)
    db = tmp_path / "t.db"
    database.build_database(clean, rep, db)
    back = database.load_records(db)
    assert len(back) == len(clean)
    assert float(back[C.GEN].sum()) == float(clean[C.GEN].sum())
    assert not database.load_quality_log(db).empty
