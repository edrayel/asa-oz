"""CMS content schema for editable page sections.

Every editable page is described here as a set of *sections*; each section has
a list of *fields*. Field types:

  text          single-line string
  textarea      multi-line string
  longtext      large multi-line string (rendered as-is)
  checkbox      on/off flag
  image         URL + media-library picker
  list          repeatable group of sub-fields (``item_fields``)
  lines        a textarea where each line becomes one item (list of strings)

``content`` in the DB is stored as JSON: {field_key: value}. For ``list``
fields the value is a JSON array of {sub_key: value}; for ``listlines`` a JSON
array of strings. ``resolve()`` merges stored values over defaults so the site
keeps working with an empty database.
"""

# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

# Owned here so the schema default and the db copy-refresh that replaces the
# previous wording cannot drift apart.
SITE_TAGLINE = (
    "Asa-OZ is a members' ONLY club bringing together adults who want to "
    "explore the world with like-minded people who feel instantly familiar, "
    "like old friends."
)

def _lt(key, label, **kw):
    return dict(key=key, label=label, type="text", **kw)

def _ta(key, label, **kw):
    return dict(key=key, label=label, type="textarea", **kw)

def _rt(key, label, **kw):
    """Rich text field, rendered with a tinyMCE-style editor and stored as HTML."""
    return dict(key=key, label=label, type="richtext", **kw)

def _vid(key, label, **kw):
    """Video embed field. Accepts YouTube/Vimeo URLs and renders an iframe."""
    return dict(key=key, label=label, type="video", **kw)

def _img(key, label, **kw):
    return dict(key=key, label=label, type="image", **kw)

def _imga(key, label, alt_label="Alt text", **kw):
    """Image field with a companion alt-text input."""
    return [
        dict(key=key, label=label, type="image", **kw),
        dict(key=key + "_alt", label=alt_label, type="text", default="", hint="Short description for screen readers and SEO."),
    ]

def _cb(key, label, default=False, **kw):
    return dict(key=key, label=label, type="checkbox", default=default, **kw)

def _sel(key, label, options, default=None, **kw):
    return dict(key=key, label=label, type="select", options=options, default=default or (options[0][0] if options else ""), **kw)

def _blocks(key, label, **kw):
    """Reusable content blocks: testimonial, CTA, feature grid, video."""
    return dict(key=key, label=label, type="content_blocks", **kw)

def _style(key="style", label="Section styling", **kw):
    """Per-section styling: background, text alignment, padding."""
    return dict(key=key, label=label, type="section_style", **kw)


# --------------------------------------------------------------------------
# Reusable content block definitions
# --------------------------------------------------------------------------

BLOCK_TYPES = {
    "testimonial": {
        "label": "Testimonial",
        "icon": "❝",
        "fields": [
            {"key": "quote", "label": "Quote", "type": "textarea", "default": ""},
            {"key": "author", "label": "Author", "type": "text", "default": ""},
            {"key": "role", "label": "Role", "type": "text", "default": ""},
            {"key": "photo", "label": "Photo (URL)", "type": "image", "default": ""},
        ],
    },
    "cta": {
        "label": "Call to Action",
        "icon": "→",
        "fields": [
            {"key": "heading", "label": "Heading", "type": "text", "default": ""},
            {"key": "text", "label": "Text", "type": "textarea", "default": ""},
            {"key": "button_label", "label": "Button label", "type": "text", "default": ""},
            {"key": "button_url", "label": "Button URL", "type": "text", "default": ""},
        ],
    },
    "feature_grid": {
        "label": "Feature Grid",
        "icon": "⊞",
        "fields": [
            {"key": "columns", "label": "Columns", "type": "text", "default": "3", "hint": "2, 3 or 4"},
            {"key": "items", "label": "Items", "type": "list", "default": [],
             "item": {
                 "title": {"label": "Title", "type": "text"},
                 "body": {"label": "Body", "type": "textarea"},
                 "image": {"label": "Image (URL)", "type": "image"},
             }},
        ],
    },
    "video": {
        "label": "Video Embed",
        "icon": "▶",
        "fields": [
            {"key": "url", "label": "Video URL (YouTube / Vimeo)", "type": "video", "default": ""},
            {"key": "caption", "label": "Caption", "type": "text", "default": ""},
        ],
    },
}

# Per-section style options
SECTION_STYLE_OPTIONS = {
    "background": [
        ("none", "None"),
        ("--cream", "Cream"),
        ("--paper", "Paper"),
        ("--espresso", "Espresso (dark)"),
        ("--sage-deep", "Sage"),
        ("custom", "Custom colour…"),
    ],
    "text_align": [
        ("left", "Left"),
        ("center", "Centre"),
        ("right", "Right"),
    ],
    "padding": [
        ("small", "Small"),
        ("medium", "Medium"),
        ("large", "Large"),
        ("none", "None"),
    ],
}


