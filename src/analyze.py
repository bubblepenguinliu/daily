"""AI 分析层，两遍：

  第一遍 analyze()      —— 全部条目 → 速览 + 一句话 + 价值 + 标签 + 动作，并挑出精选
  第二遍 translate_all()—— 精选条目 → **完整中文翻译（分段）+ 每篇≥5条边注**

设计要点：
  1. 只用 OpenAI 兼容接口（DeepSeek / OpenAI / 任何兼容服务都能跑），不绑定厂商 SDK。
  2. **没有 API Key 时自动降级**：第一遍退回抽取式摘要，第二遍退回"原文直出 + 明确标注未翻译"。
     流程照常跑完、照样出 HTML，不阻塞。
  3. 输出强制 JSON，解析容错（去 markdown 围栏、截取首尾大括号）。
  4. 翻译逐篇调用，不批量 —— 批量容易在长输出里被判 JSON 截断。
"""
from __future__ import annotations

import json
import os
import re

from curl_cffi import requests as cr

TIMEOUT = 300
# 第一遍单条送进模型的字符上限
TEXT_LIMIT = 1400

# 批注类型固定词表（前端据此着色，也给模型一个收敛的选择空间）
NOTE_KINDS = ["背景", "延伸", "质疑", "数据", "实操"]
MIN_NOTES = 5


def full_count() -> int:
    try:
        return max(1, min(6, int(os.getenv("DIGEST_FULL_COUNT", "3"))))
    except ValueError:
        return 3


def body_limit() -> int:
    try:
        return max(1200, int(os.getenv("DIGEST_BODY_LIMIT", "6000")))
    except ValueError:
        return 6000


# ---------------------------------------------------------------- 共用

READER = """读者背景：中国计算机专业本科生，正在准备考研，会 C/Python，做过 Web 开发，
对 AI 工程、系统、嵌入式有兴趣。他的诉求只有三件事：① 获取信息 ② 判断未来方向 ③ 提前接触专业工具。"""


def _proxies() -> dict | None:
    hp = os.getenv("HTTP_PROXY") or ""
    sp = os.getenv("HTTPS_PROXY") or ""
    if hp or sp:
        return {"http": hp or sp, "https": sp or hp}
    return None


def _key() -> str:
    return os.getenv("AI_API_KEY", "").strip()


