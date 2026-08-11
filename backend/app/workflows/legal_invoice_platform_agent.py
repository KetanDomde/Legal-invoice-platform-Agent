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
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional, TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

load_dotenv()

# Day 4: wired to the real SQLAlchemy data layer (app/database/crud.py +
# app/database/session.py) instead of in-memory stubs, since persistence
# needs to survive across API calls (status/review-queue/reports all read
# what submit_invoice wrote). Each stub opens and closes its own short-lived
# session — the graph has no request-scoped session to reuse.
try:
    from app.database import crud as _crud
    from app.database.session import SessionLocal as _SessionLocal
    _HAS_DB = True
except ImportError:
    _HAS_DB = False

APP_NAME = "Legal Invoice Platform Agent"

# Confidence at/above this auto-approves (subject to budget check); below it
# always goes to human review, per PRD's confidence-routing requirement.
AUTO_APPROVE_CONFIDENCE_THRESHOLD = 0.85


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class InvoiceState(TypedDict, total=False):
    # Input
    file_path: str
    matter_id: int
    firm_id: int

    # Set by ingest_invoice
    raw_text: str

    # Set by extract_with_groq
    extracted: dict          # {invoice_no, invoice_date, total_amount, line_items, ...}
    confidence_score: float

    # Set by validate
    budget_info: dict        # from get_remaining_budget()
    is_duplicate: bool
    validation_passed: bool
    validation_reason: str

    # Set by router / terminal nodes
    route: str               # "auto_approve" | "human_review"
    final_status: str        # "approved" | "pending_review" | "rejected"
    invoice_id: Optional[int]
    audit_trail: list        # list[str] — human-readable trail for the demo/report
    error: Optional[str]


def _log(state: InvoiceState, message: str) -> None:
    state.setdefault("audit_trail", []).append(f"[{datetime.now(timezone.utc).isoformat()}] {message}")
    print(message)


# ---------------------------------------------------------------------------
# STUBS — replace these bodies (or swap the import) as each module lands.
# Every stub is intentionally obvious and loud (prefixed "[stub]") so nobody
# mistakes placeholder output for a real result during the demo.
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path: str) -> str:
    """
    Bhushan's job (PyMuPDF + Tesseract OCR fallback per Architecture Doc).
    Stub: if the "PDF" is actually a plain-text sample file, just read it,
    so the pipeline is runnable before real PDF parsing exists.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        if text.strip():
            return text
    except Exception:
        pass
    # Fallback: treat the file as plain text (works for a .txt sample invoice
    # during Day 1/2 before OCR is wired in), or return a canned sample.
    if os.path.exists(file_path):
        with open(file_path, "r", errors="ignore") as f:
            return f.read()
    return (
        "[stub] Could not read file_path — using a canned sample invoice.\n"
        "Invoice No: INV-1001\nDate: 2026-08-07\nFirm: Sample Outside Counsel LLP\n"
        "Line items:\n- J. Smith, Partner, 4.5 hrs @ $450/hr = $2025.00\n"
        "- A. Lee, Associate, 6.0 hrs @ $250/hr = $1500.00\n"
        "Total: $3525.00"
    )


def extract_invoice_fields_mock(raw_text: str) -> dict:
    """Deterministic, no-API-key-needed fallback so Day 1/2 never blocks on Groq access."""
    total_match = re.search(r"Total:\s*\$?([\d,]+\.\d{2})", raw_text)
    invoice_no_match = re.search(r"Invoice No:\s*(\S+)", raw_text)
    date_match = re.search(r"Date:\s*([\d-]+)", raw_text)
    return {
        "invoice_no": invoice_no_match.group(1) if invoice_no_match else "UNKNOWN",
        "invoice_date": date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d"),
        "total_amount": float(total_match.group(1).replace(",", "")) if total_match else 0.0,
        "line_items": [],  # Bhushan: populate structured line items from the real extraction
    }


def extract_with_groq_call(raw_text: str) -> tuple[dict, float]:
    """
    Bhushan's job: the real Groq extraction call (Architecture Doc — Groq
    API, Llama 3.x free tier). Wired here for real if GROQ_API_KEY is set;
    otherwise falls back to the deterministic mock above so Ketan's graph
    and demo are never blocked waiting on API access.
    Returns (extracted_fields, confidence_score).
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_api_key_here":
        _fields = extract_invoice_fields_mock(raw_text)
        return _fields, 0.60  # deliberately below auto-approve threshold — mock data should route to review

    from groq import Groq
    client = Groq(api_key=api_key)
    prompt = (
        "Extract invoice_no, invoice_date (YYYY-MM-DD), and total_amount (number, no currency symbol) "
        "from this invoice text as strict JSON with keys invoice_no, invoice_date, total_amount, "
        "and confidence (0-1, your confidence in the extraction). Text:\n\n" + raw_text
    )
    resp = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    confidence = float(data.pop("confidence", 0.9))
    return data, confidence


