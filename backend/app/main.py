from contextlib import asynccontextmanager

from typing import Any
from fastapi import FastAPI, Request
import uuid

from app.logger_config import logger, request_id_ctx, ensure_request_id
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.review import router as review_router
from app.api.users import router as users_router
from app.api.invoices import router as invoice_router
from app.api.validation import router as validation_router
from app.database.init_db import init_db,delete_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    # Keep SQLite data on shutdown. Budget history and audit records must persist.



app = FastAPI(
    title="Legal Invoice Platform API",
    description="Synchronous SQLAlchemy backend for legal invoice processing, validation and review.",
    version="2.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    # Capture Request-ID header from Streamlit (or fallback to new UUID)
    req_id = request.headers.get("X-Request-ID") or request.headers.get("X-Session-ID")
    if not req_id:
        req_id = str(uuid.uuid4())
    # set in contextvar for downstream use
    token = request_id_ctx.set(req_id)
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        logger.info(f"Request completed with status: {response.status_code}")
        return response
    finally:
        request_id_ctx.reset(token)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(billing_router)
app.include_router(validation_router)
app.include_router(review_router)
app.include_router(audit_router)
app.include_router(invoice_router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "Legal Invoice Platform API is running"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
