"""
FastAPI app entrypoint — was a 0-byte empty file. Wired up just enough to
make the invoice pipeline reachable over HTTP; login/RBAC routes are
Trinkesh's territory and intentionally not added here (see routers/invoices.py
for the specific TODO on auth).

Run with:  uvicorn app.main:app --reload   (from backend/, venv active)
Then open: http://127.0.0.1:8000/docs      (interactive Swagger UI — lets
you upload a file and try the endpoint from the browser, no curl needed)
"""
from fastapi import FastAPI

from app.database.database import Base, engine
from app.database import base  # noqa: F401 — imports every model so it registers with Base.metadata before create_all() runs
from sqlalchemy import text


def _ensure_invoice_columns_exist():
    """Small, safe runtime migration for SQLite: add new columns if missing.

    This keeps changes minimal for the capstone project instead of
    introducing Alembic. It only affects the `invoices` table and is
    idempotent.
    """
    required = {
        "billing_period_start": "TEXT",
        "billing_period_end": "TEXT",
        "confidence_score": "REAL",
        "matter_name": "TEXT",
    }
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info('invoices')"))
            existing = {row[1] for row in res}
            for col, typ in required.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE invoices ADD COLUMN {col} {typ}"))
                    print(f"Added column '{col}' to invoices table")
    except Exception:
        # If the table doesn't exist yet or the DB is inaccessible, skip
        # — creation will be handled by Base.metadata.create_all above or
        # surfaced elsewhere.
        pass


def _ensure_invoice_schema_matches_current_model():
    """Detect and fix a stale invoices table schema created by an older model."""
    try:
        from app.models.invoice import Invoice
        from app.models.invoice_item import LineItem

        with engine.connect() as conn:
            table_exists = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='invoices'"))
            if table_exists.fetchone() is None:
                return

            columns = {row[1].lower(): row[2].upper() for row in conn.execute(text("PRAGMA table_info('invoices')"))}
            if columns.get("invoice_id") != "INTEGER" or columns.get("matter_id") not in {"VARCHAR", "TEXT"}:
                print("[schema] stale invoices schema detected; recreating invoices and line_items tables")
                Base.metadata.drop_all(bind=engine, tables=[LineItem.__table__, Invoice.__table__])
                Base.metadata.create_all(bind=engine, tables=[Invoice.__table__, LineItem.__table__])
    except Exception as e:
        print(f"[schema] invoice schema verification failed ({e})")

from app.routers import invoices

app = FastAPI(
    title="Legal Invoice Platform Agent API",
    description="AI-powered legal invoice tracking & spend management — capstone project.",
    version="0.1.0",
)

# Dev-time convenience: ensures tables exist on startup. A real deployment
# would use Alembic migrations instead of create_all(), but that's not in
# scope for the capstone timeline.
Base.metadata.create_all(bind=engine)

# Ensure any small schema additions expected by the current model are
# present in existing SQLite DB files (idempotent).
_ensure_invoice_columns_exist()
_ensure_invoice_schema_matches_current_model()


@app.on_event("startup")
def _startup_log_db_url():
    print(f"[startup] resolved database url: {engine.url}")

app.include_router(invoices.router)


@app.get("/health")
def health():
    """Basic liveness check — hit this first to confirm the server is up
    before trying anything else."""
    return {"status": "ok"}