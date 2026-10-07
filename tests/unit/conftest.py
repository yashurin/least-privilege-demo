import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()
    yield
    store.reset()


@pytest.fixture
def api():
    with TestClient(app) as client:
        yield client


def issue_token(api: TestClient, username: str, password: str | None = None) -> str:
    response = api.post(
        "/token",
        json={"username": username, "password": username if password is None else password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
