"""方向 C · 双栏阅读器 —— 非对称两栏 / 粘性侧栏索引 / 冷色亮场。

骨架：左侧常驻侧栏（刊头+速览索引+来源图例+统计）‖ 右侧信息流（按来源分组，细线分隔）
气质：现代、好读、有产品感。用「索引→内容」的对应关系替代卡片堆叠。
反 slop：**不用左色条卡片**（典型 slop），改用品类分隔线 + 精选条目浅底 + 侧栏锚点高亮。
"""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "sample_data.json").read_text(encoding="utf-8"))
E = lambda s: html.escape(str(s or ""))

deep = [i for i in D["items"] if i["deep_read"]]
rest = [i for i in D["items"] if not i["deep_read"]]

ov = "".join(
    f'<li><a href="#d{n+1}"><span class="no">{n+1:02d}</span><span>{E(x)}</span></a></li>'
    for n, x in enumerate(D["overview"]))

legend = "".join(
    f'<li><span class="dot" style="--c:hsl({(n*67)%360} 42% 46%)"></span>{E(s)}</li>'
    for n, s in enumerate(D["source_names"]))


def item(it: dict, i: int) -> str:
    tags = "".join(f'<span class="t">{E(t)}</span>' for t in it.get("tags", []))
    why = (f'<p class="why">{E(it["why_matters"])}</p>' if it.get("why_matters") else "")
    act = (f'<p class="act"><span class="k">下一步</span>{E(it["action"])}</p>'
           if it.get("action") else "")
    return f"""
      <article class="it {'pick' if it['deep_read'] else ''}" id="d{i}">
        <h3><a href="{E(it['link'])}" target="_blank" rel="noopener">{E(it['title'])}</a></h3>
        <p class="one">{E(it.get('one_line'))}</p>
        {why}{act}
        <div class="ft">{tags}<span class="src">{E(it['source_name'])}</span><span class="dt">{E(it.get('published'))}</span></div>
      </article>"""


n = 0
pick_html = ""
for it in deep:
    n += 1
    pick_html += item(it, n)
pick_ids = {}
for it in deep:
    pick_ids[it["title"]] = True

groups = ""
src_order = [s for s in D["source_names"]]
buckets: dict[str, list] = {}
for it in rest:
    buckets.setdefault(it["source_name"], []).append(it)
