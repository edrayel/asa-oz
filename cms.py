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

def _lt(key, label, **kw):
    return dict(key=key, label=label, type="text", **kw)

def _ta(key, label, **kw):
    return dict(key=key, label=label, type="textarea", **kw)

def _img(key, label, **kw):
    return dict(key=key, label=label, type="image", **kw)

def _cb(key, label, default=False, **kw):
    return dict(key=key, label=label, type="checkbox", default=default, **kw)


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
                    _lt("mid", "Between timer and date", default="— Asa-OZ goes live"),
                    _lt("date", "Launch date text", default="Monday, 3 August 2026"),
                ],
            },
            {
                "key": "marquee",
                "label": "Hero carousel (marquee)",
                "fields": [
                    _lt("rows", "Rows (1-3)", default="3"),
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
                "key": "hero",
                "label": "Hero",
                "fields": [
                    _lt("eyebrow", "Eyebrow", default="Identity • Culture • Belonging"),
                    _lt("title", "Headline", default="Return to Self."),
                    _ta("lede", "Intro paragraph", default="Asa-OZ is a cultural reconnection experience helping adults 45+ rediscover identity, belonging, and purpose through guided journeys, community, and meaningful travel."),
                    _ta("supporting", "Supporting copy", default="Connect with like-minded people who share your interests, values and curiosity. Whether you enjoy history, food, art, nature, photography or simply meaningful conversation, Asa-OZ helps you connect with others before travelling together."),
                    _lt("not_this_title", "“What this is not” title", default="What this is not."),
                    _ta("not_this_body", "“What this is not” body", default="Asa-OZ is not spiritual practice, energy work, therapy, or meditation. It is a cultural and community experience — grounded in real conversation, shared meals, storytelling, and travel."),
                ],
            },
            {
                "key": "signup",
                "label": "Hero signup",
                "fields": [
                    _cb("enabled", "Show signup form", default=True),
                    _lt("name_placeholder", "Name placeholder", default="Your name (optional)"),
                    _lt("email_placeholder", "Email placeholder", default="Enter your email to be the first to know"),
                    _lt("button", "Button label", default="Join the journey"),
                    _lt("note", "Privacy note", default="No spam — only an invitation when we open our doors."),
                ],
            },
            {
                "key": "how",
                "label": "How it works",
                "fields": [
                    _lt("title", "Heading", default="How it works"),
                    {
                        "key": "steps",
                        "label": "Steps",
                        "type": "list",
                        "item": {
                            "title": {"label": "Title", "type": "text"},
                            "body": {"label": "Body", "type": "text"},
                        },
                        "default": [
                            {"title": "Apply or join the waitlist", "body": "Begin your journey with a simple expression of interest."},
                            {"title": "Attend guided online sessions", "body": "Join our community from anywhere through curated online gatherings."},
                            {"title": "Join community experiences", "body": "Connect in person through identity circles, storytelling, and shared meals."},
                            {"title": "Participate in curated cultural journeys", "body": "Travel with meaning, guided by culture and community."},
                        ],
                    },
                ],
            },
            {
                "key": "pillars",
                "label": "What Asa-OZ offers (simple mode off)",
                "fields": [
                    {
                        "key": "entries",
                        "label": "Pillars",
                        "type": "list",
                        "item": {
                            "title": {"label": "Title", "type": "text"},
                            "body": {"label": "Body", "type": "text"},
                        },
                        "default": [
                            {"title": "Identity", "body": "Remembering who you are, beneath the years and the roles."},
                            {"title": "Culture", "body": "Grounding yourself in heritage, story, and meaning."},
                            {"title": "Belonging", "body": "Finding companionship and genuine connection again."},
                            {"title": "Community", "body": "Sharing life, presence, and warmth with others."},
                            {"title": "Exploration", "body": "Awakening joy and purpose through meaningful travel."},
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
                            {"title": "Virtual community", "body": "Regular sessions to connect, reflect and grow together."},
                            {"title": "Identity circles", "body": "Safe spaces to share, listen, and be seen."},
                            {"title": "Cultural talks & storytelling", "body": "Stories that remember you, and heritage that heals."},
                            {"title": "Hosted trips & curated journeys", "body": "Travel that restores identity and awakens joy."},
                            {"title": "Community membership", "body": "A space to belong — details and fees to be confirmed."},
                        ],
                    },
                ],
            },
            {
                "key": "storeteaser",
                "label": "Store teaser (“Tools for the journey”)",
                "fields": [
                    _lt("heading", "Heading", default="Tools for the journey"),
                ],
            },
            {
                "key": "gallery",
                "label": "Gallery",
                "fields": [
                    _lt("title", "Heading", default="Moments of return"),
                    _lt("wall_button", "Wall button label", default="View the wall of moments"),
                ],
            },
            {
                "key": "testimonials",
                "label": "Testimonials",
                "fields": [
                    _img("photo", "Photo (URL or media library)"),
                    _ta("quote", "Quote", default="“The journey was more than travel — it was a return.”"),
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
                            "Feel disconnected from their identity or heritage",
                            "Are navigating a major life transition",
                            "Long for meaningful community",
                            "Want intentional travel experiences",
                            "Are seeking reflection and personal growth",
                        ],
                    },
                    _ta("tagline", "Tagline", default="Designed for adults aged 45 and above who are ready for lasting joy, connection, and belonging."),
                ],
            },
            {
                "key": "ethos",
                "label": "Ethos (promise block)",
                "fields": [
                    _lt("quote", "Quote", default="You don't have to shrink to fit the life you've"),
                    _lt("quote_highlight", "Quote highlight", default="outgrown"),
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
                            {"text": "Not therapy", "struck": True},
                            {"text": "Not clinical", "struck": True},
                            {"text": "Not a wellness programme", "struck": True},
                            {"text": "Simply, a way home", "struck": False},
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
                    _ta("quote1", "Opening quote", default="My name is Ifeoma Adaora, and for more than 25 years, I have traveled the world discovering that travel can do much more than take us to new places — it can restore confidence, create meaningful connections, and help us rediscover parts of ourselves we thought were lost."),
                    _ta("quote2", "Second quote", default="Through journeys that matter and a community that holds space, I walk alongside adults 45+ as they reconnect with who they are and what they long for."),
                    _lt("signature", "Signature line", default="You are not starting over. You are rediscovering yourself."),
                    _lt("more", "More-about link label", default="More about Asa-OZ and the story behind it"),
                ],
            },
            {
                "key": "faq",
                "label": "FAQ section",
                "fields": [
                    _lt("prompt_title", "Heading", default="Questions, gently answered."),
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
                            {"q": "What is Asa-OZ?", "a": "Asa-OZ is a cultural reconnection experience for adults 45+ featuring guided journeys, online events, and curated travel — no therapy, no energy work, no wellness jargon."},
                            {"q": "Do I need a lot of money?", "a": "No. You can join as a Circle member, pay-as-you-go, or simply follow along with free events. Membership tiers are designed to fit different budgets."},
                            {"q": "Do I need to be in a certain country?", "a": "No — the online community is global. Some in-person meetups take place in Ireland, with cultural journeys across Europe, Africa, and beyond."},
                            {"q": "What do I get in the paid membership?", "a": "Access to online events, community group, storytelling sessions, curated trips (first-come, first-served), and a growing library of cultural resources."},
                            {"q": "Is this right for me?", "a": "If curiosity, connection, and cultural exploration pull at you, it probably is. Join the waitlist and we can have an honest conversation about it."},
                        ],
                    },
                ],
            },
            {
                "key": "pricing",
                "label": "Membership pricing",
                "fields": [
                    _lt("title", "Heading", default="Membership"),
                    _lt("lede", "Lede", default="Join a community that values presence, conversation, and cultural connection."),
                    _lt("monthly_label", "Monthly label", default="Monthly"),
                    _lt("yearly_label", "Yearly label", default="Yearly"),
                    _lt("cta_label", "Button label", default="Join the waitlist"),
                    {
                        "key": "cards",
                        "label": "Tiers",
                        "type": "list",
                        "item": {
                            "name": {"label": "Name", "type": "text"},
                            "price_m": {"label": "Monthly price", "type": "text", "default": "€19"},
                            "price_y": {"label": "Yearly price", "type": "text", "default": "€190"},
                            "note": {"label": "Note", "type": "text"},
                            "badge": {"label": "Badge text (empty = none)", "type": "text", "default": ""},
                            "features": {"label": "Included (one per line)", "type": "listlines", "default": []},
                        },
                        "default": [
                            {"name": "Circle", "price_m": "€19", "price_y": "€190",
                             "note": "Online gatherings and community meetups",
                             "badge": "", "features": ["Monthly video calls", "Community meetups in Ireland", "Newsletter and updates"]},
                            {"name": "Journey", "price_m": "€39", "price_y": "€390",
                             "note": "Everything in Circle, plus cultural sessions and curated trips",
                             "badge": "Most popular",
                             "features": ["All Circle benefits", "Cultural talks and storytelling", "Priority booking", "Guest speakers"]},
                            {"name": "Roots", "price_m": "€79", "price_y": "€790",
                             "note": "For those who want to go deeper",
                             "badge": "",
                             "features": ["All Journey benefits", "Small-group cultural trips", "One-to-one check-ins", "Early access to new experiences"]},
                        ],
                    },
                    _ta("disclaimer_note", "Disclaimer", default="All prices are illustrative. Final pricing will be confirmed before launch."),
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
                "key": "tools_products",
                "label": "Store section behaviour",
                "fields": [
                    _lt("visit_store_label", "“Visit the store” link", default="Visit the store"),
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
                    _lt("title", "Headline", default="A movement for identity, belonging & renewal."),
                    _ta("lede", "Intro paragraph", default="Asa-OZ is a cultural reconnection experience helping adults 45+ rediscover identity, belonging, and purpose through guided journeys, community, and meaningful travel."),
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
                            "Many of us reach a point in life where we feel disconnected from ourselves. After years of building careers, raising families, and caring for others, the next chapter can feel unclear — and quiet loneliness can settle in.",
                            "Asa-OZ exists to meet that moment. It is a space where adults 45+ can reconnect with their identity, culture, and sense of belonging through community, conversation, storytelling, and meaningful travel.",
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
                            {"name": "Identity", "body": "remembering who you are, beneath the years and the roles."},
                            {"name": "Culture", "body": "grounding yourself in heritage, story, and meaning."},
                            {"name": "Belonging", "body": "finding companionship and genuine connection again."},
                            {"name": "Community", "body": "sharing life, presence, and warmth with others."},
                            {"name": "Exploration", "body": "awakening joy and purpose through meaningful travel."},
                        ],
                    },
                    _lt("closing", "Closing line", default="This is not about escaping your life. It is about returning to yourself."),
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
                            "Concrete and everyday — shared meals, walking tours, group conversations, and storytelling. Real people, real places, real conversation. Community that feels like home.",
                        ],
                    },
                    _ta("proof_footnote", "Proof strip footnote", default="No renderings, no stock shots — shared meals, walking tours, and slow conversations from real Asa-OZ days."),
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
                            "Adults aged 45 and above who are ready for something more than another holiday — whether you feel disconnected from your identity or heritage, are navigating a major life transition, long for meaningful community, want intentional travel, or are seeking reflection and personal growth.",
                            "You can join on your own — many do.",
                        ],
                    },
                ],
            },
            {
                "key": "founder",
                "label": "The founder",
                "fields": [
                    _lt("heading", "Heading", default="The founder"),
                    _ta("quote", "Quote", default="You are not starting over. You are simply discovering a deeper, richer version of yourself."),
                    {
                        "key": "paragraphs",
                        "label": "Paragraphs",
                        "type": "listlines",
                        "default": [
                            "My name is Ifeoma Adaora, and for more than 25 years I have traveled the world, discovering that travel can do much more than take us to new places. It can restore confidence, create meaningful connections, and help us rediscover parts of ourselves we thought were lost.",
                            "Along the way, I met countless people whose lives had been shaped by responsibility. They had spent years building careers, raising families, caring for loved ones, and putting everyone else first. Yet many quietly admitted they felt disconnected from themselves and unsure of what the next chapter of life should look like.",
                        ],
                    },
                    _lt("name", "Name", default="Ifeoma Adaora"),
                    _lt("role", "Role", default="Founder & Cultural Guide"),
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
                            "Asa-OZ is a guided cultural and personal development experience. It is not psychotherapy or a replacement for professional health care. It is not spiritual practice, energy work, or meditation.",
                            "We do not sell travel packages — participants book their own travel, and Asa-OZ provides the cultural guidance, community, and hosting that make the journey meaningful.",
                        ],
                    },
                ],
            },
            {
                "key": "cta",
                "label": "End call to action",
                "fields": [
                    _lt("line", "Line", default="You are not starting over. You are starting deeper."),
                    _lt("join_label", "Join-waitlist button", default="Join the waitlist"),
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
                    _lt("title", "Headline", default="Questions, gently answered."),
                    _ta("lede", "Intro paragraph", default="Everything you might want to know about Asa-OZ before you join."),
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
                            "q": {"label": "Question", "type": "text"},
                            "a": {"label": "Answer", "type": "textarea"},
                        },
                        "default": [
                            {"q": "What is Asa-OZ?", "a": "Asa-OZ is a cultural reconnection experience helping adults 45+ rediscover identity, belonging, and purpose through guided journeys, community, and meaningful travel."},
                            {"q": "Who is Asa-OZ for?", "a": "Adults 45+ who feel disconnected from their identity or heritage, are navigating a major life transition, long for meaningful community, want intentional travel experiences, or are seeking reflection and personal growth."},
                            {"q": "What do I receive after joining?", "a": "Online events, group identity circles, cultural talks and storytelling sessions, hosted trips and curated journeys, and community membership."},
                            {"q": "How long is the programme?", "a": "Programme length varies. Some experiences are one-off gatherings; others form part of an ongoing journey. Details will be shared as we finalise the calendar."},
                            {"q": "Is it online or in person?", "a": "Both. We begin with guided online sessions to build connection, then move into in-person community experiences and curated cultural journeys."},
                            {"q": "How much does it cost?", "a": "Membership fees are still being finalised. Join the waitlist to be the first to know when pricing is confirmed."},
                            {"q": "Which countries or cultures will be explored?", "a": "We are starting in Ireland, with plans to expand. Destinations will be announced as our community grows."},
                            {"q": "How often are experiences organised?", "a": "The calendar is still forming. We expect a mix of regular online sessions, monthly in-person circles, and periodic curated journeys."},
                            {"q": "Is it UK/Ireland-based or international?", "a": "We are Ireland-based, with ambitions to grow internationally over time."},
                            {"q": "Can I join from anywhere in the world?", "a": "Yes. Many of our online sessions are open internationally. In-person journeys may be Ireland-based initially, but international participation is welcome where possible."},
                            {"q": "What happens after I register?", "a": "You will receive a welcome message with next steps, including invitations to upcoming online sessions and community events."},
                            {"q": "Is this therapy?", "a": "No. Asa-OZ is a guided cultural and personal development experience. It is not psychotherapy or a substitute for licensed mental-health care."},
                            {"q": "Do you sell travel packages?", "a": "No. Participants book their own travel. Asa-OZ provides cultural guidance and identity experiences — the grounding, the community, and the meaning that make the journey worthwhile."},
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
                    _lt("join_label", "Join-waitlist button", default="Join the waitlist"),
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
                            {"heading": "What Asa-OZ offers", "body": "Asa-OZ is a guided cultural and personal development experience for adults aged 45 and above. It brings people together through online sessions, community gatherings, and curated cultural journeys. It does not sell travel packages — participants arrange and book their own travel."},
                            {"heading": "Important — what Asa-OZ is not", "body": "Asa-OZ is not psychotherapy, counselling, a medical service, or spiritual or energy work. It is not a substitute for licensed mental health care. If you need professional support, please contact a qualified professional."},
                            {"heading": "Payments & refunds", "body": "Refunds apply only to programme fees for identity circles or cultural events.\n• Full refund available up to 48 hours before the event.\n• No refund within 48 hours of the event start.\nPlaces are limited and can fill quickly — we recommend booking early."},
                            {"heading": "Bookings", "body": "Bookings are confirmed by email. There is no instant online booking — enquiries are handled personally."},
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
                            {"heading": "1. Who we are", "body": "Asa-OZ is a cultural identity restoration movement for adults 45+. For privacy questions, please contact us at info@asa-oz.com."},
                            {"heading": "2. What information we collect", "body": "We collect only the information you choose to provide, such as:\n• Your name and email address when you join the waitlist or contact us\n• Your message when you use the contact form\n• Booking preferences when you request a discovery call or order from our store\nWe process payments only through our payment provider (Stripe). We do not store your card details."},
                            {"heading": "3. How we use your information", "body": "We use your information to:\n• Respond to your enquiries\n• Add you to our waitlist and notify you when we launch\n• Arrange discovery calls and bookings\n• Process store orders and deliver what you purchase\n• Improve our website and services"},
                            {"heading": "4. Cookies", "body": "We use strictly necessary cookies to make the site work. With your consent, we may use analytics cookies to understand how visitors find us. You can accept or reject non-essential cookies using the cookie banner."},
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
                    _ta("lede", "Intro paragraph", default="A suggestion, a question, or a note for the founder — every message is read."),
                ],
            },
            {
                "key": "info",
                "label": "Contact details card",
                "fields": [
                    _lt("heading", "Heading", default="Get in touch"),
                    _lt("email_label", "Email label", default="Email:"),
                    _lt("email", "Email address", default="info@asa-oz.com"),
                    _lt("call_label", "Discovery-call line", default="Book a discovery call — use the “Book a discovery call” button in the header."),
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
                    _lt("tagline", "Footer tagline", default="A movement for identity, belonging & renewal."),
                    _lt("email", "Contact email", default="info@asa-oz.com"),
                    _lt("phone", "Contact phone", default="[to be added]"),
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
                    _lt("hero_title", "Store hero title", default="Tools for the journey"),
                    _ta("hero_lede", "Store hero lede", default="Thoughtfully made things to support your return — journals, guides, circles, and keepsakes. Every item carries the same intention as the experiences themselves."),
                    _lt("similar_title", "“You may also like” title", default="You may also like"),
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
}

# --------------------------------------------------------------------------
# Resolver
# --------------------------------------------------------------------------

def default_content(section):
    """Construct the default values dict for a schema section."""
    out = {}
    for f in section["fields"]:
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