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
    "Asa-OZ is a members' ONLY club bringing together adults aged 45 and over "
    "who want to explore the world, reconnect with their culture and rediscover "
    "who they are, with like-minded people who feel instantly familiar, like old "
    "friends."
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
                    _lt("title", "Headline", default="Travel with old friends"),
                    _rt("lede", "Intro paragraph", default="AsaOZ is a members' ONLY club bringing together adults aged 45 and over who want to explore the world, reconnect with their culture and rediscover who they are, with like-minded people who feel instantly familiar, like old friends."),
                    _rt("supporting", "Supporting copy", default="Join to access hand-picked travel offers, curated group trips, cultural experiences and reflection circles, and a welcoming community of curious, open-hearted adults who share your interests and your desire to begin again."),
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
                            {"title": "Culture", "body": "Food, music, markets and stories that let you meet your heritage where it lives."},
                            {"title": "Identity", "body": "Cultural identity restoration through travel, story and reflection."},
                            {"title": "Community", "body": "A group to travel with, and to come back to."},
                            {"title": "Trips", "body": "Group journeys with set dates and a WhatsApp group before you fly."},
                            {"title": "Offers", "body": "Member deals on stays, food, activities and events."},
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
                    _rt("quote", "Quote", default="The journeys that change us start with"),
                    _rt("quote_highlight", "Quote highlight", default="a rediscovery of who we were"),
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
                            {"text": "Not therapy or counselling", "struck": True},
                            {"text": "A space for identity, belonging and renewal", "struck": False},
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
                            {"q": "What is Asa-OZ?", "a": "A members' club for adults aged 45 and over who want to travel, reconnect with their culture and rebuild a sense of belonging. Members receive hand-picked offers and group trips, and book directly with the hotel, airline or travel provider."},
                            {"q": "How does it work?", "a": "Join as a member and offers arrive by email, or sign in to browse them on the site. You choose what you love and book directly with the provider. Regular Members get current offers in their welcome email; Group Trip Members start receiving offers with the next Group Trip email."},
                            {"q": "How much does it cost?", "a": "Regular Membership is €20 a year, Group Trip Membership is €30, and both together are €45."},
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
                            "price": {"label": "Price (per year)", "type": "text", "default": "€20"},
                            "note": {"label": "Note", "type": "text"},
                            "badge": {"label": "Badge text (empty = none)", "type": "text", "default": ""},
                            "features": {"label": "Included (one per line)", "type": "listlines", "default": []},
                        },
                        "default": [
                            {"name": "Regular Membership", "price": "€20",
                             "note": "Offers, community and everyday savings.",
                             "badge": "",
                             "features": [
                                 "Member offers every month, sent straight to your inbox",
                                 "Exclusive deals on stays, food, markets and cultural events",
                                 "Ireland meetups and community nights",
                                 "Private members group and community chat",
                                 "Trip news before anyone else",
                             ]},
                            {"name": "Group Trip Membership", "price": "€30",
                             "note": "Meet the community and travel together.",
                             "badge": "",
                             "features": [
                                 "Join group trips to Nigeria, West Africa, Ireland and beyond",
                                 "Meet and travel with other members",
                                 "Most members travel solo, so you are never on your own",
                                 "Trip WhatsApp group and a video call before you fly",
                                 "More trips, more often: busy months, not quiet ones",
                             ]},
                            {"name": "Both Memberships", "price": "€45",
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
                    _ta("lede", "Intro paragraph", default="Asa-OZ is a members' club for adults aged 45 and over, built around travel, cultural identity and genuine belonging. Join for hand-picked offers and group trips, and travel with a crowd that feels like home."),
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
                            "It also changes when you go looking for where you came from. Many of us reach midlife feeling displaced from our own culture, and unsure what the next chapter is meant to look like.",
                            "Asa-OZ exists to close both gaps. It is a club that brings culture, community and travel together, so there is always somewhere to go, someone to go with, and room to rediscover who you are.",
                        ],
                    },
                ],
            },
            {
                "key": "what",
                "label": "What Asa-OZ is",
                "fields": [
                    _lt("heading", "Heading", default="What Asa-OZ is"),
                    _lt("intro", "Intro", default="Asa-OZ brings people together around six things:"),
                    {
                        "key": "pillars",
                        "label": "Values",
                        "type": "list",
                        "item": {
                            "name": {"label": "Name", "type": "text"},
                            "body": {"label": "Body", "type": "text"},
                        },
                        "default": [
                            {"name": "Culture", "body": "food, music, markets and stories that let you meet your heritage where it lives."},
                            {"name": "Identity", "body": "cultural identity restoration, through travel, story and reflection."},
                            {"name": "Community", "body": "a group to travel with, and to come back to."},
                            {"name": "Trips", "body": "group journeys with set dates and a WhatsApp group before you fly."},
                            {"name": "Offers", "body": "member deals on stays, food, activities and events."},
                            {"name": "Home and away", "body": "rooted in Ireland, travelling out to the rest of the world."},
                        ],
                    },
                    _lt("closing", "Closing line", default="This is not about escaping your life. It is about seeing more of it, and seeing yourself again."),
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
                            "Along the way I met a lot of adults over 45 who wanted to see more of the world but had nobody to go with, many of them after years of looking after everyone else. I met women who had lost touch with their own culture, and with the parts of themselves they set aside to get through life. Asa-OZ is what I built for them: a club that finds the offers, plans the trips and brings the group together, so nobody has to work out who to travel with, and nobody has to do the rediscovering alone.",
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
                            {"group": "Getting started", "q": "What is Asa-OZ?", "a": "Asa-OZ is a members' club for adults aged 45 and over who want to travel, reconnect with their culture and rebuild a sense of belonging. Members receive hand-picked offers and group trips, and book directly with the hotel, airline or travel provider."},
                            {"group": "Getting started", "q": "What happens when I join?", "a": "You'll get an order confirmation email straight away, then a separate Asa-OZ welcome email. The welcome email explains how the club works, how to access member offers, which membership you have, and how to join our community."},
                            {"group": "Getting started", "q": "How does it work?", "a": "Offers are sent to members by email, or you can sign in to browse them on our website. You choose the offers you love and book directly with the provider. Regular Members receive current offers through their welcome email. Group Trip Members start receiving offers with the next Group Trip email, which includes any group trips with availability at the time."},
                            {"group": "Getting started", "q": "Do I need to sign in to see offers?", "a": "No. Everything is emailed to you. Signing in is optional, and it is simply a place to browse current offers in one spot."},
                            {"group": "Getting started", "q": "I haven't received an email. What should I do?", "a": "Check your spam, junk and promotions folders first, as member emails sometimes land there. Searching for info@asa-oz.com usually finds them. If you still can't see anything, contact us and we'll sort it out."},
                            {"group": "Getting started", "q": "When will I get my first email?", "a": "Regular Members receive offer emails every few weeks, and Group Trip Members get a Group Trip email whenever trips open. If you've just joined, give it a day or two. Your welcome email links to the offers we've already shared, so you can start browsing straight away."},
                            {"group": "Your membership", "q": "What is the difference between Regular Membership and Group Trip Membership?", "a": "Regular Membership is for travel you plan yourself: offers on stays, food, activities and cultural events, plus community meetups. Group Trip Membership is for travelling together: set-date trips with other members, a WhatsApp group for each trip, and a video call before you fly."},
                            {"group": "Your membership", "q": "How much does it cost?", "a": "Regular Membership is €20 a year, Group Trip Membership is €30 a year, and both together are €45. One fee, no monthly billing."},
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
                            {"group": "About Asa-OZ", "q": "Is there an age limit?", "a": "Asa-OZ is for adults aged 45 and over. There is no upper age limit, and group trips are adult experiences rather than family holidays."},
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
                    _ta("lede", "Intro paragraph", default="The terms that govern your use of the Asa-OZ members' club, its cultural experiences, reflection circles and hosted gatherings."),
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
                            {"heading": "1. Introduction", "body": "These Terms & Conditions (the \"Terms\") govern your use of the Asa-OZ digital membership network, members' club, cultural experiences, reflection circles and nonpackage travel hosting services. By accessing the website or taking part in Asa-OZ activities, you agree to these Terms.\nAsa-OZ is designed for adults aged 45 and over who are seeking cultural identity restoration, community belonging and meaningful companionship.\nAsa-OZ is operated by Ifeoma, trading as Asa-OZ, a sole trader based in Drogheda, Co. Louth, Ireland. Contact us at info@asa-oz.com."},
                            {"heading": "2. Definitions", "body": "\"Asa-OZ\" means the digital membership platform, the cultural programmes and the hosted experiences.\n\"Member\" means any individual with an active subscription.\n\"Events\" means cultural experiences, reflection circles, gatherings and hosted activities.\n\"Nonpackage travel hosting\" means Asa-OZ does not arrange travel, accommodation or transport. Participants organise their own travel logistics.\n\"Platform\" means the digital membership system, the website and our communication channels."},
                            {"heading": "3. Membership eligibility and access", "body": "Membership is open to adults aged 45 and over. There is no upper age limit. To access Asa-OZ services you must:\n• Maintain an active subscription\n• Provide accurate registration information\n• Agree to our Community Conduct Policy\n• Use the platform responsibly and respectfully\nMembership is personal and non-transferable."},
                            {"heading": "4. Subscription fees and billing", "body": "Subscription fees are payable in advance and are non-refundable once activated. Fees may change, and members will receive notice before any change takes effect.\nPayments are processed securely by third-party providers. Asa-OZ does not store card details.\nBookings are confirmed by email. There is no instant online booking, and enquiries are handled personally.\nFailure to maintain payment may result in suspension or termination of membership."},
                            {"heading": "5. Nonpackage travel hosting", "body": "Asa-OZ does not act as a travel agent or tour operator, and does not sell travel packages. Members are responsible for:\n• Booking their own flights, accommodation, transport and insurance\n• Managing visas, documentation and personal travel risks\n• Ensuring they are physically able to participate in the activities they choose\nAsa-OZ provides cultural experiences, reflection circles and companionship only."},
                            {"heading": "6. Events, gatherings and cultural experiences", "body": "Some events require preregistration or an additional fee. Attendance is voluntary and subject to capacity limits.\nHosts may adjust activities for safety, cultural appropriateness or operational reasons.\nMembers must disclose accessibility needs in advance so reasonable accommodations can be arranged.\nAsa-OZ may cancel or reschedule events. Where Asa-OZ cancels, members will receive a credit or refund where the stated window applies."},
                            {"heading": "7. Behaviour and community standards", "body": "Members must:\n• Treat others with respect, dignity and cultural sensitivity\n• Maintain confidentiality within reflection circles\n• Avoid discriminatory, aggressive or exclusionary behaviour\n• Refrain from promoting external businesses or political agendas\n• Follow host instructions during events\nA breach of these standards may result in suspension or termination of membership. The full detail sits in our Community Conduct Policy."},
                            {"heading": "8. Safety and welfare", "body": "Asa-OZ prioritises emotional, cultural and physical safety. Hosts facilitate group dynamics but do not provide medical or psychological services, and nothing we offer is therapy or counselling.\nMembers must ensure they are physically capable of participating and must follow safety instructions during walks, cultural activities and group movement.\nAsa-OZ is not liable for injuries, accidents or incidents arising from personal travel or participation."},
                            {"heading": "9. Privacy and data protection", "body": "Asa-OZ complies with the General Data Protection Regulation. Personal data is used only for membership management, event coordination and communication.\nReflection circles are never recorded.\nMembers may request deletion or correction of their data at any time.\nData is not sold or shared with third parties except essential operational partners.\nThe full policy is on our Privacy Notice page."},
                            {"heading": "10. Intellectual property", "body": "All content, branding, cultural materials and digital resources provided by Asa-OZ are protected by copyright. Members may not:\n• Copy, distribute or reproduce content\n• Use Asa-OZ materials for commercial purposes\n• Record or share reflection circle content\nSome images on this site are placeholders or stock photography used in the interim before photographs from real experiences are available."},
                            {"heading": "11. Refunds and cancellations", "body": "Subscription fees are non-refundable.\nFor paid events and trips:\n• A full refund applies up to 48 hours before the event\n• No refund applies within 48 hours of the event start\n• If Asa-OZ cancels an event, members receive a credit or refund\nNo refunds are given for missed events due to personal travel issues. Places are limited, so we recommend booking early."},
                            {"heading": "12. Hospitality promotion", "body": "Asa-OZ may highlight accommodation or hospitality providers for cultural relevance. These promotions are informational only.\n• Asa-OZ does not act as a booking agent\n• Members engage directly with providers\n• Asa-OZ is not responsible for external services\nAny recommendation is optional and non-binding."},
                            {"heading": "13. Limitation of liability", "body": "Asa-OZ is not liable for:\n• Travel delays, cancellations or disruptions\n• Injuries or incidents during independently arranged travel\n• Loss of personal property\n• Actions of third-party providers\n• Member-to-member interactions\nTo the fullest extent permitted by Irish law, Asa-OZ accepts no liability arising from membership, attendance at events or use of the platform."},
                            {"heading": "14. Termination of membership", "body": "Asa-OZ may suspend or terminate membership for:\n• Breach of these Terms\n• Unsafe or disruptive behaviour\n• Non-payment\n• Misuse of the platform or community spaces\nMembers may cancel their subscription at any time by emailing info@asa-oz.com. Access continues to the end of the paid year, and refunds do not apply."},
                            {"heading": "15. Changes to these terms", "body": "Asa-OZ may update these Terms to reflect operational, legal or safety changes. Members will be notified of significant updates, and the latest version will always be available on this page."},
                            {"heading": "16. Governing law", "body": "These Terms are governed by the laws of Ireland. Any disputes will be handled under Irish jurisdiction."},
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
                    _ta("intro", "Intro", default="Asa-OZ (\"we\", \"our\", \"the Club\") is committed to protecting the privacy and personal data of every member, participant and website user. This notice explains how we collect, use, store and protect your information under the General Data Protection Regulation (GDPR) and Irish data protection law."),
                    {
                        "key": "sections",
                        "label": "Sections",
                        "type": "list",
                        "item": {
                            "heading": {"label": "Heading", "type": "text"},
                            "body": {"label": "Body", "type": "textarea"},
                        },
                        "default": [
                            {"heading": "1. Scope and introduction", "body": "This notice applies to all Asa-OZ digital platforms, membership systems, events, reflection circles, cultural experiences and communications. Asa-OZ is operated by Ifeoma, trading as Asa-OZ, a sole trader in Drogheda, Co. Louth, Ireland, who is the Data Controller and is responsible for all decisions regarding personal data processing.\nAsa-OZ is strictly for adults aged 45 and over. We do not knowingly collect data from anyone under 18."},
                            {"heading": "2. Contact details", "body": "Data Controller: Ifeoma, trading as Asa-OZ, Drogheda, Co. Louth, Ireland.\nEmail: info@asa-oz.com. The address is also provided to members on registration.\nYou may contact us at any time to make a data access request, or to raise a concern."},
                            {"heading": "3. What personal data we collect", "body": "We collect only the information necessary to operate the membership network and deliver cultural identity restoration experiences:\n• Identity data: name, age range, nationality, and cultural background where you choose to share it\n• Contact data: email address and phone number\n• Membership data: subscription status, event attendance and preferences\n• Payment data: processed securely by our payment providers. Asa-OZ does not store card details\n• Community interaction data: messages, posts or contributions within the platform\n• Reflection circle participation: notes on attendance only. No session content is recorded\n• Technical data: IP address, device type, login activity and cookies\nOur booking and store systems also record your booking preferences and order details."},
                            {"heading": "4. Special category data", "body": "Asa-OZ may process limited cultural or identity-related information that you choose to share voluntarily during sessions or at registration. This is handled with strict confidentiality and used only to support cultural identity restoration activities.\nWe do not collect health data or psychological assessments, and we do not ask for sensitive information unless you volunteer it. Hosts are not trained or authorised to provide therapy or counselling."},
                            {"heading": "5. How we use your data", "body": "We process personal data for the following purposes:\n• Membership management\n• Subscription billing and account access\n• Event coordination and communication\n• Cultural identity restoration sessions and reflection circles\n• Community belonging activities\n• Safety and welfare during gatherings\n• Platform security and fraud prevention\n• Legal compliance and recordkeeping\nWe do not use your data for automated decision-making or profiling."},
                            {"heading": "6. Legal basis for processing", "body": "Under the GDPR we rely on the following lawful bases:\n• Contract: to provide membership services and digital access\n• Consent: for optional cultural background information, cookies and marketing communications. You may withdraw consent at any time\n• Legitimate interest: to maintain community safety and platform integrity\n• Legal obligation: for tax, accounting and regulatory compliance"},
                            {"heading": "7. How we store and protect your data", "body": "We use secure digital systems with encryption, access controls and regular security reviews. Data is stored within the EU, or in GDPR-compliant environments.\nReflection circles and cultural sessions are never recorded. Community content is protected and monitored for safety.\nForms you submit are stored securely so we can respond to you, and payment details never touch our servers."},
                            {"heading": "8. Who we share your data with", "body": "We only share data with:\n• Payment processors, for subscription billing\n• Digital platform providers, for membership access\n• Event management tools, where required\n• Legal or regulatory authorities, only where required by law\nWe never sell or transfer personal data to third parties for marketing."},
                            {"heading": "9. International transfers", "body": "Where a service provider operates outside the EU, we ensure GDPR-compliant safeguards such as:\n• Standard Contractual Clauses (SCCs)\n• Adequacy decisions\n• Verified GDPR compliance"},
                            {"heading": "10. How long we keep your data", "body": "We retain personal data only for as long as necessary:\n• Membership data: the duration of the active subscription plus 24 months\n• Event attendance records: 12 months\n• Reflection circle attendance: 12 months, with no session content stored\n• Community content: until deletion or account closure\n• Financial records: 6 years, as required by law"},
                            {"heading": "11. Your rights", "body": "Under the GDPR you have the right to:\n• Access your personal data\n• Request correction or deletion\n• Withdraw consent\n• Request data portability\n• Restrict processing\n• Object to certain uses\n• Lodge a complaint with the Data Protection Commission (DPC)\nTo exercise any of these rights, email info@asa-oz.com. We respond within one month."},
                            {"heading": "12. Cookies and digital tracking", "body": "Our platform uses cookies to:\n• Maintain login sessions\n• Improve your experience\n• Analyse platform usage\n• Enhance security\nWe set only strictly necessary cookies until you choose otherwise. You can accept or reject non-essential cookies using the cookie banner, and manage preferences in your browser settings.\nThis site also displays advertising through Google AdSense. AdSense uses cookies to serve ads based on a user's prior visits to this site or other sites. You may opt out of personalised advertising at https://adsettings.google.com, or opt out of certain vendors at https://www.aboutads.info. The AdSense programme is governed by Google's own policies, available at https://policies.google.com/technologies/ads."},
                            {"heading": "13. Changes to this notice", "body": "We may update this notice to reflect operational, legal or technological changes. The latest version will always be available on this page."},
                        ],
                    },
                ],
            },
        ],
    },
    "policies": {
        "label": "Operational Policies page",
        "hint": "The eleven day-to-day policies members are asked to agree to. Every heading and paragraph is editable below. Changes apply immediately.",
        "sections": [
            {
                "key": "hero",
                "label": "Hero",
                "fields": [
                    _lt("eyebrow", "Eyebrow", default="Operational Policies"),
                    _lt("title", "Headline", default="How we run the club"),
                    _ta("lede", "Intro paragraph", default="The eleven policies that govern day-to-day life at Asa-OZ. They sit alongside our Terms & Conditions and our Privacy Notice, and they are what we ask every member to read and agree to."),
                ],
            },
            {
                "key": "blocks",
                "label": "Policies",
                "fields": [
                    {
                        "key": "sections",
                        "label": "Policies",
                        "type": "list",
                        "item": {
                            "heading": {"label": "Heading", "type": "text"},
                            "body": {"label": "Body", "type": "textarea"},
                        },
                        "default": [
                            {"heading": "Membership policy", "body": "Asa-OZ operates as a digital subscription network and members' club. Membership is open to adults aged 45 and over who seek cultural identity restoration, community belonging and meaningful travel companionship. There is no upper age limit.\nMembers must maintain an active subscription to access events, circles and community spaces.\nMembership is personal and non-transferable.\nMembers are responsible for arranging their own travel, accommodation and insurance for any gathering.\nAsa-OZ reserves the right to pause or terminate membership for behaviour that breaches our community guidelines or disrupts group safety."},
                            {"heading": "Community conduct policy", "body": "Asa-OZ is a respectful, culturally grounded community. All members must:\n• Engage with others in a way that promotes belonging, dignity and cultural respect\n• Avoid discriminatory, aggressive or exclusionary behaviour\n• Honour confidentiality within reflection circles and identity-restoration sessions\n• Follow host instructions during group activities and gatherings\n• Refrain from promoting external businesses, political agendas or personal fundraising within Asa-OZ spaces"},
                            {"heading": "Nonpackage travel hosting policy", "body": "Asa-OZ does not sell travel packages, arrange transport or act as a travel agent.\nParticipants arrange their own flights, accommodation, visas, insurance and logistics.\nAsa-OZ provides cultural experiences, reflection circles, companionship and social integration coordination only.\nAny recommendations for hotels or hospitality providers are optional and non-binding.\nAsa-OZ is not responsible for cancellations, delays or changes to travel arrangements made independently by participants."},
                            {"heading": "Event and gathering policy", "body": "Events are designed to support cultural identity restoration and community belonging.\nAttendance is voluntary and subject to capacity limits.\nSome events may require preregistration or an additional fee.\nHosts may adjust schedules or activities to ensure safety or cultural appropriateness.\nMembers must disclose any accessibility needs in advance so reasonable accommodations can be arranged.\nAsa-OZ may cancel or reschedule events due to safety, weather or operational reasons."},
                            {"heading": "Safety and welfare policy", "body": "Asa-OZ prioritises emotional, cultural and physical safety.\nHosts are trained to manage group dynamics and support respectful engagement.\nMembers must follow safety instructions during walks, cultural activities and group movement.\nAsa-OZ does not provide medical, psychological or crisis intervention services, and nothing we offer is therapy or counselling.\nMembers must ensure they are physically able to participate in chosen activities.\nAny behaviour that compromises group welfare may result in removal from an event or suspension of membership."},
                            {"heading": "Privacy and data protection policy", "body": "Asa-OZ complies with the GDPR and protects member information.\nPersonal data is used only for membership management, event coordination and communication.\nReflection circles and cultural sessions are confidential, and no recordings are permitted.\nMembers may request deletion or correction of their data at any time.\nData is not shared with third parties except essential operational partners, such as payment processors.\nThe full detail sits in our Privacy Notice."},
                            {"heading": "Refund and cancellation policy", "body": "Subscription fees are non-refundable once activated.\nEvent fees may be refundable where cancellation falls within the stated window.\nIf Asa-OZ cancels an event, members will receive a credit or refund.\nNo refunds are provided for missed events due to personal travel issues."},
                            {"heading": "Hospitality promotion policy", "body": "Asa-OZ may collaborate with hospitality and accommodation providers.\nPromotions are informational only, and Asa-OZ does not act as a booking agent.\nMembers engage directly with providers for reservations or payments.\nAsa-OZ is not responsible for the quality, availability or delivery of external services."},
                            {"heading": "Cultural identity restoration policy", "body": "This is the core of Asa-OZ's mission.\nSessions are designed to support cultural reconnection, belonging and personal reflection.\nParticipation is voluntary and may involve group dialogue, storytelling and guided reflection.\nMembers must respect cultural differences and avoid invalidating others' experiences.\nHosts facilitate but do not provide therapy or counselling."},
                            {"heading": "Digital platform use policy", "body": "Members must keep their login details secure.\nContent shared in private groups must remain within the community.\nSpam, harassment and unauthorised advertising are prohibited.\nAsa-OZ may remove content that breaches these guidelines or threatens community safety."},
                            {"heading": "Compliance", "body": "These policies sit alongside our Terms & Conditions and our Privacy Notice. Where they differ, the Terms & Conditions prevail.\nIf anything here is unclear, email info@asa-oz.com and we will explain it."},
                        ],
                    },
                ],
            },
            {
                "key": "note",
                "label": "Legal note",
                "fields": [
                    _ta("note", "Note", default="If you have any questions about any of these policies, please contact info@asa-oz.com."),
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