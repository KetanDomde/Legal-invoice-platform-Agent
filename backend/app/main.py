from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.database_async import init_db
from app.api import (
    alert,
    audit_log,
    budget,
    budget_ledger,
    firm,
    invoice,
    line_item,
    matter,
    user,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: auto-create tables. Use Alembic migrations in production.
    await init_db()
    yield


app = FastAPI(
    title="Legal Billing API",
    description="CRUD API for firms, matters, budgets, invoices, and related billing entities.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow_origins is wide open for local dev; lock this down to your
# actual frontend origin(s) before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(firm.router)
app.include_router(matter.router)
app.include_router(budget.router)
app.include_router(user.router)
app.include_router(invoice.router)
app.include_router(line_item.router)
app.include_router(budget_ledger.router)
app.include_router(alert.router)
app.include_router(audit_log.router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
