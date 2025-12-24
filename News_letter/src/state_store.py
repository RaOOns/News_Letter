import os
import sqlite3
from datetime import datetime
from typing import Optional

class StateStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS run_state (
                    run_date TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    reason TEXT
                )
            """)
            con.commit()

    def is_success(self, run_date: str) -> bool:
        with self._connect() as con:
            cur = con.execute("SELECT status FROM run_state WHERE run_date = ?", (run_date,))
            row = cur.fetchone()
            return bool(row and row[0] == "SUCCESS")

    def mark_running(self, run_date: str, attempt: int = 1):
        self._upsert(run_date, "RUNNING", attempt, None)

    def mark_success(self, run_date: str, attempt: int = 1):
        self._upsert(run_date, "SUCCESS", attempt, None)

    def mark_failed(self, run_date: str, attempt: int = 1, reason: str = ""):
        self._upsert(run_date, "FAILED", attempt, reason)

    def _upsert(self, run_date: str, status: str, attempt: int, reason: Optional[str]):
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as con:
            con.execute("""
                INSERT INTO run_state (run_date, status, attempt, updated_at, reason)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_date) DO UPDATE SET
                    status=excluded.status,
                    attempt=excluded.attempt,
                    updated_at=excluded.updated_at,
                    reason=excluded.reason
            """, (run_date, status, int(attempt), now, reason))
            con.commit()

    def reset(self, run_date: str):
        with self._connect() as con:
            con.execute("DELETE FROM run_state WHERE run_date = ?", (run_date,))
            con.commit()
