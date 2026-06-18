# Matching, flagging, and building the report

## Choosing the match for each source item
Work in this order and stop at the first that applies:

1. **Exact** — same brand, product and **size**. Confirm the size against
   `product-subtitle`, not just the name (a brand often has 100g/200g/500g/1L
   variants on one results page). Same price or not, an exact product is an exact
   match.
2. **Similar** — no exact product exists, so pick the closest substitute, judged by
   (in priority order): same **product type/use**, then nearest **size**, then a
   comparable **brand tier**. Some reliable equivalences:
   - Source house brand → the target's house brand (Woolworths own-brand →
     **Pams** at Foodstuffs; and vice versa). Good for milk, vinegar, paper, basics.
   - A mainstream source brand with no target stockist → the nearest mainstream
     brand of the same product (e.g. Meadow Fresh blue-top milk → Anchor Blue).
   - Keep the defining attribute the user clearly chose: "low sugar", "non-alcoholic",
     "25% reduced sugar", "gluten free", a specific flavour. Match that first.
3. **Flag** — only when no same-or-similar product exists at that store. Record the
   reason (e.g. "no caesar salad kit stocked"). Also flag — but still record the
   **price** — when a product exists but the **automation is blocked** (the age
   gate that won't complete; see `foodstuffs-platform.md`).

Tag every row `exact`, `similar`, or `flag` so the report shows it.

## Quantities and multi-buys
Replicate the source quantity exactly. For a source multi-buy ("2 for $4", "Fresh
Deal"), replicate the **unit count** (qty 2), not the deal. Remember the
Foodstuffs quantity gotcha: reach the target qty with the **increment button**, and
**verify it in the cart** — typed quantities don't sync.

## Loose produce (apples, bananas, onions, etc.)
Compare **per kilo**, since that is the only truly comparable figure. Match the
weight where the store sells loose by kg (use the weight flow). If a store only
sells a fixed **prepack bag**, add the bag, record `per_kg` and a note about the
bag size — the bag line will be larger but per-kg is the fair comparison. Note any
weight you couldn't match exactly (e.g. a 0.2kg minimum vs a 0.15kg source amount).

## Prices: shelf vs applied
The card shows the **shelf** price; club/member/weekly specials apply **at the
cart**. Always reconcile final per-line prices and the subtotal **from the cart**
(slide-out snippet in `foodstuffs-platform.md`) before building the report. Record,
per cell: the applied `line` total, `each`, `qty`, whether it was a `sale` (+ a
short `sale_label`, and `was` if you saw a struck price), and `per_kg` for produce.

## Don't stop early
The goal is: **every source item is either added to each target cart, or flagged
with a reason.** Push through all items. It's fine for a store to be missing one or
two items (flag them); it is not fine to abandon the run with items unaccounted for.

## Building the report
Assemble a single comparison JSON (schema documented in the header of
`scripts/build_report.py`) and run:
```
python3 scripts/build_report.py <data.json> -o comparison-report-<stamp>.html
```
The script produces a **self-contained, interactive** HTML report:
- A store summary card per store (subtotal, fees, savings, "cheapest basket" badge).
- One **searchable / sortable / filterable** table: columns are Category, Item,
  Match, then one price column per store. Click a header to sort (price columns sort
  numerically); the search box filters by item or product text; dropdowns filter by
  category, match type and "which store is cheapest"; checkboxes show "sales only"
  or "hide unavailable rows". A live footer recomputes visible totals as you filter.
- The cheapest store on each row gets a green rail; sale prices are gently tinted
  with a small badge; unavailable cells render "n/a" with the flag reason.

You only build the JSON — the script owns all the styling and interactivity, so
don't hand-write report HTML. Use a real timestamp for `generated` and the filename
(get it from `date`; the script defaults to now if you omit it).

### Totals ledger + trend report
`build_report.py` also **appends this run's per-store totals** (subtotal + fees +
item count, plus the run timestamp, source store and cheapest store) to a history
ledger — `totals-history.json` beside the data file by default, or `--history
<path>` for a shared ledger. It de-dupes on the run timestamp, so set `generated`
to the real run time and reuse the **same ledger path every run** so history
accumulates. `--no-history` skips it.

When the ledger has more than one run (or the user wants to see spend over time),
build the trend report:
```
python3 scripts/build_trends.py <totals-history.json> -o totals-over-time-<stamp>.html
```
It charts each store's basket total across runs and tallies who was cheapest. The
ledger handles stores that come and go between runs (gaps in a line).

### Minimal JSON shape (full schema in the script header)
```json
{
  "title": "Grocery Price Comparison",
  "generated": "2026-06-18 18:54 NZST",
  "source_store": "Woolworths",
  "stores": [
    {"key":"ww","name":"Woolworths","subtotal":239.20,"savings":31.92},
    {"key":"nw","name":"New World","location":"Wellington City","subtotal":253.19,"fees":1.50},
    {"key":"pak","name":"PAK'nSAVE","location":"Kilbirnie","subtotal":230.95,"fees":1.00}
  ],
  "items": [
    {"category":"Bakery","item":"Bread Soya & Linseed 750g x2","match":"exact","cells":{
      "ww":{"name":"Freyas Soya Linseed","line":9.32,"each":4.66,"qty":2},
      "nw":{"name":"Freya's Swiss Soya Linseed","line":9.32,"each":4.66,"qty":2,"sale":true,"sale_label":"low price"},
      "pak":{"name":"Freya's Swiss Soya Linseed","line":8.70,"each":4.35,"qty":2}}}
  ]
}
```
Use `"unavailable":true` (plus a `note`) on a cell the store can't match.
