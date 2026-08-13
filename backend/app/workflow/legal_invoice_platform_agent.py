"""
Legal Invoice Platform Agent
============================
Owner: Ketan (Project Lead) — LangGraph orchestration + integration.

This is the single StateGraph that runs one invoice end-to-end:

    START -> ingest_invoice -> extract_with_groq -> validate -> [router]
                                                                    |
                        -------------------------------------------+------------------------------
                        |                                                                          |
                auto_approve -> update_budget_and_alerts -> notify_report -> END        human_review -> log_for_review -> END

Day-1/2 reality: Rajat/Bhushan/Trinkesh's real functions may not exist yet.
Every call into their territory goes through a small stub in `# --- STUBS ---`
below, so this graph is runnable and demoable TODAY. As each teammate lands
their real module, replace only that stub's body (or its import) — the graph
wiring itself does not need to change. That's the point of "build thin, then
expand": integration never blocks on a module that isn't ready yet.

Ready to paste into: backend/app/workflows/graph.py
(rename the file if you'd rather keep this exact filename — either is fine,
just update the import in main.py to match.)

Run directly for the Day 2 demo:
    python -m app.workflows.legal_invoice_platform_agent path/to/sample_invoice.pdf --matter-id 1 --firm-id 1
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from app.database.invoice_repository import InvoiceAlreadyExistsError

# --- Path anchoring -----------------------------------------------------
# Everything below is resolved relative to THIS FILE, not the current
# working directory. Relying on cwd (e.g. bare `test_invoices/` or the
# default load_dotenv() search) breaks the moment someone runs this from
# the repo root, from workflows/, or from anywhere other than backend/ —
# which is exactly the failure mode this caused twice already.
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


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class InvoiceState(TypedDict, total=False):
    # Input
    file_path: str
    matter_id: str
    firm_id: Optional[int]     # optional now — derived from Matter if not given; see routers/invoices.py

    # Set by extract_with_groq
    extracted: dict          # {invoice_no, invoice_date, billing_period_start, billing_period_end, total_amount, line_items, ...}
    confidence_score: float

    # Set by persist_ticket
    invoice_id: int

    # Set by ingest_invoice
    raw_text: str

    # Set by extract_with_groq
    extracted: dict          # {invoice_no, invoice_date, billing_period_start, billing_period_end, total_amount, line_items, ...}
    confidence_score: float

    # Set by validate
    budget_info: dict        # from get_remaining_budget()
    is_duplicate: bool
    validation_passed: bool
    validation_reason: str

    # Set by router / terminal nodes
    route: str               # "auto_approve" | "human_review"
    final_status: str        # "approved" | "pending_review" | "rejected"
    audit_trail: list        # list[str] — human-readable trail for the demo/report
    error: Optional[str]


def _log(state: InvoiceState, message: str) -> None:
    state.setdefault("audit_trail", []).append(f"[{datetime.now(timezone.utc).isoformat()}] {message}")
    print(message)


# ---------------------------------------------------------------------------
# STUBS — replace these bodies (or swap the import) as each module lands.
# Every stub is intentionally obvious and loud (prefixed "[stub]") so nobody
# mistakes placeholder output for a real result during the demo.
#
# STATUS (updated 11 Aug 2026 by Bhushan):
#   DONE   extract_text_from_pdf        — real PyMuPDF + Tesseract OCR fallback
#   DONE   extract_with_groq_call       — real Groq call, line_items + billing_period
#                                         included, retry/backoff, confidence heuristic
#   DONE   persist_invoice_stub         — real INSERT via app.database.
#                                         invoice_repository; see note below
#                                         on the Matter placeholder this
#                                         needed to unblock the ORM
#   DONE   check_duplicate_invoice_stub — real duplicate check on invoice_id
#                                         directly (see REDESIGN note below)
#   TODO   get_remaining_budget_stub    — owner: Rajat (ERD: BUDGET, BUDGET_LEDGER)
#   TODO   write_audit_log_stub         — owner: Trinkesh (ERD: AUDIT_LOG)
#   TODO   update_budget_ledger_stub    — owner: Rajat (ERD: BUDGET_LEDGER, ALERT)
#
#   ⚠ persist_invoice_stub is now implemented on the assumption that ERD.docx
#   is correct (INVOICE + LINE_ITEM owned by Bhushan) over the older code
#   comment that said "Rajat's job" — get this confirmed at standup; it was
#   unblocked work either way since neither model existed yet.
#
#   ⚠ REDESIGN (11 Aug): invoice_id is no longer an auto-increment DB int.
#   It's now a REQUIRED, caller-supplied alphanumeric string (e.g.
#   "INV-2026-001") and IS the primary key on the invoices table. This was
#   a bug fix, not a preference: the old design meant a failed persist
#   attempt returned a fake "-1" that looked like a real id, and the same
#   PDF submitted twice created two full rows under two different ids
#   because nothing checked the ACTUAL identity before processing.
#   persist_invoice_stub no longer swallows failures into a fake return
#   value — it raises, and routers/invoices.py is where that becomes a
#   clean 409 (duplicate) or 500 (other failure) instead of a silent lie.
#
#   ⚠ Building this also required adding app/models/matter.py, which did NOT
#   exist AT ALL. Without it, firm.py's `relationship("Matter", ...)` made
#   the ORM unusable for every model, not just Invoice — confirmed by
#   testing. It's a TEMPORARY PLACEHOLDER (fields match the ERD, no real
#   logic) — Rajat should review/replace it, not build on top of it. See
#   that file's docstring for full detail.
# ---------------------------------------------------------------------------

def _ocr_pdf_pages(doc) -> str:
    """
    Rasterize each page of an open PyMuPDF document and run Tesseract OCR
    on it. Used when the PDF has no usable native text layer — i.e. it's a
    scanned/image-only invoice (Architecture Doc §7 edge case).
    """
    import pytesseract
    from PIL import Image

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

    is_pdf = file_path.lower().endswith(".pdf")

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
        "matter_name": matter_match.group(2).strip() if matter_match else None,
        "total_amount": total_amount,
        "line_items": line_items,
    }


def _build_extraction_prompt(raw_text: str) -> str:
    """
    FR-6 requires invoice_no, invoice_date, total_amount, AND line items
    (timekeeper, hours, rate, amount) — matches the ERD's LINE_ITEM table.
    The original stub's prompt only asked for the top-level fields; this
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
                model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
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


