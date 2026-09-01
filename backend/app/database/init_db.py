from sqlalchemy import inspect, text

from app.auth.password import hash_password
from app.database.database import Base, SessionLocal, engine
from app.models.user import User
from app.models.firm import Firm
from app.models.matter import Matter
from app.models.budget import Budget
from app.services.budget_management import normalize


def _sqlite_additive_migration() -> None:
    """Add columns introduced by budget reconciliation without deleting data.

    The project currently uses SQLite and no Alembic configuration. `create_all`
    creates missing tables but does not alter existing ones, so this additive
    migration keeps a developer's existing demo database usable after pulling
    the updated code.
    """
    if engine.dialect.name != "sqlite":
        return

    required = {
        "firms": {
            "address": "TEXT",
            "normalized_name": "VARCHAR(255)",
            "normalized_address": "TEXT",
        },
        "matters": {"matter_no": "VARCHAR(50)"},
        "line_items": {
            "line_type": "VARCHAR(20) NOT NULL DEFAULT 'fee'",
            "role": "VARCHAR(255)",
            "description": "TEXT",
        },
        "invoices": {
            "billing_period_start": "DATE",
            "billing_period_end": "DATE",
            "matter_name": "VARCHAR(255)",
            "budget_id_at_intake": "INTEGER",
            "budget_amount_at_intake": "NUMERIC(14,2)",
            "budget_used_before_invoice": "NUMERIC(14,2)",
            "budget_projected_after_invoice": "NUMERIC(14,2)",
            "budget_remaining_after_invoice": "NUMERIC(14,2)",
            "budget_projected_pct": "FLOAT",
            "budget_status_at_intake": "VARCHAR(50)",
            "budget_attention_required": "BOOLEAN DEFAULT 0",
        },
        "alerts": {
            "invoice_id": "INTEGER",
            "is_active": "BOOLEAN DEFAULT 1",
            "resolved_at": "DATETIME",
        },
        "audit_logs": {
            "request_id": "VARCHAR(100)",
            "firm_id": "INTEGER",
            "matter_id": "INTEGER",
            "budget_id": "INTEGER",
            "previous_value": "VARCHAR(255)",
            "adjustment_amount": "VARCHAR(255)",
            "new_value": "VARCHAR(255)",
            "reason": "TEXT",
            "confirmed": "BOOLEAN",
        },
    }

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in required.items():
            if table not in inspector.get_table_names():
                continue
            existing = {col["name"] for col in inspect(engine).get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))

        # Legacy line-item backfill:
        # Before line_type existed, expense rows were stored as rows with no
        # timekeeper, hours or rate. Adding line_type with DEFAULT 'fee' kept
        # those rows intact but incorrectly labelled them as fees. Reclassify
        # only that unmistakable legacy shape; real fee rows with any billing
        # identity remain fees. This is idempotent and safe to run on startup.
        if "line_items" in inspector.get_table_names():
            conn.execute(text("""
                UPDATE line_items
                SET line_type = 'expense'
                WHERE
                    (line_type IS NULL OR LOWER(TRIM(line_type)) != 'expense')
                    AND (timekeeper IS NULL OR TRIM(timekeeper) = '')
                    AND hours IS NULL
                    AND rate IS NULL
            """))
            conn.execute(text("""
                UPDATE line_items
                SET line_type = 'fee'
                WHERE line_type IS NULL OR TRIM(line_type) = ''
            """))
            conn.execute(text("""
                UPDATE line_items
                SET description = 'Legacy expense'
                WHERE line_type = 'expense'
                  AND (description IS NULL OR TRIM(description) = '')
            """))


def _backfill_normalized_firms(db) -> None:
    for firm in db.query(Firm).all():
        changed = False
        if not firm.normalized_name:
            firm.normalized_name = normalize(firm.name)
            changed = True
        if firm.normalized_address is None:
            firm.normalized_address = normalize(firm.address)
            changed = True
        if changed:
            db.flush()


def init_db():
    Base.metadata.create_all(bind=engine)
    _sqlite_additive_migration()

    db = SessionLocal()
    try:
        _backfill_normalized_firms(db)

        system_user = db.query(User).filter(User.user_id == -1).first()
        if system_user is None:
            db.add(
                User(
                    user_id=-1,
                    name="System",
                    email="system@test.com",
                    password_hash=hash_password(""),
                    role="admin",
                    is_active=False,
                )
            )
            db.flush()

        users_to_seed = [
            {"name": "Admin", "email": "admin@test.com", "password": "admin123", "role": "admin"},
            {"name": "Editor", "email": "editor@test.com", "password": "editor123", "role": "editor"},
            {"name": "Viewer", "email": "viewer@test.com", "password": "viewer123", "role": "viewer"},
        ]
        for item in users_to_seed:
            if db.query(User).filter(User.email == item["email"]).first() is None:
                db.add(
                    User(
                        name=item["name"],
                        email=item["email"],
                        password_hash=hash_password(item["password"]),
                        role=item["role"],
                    )
                )

        firm = db.query(Firm).filter(Firm.firm_id == 1).first()
        if firm is None:
            firm = Firm(
                firm_id=1,
                name="Sample Outside Counsel LLP",
                address="123 Legal Ave, Suite 400",
                normalized_name=normalize("Sample Outside Counsel LLP"),
                normalized_address=normalize("123 Legal Ave, Suite 400"),
                contact_email="contact@samplefirm.com",
                status="active",
            )
            db.add(firm)
            db.flush()

        matter = db.query(Matter).filter(Matter.matter_id == 1).first()
        if matter is None:
            db.add(
                Matter(
                    matter_id=1,
                    firm_id=1,
                    matter_no="M-1042",
                    name="Sample Litigation Matter",
                    owner="Trinkesh",
                    status="open",
                )
            )
            db.flush()

        if db.query(Budget).filter(Budget.matter_id == 1).first() is None:
            db.add(Budget(matter_id=1, allocated_amt=100000.0, threshold_pct=80))

        db.commit()
    finally:
        db.close()


def delete_db():
    Base.metadata.drop_all(bind=engine)