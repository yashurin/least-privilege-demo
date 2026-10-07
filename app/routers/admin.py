from fastapi import APIRouter, Depends, Response

from app.authz import (
    ADMIN_ROLES,
    EXPORT_SCOPE,
    PROTECTED_RESPONSES,
    require_roles,
    require_scopes,
)
from app.errors import not_found
from app.models import ExportRecord, ExportResult, PublicUser, RoleUpdate
from app.store import store

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles(*ADMIN_ROLES))],
    responses=PROTECTED_RESPONSES,
)


@router.get("/users", response_model=list[PublicUser])
def list_users() -> list[PublicUser]:
    return store.list_users()


@router.post(
    "/users/{user_id}/role",
    response_model=PublicUser,
    responses={404: {"description": "No user with that id"}},
)
def set_user_role(user_id: str, body: RoleUpdate) -> PublicUser:
    updated = store.set_role(user_id, body.role)
    if updated is None:
        raise not_found()
    return updated


@router.delete(
    "/orders/{order_id}",
    status_code=204,
    responses={404: {"description": "No order with that id"}},
)
def delete_order(order_id: str) -> Response:
    if not store.delete_order(order_id):
        raise not_found()
    return Response(status_code=204)


@router.post(
    "/export",
    response_model=ExportResult,
    dependencies=[Depends(require_scopes(EXPORT_SCOPE))],
)
def export_pii() -> ExportResult:
    return ExportResult(
        records=[
            ExportRecord(user_id="user", contact="user@example.invalid"),
            ExportRecord(user_id="manager", contact="manager@example.invalid"),
        ]
    )
