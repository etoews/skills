# Foodstuffs platform automation (New World, PAK'nSAVE, Four Square)

New World (`newworld.co.nz`), PAK'nSAVE (`paknsave.co.nz`) and Four Square
(`foursquare.co.nz`) all run the **same Foodstuffs React storefront**. The DOM,
the `data-testid` names, the search URLs and the cart all behave identically, so
every snippet here works on all three (Four Square carries a smaller range, and
range/price differ by individual store). Woolworths is a different platform — see
`woolworths.md`.

The whole point of this file is that the obvious automation approaches **silently
fail** on this storefront in three specific ways. Each gotcha below cost a real
debugging loop; the snippet next to it is the thing that actually works. Paste the
snippets into `mcp__claude-in-chrome__javascript_tool` calls.

## Preconditions
- The user must already be **logged in** and have a **store selected** (both show
  in the top bar). Do not change the store. Adding to cart requires the login.
- Load the Chrome MCP tools first (`tabs_context_mcp`, `navigate`, `computer`,
  `javascript_tool`, `find`, `form_input`, `browser_batch`).

## Search by URL
Navigate straight to the search results — no need to type in the box:
```
https://www.newworld.co.nz/shop/search?q=<url-encoded query>
https://www.paknsave.co.nz/shop/search?q=<url-encoded query>
```
Results render asynchronously, so **poll** for product cards before reading. Use
`browser_batch` to navigate + extract in one round trip.

## Product card anatomy
Each result tile is `[data-testid^="product-<SKU>"]` (e.g. `product-5025751-EA-000`;
weight items end `-KGM-000`). Inside:
- `product-title` — name
- `product-subtitle` — size (e.g. `750g`, `1l`, `12 x 330ml`)
- `product-decal-*` — promo badge; the `<img>` `aria-label` reads e.g.
  `"Badge, Everyday Low Price"`
- `product-card-details` — price block (dollars and cents are separate nodes, so
  innerText looks like `4 66 ea $0.62/100g`)
- `quantity-edit` — the quantity `<input type=number>`
- `add-to-cart` — the Add button (becomes a stepper once in trolley)
- `increment-quantity` / `decrement-quantity` — stepper buttons
- a unit `<select>` (produce only) with options `UNITS` (text "ea") / `WEIGHT` ("kg")

## Helper: realClick (use this for every button)
A plain `el.click()` does **not** reliably drive these React controls. Dispatch a
full pointer/mouse sequence instead:
```js
function rc(el){['pointerdown','mousedown','pointerup','mouseup','click']
  .forEach(t=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window})));}
```

## Extract search results (poll + read)
```js
await (async () => {
  const s=Date.now();
  while(Date.now()-s<8000){
    if(document.querySelectorAll('[data-testid="product-title"]').length>0) break;
    if(/no results|couldn.?t find/i.test(document.body.innerText)) break;
    await new Promise(r=>setTimeout(r,400));
  }
  const out=[...document.querySelectorAll('[data-testid="product-title"]')].map(t=>{
    let c=t; while(c&&!(c.getAttribute('data-testid')||'').match(/^product-\d/)) c=c.parentElement;
    const sub=c&&c.querySelector('[data-testid="product-subtitle"]');
    const d=c&&c.querySelector('[data-testid="product-card-details"]');
    return {
      title:t.innerText.trim(),
      size:sub?sub.innerText.trim():'',
      price:d?d.innerText.replace(/\n+/g,' ').replace(/ Add to list.*/,'')
            .replace(/\d\.\d \(\d+\).*?review[s]?/i,'').trim():''
    };
  });
  return JSON.stringify({count:out.length, results:out.slice(0,8)});
})();
```
`price` like `"7 00 ea $35.00/1kg"` means $7.00. A second money value such as a
badge `"5.99 ... Limit 6"` means the item is **on special at $5.99** — capture it.

