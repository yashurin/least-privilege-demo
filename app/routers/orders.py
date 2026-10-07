from fastapi import APIRouter

from app.authz import PROTECTED_RESPONSES, OrderUser
from app.errors import bad_request, not_found
from app.models import Order, OrderCreate
from app.store import store

router = APIRouter(prefix="/me", tags=["orders"], responses=PROTECTED_RESPONSES)


@router.get("/orders", response_model=list[Order])
def list_my_orders(current: OrderUser) -> list[Order]:
    return store.list_orders_for(current.id)


@router.get(
    "/orders/{order_id}",
    response_model=Order,
    responses={404: {"description": "No order with that id for the caller"}},
)
def get_my_order(order_id: str, current: OrderUser) -> Order:
    order = store.get_own_order(order_id, current.id)
    if order is None:
        raise not_found()
    return order


@router.post("/orders", response_model=Order, status_code=201)
def create_my_order(body: OrderCreate, current: OrderUser) -> Order:
    order = store.create_order(current.id, body.item_id, body.quantity)
    if order is None:
        raise bad_request("Unknown catalog item")
    return order
