from fastapi import APIRouter

from app.authz import EXPORT_SCOPE
from app.config import expires_in_seconds
from app.errors import forbidden, invalid_credentials
from app.models import LoginRequest, TokenResponse
from app.security import authenticate, create_access_token

router = APIRouter(tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    user = authenticate(body.username, body.password)
    if user is None:
        raise invalid_credentials()
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=expires_in_seconds(),
    )


@router.post("/token/scoped", response_model=TokenResponse)
def login_scoped(body: LoginRequest) -> TokenResponse:
    user = authenticate(body.username, body.password)
    if user is None:
        raise invalid_credentials()
    if user.role != "admin":
        raise forbidden()
    return TokenResponse(
        access_token=create_access_token(user, scopes=(EXPORT_SCOPE,)),
        expires_in=expires_in_seconds(),
    )
