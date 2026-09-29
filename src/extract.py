"""正文抽取层：把 RSS 摘要升级为文章正文。

为什么需要这一层：
    RSS 里只有一两句摘要，拿它做"翻译展示"只能翻译摘要，不是文章。
    要做真正的翻译 + 边注，必须先拿到文章正文。

做法：
    curl_cffi 取页面（伪装 Chrome，过 Cloudflare）→ trafilatura 抽正文 →
    清洗（去赞助段落、折叠空白）→ 切成段落 → 按 BODY_LIMIT 截断。

失败不致命：任何站点抓不到正文就返回空，该条自动退回摘要形态，不阻塞整期。
"""
from __future__ import annotations

import os
import re

from curl_cffi import requests as cr

TIMEOUT = 45
UA_IMPERSONATE = "chrome"

# 明显的推广/样板段落，抽正文时容易混进来，直接丢掉
SPONSOR_PAT = re.compile(
    r"(sponsored|this post is sponsored|advertisement|"
    r"test your .{0,40} without production|"
    r"subscribe now|upgrade to paid|"
    r"^\s*(share|tweet|discuss on hacker news)\s*$)",
    re.I,
)

# 正文里常见的收尾样板
TAIL_PAT = re.compile(
    r"^(thanks for reading|subscribe|share this post|discuss on hacker news|"
    r"leave a comment|the post .{0,80} appeared first on)",
    re.I,
)

# Cloudflare 邮件混淆产物 / 纯排版残留
JUNK_PAT = re.compile(r"\[email\s*protected\]|\[email&#160;protected\]", re.I)

# 一个 block 的上限：防止周刊类长列表把页面撑到失控
MAX_PARAS = 80


def _proxies() -> dict | None:
    hp = os.getenv("HTTP_PROXY") or ""
    sp = os.getenv("HTTPS_PROXY") or ""
    if hp or sp:
        return {"http": hp or sp, "https": sp or hp}
    return None


def _fetch(url: str) -> str | None:
    try:
        r = cr.get(url, impersonate=UA_IMPERSONATE, timeout=TIMEOUT,
                   proxies=_proxies(), allow_redirects=True)
        if r.status_code != 200:
            return None
        return r.text
    except Exception:  # noqa: BLE001
        return None


def _extract_text(html: str) -> str:
    try:
        import trafilatura

        txt = trafilatura.extract(
            html, include_comments=False, include_tables=False,
            favor_precision=True, deduplicate=True,
        )
        if txt and len(txt.strip()) > 200:
            return txt
    except Exception:  # noqa: BLE001
        pass

    # 兜底：粗暴去标签。质量差，但保证有东西可用
    body = re.sub(r"(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", html)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = re.sub(r"&nbsp;?", " ", body)
    body = re.sub(r"&amp;", "&", body)
    body = re.sub(r"&[a-z]+;", " ", body)
    return re.sub(r"[ \t]{2,}", " ", body)


def clean_and_split(text: str, limit: int = 6000, max_paras: int = MAX_PARAS) -> tuple[str, list[str]]:
    """返回 (完整原文, 段落列表)。"""
    text = JUNK_PAT.sub("", (text or "")).replace("\r", "")
    lines: list[str] = []
    for raw in text.split("\n"):
        ln = raw.strip()
        if not ln or len(ln) < 2:
            continue
        if SPONSOR_PAT.search(ln) or TAIL_PAT.match(ln):
            continue
        # 丢掉"分享/订阅"类超短样板行
        if len(ln) < 28 and re.search(r"(share|subscribe|newsletter|follow)", ln, re.I):
            continue
        lines.append(ln)

    body = "\n\n".join(lines)
    body = re.sub(r"[ \t]{2,}", " ", body).strip()
    if len(body) > limit:
        body = body[:limit].rsplit("\n", 1)[0] + "\n\n…（原文过长，此处截断）"

    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if len(paras) > max_paras:
        paras = paras[:max_paras]
        body = "\n\n".join(paras) + "\n\n…（段落过多，此处截断）"
    return body, paras


def fetch_article(url: str, limit: int = 6000) -> tuple[str, bool]:
    """抓一篇文章的正文。返回 (正文, 是否成功)。"""
    if not url:
        return "", False
    html = _fetch(url)
    if not html:
        return "", False
    raw = _extract_text(html)
    body, paras = clean_and_split(raw, limit=limit)
    # 正文太短基本是抓失败（拿到的多半是导航/样板）
    if len(body) < 400:
        return "", False
    return body, True


def enrich(items: list[dict], limit: int = 6000, only_uid: set[str] | None = None) -> int:
    """就地给条目补上 body / paras 字段。返回成功条数。"""
    ok = 0
    for it in items:
        if only_uid is not None and it["uid"] not in only_uid:
            it.setdefault("body", "")
            it.setdefault("paras", [])
            continue
        body, good = fetch_article(it.get("link", ""), limit=limit)
        it["body"] = body
        it["paras"] = [p for p in body.split("\n\n") if p.strip()] if good else []
        if good:
            ok += 1
            print(f"        [v] {len(body):5d} 字符  {it['title'][:50]}")
        else:
            print(f"        [-] 正文抓取失败，退回摘要  {it['title'][:50]}")
    return ok
