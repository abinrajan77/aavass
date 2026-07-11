"""The v1.0 `notification_templates` seed catalog — backend.md §1/§4.

Single source of truth, imported by both the Alembic seed migration
(`alembic/versions/65fb1510b01d_reporting_owner_portal_notifications.py`) and the test suite's
schema-seeding step (`tests/conftest.py`, which builds schema via `Base.metadata.create_all`
rather than running migrations — mirrors `app.core.permissions.PERMISSION_CATALOG`'s existing
"one list, two seeders" pattern so the two never drift apart.

One row per `(event_type, recipient_role)` combination, `channel='generic'` (the only channel
in v1.0). Placeholders substituted at request time by `app.services.notifications`:
`{resident_name}`, `{flat_number}`, `{tower_name}`, `{amount}`, `{due_date}`, `{period}`.
"""

NOTIFICATION_TEMPLATE_SEED: list[tuple[str, str, str]] = [
    (
        "due_generated",
        "resident",
        "Dear {resident_name}, your maintenance due of Rs. {amount} for {flat_number}, "
        "{tower_name} for {period} is due on {due_date}.",
    ),
    (
        "due_generated",
        "owner_copy",
        "Dear Owner, a maintenance due of Rs. {amount} for {flat_number}, {tower_name} for "
        "{period} (resident: {resident_name}) is due on {due_date}. This is a copy for your "
        "records.",
    ),
    (
        "overdue_reminder",
        "resident",
        "Dear {resident_name}, your maintenance payment of Rs. {amount} for {flat_number}, "
        "{tower_name} for {period} was due on {due_date} and is now overdue. Please pay at "
        "the earliest to avoid further delay.",
    ),
    (
        "overdue_reminder",
        "owner_copy",
        "Dear Owner, the maintenance payment of Rs. {amount} for {flat_number}, {tower_name} "
        "for {period} (resident: {resident_name}) was due on {due_date} and is now overdue.",
    ),
    (
        "payment_confirmed",
        "resident",
        "Dear {resident_name}, we have received your payment of Rs. {amount} for "
        "{flat_number}, {tower_name} for {period}. Thank you!",
    ),
    (
        "payment_confirmed",
        "owner_copy",
        "Dear Owner, a payment of Rs. {amount} for {flat_number}, {tower_name} for {period} "
        "(resident: {resident_name}) has been received. This is a copy for your records.",
    ),
]