def get_remaining_budget_stub(matter_id: str) -> dict:
    """
    Rajat's job — ERD entities: BUDGET, BUDGET_LEDGER. PRD FR-2/FR-3.
    Real version: SUM(BUDGET_LEDGER.amount) for this matter's budget_id,
    subtract from BUDGET.allocated_amt, compare against threshold_pct.
    Stub returns a generous placeholder budget so validate() and routing
    are testable before the real data layer exists. Swap this for
    `from app.database... import get_remaining_budget` the moment Rajat's
    function lands — signature matches exactly, so it's a one-line change.
    """
    return {"has_budget": True, "allocated": 50000.0, "spent": 0.0, "remaining": 50000.0, "pct_used": 0.0, "threshold_pct": 80}


def check_duplicate_invoice_stub(invoice_no: str, matter_id: str) -> bool:
    """
    Owner: Bhushan (see the note in the STATUS block above).

    Checks for an existing invoice by invoice_no and matter_id, which is
    the correct business duplicate key when invoice_id is generated by
    the system.

    Falls back to "not a duplicate" only if the app package isn't
    importable in this run context.
    """
    try:
        from app.database.invoice_repository import invoice_exists_by_business_key
    except Exception as e:
        print(f"[check_duplicate] app.database not importable ({e}) — falling back to 'not a duplicate'")
        return False

    return invoice_exists_by_business_key(invoice_no, matter_id)


def persist_invoice_stub(state: InvoiceState, status: str) -> int:
    """
    Owner: Bhushan (ERD: INVOICE, LINE_ITEM — see the ownership-conflict
    note in the STATUS block above; confirm at standup before relying on
    this being final).

    REDESIGNED — this is the key behavior change behind the whole
    invoice_id rework: previously, ANY failure here (DB error, app
    package not importable) silently returned -1 and let the pipeline
    report success anyway. That's exactly backwards for an identity the
    caller controls: a fake id must never look like a real one.

    Now: on any failure, this RAISES (InvoiceAlreadyExistsError for a
    genuine duplicate slipping past the pre-flight check via a race
    condition, or the underlying exception for anything else) instead of
    returning a sentinel value. auto_approve/human_review don't catch it
    either — it's the API layer's (routers/invoices.py) job to turn a
    raised exception into the right HTTP response (409 vs 500), which is
    also where the pre-flight duplicate check already lives.

    Returns the same invoice_id string that was passed in via state —
    never generates one, never fabricates a fallback.
    """
    from app.database.invoice_repository import insert_invoice_with_line_items

    return insert_invoice_with_line_items(
        matter_id=state["matter_id"],
        firm_id=state.get("firm_id"),
        extracted=state["extracted"],
        confidence_score=state.get("confidence_score", 0.0),
        status=status,
    )


