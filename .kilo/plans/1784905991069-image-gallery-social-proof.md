# Image Gallery & Social Proof Integration Plan

## Current State
- Single-page static site: `index.html` (+ inline CSS/JS). No images in repo.
- Design system: Fraunces/Jost, warm palette via CSS custom properties, vanilla JS with IntersectionObserver reveals. No build step.
- Content sources per reference: founder travel archive (interim), stock photos, post-launch member photos/testimonials.

## Goals
1. Add a dynamic image gallery using organic, non-rectangular shapes arranged in an arch/deck spread with arrow navigation, mouse/touch parallax, and responsive behavior.
2. Increase the prominence and impact of social proof without breaking the minimalist, editorial aesthetic.

---

## 1. Dynamic Image Gallery — "The Arch Deck"

### Visual Design Concept
- **Shape Language**: Each image is masked by a smooth blob/SVG path with soft bézier curves rather than a rectangle or circle. Think "polaroid cast in warm clay" — irregular organic forms that feel hand-shaped.
- **Layout Geometry**: Cards are arranged in an arch spread (concave curve up, like a hand of cards fanned). Center card is largest (1.0×), flanking cards decrease slightly (0.85×, 0.72×), outermost cards smallest (0.6×). This matches the existing circular mark and blob motif.
- **Depth/Stacking**: Cards have a subtle paper-shadow (`box-shadow` using `rgba(43,33,24,0.12)`) and very slight rotation offsets (±2–4°) so the deck feels tactile.
- **Responsive Behavior**:
  - Desktop (>860px): Arch spread, up to 5 visible cards, parallax tilt on mouse move.
  - Tablet (560–860px): Flattened arch, 3–4 cards, reduced tilt range.
  - Mobile (<560px): Horizontal swipe deck, 1–2 cards visible, no tilt.

### Interaction Design
- **Mouse Move (Desktop)**: The entire deck tracks pointer position with a subtle 3D tilt (`rotateX`/`rotateY` up to ±6°). Individual cards have a delayed, damped follow so they shift independently within the deck, creating organic fluidity.
- **Touch/Mobile**: Swipe to reveal next/prev card. Active card scales up slightly; inactive cards shrink and fade at the edges.
- **Arrow Navigation**: Left/right chevrons appear on hover (desktop) or always visible (mobile). On click, cards rotate through the deck with a smooth arc transition (not linear slide): the exiting card sweeps outward along the arch perimeter, the entering card arcs inward.
- **Keyboard**: Left/right arrow keys; focus ring follows active card.

### Technical Stack
- **Animation Library**: **GSAP + Flip plugin** (or vanilla IntersectionObserver + CSS transitions if bundle size matters). GSAP is justified here because:
  - `Flip` plugin makes state-based layout transitions trivial (reordering DOM nodes, animating position changes).
  - `quickSetter` for performant mouse-track transforms.
  - Mature, works with vanilla JS (no React dependency).
- **Shape Generation**: Inline SVGs or CSS `clip-path: path(...)` with pre-computed blob paths. Store 4–6 blob variants and assign randomly to cards for variety.
- **Responsive Grid**: CSS Grid for the arch placement. Each card’s `translateY`, `scale`, and `rotate` are set via CSS custom properties (`--arch-y`, `--arch-scale`, `--arch-rotate`) updated by JS mouse/touch handlers.

### Section Placement & Structure
- Add a new `<section class="gallery" aria-label="Moments from AsaOZ">` after **What To Expect** and before **Who AsaOZ Is For**.
- Copy reference: "Photos from cultural experiences, group discussions, nature, heritage sites, shared meals, workshops."
- Heading: inline with existing serif style, e.g., "Moments of return."

---

## 2. Social Proof Amplification

