# Plan: Similar / Recommended Products

**Status:** Not yet implemented.

## Goal

Add a “You may also like” section below the main store grid (on `store.html`) and below the product detail (on `product.html`), showing 2–3 related products based on product `type`.

## Scope

- Do not restructure the existing store grid or product detail.
- Do not add new pages or frameworks.
- Use the existing `products` array already defined in both pages.
- Match existing design tokens: `--cream`, `--espresso`, `--cafe-ink`, `--sage-deep`, `border-radius: 18px`, `box-shadow: 0 12px 40px -18px rgba(43,33,24,0.24)`.
- Responsive: degrade cleanly through existing `860px` and `560px` breakpoints.

## Requirements

1. Similarity logic: recommend products of the same `type`, excluding the current product. If fewer than 2 matches exist, fall back to cheapest remaining products.
2. Section title: “You may also like” in existing serif typography.
3. Card layout: reuse `.store-card` classes for visual consistency.
4. Each card: image, badge, name, short description, price, and “Add to cart” button.
5. On `store.html`: render below `.store-section`.
6. On `product.html`: render below `.product-detail`, before the footer.
7. No new JS dependencies; extend the existing inline script only.
8. Accessibility: cards should be focusable/scrollable; buttons should have visible focus states already handled by global `button:focus-visible`.

## Files to modify

- `store.html` — add CSS for `.similar-section` and update JS to render similar products.
- `product.html` — add CSS for `.similar-section` and update JS to render similar products after `renderProduct()`.
