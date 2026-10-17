import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db import DB


def fresh():
    d = Path(tempfile.mkdtemp())
    return DB(d / "t.db")


def test_unseen_then_seen():
    db = fresh()
    assert db.is_seen("blogA", "1001") is False
    db.mark_seen("blogA", "1001", url="http://x/1001")
    assert db.is_seen("blogA", "1001") is True
    assert db.is_seen("blogB", "1001") is False


def test_baseline_marks_without_processing():
    db = fresh()
    db.mark_seen("blogA", "1001", url="u", status="baseline")
    row = db.get("blogA", "1001")
    assert row["status"] == "baseline"
    assert row["data_json"] is None


def test_record_listing_and_status_transition():
    db = fresh()
    lid = db.record_listing("blogA", "2002", url="u", intro_text="소개글...",
                            data={"zone": "상계5구역"})
    row = db.get_by_id(lid)
    assert row["status"] == "pending"
    assert row["data"]["zone"] == "상계5구역"
    db.set_status(lid, "approved")
    assert db.get_by_id(lid)["status"] == "approved"


def test_record_skipped_when_not_listing():
    db = fresh()
    lid = db.record_skip("blogA", "3003", url="u", reason="not_listing")
    row = db.get_by_id(lid)
    assert row["status"] == "skipped"
    assert row["data"] is None


def test_record_listing_preserves_id_after_mark_seen():
    db = fresh()
    db.mark_seen("blogA", "5005", url="u")          # baseline row gets some id
    first_id = db.get("blogA", "5005")["id"]
    lid = db.record_listing("blogA", "5005", url="u", intro_text="x", data={"zone": "z"})
    assert lid == first_id                           # id MUST be stable (no REPLACE)
    assert db.get_by_id(lid)["status"] == "pending"
    assert db.get_by_id(lid)["data"]["zone"] == "z"
