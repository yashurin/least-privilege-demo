from fastapi import APIRouter, Depends

from app.authz import CATALOG_ROLES, PROTECTED_RESPONSES, require_roles
from app.errors import not_found
from app.models import CatalogItem
from app.store import store

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
    dependencies=[Depends(require_roles(*CATALOG_ROLES))],
    responses=PROTECTED_RESPONSES,
)


@router.get("/items", response_model=list[CatalogItem])
def list_items() -> list[CatalogItem]:
    return store.list_items()


@router.get(
    "/items/{item_id}",
    response_model=CatalogItem,
    responses={404: {"description": "No catalog item with that id"}},
)
def get_item(item_id: str) -> CatalogItem:
    item = store.get_item(item_id)
    if item is None:
        raise not_found()
    return item
