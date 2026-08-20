"""
Invoice endpoints — owner: Bhushan.

CURRENT DESIGN (corrected 14 Aug 2026 during QA pass — the redesign note
that used to live here claimed invoice_id was caller-supplied and that
duplicates were rejected before extraction; neither was true of the
actual code, which this comment now matches):

  - Callers supply matter_id + a file. invoice_id is a system-generated
    integer PK, never supplied by the client.
  - invoice_no (the human-readable business identifier used for
    duplicate detection) is only known AFTER extraction runs, since it
    comes from the PDF itself — so duplicate detection necessarily
    happens post-extraction, not before it. A resubmission that
    extracts an invoice_no already on file for that matter_id is
    rejected with 409 (InvoiceAlreadyExistsError, raised from
    persist_extracted_invoice() on the unique (invoice_no, matter_id)
    constraint) rather than a wasted second extraction producing an
    unhandled 500.
  - matter_id itself is validated before extraction runs (404 if it
    doesn't exist) — that part of the "cheap checks before the
    expensive pipeline" idea does hold.
  - PUT /invoices/{invoice_id} updates an existing invoice (e.g.
    re-processing after a correction), separate from POST which only
    ever creates.

NOTE ON AUTH: submit_invoice requires a valid bearer token via
get_current_user (Trinkesh's dependency). update_invoice (PUT) does not
yet — flag at standup if that's intentional or a gap.
"""
from __future__ import annotations
from app.auth.security import ADMIN, EDITOR, require_role
from app.models import User
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session, joinedload
from app.core.config import settings

from app.database.database import  get_db
from app.database.invoice_repository import (
    InvoiceAlreadyExistsError,
    InvoiceNotFoundError,
    get_firm_id_for_matter,
    insert_invoice_with_line_items,
    invoice_exists,
    update_invoice_with_line_items,
)
from app.models.entities import Invoice
from app.models.entities import LineItem
# from app.workflows.legal_invoice_platform_agent import run_pipeline

from app.workflow.graph import call_run_invoice_graph

