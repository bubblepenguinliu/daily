"""tech-daily-digest 主入口。

用法:
    python -m src.main                # 正常每日跑（只处理新条目）
    python -m src.main --all          # 忽略去重，把当前 feed 里所有条目都处理一遍
    python -m src.main --limit 3      # 每个来源最多取 3 条
    python -m src.main --full 2       # 本期做 2 篇全文精译（overrides DIGEST_FULL_COUNT）
    python -m src.main --no-ai        # 强制不使用 AI（抽取式摘要 + 原文直出）

流程：
    抓取 → 去重 → 截断 → 第一遍分析(速览/挑选) → 拉正文 → 第二遍(翻译+边注) → 渲染
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import analyze as analyze_mod  # noqa: E402
from src import extract as extract_mod  # noqa: E402
from src import fetch as fetch_mod      # noqa: E402
from src import render as render_mod    # noqa: E402
from src import store as store_mod      # noqa: E402

STEPS = 6


def load_config() -> dict:
    with open(ROOT / "config" / "sources.json", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description="技术情报日报生成器")
    ap.add_argument("--all", action="store_true", help="忽略去重状态，处理全部条目")
    ap.add_argument("--limit", type=int, default=None, help="每个来源最多取几条")
    ap.add_argument("--full", type=int, default=None, help="本期全文精译几篇")
    ap.add_argument("--no-ai", action="store_true", help="强制降级为抽取式摘要")
    ap.add_argument("--out", default=str(ROOT / "output"), help="HTML 输出目录")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")

    if args.no_ai:
        os.environ["AI_API_KEY"] = ""

    config = load_config()
    source_names = [s["name"] for s in config["sources"]]
    limit = args.limit or int(os.getenv("MAX_ITEMS_PER_SOURCE", "6"))
    if args.full:
        os.environ["DIGEST_FULL_COUNT"] = str(args.full)

    print("\n=== tech-daily-digest ===")

    print(f"[1/{STEPS}] 抓取")
    raw, used = fetch_mod.fetch_all(config)
    if not raw:
        print("\n没有抓到任何内容，检查网络/代理后重试。")
        return 2

    print(f"[2/{STEPS}] 去重")
    state_dir = ROOT / "state"
    migrated = store_mod.migrate_from_sqlite(state_dir)
    if migrated:
        print(f"    已从旧 seen.sqlite 迁移 {migrated} 条记录到 seen.jsonl")
    store = store_mod.Store(state_dir / "seen.jsonl")
    items = raw if args.all else store.filter_new(raw)
    print(f"    共 {len(raw)} 条，其中 {len(items)} 条是新内容"
          f"{'（--all：忽略去重）' if args.all else ''}")
    if not items:
        print("\n今天没有新内容，不需要生成日报。")
        store.close()
        return 0

    print(f"[3/{STEPS}] 截断（每个来源最多 {limit} 条）")
    capped: list[dict] = []
    for name in source_names:
        bucket = [it for it in items if it["source_name"] == name]
        capped.extend(bucket[:limit])
    items = capped
    print(f"    送入分析：{len(items)} 条")

    print(f"[4/{STEPS}] 分析（第一遍 · 速览与挑选）")
    analysis = analyze_mod.analyze(items)
    merged = analyze_mod.merge(items, analysis)

    picked = [it for it in merged if it["deep_read"]][:analyze_mod.full_count()]
    print(f"[5/{STEPS}] 正文精译（拉取正文 + 翻译 + 边注）")
    if picked:
        print(f"    拉取正文：{len(picked)} 篇")
        ok = extract_mod.enrich(picked, limit=analyze_mod.body_limit())
        print(f"    正文抓取成功 {ok}/{len(picked)} 篇")
        analyze_mod.translate_all(merged)
    else:
        print("    无精选条目，跳过")

    print(f"[6/{STEPS}] 生成 HTML")
    out, rstats = render_mod.render(merged, analysis, source_names, args.out)
    store.mark_seen(raw)   # 全部抓到过的都标记，避免下次重复
    stats = store.stats()
    store.close()

    print(f"\n完成：{out}")
    print(f"  模式      : {analysis.get('_mode')}")
    print(f"  本次条目  : {rstats['items']} 条")
    print(f"  全文精译  : {rstats['picked']} 篇（成功 {rstats['translated']}）/ "
          f"{rstats['blocks']} 段 / {rstats['notes']} 条边注")
    if rstats["picked"] and rstats["notes"] < rstats["picked"] * analyze_mod.MIN_NOTES:
        print(f"  ⚠ 边注密度不足：要求每篇≥{analyze_mod.MIN_NOTES} 条")
    print(f"  累计已见  : {stats['total']} 条 {stats['by_source']}")
    print(f"  打开方式  : start \"\" \"{out}\"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