## Add to cart + set quantity  ── GOTCHA 1 ──
`add-to-cart` adds qty 1 and the button becomes a stepper. **Do NOT set the
quantity by writing to `quantity-edit`.** Typing the value updates the on-screen
number but does **not** sync to the server cart — the cart will still hold qty 1.
You must click `increment-quantity` (via `rc`) to reach the target. Loop with a
guard and verify:
```js
await (async () => {
  function rc(el){['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window})));}
  const match="EXACT OR SUBSTRING OF TITLE", desired=2;          // <-- edit
  const titles=[...document.querySelectorAll('[data-testid="product-title"]')];
  const tEl=titles.find(t=>t.innerText.toLowerCase().includes(match.toLowerCase()));
  if(!tEl) return JSON.stringify({error:'no match', available:titles.map(t=>t.innerText.trim()).slice(0,8)});
  let card=tEl; while(card&&!(card.getAttribute('data-testid')||'').match(/^product-\d/)) card=card.parentElement;
  const gq=()=>{const q=card.querySelector('[data-testid="quantity-edit"]');return q?parseFloat(q.value)||0:0;};
  const add=card.querySelector('[data-testid="add-to-cart"]');
  if(add){rc(add);await new Promise(r=>setTimeout(r,1100));}    // -> qty 1
  let g=0;
  while(gq()!==desired && g<12){                                 // step to target
    const b=card.querySelector(gq()<desired?'[data-testid="increment-quantity"]':'[data-testid="decrement-quantity"]');
    if(!b) break; rc(b); await new Promise(r=>setTimeout(r,600)); g++;
  }
  return JSON.stringify({matched:tEl.innerText.trim(), finalQty:gq()});
})();
```
When two variants share a name (e.g. 200g vs 100g ham), disambiguate by checking
`product-subtitle` equals the size you want before selecting the card.

## Weight produce (sold per kg)  ── GOTCHA 2 ──
Loose produce has a unit `<select>` (ea / kg). Flipping it to kg via JS
(`el.value='WEIGHT'` + dispatch change) is **flaky — React reverts it**. The
reliable path uses the `form_input` MCP tool and a **tool-call boundary** to let
React settle:

1. `find` the select: query `"unit type select dropdown (ea / kg) inside the <Item> product card"` → gives a ref.
2. `form_input(ref, "kg")`.
3. In a **separate** `javascript_tool` call, confirm `card.querySelector('select').value==='WEIGHT'`
   (now it sticks; qty shows the min weight, step `0.1`). If it still reads
   `UNITS`, repeat steps 2–3 once — it is mildly non-deterministic.
4. Set the weight and commit with a real Add click (native value-set is fine here
   **because you commit with the button**, unlike the ea-quantity case):
```js
await (async () => {
  function rc(el){['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window})));}
  function setNV(el,v){const p=Object.getPrototypeOf(el);Object.getOwnPropertyDescriptor(p,'value').set.call(el,v);}
  const match="EXACT TITLE", kg="1.2";                            // <-- edit
  const tEl=[...document.querySelectorAll('[data-testid="product-title"]')].find(t=>t.innerText.trim().toLowerCase()===match.toLowerCase());
  let card=tEl; while(card&&!(card.getAttribute('data-testid')||'').match(/^product-\d/)) card=card.parentElement;
  const sel=card.querySelector('select');
  if(sel.value!=='WEIGHT') return JSON.stringify({err:'not weight yet — re-run form_input(kg)'});
  let q=card.querySelector('[data-testid="quantity-edit"]');
  setNV(q,kg); q.dispatchEvent(new Event('input',{bubbles:true})); q.dispatchEvent(new Event('change',{bubbles:true}));
  await new Promise(r=>setTimeout(r,700));
  const add=card.querySelector('[data-testid="add-to-cart"]');
  if(add){rc(add);await new Promise(r=>setTimeout(r,1200));}      // commit
  q=card.querySelector('[data-testid="quantity-edit"]');
  const d=card.querySelector('[data-testid="product-card-details"]');
  return JSON.stringify({qty:q?q.value:'?', state:(d.innerText.replace(/\n+/g,' ').match(/[\d.]+kg in trolley/)||['NOT'])[0]});
})();
```
Min weight is usually `0.2kg`, step `0.1`. If a store sells the item only as a
fixed prepack bag (no by-weight option), add the bag and record its `per_kg` so the
report can compare per kilo — see `matching-and-flags.md`.

