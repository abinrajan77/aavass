"""The v1.0 permission catalog — `00-architecture-and-standards.md` §5.1.

Single source of truth, imported by both the Alembic seed migration and the tower-creation
"seed the Admin role with every permission" logic, so the two never drift apart.
"""

PERMISSION_CATALOG: list[tuple[str, str]] = [
    ("MANAGE_COMPLEX", "Create/edit complex & tower records"),
    ("MANAGE_ASSOCIATION_MEMBERS", "Add/edit association members, assign roles"),
    ("MANAGE_RESIDENTS", "Add/edit flats, owners, tenants"),
    ("CONFIGURE_BILLING", "Edit maintenance formula & grace period"),
    ("CREATE_BILLING_CYCLE", "Generate a billing cycle"),
    ("RECORD_PAYMENT", "Mark dues paid, generate receipts"),
    ("MANAGE_SPECIAL_COLLECTIONS", "Create/edit special collections"),
    ("MANAGE_EXPENDITURE", "Record tower/complex expenditure"),
    ("VIEW_REPORTS", "Generate/export reports"),
    ("VIEW_TOWER_DATA", "Read-only tower-wide visibility (flat owners get this by default)"),
    ("MANAGE_OWN_FLAT", "Flat owner: edit own contact/tenant/occupancy details"),
]

ADMIN_ROLE_NAME = "Admin"
