"""渲染层：把分析结果套进 Jinja2 模板，产出可直接阅读的 HTML。

模板是方向 A「编辑部晨报」：660px 正文列 + 296px 右侧页边批注列。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env


def render(items: list[dict], analysis: dict, source_names: list[str],
           out_dir: str | Path) -> tuple[Path, dict]:
    """返回 (输出路径, 统计字典)。"""
    tpl = _env().get_template("digest.html.j2")

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
    }

    now = datetime.now()
    html = tpl.render(
        date=now.strftime("%Y-%m-%d"),
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        total=len(items),
        picked=picked,
        rest_groups=rest_groups,
        note_total=note_total,
        items=items,
        analysis=analysis,
        overview=analysis.get("overview", []),
        mode=analysis.get("_mode", "fallback"),
        source_names=source_names,
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"digest-{now.strftime('%Y-%m-%d')}.html"
    path.write_text(html, encoding="utf-8")
    (out_dir / "latest.html").write_text(html, encoding="utf-8")
    return path, stats
