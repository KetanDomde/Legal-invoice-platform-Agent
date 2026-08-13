from __future__ import annotations
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.models import Invoice
from app.services.invoice import add_audit_log, validate_invoice
from app.workflow.approval_service import approve_invoice
from app.workflow.invoice_pipeline import (
    extract_invoice_fields,
    extract_text,
    persist_extracted_invoice,
    validate_relationships,
)

AUTO_APPROVE_CONFIDENCE_THRESHOLD = 0.85


class InvoiceGraphState(TypedDict, total=False):
    db: Session
    file_path: str
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


def _log(state: InvoiceGraphState, message: str) -> None:
    state.setdefault("audit_trail", []).append(
        f"[{datetime.now(timezone.utc).isoformat()}] {message}"
    )


def ingest_invoice(state: InvoiceGraphState) -> InvoiceGraphState:
    state["raw_text"] = extract_text(state["file_path"])
    print("raw_text ======>:", state["raw_text"])
    _log(state, "Invoice document ingested.")
    return state


def extract_with_groq(state: InvoiceGraphState) -> InvoiceGraphState:
    extracted, confidence = extract_invoice_fields(state["raw_text"])
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
    transient = Invoice(
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
    invoice = persist_extracted_invoice(
        state["db"],
        matter_id=state["matter_id"],
        firm_id=state["firm_id"],
        fields=state["extracted"],
        confidence=state["confidence_score"],
    )
    result = state["validation"]
    invoice.budget_valid = result["budget_ok"]
    invoice.duplicate_flag = result["duplicate"]
    invoice.validation_status = "passed" if result["validation_passed"] else "failed"
    invoice.validation_message = "; ".join(result["reasons"])
    state["invoice_id"] = invoice.invoice_id
    state["db"].flush()
    _log(state, f"Invoice persisted with id={invoice.invoice_id} and {len(invoice.line_items)} line items.")
    return state


def route_decision(state: InvoiceGraphState) -> str:
    return state["route"]


def auto_approve(state: InvoiceGraphState) -> InvoiceGraphState:
    invoice = state["db"].get(Invoice, state["invoice_id"])
    if invoice is None:
        raise ValueError("Persisted invoice could not be loaded.")
    invoice.status = "pending_review"
    state["db"].flush()
    approve_invoice(
        db=state["db"],
        invoice=invoice,
        user_id=None,
        notes="Automatically approved by LangGraph after validation.",
    )
    state["final_status"] = "approved"
    _log(state, "Invoice auto-approved and budget workflow completed.")
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
    invoice = state["db"].get(Invoice, state["invoice_id"])
    if invoice is None:
        raise ValueError("Persisted invoice could not be loaded.")
    invoice.status = "pending_review"
    add_audit_log(
        state["db"],
        action="validated",
        invoice_id=invoice.invoice_id,
        notes=invoice.validation_message,
    )
    state["db"].commit()
    state["final_status"] = "pending_review"
    _log(state, "Invoice sent to human review.")
    return state


def log_for_review(state: InvoiceGraphState) -> InvoiceGraphState:
    _log(state, "Human-review queue entry recorded through invoice status/audit log.")
    return state


def build_invoice_graph():
    graph = StateGraph(InvoiceGraphState)
    graph.add_node("ingest_invoice", ingest_invoice)
    graph.add_node("extract_with_groq", extract_with_groq)
    graph.add_node("validate", validate)
    graph.add_node("persist_invoice", persist_invoice)
    graph.add_node("auto_approve", auto_approve)
    graph.add_node("update_budget_and_alerts", update_budget_and_alerts)
    graph.add_node("notify_report", notify_report)
    graph.add_node("human_review", human_review)
    graph.add_node("log_for_review", log_for_review)

    graph.add_edge(START, "ingest_invoice")
    graph.add_edge("ingest_invoice", "extract_with_groq")
    graph.add_edge("extract_with_groq", "validate")
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
    matter_id: int = None,
    firm_id: int = None,
) -> InvoiceGraphState:
    graph = build_invoice_graph()
    return graph.invoke(
        {
            "db": db,
            "file_path": file_path,
            "matter_id": matter_id,
            "firm_id": firm_id,
            "audit_trail": [],
        }
    )


def draw_graph():
    png_bytes = build_invoice_graph().get_graph().draw_mermaid_png()
    
    with open("graph_diagram.png", "wb") as f:
        f.write(png_bytes)

def call_run_invoice_graph():

    from app.database.database import SessionLocal
    from app.models.matter import Matter
    from app.models.firm import Firm

    matter = Matter(
            firm_id=1,
            name="Firm 1 Matter",
            owner="Owner 1",
            status="open",
        )
    firm = Firm(
            firm_id=1,
            name="Sample Outside Counsel LLP",
            contact_email="contact@samplefirm.com",
            status="active",
        )

    
    
    db = SessionLocal()
    # db.add(matter)
    # db.add(firm)

    # db.commit()

    state = run_invoice_graph(
        db, 
        file_path=r"C:\Users\RAJAT-BOMBALE\capstone\Legal-invoice-platform-Agent\legal_docs\test_invoice.pdf", 
        matter_id=1, 
        firm_id=1
    )
    print(state)

if __name__ == "__main__":
    call_run_invoice_graph()