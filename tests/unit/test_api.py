from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import JWT_ALGORITHM, JWT_SECRET
from tests.unit.conftest import bearer, issue_token


def test_health_is_public(api):
    response = api.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    schema = api.get("/openapi.json").json()
    assert "security" not in schema["paths"]["/health"]["get"]


def test_login_and_unknown_account_share_one_401(api):
    bad = api.post("/token", json={"username": "user", "password": "wrong"})
    unknown = api.post("/token", json={"username": "nobody", "password": "nobody"})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json() == {"detail": "Invalid credentials"}
    assert "www-authenticate" not in bad.headers
    extra = api.post("/token", json={"username": "user", "password": "user", "role": "admin"})
    assert extra.status_code == 422


def test_protected_routes_reject_missing_and_bad_credentials(api):
    missing = api.get("/catalog/items/missing")
    assert missing.status_code == 401
    assert missing.json() == {"detail": "Not authenticated"}
    assert missing.headers["www-authenticate"].lower().startswith("bearer")

    basic = api.get("/me/orders", headers={"Authorization": "Basic aaa"})
    garbage = api.get("/team/orders", headers={"Authorization": "Bearer not-a-jwt"})
    tampered = issue_token(api, "user") + "x"
    expired = jwt.encode(
        {
            "sub": "user",
            "username": "user",
            "role": "user",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    assert basic.status_code == 401
    assert garbage.status_code == 401
    assert api.get("/me/orders", headers=bearer(tampered)).status_code == 401
    assert api.get("/catalog/items", headers=bearer(expired)).status_code == 401


@pytest.mark.parametrize(
    ("role", "method", "path", "expected"),
    [
        ("readonly", "GET", "/catalog/items", 200),
        ("readonly", "GET", "/catalog/items/item-1", 200),
        ("readonly", "GET", "/catalog/items/missing", 404),
        ("readonly", "GET", "/me/orders", 403),
        ("readonly", "GET", "/me/orders/order-3", 403),
        ("readonly", "GET", "/team/orders", 403),
        ("readonly", "GET", "/team/reports", 403),
        ("readonly", "GET", "/admin/users", 403),
        ("readonly", "POST", "/admin/export", 403),
        ("user", "GET", "/me/orders/order-2", 200),
        ("user", "GET", "/me/orders/order-3", 404),
        ("user", "GET", "/me/orders/order-999", 404),
        ("user", "GET", "/team/reports", 403),
        ("user", "GET", "/admin/users", 403),
        ("user", "DELETE", "/admin/orders/order-1", 403),
        ("manager", "GET", "/me/orders/order-1", 404),
        ("manager", "GET", "/me/orders/order-3", 200),
        ("manager", "GET", "/team/orders", 200),
        ("manager", "GET", "/team/reports", 200),
        ("manager", "POST", "/admin/users/user/role", 403),
        ("manager", "DELETE", "/admin/orders/order-1", 403),
        ("manager", "POST", "/admin/export", 403),
        ("admin", "GET", "/team/orders", 200),
        ("admin", "GET", "/team/reports", 200),
        ("admin", "GET", "/admin/users", 200),
        ("admin", "POST", "/admin/export", 403),
    ],
)
def test_role_matrix(api, role, method, path, expected):
    kwargs = {"json": {"role": "readonly"}} if path.endswith("/role") else {}
    response = api.request(method, path, headers=bearer(issue_token(api, role)), **kwargs)
    assert response.status_code == expected


def test_foreign_and_missing_orders_share_a_404_body(api):
    headers = bearer(issue_token(api, "user"))
    foreign = api.get("/me/orders/order-3", headers=headers)
    missing = api.get("/me/orders/order-999", headers=headers)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"detail": "Not found"}
    own = api.get("/me/orders", headers=headers).json()
    assert [order["id"] for order in own] == ["order-1", "order-2"]


def test_create_order_is_owned_by_the_caller(api):
    readonly = bearer(issue_token(api, "readonly"))
    before = api.get("/team/orders", headers=bearer(issue_token(api, "admin"))).json()
    rejected = api.post("/me/orders", headers=readonly, json={"item_id": "item-1", "quantity": 1})
    after = api.get("/team/orders", headers=bearer(issue_token(api, "admin"))).json()
    assert rejected.status_code == 403
    assert rejected.json() == {"detail": "Forbidden"}
    assert [order["id"] for order in before] == [order["id"] for order in after]

    created = api.post(
        "/me/orders",
        headers=bearer(issue_token(api, "user")),
        json={"item_id": "item-1", "quantity": 1},
    )
    assert created.status_code == 201
    assert created.json()["id"] == "order-4"
    assert created.json()["owner_id"] == "user"
    assert api.post(
        "/me/orders",
        headers=bearer(issue_token(api, "user")),
        json={"item_id": "item-1", "quantity": 1, "owner_id": "admin"},
    ).status_code == 422
    assert api.post(
        "/me/orders",
        headers=bearer(issue_token(api, "user")),
        json={"item_id": "missing", "quantity": 1},
    ).status_code == 400
    assert api.post(
        "/me/orders",
        headers=bearer(issue_token(api, "admin")),
        json={"item_id": "item-3", "quantity": 2},
    ).json()["owner_id"] == "admin"


def test_admin_role_change_applies_to_the_existing_token(api):
    readonly = issue_token(api, "readonly")
    admin = bearer(issue_token(api, "admin"))
    users = api.get("/admin/users", headers=admin).json()
    assert sorted(user["username"] for user in users) == ["admin", "manager", "readonly", "user"]
    assert "password" not in str(users)

    promoted = api.post("/admin/users/readonly/role", headers=admin, json={"role": "user"})
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "user"
    assert api.get("/me/orders", headers=bearer(readonly)).status_code == 200

    restored = api.post("/admin/users/readonly/role", headers=admin, json={"role": "readonly"})
    assert restored.json()["role"] == "readonly"
    assert api.get("/me/orders", headers=bearer(readonly)).status_code == 403
    assert api.post("/admin/users/missing/role", headers=admin, json={"role": "user"}).status_code == 404
    assert api.post("/admin/users/user/role", headers=admin, json={"role": "owner"}).status_code == 422
    assert api.post(
        "/admin/users/user/role",
        headers=admin,
        json={"role": "user", "password": "nope"},
    ).status_code == 422


def test_admin_delete_and_scoped_export(api):
    admin = issue_token(api, "admin")
    assert api.delete("/admin/orders/order-1", headers=bearer(issue_token(api, "manager"))).status_code == 403
    deleted = api.delete("/admin/orders/order-1", headers=bearer(admin))
    assert deleted.status_code == 204
    assert deleted.content == b""
    remaining = [order["id"] for order in api.get("/team/orders", headers=bearer(admin)).json()]
    assert "order-1" not in remaining
    assert "order-2" in remaining
    assert api.delete("/admin/orders/order-1", headers=bearer(admin)).status_code == 404

    assert api.post("/token/scoped", json={"username": "user", "password": "user"}).status_code == 403
    assert api.post("/token/scoped", json={"username": "admin", "password": "wrong"}).status_code == 401
    scoped = api.post("/token/scoped", json={"username": "admin", "password": "admin"})
    assert scoped.status_code == 200
    token = scoped.json()["access_token"]
    claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert claims["scopes"] == ["pii:export"]
    assert claims["role"] == "admin"
    assert api.post("/admin/export", headers=bearer(admin)).status_code == 403
    exported = api.post("/admin/export", headers=bearer(token))
    assert exported.status_code == 200
    body = exported.json()
    assert body["synthetic"] is True
    assert body["records"] == [
        {"user_id": "user", "contact": "user@example.invalid"},
        {"user_id": "manager", "contact": "manager@example.invalid"},
    ]
    assert api.get("/admin/users", headers=bearer(token)).status_code == 200


def test_catalog_and_team_payloads(api):
    catalog = api.get("/catalog/items", headers=bearer(issue_token(api, "readonly"))).json()
    assert catalog[0] == {"id": "item-1", "name": "Notebook", "price_cents": 1200}
    item = api.get("/catalog/items/item-2", headers=bearer(issue_token(api, "user"))).json()
    assert item["name"] == "Pen Set"
    reports = api.get("/team/reports", headers=bearer(issue_token(api, "manager"))).json()
    assert reports[0]["title"] == "Weekly team summary"
    mine = api.get("/me/orders", headers=bearer(issue_token(api, "manager"))).json()
    assert [order["id"] for order in mine] == ["order-3"]
