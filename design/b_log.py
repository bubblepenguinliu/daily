"""方向 B · 信号日志 —— 暖色暗场 / 等宽 / 全宽密集行。

骨架：状态栏（DATE SOURCES ITEMS MODE）→ 全宽行（左侧时间槽 + 来源标签 + 标题 + 价值行）
气质：冷、快、工程师的。像 less 翻一份日志。
反 slop：**刻意避开** GitHub-dark 那套「#0D1117 均匀深蓝 + 青紫霓虹 glow」——
        这里用的是油灯色暖黑 + 琥珀单色，有作者意图，不是默认暗色模板。
"""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "sample_data.json").read_text(encoding="utf-8"))
E = lambda s: html.escape(str(s or ""))

ABBR = {"阮一峰 · 科技爱好者周刊": "RYF", "Simon Willison's Weblog": "SW",
        "ByteByteGo": "BBG", "Import AI（Jack Clark）": "IMP"}


def row(it: dict) -> str:
    star = '<span class="star">★</span>' if it["deep_read"] else '<span class="dot">·</span>'
    tags = " ".join(f'<span class="tag">#{E(t)}</span>' for t in it.get("tags", []))
    why = (f'<div class="why"><span class="arrow">↳</span>{E(it["why_matters"])}</div>'
           if it.get("why_matters") else "")
    act = (f'<div class="act"><span class="k">NEXT</span>{E(it["action"])}</div>'
           if it.get("action") else "")
    cls = "row deep" if it["deep_read"] else "row"
    return f"""
  <div class="{cls}">
    <div class="gut"><span class="dt">{E(it.get('published',''))[5:]}</span><span class="ab">{ABBR.get(it['source_name'],'???')}</span></div>
    <div class="body">
      <div class="ttl">{star}<a href="{E(it['link'])}" target="_blank" rel="noopener">{E(it['title'])}</a></div>
      <div class="one">{E(it.get('one_line'))}</div>
      {why}{act}
      <div class="meta">{tags}<span class="src">{E(it['source_name'])}</span></div>
    </div>
  </div>"""


deep = [i for i in D["items"] if i["deep_read"]]
rest = [i for i in D["items"] if not i["deep_read"]]
ov = "".join(f'<div class="ovrow"><span class="i">{n+1:02d}</span><span>{E(x)}</span></div>'
             for n, x in enumerate(D["overview"]))
