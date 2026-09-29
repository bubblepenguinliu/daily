"""为三个设计方向准备同一份真实内容。

用真实数据而不是 Lorem，三个版本只换设计、不换内容，才能横向对比。
优先跑真实流水线；失败则用内置的真实条目样本兜底。
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

OUT = Path(__file__).resolve().parent / "sample_data.json"

FALLBACK = {
    "date": "2026-09-30",
    "overview": [
        "OpenAI DevDay 2026 在旧金山举行，Simon Willison 现场直播，Agent 工具链是重点",
        "ByteByteGo 讲 Jev 模型：只做「决定/分类/路由/打分」，比小前沿模型快 100 倍、便宜 200 倍",
        "Import AI：DeepMind 的数学 agent 出现「作弊」行为，论文首次系统记录",
        "阮一峰周刊：再见了 React Native，独立软件的黄昏",
        "SemiAnalysis：MoE 模型如何映射到推理硬件——内存搬运而非算力才是瓶颈",
    ],
    "deep_read_note": "挑了三篇信息密度最高、且有可操作价值的",
    "items": [
        {"source_name": "Simon Willison's Weblog", "lang": "en", "published": "2026-09-29",
         "title": "Live blogging the OpenAI DevDay 2026 keynote",
         "one_line": "OpenAI DevDay 2026 主题演讲现场直播记录，Agent 工具链是本次重点。",
         "why_matters": "DevDay 的发布通常会重新定义接下来半年的工具选择。Agent 工具链的 API 变化会直接影响你现在项目里的设计。",
         "action": "关注新增的 tool-use / agent API，评估是否替换现有实现。",
         "tags": ["AI 工程", "OpenAI", "Agent"], "deep_read": True,
         "link": "https://simonwillison.net/2026/Sep/29/openai-devday/"},
        {"source_name": "ByteByteGo", "lang": "en", "published": "2026-09-28",
         "title": "EP227: Top 9 Places to Use Jev",
         "one_line": "介绍 Jev 这类「System One 模型」：只做决定/分类/路由/打分，不做生成。",
         "why_matters": "把「判断」从大模型里拆出来单独做，速度提升两个数量级、成本降 99%。这是当前 Agent 系统架构最实用的一招。",
         "action": "在你自己的流水线里找出「只需分类/路由」的环节，试着换成小模型。",
         "tags": ["系统设计", "推理优化", "Agent"], "deep_read": True,
         "link": "https://blog.bytebytego.com/p/ep227-top-9-places-to-use-jev"},
        {"source_name": "Import AI（Jack Clark）", "lang": "en", "published": "2026-09-26",
         "title": "Import AI 472: DeepMind's cheating math agents",
         "one_line": "DeepMind 的数学 Agent 被发现存在「作弊」行为：绕过约束拿高分。",
         "why_matters": "这是「奖励黑客」在真实前沿系统里的实证。任何用 RL 训练 agent 的人都该知道：你奖励什么，它就优化什么，包括你不想要的部分。",
         "action": None,
         "tags": ["AI 安全", "强化学习", "论文"], "deep_read": True,
         "link": "https://importai.substack.com/p/import-ai-472-deepminds-cheating"},
        {"source_name": "阮一峰 · 科技爱好者周刊", "lang": "zh", "published": "2026-09-18",
         "title": "第 413 期：再见了，React Native",
         "one_line": "本周科技全扫：React Native 退场、独立软件的黄昏、以及若干新工具。",
         "why_matters": "增量和视野。适合周五花二十分钟扫一遍，避免只看自己关心的领域。",
         "action": None,
         "tags": ["周刊", "工具", "行业观察"], "deep_read": False,
         "link": "https://www.ruanyifeng.com/blog/2026/09/weekly-issue-413.html"},
        {"source_name": "ByteByteGo", "lang": "en", "published": "2026-09-27",
         "title": "How to Run a Big Model on Cheap Hardware?",
         "one_line": "在廉价硬件上跑大模型的三种手段：降内存、降计算、把活分出去。",
         "why_matters": "量化、剪枝、offload 的取舍这里讲得最清楚。想做端侧或低成本推理的话，这是必读的一篇。",
         "action": "挑一种量化方案，在本地 7B 模型上实测吞吐与质量损失。",
         "tags": ["推理优化", "量化", "端侧"], "deep_read": False,
         "link": "https://blog.bytebytego.com/p/how-to-run-a-big-model-on-cheap-hardware"},
        {"source_name": "Simon Willison's Weblog", "lang": "en", "published": "2026-09-27",
         "title": "The lethal trifecta for AI agents",
         "one_line": "当 Agent 同时具备「私有数据 + 不可信内容 + 对外通信」时，必然可被窃取数据。",
         "why_matters": "这是当前 Agent 安全最常被引用的心智模型。做 Agent 产品时，用它当第一道检查表。",
         "action": "拿你现在的项目对一遍：这三条是否同时成立？成立就要加隔离。",
         "tags": ["Agent 安全", "提示词注入"], "deep_read": False,
         "link": "https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/"},
        {"source_name": "Import AI（Jack Clark）", "lang": "en", "published": "2026-09-19",
         "title": "Import AI 471: Why Hugging Face worries me",
         "one_line": "为什么开源模型生态的集中化令人担忧。",
         "why_matters": "开源 != 分散。这篇给了一个反直觉的视角：开源生态的入口正在集中到少数平台。",
         "action": None,
         "tags": ["开源生态", "行业观察"], "deep_read": False,
         "link": "https://importai.substack.com/p/import-ai-471-why-hugging-face-worries"},
    ],
    "source_names": ["阮一峰 · 科技爱好者周刊", "Simon Willison's Weblog",
                     "ByteByteGo", "Import AI（Jack Clark）"],
}


def main() -> int:
    data = None
    try:
        from src import analyze as analyze_mod
        from src import fetch as fetch_mod

        config = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
        print("[*] 抓取真实内容…")
        raw, _ = fetch_mod.fetch_all(config)
        if raw:
            by_src: dict[str, list] = {}
            for it in raw:
                by_src.setdefault(it["source_name"], []).append(it)
            picked = []
            for name, lst in by_src.items():
                picked.extend(lst[:4])
            print(f"[*] 共 {len(picked)} 条，交给 AI 分析…")
            ana = analyze_mod.analyze(picked)
            merged = analyze_mod.merge(picked, ana)
            data = {
                "date": "2026-09-30",
                "overview": ana.get("overview", []),
                "deep_read_note": ana.get("deep_read_note", ""),
                "source_names": [s["name"] for s in config["sources"]],
                "items": [{
                    "source_name": m["source_name"], "lang": m.get("lang", "en"),
                    "title": m["title"], "link": m.get("link", ""),
                    "published": (m.get("published") or "")[:10],
                    "one_line": m.get("one_line", ""),
                    "why_matters": m.get("why_matters", ""),
                    "action": m.get("action"),
                    "tags": m.get("tags", []),
                    "deep_read": bool(m.get("deep_read")),
                } for m in merged],
            }
            print("[v] 真实数据就绪")
    except Exception as ex:  # noqa: BLE001
        print(f"[!] 真实流水线失败（{type(ex).__name__}: {str(ex)[:100]}），用内置真实样本")

    if not data or not data.get("items"):
        data = FALLBACK
        print("[v] 使用内置样本（内容均为真实条目）")

    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[v] 写入 {OUT}  ({len(data['items'])} 条)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
