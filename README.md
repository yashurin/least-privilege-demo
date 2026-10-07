# Least Privilege Demo

A FastAPI service with four roles and one extra scope. Catalog reads, personal orders, team data, and admin actions each require a different role. Data is stored in memory and returns to the seed when the API process starts.

## Start

From this directory:

```bash
docker compose build
docker compose up -d
curl -sS -i http://localhost:8000/health
```

`/health` is public. A running API returns `200` and `{"status":"ok"}`.

The API is published at `http://localhost:8000`. Compose sets `JWT_SECRET` for the process. Interactive docs are at `/docs`. Opening a doc page does not grant access to a route.

Stop the stack with `docker compose down`. Start it again to restore the seeded users, orders, and report.

## Tests

Install the test tools once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Unit tests run inside this process and cover the store, token checks, role and scope dependencies, and every route:

```bash
pytest tests/unit
```

End-to-end tests use `requests` to run the curl checks in this README against a live API. Start the stack first. The suite expects the original seed, so restart the API before running it again.

```bash
docker compose up -d
pytest tests/e2e
```

`E2E_BASE_URL` selects the API when it is not `http://localhost:8000`. `pytest -m 'not e2e'` runs only the unit tests. `pytest -m e2e` runs only the end-to-end tests.

The curl blocks below are for bash. Run each block on its own. They expect a fresh seed, so restart the stack before a second full pass. The admin block deletes `order-1` and restores the `readonly` role before it finishes. The end-to-end suite performs that same sequence in one run.

## Accounts

Passwords match the usernames. Each account has one role.

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `admin` | `admin` |
| `manager` | `manager` | `manager` |
| `user` | `user` | `user` |
| `readonly` | `readonly` | `readonly` |

Seeded catalog items are `item-1` Notebook (1200 cents), `item-2` Pen Set (800 cents), and `item-3` Desk Lamp (4200 cents).

Seeded orders:

| Order | Owner | Item | Quantity |
| --- | --- | --- | --- |
| `order-1` | `user` | `item-1` | 1 |
| `order-2` | `user` | `item-2` | 2 |
| `order-3` | `manager` | `item-3` | 1 |

One team report is seeded: `report-1`, "Weekly team summary".

## Status codes

| Situation | Status | Body |
| --- | --- | --- |
| Missing or invalid token on a protected route | 401 | `{"detail":"Not authenticated"}` |
| Username and password do not match an account | 401 | `{"detail":"Invalid credentials"}` |
| Valid token whose role or scope is outside the route | 403 | `{"detail":"Forbidden"}` |
| Valid token whose role may read `/me/orders/{id}`, when that order is missing or owned by someone else | 404 | `{"detail":"Not found"}` |

A foreign order and a missing order return the same 404 body. `/me/orders` and `POST /me/orders` always use the token's user id as the owner.

The API reads the caller's role from the current user record on each request. A role change applies to tokens that are already issued. Scopes are a claim on the token. Login tokens omit `scopes`.

## Route matrix

Public routes accept any caller. Every other route needs `Authorization: Bearer <token>`.

| Method | Path | readonly | user | manager | admin |
| --- | --- | --- | --- | --- | --- |
| GET | `/health` | public | public | public | public |
| POST | `/token` | public | public | public | public |
| POST | `/token/scoped` | 403 | 403 | 403 | mints a scoped token |
| GET | `/catalog/items` | yes | yes | yes | yes |
| GET | `/catalog/items/{id}` | yes | yes | yes | yes |
| GET | `/me/orders` | 403 | own orders | own orders | own orders |
| GET | `/me/orders/{id}` | 403 | own order, otherwise 404 | own order, otherwise 404 | own order, otherwise 404 |
| POST | `/me/orders` | 403 | creates an order for the caller | creates an order for the caller | creates an order for the caller |
| GET | `/team/orders` | 403 | 403 | yes | yes |
| GET | `/team/reports` | 403 | 403 | yes | yes |
| GET | `/admin/users` | 403 | 403 | 403 | yes |
| POST | `/admin/users/{user_id}/role` | 403 | 403 | 403 | yes |
| DELETE | `/admin/orders/{id}` | 403 | 403 | 403 | yes |
| POST | `/admin/export` | 403 | 403 | 403 | requires scope `pii:export` |

`POST /token` and `POST /token/scoped` return 401 when the password is wrong. A correct password for `user`, `manager`, or `readonly` returns 403 from `/token/scoped`.

## Obtain a token

`POST /token` accepts JSON `username` and `password`. The access token is HS256 and expires in 30 minutes (`expires_in` is `1800`). Claims are `sub` (user id), `username`, and `role`.

```bash
curl -sS -i -X POST http://localhost:8000/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"user","password":"user"}'
```

A wrong password returns 401:

```bash
curl -sS -i -X POST http://localhost:8000/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"user","password":"wrong"}'
```

Decode a token to see the claims:

```bash
API=http://localhost:8000
USER_TOKEN=$(curl -sS -X POST "$API/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"user","password":"user"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
python3 - "$USER_TOKEN" <<'PY'
import base64, json, sys
payload = sys.argv[1].split(".")[1]
payload += "=" * (-len(payload) % 4)
print(json.dumps(json.loads(base64.urlsafe_b64decode(payload)), indent=2))
PY
```

## Readonly

Readonly can read the catalog. Creating an order returns 403.

