"""
Invoice persistence — owner: Bhushan (ERD: INVOICE, LINE_ITEM entities).

REDESIGNED: invoice_id is now a system-generated integer primary key.
This file's functions reflect that:
  - insert_invoice_with_line_items() does not take invoice_id; the DB
    generates it and returns the integer value.
  - update_invoice_with_line_items() still receives invoice_id as the
    lookup key for updates.
  - invoice_exists()/get_invoice() take the numeric invoice_id.
"""
from __future__ import annotations

from datetime import date, datetime
from sqlalchemy.exc import IntegrityError

from app.database.database import SessionLocal
from app.models.invoice import Invoice
from app.models import LineItem
from app.models.matter import Matter

from app.models.firm import Firm  # add to your existing imports at the top

UNASSIGNED_FIRM_NAME = "Unassigned Firm (Auto)"


def get_or_create_unassigned_firm(db) -> "Firm":
    """Fallback firm for matters auto-created from invoice extraction
    when the PDF has no extractable firm identity. Reassign the real
    firm later via PATCH /matters/{id}."""
    firm = db.query(Firm).filter(Firm.name == UNASSIGNED_FIRM_NAME).first()
    if firm is None:
        firm = Firm(name=UNASSIGNED_FIRM_NAME, status="active")
        db.add(firm)
        db.flush()
    return firm


def get_or_create_matter(db, matter_no: str, matter_name: str | None = None):
    """
    Resolves a Matter by its extracted matter_no. Auto-creates one under
    the fallback Unassigned Firm if it doesn't exist yet, so invoice
    upload never blocks on a missing matter.
    """
    matter_no = (matter_no or "").strip()
    if not matter_no:
        return None

    matter = db.query(Matter).filter(Matter.matter_no == matter_no).first()
    if matter is not None:
        return matter

    firm = get_or_create_unassigned_firm(db)
    matter = Matter(
        matter_no=matter_no,
        firm_id=firm.firm_id,
        name=matter_name or f"Auto-created from invoice ({matter_no})",
        owner="Unassigned",
        status="open",
    )
    db.add(matter)
    db.flush()
    return matter


def _coerce_date(value):
    """
    extract_with_groq_call() / extract_invoice_fields_mock() (in
    app/workflow/legal_invoice_platform_agent.py) return invoice_date as
    a plain "YYYY-MM-DD" string, not a date object. Passing that string
    straight into Invoice(invoice_date=...) used to raise
    `sqlalchemy.exc.StatementError: SQLite Date type only accepts Python
    date objects as input` on every insert/update that had a date at
    all. Already-a-date and None both pass through unchanged; an
    unparseable string returns None rather than crashing (same
    "don't invent data, flag for review instead" philosophy as
    extract_text_from_pdf's empty-string return).
    """
    if not value or isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


class InvoiceAlreadyExistsError(Exception):
    """Raised by insert_invoice_with_line_items() if an invoice with the
    same invoice_no and matter_id already exists.
    Distinct from a generic DB error so the API layer can turn this into
    a clean 409 instead of a 500."""
    def __init__(self, invoice_no: str, matter_id: str):
        self.invoice_no = invoice_no
        self.matter_id = matter_id
        super().__init__(f"Invoice with invoice_no={invoice_no!r} already exists for matter_id={matter_id!r}")


class InvoiceNotFoundError(Exception):
    """Raised by update_invoice_with_line_items() if invoice_id doesn't
    exist yet — PUT here means "update an existing invoice," not upsert."""
    def __init__(self, invoice_id: int):
        self.invoice_id = invoice_id
        super().__init__(f"No invoice with invoice_id={invoice_id!r}")


def invoice_exists(invoice_id: int) -> bool:
    """Lookup by numeric system-generated invoice_id."""
    db = None
    try:
        db = SessionLocal()
        return db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first() is not None
    except Exception as e:
        print(f"[invoice_exists] lookup failed ({e}) — defaulting to False")
        return False
    finally:
        if db is not None:
            db.close()


def invoice_exists_by_business_key(invoice_no: str, matter_id: str) -> bool:
    invoice_no = invoice_no.strip() if isinstance(invoice_no, str) else invoice_no
    matter_id = matter_id.strip() if isinstance(matter_id, str) else matter_id
    db = None
    try:
        db = SessionLocal()
        return db.query(Invoice).filter(
            Invoice.invoice_no == invoice_no,
            Invoice.matter_id == matter_id,
        ).first() is not None
    except Exception as e:
        print(f"[invoice_exists_by_business_key] lookup failed ({e}) — defaulting to False")
        return False
    finally:
        if db is not None:
            db.close()


def get_invoice(invoice_id: int):
    """Fetch a single Invoice row (with line_items loaded) by its
    numeric id, or None."""
    db = SessionLocal()
    try:
        return db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
    finally:
        db.close()


def get_firm_id_for_matter(matter_id: str):
    """
    Best-effort lookup: the new upload flow no longer requires the caller
    to pass firm_id directly (only invoice_id + matter_id + file) — a
    matter already belongs to a firm, so derive it instead of asking for
    redundant, potentially-inconsistent data.

    Returns None (not an error) if the matter doesn't exist — Matter is
    currently a Bhushan-added placeholder (see app/models/matter.py) with
    no real seeded data in most dev setups, so this has to degrade
    gracefully rather than block every submission until Rajat's real
    Matter/seed data lands.
    """
    db = SessionLocal()
    try:
        matter = db.query(Matter).filter(Matter.matter_id == matter_id).first()
        return matter.firm_id if matter else None
    except Exception as e:
        print(f"[get_firm_id_for_matter] lookup failed ({e}) — proceeding with firm_id=None")
        return None
    finally:
        db.close()


