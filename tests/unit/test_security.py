from dataclasses import replace
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import JWT_ALGORITHM, JWT_SECRET
from app.security import authenticate, create_access_token, get_current_user
from app.store import store

_WRONG_SECRET = "another-demo-secret-that-is-long-enough"


def _credentials(token: str, scheme: str = "Bearer") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=token)


def _user_token() -> str:
    user = store.get_user("user")
    assert user is not None
    return create_access_token(user)


def test_authenticate_accepts_the_seeded_password_only():
    user = authenticate("user", "user")
    assert user is not None
    assert user.id == "user"
    assert authenticate("user", "wrong") is None
    assert authenticate("nobody", "nobody") is None
    assert authenticate("nobody", "pässword") is None


def test_login_token_claims_omit_scopes_and_password():
    user = store.get_user("manager")
    assert user is not None
    token = create_access_token(user)
    claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert claims["sub"] == "manager"
    assert claims["username"] == "manager"
    assert claims["role"] == "manager"
    assert claims["exp"] - claims["iat"] == 1800
    assert "scopes" not in claims
    assert "password" not in claims
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "HS256"


def test_scoped_token_carries_only_the_requested_scopes():
    admin = store.get_user("admin")
    assert admin is not None
    token = create_access_token(admin, scopes=("pii:export",))
    claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert claims["scopes"] == ["pii:export"]
    assert claims["role"] == "admin"


def test_encode_may_return_bytes(monkeypatch):
    monkeypatch.setattr("app.security.jwt.encode", lambda *args, **kwargs: b"header.payload.sig")
    user = store.get_user("user")
    assert user is not None
    assert create_access_token(user) == "header.payload.sig"


def test_get_current_user_loads_the_stored_role_and_scopes():
    token = create_access_token(store.get_user("admin"), scopes=("pii:export",))
    current = get_current_user(_credentials(token, scheme="BEARER"))
    assert current.id == "admin"
    assert current.username == "admin"
    assert current.role == "admin"
    assert current.scopes == ("pii:export",)


def test_missing_or_non_bearer_credentials_are_401():
    with pytest.raises(HTTPException) as missing:
        get_current_user(None)
    with pytest.raises(HTTPException) as basic:
        get_current_user(_credentials("abc", scheme="Basic"))
    assert missing.value.status_code == basic.value.status_code == 401
    assert missing.value.detail == "Not authenticated"
    assert missing.value.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        jwt.encode(
            {
                "sub": "user",
                "username": "user",
                "role": "user",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        ),
        jwt.encode(
            {
                "sub": "user",
                "username": "user",
                "role": "admin",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            _WRONG_SECRET,
            algorithm=JWT_ALGORITHM,
        ),
        jwt.encode(
            {"sub": "user", "username": "user", "role": "admin"},
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        ),
    ],
)
def test_invalid_tokens_are_401(token):
    with pytest.raises(HTTPException) as exc:
        get_current_user(_credentials(token))
    assert exc.value.status_code == 401


def test_alg_none_is_rejected():
    token = jwt.encode(
        {
            "sub": "user",
            "username": "user",
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "",
        algorithm="none",
    )
    with pytest.raises(HTTPException) as exc:
        get_current_user(_credentials(token))
    assert exc.value.status_code == 401


def test_claim_types_and_unknown_role_fail_closed():
    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
    samples = [
        {"sub": 1, "username": "user", "role": "user", "exp": expiry},
        {"sub": "user", "username": 1, "role": "user", "exp": expiry},
        {"sub": "user", "username": "user", "role": 1, "exp": expiry},
        {"sub": "user", "username": "user", "role": "superuser", "exp": expiry},
        {"sub": "user", "username": "user", "role": "user", "scopes": "pii:export", "exp": expiry},
        {"sub": "user", "username": "user", "role": "user", "scopes": [""], "exp": expiry},
        {"sub": "user", "username": "user", "role": "user", "scopes": None, "exp": expiry},
    ]
    for payload in samples:
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        with pytest.raises(HTTPException) as exc:
            get_current_user(_credentials(token))
        assert exc.value.status_code == 401


def test_empty_scope_list_is_valid_and_grants_nothing():
    token = jwt.encode(
        {
            "sub": "admin",
            "username": "admin",
            "role": "admin",
            "scopes": [],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    current = get_current_user(_credentials(token))
    assert current.scopes == ()


def test_unknown_subject_or_username_mismatch_is_401():
    token = _user_token()
    del store._users["user"]
    with pytest.raises(HTTPException) as missing:
        get_current_user(_credentials(token))
    assert missing.value.status_code == 401

    store.reset()
    token = _user_token()
    current = store.get_user("user")
    assert current is not None
    store._users["user"] = replace(current, username="renamed")
    with pytest.raises(HTTPException) as mismatch:
        get_current_user(_credentials(token))
    assert mismatch.value.status_code == 401


def test_stored_role_overrides_the_role_claim():
    token = _user_token()
    store.set_role("user", "readonly")
    current = get_current_user(_credentials(token))
    assert current.role == "readonly"

    record = store.get_user("user")
    assert record is not None
    store._users["user"] = replace(record, role="nope")  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as exc:
        get_current_user(_credentials(token))
    assert exc.value.status_code == 401
