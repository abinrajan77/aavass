"""Intentionally does not import/re-export model classes here.

`app/db/base.py` is the single place that imports every model module (so Alembic's
autogenerate sees the full metadata) — duplicating that import list here caused a circular
import (this package's __init__ and db.base each trying to fully import the other's target
module first). Application code should import model classes from their specific submodule,
e.g. `from app.models.user import User`, not from this package directly.
"""