```bash
API=http://localhost:8000
RO_TOKEN=$(curl -sS -X POST "$API/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"readonly","password":"readonly"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

echo "# catalog — expect 200"
curl -sS -i -H "Authorization: Bearer $RO_TOKEN" "$API/catalog/items"

echo "# one item — expect 200"
curl -sS -i -H "Authorization: Bearer $RO_TOKEN" "$API/catalog/items/item-1"

echo "# create an order — expect 403"
curl -sS -i -X POST "$API/me/orders" \
  -H "Authorization: Bearer $RO_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"item_id":"item-1","quantity":1}'
```

## User

A user can read and create their own orders. The manager's order returns 404. The admin user list returns 403.

```bash
API=http://localhost:8000
USER_TOKEN=$(curl -sS -X POST "$API/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"user","password":"user"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

echo "# own orders — expect 200, order-1 and order-2"
curl -sS -i -H "Authorization: Bearer $USER_TOKEN" "$API/me/orders"

echo "# own order — expect 200"
curl -sS -i -H "Authorization: Bearer $USER_TOKEN" "$API/me/orders/order-2"

echo "# manager order — expect 404"
curl -sS -i -H "Authorization: Bearer $USER_TOKEN" "$API/me/orders/order-3"

echo "# missing order — expect 404 with the same body"
curl -sS -i -H "Authorization: Bearer $USER_TOKEN" "$API/me/orders/order-999"

echo "# create an order — expect 201 and owner_id user"
curl -sS -i -X POST "$API/me/orders" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"item_id":"item-1","quantity":1}'

echo "# admin user list — expect 403"
curl -sS -i -H "Authorization: Bearer $USER_TOKEN" "$API/admin/users"
```

On a fresh seed the created order is `order-4`.

## Manager

A manager can read team orders and the team report. Deleting an order and changing a role return 403. `/me/orders` still returns only the manager's own order.

```bash
API=http://localhost:8000
MANAGER_TOKEN=$(curl -sS -X POST "$API/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"manager","password":"manager"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

echo "# team orders — expect 200, including order-1, order-2, and order-3"
curl -sS -i -H "Authorization: Bearer $MANAGER_TOKEN" "$API/team/orders"

echo "# team report — expect 200"
curl -sS -i -H "Authorization: Bearer $MANAGER_TOKEN" "$API/team/reports"

echo "# own orders only — expect 200 with order-3"
curl -sS -i -H "Authorization: Bearer $MANAGER_TOKEN" "$API/me/orders"

echo "# delete an order — expect 403"
curl -sS -i -X DELETE \
  -H "Authorization: Bearer $MANAGER_TOKEN" \
  "$API/admin/orders/order-1"

echo "# change a role — expect 403"
curl -sS -i -X POST "$API/admin/users/user/role" \
  -H "Authorization: Bearer $MANAGER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"role":"readonly"}'
```

## Admin

An admin can list users, change a role, and delete an order. `POST /admin/export` still returns 403 until the admin mints a token that carries `pii:export`.

```bash
API=http://localhost:8000
take() { python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'; }
ADMIN_TOKEN=$(curl -sS -X POST "$API/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}' | take)
RO_TOKEN=$(curl -sS -X POST "$API/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"readonly","password":"readonly"}' | take)
MANAGER_TOKEN=$(curl -sS -X POST "$API/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"manager","password":"manager"}' | take)

echo "# user list — expect 200, four accounts, no passwords"
curl -sS -i -H "Authorization: Bearer $ADMIN_TOKEN" "$API/admin/users"

echo "# export with the login token — expect 403"
curl -sS -i -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$API/admin/export"

echo "# promote readonly to user — expect 200"
curl -sS -i -X POST "$API/admin/users/readonly/role" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"role":"user"}'

echo "# same readonly token lists orders — expect 200"
curl -sS -i -H "Authorization: Bearer $RO_TOKEN" "$API/me/orders"

echo "# restore readonly — expect 200"
curl -sS -i -X POST "$API/admin/users/readonly/role" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"role":"readonly"}'

echo "# readonly token is catalog-only again — expect 403"
curl -sS -i -H "Authorization: Bearer $RO_TOKEN" "$API/me/orders"

echo "# delete order-1 — expect 204"
curl -sS -i -X DELETE \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$API/admin/orders/order-1"

echo "# team orders after the delete — expect 200 without order-1"
curl -sS -i -H "Authorization: Bearer $MANAGER_TOKEN" "$API/team/orders"
```

## Role and scope

`POST /token` issues an admin token with no `scopes` claim. `POST /admin/export` allows the admin role only when `scopes` includes `pii:export`. `POST /token/scoped` checks the admin username and password, then returns a short-lived admin token with `scopes: ["pii:export"]`. The export body is synthetic contact data.

```bash
API=http://localhost:8000
take() { python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'; }

echo "# user password cannot mint the scoped token — expect 403"
curl -sS -i -X POST "$API/token/scoped" \
  -H 'Content-Type: application/json' \
  -d '{"username":"user","password":"user"}'

echo "# wrong admin password — expect 401"
curl -sS -i -X POST "$API/token/scoped" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"wrong"}'

echo "# admin password mints the scoped token — expect 200"
SCOPED_TOKEN=$(curl -sS -X POST "$API/token/scoped" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}' | take)

echo "# export with that token — expect 200 and synthetic records"
curl -sS -i -X POST \
  -H "Authorization: Bearer $SCOPED_TOKEN" \
  "$API/admin/export"
```

## Demo limits

This is a demo. Data is stored in memory. The JWT secret is a shared demo value. There are no refresh tokens and no production identity provider.
