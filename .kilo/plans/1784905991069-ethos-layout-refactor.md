# Ethos Section Layout Refactor

## Context
The `.ethos` section currently uses a 2-column grid (`grid-template-columns: 1.1fr 1fr; align-items: center`). The right column (founder narrative) is much taller than the left (quote + promise + not-list). `align-items: center` leaves large empty space above/below the left column, making the layout feel unbalanced.

## Research Findings
Browsed editorial/magazine layouts for long-form founder stories. Two patterns stood out as compatible with AsaOZ’s design system:

1. **Sticky sidebar** (Shadcn blog + minimalist editorial grids): Wide reading column left, sticky metadata/aside right. The aside stays visible while the main narrative scrolls, creating a "compass" effect.
2. **Asymmetric callout column** (Chun layout, Design Rails editorial): 65/35 or 40/60 split with the shorter content given visual weight via borders/sticky positioning.

## Recommended Approach: Sticky Editorial Aside
Flip the visual weight to the **left column** as a sticky promise card, with the **founder story as the primary reading column on the right**.

### What changes
- **Grid**: Keep `.ethos` as a 2-column grid, but change `align-items` from `center` to `start`.
- **Left column**: Add `position: sticky; top: clamp(2rem, 5vh, 4rem);` so the AsaOZ Promise and not-list stay anchored while scrolling.
- **Visual separator**: Add a subtle right border (`1px solid rgba(111, 90, 63, 0.18)`) to the left column to give it editorial sidebar weight.
- **Mobile**: Stack naturally—promise block above the founder story (`flex-direction: column` at `< 860px`).
- **Preserved**: Fonts (Fraunces/Jost), palette (`--espresso`, `--sage-deep`, etc.), reveal animations, responsive breakpoints, and all existing copy.

### What does NOT change
- No new markup structure—only CSS adjustments to existing `.ethos > div` elements.
- No JavaScript changes.
- No breakpoint additions beyond confirming the existing `@media (max-width: 860px)` collapse handles the stack.

## Decision Needed
**Sticky `top` offset behavior**

- **Recommended**: `top: clamp(2rem, 5vh, 4rem)` — keeps the promise card visible near the top of the viewport while reading the founder story, creating a persistent "north star" feel that matches the brand’s return-to-self theme.
- **Alternative**: No sticky behavior, just `align-items: start` — simpler, but the promise block scrolls away like normal content.

Which do you prefer?

## Validation
- Open `index.html`, scroll to `.ethos` on desktop: left promise block should remain visible while the right founder narrative scrolls.
- Resize to < 860px: columns stack; no sticky behavior needed/expected.
- Verify reveal animation still triggers for both columns.
- Confirm no horizontal overflow from sticky element.
