import pytest
from pydantic import ValidationError

from app.models import ROLE_SET, ExportResult, LoginRequest, OrderCreate, RoleUpdate, TokenResponse


def test_role_set_matches_the_documented_roles():
    assert ROLE_SET == {"admin", "manager", "user", "readonly"}


def test_login_rejects_extra_fields():
    with pytest.raises(ValidationError):
        LoginRequest.model_validate({"username": "user", "password": "user", "role": "admin"})


def test_order_create_bounds_and_owner_are_closed():
    order = OrderCreate.model_validate({"item_id": "item-1", "quantity": 100})
    assert order.quantity == 100
    with pytest.raises(ValidationError):
        OrderCreate.model_validate({"item_id": "item-1", "quantity": 0})
    with pytest.raises(ValidationError):
        OrderCreate.model_validate({"item_id": "item-1", "quantity": 101})
    with pytest.raises(ValidationError):
        OrderCreate.model_validate({"item_id": "", "quantity": 1})
    with pytest.raises(ValidationError):
        OrderCreate.model_validate({"item_id": "item-1", "quantity": 1, "owner_id": "admin"})


def test_role_update_rejects_unknown_roles_and_extra_fields():
    assert RoleUpdate.model_validate({"role": "manager"}).role == "manager"
    with pytest.raises(ValidationError):
        RoleUpdate.model_validate({"role": "owner"})
    with pytest.raises(ValidationError):
        RoleUpdate.model_validate({"role": "user", "password": "user"})


def test_token_and_export_defaults():
    token = TokenResponse(access_token="abc", expires_in=1800)
    assert token.token_type == "bearer"
    exported = ExportResult(records=[])
    assert exported.synthetic is True
