"""AI 分析层：把抓到的原始条目交给 LLM 做摘要 / 重写 / 价值判断。

设计要点：
  1. 只用 OpenAI 兼容接口（DeepSeek / OpenAI / 任何兼容服务都能跑），不绑定厂商 SDK。
  2. **没有 API Key 时自动降级**为"抽取式摘要"，流程照常跑完、照样出 HTML。
     这样你第一次跑就能看到效果，不用先去申请 Key。
  3. 输出强制 JSON，解析容错（去 markdown 围栏、截取首尾大括号）。
"""
from __future__ import annotations

import json
import os
import re

from curl_cffi import requests as cr

TIMEOUT = 180
# 单条正文送进模型的字符上限，防止 ByteByteGo 那种全文 feed 撑爆上下文
TEXT_LIMIT = 1400


SYSTEM_PROMPT = """你是一名给中国计算机专业本科生做技术情报简报的资深编辑。
读者背景：计算机专业本科，正在准备考研，会 C/Python，做过 Web 开发，对 AI 工程、系统、嵌入式有兴趣。
他的诉求只有三件事：① 获取信息 ② 判断未来方向 ③ 提前接触专业工具。

要求：
- 用中文输出（技术名词保留英文原词）。
- 不讲套话，不说"值得关注""具有重要意义"这类空话；每条必须给出具体信息。
- 判断要有依据，不确定就说不确定。
- 只输出 JSON，不要任何解释性文字、不要 markdown 代码围栏。"""

USER_TEMPLATE = """下面是今天抓取到的新条目（共 {n} 条）。请分析并返回 JSON。

{payload}

请严格返回如下 JSON 结构（不要增删顶层字段）：

{{
  "overview": ["今日速览第1条", "第2条", "第3条"],
  "items": [
    {{
      "uid": "原样照抄条目里的 uid",
      "one_line": "一句话说清这条讲了什么（40字以内）",
      "why_matters": "对读者有什么实际价值：是技能/工具/方向判断/行业信号？如何用得上？（80字以内）",
      "tags": ["标签1", "标签2"],
      "action": "读者可以做的下一步动作（没有合适的就写 null）",
      "deep_read": true 或 false
    }}
  ],
  "deep_read_note": "如果挑出了值得深读的，用一句话说明为什么挑它们"
}}

规则：
- overview 3-5 条，覆盖今天最重要的信息，不要去重后重复条目。
- items 必须覆盖上面全部 {n} 条，uid 原样照抄。
- deep_read 为 true 的**最多 3 条**，标准是"信息密度高、有可操作价值、或能改变读者对方向的判断"。
- 纯广告、纯课程推广、纯招聘的条目，deep_read 一律 false。"""


def _truncate(s: str, n: int = TEXT_LIMIT) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + " …[截断]"


def _build_payload(items: list[dict]) -> str:
    blocks = []
    for it in items:
        blocks.append(
            f"### uid: {it['uid']}\n"
            f"来源: {it['source_name']}\n"
            f"标题: {it['title']}\n"
            f"链接: {it.get('link','')}\n"
            f"正文节选: {_truncate(it.get('text',''))}\n"
        )
    return "\n".join(blocks)


def _parse_json(raw: str) -> dict | None:
    if not raw:
        return None
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except Exception:
        pass
    i, j = s.find("{"), s.rfind("}")
    if 0 <= i < j:
        try:
            return json.loads(s[i:j + 1])
        except Exception:
            return None
    return None


def _fallback(items: list[dict]) -> dict:
    """无 API Key 时的降级方案：抽取式摘要，不调 AI。"""
    out_items = []
    for it in items:
        text = re.sub(r"\s+", " ", it.get("text", "")).strip()
        first = re.split(r"(?<=[。.!?])\s", text)[:1]
        one = (first[0] if first else text)[:90] or it["title"][:90]
        out_items.append({
            "uid": it["uid"],
            "one_line": one,
            "why_matters": "（未启用 AI 分析：在 .env 里填 AI_API_KEY 后可获得价值判断）",
            "tags": [],
            "action": None,
            "deep_read": False,
        })
    return {
        "overview": [f"{it['source_name']}：{it['title']}" for it in items[:4]],
        "items": out_items,
        "deep_read_note": "（降级模式：未进行 AI 筛选）",
        "_mode": "fallback",
    }


def analyze(items: list[dict]) -> dict:
    """返回 {overview, items, deep_read_note, _mode}。"""
    if not items:
        return {"overview": [], "items": [], "deep_read_note": "", "_mode": "empty"}

    key = os.getenv("AI_API_KEY", "").strip()
    base = (os.getenv("AI_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
    model = os.getenv("AI_MODEL") or "deepseek-chat"

    if not key:
        print("    [!] 未配置 AI_API_KEY -> 使用抽取式摘要降级模式")
        return _fallback(items)

    payload = _build_payload(items)
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(n=len(items), payload=payload)},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    proxies = None
    hp = os.getenv("HTTP_PROXY") or ""
    sp = os.getenv("HTTPS_PROXY") or ""
    if hp or sp:
        proxies = {"http": hp or sp, "https": sp or hp}

    try:
        print(f"    [*] 调用 {model} 分析 {len(items)} 条…")
        r = cr.post(f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json=body, timeout=TIMEOUT, proxies=proxies)
        if r.status_code != 200:
            print(f"    [x] AI 接口返回 HTTP {r.status_code}: {r.text[:200]}")
            return _fallback(items)
        content = r.json()["choices"][0]["message"]["content"]
        data = _parse_json(content)
        if not data or "items" not in data:
            print("    [x] AI 返回无法解析为 JSON -> 降级")
            return _fallback(items)
        data["_mode"] = "ai"
        data.setdefault("overview", [])
        data.setdefault("deep_read_note", "")
        print(f"    [v] AI 分析完成：{len(data['items'])} 条结果")
        return data
    except Exception as ex:  # noqa: BLE001
        print(f"    [x] AI 调用异常 {type(ex).__name__}: {str(ex)[:150]} -> 降级")
        return _fallback(items)


def merge(items: list[dict], analysis: dict) -> list[dict]:
    """把 AI 结果按 uid 合回条目。"""
    by_uid = {a.get("uid"): a for a in analysis.get("items", [])}
    merged = []
    for it in items:
        a = by_uid.get(it["uid"], {})
        merged.append({**it,
                       "one_line": a.get("one_line", ""),
                       "why_matters": a.get("why_matters", ""),
                       "tags": a.get("tags", []) or [],
                       "action": a.get("action"),
                       "deep_read": bool(a.get("deep_read"))})
    return merged
