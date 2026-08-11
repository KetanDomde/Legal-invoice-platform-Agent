# Legal Invoice Platform Backend

Merged backend from the two provided branches.

## What was merged

- FastAPI application and authentication/RBAC from the review workflow branch.
- Firms, matters, budgets, invoices, line items, budget ledger and alerts from the billing branch.
- Invoice validation: budget checks, duplicate detection and extraction-confidence routing.
- Human review workflow: approve, reject and request clarification.
- Audit logging.
- Groq invoice extraction workflow with a deterministic fallback.
- All persistence uses **synchronous SQLAlchemy**. SQLModel and async database code were removed.
- Duplicate/empty models and overlapping APIs were consolidated.

## Project structure

```text
backend/
├── README.md
├── requirements.txt
├── Dockerfile
├── pytest.ini
└── app/
    ├── main.py
    ├── api/
    │   ├── auth.py
    │   ├── users.py
    │   ├── billing.py
    │   ├── validation.py
    │   ├── review.py
    │   └── admin.py
    ├── auth/
    │   └── security.py
    ├── core/
    │   └── config.py
    ├── database/
    │   ├── database.py
    │   └── init_db.py
    ├── models/
    │   └── entities.py
    ├── schemas/
    │   ├── auth.py
    │   ├── admin.py
    │   ├── billing.py
    │   ├── review.py
    │   └── validation.py
    ├── services/
    │   └── invoice.py
    └── workflow/
        └── invoice_pipeline.py
```

## Run locally

Python 3.12 is recommended.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Environment

Create a `.env` file:

```env
DATABASE_URL=sqlite:///./legal_invoice.db
SECRET_KEY=change-me-in-development
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
GROQ_API_KEY=
GROQ_MODEL=llama-3.1-8b-instant
```

For PostgreSQL, only `DATABASE_URL` needs to change, for example:

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/legal_invoice
```

and install the PostgreSQL driver separately.

## Important API areas

- `/auth/login` — login and JWT token
- `/users` — current user and basic user CRUD
- `/admin/users` — admin user management
- `/firms`, `/matters`, `/budgets`, `/invoices`, `/line-items` — billing CRUD
- `/budget-ledger`, `/alerts`, `/audit-logs` — billing/audit records
- `/validation` — invoice validation and routing
- `/review` — human-review queue and review actions

## Invoice routing

An invoice is auto-approved only when:

1. extraction confidence is at least `0.85`;
2. the invoice is within the matter's remaining budget; and
3. no duplicate invoice is found for the firm.

Otherwise it is sent to `pending_review`.

## Notes

`Base.metadata.create_all()` is used for development bootstrap. For production, use Alembic migrations rather than relying on automatic table creation.
