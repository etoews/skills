#!/usr/bin/env python3
"""
build_trends.py - Track each store's basket total over time.

Reads the totals ledger JSON written by build_report.py (one entry per
timestamped comparison run) and emits a single self-contained HTML report with
an SVG line chart of every store's basket total across runs, summary cards, a
"cheapest league table", and a run-by-run table.

Usage:
    python build_trends.py <totals-history.json> [-o output.html] [--title "..."]

If -o is omitted the file is written next to the ledger as
    totals-over-time-<YYYYMMDD-HHMMSS>.html

LEDGER SCHEMA (produced by build_report.py)
-------------------------------------------
{
  "history": [
    {
      "timestamp": "2026-06-18 18:54:27 NZST",
      "source_store": "Woolworths",
      "cheapest": "PAK'nSAVE",
      "stores": {
        "Woolworths": {"key":"ww","subtotal":239.20,"fees":0,"total":239.20,"items":41},
        "New World":  {"key":"nw","subtotal":253.19,"fees":1.50,"total":254.69,"items":41},
        "PAK'nSAVE":  {"key":"pak","subtotal":230.95,"fees":1.00,"total":231.95,"items":40}
      }
    },
    ...
  ]
}
Each run can list a different set of stores; the chart handles stores that come
and go (gaps in a line).
"""

import argparse
import json
import sys
import datetime
from pathlib import Path
from html import escape


def load_history(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        sys.exit(f"error: could not read ledger {path}: {e}")
    runs = data.get("history") if isinstance(data, dict) else None
    if not isinstance(runs, list) or not runs:
        sys.exit("error: ledger has no 'history' entries yet — run build_report.py first")
    return data


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en-NZ">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root{--ink:#1d2126;--muted:#6b7280;--line:#e7e9ee;--bg:#f6f7f9;--card:#fff;--cheap:#0f7a3d;--cheap-soft:#eaf7ef;--up:#b8530a;--down:#0f7a3d;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.45;font-size:14px;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1100px;margin:0 auto;padding:28px 20px 80px}
  h1{font-size:24px;margin:0 0 4px;letter-spacing:-.3px}
  .sub{color:var(--muted);font-size:13.5px}
  .stamp{display:inline-block;margin-top:9px;font-size:12px;color:var(--muted);background:var(--card);border:1px solid var(--line);border-radius:999px;padding:4px 11px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:18px 0}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;border-top:5px solid var(--accent,#888)}
  .card .store{font-size:12.5px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--accent,#333)}
  .card .big{font-size:26px;font-weight:800;letter-spacing:-.5px;margin-top:5px}
  .card .delta{font-size:12px;margin-top:4px}
  .up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--muted)}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:14px 0}
  .panel h2{font-size:14px;margin:0 0 10px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)}
  svg{width:100%;height:auto;display:block}
  .legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;font-size:12.5px}
  .legend span{display:inline-flex;align-items:center;gap:6px}
  .swatch{width:12px;height:12px;border-radius:3px;display:inline-block}
  table{width:100%;border-collapse:separate;border-spacing:0;font-size:12.8px;margin-top:4px}
  th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
  th{font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:var(--muted);font-weight:700}
  td.num{text-align:right;font-variant-numeric:tabular-nums}
  td.cheap{box-shadow:inset 3px 0 0 var(--cheap);color:var(--cheap);font-weight:700}
  .pill{display:inline-block;font-size:11px;font-weight:700;border-radius:999px;padding:2px 9px;background:var(--cheap-soft);color:var(--cheap)}
  .league{display:flex;flex-wrap:wrap;gap:10px}
  .league .row{display:flex;align-items:center;gap:8px;font-size:13px}
  footer{margin-top:26px;font-size:11.5px;color:var(--muted);text-align:center}
</style>
</head>
<body>
<div class="wrap">
  <h1 id="title"></h1>
  <div class="sub" id="subtitle"></div>
  <div class="stamp" id="stamp"></div>

  <div class="cards" id="cards"></div>

  <div class="panel">
    <h2>Basket total over time</h2>
    <div id="chart"></div>
    <div class="legend" id="legend"></div>
  </div>

  <div class="panel">
    <h2>Cheapest league (times each store was cheapest)</h2>
    <div class="league" id="league"></div>
  </div>

  <div class="panel">
    <h2>Run history</h2>
    <div style="overflow:auto"><table id="table"></table></div>
  </div>

  <footer id="footer"></footer>
