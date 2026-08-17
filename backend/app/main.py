from contextlib import asynccontextmanager

from fastapi import FastAPI
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
    delete_db()


app = FastAPI(
    title="Legal Invoice Platform API",
    description="Synchronous SQLAlchemy backend for legal invoice processing, validation and review.",
    version="2.0.0",
    lifespan=lifespan,
)

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
