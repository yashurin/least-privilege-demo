from fastapi import FastAPI

from app.models import HealthResponse
from app.routers import admin, auth, catalog, orders, team

app = FastAPI(
    title="Least Privilege Demo",
    version="1.0.0",
    description="Role checks and one scope check on an in-memory API.",
)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(orders.router)
app.include_router(team.router)
app.include_router(admin.router)
