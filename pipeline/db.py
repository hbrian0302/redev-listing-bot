"""매물 상태 SQLite. status: baseline|skipped|pending|approved|rejected|published."""
import json, sqlite3
from datetime import datetime
from pathlib import Path

VALID_STATUSES = ("baseline", "skipped", "pending", "approved", "rejected", "published")

DEFAULT_PATH = Path(__file__).resolve().parent / "listings.db"


class DB:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS listings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              blog_id TEXT NOT NULL, log_no TEXT NOT NULL,
              url TEXT, status TEXT NOT NULL,
              data_json TEXT, intro_text TEXT, reason TEXT,
              created_at TEXT, updated_at TEXT,
              UNIQUE(blog_id, log_no)
            )""")
        self.conn.commit()

    def _now(self):
        return datetime.now().isoformat(timespec="seconds")

    def is_seen(self, blog_id: str, log_no: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM listings WHERE blog_id=? AND log_no=?", (blog_id, log_no))
        return cur.fetchone() is not None

    def mark_seen(self, blog_id, log_no, url="", status="baseline"):
        now = self._now()
        self.conn.execute(
            "INSERT OR IGNORE INTO listings(blog_id,log_no,url,status,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?)", (blog_id, log_no, url, status, now, now))
        self.conn.commit()

    def record_listing(self, blog_id, log_no, url, intro_text, data: dict) -> int:
        now = self._now()
        self.conn.execute(
            "INSERT OR IGNORE INTO listings(blog_id,log_no,url,status,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?)", (blog_id, log_no, url, "pending", now, now))
        self.conn.execute(
            "UPDATE listings SET url=?, status=?, data_json=?, intro_text=?, updated_at=?"
            " WHERE blog_id=? AND log_no=?",
            (url, "pending", json.dumps(data, ensure_ascii=False), intro_text, now,
             blog_id, log_no))
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM listings WHERE blog_id=? AND log_no=?", (blog_id, log_no)).fetchone()
        return row["id"]

    def record_skip(self, blog_id, log_no, url, reason) -> int:
        now = self._now()
        self.conn.execute(
            "INSERT OR IGNORE INTO listings(blog_id,log_no,url,status,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?)", (blog_id, log_no, url, "skipped", now, now))
        self.conn.execute(
            "UPDATE listings SET url=?, status=?, reason=?, updated_at=?"
            " WHERE blog_id=? AND log_no=?",
            (url, "skipped", reason, now, blog_id, log_no))
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM listings WHERE blog_id=? AND log_no=?", (blog_id, log_no)).fetchone()
        return row["id"]

    def set_status(self, listing_id: int, status: str):
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status}")
        self.conn.execute("UPDATE listings SET status=?, updated_at=? WHERE id=?",
                          (status, self._now(), listing_id))
        self.conn.commit()

    def _row(self, r):
        if r is None:
            return None
        d = dict(r)
        d["data"] = json.loads(d["data_json"]) if d["data_json"] else None
        return d

    def get(self, blog_id, log_no):
        return self._row(self.conn.execute(
            "SELECT * FROM listings WHERE blog_id=? AND log_no=?", (blog_id, log_no)).fetchone())

    def get_by_id(self, listing_id):
        return self._row(self.conn.execute(
            "SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone())
