import threading
from dataclasses import replace

import pytest

from app.models import Order
from app.store import MemoryStore, UserRecord, store


def test_seed_matches_the_documented_data():
    assert [user.username for user in store.list_users()] == [
        "admin",
        "manager",
        "readonly",
        "user",
    ]
    assert [(user.username, user.role) for user in store.list_users()] == [
        ("admin", "admin"),
        ("manager", "manager"),
        ("readonly", "readonly"),
        ("user", "user"),
    ]
    assert [(item.id, item.name, item.price_cents) for item in store.list_items()] == [
        ("item-1", "Notebook", 1200),
        ("item-2", "Pen Set", 800),
        ("item-3", "Desk Lamp", 4200),
    ]
    assert [(order.id, order.owner_id, order.item_id, order.quantity) for order in store.list_orders()] == [
        ("order-1", "user", "item-1", 1),
        ("order-2", "user", "item-2", 2),
        ("order-3", "manager", "item-3", 1),
    ]
    reports = store.list_reports()
    assert len(reports) == 1
    assert reports[0].id == "report-1"
    assert reports[0].title == "Weekly team summary"


def test_user_lookup_and_password_repr():
    admin = store.get_user("admin")
    assert admin is not None
    assert store.get_user_by_username("admin") == admin
    assert store.get_user("missing") is None
    assert store.get_user_by_username("missing") is None
    assert "password=" not in repr(admin)
    listed = store.list_users()
    assert all(not hasattr(user, "password") for user in listed)


def test_seed_rejects_an_order_for_an_unknown_owner(monkeypatch):
    monkeypatch.setattr(
        "app.store._SEED_ORDERS",
        (Order(id="order-x", owner_id="ghost", item_id="item-1", quantity=1),),
    )
    with pytest.raises(RuntimeError, match="bad seed order order-x"):
        MemoryStore()


def test_duplicate_user_is_rejected():
    with pytest.raises(RuntimeError, match="duplicate user"):
        store._add_user(UserRecord(id="extra", username="admin", password="admin", role="admin"))


def test_set_role_updates_the_record_and_rejects_unknown_values():
    updated = store.set_role("readonly", "user")
    assert updated is not None
    assert updated.role == "user"
    assert store.get_user("readonly").role == "user"
    assert store.set_role("missing", "user") is None
    with pytest.raises(ValueError, match="unknown role"):
        store.set_role("user", "owner")  # type: ignore[arg-type]


def test_orders_are_scoped_to_the_owner_and_sorted_numerically():
    assert [order.id for order in store.list_orders_for("user")] == ["order-1", "order-2"]
    assert [order.id for order in store.list_orders_for("admin")] == []
    own = store.get_own_order("order-2", "user")
    assert own is not None and own.owner_id == "user"
    assert store.get_own_order("order-3", "user") is None
    assert store.get_own_order("order-999", "user") is None

    for _ in range(7):
        store.create_order("user", "item-1", 1)
    ids = [order.id for order in store.list_orders()]
    assert ids.index("order-10") > ids.index("order-2")
    assert ids == sorted(ids, key=lambda order_id: int(order_id.removeprefix("order-")))


def test_create_order_assigns_the_next_id_and_rejects_bad_input():
    created = store.create_order("manager", "item-2", 4)
    assert created == Order(id="order-4", owner_id="manager", item_id="item-2", quantity=4)
    assert store.get_item("missing") is None
    assert store.create_order("user", "missing", 1) is None
    with pytest.raises(RuntimeError, match="unknown owner"):
        store.create_order("ghost", "item-1", 1)


def test_delete_order_removes_only_that_row():
    assert store.delete_order("order-1") is True
    assert store.get_own_order("order-1", "user") is None
    assert store.get_own_order("order-2", "user") is not None
    assert store.delete_order("order-1") is False


def test_reset_restores_the_seed_after_writes():
    store.set_role("readonly", "admin")
    store.create_order("user", "item-1", 1)
    store.delete_order("order-2")
    store.reset()
    assert store.get_user("readonly").role == "readonly"
    assert [order.id for order in store.list_orders()] == ["order-1", "order-2", "order-3"]
    assert store.create_order("user", "item-1", 1).id == "order-4"


def test_concurrent_creates_keep_unique_ids():
    errors: list[Exception] = []

    def create() -> None:
        try:
            store.create_order("user", "item-1", 1)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=create) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    ids = [order.id for order in store.list_orders()]
    assert len(ids) == 23
    assert len(set(ids)) == 23


def test_replacing_a_user_record_does_not_break_lookup_of_others():
    current = store.get_user("user")
    assert current is not None
    store._users["user"] = replace(current, role="manager")
    assert store.get_user("admin").role == "admin"
    assert store.get_user("user").role == "manager"
