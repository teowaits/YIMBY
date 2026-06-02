"""SQLite HTTP response cache."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


class Cache:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                url_hash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at REAL DEFAULT (unixepoch('now'))
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def hash_url(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def get(self, url: str) -> dict[str, Any] | None:
        h = self.hash_url(url)
        row = self._conn.execute(
            "SELECT body FROM cache WHERE url_hash = ?", (h,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def set(self, url: str, data: dict[str, Any]) -> None:
        h = self.hash_url(url)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (url_hash, url, body) VALUES (?, ?, ?)",
            (h, url, json.dumps(data)),
        )
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM cache")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