## Age gate (alcohol category)  ── GOTCHA 3 ──
Alcohol-category items — **including 0.0% non-alcoholic beer** like Peroni 0.0% —
pop an "Are you 18 or older?" modal that blocks the add. Sequence:
1. Real-click `add-to-cart` (use the `computer` tool, not JS) → modal appears.
2. Real-click **Yes**.
3. Verify the cart count rose / the card shows "in trolley".

On New World this completes after a Yes + one more Add. On **PAK'nSAVE Kilbirnie it
would not complete via automation** (Yes closes the modal but never finalises the
add, and it re-prompts each time). So: try real-click Add → Yes → verify, at most
2–3 times; if it still won't add, **flag the item** (record its shelf price from the
card) and move on. Do not keep hammering.

Confirming an age gate for the user's **own logged-in account** on a **non-alcoholic
item they themselves listed** is reasonable. Do not bypass any other kind of gate
(CAPTCHA, real alcohol the user didn't ask for, etc.).

## Cart count is line items, not units
`[data-testid="cart-total-items"]` counts **distinct products**, not total
quantity. Verify quantities on the product card ("N in trolley") or in the cart —
never infer them from this bubble.

## Reconcile authoritative prices from the cart slide-out
Search-card prices are **shelf** prices. Club / member / weekly specials only apply
**at the cart**, so always reconcile final prices from the cart before reporting.
Use the slide-out (the full `/shop/shopping-cart` page is heavy and its DOM
extraction can be slow or privacy-blocked):
```js
await (async () => {
  function rc(el){['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window})));}
  const btn=document.querySelector('[data-testid="bar-cart-button"]'); if(btn) rc(btn);
  await new Promise(r=>setTimeout(r,2000));
  const items=[...document.querySelectorAll('[data-testid^="cart-preview-5"]')]
    .filter(e=>/^cart-preview-\d+-/.test(e.getAttribute('data-testid')));
  const out=items.map(c=>{
    const q=c.querySelector('input');
    const pm=c.innerText.replace(/\n+/g,' ').match(/\$[\d,]+\.\d{2}/);
    return c.getAttribute('data-testid').replace('cart-preview-','').replace('-000','')
      +'|q'+(q?q.value:'?')+'|'+(pm?pm[0]:'?');
  });
  const sub=document.querySelector('[data-testid="cart-preview-subtotal"]');
  return JSON.stringify({lines:out.length, subtotal:sub?sub.innerText.trim():'?', items:out});
})();
```
Each line is `cart-preview-<SKU>`; match SKUs back to the products you added.
`cart-preview-product-name`, an `<input>` (qty) and a `$X.XX` are inside each.
`cart-preview-subtotal` is the authoritative subtotal. Reading the cart this way
also lets you **verify** every quantity landed (catches the GOTCHA-1 sync issue).

## javascript_tool privacy filter
The tool blocks returning content that looks like cookie/query-string data, and
returning `location.href` (it contains the query string) can trip it with
`[BLOCKED: Cookie/query string data]`. Keep return values to compact
product/price JSON; never return `location.href` or large `innerText` dumps.

## Speed
Batch `navigate` + the extract/add JS into one `browser_batch`, and process
several items in a single batch (navigate item A, add A, navigate item B, add B, …)
— each JS step returns its own result. Keep heavy `querySelectorAll('*')` out of
the page JS; it can freeze the renderer. Always select by `data-testid`.
