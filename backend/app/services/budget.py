from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Alert, Budget, BudgetLedger, Invoice, Matter


# The ledger is the single financial source of truth for budget utilization.
APPROVED_ENTRY_TYPE = "invoice_approved"


def _calculate_summary(db: Session, budget: Budget) -> dict:
    """
    Calculate the current budget position from BudgetLedger.

    IMPORTANT:
    We intentionally do NOT calculate utilization from Invoice.status.
    Every part of the application should use the approved ledger entries
    as the financial source of truth.
    """

    utilized = (
        db.query(func.coalesce(func.sum(BudgetLedger.amount), 0))
        .filter(
            BudgetLedger.budget_id == budget.budget_id,
            BudgetLedger.entry_type == APPROVED_ENTRY_TYPE,
        )
        .scalar()
    )

    utilized = float(utilized or 0)
    allocated = float(budget.allocated_amt or 0)
    remaining = allocated - utilized
    pct_used = (utilized / allocated * 100) if allocated > 0 else 0.0

    return {
        "has_budget": True,
        "budget_id": budget.budget_id,
        "matter_id": budget.matter_id,
        "allocated": allocated,
        "utilized": utilized,
        "remaining": remaining,
        "pct_used": pct_used,
        "threshold_pct": float(budget.threshold_pct or 0),
        "threshold_reached": pct_used >= float(budget.threshold_pct or 0),
        "over_budget": utilized > allocated,
    }


def get_budget_summary(db: Session, matter_id: int) -> dict:
    """
    Return the canonical budget summary for one matter.

    A missing budget is represented explicitly instead of silently being
    treated as budget-valid.
    """

    budget = (
        db.query(Budget)
        .filter(Budget.matter_id == matter_id)
        .first()
    )

    if budget is None:
        return {
            "has_budget": False,
            "budget_id": None,
            "matter_id": matter_id,
            "allocated": 0.0,
            "utilized": 0.0,
            "remaining": 0.0,
            "pct_used": 0.0,
            "threshold_pct": 0.0,
            "threshold_reached": False,
            "over_budget": False,
        }

    return _calculate_summary(db, budget)


def get_all_budget_summaries(
    db: Session,
    firm_id: int | None = None,
) -> list[dict]:
    """
    Return canonical summaries for all budgets.

    The frontend uses this instead of calculating SUM(ledger.amount)
    independently on each page.
    """

    query = db.query(Budget).join(Budget.matter)

    if firm_id is not None:
        query = query.filter(Matter.firm_id == firm_id)

    budgets = query.order_by(Budget.budget_id.asc()).all()

    return [_calculate_summary(db, budget) for budget in budgets]


def get_invoice_budget_context(
    db: Session,
    invoice: Invoice,
) -> dict:
    """
    Calculate the budget position if this invoice is approved.

    This is used before approval so the system can determine whether:
      - there is no budget,
      - approval stays within budget,
      - approval exceeds budget and therefore requires a human override.
    """

    summary = get_budget_summary(db, invoice.matter_id)

    if not summary["has_budget"]:
        return {
            **summary,
            "invoice_amount": float(invoice.total_amount or 0),
            "already_posted": False,
            "projected_utilized": 0.0,
            "projected_remaining": 0.0,
            "projected_pct_used": 0.0,
            "projected_over_budget": False,
        }

    existing_entry = (
        db.query(BudgetLedger)
        .filter(
            BudgetLedger.invoice_id == invoice.invoice_id,
            BudgetLedger.entry_type == APPROVED_ENTRY_TYPE,
        )
        .first()
    )

    already_posted = existing_entry is not None
    invoice_amount = float(invoice.total_amount or 0)

    additional_amount = 0.0 if already_posted else invoice_amount
    projected_utilized = summary["utilized"] + additional_amount
    projected_remaining = summary["allocated"] - projected_utilized
    projected_pct_used = (
        projected_utilized / summary["allocated"] * 100
        if summary["allocated"] > 0
        else 0.0
    )

    return {
        **summary,
        "invoice_amount": invoice_amount,
        "already_posted": already_posted,
        "projected_utilized": projected_utilized,
        "projected_remaining": projected_remaining,
        "projected_pct_used": projected_pct_used,
        "projected_over_budget": projected_utilized > summary["allocated"],
    }


