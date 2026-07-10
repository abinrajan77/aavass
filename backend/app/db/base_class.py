"""The declarative base, isolated in its own module with zero dependency on any model module.

Every model imports `Base` from *here*, not from `app.db.base` — `app.db.base` imports all
model modules (for Alembic's autogenerate metadata) and therefore cannot be imported back by
any individual model without creating a circular import (whichever model happened to be the
first "entry point" into the models package would try to re-import itself mid-execution).
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
