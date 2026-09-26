"""抓取层：curl_cffi 伪装浏览器指纹，按 url -> fallbacks 顺序尝试，第一个成功即返回。

为什么用 curl_cffi 而不是 requests：
    阮一峰 / Substack 等站点挂了 Cloudflare，普通 requests 会拿到 403
    "Just a moment..."（JS 挑战页）。curl_cffi 能伪装 Chrome 的 TLS/JA3
    指纹，从而在大部分情况下直接拿到正文。
"""
from __future__ import annotations

import hashlib
import html
import os
import re
from datetime import datetime, timezone

from curl_cffi import requests as cr
from feedparser import parse

IMPERSONATE = "chrome"

HEADERS = {
    "Accept": "application/atom+xml,application/rss+xml,application/xml;q=0.9,text/html;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Cache-Control": "no-cache",
}


def _proxies() -> dict | None:
    """从环境变量读代理；为空则不走代理（例如在 GitHub Actions 上）。"""
    hp = os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or ""
    sp = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or ""
    if not hp and not sp:
        return None
    return {"http": hp or sp, "https": sp or hp}


def strip_html(raw: str) -> str:
    """把 RSS 里带的 HTML 正文压成纯文本。"""
    if not raw:
        return ""
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(p|div|li|h[1-6])>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _entry_text(e) -> str:
    for key in ("content", "summary_detail", "summary", "description"):
        v = e.get(key)
        if isinstance(v, list) and v:
            v = v[0].get("value")
        if isinstance(v, str) and v.strip():
            return strip_html(v)
    return ""


def _entry_time(e) -> str:
    for key in ("published_parsed", "updated_parsed"):
        t = e.get(key)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).astimezone().isoformat(timespec="seconds")
            except Exception:
                pass
    return ""


def fetch_source(src: dict) -> tuple[list[dict], str]:
    """返回 (items, 实际使用的入口)。items 为空表示全部入口都失败。"""
    urls = [src["url"]] + src.get("fallbacks", [])
    errors: list[str] = []

    for url in urls:
        try:
            r = cr.get(url, impersonate=IMPERSONATE, headers=HEADERS,
                       timeout=45, proxies=_proxies())
            if r.status_code != 200:
                errors.append(f"HTTP {r.status_code} @ {url}")
                continue

            d = parse(r.content)
            if not d.entries:
                errors.append(f"0 entries @ {url}")
                continue

            items = []
            for e in d.entries:
                link = (e.get("link") or "").strip()
                title = strip_html(e.get("title") or "").strip()
                if not title:
                    continue
                text = _entry_text(e)
                items.append({
                    "source_id": src["id"],
                    "source_name": src["name"],
                    "lang": src.get("lang", "en"),
                    "title": title,
                    "link": link,
                    "published": _entry_time(e),
                    "text": text,
                    "uid": hashlib.sha1((link or title).encode("utf-8")).hexdigest()[:16],
                })
            return items, url

        except Exception as ex:  # noqa: BLE001
            errors.append(f"{type(ex).__name__}: {str(ex)[:110]}")

    print(f"    [x] {src['name']} 全部入口失败 -> {' | '.join(errors)}")
    return [], ""


def fetch_all(config: dict) -> tuple[list[dict], dict[str, str]]:
    """抓取配置里的全部源。返回 (所有条目, {source_id: 实际入口})。"""
    all_items: list[dict] = []
    used: dict[str, str] = {}
    for src in config["sources"]:
        items, url = fetch_source(src)
        if items:
            used[src["id"]] = url
            print(f"    [v] {src['name']}: {len(items)} 条  <-  {url}")
            all_items.extend(items)
        else:
            used[src["id"]] = ""
    return all_items, used
