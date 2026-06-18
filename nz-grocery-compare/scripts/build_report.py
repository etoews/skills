#!/usr/bin/env python3
"""
build_report.py - Generate an interactive grocery price-comparison report.

Takes a comparison JSON describing one basket priced across several NZ
supermarkets and emits a single self-contained HTML file with a searchable,
sortable, filterable table, per-store totals, gentle sale highlighting,
cheapest-cell-per-row marking, and unavailable/flagged items.

Usage:
    python build_report.py <data.json> [-o output.html] [--title "..."]

If -o is omitted the file is written next to the data file as
    comparison-report-<YYYYMMDD-HHMMSS>.html

INPUT JSON SCHEMA
-----------------
{
  "title": "Grocery Price Comparison",          # optional
  "generated": "2026-06-18 18:54 NZST",         # optional; auto-filled if absent
  "source_store": "Woolworths",                 # optional; the basket that was copied
  "stores": [                                   # required; order = column order
    {
      "key": "ww",                              # required; short id used in item cells
      "name": "Woolworths",                     # required; column header
      "location": "Online trolley",             # optional
      "subtotal": 239.20,                       # optional; authoritative cart subtotal
      "fees": 0,                                # optional; service/bag fees
      "savings": 31.92,                         # optional; specials already applied
      "note": "incl. member prices"             # optional; shown on the summary card
    },
    ...
  ],
  "items": [                                    # required
    {
      "category": "Bakery",                     # optional; groups + enables the filter
      "item": "Toast Bread Soya & Linseed 750g x2",  # required; the row label
      "match": "exact",                         # optional; exact | similar | flag
      "note": "",                               # optional; small note under the item
      "cells": {                                # required; keyed by store "key"
        "ww":  {"name": "Freyas ... Linseed", "line": 9.32, "each": 4.66, "qty": 2,
                 "sale": true, "sale_label": "20% off", "was": 11.65},
        "nw":  {"name": "Freya's Swiss ...", "line": 9.32, "each": 4.66, "qty": 2},
        "pak": {"name": "Freya's Swiss ...", "line": 8.70, "each": 4.35, "qty": 2}
      }
    },
    ...
  ]
}

Per-cell fields (all optional except when you want a price shown):
    name        product name at that store
    line        line total (number) - drives totals, sorting, cheapest marking
    each        unit price (number) - shown as a small "($X ea)" note
    qty         quantity (number)
    per_kg      per-kg price for loose produce (shown instead of/with each)
    sale        true to gently highlight as a special/member price
    sale_label  short badge text (e.g. "20% off", "member", "club")
    was         struck-through previous price (number)
    unavailable true if the store has no match (renders "n/a", excluded from totals)
    note        small note under the cell

Anything you omit is simply not rendered. Missing cells = blank for that store.
"""

import argparse
import json
import sys
import datetime
from pathlib import Path
from html import escape


