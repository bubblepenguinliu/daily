"""去重状态层：记录"哪些条目已经给你看过"。

为什么不用 SQLite（踩过的坑）：
    这个文件要提交回 Git 仓库，而 GitHub Actions 也会往里写。
    SQLite 是二进制文件，一旦本地和 CI 都写过，Git 直接报
    "Cannot merge binary files" 并把整个 workflow 干挂。

为什么是 JSONL（每行一条独立 JSON）而不是一个大 JSON：
    JSONL 配合 Git 的 union 合并驱动（见 .gitattributes），
    两边各自新增的行会被直接拼接，**永远不会产生冲突** ——
    这对"多人/多机器同时写一个集合"是最稳的形态。
    一个大 JSON 对象做不到这点（行交错就会冲突）。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# 保留天数：超过这个天数的记录在保存时剔除。
# 注意：union 合并可能让被剔除的行"复活"，但这不影响正确性 ——
# feed 里早就没有的旧条目，就算 uid 还在也不会再被抓到。
KEEP_DAYS = 400


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.seen: dict[str, dict] = {}
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        bad = 0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                uid = rec["uid"]
                self.seen[uid] = {"src": rec.get("src", "?"), "date": rec.get("date", "")}
            except Exception:
                bad += 1
        if bad:
            print(f"    [!] {self.path.name} 有 {bad} 行无法解析，已跳过（不影响其余记录）")

    def filter_new(self, items: list[dict]) -> list[dict]:
        return [it for it in items if it["uid"] not in self.seen]

    def mark_seen(self, items: list[dict]) -> None:
        day = datetime.now().strftime("%Y-%m-%d")
        for it in items:
            self.seen.setdefault(it["uid"], {"src": it["source_id"], "date": day})

    def save(self) -> None:
        # 按 uid 排序 + 每行一条：同样的集合永远产出同样的文件，
        # 这是让 union 合并结果稳定的前提。
        cutoff = datetime.now().toordinal() - KEEP_DAYS
        rows = []
        for uid, v in self.seen.items():
            try:
                if datetime.strptime(v.get("date", ""), "%Y-%m-%d").toordinal() < cutoff:
                    continue
            except Exception:
                pass
            rows.append(json.dumps({"uid": uid, "src": v.get("src", "?"),
                                    "date": v.get("date", "")},
                                   ensure_ascii=False, sort_keys=True))
        rows.sort()
        self.path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def stats(self) -> dict:
        by_src: dict[str, int] = {}
        for v in self.seen.values():
            s = v.get("src", "?")
            by_src[s] = by_src.get(s, 0) + 1
        return {"total": len(self.seen), "by_source": by_src}

    def close(self) -> None:   # 兼容旧调用
        self.save()


def migrate_from_sqlite(state_dir: str | Path) -> int:
    """一次性迁移：seen.sqlite -> seen.jsonl。返回迁移条数。"""
    import sqlite3

    d = Path(state_dir)
    old, new = d / "seen.sqlite", d / "seen.jsonl"
    if not old.exists() or new.exists():
        return 0
    conn = sqlite3.connect(str(old))
    try:
        rows = conn.execute("SELECT uid, source_id, substr(first_seen,1,10) FROM seen").fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    lines = sorted(json.dumps({"uid": r[0], "src": r[1], "date": r[2] or ""},
                              ensure_ascii=False, sort_keys=True) for r in rows)
    new.write_text("\n".join(lines) + "\n", encoding="utf-8")
    old.rename(old.with_suffix(".sqlite.migrated"))
    return len(lines)
