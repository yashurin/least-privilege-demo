from fastapi import APIRouter, Depends

from app.authz import PROTECTED_RESPONSES, TEAM_ROLES, require_roles
from app.models import Order, TeamReport
from app.store import store

router = APIRouter(
    prefix="/team",
    tags=["team"],
    dependencies=[Depends(require_roles(*TEAM_ROLES))],
    responses=PROTECTED_RESPONSES,
)


@router.get("/orders", response_model=list[Order])
def list_team_orders() -> list[Order]:
    return store.list_orders()


@router.get("/reports", response_model=list[TeamReport])
def list_team_reports() -> list[TeamReport]:
    return store.list_reports()
