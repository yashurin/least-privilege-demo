import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import ACCESS_TOKEN_TTL, JWT_ALGORITHM, JWT_SECRET
from app.errors import unauthorized
from app.models import ROLE_SET, Role
from app.store import UserRecord, store

# Missing credentials must be 401. HTTPBearer(auto_error=True) returns 403.
bearer_scheme = HTTPBearer(auto_error=False)

_DUMMY_PASSWORD = b"demo-password-placeholder"


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: str
    username: str
    role: Role
    scopes: tuple[str, ...]


def authenticate(username: str, password: str) -> UserRecord | None:
    user = store.get_user_by_username(username)
    stored = user.password.encode("utf-8") if user is not None else _DUMMY_PASSWORD
    provided = password.encode("utf-8")
    matches = secrets.compare_digest(stored, provided)
    if user is None or not matches:
        return None
    return user


def create_access_token(user: UserRecord, scopes: tuple[str, ...] = ()) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
    }
    if scopes:
        payload["scopes"] = list(scopes)
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        return token.decode("ascii")
    return token


def _parse_scopes(payload: dict[str, object]) -> tuple[str, ...]:
    if "scopes" not in payload:
        return ()
    raw = payload["scopes"]
    if not isinstance(raw, list) or any(
        not isinstance(item, str) or item == "" for item in raw
    ):
        raise unauthorized()
    return tuple(raw)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "username", "role"]},
        )
    except jwt.PyJWTError:
        raise unauthorized() from None

    subject = payload.get("sub")
    username = payload.get("username")
    role_claim = payload.get("role")
    if (
        not isinstance(subject, str)
        or not isinstance(username, str)
        or not isinstance(role_claim, str)
        or role_claim not in ROLE_SET
    ):
        raise unauthorized()

    scopes = _parse_scopes(payload)
    user = store.get_user(subject)
    # Role is read from the user record so an admin role change applies
    # before this token expires. Scopes stay on the token.
    if user is None or user.username != username or user.role not in ROLE_SET:
        raise unauthorized()
    return CurrentUser(
        id=user.id,
        username=user.username,
        role=user.role,
        scopes=scopes,
    )