def get_remaining_budget_stub(matter_id: int) -> dict:
    """
    Rajat's job (budget/ledger query). Real SQLAlchemy data layer wired in
    as of Day 4 — falls back to a generous placeholder only if the data
    layer genuinely isn't importable, so the demo never hard-crashes.
    """
    if not _HAS_DB:
        return {"has_budget": True, "allocated": 50000.0, "spent": 0.0, "remaining": 50000.0, "pct_used": 0.0, "threshold_pct": 80}
    db = _SessionLocal()
    try:
        return _crud.get_remaining_budget(db, matter_id)
    finally:
        db.close()


def check_duplicate_invoice_stub(invoice_no: str, firm_id: int) -> bool:
    """Trinkesh/Rajat's job (duplicate detection). Wired to the real DB check; falls back to False if unavailable."""
    if not _HAS_DB:
        return False
    db = _SessionLocal()
    try:
        return _crud.check_duplicate_invoice(db, invoice_no, firm_id)
    finally:
        db.close()


def persist_invoice_stub(state: InvoiceState) -> int:
    """Rajat's job (INSERT into invoice table). Wired to the real DB insert as of Day 4."""
    if not _HAS_DB:
        return -1
    extracted = state["extracted"]
    db = _SessionLocal()
    try:
        return _crud.insert_invoice(
            db,
            matter_id=state["matter_id"],
            firm_id=state["firm_id"],
            invoice_no=extracted.get("invoice_no", "UNKNOWN"),
            invoice_date=extracted.get("invoice_date", ""),
            total_amount=extracted.get("total_amount", 0.0),
            confidence_score=state.get("confidence_score"),
            status="submitted",
        )
    finally:
        db.close()


def write_audit_log_stub(action: str, invoice_id, notes: str = "", user_id: int = None) -> None:
    """Trinkesh's job (audit_log table). Wired to the real DB write as of Day 4."""
    if not _HAS_DB or invoice_id in (None, -1):
        print(f"[stub audit_log] action={action} invoice_id={invoice_id} notes={notes}")
        return
    db = _SessionLocal()
    try:
        _crud.write_audit_log(db, action=action, invoice_id=invoice_id, user_id=user_id, notes=notes)
    finally:
        db.close()


def update_budget_ledger_stub(matter_id: int, invoice_id, amount: float) -> None:
    """Rajat's job (budget_ledger INSERT + threshold alert). Wired to the real DB as of Day 4."""
    if not _HAS_DB or invoice_id in (None, -1):
        print(f"[stub budget_ledger] matter_id={matter_id} invoice_id={invoice_id} amount={amount}")
        return
    db = _SessionLocal()
    try:
        budget_info = _crud.get_remaining_budget(db, matter_id)
        if not budget_info["has_budget"]:
            print(f"[budget_ledger] no budget found for matter_id={matter_id}, skipping ledger entry")
            return
        _crud.record_ledger_entry(db, budget_info["budget_id"], invoice_id, amount)
        alert_msg = _crud.create_alert_if_threshold_crossed(db, budget_info["budget_id"])
        if alert_msg:
            print(f"[ALERT] {alert_msg}")
        _crud.update_invoice_status(db, invoice_id, "approved")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def ingest_invoice(state: InvoiceState) -> InvoiceState:
    _log(state, f"[ingest_invoice] reading {state['file_path']}")
    state["raw_text"] = extract_text_from_pdf(state["file_path"])
    return state