PAGES = {
    "home": {
        "label": "Home page",
        "hint": "Every heading, paragraph, image and list on the homepage is editable below. Changes apply immediately.",
        "sections": [
            {
                "key": "countdown",
                "label": "Countdown bar",
                "fields": [
                    _lt("prefix", "Prefix label", default="Our website launches in"),
                    _lt("mid", "Between timer and date", default="and Asa-OZ goes live on"),
                    _lt("date", "Launch date text", default="Monday, 3 August 2026"),
                ],
            },
            {
                "key": "hero",
                "label": "Hero",
                "fields": [
                    _lt("eyebrow", "Eyebrow", default="Culture • Community • Connection • Asa-OZ"),
                    _lt("title", "Headline", default="Travel with people who feel like old friends"),
                    _rt("lede", "Intro paragraph", default="AsaOZ is a members’ ONLY club bringing together adults who want to explore the world with like-minded people who feel instantly familiar, like old friends."),
                    _rt("supporting", "Supporting copy", default="Join to access hand-picked travel offers, curated group trips, and a welcoming community of curious, open-hearted adults who share your interests and your desire to begin again."),
                    _lt("not_this_title", "“What this is not” title", default="What this is not."),
                    _rt("not_this_body", "“What this is not” body", default="Asa-OZ is a members' travel club, not a tour operator. We bring the offers, the group and the culture. You book your own tickets and travel on your own terms."),
                ],
            },
            {
                "key": "signup",
                "label": "Hero signup",
                "fields": [
                    _cb("enabled", "Show signup form", default=True),
                    _lt("name_placeholder", "Name placeholder", default="Your name (optional)"),
                    _lt("email_placeholder", "Email placeholder", default="Enter your email to join the club"),
                    _lt("button", "Button label", default="Join the club"),
                    _lt("note", "Privacy note", default="No spam. Member offers and updates only, and you can unsubscribe any time."),
                ],
            },
            {
                "key": "marquee",
                "label": "Hero carousel (marquee)",
                "hint": "Photos that scroll behind the hero. Seeded from images/wall-of-memories/ on a fresh site; clear the images to leave the marquee empty.",
                "fields": [
                    _lt("rows", "Rows (1-3)", default="3"),
                    _sel("speed", "Scrolling speed",
                         [("1.4", "Calm (slower)"), ("1", "Normal"), ("0.65", "Lively (faster)")],
                         default="1",
                         hint="How fast the photo rows scroll. Calm is slower and gentler; lively is quicker."),
                    {
                        "key": "images",
                        "label": "Images",
                        "type": "list",
                        "item": {
                            "image": {"label": "Image (URL or media library)", "type": "image", "default": ""},
                        },
                        "default": [],
                    },
                ],
            },
            {
                "key": "how",
                "label": "How it works",
                "fields": [
                    _lt("title", "Heading", default="How it works"),
                    _ta("lede", "Intro", default="Once you join as an Asa-OZ member, here is how it works."),
                    {
                        "key": "steps",
                        "label": "Steps",
                        "type": "list",
                        "item": {
                            "title": {"label": "Title", "type": "text"},
                            "body": {"label": "Body", "type": "text"},
                        },
                        "default": [
                            {"title": "Join as a member", "body": "Sign up and you will receive an order confirmation email plus a separate Asa-OZ welcome email, including how to join our community."},
                            {"title": "Receive member offers", "body": "Exclusive member offers are sent to you by email, or you can sign in to browse them on our website."},
                            {"title": "Choose what you love", "body": "Pick the offers that appeal to you, from stays and experiences to group trips."},
                            {"title": "Book directly", "body": "Book directly with the hotel or travel provider. All members book their own tickets, so you stay in control."},
                        ],
                    },
                    _ta("note", "Footnote", default="Regular Members receive current offers through their welcome email. Group Trip Members start receiving offers with the next Group Trip email, which includes any group trips with availability at the time."),
                ],
            },
            {
                "key": "pillars",
                "label": "What Asa-OZ offers (simple mode off)",
                "fields": [
                    _lt("title", "Heading", default="What Asa-OZ offers"),
                    {
                        "key": "entries",
                        "label": "Pillars",
                        "type": "list",
                        "item": {
                            "title": {"label": "Title", "type": "text"},
                            "body": {"label": "Body", "type": "text"},
                        },
                        "default": [
                            {"title": "Culture", "body": "Food, music, markets and stories, from home and away."},
                            {"title": "Community", "body": "A group to travel with, and to come back to."},
                            {"title": "Trips", "body": "Group journeys with set dates and a WhatsApp group before you fly."},
                            {"title": "Offers", "body": "Member deals on stays, food, activities and events."},
                            {"title": "Two homes", "body": "Ireland, Nigeria and the road between."},
                        ],
                    },
                ],
            },
            {
                "key": "expect",
                "label": "What to expect",
                "fields": [
                    _lt("title", "Heading", default="What to expect"),
                    {
                        "key": "entries",
                        "label": "Items",
                        "type": "list",
                        "item": {
                            "title": {"label": "Title", "type": "text"},
                            "body": {"label": "Body", "type": "textarea"},
                        },
                        "default": [
                            {"title": "Online meetups", "body": "Monthly calls to talk trips, swap tips and meet the group."},
                            {"title": "Culture nights", "body": "Food, music and stories from home and away."},
                            {"title": "Talks and storytelling", "body": "Cooks, writers and travellers in conversation."},
                            {"title": "Group trips", "body": "Set dates, a WhatsApp group, and people to travel with."},
                            {"title": "Membership", "body": "One small yearly fee, offers all year. Cancel any time."},
                        ],
                    },
                ],
            },
            {
                "key": "storeteaser",
                "label": "Store teaser (“things to take with you”)",
                "fields": [
                    _lt("heading", "Heading", default="Things to take with you"),
                ],
            },
            {
                "key": "tools_products",
                "label": "Store section behaviour",
                "fields": [
                    _lt("visit_store_label", "“Visit the store” link", default="Visit the store"),
                ],
            },
            {
                "key": "gallery",
                "label": "Stories (blog teaser)",
                "fields": [
                    _lt("title", "Heading", default="Latest stories"),
                    _lt("cta_label", "Stories link label", default="See more stories"),
                    _lt("wall_button", "Wall button label", default="View the wall of moments"),
                ],
            },
            {
                "key": "testimonials",
                "label": "Testimonials",
                "fields": [
                    *_imga("photo", "Photo (URL or media library)", alt_label="Photo alt text"),
                    _rt("quote", "Quote", default="“I booked one trip and came home with a crowd I would travel with again.”"),
                    _lt("author", "Author", default="Margaret"),
                    _lt("role", "Role", default="Community Member"),
                ],
            },
            {
                "key": "who",
                "label": "Who this is for",
                "fields": [
                    _lt("title", "Heading", default="Who this is for"),
                    _lt("intro", "Intro", default="The experience is for people who:"),
                    {
                        "key": "points",
                        "label": "Points",
                        "type": "listlines",
                        "default": [
                            "Want to see more of the world with good company",
                            "Love food, music and culture",
                            "Want member offers on stays and activities",
                            "Are between trips and need a reason to go",
                            "Travel solo and would rather not do it alone",
                        ],
                    },
                    _rt("tagline", "Tagline", default="Designed for anyone who wants to travel more, and travel better."),
                ],
            },
            {
                "key": "ethos",
                "label": "Ethos (promise block)",
                "fields": [
                    {
                        "key": "avatar",
                        "label": "Avatar (URL or media library)",
                        "type": "image",
                        "default": "/images/founder/WhatsApp%20Image%202026-08-08%20at%2010.57.48.jpeg",
                        "hint": "Small round portrait shown above the promise line. Clear it to hide the avatar.",
                    },
                    _lt("avatar_alt", "Avatar alt text", default="Ifeoma Adaora, founder of Asa-OZ"),
                    _rt("quote", "Quote", default="The best trips start with"),
                    _rt("quote_highlight", "Quote highlight", default="your people"),
                    _lt("from", "Attribution", default="The Asa-OZ Promise"),
                    {
                        "key": "not",
                        "type": "list",
                        "label": "Not-list",
                        "item": {
                            "text": {"label": "Text", "type": "text"},
                            "struck": {"label": "Struck through", "type": "checkbox", "default": True},
                        },
                        "default": [
                            {"text": "Not a tour operator", "struck": True},
                            {"text": "Not a booking site", "struck": True},
                            {"text": "Not a package holiday", "struck": True},
                            {"text": "Just a club worth joining", "struck": False},
                        ],
                    },
                ],
            },
            {
                "key": "founder",
                "label": "Founder (story)",
                "fields": [
                    _lt("name", "Name", default="Ifeoma Adaora"),
                    _lt("role", "Role", default="Founder & Cultural Guide"),
                    {
                        "key": "credentials",
                        "label": "Credentials (one per line)",
                        "type": "listlines",
                        "default": ["25+ years cultural travel", "Cultural Guide", "Community Builder"],
                    },
                    _rt("quote1", "Opening quote", default="My name is Ifeoma Adaora. For more than 25 years I have travelled between Ireland and Nigeria, and I have seen what travel does for people: it opens doors, builds friendships and changes how you see your own life."),
                    _rt("quote2", "Second quote", default="I find the offers, plan the trips and travel with the group, so nobody has to work out who to go with."),
                    _lt("signature", "Signature line", default="Come for the trip. Stay for the people."),
                    _vid("video", "Featured video", hint="Paste a YouTube or Vimeo URL to embed a video."),
                    _lt("more", "More-about link label", default="More about Asa-OZ and the story behind it"),
                ],
            },
            {
                "key": "faq",
                "label": "FAQ section",
                "fields": [
                    _lt("prompt_title", "Heading", default="Questions, answered."),
                    _lt("more", "See-all link label", default="Have more questions? See all of them on the FAQ page"),
                    {
                        "key": "entries",
                        "label": "Questions",
                        "type": "list",
                        "item": {
                            "q": {"label": "Question", "type": "text"},
                            "a": {"label": "Answer", "type": "textarea"},
                        },
                        "default": [
                            {"q": "What is Asa-OZ?", "a": "A members' club for culture, community and travel. Members receive hand-picked offers and group trips, and book directly with the hotel, airline or travel provider."},
                            {"q": "How does it work?", "a": "Join as a member and offers arrive by email, or sign in to browse them on the site. You choose what you love and book directly with the provider. Regular Members get current offers in their welcome email; Group Trip Members start receiving offers with the next Group Trip email."},
                            {"q": "How much does it cost?", "a": "Regular Membership is €10 a year, Group Trip Membership is €12, and both together are €18."},
                            {"q": "Can I come on a group trip on my own?", "a": "Yes, and many of our members do. Solo travellers are the heart of the club, and every trip has a WhatsApp group so you can meet everyone before you fly."},
                            {"q": "Do you sell travel packages?", "a": "No. Asa-OZ is not a travel-booking site. All members book their own tickets and pay the provider directly. We bring you the offers and the community."},
                        ],
                    },
                ],
            },
            {
                "key": "pricing",
                "label": "Membership plans",
                "fields": [
                    _lt("title", "Heading", default="Membership"),
                    _lt("lede", "Lede", default="Two memberships, one small yearly fee. Join the club and start receiving member offers."),
                    _lt("cta_label", "Button label", default="Join now"),
                    {
                        "key": "cards",
                        "label": "Plans",
                        "type": "list",
                        "item": {
                            "name": {"label": "Name", "type": "text"},
                            "price": {"label": "Price (per year)", "type": "text", "default": "€10"},
                            "note": {"label": "Note", "type": "text"},
                            "badge": {"label": "Badge text (empty = none)", "type": "text", "default": ""},
                            "features": {"label": "Included (one per line)", "type": "listlines", "default": []},
                        },
                        "default": [
                            {"name": "Regular Membership", "price": "€10",
                             "note": "Offers, community and everyday savings.",
                             "badge": "",
                             "features": [
                                 "Member offers every month, sent straight to your inbox",
                                 "Exclusive deals on stays, food, markets and cultural events",
                                 "Ireland meetups and community nights",
                                 "Private members group and community chat",
                                 "Trip news before anyone else",
                             ]},
                            {"name": "Group Trip Membership", "price": "€12",
                             "note": "Meet the community and travel together.",
                             "badge": "",
                             "features": [
                                 "Join group trips to Nigeria, West Africa, Ireland and beyond",
                                 "Meet and travel with other members",
                                 "Most members travel solo, so you are never on your own",
                                 "Trip WhatsApp group and a video call before you fly",
                                 "More trips, more often: busy months, not quiet ones",
                             ]},
                            {"name": "Both Memberships", "price": "€18",
                             "note": "Everything in both, for less than you would pay separately.",
                             "badge": "Best value",
                             "features": [
                                 "Everything in Regular and Group Trip",
                                 "Ireland and international trips",
                                 "Member offers every month",
                                 "Priority places on group trips",
                                 "Save on stays, food and activities",
                             ]},
                        ],
                    },
                    _rt("disclaimer_note", "Disclaimer", default="One yearly fee per membership. Cancel any time. Prices shown are illustrative until launch."),
                ],
            },
            {
                "key": "feedback",
                "label": "Feedback form",
                "fields": [
                    _lt("title", "Heading", default="Share your thoughts"),
                    _lt("lede", "Lede", default="Have a suggestion, question, or piece of feedback? We read every message and use it to shape what comes next."),
                    _lt("submit", "Submit label", default="Send feedback"),
                    _lt("topic_label", "Topic label", default="Topic"),
                    _lt("topic_placeholder", "Topic placeholder", default="Select a topic..."),
                    _lt("feedback_label", "Feedback label", default="Your feedback"),
                    _lt("feedback_placeholder", "Feedback placeholder", default="Tell us what you think..."),
                    {
                        "key": "categories",
                        "label": "Topics",
                        "type": "listlines",
                        "default": [
                            "Pricing / Membership",
                            "Website content",
                            "Journey / Experience",
                            "Navigation / UX",
                            "Other",
                        ],
                    },
                ],
            },
            {
                "key": "custom_blocks",
                "label": "Custom content blocks",
                "hint": "Add reusable blocks such as testimonials, calls to action, feature grids and videos, then reorder them freely.",
                "fields": [
                    _blocks("blocks", "Content blocks"),
                    _style(),
                ],
            },
        ],
    },
    "about": {
        "label": "About page",
        "hint": "Every heading, paragraph, image and list on the About page is editable below. Changes apply immediately.",
        "sections": [
            {
                "key": "hero",
                "label": "Hero",
                "fields": [
                    _lt("eyebrow", "Eyebrow", default="About Asa-OZ"),
                    _lt("title", "Headline", default="Culture, community and the journeys between."),
                    _ta("lede", "Intro paragraph", default="Asa-OZ is a members' club for culture, community and travel. Join for hand-picked offers and group trips, and travel with a crowd that feels like home."),
                ],
            },
            {
                "key": "why",
                "label": "Why Asa-OZ exists",
                "fields": [
                    _lt("heading", "Heading", default="Why Asa-OZ exists"),
                    {
                        "key": "paragraphs",
                        "label": "Paragraphs",
                        "type": "listlines",
                        "default": [
                            "Travel changes when you have people to share it with. Most of us keep a list of places we mean to see and never quite get there, because going alone is harder than it sounds.",
                            "Asa-OZ exists to close that gap. It is a club that brings culture, community and travel together, so there is always somewhere to go and someone to go with.",
                        ],
                    },
                ],
            },
            {
                "key": "what",
                "label": "What Asa-OZ is",
                "fields": [
                    _lt("heading", "Heading", default="What Asa-OZ is"),
                    _lt("intro", "Intro", default="Asa-OZ brings people together around five things:"),
                    {
                        "key": "pillars",
                        "label": "Values",
                        "type": "list",
                        "item": {
                            "name": {"label": "Name", "type": "text"},
                            "body": {"label": "Body", "type": "text"},
                        },
                        "default": [
                            {"name": "Culture", "body": "food, music, markets and stories, from home and away."},
                            {"name": "Community", "body": "a group to travel with, and to come back to."},
                            {"name": "Trips", "body": "group journeys with set dates and a WhatsApp group before you fly."},
                            {"name": "Offers", "body": "member deals on stays, food, activities and events."},
                            {"name": "Two homes", "body": "Ireland, Nigeria and the road between."},
                        ],
                    },
                    _lt("closing", "Closing line", default="This is not about escaping your life. It is about seeing more of it."),
                ],
            },
            {
                "key": "film",
                "label": "The film",
                "hint": "The portrait film sits between the “What Asa-OZ is” and “Who it is for” copy.",
                "fields": [
                    _cb("enabled", "Show the film", default=True),
                    _lt("kicker", "Kicker", default="The film"),
                    _lt("summary", "Summary line", default="What Asa-OZ is, and who it is for. One minute."),
                    _lt("source", "Video file or direct URL",
                        default="/images/journeys/about-asa-oz-short.mp4",
                        hint="A direct .mp4 or .webm link. Files placed in images/journeys/ work as /images/journeys/name.mp4."),
                    _lt("poster", "Poster image",
                        default="/images/journeys/about-asa-oz-short-poster.jpg",
                        hint="Shown before playback and when autoplay is off."),
                    _lt("label", "Accessible label",
                        default="A one minute film about Asa-OZ: what the club is and who it is for."),
                ],
            },
            {
                "key": "feels",
                "label": "What it feels like",
                "fields": [
                    _lt("heading", "Heading", default="What it feels like"),
                    {
                        "key": "paragraphs",
                        "label": "Paragraphs",
                        "type": "listlines",
                        "default": [
                            "Concrete and everyday: shared meals, walking tours, markets, music and long conversations. Real people, real places, real trips.",
                        ],
                    },
                    _sel("speed", "Scrolling speed",
                         [("1.4", "Calm (slower)"), ("1", "Normal"), ("0.65", "Lively (faster)")],
                         default="1.4",
                         hint="How fast the photo rows scroll on this section."),
                    _rt("proof_footnote", "Marquee footnote", default="No renderings, no stock shots. Just meals, markets and conversations from real Asa-OZ trips."),
                ],
            },
            {
                "key": "who",
                "label": "Who it is for",
                "fields": [
                    _lt("heading", "Heading", default="Who it is for"),
                    {
                        "key": "paragraphs",
                        "label": "Paragraphs",
                        "type": "listlines",
                        "default": [
                            "Anyone who wants to see more of the world with good company. Whether you travel solo, are between trips, love food and music, or simply want a group to go with, there is a place for you here.",
                            "You can join on your own. Many do.",
                        ],
                    },
                ],
            },
            {
                "key": "founder",
                "label": "The founder",
                "fields": [
                    _lt("heading", "Heading", default="The founder"),
                    _rt("quote", "Quote", default="You do not need a reason to travel. You just need good company."),
                    {
                        "key": "paragraphs",
                        "label": "Paragraphs",
                        "type": "listlines",
                        "default": [
                            "My name is Ifeoma Adaora, and for almost 30 years I have travelled between Ireland, Nigeria and further afield. I have learned that the kind of travel that matters is not the kind that rushes from one attraction to the next, but the kind that slows you down and roots you in a place and its people.",
                            "Along the way I met a lot of adults who wanted to see more of the world but had nobody to go with, many of them after years of looking after everyone else. Asa-OZ is what I built for them: a club that finds the offers, plans the trips and brings the group together, so nobody has to work out who to travel with.",
                        ],
                    },
                    _lt("story_label", "Read-more label", default="Read the full story"),
                    _lt("story_url", "Read-more link",
                        default="/blog/the-story-behind-asa-oz",
                        hint="Where the full founder story lives. Leave blank to hide the link."),
                    _vid("video", "Featured video",
                         hint="Paste a YouTube or Vimeo URL to embed a video."),
                    _cb("video_enabled", "Show the video", default=False,
                        hint="Off by default. The video appears only when a URL is set above and this is switched on."),
                    _lt("name", "Name", default="Ifeoma Adaora"),
                    _lt("role", "Role", default="Founder & Cultural Guide"),
                    {
                        "key": "photo",
                        "label": "Portrait (sits right of the story)",
                        "type": "image",
                        "default": "/images/founder/WhatsApp%20Image%202026-08-08%20at%2010.59.58%20(1).jpeg",
                        "hint": "Shown to the right of the story on wide screens, below it on small ones. Clear it to hide the portrait.",
                    },
                    _lt("photo_alt", "Portrait alt text", default="Ifeoma Adaora, founder of Asa-OZ"),
                ],
            },
            {
                "key": "not",
                "label": "What Asa-OZ is not",
                "fields": [
                    _lt("heading", "Heading", default="What Asa-OZ is not"),
                    {
                        "key": "paragraphs",
                        "label": "Paragraphs",
                        "type": "listlines",
                        "default": [
                            "Asa-OZ is a members' club. It is not a tour operator, a travel agency or a booking site.",
                            "We do not sell travel packages. All members book their own tickets, and Asa-OZ brings the offers, the community and the hosting that make a trip worth taking.",
                        ],
                    },
                ],
            },
            {
                "key": "cta",
                "label": "End call to action",
                "fields": [
                    _lt("line", "Line", default="Ready to see where we are going next?"),
                    _lt("join_label", "Join button", default="Join the club"),
                    _lt("contact_label", "Contact button", default="Contact us"),
                ],
            },
        ],
    },
    "faq": {
        "label": "FAQ page",
        "hint": "Every heading, paragraph and question below is editable. Changes apply immediately.",
        "sections": [
            {
                "key": "hero",
                "label": "Hero",
                "fields": [
                    _lt("eyebrow", "Eyebrow", default="FAQ"),
                    _lt("title", "Headline", default="Questions, answered."),
                    _ta("lede", "Intro paragraph", default="Everything you might want to know before you join the club."),
                ],
            },
            {
                "key": "entries",
                "label": "Questions & answers",
                "fields": [
                    {
                        "key": "faqs",
                        "label": "Questions",
                        "type": "list",
                        "item": {
                            "group": {"label": "Section (leave blank for none)", "type": "text", "default": ""},
                            "q": {"label": "Question", "type": "text"},
                            "a": {"label": "Answer", "type": "textarea"},
                        },
                        "default": [
                            {"group": "Getting started", "q": "What is Asa-OZ?", "a": "Asa-OZ is a members' club for culture, community and travel. Members receive hand-picked offers and group trips, and book directly with the hotel, airline or travel provider."},
                            {"group": "Getting started", "q": "What happens when I join?", "a": "You'll get an order confirmation email straight away, then a separate Asa-OZ welcome email. The welcome email explains how the club works, how to access member offers, which membership you have, and how to join our community."},
                            {"group": "Getting started", "q": "How does it work?", "a": "Offers are sent to members by email, or you can sign in to browse them on our website. You choose the offers you love and book directly with the provider. Regular Members receive current offers through their welcome email. Group Trip Members start receiving offers with the next Group Trip email, which includes any group trips with availability at the time."},
                            {"group": "Getting started", "q": "Do I need to sign in to see offers?", "a": "No. Everything is emailed to you. Signing in is optional, and it is simply a place to browse current offers in one spot."},
                            {"group": "Getting started", "q": "I haven't received an email. What should I do?", "a": "Check your spam, junk and promotions folders first, as member emails sometimes land there. Searching for info@asa-oz.com usually finds them. If you still can't see anything, contact us and we'll sort it out."},
                            {"group": "Getting started", "q": "When will I get my first email?", "a": "Regular Members receive offer emails every few weeks, and Group Trip Members get a Group Trip email whenever trips open. If you've just joined, give it a day or two. Your welcome email links to the offers we've already shared, so you can start browsing straight away."},
                            {"group": "Your membership", "q": "What is the difference between Regular Membership and Group Trip Membership?", "a": "Regular Membership is for travel you plan yourself: offers on stays, food, activities and cultural events, plus community meetups. Group Trip Membership is for travelling together: set-date trips with other members, a WhatsApp group for each trip, and a video call before you fly."},
                            {"group": "Your membership", "q": "How much does it cost?", "a": "Regular Membership is €10 a year, Group Trip Membership is €12 a year, and both together are €18. One fee, no monthly billing."},
                            {"group": "Your membership", "q": "Is it a rolling subscription?", "a": "Each membership runs for one year. You can cancel at any time, and your membership stays active until the year is up."},
                            {"group": "Your membership", "q": "Can I swap my membership?", "a": "Yes. If you've just joined and picked the wrong one, contact us within four weeks and we'll swap it. After that, you can add or change membership when your year is up."},
                            {"group": "Your membership", "q": "How do I cancel my membership?", "a": "Email us at info@asa-oz.com and we'll cancel it for you. You keep access until the end of your membership year."},
                            {"group": "Group trips", "q": "Can I come on a group trip on my own?", "a": "Yes, and many of our members do. Solo travellers are the heart of the club. It is the easiest way to meet people, and plenty of members book the next trip together."},
                            {"group": "Group trips", "q": "Do all group trips have a WhatsApp group?", "a": "Yes. Every group trip has its own WhatsApp group, so you can meet everyone, ask questions and plan together before you travel."},
                            {"group": "Group trips", "q": "Is there a video call before a trip?", "a": "Yes. We hold an optional video call a few weeks before international trips. It is a chance to meet the group and ask anything. We share a summary in the WhatsApp group afterwards."},
                            {"group": "Group trips", "q": "How is my data protected in the WhatsApp group and calls?", "a": "You are only added when you ask us to, and only after you have joined as a Group Trip Member. Your number is shared within that trip group so members can get to know each other. We never pass your details to anyone else, and you can leave the group once the trip is over."},
                            {"group": "Group trips", "q": "Why can't I send a message in the WhatsApp group?", "a": "The group for your trip may not be open yet. We open groups for international trips a few weeks before departure, and Ireland trips closer to the date."},
                            {"group": "Group trips", "q": "What should I prepare before a group trip?", "a": "Save your booking details and dates, arrange travel insurance, check your passport and any visa requirements, and note your baggage allowance. For Ireland trips, check your travel to the hotel and your check-in times. Then join the WhatsApp group and say hello."},
                            {"group": "Group trips", "q": "Will I need vaccines?", "a": "That depends on your destination. Asa-OZ is not a medical organisation, so please speak to your GP or a travel clinic about what is recommended for where you are going."},
                            {"group": "Group trips", "q": "What happens if a group trip is cancelled?", "a": "Because you book your own flights and stays, any refund or change is handled by the airline, hotel or provider you booked with. We'll tell the group in the WhatsApp group and help where we can."},
                            {"group": "Group trips", "q": "Can I cancel a group trip?", "a": "Yes. Check the cancellation terms of whoever you booked with. Their deposit and fare rules decide what you get back."},
                            {"group": "About Asa-OZ", "q": "Do you sell travel packages?", "a": "No. Asa-OZ is not a travel-booking site. All members book their own tickets and pay the hotel, airline or travel provider directly. We bring you the offers and the community."},
                            {"group": "About Asa-OZ", "q": "What kind of trips are they?", "a": "Culture-first trips: cities, markets, food, music and history, with free time built in. Some are guided, some are more independent, and every trip is described clearly before you book."},
                            {"group": "About Asa-OZ", "q": "Is there an age limit?", "a": "Asa-OZ is for adults. There is no upper age limit, and group trips are adult experiences rather than family holidays."},
                            {"group": "About Asa-OZ", "q": "Where do you travel?", "a": "Ireland, Nigeria, West Africa and beyond. Destinations and dates are shared with Group Trip Members as each trip is confirmed."},
                            {"group": "About Asa-OZ", "q": "Can I join from anywhere?", "a": "Yes. Member offers and the community are open internationally. Some group trips start in Ireland, and you are welcome to join us there."},
                        ],
                    },
                ],
            },
            {
                "key": "cta",
                "label": "End call to action",
                "fields": [
                    _lt("line", "Line", default="Still have a question? We read every message."),
                    _lt("contact_label", "Contact button", default="Contact us"),
                    _lt("join_label", "Join button", default="Join the club"),
                ],
            },
        ],
    },
    "terms": {
        "label": "Terms & Conditions",
        "hint": "Every heading and paragraph on this page is editable below. Changes apply immediately.",
        "sections": [
            {
                "key": "hero",
                "label": "Hero",
                "fields": [
                    _lt("eyebrow", "Eyebrow", default="Terms & Conditions"),
                    _lt("title", "Headline", default="Terms & Conditions"),
                    _ta("lede", "Intro paragraph", default="A few straightforward points about how Asa-OZ works."),
                ],
            },
            {
                "key": "blocks",
                "label": "Sections",
                "fields": [
                    {
                        "key": "sections",
                        "label": "Sections",
                        "type": "list",
                        "item": {
                            "heading": {"label": "Heading", "type": "text"},
                            "body": {"label": "Body", "type": "textarea"},
                        },
                        "default": [
                            {"heading": "About this website", "body": "This website is operated by Ifeoma travelled as Asa-OZ, run as a community and cultural venture. Contact email: info@asa-oz.com. Registered: Ireland."},
                            {"heading": "What Asa-OZ offers", "body": "Asa-OZ is a members' club for culture, community and travel. It brings people together through online sessions, community gatherings, member offers and group trips. It does not sell travel packages. All members book their own tickets directly with the hotel, airline or travel provider."},
                            {"heading": "What Asa-OZ is not", "body": "Asa-OZ is a members' club, not a tour operator, travel agency or medical service. We do not sell travel packages. Nothing on this site is medical or therapeutic advice. If you need professional support, please contact a qualified professional."},
                            {"heading": "Payments & refunds", "body": "Refunds apply to paid events and trips.\n• Full refund available up to 48 hours before the event.\n• No refund within 48 hours of the event start.\nPlaces are limited and can fill quickly, so we recommend booking early."},
                            {"heading": "Bookings", "body": "Bookings are confirmed by email. There is no instant online booking. Enquiries are handled personally."},
                            {"heading": "Privacy", "body": "We collect only the information you choose to share (such as your email) and use it to respond and to keep you informed. We do not sell personal data. This site sets only essential cookies until you choose otherwise."},
                            {"heading": "Content & photography", "body": "Some images are placeholders or stock photography used in the interim before photos from real experiences are available."},
                            {"heading": "Changes to these terms", "body": "These terms may be updated as Asa-OZ grows. The latest version will always be available on this page."},
                        ],
                    },
                ],
            },
            {
                "key": "note",
                "label": "Legal note",
                "fields": [
                    _ta("note", "Note", default="If you have any questions about these terms, please contact info@asa-oz.com."),
                ],
            },
        ],
    },
    "privacy": {
        "label": "Privacy Notice",
        "hint": "Every heading and paragraph on this page is editable below. Changes apply immediately.",
        "sections": [
            {
                "key": "hero",
                "label": "Hero",
                "fields": [
                    _lt("title", "Headline", default="Privacy Notice"),
                ],
            },
            {
                "key": "body",
                "label": "Content",
                "fields": [
                    _ta("intro", "Intro", default="This privacy notice explains how Asa-OZ collects, uses, and protects your personal information when you use our website."),
                    {
                        "key": "sections",
                        "label": "Sections",
                        "type": "list",
                        "item": {
                            "heading": {"label": "Heading", "type": "text"},
                            "body": {"label": "Body", "type": "textarea"},
                        },
                        "default": [
                            {"heading": "1. Who we are", "body": "Asa-OZ is a members' club for culture, community and travel. For privacy questions, please contact us at info@asa-oz.com."},
                            {"heading": "2. What information we collect", "body": "We collect only the information you choose to provide, such as:\n• Your name and email address when you join the club or contact us\n• Your message when you use the contact form\n• Booking preferences when you request a discovery call or order from our store\nWe process payments only through our payment provider (Stripe). We do not store your card details."},
                            {"heading": "3. How we use your information", "body": "We use your information to:\n• Respond to your enquiries\n• Add you to our member list and keep you posted\n• Arrange discovery calls and bookings\n• Process store orders and deliver what you purchase\n• Improve our website and services"},
                            {"heading": "4. Cookies", "body": "We use strictly necessary cookies to make the site work. With your consent, we may use analytics cookies to understand how visitors find us. You can accept or reject non-essential cookies using the cookie banner."},
                            {"heading": "4a. Advertising (Google AdSense)", "body": "We use Google AdSense to display ads. AdSense uses cookies to serve ads based on a user's prior visits to our site or other sites on the Internet. Google's use of advertising cookies enables it and its partners to serve ads based on your visit to our site and/or other sites on the Internet. You may opt out of personalised advertising by visiting Google Ads Settings (https://adsettings.google.com). You can also opt out of certain third-party vendors' use of cookies for personalised advertising by visiting www.aboutads.info. The AdSense programme is governed by Google's own policies, available at https://policies.google.com/technologies/ads."},
                            {"heading": "5. Your rights", "body": "You have the right to access, correct, or delete your personal information. To exercise these rights, email us at info@asa-oz.com."},
                            {"heading": "6. Data security", "body": "We take reasonable measures to protect your information. Forms you submit are stored securely so we can respond; payment details never touch our servers."},
                            {"heading": "7. Changes to this notice", "body": "We may update this notice from time to time. The latest version will always be available on this page."},
                        ],
                    },
                ],
            },
        ],
    },
    "contact": {
        "label": "Contact page",
        "hint": "Every heading, paragraph and label on the Contact page is editable below. Changes apply immediately.",
        "sections": [
            {
                "key": "hero",
                "label": "Hero",
                "fields": [
                    _lt("eyebrow", "Eyebrow", default="Contact"),
                    _lt("title", "Headline", default="We’d love to hear from you."),
                    _ta("lede", "Intro paragraph", default="A suggestion, a question, or a note for the founder. Every message is read."),
                ],
            },
            {
                "key": "info",
                "label": "Contact details card",
                "fields": [
                    _lt("heading", "Heading", default="Get in touch"),
                    _lt("email_label", "Email label", default="Email:"),
                    _lt("email", "Email address", default="info@asa-oz.com"),
                    _lt("phone_label", "Phone label", default="Phone:"),
                    _lt("call_label", "Discovery-call line", default="Prefer to talk first? Book a discovery call using the button at the top of the page."),
                    _lt("location_label", "Location label", default="Find us:"),
                    _lt("location", "Location", default="Ireland, with plans to expand."),
                    _lt("legal_line", "Legal line", default="Sole Trader: Ifeoma t/a Asa-OZ · Ireland"),
                ],
            },
            {
                "key": "form",
                "label": "Message form",
                "fields": [
                    _lt("name_label", "Name label", default="Name"),
                    _lt("name_placeholder", "Name placeholder", default="Your name"),
                    _lt("email_label", "Email label", default="Email"),
                    _lt("email_placeholder", "Email placeholder", default="you@example.com"),
                    _lt("message_label", "Message label", default="Message"),
                    _lt("message_placeholder", "Message placeholder", default="How can we help?"),
                    _lt("submit", "Submit label", default="Send message"),
                ],
            },
        ],
    },
    "sitewide": {
        "label": "Site-wide",
        "hint": "Contact details and footer/legal copy shown across every page.",
        "sections": [
            {
                "key": "site",
                "label": "Site-wide copy",
                "fields": [
                    _lt("tagline", "Footer tagline", default=SITE_TAGLINE),
                    _lt("email", "Contact email", default="info@asa-oz.com"),
                    _lt("phone", "Contact phone", default="+353 87 258 9943"),
                    _lt("legal", "Legal line (footer)", default="Sole Trader: Ifeoma t/a Asa-OZ · Ireland"),
                    _lt("rc", "Registration number line (footer)", default="RC No: Not applicable (sole trader)"),
                ],
            },
        ],
    },
    "store": {
        "label": "Store",
        "hint": "Headings and intro copy for the store and product pages.",
        "sections": [
            {
                "key": "store",
                "label": "Store copy",
                "fields": [
                    _lt("hero_title", "Store hero title", default="Things to take with you"),
                    _ta("hero_lede", "Store hero lede", default="Journals, guides, prints and keepsakes from the places we go. Take a piece of the trip home with you."),
                    _lt("similar_title", "“You may also like” title (product pages)", default="You may also like"),
                ],
            },
        ],
    },
    "booking": {
        "label": "Booking",
        "hint": "Labels, placeholders, validation messages and confirmation copy for the discovery-call booking form.",
        "sections": [
            {
                "key": "booking",
                "label": "Booking call form",
                "fields": [
                    _lt("label", "Header button label", default="Book a discovery call"),
                    _lt("submit", "Submit button", default="Request booking"),
                    _lt("cancel", "Cancel button", default="Cancel"),
                    _lt("full_name", "Full name label", default="Full name"),
                    _lt("email", "Email label", default="Email"),
                    _lt("phone", "Phone label", default="Phone"),
                    _lt("date", "Preferred date label", default="Preferred date"),
                    _lt("time", "Preferred time label", default="Preferred time"),
                    _lt("topic", "Topic label", default="What would you like to discuss?"),
                    _lt("placeholder_full", "Full name placeholder", default="Your full name"),
                    _lt("placeholder_email", "Email placeholder", default="you@example.com"),
                    _lt("placeholder_phone", "Phone placeholder", default="+353 ..."),
                    _lt("placeholder_topic", "Topic placeholder", default="Tell us a little about what you are looking for..."),
                    _lt("err_name", "Name error message", default="Please enter your name."),
                    _lt("err_email", "Email error message", default="Please enter a valid email."),
                    _lt("err_date", "Date error message", default="Please choose a date."),
                    _lt("err_time", "Time error message", default="Please choose a time."),
                    _lt("confirm_title", "Confirmation title", default="You’re in"),
                    _ta("confirm_body", "Confirmation body (use {email} for the contact address)", default='We’ll be in touch within 24 hours to confirm your discovery call. If you need to reach us sooner, please email <a href="mailto:{email}" style="color:var(--sage-deep);text-decoration:underline;text-underline-offset:2px;">{email}</a>.'),
                    _lt("confirm_close", "Confirmation close button", default="Close"),
                ],
            },
        ],
    },
    "blog": {
        "label": "Stories",
        "sections": [
            {
                "key": "hero",
                "label": "Stories page",
                "fields": [
                    _lt("title", "Heading", default="Stories"),
                    _ta("lede", "Intro", default="Reports from the road, written by members and the Asa-OZ team."),
                    _rt("cta", "Call to action", default="Have a trip worth telling? Send us your story."),
                ],
            },
        ],
    },
    # Copy for the automated emails. Behaviour (on/off) lives in Settings; the
    # layout lives in templates/emails/. Bodies are textareas, not richtext:
    # richtext is sanitised for page HTML and would strip email markup.
    "emails": {
        "label": "Emails",
        "hint": "Wording for the automatic emails. Blank lines start a new paragraph.",
        "sections": [
            {
                "key": "newsletter_confirm",
                "label": "Newsletter: confirm your email",
                "fields": [
                    _lt("subject", "Subject", default="Confirm your email | Asa-OZ"),
                    _lt("heading", "Heading", default="One click and you are in"),
                    _ta("body", "Body", default="Thanks for asking to join the Asa-OZ list.\n\nConfirm your email address and we will send you member offers, group trip dates and stories from the road."),
                    _lt("button", "Button label", default="Confirm my email"),
                    _lt("signoff", "Sign off", default="Ifeoma, Asa-OZ"),
                ],
            },
            {
                "key": "newsletter_welcome",
                "label": "Newsletter: welcome",
                "fields": [
                    _lt("subject", "Subject", default="You are on the list | Asa-OZ"),
                    _lt("heading", "Heading", default="You are on the list"),
                    _ta("body", "Body", default="Your email is confirmed, so you will hear from us when new offers and group trips are ready.\n\nIn the meantime, the Stories page has reports from members and from the team."),
                    _lt("signoff", "Sign off", default="Ifeoma, Asa-OZ"),
                ],
            },
            {
                "key": "contact_ack",
                "label": "Contact form: acknowledgement",
                "fields": [
                    _lt("subject", "Subject", default="We have your message | Asa-OZ"),
                    _lt("heading", "Heading", default="Thanks for writing to us"),
                    _ta("body", "Body", default="We have your message and we will reply as soon as we can.\n\nIf it is urgent, you can call us instead."),
                    _lt("signoff", "Sign off", default="Ifeoma, Asa-OZ"),
                ],
            },
            {
                "key": "booking_confirm",
                "label": "Discovery call: confirmation",
                "fields": [
                    _lt("subject", "Subject", default="Your discovery call | Asa-OZ"),
                    _lt("heading", "Heading", default="Your call is booked"),
                    _ta("body", "Body", default="Thanks for booking a discovery call. Here are the details we have.\n\nIf anything needs to change, just reply to this email."),
                    _lt("signoff", "Sign off", default="Ifeoma, Asa-OZ"),
                ],
            },
            {
                "key": "order_confirm",
                "label": "Order: confirmation",
                "fields": [
                    _lt("subject", "Subject", default="Your Asa-OZ order | Asa-OZ"),
                    _lt("heading", "Heading", default="Your order has been received"),
                    _ta("body", "Body", default="Thank you. Here is what you asked for.\n\nWe will be in touch by email with the next steps. Members book their own travel directly with the provider, so nothing here is a ticket."),
                    _lt("signoff", "Sign off", default="Ifeoma, Asa-OZ"),
                ],
            },
            {
                "key": "story_ack",
                "label": "Story submission: acknowledgement",
                "fields": [
                    _lt("subject", "Subject", default="We have your story | Asa-OZ"),
                    _lt("heading", "Heading", default="Thanks for sending your story"),
                    _ta("body", "Body", default="We have it and we will read it properly. If we publish it on the Stories page, we will be in touch first."),
                    _lt("signoff", "Sign off", default="Ifeoma, Asa-OZ"),
                ],
            },
            {
                "key": "footer",
                "label": "Email footer",
                "fields": [
                    _ta("legal", "Legal line", default="Sole Trader: Ifeoma t/a Asa-OZ, Ireland. RC No: Not applicable (sole trader)."),
                    _ta("note", "Footer note", default="You received this email because you contacted Asa-OZ or joined the club at asa-oz.com."),
                    _lt("unsubscribe_label", "Unsubscribe link label", default="Unsubscribe from the newsletter"),
                    _lt("contact_label", "Contact link label", default="Contact us"),
                ],
            },
        ],
    },
}