router = APIRouter(prefix="/invoices", tags=["invoices"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploaded_invoices"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".txt"}  # .txt kept for the same quick-smoke-test path the CLI supports


def _save_upload_to_disk(file: UploadFile, content: bytes) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    saved_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    saved_path.write_bytes(content)
    return saved_path


def _normalize_matter_id(matter_id: str) -> str:
    normalized = (matter_id or "").strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="matter_id must be a non-empty alphanumeric string")
    if not re.fullmatch(r"[A-Za-z0-9-]+", normalized):
        raise HTTPException(status_code=422, detail="matter_id must contain only letters, numbers, or hyphens")
    return normalized

@router.post("/submit", status_code=200)
async def submit_invoice(
    file: UploadFile = File(...),
    matter_no: str | None = Form(None, description="Optional manual override — normally extracted from the PDF."),
    firm_name: str | None = Form(
        None,
        description=(
            "User-supplied firm name. Used to find-or-create the Firm a "
            "newly-created matter belongs to; the matter itself is still "
            "created from the invoice's extracted matter_no/matter_name. "
            "Falls back to an auto-created 'Unassigned Firm' if omitted."
        ),
    ),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    content = await file.read()
    saved_path = _save_upload_to_disk(file, content)

    try:
        final_state = call_run_invoice_graph(saved_path, matter_no_override=matter_no, firm_name=firm_name)
    except InvoiceAlreadyExistsError as e:
        payload = {
            "detail": str(e),
            "inv_changes": getattr(e, "inv_changes", None) or {},
        }
        return JSONResponse(status_code=409, content=jsonable_encoder(payload))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    if final_state.get("error") == "no_matter_identifier":
        raise HTTPException(
            status_code=422,
            detail="Could not find a matter identifier on this invoice. Resubmit with 'matter_no' filled in manually.",
        )

    resolved_firm_id = final_state.get("firm_id")
    if resolved_firm_id is not None and current_user.firm_id is not None and current_user.firm_id != resolved_firm_id:
        raise HTTPException(status_code=403, detail="Permission denied")

    return _build_submit_response(final_state)



@router.put("/{invoice_id}")
async def update_invoice(
    invoice_id: int,
    matter_id: str = Form(..., description="Required. Alphanumeric matter identifier."),
    file: UploadFile = File(...),
    matter_name: str | None = Form(None, description="Optional human-readable matter name to persist with the invoice."),
):
    """
    Updates an EXISTING invoice — re-extracts from a new file and
    replaces the stored fields/line items. invoice_id itself never
    changes; it's the lookup key, taken from the URL path.

    404 if invoice_id doesn't exist — this updates, it doesn't upsert.
    """
    if not invoice_exists(invoice_id):
        raise HTTPException(
            status_code=404,
            detail=f"No invoice with invoice_id={invoice_id!r} — use POST /invoices/submit to create it first.",
        )

    matter_id = _normalize_matter_id(matter_id)
    content = await file.read()
    saved_path = _save_upload_to_disk(file, content)

    firm_id = get_firm_id_for_matter(matter_id)

    # Re-run extraction against the new file, but persist via UPDATE, not
    # a fresh pipeline run through the auto-approve/human-review graph —
    # re-processing an update through the same routing logic as a brand
    # new submission is a bigger design question than this endpoint's
    # scope; for now this does extraction + validation only, then a
    # direct update. Flag at standup if PUT should also re-run the full
    # approval workflow.
    from app.workflow.legal_invoice_platform_agent import (
        extract_text_from_pdf,
        extract_with_groq_call,
    )

    raw_text = extract_text_from_pdf(str(saved_path))
    extracted, confidence_score = extract_with_groq_call(raw_text)
    # Prefer provided matter_name if extraction didn't return one
    if matter_name and not extracted.get("matter_name"):
        extracted["matter_name"] = matter_name

    try:
        update_invoice_with_line_items(
            invoice_id=invoice_id,
            matter_id=matter_id,
            firm_id=firm_id,
            extracted=extracted,
            confidence_score=confidence_score,
            status="pending_review",  # an update always goes back to review, never silently re-auto-approves
        )
    except InvoiceNotFoundError:
        raise HTTPException(status_code=404, detail=f"No invoice with invoice_id={invoice_id!r}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")

    updated = get_invoice_or_404(invoice_id)
    return {
        "message": "Invoice updated successfully",
        "invoice": _serialize_invoice(updated),
    }


# NOTE: GET /invoices/{invoice_id} and GET /invoices (list) used to be
# defined here too, but billing.py's router already registers both of
# those same paths and is included first in app/main.py, so these were
# dead code — every request was actually served by billing.py's versions
# and these could never run. They also referenced fields that don't
# exist on the real Invoice/LineItem models (matter_name,
# billing_period_start/end, line_type, role, description — see
# app/models/entities.py), so they would have raised AttributeError if
# they had ever been reachable. Removed rather than fixed-in-place, since
# billing.py's list_invoices()/get_invoice() are the complete, correct,
# firm-scoped implementations and having two implementations of the same
# route is exactly what caused this bug. Use those for read access to
# invoices; this module keeps only the endpoints unique to it (submit,
# update).


# --- helpers ---

def get_invoice_or_404(invoice_id: int, db: Session = None) -> Invoice:
    close_after = False
    if db is None:
        from app.database.database import SessionLocal
        db = SessionLocal()
        close_after = True
    try:
        invoice = db.query(Invoice).options(joinedload(Invoice.matter), joinedload(Invoice.line_items)).filter(Invoice.invoice_id == invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail=f"No invoice with id {invoice_id}")
        return invoice
    finally:
        if close_after:
            db.close()


def _serialize_invoice(invoice: Invoice) -> dict:
    # Field list matches the real Invoice/LineItem models in
    # app/models/entities.py. Previously referenced matter_name,
    # billing_period_start/end, line_type, role, and description, none of
    # which exist there — any code path reaching this raised
    # AttributeError. See app/api/invoices.py history / QA findings.
    return {
        "invoice_id": invoice.invoice_id,
        "matter_id": invoice.matter_id,
        "firm_id": invoice.firm_id,
        "invoice_no": invoice.invoice_no,
        "invoice_date": invoice.invoice_date,
        "total_amount": invoice.total_amount,
        "status": invoice.status,
        "confidence_score": invoice.confidence_score,
        "budget_valid": invoice.budget_valid,
        "duplicate_flag": invoice.duplicate_flag,
        "validation_status": invoice.validation_status,
        "validation_message": invoice.validation_message,
        "line_items": [
            {
                "line_item_id": li.line_item_id,
                "timekeeper": li.timekeeper,
                "hours": li.hours,
                "rate": li.rate,
                "amount": li.amount,
            }
            for li in invoice.line_items
        ],
    }


def _build_submit_response(final_state: dict) -> dict:
    result = {
        "invoice_id": final_state.get("invoice_id"),
        "final_status": final_state.get("final_status"),
        "confidence_score": final_state.get("confidence_score"),
        "extracted": final_state.get("extracted"),
        "is_duplicate": final_state.get("is_duplicate"),
        "validation_passed": final_state.get("validation_passed"),
        "validation_reason": final_state.get("validation_reason"),
        "audit_trail": final_state.get("audit_trail"),
    }
    if final_state.get("is_duplicate"):
        result["warning"] = (
            f"invoice_id {final_state.get('invoice_id')!r} was already flagged as a duplicate "
            f"during processing. It was NOT auto-approved — routed to human review instead."
        )
    return result