def extract_with_groq(state: InvoiceState) -> InvoiceState:
    extracted, confidence = extract_with_groq_call(state["raw_text"])
    state["extracted"] = extracted
    state["confidence_score"] = confidence
    _log(state, f"[extract_with_groq] extracted={extracted} confidence={confidence:.2f}")
    return state


def validate(state: InvoiceState) -> InvoiceState:
    budget_info = get_remaining_budget_stub(state["matter_id"])
    state["budget_info"] = budget_info

    invoice_no = state["extracted"].get("invoice_no", "UNKNOWN")
    is_duplicate = check_duplicate_invoice_stub(invoice_no, state["firm_id"])
    state["is_duplicate"] = is_duplicate

    total_amount = state["extracted"].get("total_amount", 0.0)
    within_budget = budget_info["has_budget"] and total_amount <= budget_info["remaining"]

    passed = within_budget and not is_duplicate
    reason_parts = []
    if not within_budget:
        reason_parts.append(f"total ${total_amount} exceeds remaining budget ${budget_info.get('remaining')}")
    if is_duplicate:
        reason_parts.append("duplicate invoice_no for this firm")
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
    invoice_id = persist_invoice_stub(state)
    state["invoice_id"] = invoice_id
    state["final_status"] = "approved"
    write_audit_log_stub("auto_approved", invoice_id, state["validation_reason"])
    _log(state, f"[auto_approve] invoice_id={invoice_id} status=approved")
    return state


def human_review(state: InvoiceState) -> InvoiceState:
    invoice_id = persist_invoice_stub(state)
    state["invoice_id"] = invoice_id
    state["final_status"] = "pending_review"
    if _HAS_DB and invoice_id not in (None, -1):
        db = _SessionLocal()
        try:
            _crud.update_invoice_status(db, invoice_id, "pending_review")
        finally:
            db.close()
    write_audit_log_stub("sent_to_review", invoice_id, state["validation_reason"])
    _log(state, f"[human_review] invoice_id={invoice_id} status=pending_review reason={state['validation_reason']}")
    return state


def update_budget_and_alerts(state: InvoiceState) -> InvoiceState:
    update_budget_ledger_stub(state["matter_id"], state["invoice_id"], state["extracted"].get("total_amount", 0.0))
    _log(state, "[update_budget_and_alerts] ledger entry posted, invoice marked approved, threshold alert checked")
    return state


def notify_report(state: InvoiceState) -> InvoiceState:
    _log(state, f"[notify_report] final_status={state['final_status']} invoice={state['extracted']}")
    return state


def log_for_review(state: InvoiceState) -> InvoiceState:
    _log(state, "[log_for_review] invoice is now visible in GET /invoices/review-queue")
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


def run_pipeline(file_path: str, matter_id: int, firm_id: int) -> InvoiceState:
    agent = build_legal_invoice_platform_agent()
    initial_state: InvoiceState = {"file_path": file_path, "matter_id": matter_id, "firm_id": firm_id}
    result = agent.invoke(initial_state)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{APP_NAME} — run one invoice through the pipeline (Day 2 demo).")
    parser.add_argument("file_path", help="Path to a sample invoice (PDF, or .txt for a quick smoke test)")
    parser.add_argument("--matter-id", type=int, default=1)
    parser.add_argument("--firm-id", type=int, default=1)
    args = parser.parse_args()

    print(f"=== {APP_NAME} — Day 2 demo run ===")
    final_state = run_pipeline(args.file_path, args.matter_id, args.firm_id)
    print("\n=== Final state ===")
    print(json.dumps({k: v for k, v in final_state.items() if k != "audit_trail"}, indent=2, default=str))
    print("\n=== Audit trail ===")
    for line in final_state.get("audit_trail", []):
        print(line)