from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Invoice
from app.services.invoice import validate_and_route_invoice, post_approved_invoice_to_budget


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

    return (
        {
            "invoice_no": invoice_no.group(1) if invoice_no else "UNKNOWN",
            "invoice_date": invoice_date.group(1) if invoice_date else None,
            "total_amount": float(total.group(1).replace(",", "")) if total else 0.0,
        },
        0.60,
    )


def extract_invoice_fields(raw_text: str) -> tuple[dict, float]:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return _mock_extract(raw_text)

    from groq import Groq

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract invoice_no, invoice_date (YYYY-MM-DD), total_amount "
                    "and confidence (0-1) as strict JSON from this invoice text:\n\n"
                    + raw_text
                ),
            }
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    confidence = float(data.pop("confidence", 0.9))
    return data, confidence


def process_invoice(
    db: Session,
    *,
    file_path: str,
    matter_id: int,
    firm_id: int,
) -> Invoice:
    raw_text = extract_text(file_path)
    fields, confidence = extract_invoice_fields(raw_text)

    invoice_date = fields.get("invoice_date")
    parsed_date = date.fromisoformat(invoice_date) if invoice_date else None

    invoice = Invoice(
        matter_id=matter_id,
        firm_id=firm_id,
        invoice_no=fields.get("invoice_no", "UNKNOWN"),
        invoice_date=parsed_date,
        total_amount=float(fields.get("total_amount", 0)),
        status="submitted",
        confidence_score=confidence,
    )
    db.add(invoice)
    db.flush()

    validate_and_route_invoice(db, invoice, confidence_score=confidence)
    return invoice