</div>

<script>
const DATA = __DATA__;
const ACCENTS = ['#178841','#d62828','#b8860b','#2563eb','#7c3aed','#0891b2','#db2777','#475569'];
const $ = s => document.querySelector(s);
const fmt = n => (n===null||n===undefined||isNaN(n)) ? '' : '$'+Number(n).toFixed(2);
const esc = t => {const d=document.createElement('div');d.textContent=(t==null?'':String(t));return d.innerHTML;};

const runs = (DATA.history||[]).slice();
// store order: first appearance across runs
const order = [];
runs.forEach(r => Object.keys(r.stores||{}).forEach(n => {if(!order.includes(n)) order.push(n);}));
const colorOf = {}; order.forEach((n,i)=>colorOf[n]=ACCENTS[i%ACCENTS.length]);
const totalOf = (r,n) => (r.stores && r.stores[n] && typeof r.stores[n].total==='number') ? r.stores[n].total : null;

$('#title').textContent = DATA.title || "Store basket totals over time";
$('#subtitle').textContent = order.length
  ? ('Tracking ' + order.join(', ') + ' across ' + runs.length + ' run' + (runs.length===1?'':'s') + '.')
  : 'No runs recorded yet.';
$('#stamp').textContent = 'Generated ' + (DATA.generated || '');

// ---- summary cards: latest, delta vs previous run, delta vs first ----
const cards = $('#cards');
order.forEach(n => {
  const series = runs.map(r=>totalOf(r,n));
  const present = series.map((v,i)=>[v,i]).filter(x=>x[0]!==null);
  if(!present.length) return;
  const latest = present[present.length-1][0];
  const first = present[0][0];
  const prev = present.length>1 ? present[present.length-2][0] : null;
  const dPrev = prev===null?null:latest-prev;
  const dFirst = latest-first;
  function deltaHTML(d,label){
    if(d===null) return '';
    const cls = Math.abs(d)<0.005?'flat':(d>0?'up':'down');
    const sign = d>0?'+':'';
    return '<div class="delta '+cls+'">'+sign+fmt(d).replace('$','$')+' '+label+'</div>';
  }
  const div=document.createElement('div'); div.className='card'; div.style.setProperty('--accent',colorOf[n]);
  div.innerHTML='<div class="store">'+esc(n)+'</div><div class="big">'+fmt(latest)+'</div>'
    + deltaHTML(dPrev,'vs last run') + deltaHTML(dFirst,'vs first run');
  cards.appendChild(div);
});

// ---- SVG line chart ----
(function drawChart(){
  const W=900,H=360, ml=64,mr=20,mt=18,mb=58;
  const cw=W-ml-mr, ch=H-mt-mb;
  const vals=[]; runs.forEach(r=>order.forEach(n=>{const v=totalOf(r,n); if(v!==null) vals.push(v);}));
  if(!vals.length){ $('#chart').innerHTML='<p class="sub">No totals to plot.</p>'; return; }
  let lo=Math.min(...vals), hi=Math.max(...vals);
  const pad=(hi-lo)*0.12 || hi*0.05 || 1; lo=Math.max(0,lo-pad); hi=hi+pad;
  const n=runs.length;
  const X=i=> n===1 ? ml+cw/2 : ml + cw*(i/(n-1));
  const Y=v=> mt + ch*(1-(v-lo)/(hi-lo||1));
  let svg='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Basket total over time">';
  // gridlines + y labels
  const TICKS=5;
  for(let t=0;t<=TICKS;t++){
    const v=lo+(hi-lo)*t/TICKS, y=Y(v);
    svg+='<line x1="'+ml+'" y1="'+y.toFixed(1)+'" x2="'+(W-mr)+'" y2="'+y.toFixed(1)+'" stroke="#eceef2"/>';
    svg+='<text x="'+(ml-8)+'" y="'+(y+4).toFixed(1)+'" text-anchor="end" font-size="11" fill="#6b7280">'+fmt(v)+'</text>';
  }
  // x labels (timestamps; thin out if many)
  const step=Math.ceil(n/8);
  runs.forEach((r,i)=>{
    if(i%step!==0 && i!==n-1) return;
    const x=X(i); const lbl=(r.timestamp||('run '+(i+1))).replace(/ [A-Z]{2,4}$/,'').replace(' ',' ');
    svg+='<text x="'+x.toFixed(1)+'" y="'+(H-mb+18)+'" text-anchor="middle" font-size="10" fill="#6b7280" transform="rotate(0 '+x.toFixed(1)+' '+(H-mb+18)+')">'+esc(lbl.slice(0,16))+'</text>';
  });
  // one polyline + dots per store
  order.forEach(name=>{
    const col=colorOf[name];
    const pts=runs.map((r,i)=>{const v=totalOf(r,name); return v===null?null:[X(i),Y(v),v,r.timestamp];}).filter(Boolean);
    if(pts.length>1){
      svg+='<polyline fill="none" stroke="'+col+'" stroke-width="2.5" stroke-linejoin="round" points="'
        + pts.map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ')+'"/>';
    }
    pts.forEach(p=>{
      svg+='<circle cx="'+p[0].toFixed(1)+'" cy="'+p[1].toFixed(1)+'" r="3.6" fill="'+col+'">'
        +'<title>'+esc(name+' · '+(p[3]||'')+' · '+fmt(p[2]))+'</title></circle>';
    });
  });
  svg+='</svg>';
  $('#chart').innerHTML=svg;
  $('#legend').innerHTML=order.map(n=>'<span><i class="swatch" style="background:'+colorOf[n]+'"></i>'+esc(n)+'</span>').join('');
})();

