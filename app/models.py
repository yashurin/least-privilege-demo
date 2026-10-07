from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["admin", "manager", "user", "readonly"]
ROLE_SET = frozenset({"admin", "manager", "user", "readonly"})


class HealthResponse(BaseModel):
    status: Literal["ok"]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class PublicUser(BaseModel):
    id: str
    username: str
    role: Role


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role


class CatalogItem(BaseModel):
    id: str
    name: str
    price_cents: int


class Order(BaseModel):
    id: str
    owner_id: str
    item_id: str
    quantity: int


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=100)


class TeamReport(BaseModel):
    id: str
    title: str
    summary: str


class ExportRecord(BaseModel):
    user_id: str
    contact: str


class ExportResult(BaseModel):
    synthetic: Literal[True] = True
    records: list[ExportRecord]