def write_audit_log_stub(action: str, invoice_id, notes: str = "") -> None:
    """
    Trinkesh's job — ERD entity: AUDIT_LOG. PRD FR-14/FR-22.
    Real version: INSERT into audit_logs (invoice_id, user_id, action,
    notes, timestamp). Stub just prints — swap for
    app.database.write_audit_log(...).
    """
    print(f"[stub audit_log] action={action} invoice_id={invoice_id} notes={notes}")


def update_budget_ledger_stub(matter_id: str, invoice_id, amount: float) -> None:
    """
    Rajat's job — ERD entities: BUDGET_LEDGER, ALERT. PRD FR-15/FR-16.
    Real version: INSERT into budget_ledger, then check the new spend
    against BUDGET.threshold_pct and INSERT an ALERT row if crossed.
    Stub is a no-op print.
    """
    print(f"[stub budget_ledger] matter_id={matter_id} invoice_id={invoice_id} amount={amount}")


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def ingest_invoice(state: InvoiceState) -> InvoiceState:
    _log(state, f"[ingest_invoice] reading {state['file_path']}")
    state["raw_text"] = extract_text_from_pdf(state["file_path"])
    return state


def extract_with_groq(state: InvoiceState) -> InvoiceState:
    extracted, confidence = extract_with_groq_call(state["raw_text"])
    # If the caller provided an initial matter_name (from the upload form),
    # prefer the extracted one but fall back to the provided value.
    if state.get("initial_matter_name") and not extracted.get("matter_name"):
        extracted["matter_name"] = state.get("initial_matter_name")
    state["extracted"] = extracted
    state["confidence_score"] = confidence
    _log(state, f"[extract_with_groq] extracted={extracted} confidence={confidence:.2f}")
    return state


def validate(state: InvoiceState) -> InvoiceState:
    budget_info = get_remaining_budget_stub(state["matter_id"])
    state["budget_info"] = budget_info

    invoice_no = state["extracted"].get("invoice_no", "")
    if isinstance(invoice_no, str):
        invoice_no = invoice_no.strip()

    if invoice_no:
        is_duplicate = check_duplicate_invoice_stub(invoice_no, state["matter_id"])
        if is_duplicate:
            raise InvoiceAlreadyExistsError(invoice_no, state["matter_id"])
    else:
        is_duplicate = False

    state["is_duplicate"] = is_duplicate

    total_amount = state["extracted"].get("total_amount", 0.0)
    within_budget = budget_info["has_budget"] and total_amount <= budget_info["remaining"]

    passed = within_budget and not is_duplicate
    reason_parts = []
    if not within_budget:
        reason_parts.append(f"total ${total_amount} exceeds remaining budget ${budget_info.get('remaining')}")
    if is_duplicate:
        reason_parts.append(f"duplicate invoice_no {invoice_no!r} for matter_id {state['matter_id']!r}")
    if not reason_parts:
        reason_parts.append("within budget, no duplicate detected")

    state["validation_passed"] = passed
    state["validation_reason"] = "; ".join(reason_parts)
    _log(state, f"[validate] passed={passed} reason={state['validation_reason']}")
    return state


def route_decision(state: InvoiceState) -> str:
    """Conditional edge: high confidence AND valid -> auto_approve, else human_review."""
    high_confidence = state.get("confidence_score", 0.0) >= AUTO_APPROVE_CONFIDENCE_THRESHOLD
    if high_confidence and state.get("validation_passed"):
        return "auto_approve"
    return "human_review"


def auto_approve(state: InvoiceState) -> InvoiceState:
    # Status is set BEFORE persisting (not after, as the original stub
    # implied) because a real DB insert needs the final status up front —
    # see persist_invoice_stub's docstring.
    state["final_status"] = "approved"
    invoice_id = persist_invoice_stub(state, status="approved")
    state["invoice_id"] = invoice_id
    write_audit_log_stub("auto_approved", invoice_id, state["validation_reason"])
    _log(state, f"[auto_approve] invoice_id={invoice_id} status=approved")
    return state


