import os

import pytest
import requests

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000").rstrip("/")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def http() -> requests.Session:
    with requests.Session() as session:
        yield session


@pytest.fixture(scope="session", autouse=True)
def fresh_seed(http: requests.Session, base_url: str) -> None:
    try:
        health = http.get(f"{base_url}/health", timeout=3)
    except requests.RequestException as exc:
        pytest.fail(
            f"The API at {base_url} is not reachable ({exc}). "
            "Start it with `docker compose up -d`."
        )
    assert health.status_code == 200, health.text
    assert health.json() == {"status": "ok"}

    token = _token(http, base_url, "user", "user")
    orders = http.get(
        f"{base_url}/me/orders",
        headers={"Authorization": f"Bearer {token}"},
        timeout=3,
    )
    assert orders.status_code == 200, orders.text
    order_ids = [order["id"] for order in orders.json()]
    if order_ids != ["order-1", "order-2"]:
        pytest.fail(
            "End-to-end tests need a fresh seed "
            f"(user orders are {order_ids}). Restart with `docker compose restart api`."
        )

    admin = _token(http, base_url, "admin", "admin")
    users = http.get(
        f"{base_url}/admin/users",
        headers={"Authorization": f"Bearer {admin}"},
        timeout=3,
    )
    assert users.status_code == 200, users.text
    roles = {user["username"]: user["role"] for user in users.json()}
    if roles.get("readonly") != "readonly":
        pytest.fail(
            "End-to-end tests need the seeded readonly role. "
            "Restart with `docker compose restart api`."
        )


def _token(http: requests.Session, base_url: str, username: str, password: str) -> str:
    response = http.post(
        f"{base_url}/token",
        json={"username": username, "password": password},
        timeout=3,
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