# --------------------------------------------------------------------------
# Resolver
# --------------------------------------------------------------------------

def _default_style():
    return {"background": "none", "background_custom": "", "text_align": "left", "padding": "medium"}


def _flatten_fields(fields):
    """Flatten a field list that may contain nested lists (from _imga groups)."""
    flat = []
    for f in fields:
        if isinstance(f, list):
            flat.extend(f)
        else:
            flat.append(f)
    return flat


def default_content(section):
    """Construct the default values dict for a schema section."""
    out = {}
    for f in _flatten_fields(section["fields"]):
        if f["type"] == "list":
            defaults = []
            for item in f.get("default", []):
                merged = {}
                for sub_key, sub in f["item"].items():
                    merged[sub_key] = item.get(sub_key, sub.get("default", ""))
                defaults.append(merged)
            out[f["key"]] = defaults
        elif f["type"] == "listlines":
            out[f["key"]] = list(f.get("default", []))
        elif f["type"] == "content_blocks":
            out[f["key"]] = f.get("default", [])
        elif f["type"] == "section_style":
            out[f["key"]] = _default_style()
        else:
            out[f["key"]] = f.get("default", "")
    return out


def resolve(page_name, stored):
    """Merge stored DB content onto schema defaults for a page.

    ``stored`` is {section_key: {"content": {...}, "active": bool}}.
    Returns {section_key: {"active": bool, **field_values}}.
    """
    page = PAGES.get(page_name)
    if not page:
        return {}
    out = {}
    for section in page["sections"]:
        key = section["key"]
        data = (stored.get(key) or {}).get("content") or {}
        merged = default_content(section)
        for sk, sv in data.items():
            merged[sk] = sv
        out[key] = {"active": bool((stored.get(key) or {}).get("active", True)), **merged}
    return out