def _call(system: str, user: str, temperature: float = 0.3, max_tokens: int | None = None) -> dict | None:
    """调一次模型，返回解析后的 JSON；失败返回 None。"""
    base = (os.getenv("AI_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
    model = os.getenv("AI_MODEL") or "deepseek-chat"
    body: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    if max_tokens:
        body["max_tokens"] = max_tokens
    try:
        r = cr.post(f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {_key()}",
                             "Content-Type": "application/json"},
                    json=body, timeout=TIMEOUT, proxies=_proxies())
        if r.status_code != 200:
            print(f"        [x] AI 接口 HTTP {r.status_code}: {r.text[:160]}")
            return None
        return _parse_json(r.json()["choices"][0]["message"]["content"])
    except Exception as ex:  # noqa: BLE001
        print(f"        [x] AI 调用异常 {type(ex).__name__}: {str(ex)[:140]}")
        return None


def _parse_json(raw: str) -> dict | None:
    if not raw:
        return None
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        pass
    i, j = s.find("{"), s.rfind("}")
    if 0 <= i < j:
        try:
            return json.loads(s[i:j + 1])
        except Exception:  # noqa: BLE001
            return None
    return None


def _truncate(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + " …[截断]"


# ---------------------------------------------------------------- 第一遍：全局速览

SYS1 = f"""你是一名给中国计算机专业本科生做技术情报简报的资深编辑。
{READER}

要求：
- 用中文输出（技术名词保留英文原词）。
- 不讲套话，不说"值得关注""具有重要意义"这类空话；每条必须给出具体信息。
- 判断要有依据，不确定就说不确定。
- 只输出 JSON，不要任何解释性文字、不要 markdown 代码围栏。"""

USER1 = """下面是今天抓取到的新条目（共 {n} 条）。请分析并返回 JSON。

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
- overview 3-5 条，覆盖今天最重要的信息，不要与条目重复。
- items 必须覆盖上面全部 {n} 条，uid 原样照抄。
- deep_read 为 true 的**最多 {cap} 条**，标准是"信息密度高、有可操作价值、或能改变读者对方向的判断"。
- 纯广告、纯课程推广、纯招聘的条目，deep_read 一律 false。"""


def _build_payload(items: list[dict]) -> str:
    return "\n".join(
        f"### uid: {it['uid']}\n"
        f"来源: {it['source_name']}\n"
        f"标题: {it['title']}\n"
        f"链接: {it.get('link','')}\n"
        f"正文节选: {_truncate(it.get('text',''), TEXT_LIMIT)}\n"
        for it in items
    )


def _fallback(items: list[dict]) -> dict:
    out = []
    for it in items:
        text = re.sub(r"\s+", " ", it.get("text", "")).strip()
        first = re.split(r"(?<=[。.!?])\s", text)[:1]
        one = (first[0] if first else text)[:90] or it["title"][:90]
        out.append({"uid": it["uid"], "one_line": one,
                    "why_matters": "（未启用 AI 分析：在 .env 里填 AI_API_KEY 后可获得价值判断）",
                    "tags": [], "action": None, "deep_read": False})
    return {"overview": [f"{it['source_name']}：{it['title']}" for it in items[:4]],
            "items": out, "deep_read_note": "（降级模式：未进行 AI 筛选）", "_mode": "fallback"}


# ---------------------------------------------------------------- 第二遍：翻译 + 边注

SYS2 = f"""你是一名技术翻译 + 技术评论者，同时做两件事：

【任务一 · 翻译】把一篇英文技术文章**完整、忠实地**译成中文。
  · 忠实优先：不压缩、不概括、不合并段落。原文有几段就译几段，论证链和细节都要在。
  · 技术名词保留英文原词（如 KV cache、prefill、tool use、write skew），不要生硬意译。
  · 译文要通顺，是"润色过的中文"，不是逐字硬译。但润色不等于改写内容。
  · 原文里的数字、版本号、模型名、URL、人名，一律照抄不改。

【任务二 · 边注】在正文右侧的页边空白处，为读者加**补充拓展**批注。
  · **每篇至少 {MIN_NOTES} 条**（通常 6-8 条），分布在**至少 3 个不同段落**上。
  · 批注的价值在于"**原文没说的信息**"，六种取向随机应变：
      - 背景：这条依赖的前置知识 / 历史脉络 / 是谁在说
      - 延伸：顺着这个思路还有什么相关进展、相邻领域在做什么
      - 质疑：这个结论的成立条件是什么，什么情况下会不成立
      - 数据：补一个具体数字/对比/量级，让抽象说法落地
      - 实操：读者自己怎么动手验证或复现
      - 纠偏：原文可能的疏漏、术语误用、或与其他来源冲突之处
  · **禁止**复述原文、禁止"值得关注""很有启发"这类空话。每条批注独立的、具体的、可验证。
  · 批注 40-120 字，一句话说清一件事。

{READER}

只输出 JSON，不要任何解释性文字、不要 markdown 代码围栏。"""

USER2 = """请翻译并加边注。

标题（原文）：{title}
来源：{source}
链接：{link}

正文（原文）：
---
{body}
---

请严格返回如下 JSON 结构：

{{
  "title_zh": "标题的中文译名（保留必要英文术语）",
  "standfirst": "一句话导语，30字以内，说清这篇文章在讲什么",
  "blocks": [
    {{
      "p": "第1段的中文译文",
      "notes": [
        {{"k": "背景", "t": "这一段的补充批注"}},
        {{"k": "数据", "t": "另一条批注"}}
      ]
    }},
    {{"p": "第2段的中文译文", "notes": []}}
  ],
  "takeaway": "读完之后读者应该记住的一件事（50字以内，要具体）"
}}

规则：
- blocks 必须覆盖原文**全部段落**，不要跳段、不要合并段。原文有 N 段就至少输出 N 个 block。
- notes 的 k 只能从这些值里选：{kinds}
- 全篇批注总数**至少 {MIN_NOTES} 条**，且不能全部堆在同一段上。
- 如果原文某段很短（如小标题），p 照译，notes 可为空。
- 不要输出原文，只输出译文。"""


# ---------------------------------------------------------------- 中文源：只加边注

CJK = re.compile(r"[\u4e00-\u9fff]")


def detect_lang(text: str, threshold: float = 0.15) -> str:
    """粗判正文语言：中日韩字符占比过阈值即视为中文源。"""
    t = (text or "")[:3000]
    if not t:
        return "en"
    return "zh" if len(CJK.findall(t)) / len(t) > threshold else "en"


SYS_ZH = f"""你是一名技术评论者。这篇文章**本身就是中文，不需要翻译**，你的唯一任务是给它加边注。

边注写在正文右侧的页边空白处，作用是为读者**补充拓展**原文没有的信息：
  · **每篇至少 {MIN_NOTES} 条**（通常 6-8 条），分布在**至少 3 个不同段落**上。
  · 取向随机应变：
      - 背景：这条依赖的前置知识 / 历史脉络 / 是谁在说
      - 延伸：顺着这个思路还有什么相关进展、相邻领域在做什么
      - 质疑：这个结论的成立条件是什么，什么情况下会不成立
      - 数据：补一个具体数字/对比/量级，让抽象说法落地
      - 实操：读者自己怎么动手验证或复现
      - 纠偏：原文可能的疏漏、术语误用、或与其他来源冲突之处
  · **禁止**复述原文、禁止"值得关注""很有启发"这类空话。每条都要具体、可验证。
  · 批注 40-120 字，一句话说清一件事。

{READER}

只输出 JSON，不要任何解释性文字、不要 markdown 代码围栏。"""

USER_ZH = """下面是一篇中文文章的段落（已编号）。请加边注并返回 JSON。

标题：{title}
来源：{source}
链接：{link}

段落：
{numbered}

请严格返回：

{{
  "standfirst": "一句话导语，30字以内，说清这篇文章在讲什么",
  "takeaway": "读完之后读者应该记住的一件事（50字以内，要具体）",
  "notes": [
    {{"i": 3, "k": "背景", "t": "挂在第 3 段上的批注"}},
    {{"i": 7, "k": "数据", "t": "挂在第 7 段上的批注"}}
  ]
}}

规则：
- notes 的 i 是**段落编号**，必须落在 0 到 {last} 之间（含端点）。
- 全篇至少 {MIN_NOTES} 条，且不能全部堆在同一段上。
- k 只能从这些值里选：{kinds}
- 不要输出译文、不要复述段落内容。"""


def _annotate_zh(item: dict) -> dict:
    """中文源：段落原样保留，只让 AI 补边注。"""
    paras = item.get("paras") or []
    if not paras:
        return _degraded(item, "无段落")
    numbered = "\n".join(f"[{i}] {p}" for i, p in enumerate(paras))
    data = _call(SYS_ZH, USER_ZH.format(
        title=item["title"], source=item["source_name"], link=item.get("link", ""),
        numbered=_truncate(numbered, body_limit()), kinds=" / ".join(NOTE_KINDS),
        MIN_NOTES=MIN_NOTES, last=len(paras) - 1), temperature=0.25)
    if not data:
        return _degraded(item, "AI 批注失败")

    buckets: dict[int, list] = {}
    dropped = 0
    for nt in data.get("notes") or []:
        t = (nt.get("t") or "").strip()
        if not t:
            continue
        try:
            i = int(nt.get("i"))
        except (TypeError, ValueError):
            dropped += 1
            continue
        if not (0 <= i < len(paras)):
            dropped += 1
            continue
        k = (nt.get("k") or "").strip()
        if k not in NOTE_KINDS:
            k = "延伸"
        buckets.setdefault(i, []).append({"k": k, "t": t})

    if dropped:
        print(f"        [!] {dropped} 条批注的段落编号越界，已丢弃")
    blocks = [{"p": p, "notes": buckets.get(i, [])} for i, p in enumerate(paras)]
    n_notes = sum(len(v) for v in buckets.values())
    return {
        "title_zh": item["title"],
        "standfirst": (data.get("standfirst") or "").strip(),
        "takeaway": (data.get("takeaway") or "").strip(),
        "blocks": blocks,
        "n_notes": n_notes,
        "translated": True,      # AI 处理成功（中文源是"原文 + 批注"，非失败）
        "annotated": True,
        "src_lang": "zh",
    }


def translate_one(item: dict) -> dict:
    """对一篇精选文章做完整翻译 + 边注。中文源只加边注，不做无意义的中译中。"""
    body = item.get("body") or ""
    if not _key():
        return _degraded(item, "未配置 AI_API_KEY")
    if len(body) < 400:
        return _degraded(item, "未取到正文")

    if detect_lang(body) == "zh":
        return _annotate_zh(item)

    data = _call(SYS2, USER2.format(
        title=item["title"], source=item["source_name"],
        link=item.get("link", ""), body=_truncate(body, body_limit()),
        kinds=" / ".join(NOTE_KINDS), MIN_NOTES=MIN_NOTES),
        temperature=0.25)
    if not data or not data.get("blocks"):
        return _degraded(item, "AI 翻译失败")

    blocks = []
    n_notes = 0
    for b in data.get("blocks", []):
        p = (b.get("p") or "").strip()
        if not p:
            continue
        notes = []
        for nt in b.get("notes") or []:
            t = (nt.get("t") or "").strip()
            if not t:
                continue
            k = (nt.get("k") or "").strip()
            if k not in NOTE_KINDS:
                k = "延伸"
            notes.append({"k": k, "t": t})
        n_notes += len(notes)
        blocks.append({"p": p, "notes": notes})

    return {
        "title_zh": (data.get("title_zh") or item["title"]).strip(),
        "standfirst": (data.get("standfirst") or "").strip(),
        "takeaway": (data.get("takeaway") or "").strip(),
        "blocks": blocks,
        "n_notes": n_notes,
        "translated": True,
        "src_lang": "en",
    }


def _degraded(item: dict, why: str) -> dict:
    """没能翻译时：原文直出，并明确标注，不假装有译文。"""
    paras = item.get("paras") or []
    if not paras:
        body = item.get("body") or item.get("text") or ""
        paras = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
    blocks = [{"p": p, "notes": []} for p in paras[:40]]
    return {
        "title_zh": item["title"],
        "standfirst": f"（{why}，此篇显示原文，未翻译、无批注）",
        "takeaway": "",
        "blocks": blocks,
        "n_notes": 0,
        "translated": False,
    }


# ---------------------------------------------------------------- 对外接口

def analyze(items: list[dict]) -> dict:
    """第一遍：速览 + 每条摘要 + 挑精选。"""
    if not items:
        return {"overview": [], "items": [], "deep_read_note": "", "_mode": "empty"}
    if not _key():
        print("    [!] 未配置 AI_API_KEY -> 使用抽取式摘要降级模式")
        return _fallback(items)

    print(f"    [*] 第一遍：调用 {os.getenv('AI_MODEL') or 'deepseek-chat'} 分析 {len(items)} 条…")
    data = _call(SYS1, USER1.format(n=len(items), payload=_build_payload(items),
                                    cap=full_count()))
    if not data or "items" not in data:
        print("    [x] 第一遍返回无法解析 -> 降级")
        return _fallback(items)
    data["_mode"] = "ai"
    data.setdefault("overview", [])
    data.setdefault("deep_read_note", "")
    print(f"    [v] 第一遍完成：{len(data['items'])} 条结果，"
          f"精选 {sum(1 for i in data['items'] if i.get('deep_read'))} 条")
    return data


def translate_all(items: list[dict]) -> None:
    """第二遍：给精选条目就地补上 title_zh / standfirst / blocks / takeaway。"""
    picked = [it for it in items if it.get("deep_read")][:full_count()]
    if not picked:
        print("    [-] 没有精选条目，跳过翻译")
        return
    print(f"    [*] 第二遍：翻译 {len(picked)} 篇精选（目标每篇≥{MIN_NOTES}条边注）…")
    for it in picked:
        print(f"      -> {it['title'][:52]}")
        tr = translate_one(it)
        it.update(tr)
        flag = "v" if tr["translated"] else "-"
        warn = ""
        if tr["translated"] and tr["n_notes"] < MIN_NOTES:
            warn = f"  ⚠ 边注仅 {tr['n_notes']} 条（要求≥{MIN_NOTES}）"
        print(f"        [{flag}] {len(tr['blocks'])} 段 / {tr['n_notes']} 条边注{warn}")


def merge(items: list[dict], analysis: dict) -> list[dict]:
    """把第一遍结果按 uid 合回条目。"""
    by_uid = {a.get("uid"): a for a in analysis.get("items", [])}
    merged = []
    for it in items:
        a = by_uid.get(it["uid"], {})
        merged.append({**it,
                       "one_line": a.get("one_line", ""),
                       "why_matters": a.get("why_matters", ""),
                       "tags": a.get("tags", []) or [],
                       "action": a.get("action"),
                       # 时间戳统一裁成 YYYY-MM-DD，别把 ISO 全串糊在页面上
                       "published": (it.get("published") or "")[:10],
                       "deep_read": bool(a.get("deep_read"))})
    return merged
