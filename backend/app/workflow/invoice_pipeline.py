from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()
import json
import os
import re
from datetime import date
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.invoice_repository import InvoiceAlreadyExistsError
from app.models import Invoice, LineItem, Matter, Firm
from app.schemas.invoice_extraction import ExtractedInvoice
from app.services.invoice import validate_invoice, get_duplicate_invoice, diff_invoices, find_duplicate_invoice
from app.core.config import settings


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(file_path)

    try:
        import fitz

        doc = fitz.open(file_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        if text.strip():
            return text
    except Exception:
        pass

    return path.read_text(errors="ignore")


def _mock_extract(raw_text: str) -> tuple[dict, float]:
    invoice_no = re.search(r"Invoice No:\s*(\S+)", raw_text, re.I)
    invoice_date = re.search(r"Date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", raw_text, re.I)
    total = re.search(r"Total:\s*\$?([\d,]+(?:\.\d{2})?)", raw_text, re.I)

    line_items = []
    pattern = re.compile(
        r"[-*]\s*(?P<timekeeper>[^,\n]+),\s*[^,\n]+,\s*"
        r"(?P<hours>[\d.]+)\s*hrs\s*@\s*\$?(?P<rate>[\d.]+).*?"
        r"=\s*\$?(?P<amount>[\d,]+(?:\.\d{2})?)",
        re.I,
    )
    for match in pattern.finditer(raw_text):
        line_items.append(
            {
                "timekeeper": match.group("timekeeper").strip(),
                "hours": float(match.group("hours")),
                "rate": float(match.group("rate")),
                "amount": float(match.group("amount").replace(",", "")),
            }
        )

    return (
        {
            "invoice_no": invoice_no.group(1) if invoice_no else "UNKNOWN",
            "invoice_date": invoice_date.group(1) if invoice_date else None,
            "total_amount": float(total.group(1).replace(",", "")) if total else 0.0,
            "line_items": line_items,
        },
        0.60,
    )


def extract_invoice_fields(raw_text: str) -> tuple[dict, float]:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return _mock_extract(raw_text)

    from groq import Groq

    client = Groq(api_key=api_key)
    schema = ExtractedInvoice.model_json_schema()
    
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    f"""
                You are an expert legal invoice extraction system.

                Extract all information available in the invoice.

                Return ONLY JSON matching this schema:

                {json.dumps(schema, indent=2)}

                Important rules:

                1. Do not invent values.
                2. Use null when a value is not present.
                3. Extract every invoice line item.
                4. Preserve monetary values accurately.
                5. Extract firm and matter names when present.
                6. Do not generate database IDs such as invoice_id, firm_id,
                matter_id, or line_item_id.
                7. Do not omit line items.
                8. Convert all date to 'yyyy-mm-dd' format.
                9. Classify each charge line with line_type: use "fee" for
                   timekeeper/professional-service charges and "expense" for
                   disbursements such as filing fees, courier, travel, copies,
                   taxes, or other non-timekeeper charges.
                10. For expense rows, put the expense label in description and
                    leave timekeeper, hours, and rate null when they do not apply.
                """
                ),
            },
            {"role": "user", "content": raw_text},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    confidence = float(data.pop("confidence", 0.9))
    extracted = ExtractedInvoice.model_validate(data)
    return extracted.model_dump(mode="json"), confidence


def validate_relationships(db: Session, matter_id: int, firm_id: int) -> tuple[Matter, Firm]:
    
    matter = db.get(Matter, matter_id)
    if matter is None:
        raise ValueError(f"Matter not found: {matter_id}")
    firm = db.get(Firm, firm_id)
    if firm is None:
        raise ValueError(f"Firm not found: {firm_id}")
    if matter.firm_id != firm_id:
        raise ValueError("Matter does not belong to the supplied firm.")
    return matter, firm



def _classify_line_type(item):
    explicit_type = str(getattr(item, "line_type", None) or "").strip().lower()
    has_timekeeper = bool(str(getattr(item, "timekeeper", None) or "").strip())
    has_hours = getattr(item, "hours", None) is not None
    has_rate = getattr(item, "rate", None) is not None
    if explicit_type == "expense":
        return "expense"
    if not has_timekeeper and not has_hours and not has_rate:
        return "expense"
    return "fee"