def load_data(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "stores" not in data or not data["stores"]:
        sys.exit("error: JSON must contain a non-empty 'stores' array")
    if "items" not in data or not data["items"]:
        sys.exit("error: JSON must contain a non-empty 'items' array")
    for s in data["stores"]:
        if "key" not in s or "name" not in s:
            sys.exit("error: every store needs 'key' and 'name'")
    return data


# The HTML app is one template string. We avoid str.format on the whole thing
# (CSS/JS use lots of braces); instead we replace a few explicit placeholders.
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en-NZ">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root{
    --ink:#1d2126; --muted:#6b7280; --line:#e7e9ee; --bg:#f6f7f9; --card:#fff;
    --sale:#b8530a; --sale-soft:#fff4e8; --cheap:#0f7a3d; --cheap-soft:#eaf7ef;
    --flag:#9a3412; --flag-soft:#fdf0e9;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    line-height:1.45;-webkit-font-smoothing:antialiased;font-size:14px}
  .wrap{max-width:1340px;margin:0 auto;padding:28px 20px 80px}
  h1{font-size:24px;margin:0 0 4px;letter-spacing:-.3px}
  .sub{color:var(--muted);font-size:13.5px}
  .stamp{display:inline-block;margin-top:9px;font-size:12px;color:var(--muted);
    background:var(--card);border:1px solid var(--line);border-radius:999px;padding:4px 11px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:18px 0 18px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px 17px;border-top:5px solid var(--accent,#888)}
  .card .store{font-size:12.5px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--accent,#333)}
  .card .loc{font-size:11.5px;color:var(--muted);margin-bottom:9px}
  .card .big{font-size:30px;font-weight:800;letter-spacing:-1px}
  .card .meta{font-size:11.5px;color:var(--muted);margin-top:5px}
  .card .badge{display:inline-block;margin-top:9px;font-size:11.5px;font-weight:700;color:var(--cheap);background:var(--cheap-soft);border-radius:999px;padding:3px 10px}
  .controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:6px 0 12px;
    background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 13px}
  .controls input[type=search],.controls select{font:inherit;font-size:13px;padding:6px 9px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink)}
  .controls input[type=search]{min-width:220px;flex:1 1 220px}
  .controls label{font-size:12.5px;color:var(--muted);display:inline-flex;align-items:center;gap:5px;cursor:pointer}
  .controls .spacer{flex:1 1 auto}
  .controls button{font:inherit;font-size:12.5px;padding:6px 11px;border:1px solid var(--line);border-radius:8px;background:#fff;cursor:pointer;color:var(--ink)}
  .controls button:hover{background:#f3f4f6}
  .count{font-size:12px;color:var(--muted)}
  .tablewrap{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:auto}
  table{width:100%;border-collapse:separate;border-spacing:0;min-width:760px}
  thead th{position:sticky;top:0;background:#fbfbfc;font-size:11px;text-transform:uppercase;letter-spacing:.4px;
    color:var(--muted);text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);font-weight:700;cursor:pointer;white-space:nowrap;user-select:none}
  thead th .arrow{opacity:.35;font-size:10px;margin-left:3px}
  thead th.sorted .arrow{opacity:1;color:var(--ink)}
  tbody td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top;font-size:12.8px}
  tbody tr:hover td{background:#fafbfc}
  td.store{border-left:1px solid var(--line)}
  .pname{font-weight:600;font-size:12.5px}
  .pmeta{color:var(--muted);font-size:11px;margin-top:1px}
  .price{font-weight:700;white-space:nowrap}
  .price .q{font-weight:500;color:var(--muted);font-size:10.5px}
  .was{color:var(--muted);text-decoration:line-through;font-size:10.5px;margin-left:4px}
  .pill{display:inline-block;font-size:9.5px;font-weight:700;border-radius:999px;padding:1px 6px;vertical-align:middle;white-space:nowrap}
  .pill.sale{color:var(--sale);background:var(--sale-soft);border:1px solid #f3d9be}
  .pill.exact{color:#374151;background:#eef1f5;border:1px solid #e0e4ea}
  .pill.similar{color:#7a5b12;background:#fbf3df;border:1px solid #efe2bf}
  .pill.flag{color:var(--flag);background:var(--flag-soft);border:1px solid #f1cdbb}
  .cheap{box-shadow:inset 3px 0 0 var(--cheap)}
  .cheap .price{color:var(--cheap)}
  .saletint{background:var(--sale-soft)!important}
  .na{color:var(--flag);font-weight:600}
  tfoot td{padding:11px 12px;border-top:2px solid var(--line);font-weight:800;font-size:13px;background:#fbfbfc}
  tfoot td.lbl{color:var(--muted);font-weight:700;text-transform:uppercase;font-size:11px;letter-spacing:.4px}
  .legend{font-size:11.5px;color:var(--muted);margin:12px 2px 0;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
  footer{margin-top:26px;font-size:11.5px;color:var(--muted);text-align:center}
  .empty{padding:26px;text-align:center;color:var(--muted)}
</style>
</head>
<body>
<div class="wrap">
  <h1 id="title"></h1>
  <div class="sub" id="subtitle"></div>
  <div class="stamp" id="stamp"></div>
  <div class="cards" id="cards"></div>

  <div class="controls">
    <input type="search" id="search" placeholder="Search items or products...">
    <label>Category <select id="fcat"></select></label>
    <label>Match <select id="fmatch"></select></label>
    <label>Cheapest <select id="fcheap"></select></label>
    <label><input type="checkbox" id="fsale"> sales only</label>
    <label><input type="checkbox" id="fhide"> hide unavailable rows</label>
    <span class="spacer"></span>
    <span class="count" id="count"></span>
    <button id="reset">Reset</button>
  </div>

  <div class="tablewrap">
    <table>
      <thead id="thead"></thead>
      <tbody id="tbody"></tbody>
      <tfoot id="tfoot"></tfoot>
    </table>
  </div>
  <div class="empty" id="empty" style="display:none">No rows match the current filters.</div>

  <div class="legend">
    <span><span class="pill exact">exact</span> same product</span>
    <span><span class="pill similar">similar</span> closest substitute</span>
    <span><span class="pill flag">flag</span> unavailable / not added</span>
    <span><span class="pill sale">sale</span> special / member price</span>
    <span><b style="color:var(--cheap)">&#9614;</b> cheapest of the stores on that row</span>
  </div>

  <footer id="footer"></footer>
</div>

<script>
const DATA = __DATA__;
const ACCENTS = ['#178841','#d62828','#b8860b','#2563eb','#7c3aed','#0891b2'];
const $ = s => document.querySelector(s);
const fmt = n => (n===null||n===undefined||isNaN(n)) ? '' : '$'+Number(n).toFixed(2);

const stores = DATA.stores;
stores.forEach((s,i)=>{ if(!s.accent) s.accent = ACCENTS[i%ACCENTS.length]; });

// ---- header ----
$('#title').textContent = DATA.title || 'Grocery Price Comparison';
$('#subtitle').textContent = DATA.source_store
  ? ('Basket from ' + DATA.source_store + ', priced across ' + stores.map(s=>s.name).join(', ') + '.')
  : ('Basket priced across ' + stores.map(s=>s.name).join(', ') + '.');
$('#stamp').textContent = 'Generated ' + (DATA.generated || '');

// ---- store summary cards (totals) ----
function storeSubtotal(key){
  const s = stores.find(x=>x.key===key);
  if(s && typeof s.subtotal === 'number') return s.subtotal;
  // fall back to summing line values
  let t=0; DATA.items.forEach(it=>{const c=it.cells&&it.cells[key]; if(c&&!c.unavailable&&typeof c.line==='number') t+=c.line;});
  return t;
}
const totalsByKey = {};
stores.forEach(s=>{ totalsByKey[s.key] = storeSubtotal(s.key); });
const cheapestTotal = Math.min(...stores.map(s=>totalsByKey[s.key]));

const cards = $('#cards');
stores.forEach(s=>{
  const sub = totalsByKey[s.key];
  const bits = [];
  if(typeof s.fees === 'number' && s.fees>0) bits.push('+'+fmt(s.fees)+' fees');
  if(typeof s.savings === 'number' && s.savings>0) bits.push(fmt(s.savings)+' specials applied');
  if(s.note) bits.push(s.note);
  const win = Math.abs(sub - cheapestTotal) < 0.005;
  const div = document.createElement('div');
  div.className='card'; div.style.setProperty('--accent', s.accent);
  div.innerHTML = '<div class="store">'+esc(s.name)+'</div>'
    + '<div class="loc">'+esc(s.location||'')+'</div>'
    + '<div class="big">'+fmt(sub)+'</div>'
    + (bits.length?'<div class="meta">'+esc(bits.join(' · '))+'</div>':'')
    + (win?'<div class="badge">Cheapest basket</div>':'');
  cards.appendChild(div);
});

// ---- table columns ----
// fixed cols: Category, Item, Match, then one per store
const COLS = [
  {id:'category', label:'Category', kind:'text', get:it=>it.category||''},
  {id:'item', label:'Item', kind:'text', get:it=>it.item||''},
  {id:'match', label:'Match', kind:'text', get:it=>it.match||''},
];
stores.forEach(s=>{
  COLS.push({id:'store:'+s.key, label:s.name, kind:'num', store:s,
    get:it=>{const c=it.cells&&it.cells[s.key]; return (c&&!c.unavailable&&typeof c.line==='number')?c.line:null;}});
});

function esc(t){const d=document.createElement('div');d.textContent=(t==null?'':String(t));return d.innerHTML;}

// cheapest store key(s) per row
function cheapestKeys(it){
  let best=Infinity, keys=[];
  stores.forEach(s=>{const c=it.cells&&it.cells[s.key]; if(c&&!c.unavailable&&typeof c.line==='number'){ if(c.line<best-0.005){best=c.line;keys=[s.key];} else if(Math.abs(c.line-best)<0.005){keys.push(s.key);} }});
  return keys;
}

function cellHTML(it, s){
  const c = it.cells && it.cells[s.key];
  if(!c) return '';
  if(c.unavailable) return '<span class="na">n/a</span>'+(c.note?'<div class="pmeta">'+esc(c.note)+'</div>':'');
  let priceTxt = '';
  if(typeof c.line === 'number') priceTxt = fmt(c.line);
  else if(typeof c.per_kg === 'number') priceTxt = fmt(c.per_kg)+'<span class="q">/kg</span>';
  let q = '';
  if(typeof c.each==='number' && c.qty && c.qty!==1) q = ' <span class="q">($'+c.each.toFixed(2)+' ea ×'+c.qty+')</span>';
  else if(typeof c.per_kg==='number' && typeof c.line==='number') q = ' <span class="q">('+fmt(c.per_kg)+'/kg)</span>';
  let was = (typeof c.was==='number')?'<span class="was">'+fmt(c.was)+'</span>':'';
  let badge = c.sale?(' <span class="pill sale">'+esc(c.sale_label||'sale')+'</span>'):'';
  return (c.name?'<div class="pname">'+esc(c.name)+'</div>':'')
    + '<div class="price">'+priceTxt+was+q+badge+'</div>'
    + (c.note?'<div class="pmeta">'+esc(c.note)+'</div>':'');
}

// ---- build static row models ----
const ROWS = DATA.items.map((it,idx)=>{
  const cheap = cheapestKeys(it);
  const hasSale = stores.some(s=>{const c=it.cells&&it.cells[s.key];return c&&c.sale;});
  const hasNA = stores.some(s=>{const c=it.cells&&it.cells[s.key];return c&&c.unavailable;});
  const searchBlob = [it.category,it.item,it.match,it.note].concat(
    stores.map(s=>{const c=it.cells&&it.cells[s.key];return c?[c.name,c.note,c.sale_label].filter(Boolean).join(' '):'';})
  ).filter(Boolean).join(' ').toLowerCase();
  return {it, idx, cheap, hasSale, hasNA, searchBlob};
});

// ---- thead ----
const matchPill = m => m?('<span class="pill '+(['exact','similar','flag'].includes(m)?m:'')+'">'+esc(m)+'</span>'):'';
const thead = $('#thead');
const tr = document.createElement('tr');
COLS.forEach((col,ci)=>{
  const th=document.createElement('th');
  th.innerHTML = esc(col.label)+'<span class="arrow">↕</span>';
  if(col.store) { th.className='store'; th.style.color=col.store.accent; }
  th.addEventListener('click',()=>sortBy(ci));
  tr.appendChild(th);
});
thead.appendChild(tr);

// ---- filters population ----
const cats = [...new Set(DATA.items.map(it=>it.category).filter(Boolean))].sort();
const fcat=$('#fcat'); fcat.innerHTML='<option value="">all</option>'+cats.map(c=>'<option>'+esc(c)+'</option>').join('');
const matches=[...new Set(DATA.items.map(it=>it.match).filter(Boolean))];
const fmatch=$('#fmatch'); fmatch.innerHTML='<option value="">all</option>'+matches.map(m=>'<option>'+esc(m)+'</option>').join('');
const fcheap=$('#fcheap'); fcheap.innerHTML='<option value="">any store</option>'+stores.map(s=>'<option value="'+s.key+'">'+esc(s.name)+' cheapest</option>').join('');

// ---- state ----
let sortCol = null, sortDir = 1;
function sortBy(ci){ if(sortCol===ci){sortDir*=-1;} else {sortCol=ci;sortDir=1;} render(); }

function currentRows(){
  const q=$('#search').value.trim().toLowerCase();
  const cat=fcat.value, mt=fmatch.value, ch=fcheap.value;
  const saleOnly=$('#fsale').checked, hideNA=$('#fhide').checked;
  let rows = ROWS.filter(r=>{
    if(q && !r.searchBlob.includes(q)) return false;
    if(cat && r.it.category!==cat) return false;
    if(mt && r.it.match!==mt) return false;
    if(ch && !r.cheap.includes(ch)) return false;
    if(saleOnly && !r.hasSale) return false;
    if(hideNA && r.hasNA) return false;
    return true;
  });
  if(sortCol!==null){
    const col=COLS[sortCol];
    rows = rows.slice().sort((a,b)=>{
      let va=col.get(a.it), vb=col.get(b.it);
      if(col.kind==='num'){ va=(va==null?Infinity:va); vb=(vb==null?Infinity:vb); return (va-vb)*sortDir; }
      return String(va).localeCompare(String(vb))*sortDir;
    });
  }
  return rows;
}

function render(){
  const rows = currentRows();
  // thead sort indicators
  thead.querySelectorAll('th').forEach((th,i)=>{ th.classList.toggle('sorted', i===sortCol);
    const ar=th.querySelector('.arrow'); if(ar) ar.textContent = (i===sortCol)?(sortDir>0?'↑':'↓'):'↕'; });
  const tb=$('#tbody'); tb.innerHTML='';
  rows.forEach(r=>{
    const it=r.it; const trEl=document.createElement('tr');
    let html = '<td><div class="pmeta">'+esc(it.category||'')+'</div></td>'
      + '<td><div class="pname">'+esc(it.item||'')+'</div>'+(it.note?'<div class="pmeta">'+esc(it.note)+'</div>':'')+'</td>'
      + '<td>'+matchPill(it.match)+'</td>';
    stores.forEach(s=>{
      const c=it.cells&&it.cells[s.key];
      const isCheap=r.cheap.includes(s.key)&&r.cheap.length<stores.length;
      const isSale=c&&c.sale;
      html += '<td class="store'+(isCheap?' cheap':'')+(isSale?' saletint':'')+'">'+cellHTML(it,s)+'</td>';
    });
    trEl.innerHTML=html; tb.appendChild(trEl);
  });
  // footer visible totals
  const tf=$('#tfoot');
  let f='<tr><td class="lbl">Visible totals</td><td></td><td></td>';
  stores.forEach(s=>{ let t=0; rows.forEach(r=>{const c=r.it.cells&&r.it.cells[s.key]; if(c&&!c.unavailable&&typeof c.line==='number') t+=c.line;});
    f+='<td class="store">'+fmt(t)+'</td>'; });
  f+='</tr>'; tf.innerHTML=f;
  $('#count').textContent = rows.length+' of '+ROWS.length+' items';
  $('#empty').style.display = rows.length?'none':'block';
}

['#search','#fcat','#fmatch','#fcheap','#fsale','#fhide'].forEach(sel=>{
  const el=$(sel); el.addEventListener(el.tagName==='INPUT'&&el.type!=='checkbox'?'input':'change', render);
});
$('#reset').addEventListener('click',()=>{
  $('#search').value=''; fcat.value=''; fmatch.value=''; fcheap.value=''; $('#fsale').checked=false; $('#fhide').checked=false;
  sortCol=null; sortDir=1; render();
});

// footer line
$('#footer').textContent = stores.map(s=>s.name+' '+fmt(totalsByKey[s.key])).join('  ·  ')
  + '  ·  cheapest: ' + stores.find(s=>Math.abs(totalsByKey[s.key]-cheapestTotal)<0.005).name
  + (DATA.generated?('  ·  '+DATA.generated):'');

render();
</script>
</body>
</html>
"""


def compute_store_totals(data: dict) -> dict:
    """Per-store {subtotal, fees, total, items} for this run. Uses the store's
    declared authoritative subtotal when present, else sums the cell line totals."""
    rows = data["items"]
    out = {}
    for s in data["stores"]:
        key = s["key"]
        cells = [(it.get("cells") or {}).get(key) for it in rows]
        priced = [c for c in cells if c and not c.get("unavailable")]
        if isinstance(s.get("subtotal"), (int, float)):
            sub = float(s["subtotal"])
        else:
            sub = sum(float(c["line"]) for c in priced if isinstance(c.get("line"), (int, float)))
        fees = float(s.get("fees") or 0)
        items = sum(1 for c in priced
                    if isinstance(c.get("line"), (int, float)) or isinstance(c.get("per_kg"), (int, float)))
        out[key] = {"name": s["name"], "subtotal": round(sub, 2), "fees": round(fees, 2),
                    "total": round(sub + fees, 2), "items": items}
    return out


def record_history(data: dict, totals: dict, history_path: Path) -> int:
    """Append this run's per-store totals to the timestamped ledger JSON.
    De-dupes on the run timestamp so re-running the same data won't double-count.
    Returns the number of runs now tracked."""
    try:
        hist = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        hist = {}
    runs = hist.get("history") if isinstance(hist, dict) else None
    if not isinstance(runs, list):
        runs = []
    cheapest = min(totals.values(), key=lambda t: t["total"])["name"] if totals else None
    entry = {
        "timestamp": data.get("generated"),
        "source_store": data.get("source_store"),
        "cheapest": cheapest,
        "stores": {t["name"]: {"key": k, "subtotal": t["subtotal"], "fees": t["fees"],
                               "total": t["total"], "items": t["items"]}
                   for k, t in totals.items()},
    }
    runs = [e for e in runs if e.get("timestamp") != entry["timestamp"]]
    runs.append(entry)
    runs.sort(key=lambda e: e.get("timestamp") or "")
    history_path.write_text(json.dumps({"history": runs}, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(runs)


def main():
    ap = argparse.ArgumentParser(description="Generate an interactive grocery price-comparison report and record per-store totals to a history ledger.")
    ap.add_argument("data", help="Path to the comparison JSON file")
    ap.add_argument("-o", "--output", help="Output HTML path")
    ap.add_argument("--title", help="Override the report title")
    ap.add_argument("--generated", help="Override the generated timestamp string")
    ap.add_argument("--history", help="Path to the totals ledger JSON (default: totals-history.json next to the data file)")
    ap.add_argument("--no-history", action="store_true", help="Do not record this run's totals to the ledger")
    args = ap.parse_args()

    data_path = Path(args.data)
    data = load_data(data_path)

    if args.title:
        data["title"] = args.title
    if args.generated:
        data["generated"] = args.generated
    if not data.get("generated"):
        data["generated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    title = data.get("title", "Grocery Price Comparison")

    html = (TEMPLATE
            .replace("__TITLE__", escape(title))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))

    if args.output:
        out = Path(args.output)
    else:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = data_path.with_name(f"comparison-report-{stamp}.html")

    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out}")

    if not args.no_history:
        history_path = Path(args.history) if args.history else data_path.with_name("totals-history.json")
        totals = compute_store_totals(data)
        n = record_history(data, totals, history_path)
        line = "  ".join(f"{t['name']} ${t['total']:.2f}" for t in totals.values())
        print(f"Recorded totals to {history_path} ({n} run{'s' if n != 1 else ''} tracked): {line}")


if __name__ == "__main__":
    main()
