"""
FastAPI layer — Ketan's Day 4 task: wrap the LangGraph workflow (Legal
Invoice Platform Agent) behind HTTP endpoints, and integration-test across
all four modules (LangGraph orchestration, data layer, extraction, auth).

Wired against the REAL app/auth/* (Trinkesh) using SQLAlchemy — not the
raw-sqlite version from the first pass. See app/database/session.py and
app/models/ for what had to be added to make app/auth/auth.py's existing
imports (app.models.user.User, app.core.config.settings) actually resolve.

Run it:
    uvicorn app.main:app --reload --port 8000
Then see the auto-generated docs at http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI

from app.api import auth, invoices, reports
from app.database.session import init_db

app = FastAPI(title="Legal Invoice Platform Agent", version="0.2.0")

app.include_router(auth.router)
app.include_router(invoices.router)
app.include_router(reports.router)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "app": "Legal Invoice Platform Agent"}