// ---- cheapest league ----
(function(){
  const tally={}; order.forEach(n=>tally[n]=0);
  runs.forEach(r=>{
    let best=null,bn=null;
    Object.keys(r.stores||{}).forEach(n=>{const v=totalOf(r,n); if(v!==null && (best===null||v<best)){best=v;bn=n;}});
    if(bn!==null) tally[bn]=(tally[bn]||0)+1;
  });
  const sorted=Object.entries(tally).sort((a,b)=>b[1]-a[1]);
  $('#league').innerHTML=sorted.map(([n,c])=>'<div class="row"><i class="swatch" style="background:'+colorOf[n]+'"></i>'
    +esc(n)+' <span class="pill">'+c+'×</span></div>').join('') || '<span class="sub">No data.</span>';
})();

// ---- run history table ----
(function(){
  let h='<tr><th>Run</th><th>Source</th>'+order.map(n=>'<th>'+esc(n)+'</th>').join('')+'<th>Cheapest</th></tr>';
  runs.slice().reverse().forEach(r=>{
    let best=null; Object.keys(r.stores||{}).forEach(n=>{const v=totalOf(r,n); if(v!==null&&(best===null||v<best))best=v;});
    h+='<tr><td>'+esc(r.timestamp||'')+'</td><td>'+esc(r.source_store||'')+'</td>';
    order.forEach(n=>{const v=totalOf(r,n); const isCheap=(v!==null&&best!==null&&Math.abs(v-best)<0.005);
      h+='<td class="num'+(isCheap?' cheap':'')+'">'+(v===null?'—':fmt(v))+'</td>';});
    h+='<td>'+esc(r.cheapest||'')+'</td></tr>';
  });
  $('#table').innerHTML=h;
})();

$('#footer').textContent = runs.length+' run'+(runs.length===1?'':'s')+' tracked'
  + (runs.length?(' · '+(runs[0].timestamp||'')+' → '+(runs[runs.length-1].timestamp||'')):'')
  + (DATA.generated?(' · generated '+DATA.generated):'');
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="Build an over-time trend report of store basket totals from the ledger.")
    ap.add_argument("history", help="Path to the totals-history.json ledger")
    ap.add_argument("-o", "--output", help="Output HTML path")
    ap.add_argument("--title", help="Override the report title")
    ap.add_argument("--generated", help="Override the generated timestamp string")
    args = ap.parse_args()

    history_path = Path(args.history)
    data = load_history(history_path)
    if args.title:
        data["title"] = args.title
    data["generated"] = args.generated or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = data.get("title", "Store basket totals over time")

    html = (TEMPLATE
            .replace("__TITLE__", escape(title))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")))

    if args.output:
        out = Path(args.output)
    else:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = history_path.with_name(f"totals-over-time-{stamp}.html")

    out.write_text(html, encoding="utf-8")
    n = len(data["history"])
    print(f"Wrote {out} ({n} run{'s' if n != 1 else ''} charted)")


if __name__ == "__main__":
    main()