def human_review(state: InvoiceState) -> InvoiceState:
    state["final_status"] = "pending_review"
    invoice_id = persist_invoice_stub(state, status="pending_review")
    state["invoice_id"] = invoice_id
    write_audit_log_stub("sent_to_review", invoice_id, state["validation_reason"])
    _log(state, f"[human_review] invoice_id={invoice_id} status=pending_review reason={state['validation_reason']}")
    return state


def update_budget_and_alerts(state: InvoiceState) -> InvoiceState:
    update_budget_ledger_stub(state["matter_id"], state["invoice_id"], state["extracted"].get("total_amount", 0.0))
    _log(state, "[update_budget_and_alerts] ledger updated (stub) — Rajat: wire real threshold alert check here")
    return state


def notify_report(state: InvoiceState) -> InvoiceState:
    _log(state, f"[notify_report] final_status={state['final_status']} invoice={state['extracted']}")
    return state


def log_for_review(state: InvoiceState) -> InvoiceState:
    _log(state, "[log_for_review] added to human-review queue (stub) — Trinkesh: wire real review-queue table here")
    return state


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

def build_legal_invoice_platform_agent():
    graph = StateGraph(InvoiceState)

    graph.add_node("ingest_invoice", ingest_invoice)
    graph.add_node("extract_with_groq", extract_with_groq)
    graph.add_node("validate", validate)
    graph.add_node("auto_approve", auto_approve)
    graph.add_node("human_review", human_review)
    graph.add_node("update_budget_and_alerts", update_budget_and_alerts)
    graph.add_node("notify_report", notify_report)
    graph.add_node("log_for_review", log_for_review)

    graph.add_edge(START, "ingest_invoice")
    graph.add_edge("ingest_invoice", "extract_with_groq")
    graph.add_edge("extract_with_groq", "validate")

    graph.add_conditional_edges(
        "validate",
        route_decision,
        {"auto_approve": "auto_approve", "human_review": "human_review"},
    )

    graph.add_edge("auto_approve", "update_budget_and_alerts")
    graph.add_edge("update_budget_and_alerts", "notify_report")
    graph.add_edge("notify_report", END)

    graph.add_edge("human_review", "log_for_review")
    graph.add_edge("log_for_review", END)

    return graph.compile()


def run_pipeline(file_path: str, matter_id: str, firm_id: Optional[int] = None, initial_matter_name: Optional[str] = None) -> InvoiceState:
    """
    Run extraction and persistence for a new invoice. The database
    generates the integer invoice_id; this function returns it in the
    final state.
    """
    agent = build_legal_invoice_platform_agent()
    initial_state: InvoiceState = {
        "file_path": file_path,
        "matter_id": matter_id,
        "firm_id": firm_id,
        "initial_matter_name": initial_matter_name,
    }
    result = agent.invoke(initial_state)
    return result


if __name__ == "__main__":
    import uuid

    parser = argparse.ArgumentParser(description=f"{APP_NAME} — run one invoice through the pipeline (Day 2 demo).")
    parser.add_argument(
        "file_path",
        nargs="?",
        default=None,
        help=(
            "Path to a sample invoice (PDF, or .txt for a quick smoke test). "
            f"If omitted, uses the first PDF found in {DEFAULT_TEST_INVOICES_DIR} "
            "— works from any directory, since it's anchored to this script's location."
        ),
    )
    parser.add_argument("--matter-id", type=str, default="M-1042")
    parser.add_argument("--firm-id", type=int, default=1)
    args = parser.parse_args()

    file_path = args.file_path
    if not file_path:
        candidates = sorted(DEFAULT_TEST_INVOICES_DIR.glob("*.pdf"))
        if not candidates:
            parser.error(
                f"No file_path given, and no PDFs found in {DEFAULT_TEST_INVOICES_DIR} "
                "— either pass a path explicitly or drop a sample PDF in that folder."
            )
        file_path = str(candidates[0])
        print(f"[cli] no file_path given — using '{file_path}' (first PDF found in {DEFAULT_TEST_INVOICES_DIR})")

    print(f"=== {APP_NAME} — Day 2 demo run ===")
    final_state = run_pipeline(file_path, args.matter_id, args.firm_id)
    print("\n=== Final state ===")
    print(json.dumps({k: v for k, v in final_state.items() if k != "audit_trail"}, indent=2, default=str))
    print("\n=== Audit trail ===")
    for line in final_state.get("audit_trail", []):
        print(line)