"""渲染层：把分析结果套进 Jinja2 模板，产出可直接阅读的 HTML。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def render(items: list[dict], analysis: dict, source_names: list[str], out_dir: str | Path) -> Path:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("digest.html.j2")

    # 按来源分组，保持 config 里的顺序
    groups: list[tuple[str, list[dict]]] = []
    for name in source_names:
        bucket = [it for it in items if it["source_name"] == name]
        if bucket:
            groups.append((name, bucket))

    now = datetime.now()
    html = tpl.render(
        date=now.strftime("%Y-%m-%d"),
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        total=len(items),
        groups=groups,
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
    latest = out_dir / "latest.html"
    latest.write_text(html, encoding="utf-8")
    return path
