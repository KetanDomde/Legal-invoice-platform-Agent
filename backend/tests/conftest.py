"""
Shared pytest fixtures.

Two setup problems solved here, both BEFORE any `app.*` module gets
imported (import order matters — Settings() and the DB engine are both
configured at import time):

1. Settings() requires DATABASE_URL/JWT_SECRET/etc. to exist somewhere
   (env var or .env) or it raises on import. Rather than requiring every
   contributor to hand-craft a .env before `pytest` even works, this sets
   safe process-env defaults via os.environ.setdefault() — real env vars
   / a real .env still take priority if already present (confirmed
   empirically: explicit env vars override .env file values in this
   pydantic-settings config).

2. Tests use their OWN database file (test_pytest.db), never the
   developer's real test.db from manual CLI runs — so running the test
   suite can never silently wipe someone's manual testing data.
"""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_pytest.db")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-real-use")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
# Deliberately the placeholder value, NOT unset — extract_with_groq_call
# checks for exactly "your_groq_api_key_here" (or empty) to decide
# whether to use the mock path. Tests should be deterministic and not
# depend on whether the developer happens to have a real key exported.
# A real key in a real .env still wins (see precedence note above) if a
# developer explicitly wants to test the live-Groq path.
os.environ.setdefault("GROQ_API_KEY", "your_groq_api_key_here")

import pytest  # noqa: E402 — must come after the env setup above


@pytest.fixture(scope="session", autouse=True)
def _fresh_test_database():
    """Creates all tables once per test session in the isolated pytest DB."""
    from app.database.database import Base, engine
    from app.database import base  # noqa: F401 — importing this registers every model with Base.metadata

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    """A single DB session for a test; closed automatically afterward."""
    from app.database.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_native_pdf():
    path = BACKEND_DIR / "test_invoices" / "sample_invoice_native.pdf"
    if not path.exists():
        pytest.skip(f"{path} not found — copy the sample PDFs into test_invoices/ first")
    return str(path)


@pytest.fixture
def sample_scanned_pdf():
    path = BACKEND_DIR / "test_invoices" / "sample_invoice_scanned.pdf"
    if not path.exists():
        pytest.skip(f"{path} not found — copy the sample PDFs into test_invoices/ first")
    return str(path)