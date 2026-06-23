---
name: comparison
description: >-
  Comparison-shop a grocery basket across New Zealand's main supermarket websites
  — Woolworths (woolworths.co.nz), and the Foodstuffs sites New World
  (newworld.co.nz), PAK'nSAVE (paknsave.co.nz) and Four Square (foursquare.co.nz).
  Reads an existing online trolley/cart from one store (default Woolworths), finds
  the same-or-closest product at each other store, adds it to that store's cart via
  Chrome browser automation, reconciles the real cart prices, and builds an
  interactive timestamped HTML price-comparison report (searchable, sortable,
  filterable table with per-store totals and sale highlighting). Every run also
  appends each store's basket total to a history ledger and can chart how each
  store's total moves over time. Use this whenever the user wants to compare
  supermarket/grocery prices across stores, copy or replicate a cart/trolley from
  one NZ supermarket into another, price-match or "comparison shop" a grocery
  basket, check which store is cheapest, or track grocery totals/spend over time —
  even if they don't name every store or say the word "report". Requires the
  Claude-in-Chrome browser tools and the user being logged in to the relevant store
  sites.
---

# NZ grocery price comparison

Copy one supermarket basket across the others and show, item by item, which store
is cheapest. The deliverable is an interactive HTML report.

## What this skill knows that's hard-won
The New World / PAK'nSAVE / Four Square storefronts share one React app whose
automation **silently fails** in specific ways (typed quantities don't sync to the
cart; the kg/ea unit switch reverts; alcohol items hit an 18+ gate; specials only
apply at the cart, not on the shelf). `references/foodstuffs-platform.md` has the
exact working snippets for each. Don't rediscover these the hard way — read it
before automating those sites.

## Preconditions
- The Claude-in-Chrome MCP tools are available and the user is **logged in** to
  each store with a **store/location selected**. You add to *their* carts; you do
  not check out. Treat building the carts as the goal and tell them to review and
  order themselves.
- Confirm which store is the **source** (the basket to copy). Default: Woolworths.
  Targets: the other stores the user wants compared (default New World + PAK'nSAVE).

## Workflow

**All output goes in a `comparison/` directory.** Every file this skill produces —
the parsed-basket working JSON, the comparison data JSON, both HTML reports, and the
`totals-history.json` ledger — is written under a `comparison/` directory in the
current working directory. Use this prefix on every path below. The report scripts
create the directory automatically, so you don't need to `mkdir` it first.

### 1. Read the source basket
- Woolworths: `woolworths.co.nz/reviewtrolley` → `get_page_text`. Parse into items
  (name, size, price-each or per-kg, quantity, item-total, special label). See
  `references/woolworths.md`.
- A Foodstuffs store as source: read its cart slide-out (snippet in
  `references/foodstuffs-platform.md`).
- **Persist the parsed basket to `comparison/basket.json` immediately** so a long
  run survives context compaction.

### 2. For each item, match + add at each target store
For each source item, at each target store: search by URL, decide the match, add it.
- Search + read results, choose **exact / similar / flag** — rules in
  `references/matching-and-flags.md`.
- Add with the correct quantity using the **increment-button** method (not typed
  quantities); handle **weight produce** via the `form_input` kg flow; handle the
  **age gate** by trying real-click Add → Yes a couple of times, else flag. All in
  `references/foodstuffs-platform.md`.
- Batch several items per `browser_batch` call to stay quick.
- **Keep going until every source item is added at each store or flagged.** Missing
  one or two items at a store is fine if flagged; abandoning the run is not.

### 3. Reconcile real prices from each cart
Shelf prices ≠ cart prices (club/member/weekly specials apply at the cart). Open
each store's **cart slide-out** and read authoritative per-line prices + subtotal
(snippet in `references/foodstuffs-platform.md`). This also **verifies** every
quantity actually landed — re-check, because typed quantities silently stay at 1.
Reconcile the cart count: source line count should equal items-added + items-flagged.

### 4. Build the interactive report (and record the run's totals)
Assemble one comparison JSON at `comparison/data.json` (schema in the header of
`scripts/build_report.py` and summarised in `references/matching-and-flags.md`) and
run:
```
python3 scripts/build_report.py comparison/data.json -o comparison/comparison-report-<YYYYMMDD-HHMMSS>.html
```
Get the timestamp from `date`. The script owns all styling/interactivity — you only
produce the JSON, never hand-write report HTML. **The same command automatically
appends this run's per-store totals (subtotal + fees + item count) to a history
ledger** — `comparison/totals-history.json` next to the data file by default, or pass
`--history comparison/totals-history.json` explicitly to keep one shared ledger across
runs (recommended, so the trend builds up over time). It de-dupes on the run
timestamp, so make sure `generated` is set to the real run time. Use `--no-history`
to skip recording.

Open the report for the user (`open` on macOS) and summarise: the cheapest basket,
the headline totals, and every flagged item with its reason.

### 5. Build the over-time trend report
Whenever there is more than one run in the ledger (or the user asks how totals are
trending), generate the trend report from the ledger:
```
python3 scripts/build_trends.py comparison/totals-history.json -o comparison/totals-over-time-<YYYYMMDD-HHMMSS>.html
```
It charts each store's basket total across runs (SVG line chart, no dependencies),
with per-store latest/delta cards, a "cheapest league" tally, and a run-by-run
table. Open it and call out the trend (who's trending cheapest, any notable moves).
Use the **same ledger path every time** so history accumulates.

## Output expectations
- An interactive table: per-column **sort**, a **search** box, and **filters**
  (category, match type, which store is cheapest, sales-only, hide-unavailable),
  with live visible-totals and the cheapest cell per row marked.
- **Gently emphasise sale prices** on every store side (source specials and the
  target stores' cart-applied specials).
- Per-store totals at the top; flagged items clearly shown as "n/a" with the reason.

## Guardrails
- Don't change the user's selected store or log in for them.
- The 18+ age gate: confirming it for the user's **own** account on a
  **non-alcoholic** item they listed is reasonable; never bypass CAPTCHAs or add
  real alcohol they didn't ask for. If a gate won't complete after 2–3 tries, flag
  the item (keep its price) and move on rather than hammering.
- You build carts; you do **not** check out or pay. Say so.

## Reference map
- `references/foodstuffs-platform.md` — New World / PAK'nSAVE / Four Square DOM,
  testids, and the working JS snippets for search, add-to-cart, quantities, weight
  produce, the age gate, and cart reconciliation. **The core technical file.**
- `references/woolworths.md` — reading the Woolworths trolley (and Woolworths as a
  best-effort target).
- `references/matching-and-flags.md` — exact/similar/flag decisions, produce, and
  the report JSON schema + how to run the generators.
- `scripts/build_report.py` — the interactive per-run report generator; also
  appends per-store totals to the history ledger (full schema in its header).
- `scripts/build_trends.py` — the over-time trend report from the ledger (ledger
  schema in its header).