### Strategy A — Testimonial Ribbon (Minimalist)
- Place a **single, full-width testimonial ribbon** between the gallery and the founder section.
- Visual: One large serif pull-quote, centered, with a thin horizontal rule above and below. Author name small caps below. No card, no box, no border radius — just typography and whitespace.
- Interaction: On scroll into view, the quote fades up (`reveal` class). A subtle arrow button lets visitors cycle through 3–5 testimonials (same carousel logic as the gallery, but text-only). Keeps it to one line of visual weight at any moment.

### Strategy B — Identity-Circle Quote Cards (Scattered)
- Reuse the existing **pillars** section: overlay short testimonial micro-quotes (1 sentence) onto the 5 pillar cards using absolute positioning.
- Each quote appears on hover/tap with a gentle scale-up of the pillar and a warm `--sage` background wash. This integrates social proof into an already-existing component, avoiding new visual weight.

### Recommended Approach
- **Use Strategy A** as the primary social proof mechanism. It is clean, editorial, and matches the existing quote styling already used in `.ethos blockquote`.
- **Do not use Strategy B** now: pillars are already doing narrative work; adding hover states to 5 cards risks visual noise. Revisit only if testimonials are abundant post-launch.

### Additional Low-Clutter Additions
- **Trust line under signup form**: "Trusted by adults across Ireland and beyond" — small, muted, below the "Join the journey" button. Becomes visible only after first member photos/testimonials exist (controlled by a CSS class).
- **Founder credential pills**: If certifications/background become available, add them as tiny uppercase pills under the founder name (same `.not-list` treatment), so they reinforce trust without redesign.

---

## 3. Technical Implementation Plan

### A. New CSS
```css
/* Gallery deck base */
.gallery { position: relative; padding: clamp(3rem,8vh,5.5rem) 0; }
.gallery-stage {
  display: grid;
  place-items: center;
  perspective: 1200px;
  height: clamp(360px, 50vh, 520px);
}
.gallery-track {
  display: flex;
  justify-content: center;
  gap: 1.5rem;
  transform-style: preserve-3d;
}
.gallery-card {
  flex: 0 0 auto;
  width: clamp(200px, 28vw, 340px);
  aspect-ratio: 3/4;
  background: var(--cream);
  border-radius: 60% 40% 50% 50% / 50% 60% 40% 50%; /* blob shape */
  box-shadow: 0 12px 40px -16px rgba(43,33,24,0.25);
  overflow: hidden;
  transition: transform 0.6s var(--ease), opacity 0.6s var(--ease);
  will-change: transform;
}
.gallery-card img { width: 100%; height: 100%; object-fit: cover; display: block; }
.gallery-card.active { transform: scale(1) translateY(0); z-index: 2; }
.gallery-card:not(.active) { opacity: 0.7; filter: grayscale(20%); }
.gallery-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255,255,255,0.6);
  border: 1px solid rgba(111,90,63,0.25);
  backdrop-filter: blur(6px);
  border-radius: 100px;
  width: 44px; height: 44px;
  cursor: pointer;
  font-size: 1.1rem;
  color: var(--espresso);
}
.gallery-nav.prev { left: 0; }
.gallery-nav.next { right: 0; }
@media (max-width: 860px) {
  .gallery-stage { height: auto; flex-direction: column; }
  .gallery-card { width: 75vw; max-width: 320px; }
}
```

### B. New HTML
```html
<section class="gallery" aria-label="Moments from AsaOZ">
  <h2 class="reveal">Moments of return</h2>
  <div class="gallery-stage reveal">
    <button class="gallery-nav prev" aria-label="Previous">←</button>
    <div class="gallery-track" id="galleryTrack"></div>
    <button class="gallery-nav next" aria-label="Next">→</button>
  </div>
</section>
<section class="testimonial-ribbon" aria-label="Testimonials">
  <blockquote class="reveal" id="testimonialQuote">…</blockquote>
  <p class="reveal" id="testimonialAuthor">…</p>
</section>
```

