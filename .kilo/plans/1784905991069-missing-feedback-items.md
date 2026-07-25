# Feedback-v1.md Gap Audit & Implementation Plan

**Source:** `/home/edrayel/dev/asa-oz/feedback/feedback-v1.md`  
**Status:** Pre-audit of what is implemented on the live site vs. what is missing.

---

## Already Implemented (Verified)

| Feedback Item | Site Status |
|---|---|
| Tagline: "Identity • Culture • Belonging" | ✅ eyebrow in hero |
| H1: "Return to Self." | ✅ hero h1 |
| Value proposition + supporting line | ✅ hero lede + supporting |
| "A AsaOZ" typo | ✅ already fixed |
| How It Works (4-step) | ✅ in-page section |
| What To Expect (5 items) | ✅ in-page section |
| Who AsaOZ Is For (5 bullets) | ✅ in-page section |
| Founder bio (Ifeoma Adaora) | ✅ in .founder block |
| Trust note / not therapy disclaimer | ✅ FAQ + earmarked |
| Social proof rotator (text only) | ✅ testimonial ribbon |
| FAQ list (all 14 questions) | ✅ answers present |

---

## Missing / Incomplete

### Tier 1 — Content & UX (implement now)

**1. Founder photograph**  
Feedback §5: "Add a friendly founder photograph alongside this copy."  
Current: `.founder` block is text-only. Insert `<img>` or `<figure>` with consistent `border-radius: 18px`, warm filter, and `loading="lazy"`. Place above the text, beside or inline with the opening paragraph.

**2. Founder credibility details**  
Feedback §5: "years of experience framing, professional background, any certifications/relevant training, media mentions, and organisations/partners."  
Current: bio mentions "more than 25 years" but no credential badges, name-drops, partner logos, or media logos. Add a discrete credential strip or byline enhancements.

**3. Missing CTAs in nav / page**  
Feedback §7: Explore the Experience, Learn More, Meet the Founder, Join the Waitlist.  
Current nav: Journey, Store, Connect. "Join the journey" exists as form button text but not as a nav CTA. "Meet the Founder" has no anchor link. "Explore the Experience" and "Learn More" are absent.

**4. Social proof photos**  
Feedback §9: testimonials with names + photos.  
Current: text-only rotator. Add portrait or event photos alongside each quote (or at least one featured testimonial photo).

**5. /privacy link broken**  
Cookie consent bar links to `/privacy` but the page does not exist. Create `/privacy.html` or remove the link until ready. Same risk for any future `/terms`, `/about`, `/contact` placeholders.

### Tier 2 — Infrastructure (needs decisions/accounts)

**6. Actual social media URLs**  
Feedback §16: Instagram, Facebook, TikTok, YouTube accounts exist as placeholders only. Replace `href="#"` with real URLs when accounts are live.

**7. Footer phone number**  
Feedback §12, §16: "Phone: [to be added]" is still a placeholder. Add real number or remove the line.

**8. Blog / articles section**  
Feedback §14 (SEO topics) and §16. No blog page exists. Requires CMS or static markdown build step. Defer until content strategy is finalised.

**9. Booking flow routing**  
Feedback §15: "Book Now" form routes to WhatsApp/Email. Current CTAs route to `mailto:` only. Add WhatsApp button/link (`https://wa.me/...`) alongside or instead of mailto for discovery calls.

**10. Payment & checkout details**  
Feedback §15: Stripe + Bank Transfer. Current store cart has no payment integration, no bank-details page, and no checkout flow beyond a cart drawer. Defer to payment-provider integration phase.

**11. Maps / location embed**  
Feedback §15: Google Maps embed for event locations. No map exists. Add to a "Contact" or "Where we meet" section when venues are confirmed.

**12. Analytics & pixels**  
Feedback §16: GA, Search Console, Maps API, Facebook Pixel, TikTok Pixel, Google Ads ID. None are injected. Add `<script>` snippets in `<head>` when IDs are available.

### Tier 3 — Nice-to-have / Post-launch

**13. Founder video activate**  
Placeholder already added. Set `FOUNDER_VIDEO_ID` when the YouTube asset is ready.

**14. Event/trip photos**  
Feedback §16: none yet. Use founder's travel archive or stock until first trips are documented.

**15. Brand guidelines finalised**  
Feedback §16. Needed for consistent logos, colour tokens, typography rules across social and print.

---

## Recommended Execution Order

1. Founder photo + credentials strip (Tier 1)
2. Fix /privacy link + nav CTA alignment (Tier 1)
3. Social proof photos (Tier 1)
4. Real social URLs + phone (Tier 2, fast)
5. WhatsApp button + contact/organiser details (Tier 2)
6. Maps embed + payment details (Tier 2, after venues/fees confirmed)
7. Blog + analytics (Tier 3, post-launch)

---

## Responsive Guardrails

All Tier 1 changes must live inside existing `.ethos > .founder` block and respect the `@media (max-width: 860px)` single-column breakpoint already in place. No new breakpoints needed per feedback doc constraints.
