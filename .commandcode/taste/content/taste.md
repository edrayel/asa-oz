# Taste

- Positions Asa-OZ as a members' club for culture, community and travel — the site copy must never read like a travel-booking platform. Members choose offers and "book directly with the hotel or travel provider"; all members book their own tickets, and the site explicitly says it is not a travel-booking site. Confidence: 0.75

- Marketing copy must stay inclusive with no age gate: remove the 45+ / "adults aged 45 and above" framing everywhere (hero lede, About, FAQ, terms, privacy, meta description) and replace it with "members" / "anyone ready for…" language. Confidence: 0.75

- Wants all "wellness-guru" / meditation / spiritual / self-discovery tone stripped from the site's marketing copy — the brand voice must be travel- and experience-focused (like a travel club), not wellness- or identity-flavoured. Confidence: 0.85

- Wants the brand voice to move toward a chosen benchmark site (Rory's Travel Club), but "gradually" — layered onto the existing structure and constraints rather than a wholesale rewrite or a literal copy of the reference. Confidence: 0.6

- When benchmarking against a reference site (e.g. Rory Travel Club), expects the agent to adapt the shape/structure to Asa-OZ's own audience rather than clone it literally — the offering should be tailored to the brand's specific community. Repeats this by pasting a concrete reference URL (e.g. `rorystravelclub.com/pages/faq`) and asking to "repurpose … intelligently", i.e. borrow the underlying structure/question set but rewrite the substance for Asa-OZ, not transcribe. Reiterates this firmly — aligning to a benchmark must never become an "exact copycat/rip-off"; preserving Asa-OZ's own distinct identity is a hard constraint. Confidence: 0.8

- Content and offerings (e.g. membership plans) should be positioned for Asa-OZ's actual audience — a Nigerian-born, Ireland-settled founder with an energetic, community-filled travel experience — and feel affordable/accessible ("cheap") rather than matching the typical tone and pricing of Western/white-oriented travel clubs. Confidence: 0.55

- When adapting copy from a reference site, refuses to carry over the reference's invented/unverifiable statistics and metrics (e.g. Rory's "40% solo travellers", "100+ group trips a year", "20% average savings") — prefers honest, qualitative phrasing ("many of our members travel solo") until real numbers can be substantiated, and expects the agent to flag which claims are being softened. Confidence: 0.6

- Wants the visibility/availability of UI elements and sections — whether prices are shown, whether a store/section appears at all — to be controlled by CMS/admin toggles rather than hardcoded in templates. When a value or section renders unconditionally while other parts of the site honour the setting, treats that as a gap "that requires implementation." Expects a visibility toggle to genuinely gate the whole feature — nav links on every menu (desktop + mobile), the home section, direct routes (e.g. `/store`, `/product/<id>`), and SEO surfaces (sitemaps, robots directives, meta tags) — not just hide one section while leaving links/routes/search indexes live. When handling a feature toggle, defaults the feature to OFF rather than on so nothing is exposed until the admin explicitly enables it. Repeatedly requests hide/show toggles for membership, video embeds, prices, and the whole storefront. Confidence: 0.88

- Never uses dashes (em dashes) in written copy: "Never use dashes in your writing style." Treats them as "complete dead giveaways for AI." Applied broadly — user-facing prose, headings, meta descriptions, `<title>` separators (switched from "Page — Asa-OZ" to "Page | Asa-OZ"), even code comments and docstrings. Confidence: 0.9

- Avoids redundancy in writing: do not say the same thing twice in one sentence (e.g. quoting a button's label verbatim inside a sentence that also names it). Pairs this with the anti-AI-tell goal — copy should read as natural human writing, not repetitive or formulaic. Confidence: 0.8

- When flagging a copy/voice problem, expects the fix swept consistently across the whole site (all templates, CMS defaults, persisted DB sections, and JS fallbacks) rather than patching only the single cited line. Confidence: 0.7

- Prefers one control per behaviour in admin/CMS settings: when two controls have the same effect (e.g. a "Show prices" toggle plus a duplicate "Price display" Public/Hidden select), wants them reconciled into a single source of truth rather than left as ambiguous duplicates. Confidence: 0.55
- Wants the landing page to stay focused and free of duplication with the About page: sections already covered on About (e.g. "Who this is for") should be moved there or removed from Home rather than repeated in both places. Confidence: 0.7
- Prefers lean hero copy capped at about three text blocks and treats extra lines as clutter to be consolidated rather than stacked. Confidence: 0.65
- Prefers long personal stories to live as full entries on the Stories blog while About sections show a short excerpt rewritten to match site webcopy with a read more link to the full entry, rather than publishing the full draft inline. Confidence: 0.75
- Prefers headings and labels that are broadly applicable rather than tied to a single mode or segment: renamed the blog band from "From the road" (transport-specific, not inclusive of other ways of travelling) to a generic "Latest stories". Confidence: 0.6
- Prefers a tightly curated set of published stories rather than a padded blog: asked to delete every post except the real founder story, keeping placeholder/example/dummy entries out of the live content set. Confidence: 0.55
