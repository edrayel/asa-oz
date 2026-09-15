# Taste

- Wants consistent layout, alignment, and content width across all pages — subpages should replicate the homepage's sections and match its visual rhythm and constrained content width rather than diverging (e.g., about.html/faq.html were "heavily left-aligned" compared to index.html; later flagged again for content spreading too wide on the left/right instead of matching index's width). Confidence: 0.9

- Prefers slick, minimalist UI treatments (e.g., founder photo refactored into "a carousel that is slick and minimalist") while preserving the existing styling of established components. Confidence: 0.7

- Prefers calm, slower motion for animated/immersive features (e.g., reduce the wall-of-moments default scrolling speed) and seamless, infinite/continuous experiences over finite or jumpy ones. Confidence: 0.7

- Prefers conservative defaults for in-flux features: content/sections that aren't final should be off/hidden by default and only appear when explicitly enabled (e.g., "Make it off/hidden by default for now" for the membership pricing section — hidden unless toggled on in admin), rather than shown until disabled. Confidence: 0.5

- Treats the existing "premium" look as the design system to extend: design changes/refactors (e.g., making the header sticky) must be "beautiful and consistent with the existing premium design and look currently used" rather than introducing a new visual style. Confidence: 0.75

- Cares about pixel-level responsive polish — spacing (e.g., header padding) should be "perfectly balanced across different screen sizes," not tuned to a single breakpoint; expects responsive spacing scales that hold at every width. Confidence: 0.7

- Expects optical centering of text inside UI elements (buttons/pills), not just CSS box centering — e.g., noticed a short uppercase button label sitting "not perfectly center-aligned" and expected it debugged and fixed even though the offset was ~1px (font asc/descent imbalance under `line-height: 1`, plus trailing letter-spacing bias). Treats sub-pixel/optical misalignment as a real defect to fix. Confidence: 0.6

- Expects UI/visual changes to be verified by actually viewing rendered screenshots (vision-enabled image inspection), not just by measuring DOM values/numeric CSS — will point out that vision is available so the agent looks at the captured images rather than only reading back computed styles. Confidence: 0.55

- Expects shared UI elements (e.g., the header cart icon) to be present and functional on every page — notices when an element shows up on only some pages and asks whether that was "intentional or missed," treating any page where the element is missing or dead as an inconsistency to fix rather than acceptable divergence. Confidence: 0.65
