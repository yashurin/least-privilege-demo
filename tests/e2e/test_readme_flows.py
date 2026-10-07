"""The curl sequences from the README, in the same order, against a running API.

Run this file on a fresh process. Later tests create order-4 and delete order-1.
"""

import base64
import json

import pytest
import requests

pytestmark = pytest.mark.e2e


def _token(http: requests.Session, base_url: str, username: str, password: str) -> str:
    response = http.post(
        f"{base_url}/token",
        json={"username": username, "password": password},
        timeout=3,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    return body["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _claims(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def _header(token: str) -> dict:
    segment = token.split(".")[0]
    segment += "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(segment))


def test_health(http: requests.Session, base_url: str):
    response = http.get(f"{base_url}/health", timeout=3)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_obtain_a_token(http: requests.Session, base_url: str):
    issued = http.post(
        f"{base_url}/token",
        json={"username": "user", "password": "user"},
        timeout=3,
    )
    assert issued.status_code == 200
    body = issued.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    claims = _claims(body["access_token"])
    assert claims["sub"] == "user"
    assert claims["username"] == "user"
    assert claims["role"] == "user"
    assert claims["exp"] - claims["iat"] == 1800
    assert "scopes" not in claims
    assert _header(body["access_token"])["alg"] == "HS256"

    rejected = http.post(
        f"{base_url}/token",
        json={"username": "user", "password": "wrong"},
        timeout=3,
    )
    assert rejected.status_code == 401
    assert rejected.json() == {"detail": "Invalid credentials"}


def test_readonly(http: requests.Session, base_url: str):
    token = _token(http, base_url, "readonly", "readonly")
    catalog = http.get(f"{base_url}/catalog/items", headers=_auth(token), timeout=3)
    assert catalog.status_code == 200
    assert [item["id"] for item in catalog.json()] == ["item-1", "item-2", "item-3"]

    item = http.get(f"{base_url}/catalog/items/item-1", headers=_auth(token), timeout=3)
    assert item.status_code == 200
    assert item.json() == {"id": "item-1", "name": "Notebook", "price_cents": 1200}

    created = http.post(
        f"{base_url}/me/orders",
        headers={**_auth(token), "Content-Type": "application/json"},
        json={"item_id": "item-1", "quantity": 1},
        timeout=3,
    )
    assert created.status_code == 403
    assert created.json() == {"detail": "Forbidden"}


def test_user(http: requests.Session, base_url: str):
    token = _token(http, base_url, "user", "user")
    orders = http.get(f"{base_url}/me/orders", headers=_auth(token), timeout=3)
    assert orders.status_code == 200
    assert [order["id"] for order in orders.json()] == ["order-1", "order-2"]

    own = http.get(f"{base_url}/me/orders/order-2", headers=_auth(token), timeout=3)
    assert own.status_code == 200
    assert own.json()["owner_id"] == "user"
    assert own.json()["item_id"] == "item-2"
    assert own.json()["quantity"] == 2

    foreign = http.get(f"{base_url}/me/orders/order-3", headers=_auth(token), timeout=3)
    missing = http.get(f"{base_url}/me/orders/order-999", headers=_auth(token), timeout=3)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"detail": "Not found"}

    created = http.post(
        f"{base_url}/me/orders",
        headers={**_auth(token), "Content-Type": "application/json"},
        json={"item_id": "item-1", "quantity": 1},
        timeout=3,
    )
    assert created.status_code == 201
    assert created.json()["id"] == "order-4"
    assert created.json()["owner_id"] == "user"

    admin_users = http.get(f"{base_url}/admin/users", headers=_auth(token), timeout=3)
    assert admin_users.status_code == 403
    assert admin_users.json() == {"detail": "Forbidden"}


def test_manager(http: requests.Session, base_url: str):
    token = _token(http, base_url, "manager", "manager")
    team = http.get(f"{base_url}/team/orders", headers=_auth(token), timeout=3)
    assert team.status_code == 200
    team_ids = [order["id"] for order in team.json()]
    assert {"order-1", "order-2", "order-3"} <= set(team_ids)

    reports = http.get(f"{base_url}/team/reports", headers=_auth(token), timeout=3)
    assert reports.status_code == 200
    assert reports.json()[0]["id"] == "report-1"
    assert reports.json()[0]["title"] == "Weekly team summary"

    mine = http.get(f"{base_url}/me/orders", headers=_auth(token), timeout=3)
    assert mine.status_code == 200
    assert [order["id"] for order in mine.json()] == ["order-3"]

    deleted = http.delete(f"{base_url}/admin/orders/order-1", headers=_auth(token), timeout=3)
    assert deleted.status_code == 403
    assert deleted.json() == {"detail": "Forbidden"}

    role_change = http.post(
        f"{base_url}/admin/users/user/role",
        headers={**_auth(token), "Content-Type": "application/json"},
        json={"role": "readonly"},
        timeout=3,
    )
    assert role_change.status_code == 403
    assert role_change.json() == {"detail": "Forbidden"}


def test_admin(http: requests.Session, base_url: str):
    admin = _token(http, base_url, "admin", "admin")
    readonly = _token(http, base_url, "readonly", "readonly")
    manager = _token(http, base_url, "manager", "manager")

    users = http.get(f"{base_url}/admin/users", headers=_auth(admin), timeout=3)
    assert users.status_code == 200
    body = users.json()
    assert sorted(user["username"] for user in body) == ["admin", "manager", "readonly", "user"]
    assert "password" not in json.dumps(body)

    export = http.post(f"{base_url}/admin/export", headers=_auth(admin), timeout=3)
    assert export.status_code == 403
    assert export.json() == {"detail": "Forbidden"}

    promoted = http.post(
        f"{base_url}/admin/users/readonly/role",
        headers={**_auth(admin), "Content-Type": "application/json"},
        json={"role": "user"},
        timeout=3,
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "user"
    listed = http.get(f"{base_url}/me/orders", headers=_auth(readonly), timeout=3)
    assert listed.status_code == 200
    assert listed.json() == []

    restored = http.post(
        f"{base_url}/admin/users/readonly/role",
        headers={**_auth(admin), "Content-Type": "application/json"},
        json={"role": "readonly"},
        timeout=3,
    )
    assert restored.status_code == 200
    assert restored.json()["role"] == "readonly"
    denied = http.get(f"{base_url}/me/orders", headers=_auth(readonly), timeout=3)
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Forbidden"}

    deleted = http.delete(f"{base_url}/admin/orders/order-1", headers=_auth(admin), timeout=3)
    assert deleted.status_code == 204
    assert deleted.content == b""

    team = http.get(f"{base_url}/team/orders", headers=_auth(manager), timeout=3)
    assert team.status_code == 200
    team_ids = [order["id"] for order in team.json()]
    assert "order-1" not in team_ids
    assert "order-2" in team_ids
    assert "order-3" in team_ids


def test_role_and_scope(http: requests.Session, base_url: str):
    user_scoped = http.post(
        f"{base_url}/token/scoped",
        json={"username": "user", "password": "user"},
        timeout=3,
    )
    assert user_scoped.status_code == 403
    assert user_scoped.json() == {"detail": "Forbidden"}

    bad_admin = http.post(
        f"{base_url}/token/scoped",
        json={"username": "admin", "password": "wrong"},
        timeout=3,
    )
    assert bad_admin.status_code == 401
    assert bad_admin.json() == {"detail": "Invalid credentials"}

    minted = http.post(
        f"{base_url}/token/scoped",
        json={"username": "admin", "password": "admin"},
        timeout=3,
    )
    assert minted.status_code == 200
    token = minted.json()["access_token"]
    assert minted.json()["expires_in"] == 1800
    claims = _claims(token)
    assert claims["sub"] == "admin"
    assert claims["role"] == "admin"
    assert claims["scopes"] == ["pii:export"]
    assert claims["exp"] - claims["iat"] == 1800

    exported = http.post(f"{base_url}/admin/export", headers=_auth(token), timeout=3)
    assert exported.status_code == 200
    body = exported.json()
    assert body["synthetic"] is True
    assert body["records"] == [
        {"user_id": "user", "contact": "user@example.invalid"},
        {"user_id": "manager", "contact": "manager@example.invalid"},
    ]