### C. New JS
- **Gallery controller**: vanilla class `ArchDeck` in the inline `<script>` block.
  - State: `currentIndex`, `cards[]`, `totalSlides`.
  - Methods: `render()`, `next()`, `prev()`, `goTo(index)`, `applyArchPose(index)`, `onPointerMove(e)`, `onTouchStart/Move/End(e)`.
  - Mouse parallax: throttle `requestAnimationFrame`; update `--tilt-x`, `--tilt-y` on `.gallery-track` via `quickSetter` or direct `style.transform`.
  - Touch: simple swipe threshold (40px) triggers `next/prev`.
  - Keyboard: `keydown` listener for `ArrowLeft/ArrowRight`.
- **Testimonial rotator**: same timing, but fades text opacity/translateY. Auto-advance every 8s unless user interacts.

### D. Content Population
- Interim: 5–6 placeholder images from Unsplash (culture, conversation, travel, nature, heritage) with `loading="lazy"`.
- Post-launch: swap `src` to founder archive and member photos. Alt text follows the brand tone.

### E. Performance & Accessibility
- Images: `loading="lazy"`, `decoding="async"`, explicit `width`/`height` to avoid CLS.
- Reduced motion: `@media (prefers-reduced-motion): reduce` disables tilt and carousel animation; show all cards statically.
- Focus management: arrow buttons have visible focus rings (existing `a:focus-visible` style applies).

---

## 4. Design System Consistency
- All new components reuse existing CSS variables (`--espresso`, `--sage-deep`, `--paper`, `--ease`, `--serif`, `--sans`).
- New section padding uses the same `clamp()` rhythm as existing sections.
- Reveal animations use the existing `.reveal` / `.reveal.in` class mechanism.
- No new font families, no external CSS frameworks.

---

## 5. Validation
1. Desktop > 860px: mouse tilt feels damped and smooth, not jittery. Arch shape is visible and cards do not overlap awkwardly.
2. Tablet 560–860px: cards flatten to a shallow arch; nav arrows remain clickable; swipe not required but works.
3. Mobile < 560px: single-card deck, swipe works, no sticky/tilt behavior.
4. Testimonial ribbon fades in with existing reveal timing; cycling does not interrupt page scroll.
5. `prefers-reduced-motion` media query collapses all animation to static layout.
6. No horizontal overflow (`overflow-x: hidden` remains on `body`).

---

## 6. Open Decisions

**Where should the gallery section live on the homepage?**
- **Recommended**: Between **What To Expect** and **Who AsaOZ Is For**, because social proof naturally softens the transition from "what you get" to "who this is for."
- Alternative: Place after **Meet the Founder** so the founder’s personal photos bookend the testimonial ribbon.

**Which image source do we use for the interim gallery?**
- **Recommended**: Unsplash culture/travel/community images as placeholders, with clear alt text noting they are placeholders until founder archive + member photos are available.
- Alternative: Start with an empty state and a message "Moments will appear here as our community grows" to align with the reference’s placeholder stance.

---

## 7. Risks
- **Over-animation**: The 3D tilt and arch motion are novel; overuse can feel gimmicky against a calm, editorial brand. Mitigation: keep rotation/tilt amplitude subtle (±4–6°), use slow easing (`cubic-bezier(0.22, 1, 0.36, 1)` already in design system).
- **Performance on low-end devices**: `will-change` and `preserve-3d` can tax older GPUs. Mitigation: disable tilt on devices that do not report fine pointer (`matchMedia('(pointer: fine)')`), fall back to static deck.
- **CLS from images**: mitigate with aspect-ratio boxes and explicit dimensions.

---

## 8. Rollout
- Phase 1: Implement gallery shell + testimonial ribbon with placeholder content and vanilla JS.
- Phase 2: Swap in real founder archive and first member photos.
- Phase 3: If post-launch testimonials are abundant, revisit Strategy B (pillar micro-quotes on hover).