deep_html = "".join(row(i) for i in deep)
rest_html = "".join(row(i) for i in rest)

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>daily.log · {E(D['date'])}</title>
<style>
  :root {{
    --bg:#16130f; --panel:#1c1813; --line:#2e2820; --line2:#403728;
    --ink:#e9e1d4; --dim:#a2988a; --faint:#6d6459;
    --amber:#d98c2b; --amber-soft:#3a2a15; --green:#7fae6b;
  }}
  * {{ box-sizing:border-box; }}
  html {{ background:var(--bg); }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:"Cascadia Mono","JetBrains Mono",Consolas,"Microsoft YaHei",monospace;
    font-size:13.5px; line-height:1.68; letter-spacing:.005em;
    background-image:radial-gradient(ellipse 90% 50% at 50% -8%, rgba(217,140,43,.10), transparent 70%);
  }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:0 22px 84px; }}

  /* ---- 状态栏 ---- */
  header {{
    position:sticky; top:0; z-index:9; background:rgba(22,19,15,.94);
    backdrop-filter:blur(8px); border-bottom:1px solid var(--line2);
    margin:0 -22px; padding:14px 22px 12px;
  }}
  .cmd {{ font-size:12.5px; color:var(--dim); }}
  .cmd .p {{ color:var(--amber); }}
  .cmd .c {{ color:var(--green); }}
  .kv {{ display:flex; gap:22px; flex-wrap:wrap; margin-top:8px; font-size:11.5px;
         letter-spacing:.1em; color:var(--faint); }}
  .kv b {{ color:var(--ink); font-weight:600; }}
  .kv .hl {{ color:var(--amber); }}

  /* ---- 提要 ---- */
  .blk {{ margin-top:30px; }}
  .h {{ font-size:11px; letter-spacing:.3em; color:var(--amber);
        border-bottom:1px solid var(--line2); padding-bottom:7px; margin-bottom:12px; }}
  .ovrow {{ display:flex; gap:14px; padding:6px 0; border-bottom:1px solid var(--line); color:var(--ink); }}
  .ovrow:last-child {{ border-bottom:0; }}
  .ovrow .i {{ color:var(--amber); flex:0 0 22px; }}

  /* ---- 行 ---- */
  .row {{ display:flex; gap:16px; padding:15px 0; border-bottom:1px solid var(--line); }}
  .row:hover {{ background:linear-gradient(90deg, rgba(217,140,43,.055), transparent 62%); }}
  .row.deep {{ background:var(--panel); margin:0 -14px; padding:17px 14px;
               border-left:2px solid var(--amber); border-bottom-color:var(--line2); }}
  .gut {{ flex:0 0 62px; padding-top:2px; text-align:right; }}
  .dt {{ display:block; color:var(--faint); font-size:11.5px; font-variant-numeric:tabular-nums; }}
  .ab {{ display:block; margin-top:4px; font-size:10.5px; letter-spacing:.14em; color:var(--amber); }}
  .body {{ flex:1; min-width:0; }}
  .ttl {{ font-size:15px; line-height:1.5; }}
  .row.deep .ttl {{ font-size:17px; }}
  .star {{ color:var(--amber); margin-right:7px; }}
  .dot {{ color:var(--faint); margin-right:7px; }}
  .ttl a {{ color:var(--ink); text-decoration:none; border-bottom:1px solid transparent; }}
  .ttl a:hover {{ color:var(--amber); border-bottom-color:var(--amber); }}
  .one {{ color:var(--dim); margin-top:5px; }}
  .why {{ margin-top:9px; padding:8px 12px; background:rgba(217,140,43,.07);
          border-left:2px solid var(--amber-soft); color:#d5cbb9; font-size:13px; }}
  .why .arrow {{ color:var(--amber); margin-right:8px; }}
  .act {{ margin-top:7px; font-size:12.5px; color:#a9c79b; }}
  .act .k {{ color:var(--green); font-size:10.5px; letter-spacing:.16em; margin-right:9px; }}
  .meta {{ margin-top:9px; display:flex; gap:10px; flex-wrap:wrap; align-items:center; font-size:11.5px; }}
  .tag {{ color:var(--faint); }}
  .src {{ margin-left:auto; color:var(--faint); letter-spacing:.08em; }}

  footer {{ margin-top:44px; padding-top:14px; border-top:1px solid var(--line2);
            font-size:11.5px; color:var(--faint); display:flex; justify-content:space-between; }}
</style></head>
<body><div class="wrap">

  <header>
    <div class="cmd"><span class="p">digest@local</span>:<span class="c">~</span>$ tail -f today.log</div>
    <div class="kv">
      <span>DATE <b>{E(D['date'])}</b></span>
      <span>SOURCES <b>{len(D['source_names'])}</b></span>
      <span>ITEMS <b>{len(D['items'])}</b></span>
      <span>PICKED <b class="hl">{len(deep)}</b></span>
      <span>MODE <b class="hl">AI</b></span>
    </div>
  </header>

  <div class="blk">
    <div class="h">SUMMARY</div>
    {ov}
  </div>

  <div class="blk">
    <div class="h">★ PICKED {len(deep)}{(' — ' + E(D['deep_read_note'])) if D.get('deep_read_note') else ''}</div>
    {deep_html}
  </div>

  <div class="blk">
    <div class="h">ALL ENTRIES</div>
    {rest_html}
  </div>

  <footer>
    <span>tech-daily-digest · auto-generated</span>
    <span>{E(D['date'])} 09:00 CST</span>
  </footer>
</div></body></html>"""

(HERE / "B-log.html").write_text(HTML, encoding="utf-8")
print(f"[v] B-log.html  {len(HTML):,} bytes")
