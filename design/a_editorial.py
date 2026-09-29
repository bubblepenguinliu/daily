"""方向 A · 编辑部晨报 —— 衬线 / 报纸版式 / 单栏。

骨架：报头（双线+刊号）→ 提要（编号）→ 头条（大字号衬线）→ 分类条目（细分隔线）
气质：有分量、克制、像一本正经的刊物。反 slop：无渐变、无卡片、无 emoji、无 icon。
"""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "sample_data.json").read_text(encoding="utf-8"))
E = lambda s: html.escape(str(s or ""))


def esc(n: int) -> str:
    cn = "零一二三四五六七八九"
    if n < 10:
        return cn[n]
    if n < 20:
        return "十" + (cn[n - 10] if n > 10 else "")
    return cn[n // 10] + "十" + (cn[n % 10] if n % 10 else "")


def entry(it: dict, idx: int) -> str:
    tags = "".join(f'<span class="t">{E(t)}</span>' for t in it.get("tags", []))
    act = (f'<p class="act"><span>下一步</span>{E(it["action"])}</p>' if it.get("action") else "")
    why = (f'<p class="why">{E(it["why_matters"])}</p>' if it.get("why_matters") else "")
    return f"""
    <article class="entry">
      <div class="enum">{idx:02d}</div>
      <h3><a href="{E(it['link'])}" target="_blank" rel="noopener">{E(it['title'])}</a></h3>
      <p class="one">{E(it.get('one_line'))}</p>
      {why}{act}
      <div class="foot"><span class="src">{E(it['source_name'])}</span>{tags}<span class="dt">{E(it.get('published'))}</span></div>
    </article>"""


deep = [i for i in D["items"] if i["deep_read"]]
rest = [i for i in D["items"] if not i["deep_read"]]
ov = "".join(f"<li>{E(x)}</li>" for x in D["overview"])
deep_html = "".join(entry(i, n + 1) for n, i in enumerate(deep))
rest_by_src: dict[str, list] = {}
for i in rest:
    rest_by_src.setdefault(i["source_name"], []).append(i)
rest_html = ""
n = len(deep)
for src, lst in rest_by_src.items():
    rows = ""
    for i in lst:
        n += 1
        rows += entry(i, n)
    rest_html += f'<div class="srcblock"><div class="srcname">{E(src)}</div>{rows}</div>'

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>技术情报日报 · {E(D['date'])}</title>
<style>
  :root {{
    --paper:#faf7f2; --ink:#1c1a17; --muted:#6b6357; --rule:#d8d0c3;
    --accent:#9b2c20; --soft:#f2ece2;
  }}
  * {{ box-sizing:border-box; }}
  html {{ background:var(--paper); }}
  body {{
    margin:0; color:var(--ink); background:var(--paper);
    font-family:Georgia,"Source Han Serif SC","Noto Serif SC",SimSun,"Songti SC",serif;
    font-size:15.5px; line-height:1.82;
    background-image:radial-gradient(circle at 18% 10%, rgba(155,44,32,.035), transparent 42%);
  }}
  .wrap {{ max-width:720px; margin:0 auto; padding:44px 26px 96px; }}

  /* ---- 报头 ---- */
  .masthead {{ text-align:center; padding-bottom:14px; border-bottom:1px solid var(--ink); }}
  .kicker {{ font-size:11.5px; letter-spacing:.42em; color:var(--muted);
             text-transform:uppercase; font-family:"Microsoft YaHei",sans-serif; }}
  h1 {{ font-size:44px; margin:12px 0 4px; letter-spacing:.14em; font-weight:600; }}
  .masthead .sub {{ font-size:13px; color:var(--muted); letter-spacing:.06em; }}
  .rule2 {{ border-top:3px solid var(--ink); border-bottom:1px solid var(--ink);
            height:4px; margin-top:8px; }}

  .lede {{ display:flex; justify-content:space-between; align-items:baseline;
           font-size:12.5px; color:var(--muted); padding:12px 2px 0;
           font-family:"Microsoft YaHei",sans-serif; letter-spacing:.04em; }}
  .lede b {{ color:var(--accent); font-weight:600; }}

  /* ---- 提要 ---- */
  .digest {{ margin:34px 0 6px; }}
  .sec {{ font-family:"Microsoft YaHei",sans-serif; font-size:12.5px; letter-spacing:.3em;
          color:var(--accent); border-bottom:1px solid var(--rule); padding-bottom:8px;
          margin-bottom:16px; }}
  ul.ov {{ list-style:none; margin:0; padding:0; counter-reset:o; }}
  ul.ov li {{ counter-increment:o; position:relative; padding:7px 0 7px 40px;
              border-bottom:1px dotted var(--rule); }}
  ul.ov li:last-child {{ border-bottom:0; }}
  ul.ov li::before {{ content:counter(o,decimal-leading-zero); position:absolute; left:0; top:8px;
                      font-size:11.5px; color:var(--accent); letter-spacing:.06em;
                      font-family:Georgia,serif; }}

  /* ---- 头条 ---- */
  .deepsec {{ margin-top:46px; }}
  .deepsec .sec {{ color:var(--ink); border-bottom:2px solid var(--ink); }}
  .note {{ font-size:13px; color:var(--muted); font-style:italic; margin:-6px 0 22px; }}

  article.entry {{ padding:22px 0; border-bottom:1px solid var(--rule); position:relative; }}
  article.entry:last-child {{ border-bottom:0; }}
  .deepsec article.entry {{ border-bottom:1px solid var(--ink); }}
  .deepsec article.entry:last-child {{ border-bottom:2px solid var(--ink); }}
  .enum {{ position:absolute; left:-2px; top:24px; font-size:11px; color:var(--accent);
           font-family:Georgia,serif; letter-spacing:.04em; }}
  h3 {{ font-size:20.5px; line-height:1.5; margin:0 0 10px; font-weight:600; }}
  .deepsec h3 {{ font-size:24px; line-height:1.42; }}
  h3 a {{ color:var(--ink); text-decoration:none; }}
  h3 a:hover {{ color:var(--accent); }}
  .one {{ margin:0 0 10px; }}
  .deepsec .one {{ font-size:17px; }}
  .why {{ margin:10px 0; padding-left:16px; border-left:2px solid var(--accent);
          color:#3b352c; font-size:14.6px; }}
  .act {{ margin:10px 0; font-size:14.5px; color:#2c4a2e; }}
  .act span {{ display:inline-block; font-family:"Microsoft YaHei",sans-serif; font-size:11.5px;
               letter-spacing:.14em; color:#3f6b45; margin-right:9px; }}
  .foot {{ display:flex; align-items:center; gap:10px; margin-top:14px; flex-wrap:wrap;
           font-family:"Microsoft YaHei",sans-serif; font-size:11.5px; }}
  .src {{ letter-spacing:.1em; color:var(--muted); }}
  .t {{ color:var(--accent); border:1px solid var(--rule); border-radius:2px;
        padding:1px 7px; letter-spacing:.04em; }}
  .dt {{ margin-left:auto; color:#9a9084; font-variant-numeric:tabular-nums; }}

  .srcblock {{ margin-top:40px; }}
  .srcname {{ font-family:"Microsoft YaHei",sans-serif; font-size:12px; letter-spacing:.26em;
              color:var(--muted); border-bottom:1px solid var(--ink); padding-bottom:7px; }}

  footer {{ margin-top:52px; padding-top:16px; border-top:3px double var(--ink);
            font-family:"Microsoft YaHei",sans-serif; font-size:11.5px; color:var(--muted);
            display:flex; justify-content:space-between; letter-spacing:.05em; }}
</style></head>
<body><div class="wrap">

  <header class="masthead">
    <div class="kicker">Daily Tech Digest</div>
    <h1>技术情报日报</h1>
    <div class="sub">{E(D['date'])} · 第 {len(D['items'])} 号</div>
    <div class="rule2"></div>
    <div class="lede">
      <span>本期收录 <b>{len(D['items'])}</b> 条 · 精选 <b>{len(deep)}</b> 条</span>
      <span>来源 {' · '.join(E(s) for s in D['source_names'][:2])} 等 {len(D['source_names'])} 家</span>
    </div>
  </header>

  <section class="digest">
    <div class="sec">今 日 提 要</div>
    <ul class="ov">{ov}</ul>
  </section>

  <section class="deepsec">
    <div class="sec">值 得 细 读</div>
    {f'<p class="note">{E(D["deep_read_note"])}</p>' if D.get('deep_read_note') else ''}
    {deep_html}
  </section>

  <section class="deepsec" style="margin-top:52px">
    <div class="sec">其 余 条 目</div>
    {rest_html}
  </section>

  <footer>
    <span>本刊由 tech-daily-digest 自动编纂</span>
    <span>每日 09:00 出刊</span>
  </footer>
</div></body></html>"""

(HERE / "A-editorial.html").write_text(HTML, encoding="utf-8")
print(f"[v] A-editorial.html  {len(HTML):,} bytes")