def _apply_line_items(db, invoice_id: int, line_items_data: list) -> None:
    """Shared by insert and update — adds LineItem rows for an invoice
    that's already been added/flushed to the session.

    FIXED during QA pass (14 Aug 2026): previously passed line_type,
    role, and description to LineItem(...) — none of those are columns
    on the real LineItem model in app/models/entities.py. SQLAlchemy's
    generated __init__ raises TypeError on an unrecognized keyword
    argument, so this crashed on every invoice that had any line items
    at all (i.e. almost every real submission) — this is the deeper
    cause behind PUT /invoices/{invoice_id} still failing even once its
    ModuleNotFoundError (QA findings bug #6) is fixed. Extraction still
    produces line_type/role/description (see extract_with_groq_call in
    app/workflow/legal_invoice_platform_agent.py) — they're just not
    persisted today. Flag at standup if the schema should be extended to
    keep them rather than dropping them here.
    """
    for li in (line_items_data or []):
        db.add(LineItem(
            invoice_id=invoice_id,
            timekeeper=li.get("timekeeper"),
            hours=li.get("hours"),
            rate=li.get("rate"),
            amount=li.get("amount", 0.0),
        ))


def insert_invoice_with_line_items(
    matter_id: str,
    firm_id,
    extracted: dict,
    confidence_score: float,
    status: str,
) -> int:
    """
    Inserts one NEW Invoice row plus its LineItem rows. invoice_id is
    system-generated by the database and returned on success.

    Raises InvoiceAlreadyExistsError if the same invoice_no already
    exists for the given matter_id.
    """
    db = SessionLocal()
    invoice_no = extracted.get("invoice_no") or None
    invoice_no = invoice_no.strip() if isinstance(invoice_no, str) else invoice_no
    matter_id = matter_id.strip() if isinstance(matter_id, str) else matter_id

    if invoice_no and invoice_exists_by_business_key(invoice_no, matter_id):
        db.close()
        raise InvoiceAlreadyExistsError(invoice_no, matter_id)

    try:
        # billing_period_start/end and matter_name removed from this
        # constructor call — same reason as _apply_line_items above:
        # none of them are real columns on Invoice (entities.py), and
        # SQLAlchemy's generated __init__ raises TypeError on an
        # unrecognized keyword rather than ignoring it.
        invoice = Invoice(
            matter_id=matter_id,
            firm_id=firm_id,
            invoice_no=invoice_no,
            invoice_date=_coerce_date(extracted.get("invoice_date")),
            total_amount=extracted.get("total_amount", 0.0),
            status=status,
            confidence_score=confidence_score,
        )
        db.add(invoice)
        db.flush()  # generates invoice_id before line items are added

        _apply_line_items(db, invoice.invoice_id, extracted.get("line_items"))

        db.commit()
        return invoice.invoice_id
    except IntegrityError as ie:
        db.rollback()
        if invoice_no and invoice_exists_by_business_key(invoice_no, matter_id):
            raise InvoiceAlreadyExistsError(invoice_no, matter_id)
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_invoice_with_line_items(
    invoice_id: int,
    matter_id: str,
    firm_id,
    extracted: dict,
    confidence_score: float,
    status: str,
) -> int:
    """
    Updates an EXISTING invoice's fields and replaces its line items —
    backs PUT /invoices/{invoice_id}. invoice_id itself never changes
    (it's the lookup key, not a field being updated).

    Raises InvoiceNotFoundError if invoice_id doesn't exist — PUT here
    means "update", not "upsert"; use POST /invoices/submit to create.
    """
    db = SessionLocal()
    try:
        invoice = db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        if invoice is None:
            raise InvoiceNotFoundError(invoice_id)

        # matter_name/billing_period_start/billing_period_end removed:
        # none of these are real columns on Invoice (entities.py). The
        # old code read `invoice.matter_name` as a fallback default
        # (`extracted.get(...) or invoice.matter_name`) — reading an
        # attribute that was never declared as a mapped column raises
        # AttributeError on a SQLAlchemy declarative instance, so this
        # crashed immediately on every PUT, before line items were even
        # touched.
        invoice.matter_id = matter_id
        invoice.firm_id = firm_id
        invoice.invoice_no = extracted.get("invoice_no") or invoice.invoice_no
        invoice.invoice_date = _coerce_date(extracted.get("invoice_date")) or invoice.invoice_date
        invoice.total_amount = extracted.get("total_amount", invoice.total_amount)
        invoice.status = status
        invoice.confidence_score = confidence_score

        # Replace line items wholesale rather than trying to diff old vs
        # new — simpler and correct for "re-extracted from a new file"
        # semantics, which is what PUT represents here.
        db.query(LineItem).filter(LineItem.invoice_id == invoice_id).delete()
        _apply_line_items(db, invoice_id, extracted.get("line_items"))

        db.commit()
        return invoice_id
    except InvoiceNotFoundError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()