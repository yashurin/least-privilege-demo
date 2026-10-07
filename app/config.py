import os
from datetime import timedelta

JWT_SECRET = os.environ.get("JWT_SECRET", "demo-only-shared-secret-not-for-production")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must not be empty")

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(minutes=30)


def expires_in_seconds() -> int:
    return int(ACCESS_TOKEN_TTL.total_seconds())