def persist_extracted_invoice(
    state
) -> Invoice:
    db = state["db"]
    matter_id = state["matter_id"]
    firm_id = state["firm_id"]
    fields = state["extracted"]
    duplicate_inv_id = state["validation"]["duplicate_invoice_id"]
    confidence = state["confidence_score"]

    validate_relationships(db, matter_id, firm_id)
    parsed = ExtractedInvoice.model_validate(fields)

    duplicate = db.get(Invoice, duplicate_inv_id)
    orig_inv = duplicate
    inv_changes = diff_invoices(orig_inv, parsed) if orig_inv is not None else {}
    state["inv_changes"] = inv_changes

    if duplicate_inv_id and inv_changes:    
        duplicate = db.get(Invoice, duplicate_inv_id)
        # 2. Update scalar attributes directly
        duplicate.matter_id = matter_id
        duplicate.firm_id = firm_id
        duplicate.invoice_no = parsed.invoice_no
        duplicate.invoice_date = parsed.invoice_date
        duplicate.total_amount = parsed.total_amount
        duplicate.status = "submitted"
        duplicate.confidence_score = confidence

        # 3. Replace the relationship list
        duplicate.line_items = [
            LineItem(
                line_type=_classify_line_type(item),
                timekeeper=item.timekeeper,
                role=getattr(item, "role", None),
                description=getattr(item, "description", None),
                hours=item.hours,
                rate=item.rate,
                amount=item.amount,
            )
            for item in parsed.line_items
        ]
        invoice = duplicate
    elif duplicate_inv_id:
        db.rollback()
        # duplicate
        raise InvoiceAlreadyExistsError(
            invoice_no=parsed.invoice_no,
            matter_id=str(matter_id)
        )
    else:
        invoice = Invoice(
            matter_id=matter_id,
            firm_id=firm_id,
            invoice_no=parsed.invoice_no,
            invoice_date=parsed.invoice_date,
            total_amount=parsed.total_amount,
            status="submitted",
            confidence_score=confidence,
        )
        invoice.line_items = [
            LineItem(
                line_type=_classify_line_type(item),
                timekeeper=item.timekeeper,
                role=getattr(item, "role", None),
                description=getattr(item, "description", None),
                hours=item.hours,
                rate=item.rate,
                amount=item.amount,
            )
            for item in parsed.line_items
        ]
        db.add(invoice)
    try:
        db.flush()
    except IntegrityError as e:
        # Same invoice_no already exists for this matter_id (the unique
        # constraint on the invoices table). This used to propagate as a
        # raw, unhandled IntegrityError all the way up to a bare 500 —
        # now it's a typed, catchable error the API layer turns into a
        # clean 409 (see app/api/invoices.py submit_invoice).
        # Must rollback BEFORE querying again — the session is left in an
        # aborted state after a failed flush, so any query on it (e.g.
        # find_duplicate_invoice below) would raise PendingRollbackError.
        db.rollback()
        org_inv = find_duplicate_invoice(
            db,
            matter_id=matter_id,
            invoice_no=parsed.invoice_no,
            total_amount=float(parsed.total_amount or 0),
        )
        org_inv = get_duplicate_invoice(org_inv)
        inv_changes = diff_invoices(org_inv, parsed) if org_inv is not None else {}
        raise InvoiceAlreadyExistsError(
            invoice_no=parsed.invoice_no,
            matter_id=str(matter_id),
            inv_changes=inv_changes,
        ) from e

    return invoice


def process_invoice(
    db: Session,
    *,
    file_path: str,
    matter_id: int,
    firm_id: int,
) -> Invoice:
    """Backward-compatible synchronous entry point for the LangGraph pipeline."""
    from app.workflow.graph import run_invoice_graph

    result = run_invoice_graph(
        db,
        file_path=file_path,
        matter_id=matter_id,
        firm_id=firm_id,
    )
    invoice_id = result.get("invoice_id")
    if invoice_id is None:
        raise ValueError(result.get("error", "Invoice processing failed."))
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} was not persisted.")
    return invoice