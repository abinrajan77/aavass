"""Model registry import hook — used by Alembic autogenerate (`alembic/env.py`) and the test
suite (`tests/conftest.py`) to populate `Base.metadata` with every table.

Application code (routers/services/dependencies) should import model classes from their
specific submodule (e.g. `from app.models.user import User`) and import `Base` from
`app.db.base_class`, not from this module — see that module's docstring for why.
"""

from app.db.base_class import Base

# Import all models here so Alembic's autogenerate / metadata creation sees them.
from app.models.apartment_complex import ApartmentComplex  # noqa: E402, F401
from app.models.association_member import AssociationMember  # noqa: E402, F401
from app.models.audit_log import AuditLog  # noqa: E402, F401
from app.models.flat import Flat  # noqa: E402, F401
from app.models.flat_ownership import FlatOwnership  # noqa: E402, F401
from app.models.owner import Owner  # noqa: E402, F401
from app.models.password_reset_token import PasswordResetToken  # noqa: E402, F401
from app.models.permission import Permission  # noqa: E402, F401
from app.models.refresh_token import RefreshToken  # noqa: E402, F401
from app.models.role import Role  # noqa: E402, F401
from app.models.role_permission import RolePermission  # noqa: E402, F401
from app.models.tenant import Tenant  # noqa: E402, F401
from app.models.tower import Tower  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401

__all__ = ["Base"]
