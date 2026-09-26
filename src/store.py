"""去重状态层：用 SQLite 记录"哪些条目已经给你看过"。

为什么不用 JSON：
    每天跑一次、每次几十条，JSON 会不断增大且并发写不安全；
    SQLite 是标准库自带，单文件、可查询、天然幂等。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    uid        TEXT PRIMARY KEY,
    source_id  TEXT NOT NULL,
    title      TEXT,
    link       TEXT,
    first_seen TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seen_source ON seen(source_id);
CREATE INDEX IF NOT EXISTS idx_seen_time   ON seen(first_seen);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def filter_new(self, items: list[dict]) -> list[dict]:
        """只留下没见过的条目。"""
        cur = self.conn.cursor()
        fresh = []
        for it in items:
            cur.execute("SELECT 1 FROM seen WHERE uid = ?", (it["uid"],))
            if cur.fetchone() is None:
                fresh.append(it)
        return fresh

    def mark_seen(self, items: list[dict]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.executemany(
            "INSERT OR IGNORE INTO seen (uid, source_id, title, link, first_seen) VALUES (?,?,?,?,?)",
            [(it["uid"], it["source_id"], it["title"][:300], it.get("link", "")[:800], now)
             for it in items],
        )
        self.conn.commit()

    def stats(self) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM seen")
        total = cur.fetchone()[0]
        cur.execute("SELECT source_id, COUNT(*) FROM seen GROUP BY source_id")
        by_src = dict(cur.fetchall())
        return {"total": total, "by_source": by_src}

    def close(self) -> None:
        self.conn.close()
