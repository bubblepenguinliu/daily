"""渲染层：把分析结果套进 Jinja2 模板，产出可直接阅读的 HTML。

模板是方向 A「编辑部晨报」：660px 正文列 + 296px 右侧页边批注列。

两种模式：
  正常    —— items + analysis（含全文精译与页边批注）
  无新条目 —— no_news=True：只更新 latest.html，渲染一页状态页证明"任务跑过了"，
              并把时间戳刷新。**不占用归档文件名**，归档里不会塞进空日报。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _prev_digest(out_dir: Path, today_name: str) -> str | None:
    """找最近一期有内容的归档日报，供状态页回链。"""
    if not out_dir.exists():
        return None
    files = sorted((f for f in out_dir.glob("digest-*.html")), reverse=True)
    for f in files:
        if f.name != today_name:
            return f.name
    return files[0].name if files else None


def render(items: list[dict], analysis: dict, source_names: list[str],
           out_dir: str | Path, no_news: bool = False,
           newest: list[dict] | None = None) -> tuple[Path, dict]:
    """返回 (输出路径, 统计字典)。"""
    tpl = _env().get_template("digest.html.j2")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 精选 = 标了 deep_read 且真的有译文段落
    picked = [it for it in items if it.get("deep_read") and it.get("blocks")]
    picked_ids = {id(x) for x in picked}
    rest = [it for it in items if id(it) not in picked_ids]

    # 其余条目按来源分组，保持 config 顺序
    rest_groups: list[tuple[str, list[dict]]] = []
    for name in source_names:
        bucket = [it for it in rest if it["source_name"] == name]
        if bucket:
            rest_groups.append((name, bucket))

    note_total = sum(int(it.get("n_notes") or 0) for it in picked)
    stats = {
        "items": len(items),
        "picked": len(picked),
        "notes": note_total,
        "blocks": sum(len(it.get("blocks") or []) for it in picked),
        "translated": sum(1 for it in picked if it.get("translated")),
        "no_news": no_news,
    }

    now = datetime.now()
    today_name = f"digest-{now.strftime('%Y-%m-%d')}.html"
    html = tpl.render(
        date=now.strftime("%Y-%m-%d"),
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        scan_time=now.strftime("%H:%M"),
        total=len(items),
        picked=picked,
        rest_groups=rest_groups,
        note_total=note_total,
        items=items,
        analysis=analysis,
        overview=analysis.get("overview", []),
        mode=analysis.get("_mode", "fallback"),
        source_names=source_names,
        no_news=no_news,
        newest=newest or [],
        prev_digest=_prev_digest(out_dir, today_name),
    )

    latest = out_dir / "latest.html"
    if no_news:
        # 无新内容：只刷新 latest.html（归档不落空日报），时间戳会变，
        # 用户一眼能看出"任务跑了，只是今天没有新东西"。
        latest.write_text(html, encoding="utf-8")
        return latest, stats

    path = out_dir / today_name
    path.write_text(html, encoding="utf-8")
    latest.write_text(html, encoding="utf-8")
    return path, stats