def _create_budget_alerts(
    db: Session,
    *,
    budget_id: int,
    matter_id: int,
    invoice_id: int,
    before_summary: dict,
    after_summary: dict,
) -> None:
    """
    Create alerts only when the approval actually crosses an important boundary.

    This prevents every later invoice from creating duplicate threshold alerts
    when a matter is already above the threshold.
    """

    threshold = after_summary["threshold_pct"]
    before_pct = before_summary["pct_used"]
    after_pct = after_summary["pct_used"]

    matter = db.get(Matter, matter_id)
    invoice = db.get(Invoice, invoice_id)
    firm_name = (matter.firm.name if matter is not None and getattr(matter, "firm", None) else f"Firm #{matter.firm_id}" if matter is not None else "Unknown Firm")
    matter_label = (matter.matter_no or str(matter_id)) if matter is not None else str(matter_id)
    matter_name = matter.name if matter is not None else "Unknown matter"
    invoice_no = invoice.invoice_no if invoice is not None and invoice.invoice_no else f"#{invoice_id}"
    alert_prefix = f"Firm: {firm_name} | Matter: {matter_label} — {matter_name} | Invoice: {invoice_no}."

    # Threshold crossing, for example 75% -> 85% with an 80% threshold.
    crossed_threshold = (
        before_pct < threshold <= after_pct
    )

    # Special handling for a threshold of 0%.
    if threshold == 0 and before_summary["utilized"] == 0 and after_summary["utilized"] > 0:
        crossed_threshold = True

    if crossed_threshold:
        existing = (
            db.query(Alert)
            .filter(
                Alert.budget_id == budget_id,
                Alert.invoice_id == invoice_id,
                Alert.type.in_(["budget_threshold", "BUDGET_THRESHOLD_REACHED"]),
            )
            .first()
        )
        if existing is None:
            db.add(
                Alert(
                    budget_id=budget_id,
                    invoice_id=invoice_id,
                    type="budget_threshold",
                    message=(
                        f"{alert_prefix} Budget threshold reached at {after_pct:.1f}% utilization. "
                        f"Configured threshold: {threshold:.1f}%."
                    ),
                )
            )

    # A separate alert is created when an approved override pushes utilization
    # from within budget to above 100%.
    crossed_over_budget = before_pct <= 100 < after_pct

    if crossed_over_budget:
        existing = (
            db.query(Alert)
            .filter(
                Alert.budget_id == budget_id,
                Alert.invoice_id == invoice_id,
                Alert.type.in_(["budget_overrun", "OVER_BUDGET_DETECTED"]),
            )
            .first()
        )
        if existing is None:
            db.add(
                Alert(
                    budget_id=budget_id,
                    invoice_id=invoice_id,
                    type="budget_overrun",
                    message=(
                        f"{alert_prefix} Matter is over budget at {after_pct:.1f}% utilization. "
                        f"Remaining budget: ${after_summary['remaining']:,.2f}."
                    ),
                )
            )


def post_approved_invoice_to_budget(
    db: Session,
    invoice: Invoice,
) -> dict:
    """
    Post an approved invoice to BudgetLedger exactly once.

    This function:
      1. Requires a configured budget.
      2. Prevents duplicate ledger postings for the same invoice.
      3. Flushes the new ledger entry before recalculating utilization.
      4. Creates threshold/overrun alerts when boundaries are crossed.

    The caller controls whether an over-budget invoice is allowed as a
    human-approved override.
    """

    context = get_invoice_budget_context(db, invoice)

    if not context["has_budget"]:
        raise ValueError(
            f"No budget configured for matter_id={invoice.matter_id}. "
            "Configure a budget before approving this invoice."
        )

    if context["already_posted"]:
        return {
            "status": "already_posted",
            "summary": get_budget_summary(db, invoice.matter_id),
            "context": context,
        }

    before_summary = get_budget_summary(db, invoice.matter_id)

    db.add(
        BudgetLedger(
            budget_id=context["budget_id"],
            invoice_id=invoice.invoice_id,
            amount=invoice.total_amount,
            entry_type=APPROVED_ENTRY_TYPE,
        )
    )

    # Make the ledger row visible to the next summary query in this transaction.
    db.flush()

    after_summary = get_budget_summary(db, invoice.matter_id)

    _create_budget_alerts(
        db,
        budget_id=context["budget_id"],
        matter_id=invoice.matter_id,
        invoice_id=invoice.invoice_id,
        before_summary=before_summary,
        after_summary=after_summary,
    )

    return {
        "status": "posted",
        "summary": after_summary,
        "context": context,
    }