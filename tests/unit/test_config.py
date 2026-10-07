import importlib

import pytest

from app.config import ACCESS_TOKEN_TTL, JWT_ALGORITHM, JWT_SECRET, expires_in_seconds


def test_token_lifetime_is_thirty_minutes():
    assert JWT_ALGORITHM == "HS256"
    assert expires_in_seconds() == 1800
    assert ACCESS_TOKEN_TTL.total_seconds() == 1800


def test_hmac_secret_meets_sha256_length():
    assert len(JWT_SECRET.encode("utf-8")) >= 32


def test_empty_secret_fails_closed(monkeypatch):
    import app.config as config

    monkeypatch.setenv("JWT_SECRET", "")
    try:
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            importlib.reload(config)
    finally:
        monkeypatch.setenv("JWT_SECRET", "demo-only-shared-secret-not-for-production")
        importlib.reload(config)
    assert config.expires_in_seconds() == 1800
