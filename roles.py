"""Roles and permissions for the Asa-OZ CMS.

Five roles, ranked. A user may only hand out roles at or below their own,
and may only manage accounts strictly below their own rank — that is what
stops an ``admin`` from promoting somebody to ``superadmin``.

    superadmin              everything, including user management
    admin                   everything except assigning superadmin
    digital marketing manager   content, media and audience — no shop, no system
    ecommerce manager           shop, media and bookings — no content, no system
    member                      a public-site account with no admin access

Permissions are plain strings grouped by area (``content.blog``,
``shop.orders``, …). Every admin route is mapped to one; a route that is
not in the map is superadmin-only, so a new admin view fails closed.
"""

SUPERADMIN = "superadmin"
ADMIN = "admin"
MARKETING = "digital marketing manager"
ECOMMERCE = "ecommerce manager"
MEMBER = "member"

# Highest first. The index is the rank.
ROLE_ORDER = [SUPERADMIN, ADMIN, MARKETING, ECOMMERCE, MEMBER]

ROLE_LABELS = {
    SUPERADMIN: "Superadmin",
    ADMIN: "Admin",
    MARKETING: "Digital marketing manager",
    ECOMMERCE: "Ecommerce manager",
    MEMBER: "Member",
}

ROLE_DESCRIPTIONS = {
    SUPERADMIN: "Full access, including managing users and their roles.",
    ADMIN: "Full access to the CMS. Cannot create or promote superadmins.",
    MARKETING: "Content, pages, stories, navigation, brand, media and audience. No shop, no settings.",
    ECOMMERCE: "Products, orders, media and bookings. No content editing, no settings.",
    MEMBER: "A public-site account. No access to the admin area.",
}

# The permission only a superadmin ever holds.
SUPERADMIN_ONLY = "superadmin.only"

CONTENT = {"content.pages", "content.blog", "content.dynamic_pages", "content.navigation", "content.brand"}
MEDIA = {"media.files", "media.drive", "media.photos"}
SHOP = {"shop.products", "shop.orders"}
AUDIENCE = {"audience.feedback", "audience.waitlist", "audience.journey", "audience.bookings", "audience.contacts"}
SYSTEM = {"system.emails", "system.settings", "system.restore", "system.export", "system.users"}

ALL_PERMISSIONS = CONTENT | MEDIA | SHOP | AUDIENCE | SYSTEM | {SUPERADMIN_ONLY}

ROLE_PERMISSIONS = {
    SUPERADMIN: set(ALL_PERMISSIONS),
    ADMIN: (CONTENT | MEDIA | SHOP | AUDIENCE | SYSTEM) - {SUPERADMIN_ONLY},
    MARKETING: CONTENT | MEDIA | AUDIENCE | {"system.emails", "system.export"},
    ECOMMERCE: SHOP | MEDIA | {"audience.bookings", "audience.contacts", "system.emails", "system.export"},
    MEMBER: set(),
}

# Admin routes that any signed-in user may reach, whatever their role.
ALWAYS_ALLOWED = {
    "admin_login",
    "admin_logout",
    "admin_dashboard",
    "admin_password",
}

ROUTE_PERMISSIONS = {
    "admin_products": "shop.products",
    "admin_products_new": "shop.products",
    "admin_product_update": "shop.products",
    "admin_product_delete": "shop.products",
    "admin_files": "media.files",
    "admin_files_upload": "media.files",
    "admin_file_delete": "media.files",
    "admin_blog": "content.blog",
    "admin_blog_new": "content.blog",
    "admin_blog_edit": "content.blog",
    "admin_blog_delete": "content.blog",
    "admin_drive": "media.drive",
    "admin_drive_import": "media.drive",
    "admin_drive_link": "media.drive",
    "admin_photos": "media.photos",
    "admin_photos_session": "media.photos",
    "admin_photos_cancel": "media.photos",
    "admin_photos_import": "media.photos",
    "admin_feedback": "audience.feedback",
    "admin_feedback_update": "audience.feedback",
    "admin_feedback_delete": "audience.feedback",
    "admin_import": "system.restore",
    "admin_waitlist": "audience.waitlist",
    "admin_emails": "system.emails",
    "admin_bookings": "audience.bookings",
    "admin_booking_status": "audience.bookings",
    "admin_contacts": "audience.contacts",
    "admin_journey": "audience.journey",
    "admin_journey_delete": "audience.journey",
    "admin_orders": "shop.orders",
    "admin_order_status": "shop.orders",
    "admin_pages": "content.pages",
    "admin_page": "content.pages",
    "admin_page_reorder": "content.pages",
    "admin_settings": "system.settings",
    "admin_export": "system.export",
    "export_waitlist_csv": "system.export",
    "export_contacts_csv": "system.export",
    "export_orders_csv": "system.export",
    "export_bookings_csv": "system.export",
    "export_feedback_csv": "system.export",
    "admin_dynamic_pages": "content.dynamic_pages",
    "admin_dynamic_page_new": "content.dynamic_pages",
    "admin_dynamic_page_edit": "content.dynamic_pages",
    "admin_dynamic_page_save": "content.dynamic_pages",
    "admin_dynamic_page_section": "content.dynamic_pages",
    "admin_dynamic_page_delete": "content.dynamic_pages",
    "admin_navigation": "content.navigation",
    "admin_brand": "content.brand",
    "admin_users": "system.users",
    "admin_user_new": "system.users",
    "admin_user_edit": "system.users",
    "admin_user_role": "system.users",
    "admin_user_status": "system.users",
    "admin_user_invite": "system.users",
    "admin_user_delete": "system.users",
}


def is_role(value):
    return value in ROLE_PERMISSIONS


def rank(role):
    """Power ranking: higher means more power. Unknown roles rank lowest."""
    try:
        return len(ROLE_ORDER) - ROLE_ORDER.index(role)
    except ValueError:
        return -1


def label(role):
    return ROLE_LABELS.get(role, role or "Unknown")


def permissions_for(role):
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role, permission):
    if not permission:
        return True
    return permission in permissions_for(role)


def permission_for(endpoint):
    """The permission an admin endpoint needs, or None for "any signed-in user".

    An endpoint that is not in the map is superadmin-only: a new admin view
    must be given a permission on purpose, otherwise it is closed to
    everybody else by default.
    """
    if endpoint in ALWAYS_ALLOWED:
        return None
    return ROUTE_PERMISSIONS.get(endpoint, SUPERADMIN_ONLY)


def may_assign(actor_role, target_role):
    """May a user with ``actor_role`` hand out ``target_role``?"""
    if not is_role(target_role):
        return False
    return rank(target_role) <= rank(actor_role)


def may_manage(actor_role, target_role, target_id=None, actor_id=None):
    """May a user with ``actor_role`` edit the account that has ``target_role``?

    You may always edit yourself (but never your own role), and you may
    edit anybody strictly below your own rank.
    """
    if target_id is not None and actor_id is not None and target_id == actor_id:
        return True
    return rank(target_role) < rank(actor_role)


def assignable_roles(actor_role):
    """The roles ``actor_role`` is allowed to hand out."""
    return [r for r in ROLE_ORDER if may_assign(actor_role, r)]
