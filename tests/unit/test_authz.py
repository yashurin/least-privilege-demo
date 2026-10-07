import pytest
from fastapi import HTTPException

from app.authz import require_roles, require_scopes
from app.security import CurrentUser


def _user(role: str, scopes: tuple[str, ...] = ()) -> CurrentUser:
    return CurrentUser(id=role, username=role, role=role, scopes=scopes)  # type: ignore[arg-type]


def test_require_roles_allows_only_the_named_set():
    allow = require_roles("manager", "admin")
    manager = _user("manager")
    assert allow(manager) is manager
    with pytest.raises(HTTPException) as exc:
        allow(_user("user"))
    assert exc.value.status_code == 403
    assert exc.value.detail == "Forbidden"


def test_require_scopes_fails_closed_when_the_claim_is_absent():
    allow = require_scopes("pii:export")
    granted = _user("admin", scopes=("pii:export", "other"))
    assert allow(granted) is granted
    with pytest.raises(HTTPException) as missing:
        allow(_user("admin"))
    with pytest.raises(HTTPException) as partial:
        allow(_user("admin", scopes=("other",)))
    assert missing.value.status_code == partial.value.status_code == 403


def test_empty_role_or_scope_sets_are_rejected():
    with pytest.raises(RuntimeError, match="require_roles"):
        require_roles()
    with pytest.raises(RuntimeError, match="require_scopes"):
        require_scopes()
