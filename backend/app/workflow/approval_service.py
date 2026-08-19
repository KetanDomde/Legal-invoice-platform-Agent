# from __future__ import annotations

# from sqlalchemy.orm import Session

# from app.models import Invoice
# from app.services.invoice import add_audit_log, get_budget_summary


# def post_approved_invoice_to_budget(db: Session, invoice: Invoice) -> dict:
#     """Post an approved invoice to the budget ledger.

#     Kept in the approval workflow so approval has one clear integration point.
#     The function is intentionally safe when a matter has no configured budget.
#     """
#     from app.models import Budget, BudgetLedger

#     budget = (
#         db.query(Budget)
#         .filter(Budget.matter_id == invoice.matter_id)
#         .first()
#     )
#     if budget is None:
#         return {
#             "invoice_id": invoice.invoice_id,
#             "amount_posted": invoice.total_amount,
#             "status": "no_budget_configured",
#         }

#     existing = (
#         db.query(BudgetLedger)
#         .filter(
#             BudgetLedger.invoice_id == invoice.invoice_id,
#             BudgetLedger.entry_type == "invoice_approved",
#         )
#         .first()
#     )
#     if existing is None:
#         db.add(
#             BudgetLedger(
#                 budget_id=budget.budget_id,
#                 invoice_id=invoice.invoice_id,
#                 amount=invoice.total_amount,
#                 entry_type="invoice_approved",
#             )
#         )

#     return {
#         "invoice_id": invoice.invoice_id,
#         "amount_posted": invoice.total_amount,
#         "status": "posted",
#     }


# def approve_invoice(
#     db: Session,
#     invoice: Invoice,
#     user_id: int | None = None,
#     notes: str | None = None,
# ) -> Invoice:
#     """Approve a pending-review invoice and post it to the budget."""
#     if invoice.status != "pending_review":
#         raise ValueError("Only invoices pending review can be approved.")

#     # This symbol is deliberately called through this module so existing
#     # integrations/tests can replace the budget-posting step safely.
#     budget_result = post_approved_invoice_to_budget(db=db, invoice=invoice)

#     old_status = invoice.status
#     invoice.status = "approved"
#     db.add(invoice)

#     audit_note = (
#         f"Status changed from '{old_status}' to 'approved'."
#     )
#     if notes:
#         audit_note += f" Reason: {notes}"
#     if budget_result.get("status"):
#         audit_note += f" Budget: {budget_result['status']}."

#     add_audit_log(
#         db,
#         action="approved",
#         user_id=user_id,
#         invoice_id=invoice.invoice_id,
#         notes=audit_note,
#     )
#     db.commit()
#     db.refresh(invoice)
#     return invoice


from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Invoice
from app.services.invoice import add_audit_log


def post_approved_invoice_to_budget(
    db: Session,
    invoice: Invoice,
) -> dict:

    from app.models import Budget, BudgetLedger

    budget = (
        db.query(Budget)
        .filter(
            Budget.matter_id == invoice.matter_id
        )
        .first()
    )

    if budget is None:
        return {
            "invoice_id": invoice.invoice_id,
            "amount_posted": invoice.total_amount,
            "status": "no_budget_configured",
        }

    existing = (
        db.query(BudgetLedger)
        .filter(
            BudgetLedger.invoice_id
            == invoice.invoice_id,
            BudgetLedger.entry_type
            == "invoice_approved",
        )
        .first()
    )

    if existing is None:

        db.add(
            BudgetLedger(
                budget_id=budget.budget_id,
                invoice_id=invoice.invoice_id,
                amount=invoice.total_amount,
                entry_type="invoice_approved",
            )
        )

    return {
        "invoice_id": invoice.invoice_id,
        "amount_posted": invoice.total_amount,
        "status": "posted",
    }


def auto_approve_invoice(
    db: Session,
    invoice: Invoice,
) -> Invoice:
    """
    System-generated approval.

    Used only when the LangGraph validation rules
    have determined that the invoice qualifies
    for automatic approval.
    """

    if invoice.status != "submitted":
        raise ValueError(
            "Only submitted invoices can be auto-approved."
        )

    budget_result = post_approved_invoice_to_budget(
        db=db,
        invoice=invoice,
    )

    old_status = invoice.status

    invoice.status = "approved"

    db.add(invoice)

    note = (
        f"Status changed from '{old_status}' "
        f"to 'approved' automatically. "
        f"Budget: {budget_result['status']}."
    )

    add_audit_log(
        db=db,
        action="auto_approved",
        user_id=-1,
        invoice_id=invoice.invoice_id,
        notes=note,
    )

    db.commit()
    db.refresh(invoice)

    return invoice


def approve_invoice(
    db: Session,
    invoice: Invoice,
    user_id: int | None = None,
    notes: str | None = None,
) -> Invoice:

    if invoice.status != "pending_review":
        raise ValueError(
            "Only invoices pending review can be approved."
        )

    budget_result = post_approved_invoice_to_budget(
        db=db,
        invoice=invoice,
    )

    old_status = invoice.status

    invoice.status = "approved"

    db.add(invoice)

    audit_note = (
        f"Status changed from '{old_status}' "
        f"to 'approved'."
    )

    if notes:
        audit_note += f" Reason: {notes}"

    audit_note += (
        f" Budget: {budget_result['status']}."
    )

    add_audit_log(
        db=db,
        action="approved",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=audit_note,
    )

    db.commit()
    db.refresh(invoice)

    return invoice