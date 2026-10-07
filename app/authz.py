from typing import Annotated

from fastapi import Depends

from app.errors import forbidden
from app.models import Role
from app.security import CurrentUser, get_current_user

CATALOG_ROLES: tuple[Role, ...] = ("readonly", "user", "manager", "admin")
ORDER_ROLES: tuple[Role, ...] = ("user", "manager", "admin")
TEAM_ROLES: tuple[Role, ...] = ("manager", "admin")
ADMIN_ROLES: tuple[Role, ...] = ("admin",)
EXPORT_SCOPE = "pii:export"

PROTECTED_RESPONSES = {
    401: {"description": "Missing or invalid bearer token"},
    403: {"description": "The token is valid, but the role or scope is not allowed"},
}


def require_roles(*allowed: Role):
    """Allow only these roles. A valid token outside the set is 403."""
    allowed_set = frozenset(allowed)
    if not allowed_set:
        raise RuntimeError("require_roles needs at least one role")

    def checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current.role not in allowed_set:
            raise forbidden()
        return current

    return checker


def require_scopes(*required: str):
    """Require every named scope. A valid token missing one is 403."""
    required_set = frozenset(required)
    if not required_set:
        raise RuntimeError("require_scopes needs at least one scope")

    def checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not required_set.issubset(current.scopes):
            raise forbidden()
        return current

    return checker


OrderUser = Annotated[CurrentUser, Depends(require_roles(*ORDER_ROLES))]
