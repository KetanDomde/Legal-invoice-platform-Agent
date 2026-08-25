from __future__ import annotations
from pathlib import Path
from dotenv import load_dotenv
import re
import os
import json
import time
from typing import Optional, TypedDict
from datetime import datetime, timezone
from typing import TypedDict
import io
from langgraph import graph
import pytesseract
from PIL import Image
from app.database.database import SessionLocal
from app.models.matter import Matter
from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.models import entities

from app.services.invoice import add_audit_log, validate_invoice
from app.core.config import settings

from app.workflow.approval_service import (
    auto_approve_invoice,
)

from app.workflow.invoice_pipeline import (
    extract_invoice_fields,
    persist_extracted_invoice,
    validate_relationships,
)


SCRIPT_DIR = Path(__file__).resolve().parent          # backend/app/workflows
BACKEND_DIR = SCRIPT_DIR.parent.parent                 # backend/
DEFAULT_TEST_INVOICES_DIR = BACKEND_DIR / "test_invoices"
ENV_PATH = BACKEND_DIR / ".env"

# Loads backend/.env explicitly regardless of cwd. Falls back to
# load_dotenv()'s normal upward-search behavior too, in case someone's
# intentionally using a .env somewhere else — explicit path just takes
# priority when it exists.
load_dotenv(dotenv_path=ENV_PATH if ENV_PATH.exists() else None)

APP_NAME = "Legal Invoice Platform Agent"

# Confidence at/above this auto-approves (subject to budget check); below it
# always goes to human review, per PRD's confidence-routing requirement.
AUTO_APPROVE_CONFIDENCE_THRESHOLD = 0.85

# --- Bhushan's config (extraction) -----------------------------------------
# Below this many characters per page, PyMuPDF's native extraction is treated
# as "no usable text layer" and we fall back to OCR (Architecture Doc §7:
# "Scanned / image-only PDF"). 20 chars/page comfortably separates a blank/
# image-only page from even a sparse real invoice page.
MIN_CHARS_PER_PAGE_FOR_NATIVE_TEXT = 20

# OCR render resolution — higher improves Tesseract accuracy at the cost of
# speed; 300dpi is a standard sweet spot for invoice-quality scans.
OCR_RENDER_DPI = 300

GROQ_MAX_RETRIES = 3
GROQ_RETRY_BASE_DELAY_SECONDS = 1.5  # exponential backoff: 1.5s, 3s, 6s

EXTRACTION_SYSTEM_PROMPT = (
    "You are an accurate invoice data extraction engine for a legal spend "
    "management system. You extract structured billing data from legal "
    "invoice text and return ONLY strict JSON — no prose, no markdown "
    "fences. If a field is not present in the text, use null (or an empty "
    "list for line_items) rather than guessing a value."
)


class InvoiceGraphState(TypedDict, total=False):
    db: Session
    file_path: str
    matter_no_override: str | None   # NEW
    firm_name: str | None            # user-supplied fallback
    firm_address: str | None         # user-supplied fallback
    matter_id: int
    firm_id: int
    raw_text: str
    extracted: dict
    confidence_score: float
    invoice_id: int
    validation: dict
    route: str
    final_status: str
    audit_trail: list[str]
    error: str
    inv_changes: dict
    
    
