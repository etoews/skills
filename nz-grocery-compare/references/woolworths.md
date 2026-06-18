# Woolworths (woolworths.co.nz)

Woolworths NZ (formerly Countdown) runs its own storefront, separate from the
Foodstuffs platform. In practice it is most often the **source** basket (the
trolley you copy from). Reading the trolley is fully validated; using Woolworths as
an add-to-cart **target** is best-effort (see the end).

## Read the trolley (the usual starting point)
1. Navigate to `https://www.woolworths.co.nz/reviewtrolley` (the user must be
   logged in; their saved trolley loads).
2. Extract with `mcp__claude-in-chrome__get_page_text` — the trolley renders as
   plain text grouped by category, which parses cleanly. (A screenshot only shows
   the summary; `get_page_text` gives the full item list.)

Each item block looks like:
```
<Category>                         e.g. Pantry
[Special | Member Price | <N>% Off | Save $X | Fresh Deal <M> for $Y]   (optional)
<Product name>                     e.g. Arnotts Crackers Cheds
<size> $<unit price>               e.g. Box 250g $1.40 / 100g
$<price> each                      e.g. $3.50 each       (per-unit items)
   — or, for loose produce —
$<X> / 1kg                         e.g. $4.75 / 1kg
$<Y> / ea (approx)                 the approximate each price
Savings: $<Z>                      (only when on special)
Item total: $<total>               e.g. $9.32  (this reflects quantity)
```
Derive **quantity** from `item total ÷ price each`. For weight items, derive
weight from `item total ÷ per-kg price`. The header "N items" is the number of
**distinct lines**, not total units.

Capture per item: category, name, size, price-each (or per-kg), qty, item-total,
and the special label if present. Persist this to a JSON working file early so you
don't lose it.

### Specials vocabulary
`Special` + `N% Off` / `Save $X`, `Member Price`, `Fresh Deal M for $Y` (multi-buy),
`Low Price`. These are the source-store sale prices — mark them so the report can
gently emphasise them, and so you replicate multi-buy quantities correctly.

## Reading a Foodstuffs cart as the source instead
If the source is New World / PAK'nSAVE / Four Square rather than Woolworths, read
its cart slide-out using the reconciliation snippet in `foodstuffs-platform.md`
(it returns name, qty and price per line). Default source is Woolworths unless the
user says otherwise.

## Woolworths as a TARGET (best-effort)
Search: `https://www.woolworths.co.nz/shop/searchproducts?searchTerm=<query>` (the
UI search box also works). Product tiles have their own structure (not the
Foodstuffs testids). Adding to cart works through the tile's "Add to cart" / qty
stepper, driven with the same `realClick` pointer-event approach. This path is not
as battle-tested as the Foodstuffs one, so verify the cart afterwards and fall back
to reading prices only (then flag) if an add won't take. When the user just wants a
price comparison, you can capture Woolworths prices without adding to a cart.