for src in src_order:
    lst = buckets.get(src)
    if not lst:
        continue
    rows = ""
    for it in lst:
        n += 1
        rows += item(it, n)
    groups += f'<section class="grp"><div class="gn">{E(src)}<span>{len(lst)} 条</span></div>{rows}</section>'

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>技术情报日报 · {E(D['date'])}</title>
<style>
  :root {{
    --bg:#eef1f5; --card:#ffffff; --ink:#0f1419; --muted:#5b6675; --line:#dbe1e8;
    --accent:#0e6b64; --accent-2:#c2410c; --tint:#f0f8f7;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:"Microsoft YaHei","PingFang SC",system-ui,-apple-system,"Segoe UI",sans-serif;
    font-size:14.5px; line-height:1.75; text-wrap:pretty;
  }}
  #bar {{ position:fixed; top:0; left:0; height:2px; background:var(--accent);
          width:0; z-index:99; transition:width .12s linear; }}

  .shell {{ max-width:1120px; margin:0 auto; padding:34px 26px 90px;
            display:grid; grid-template-columns:238px 1fr; gap:44px; align-items:start; }}

  /* ---- 侧栏 ---- */
  aside {{ position:sticky; top:34px; }}
  .brand {{ font-size:11px; letter-spacing:.34em; color:var(--accent); font-weight:600; }}
  .brand-l {{ font-family:Georgia,"Songti SC",serif; font-size:23px; letter-spacing:.06em;
              margin:8px 0 3px; font-weight:600; }}
  .brand-d {{ font-size:12px; color:var(--muted); font-variant-numeric:tabular-nums; }}
  .stats {{ display:flex; gap:8px; margin:18px 0 24px; }}
  .st {{ flex:1; background:var(--card); border:1px solid var(--line); border-radius:8px;
         padding:9px 10px; }}
  .st b {{ display:block; font-size:18px; font-variant-numeric:tabular-nums; line-height:1.2; }}
  .st span {{ font-size:10.5px; color:var(--muted); letter-spacing:.08em; }}
  .st.hi b {{ color:var(--accent-2); }}

  .sect {{ font-size:10.5px; letter-spacing:.26em; color:var(--muted);
           margin:0 0 10px; padding-bottom:6px; border-bottom:1px solid var(--line); }}
  ul.idx {{ list-style:none; margin:0 0 26px; padding:0; }}
  ul.idx li a {{ display:flex; gap:9px; padding:7px 8px 7px 0; text-decoration:none;
                 color:var(--ink); font-size:13px; line-height:1.5; border-radius:6px; }}
  ul.idx li a:hover {{ background:#e6ebf1; }}
  ul.idx .no {{ color:var(--accent); font-variant-numeric:tabular-nums; font-size:11.5px;
                flex:0 0 18px; padding-top:1px; }}
  ul.leg {{ list-style:none; margin:0; padding:0; }}
  ul.leg li {{ display:flex; align-items:center; gap:9px; font-size:12.5px; color:var(--muted);
               padding:5px 0; }}
  ul.leg .dot {{ width:7px; height:7px; border-radius:50%; background:var(--c); flex:0 0 7px; }}

  /* ---- 主区 ---- */
  header.top {{ margin-bottom:26px; }}
  h1 {{ font-size:26px; margin:0 0 6px; letter-spacing:.02em; }}
  .sub {{ color:var(--muted); font-size:13px; }}

  .pickwrap {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
               padding:6px 20px 12px; margin-bottom:34px; }}
  .pickwrap > .sect {{ margin-top:16px; }}
  article.it {{ padding:17px 0; border-bottom:1px solid var(--line); }}
  article.it:last-child {{ border-bottom:0; }}
  article.pick {{ padding:17px 0; }}
  article.pick h3 {{ font-size:18.5px; }}
  h3 {{ font-size:15.5px; margin:0 0 7px; line-height:1.5; font-weight:600; }}
  h3 a {{ color:var(--ink); text-decoration:none; }}
  h3 a:hover {{ color:var(--accent); }}
  .one {{ margin:0; color:#2c3540; }}
  .why {{ margin:10px 0 0; background:var(--tint); border-radius:8px; padding:9px 13px;
          font-size:13.5px; color:#204a47; }}
  .act {{ margin:9px 0 0; font-size:13.5px; color:#7c2d12; }}
  .act .k {{ display:inline-block; font-size:10.5px; letter-spacing:.12em; color:var(--accent);
             margin-right:8px; }}
  .ft {{ display:flex; gap:8px; align-items:center; margin-top:11px; flex-wrap:wrap; }}
  .t {{ font-size:11.5px; color:var(--muted); background:#e9eef3; border-radius:5px; padding:1px 8px; }}
  .src {{ font-size:11.5px; color:var(--muted); padding-left:9px; border-left:1px solid var(--line); }}
  .dt {{ font-size:11.5px; color:#93a0ad; margin-left:auto; font-variant-numeric:tabular-nums; }}

  .grp {{ margin-top:30px; }}
  .gn {{ display:flex; justify-content:space-between; align-items:baseline;
         font-size:12.5px; font-weight:600; color:var(--ink);
         border-bottom:2px solid var(--ink); padding-bottom:7px; }}
  .gn span {{ font-weight:400; color:var(--muted); font-size:11.5px; }}

  footer {{ grid-column:1 / -1; margin-top:40px; padding-top:16px;
            border-top:1px solid var(--line); color:var(--muted); font-size:12px;
            display:flex; justify-content:space-between; }}
  @media (max-width:820px) {{ .shell {{ grid-template-columns:1fr; gap:26px; }}
                              aside {{ position:static; }} }}
</style></head>
<body>
<div id="bar"></div>
<div class="shell">

  <aside>
    <div class="brand">DAILY TECH DIGEST</div>
    <div class="brand-l">技术情报日报</div>
    <div class="brand-d">{E(D['date'])}</div>
    <div class="stats">
      <div class="st"><b>{len(D['items'])}</b><span>收录</span></div>
      <div class="st hi"><b>{len(deep)}</b><span>精选</span></div>
      <div class="st"><b>{len(D['source_names'])}</b><span>来源</span></div>
    </div>
    <div class="sect">今日速览</div>
    <ul class="idx">{ov}</ul>
    <div class="sect">来源</div>
    <ul class="leg">{legend}</ul>
  </aside>

  <main>
    <header class="top">
      <h1>今天，这 {len(D['items'])} 条值得你知道</h1>
      <div class="sub">{E(D.get('deep_read_note') or '按信息密度排序，精选放在最前')}</div>
    </header>

    <div class="pickwrap">
      <div class="sect">精选</div>
      {pick_html}
    </div>

    {groups}

    <footer>
      <span>tech-daily-digest · 自动生成</span>
      <span>每日 09:00 CST</span>
    </footer>
  </main>
</div>
<script>
  var bar = document.getElementById('bar');
  function onScroll() {{
    var h = document.documentElement;
    var p = h.scrollTop / (h.scrollHeight - h.clientHeight || 1);
    bar.style.width = Math.min(100, p * 100) + '%';
  }}
  addEventListener('scroll', onScroll, {{ passive: true }});
  onScroll();
</script>
</body></html>"""

(HERE / "C-reader.html").write_text(HTML, encoding="utf-8")
print(f"[v] C-reader.html  {len(HTML):,} bytes")