def _ocr_pdf_pages(doc) -> str:
    """
    Rasterize each page of an open PyMuPDF document and run Tesseract OCR
    on it. Used when the PDF has no usable native text layer.
    """
    import pytesseract
    from PIL import Image

    # Explicit path first (reliable on Windows regardless of PATH state),
    # falling back to PATH auto-discovery on other platforms.
    tesseract_cmd = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    page_texts = []
    for page in doc:
        pix = page.get_pixmap(dpi=OCR_RENDER_DPI)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        page_texts.append(pytesseract.image_to_string(img))
    return "\n".join(page_texts)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Bhushan's job (PyMuPDF + Tesseract OCR fallback per Architecture Doc,
    PRD FR-5, Architecture Doc §7 "Scanned / image-only PDF").

    Order of attempts:
      1. Native PyMuPDF text extraction (fast, exact, free) — works for any
         digitally-authored PDF (the normal case).
      2. If the text layer is missing or too sparse (scanned/image-only
         pages), rasterize each page and OCR it with Tesseract.
      3. Non-PDF input (e.g. a .txt sample used for quick smoke tests) is
         still read as plain text, so this stays a drop-in replacement for
         the original stub during early testing.

    Malformed/unreadable input (missing file, corrupt PDF, OCR also finds
    nothing) intentionally returns "" rather than inventing placeholder
    text — per FR-8, that case must be *flagged for human review*, not
    silently papered over with fake-looking data. extract_with_groq_call
    below treats "" as exactly that signal (confidence 0.0 -> router always
    sends it to human_review).
    """
    if not os.path.exists(file_path):
        return ""

    # file_path arrives as a pathlib.Path from the live API
    # (app/api/invoices.py's _save_upload_to_disk returns a Path) — this
    # function was dead code before the QA-pass fix that wired it into
    # ingest_invoice (bug #7), so this .lower() call on a Path object
    # (AttributeError: 'PosixPath' object has no attribute 'lower') was
    # never actually exercised end-to-end until now. str() handles both
    # a Path and a plain string.
    is_pdf = str(file_path).lower().endswith(".pdf")

    if is_pdf:
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            try:
                native_text = "\n".join(page.get_text() for page in doc)
                avg_chars_per_page = len(native_text.strip()) / max(doc.page_count, 1)

                if avg_chars_per_page >= MIN_CHARS_PER_PAGE_FOR_NATIVE_TEXT:
                    return native_text

                # Native layer is empty/too sparse -> scanned/image-only PDF.
                ocr_text = _ocr_pdf_pages(doc)
                return ocr_text if ocr_text.strip() else native_text
            finally:
                doc.close()
        except Exception as e:
            print(f"[extract_text_from_pdf] could not open/parse '{file_path}' as PDF: {e}")
            return ""

    # Non-PDF path: treat as plain text (quick smoke-test .txt samples).
    try:
        with open(file_path, "r", errors="ignore") as f:
            return f.read()
    except Exception as e:
        print(f"[extract_text_from_pdf] could not read '{file_path}': {e}")
        return ""


_MOCK_LINE_ITEM_RE = re.compile(
    r"-\s*(?P<timekeeper>[\w.\s]+?),\s*(?P<role>[\w]+),\s*"
    r"(?P<hours>[\d.]+)\s*hrs\s*@\s*\$?(?P<rate>[\d,.]+)/hr\s*=\s*\$?(?P<amount>[\d,]+\.\d{2})"
)


def _parse_table_line_items(raw_text: str) -> list[dict]:
    """Parse table-style fee lines from the extracted invoice text."""
    line_items = []
    for line in raw_text.splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("Timekeeper") or candidate.startswith("Role"):
            continue

        # Many invoice text extractors collapse columns to multiple spaces.
        cols = re.split(r"\s{2,}", candidate)
        if len(cols) < 5:
            continue

        # Expected fee row shape: Timekeeper, Role, Date, Hours, Rate, Amount
        # Some variations may omit a description column, so try to find the numeric tail.
        tail = cols[-3:]
        if not re.fullmatch(r"[\d.]+", tail[0]) or not re.fullmatch(r"[\d,]+\.\d{2}", tail[1]) or not re.fullmatch(r"[\d,]+\.\d{2}", tail[2]):
            continue

        timekeeper = cols[0].strip()
        role = cols[1].strip() if len(cols) >= 6 else None
        date = cols[2].strip() if len(cols) >= 6 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cols[2].strip()) else None
        hours = float(tail[0])
        rate = float(tail[1].replace(",", ""))
        amount = float(tail[2].replace(",", ""))

        if timekeeper and role and date:
            line_items.append({
                "line_type": "fee",
                "timekeeper": timekeeper,
                "role": role,
                "hours": hours,
                "rate": rate,
                "amount": amount,
            })
    return line_items


def _parse_expense_lines(raw_text: str) -> list[dict]:
    """Parse expense lines from the invoice text after the Expenses header."""
    expenses = []
    expenses_section = re.search(r"Expenses\s*(.*?)\s*(?:Subtotal|Tax|Total|$)", raw_text, re.S | re.IGNORECASE)
    if not expenses_section:
        return expenses

    for line in expenses_section.group(1).splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        m = re.match(r"^(.+?)\s+([\d,]+\.\d{2})$", candidate)
        if not m:
            continue
        label = m.group(1).strip()
        amount = float(m.group(2).replace(",", ""))
        if label and amount > 0:
            expenses.append({
                "line_type": "expense",
                "timekeeper": None,
                "role": None,
                "hours": None,
                "rate": None,
                "amount": amount,
                "description": label,
            })
    return expenses


def extract_invoice_fields_mock(raw_text: str) -> dict:
    """
    Deterministic, no-API-key-needed fallback so Day 1/2 never blocks on
    Groq access. Also used as the final safety net if the real Groq call
    fails after all retries (see extract_with_groq_call).

    Now populates line_items too (was a TODO in the original stub) by
    regex-parsing the text output from the invoice. This supports both
    bullet-style sample text and table-style invoice text like the PDF.
    """
    invoice_no_match = re.search(r"Invoice\s*No[:]?\s*(\S+)", raw_text, re.IGNORECASE)
    date_match = re.search(r"Invoice\s*Date[:]?\s*([\d]{4}-[\d]{2}-[\d]{2})", raw_text, re.IGNORECASE)
    if not date_match:
        date_match = re.search(r"Date[:]?\s*([\d]{4}-[\d]{2}-[\d]{2})", raw_text, re.IGNORECASE)

    billing_period_match = re.search(
        r"Billing\s*Period[:]?\s*([\d]{4}-[\d]{2}-[\d]{2})\s*(?:to|-)\s*([\d]{4}-[\d]{2}-[\d]{2})",
        raw_text,
        re.IGNORECASE,
    )
    # Try extracting a human-readable Matter name (e.g. "MAT-771B - Nova Retail v. Green Market")
    matter_match = re.search(r"Matter[:]?\s*([A-Za-z0-9-]+)\s*-\s*(.+)", raw_text, re.IGNORECASE)
    firm_match = re.search(r"\b([A-Z][a-zA-C-z0-9'&.\- ]+?\b(?:L\.?L\.?P\.?|P\.?C\.?|L\.?L\.?C\.?|P\.?L\.?L\.?C\.?|Inc\.?|Ltd\.?|Law\s+Offices?|Legal\s+Group|Law\s+Group|Attorneys\s+at\s+Law))\b", raw_text, re.IGNORECASE)
    total_match = re.search(r"Total[:]?\s*\$?([\d,]+\.\d{2})", raw_text, re.IGNORECASE)

    line_items = []
    for m in _MOCK_LINE_ITEM_RE.finditer(raw_text):
        hours = float(m.group("hours"))
        rate = float(m.group("rate").replace(",", ""))
        line_items.append({
            "line_type": "fee",
            "timekeeper": m.group("timekeeper").strip(),
            "role": m.group("role").strip(),
            "hours": hours,
            "rate": rate,
            "amount": float(m.group("amount").replace(",", "")),
        })

    if not line_items:
        line_items = _parse_table_line_items(raw_text)

    expense_items = _parse_expense_lines(raw_text)
    line_items.extend(expense_items)

    total_amount = 0.0
    if total_match:
        total_amount = float(total_match.group(1).replace(",", ""))
    elif line_items:
        total_amount = sum(item["amount"] for item in line_items)

    return {
        "invoice_no": invoice_no_match.group(1) if invoice_no_match else "UNKNOWN",
        "invoice_date": date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d"),
        "billing_period_start": billing_period_match.group(1) if billing_period_match else None,
        "billing_period_end": billing_period_match.group(2) if billing_period_match else None,
        "matter_no": matter_match.group(1).strip() if matter_match else None,      # NEW

        "matter_name": matter_match.group(2).strip() if matter_match else None,
        "firm_name": firm_match.group(1).strip() if firm_match else None,
        # Most legal invoices place the address immediately below the firm letterhead.
        "firm_address": (raw_text.splitlines()[1].strip() if len(raw_text.splitlines()) > 1 and raw_text.splitlines()[1].strip() else None),
        "total_amount": total_amount,
        "line_items": line_items,
    }


def _build_extraction_prompt(raw_text: str) -> str:
    """
    FR-6 requires invoice_no, invoice_date, total_amount, AND line items
    (timekeeper, hours, rate, amount) — matches the ERD's LINE_ITEM table.
    The original stub's prompt only asked for the top-level fields; 
    expands it to actually satisfy FR-6.

    billing_period_start/end added per a later requirement — these were
    never extracted or stored before this, despite being explicitly
    required ("Extract billing_period from the PDF and save it").
    """
    return (
        "Extract billing data from the following legal invoice text and "
        "return it as strict JSON with exactly this shape:\n"
        "{\n"
        '  "invoice_no": string,\n'
        '  "invoice_date": string (YYYY-MM-DD),\n'
        '  "billing_period_start": string or null (YYYY-MM-DD — start of the billing period covered by this invoice),\n'
        '  "billing_period_end": string or null (YYYY-MM-DD — end of the billing period covered by this invoice),\n'
        '  "matter_no": string or null (the matter/case identifier printed on the invoice, e.g. "MAT-771B"),\n'
        '  "matter_name": string or null (the matter/case name, e.g. "Nova Retail v. Green Market"),\n'
        '  "firm_name": string or null (the firm/org name, e.g. "ABC Legal Associates"),\n'
        '  "firm_address": string or null (the mailing address shown for the firm),\n'
        
        '  "total_amount": number (no currency symbol, no commas),\n'
        '  "line_items": [\n'
        "    {\n"
        '      "line_type": "fee" or "expense",\n'
        '      "timekeeper": string or null (null for expense lines — e.g. filing fees, courier — that have no associated biller),\n'
        '      "role": string or null,\n'
        '      "hours": number or null,\n'
        '      "rate": number or null,\n'
        '      "amount": number,\n'
        '      "description": string or null (required for expense lines, e.g. "Filing Fee", "Courier")\n'
        "    }\n"
        "  ],\n"
        '  "confidence": number between 0 and 1 (your own confidence in this extraction)\n'
        "}\n\n"
        "Classify each line as line_type \"fee\" (a timekeeper billed hours at a "
        "rate) or \"expense\" (a flat cost like filing fees, courier, printing, "
        "travel — no timekeeper, no hours, no rate). Include one entry per "
        "timekeeper/task line AND per itemized expense, correctly classified. "
        "Never invent a placeholder timekeeper name (e.g. \"UNKNOWN\" or \"N/A\") "
        "for expense lines — use null. "
        "If the text has no line-item detail at all, return an empty list "
        "for line_items rather than inventing entries. "
        "If billing_period isn't explicitly stated, use null rather than guessing.\n\n"
        "Invoice text:\n" + raw_text
    )


def _normalize_extracted_fields(data: dict) -> dict:
    """Coerce Groq's JSON into consistent types so downstream (validate(),
    budget math, persistence) never has to guard against strings-that-
    should-be-numbers etc."""
    def _to_float(v, default=0.0):
        if v is None:
            return default
        try:
            return float(str(v).replace(",", "").replace("$", ""))
        except (ValueError, TypeError):
            return default

    line_items_in = data.get("line_items") or []
    line_items = []
    for li in line_items_in:
        if not isinstance(li, dict):
            continue
        timekeeper = li.get("timekeeper") or None  # preserve null — do NOT coerce to "UNKNOWN"; expense lines legitimately have no timekeeper
        hours = _to_float(li.get("hours"), default=None) if li.get("hours") is not None else None
        rate = _to_float(li.get("rate"), default=None) if li.get("rate") is not None else None

        # Trust the model's line_type if it gave one; otherwise infer from
        # whether a timekeeper is present. Keeps this safe even against a
        # model that ignores the schema instruction.
        line_type = li.get("line_type")
        if line_type not in ("fee", "expense"):
            line_type = "expense" if timekeeper is None else "fee"

        line_items.append({
            "line_type": line_type,
            "timekeeper": timekeeper,
            "role": li.get("role"),
            "hours": hours,
            "rate": rate,
            "amount": _to_float(li.get("amount")),
            "description": li.get("description"),
        })

    invoice_no = data.get("invoice_no")
    if isinstance(invoice_no, str):
        invoice_no = invoice_no.strip()

    return {
        "invoice_no": invoice_no or "UNKNOWN",
        "invoice_date": data.get("invoice_date"),
        "billing_period_start": data.get("billing_period_start"),
        "billing_period_end": data.get("billing_period_end"),
        "matter_no": (data.get("matter_no") or "").strip() or None,
        "matter_name": data.get("matter_name"),
        "firm_name": data.get("firm_name"),
        "firm_address": data.get("firm_address"),
        "total_amount": _to_float(data.get("total_amount")),
        "line_items": line_items,
    }


def _completeness_heuristic(fields: dict) -> float:
    """
    Simple field-completeness score (Architecture Doc §5: confidence is
    "derived from the model's own stated confidence ... combined with a
    simple completeness heuristic"). Independent of what the model *says*
    about itself — this checks what actually came back.
    """
    checks = 0
    passed = 0

    checks += 1
    if fields.get("invoice_no") and fields["invoice_no"] != "UNKNOWN":
        passed += 1

    checks += 1
    if fields.get("invoice_date"):
        passed += 1

    checks += 1
    if fields.get("total_amount", 0) > 0:
        passed += 1

    checks += 1
    line_items = fields.get("line_items") or []
    if line_items:
        passed += 1
        # Bonus signal (doesn't add a new check slot): line items should
        # roughly sum to the total. Large mismatches suggest a bad parse.
        try:
            line_sum = sum(li.get("amount") or 0.0 for li in line_items)
            total = fields.get("total_amount") or 0.0
            if total > 0 and abs(line_sum - total) / total < 0.05:
                passed += 0.5
        except (TypeError, ZeroDivisionError):
            pass

    return min(passed / checks, 1.0)


def extract_with_groq_call(raw_text: str) -> tuple[dict, float]:
    """
    Bhushan's job: the real Groq extraction call (Architecture Doc — Groq
    API, Llama 3.x free tier). Wired here for real if GROQ_API_KEY is set;
    otherwise falls back to the deterministic mock above so Ketan's graph
    and demo are never blocked waiting on API access.

    Returns (extracted_fields, confidence_score).

    Edge cases handled (Architecture Doc §7):
    - Empty raw_text (malformed/unreadable PDF that extract_text_from_pdf
      couldn't read even via OCR) -> confidence 0.0, never calls the API.
      0.0 is always below AUTO_APPROVE_CONFIDENCE_THRESHOLD, so router()
      sends it straight to human_review — "flagged for manual entry rather
      than failing silently," per the edge-case table.
    - Groq rate-limited / transient error -> retry with exponential
      backoff (NFR: "must retry with backoff ... rather than crash the
      pipeline"); after GROQ_MAX_RETRIES failures, falls back to the mock
      extractor with a conservative confidence rather than crashing.
    - Non-JSON / malformed model response -> same retry-then-fallback path.
    """
    if not raw_text or not raw_text.strip():
        return (
            {"invoice_no": "UNKNOWN", "invoice_date": None, "billing_period_start": None, "billing_period_end": None, "total_amount": 0.0, "line_items": []},
            0.0,
        )

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_api_key_here":
        _fields = extract_invoice_fields_mock(raw_text)
        return _fields, 0.60  # deliberately below auto-approve threshold — mock data should route to review

    from groq import Groq
    client = Groq(api_key=api_key)
    prompt = _build_extraction_prompt(raw_text)

    data = None
    last_error: Optional[Exception] = None

    for attempt in range(1, GROQ_MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            break
        except Exception as e:
            last_error = e
            print(f"[extract_with_groq_call] attempt {attempt}/{GROQ_MAX_RETRIES} failed: {e}")
            if attempt < GROQ_MAX_RETRIES:
                time.sleep(GROQ_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))

    if data is None:
        # All retries exhausted (rate limit, timeout, bad JSON, etc.) —
        # degrade to the mock rather than crashing the pipeline (NFR:
        # Reliability). Confidence stays low so it routes to human review.
        print(f"[extract_with_groq_call] giving up after {GROQ_MAX_RETRIES} attempts ({last_error}); falling back to mock")
        _fields = extract_invoice_fields_mock(raw_text)
        return _fields, 0.5

    model_confidence = float(data.pop("confidence", 0.9))
    fields = _normalize_extracted_fields(data)
    completeness = _completeness_heuristic(fields)
    confidence = round((model_confidence + completeness) / 2, 2)

    return fields, confidence


def resolve_matter(state: InvoiceGraphState) -> InvoiceGraphState:
    from app.database.invoice_repository import get_or_create_matter

    extracted = state["extracted"]
    matter_no = extracted.get("matter_no") or state.get("matter_no_override")
    firm_name = extracted.get("firm_name") or state.get("firm_name")
    firm_address = extracted.get("firm_address") or state.get("firm_address")

    if not matter_no:
        # No matter identifier extractable at all — can't proceed automatically.
        state["error"] = "no_matter_identifier"
        _log(state, "No matter_no could be extracted from the invoice; cannot resolve a matter.")
        return state

    matter = get_or_create_matter(
        state["db"], matter_no, extracted.get("matter_name"), firm_name=firm_name, firm_address=firm_address
    )
    state["matter_id"] = matter.matter_id
    state["firm_id"] = matter.firm_id
    _log(state, f"Resolved matter_no={matter_no!r} to matter_id={matter.matter_id} (firm_id={matter.firm_id}).")
    return state


def route_after_resolve(state: InvoiceGraphState) -> str:
    return "no_matter" if state.get("error") == "no_matter_identifier" else "matter_ok"


def no_matter_found(state: InvoiceGraphState) -> InvoiceGraphState:
    state["final_status"] = "extraction_failed_no_matter"
    _log(state, "Routed to manual handling — no matter identifier found on the invoice.")
    return state


def _log(state: InvoiceGraphState, message: str) -> None:
    ts_msg = f"[{datetime.now(timezone.utc).isoformat()}] {message}"
    state.setdefault("audit_trail", []).append(ts_msg)

    # Persist as structured audit log when a DB session is available.
    db = state.get("db")
    if db is not None:
        try:
            def _derive_action(msg: str) -> str:
                # Create a short machine-friendly action key from the
                # human message: take first 3 alpha words, lowercase,
                # replace non-alphanum with underscores.
                words = re.findall(r"[A-Za-z0-9]+", msg)
                key = "_".join(words[:3]).lower()
                return key or "event"

            action = _derive_action(message)
            add_audit_log(
                db,
                action=action,
                user_id=-1,
                invoice_id=state.get("invoice_id"),
                notes=message,
            )
            # Flush so downstream nodes can rely on persisted audit ids
            # if needed; ignore flush errors to avoid interrupting flow.
            try:
                db.flush()
            except Exception:
                pass
        except Exception:
            # Never let audit persistence break the workflow; keep silent
            # and rely on the in-memory `audit_trail` for debugging.
            pass


def ingest_invoice(state: InvoiceGraphState) -> InvoiceGraphState:
    # Fixed during QA pass (14 Aug 2026): this used to call extract_text()
    # from invoice_pipeline.py, which has no OCR fallback — for a
    # scanned/image-only PDF (no native text layer), it fell straight
    # through to reading the raw PDF *file bytes* as text, feeding
    # binary garbage into extraction and silently returning empty/
    # "UNKNOWN" fields with no error. The real OCR fallback
    # (extract_text_from_pdf, below in this file) already existed but
    # was never wired into the pipeline — this now actually calls it.
    state["raw_text"] = extract_text_from_pdf(state["file_path"])
    _log(state, "Invoice document ingested.")
    return state


def extract_with_groq(state: InvoiceGraphState) -> InvoiceGraphState:
    extracted, confidence = extract_with_groq_call(state["raw_text"])
    state["extracted"] = extracted
    state["confidence_score"] = confidence
    _log(state, f"Invoice fields extracted with confidence={confidence:.2f}.")
    return state


def validate(state: InvoiceGraphState) -> InvoiceGraphState:
    db = state["db"]
    validate_relationships(db, state["matter_id"], state["firm_id"])

    fields = state["extracted"]
    # Validate against a transient Invoice so the existing validation service
    # remains the single source of validation/business rules.
    transient = entities.Invoice(
        matter_id=state["matter_id"],
        firm_id=state["firm_id"],
        invoice_no=fields["invoice_no"],
        invoice_date=fields.get("invoice_date"),
        total_amount=fields["total_amount"],
        confidence_score=state["confidence_score"],
    )
    
    
    result = validate_invoice(db, transient, confidence_score=state["confidence_score"])
    state["validation"] = result
    state["route"] = (
        "auto_approve"
        if result["validation_passed"]
        and state["confidence_score"] >= AUTO_APPROVE_CONFIDENCE_THRESHOLD
        else "human_review"
    )
    _log(state, f"Validation completed: {state['route']}.")
    return state


def persist_invoice(state: InvoiceGraphState) -> InvoiceGraphState:
    invoice = persist_extracted_invoice(state)

    # Persist the immutable intake snapshot immediately after the invoice gets
    # a real id. The snapshot powers the budget decision/history UI and must
    # exist before the route can auto-approve or send the invoice to review.
    from app.models import Budget
    from app.services.budget_management import apply_intake_snapshot
    budget = state["db"].query(Budget).filter(Budget.matter_id == invoice.matter_id).first()
    if budget is not None:
        apply_intake_snapshot(state["db"], invoice, budget, user_id=-1)

    result = state["validation"]
    invoice.budget_valid = result["budget_ok"]
    invoice.duplicate_flag = result["duplicate"]
    invoice.validation_status = "passed" if result["validation_passed"] else "failed"
    invoice.validation_message = "; ".join(result["reasons"])
    state["validation_passed"] = result["validation_passed"]
    state["validation_reason"] = invoice.validation_message
    state["is_duplicate"] = result["duplicate"]
    state["invoice_id"] = invoice.invoice_id
    state["db"].flush()
    _log(state, f"Invoice '{invoice.invoice_no}' persisted with id={invoice.invoice_id} and {len(invoice.line_items)} line items.")
    return state


def route_decision(state: InvoiceGraphState) -> str:
    return state["route"]

def auto_approve(
    state: InvoiceGraphState,
) -> InvoiceGraphState:

    db = state["db"]

    invoice = db.get(
        entities.Invoice,
        state["invoice_id"],
    )

    if invoice is None:
        raise ValueError(
            "Persisted invoice could not be loaded."
        )

    auto_approve_invoice(
        db=db,
        invoice=invoice,
    )

    state["final_status"] = "approved"

    _log(
        state,
        "Invoice auto-approved by LangGraph.",
    )

    return state


def update_budget_and_alerts(state: InvoiceGraphState) -> InvoiceGraphState:
    # Budget posting is intentionally delegated to approval_service so there is
    # only one implementation of ledger/alert side effects.
    _log(state, "Budget and alert side effects handled by approval workflow.")
    return state


def notify_report(state: InvoiceGraphState) -> InvoiceGraphState:
    _log(state, f"Processing completed with status={state['final_status']}.")
    return state


def human_review(state: InvoiceGraphState) -> InvoiceGraphState:
    invoice = state["db"].get(entities.Invoice, state["invoice_id"])
    if invoice is None:
        raise ValueError("Persisted invoice could not be loaded.")
    invoice.status = "pending_review"
    add_audit_log(
        state["db"],
        action="validated",
        user_id=-1,
        invoice_id=invoice.invoice_id,
        notes=invoice.validation_message,
    )
    state["db"].commit()
    state["final_status"] = "pending_review"
    _log(state, "Invoice sent to human review.")
    return state


def log_for_review(state: InvoiceGraphState) -> InvoiceGraphState:
    _log(state, "Human-review queue entry recorded through invoice status/audit log.")

    from app.database.invoice_repository import InvoiceAlreadyExistsError
    if state["inv_changes"]:
        raise InvoiceAlreadyExistsError(
                    invoice_no=state["extracted"]["invoice_no"],
                    matter_id=str(state["matter_id"]),
                    inv_changes=state["inv_changes"],
                )

    return state


def build_invoice_graph():
    graph = StateGraph(InvoiceGraphState)
    graph.add_node("ingest_invoice", ingest_invoice)
    graph.add_node("extract_with_groq", extract_with_groq)
    
    graph.add_node("resolve_matter", resolve_matter)          # NEW
    graph.add_node("no_matter_found", no_matter_found)         # NEW
    
    graph.add_node("validate", validate)
    graph.add_node("persist_invoice", persist_invoice)
    graph.add_node("auto_approve", auto_approve)
    graph.add_node("update_budget_and_alerts", update_budget_and_alerts)
    graph.add_node("notify_report", notify_report)
    graph.add_node("human_review", human_review)
    graph.add_node("log_for_review", log_for_review)

    graph.add_edge(START, "ingest_invoice")
    graph.add_edge("ingest_invoice", "extract_with_groq")
    
    graph.add_edge("extract_with_groq", "resolve_matter")
    
    graph.add_conditional_edges(
        "resolve_matter",
        route_after_resolve,
        {"matter_ok": "validate", "no_matter": "no_matter_found"},
    )
    graph.add_edge("no_matter_found", END)
    
    graph.add_edge("validate", "persist_invoice")
    graph.add_conditional_edges(
        "persist_invoice",
        route_decision,
        {"auto_approve": "auto_approve", "human_review": "human_review"},
    )
    graph.add_edge("auto_approve", "update_budget_and_alerts")
    graph.add_edge("update_budget_and_alerts", "notify_report")
    graph.add_edge("notify_report", END)
    graph.add_edge("human_review", "log_for_review")
    graph.add_edge("log_for_review", END)
    return graph.compile()


def run_invoice_graph(
    db: Session,
    *,
    file_path: str,
    matter_no_override: str | None = None,
    firm_name: str | None = None,
    firm_address: str | None = None,
) -> InvoiceGraphState:
    graph = build_invoice_graph()
    return graph.invoke(
        {
            "db": db,
            "file_path": file_path,
            "matter_no_override": matter_no_override,
            "firm_name": firm_name,
            "firm_address": firm_address,
            "audit_trail": [],
        }
    )


def draw_graph():
    png_bytes = build_invoice_graph().get_graph().draw_mermaid_png()
    
    with open("graph_diagram.png", "wb") as f:
        f.write(png_bytes)
  
def call_run_invoice_graph(filepath, matter_no_override: str | None = None, firm_name: str | None = None, firm_address: str | None = None):
    from app.database.database import SessionLocal

    db = SessionLocal()
    try:
        state = run_invoice_graph(
            db, file_path=filepath, matter_no_override=matter_no_override, firm_name=firm_name, firm_address=firm_address
        )
        db.commit()
        return state
    finally:
        db.close()

if __name__=="__main__":
    draw_graph()