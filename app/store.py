"""In-memory users, catalog, orders, and reports. A restart restores the seed."""

from dataclasses import dataclass, field, replace
from threading import Lock

from app.models import ROLE_SET, CatalogItem, Order, PublicUser, Role, TeamReport


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: str
    username: str
    password: str = field(repr=False)
    role: Role


def _order_sort_key(order: Order) -> int:
    return int(order.id.removeprefix("order-"))


_SEED_ORDERS = (
    Order(id="order-1", owner_id="user", item_id="item-1", quantity=1),
    Order(id="order-2", owner_id="user", item_id="item-2", quantity=2),
    Order(id="order-3", owner_id="manager", item_id="item-3", quantity=1),
)


class MemoryStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._users: dict[str, UserRecord] = {}
        self._users_by_name: dict[str, UserRecord] = {}
        self._items: dict[str, CatalogItem] = {}
        self._orders: dict[str, Order] = {}
        self._reports: dict[str, TeamReport] = {}
        self._next_order = 0
        self._seed()

    def reset(self) -> None:
        """Replace all data with the original seed."""
        with self._lock:
            self._users.clear()
            self._users_by_name.clear()
            self._items.clear()
            self._orders.clear()
            self._reports.clear()
            self._next_order = 0
            self._seed()

    def _add_user(self, user: UserRecord) -> None:
        if user.id in self._users or user.username in self._users_by_name:
            raise RuntimeError(f"duplicate user {user.username}")
        self._users[user.id] = user
        self._users_by_name[user.username] = user

    def _seed(self) -> None:
        for username, role in (
            ("admin", "admin"),
            ("manager", "manager"),
            ("user", "user"),
            ("readonly", "readonly"),
        ):
            self._add_user(
                UserRecord(
                    id=username,
                    username=username,
                    password=username,
                    role=role,
                )
            )

        for item in (
            CatalogItem(id="item-1", name="Notebook", price_cents=1200),
            CatalogItem(id="item-2", name="Pen Set", price_cents=800),
            CatalogItem(id="item-3", name="Desk Lamp", price_cents=4200),
        ):
            self._items[item.id] = item

        for order in _SEED_ORDERS:
            if order.owner_id not in self._users or order.item_id not in self._items:
                raise RuntimeError(f"bad seed order {order.id}")
            self._orders[order.id] = order
        self._next_order = 3

        report = TeamReport(
            id="report-1",
            title="Weekly team summary",
            summary="Synthetic totals for the demo team.",
        )
        self._reports[report.id] = report

    def get_user(self, user_id: str) -> UserRecord | None:
        with self._lock:
            return self._users.get(user_id)

    def get_user_by_username(self, username: str) -> UserRecord | None:
        with self._lock:
            return self._users_by_name.get(username)

    def list_users(self) -> list[PublicUser]:
        with self._lock:
            users = list(self._users.values())
        return [
            PublicUser(id=user.id, username=user.username, role=user.role)
            for user in sorted(users, key=lambda user: user.id)
        ]

    def set_role(self, user_id: str, role: Role) -> PublicUser | None:
        if role not in ROLE_SET:
            raise ValueError("unknown role")
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                return None
            updated = replace(user, role=role)
            self._users[user_id] = updated
            self._users_by_name[updated.username] = updated
        return PublicUser(id=updated.id, username=updated.username, role=updated.role)

    def list_items(self) -> list[CatalogItem]:
        with self._lock:
            items = list(self._items.values())
        return sorted(items, key=lambda item: item.id)

    def get_item(self, item_id: str) -> CatalogItem | None:
        with self._lock:
            return self._items.get(item_id)

    def list_orders_for(self, owner_id: str) -> list[Order]:
        with self._lock:
            orders = [
                order for order in self._orders.values() if order.owner_id == owner_id
            ]
        return sorted(orders, key=_order_sort_key)

    def get_own_order(self, order_id: str, owner_id: str) -> Order | None:
        """Return the order only when this owner holds it.

        A missing id and someone else's id both return None so callers
        answer 404 either way.
        """
        with self._lock:
            order = self._orders.get(order_id)
            if order is None or order.owner_id != owner_id:
                return None
            return order

    def list_orders(self) -> list[Order]:
        with self._lock:
            orders = list(self._orders.values())
        return sorted(orders, key=_order_sort_key)

    def create_order(self, owner_id: str, item_id: str, quantity: int) -> Order | None:
        with self._lock:
            if owner_id not in self._users:
                raise RuntimeError(f"unknown owner {owner_id}")
            if item_id not in self._items:
                return None
            self._next_order += 1
            order = Order(
                id=f"order-{self._next_order}",
                owner_id=owner_id,
                item_id=item_id,
                quantity=quantity,
            )
            self._orders[order.id] = order
            return order

    def delete_order(self, order_id: str) -> bool:
        with self._lock:
            if order_id not in self._orders:
                return False
            del self._orders[order_id]
            return True

    def list_reports(self) -> list[TeamReport]:
        with self._lock:
            reports = list(self._reports.values())
        return sorted(reports, key=lambda report: report.id)


store = MemoryStore()
