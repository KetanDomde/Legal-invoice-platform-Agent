from datetime import date


def test_review_queue_only_returns_same_firm(db):
    from app.models.matter import Matter
    from app.models.invoice import Invoice
    from app.workflow.review_queue import get_review_queue

    # Create matters for each firm
    matter_1 = Matter(
        firm_id=1,
        name="Firm 1 Matter",
        owner="Owner 1",
        status="open",
    )

    matter_2 = Matter(
        firm_id=2,
        name="Firm 2 Matter",
        owner="Owner 2",
        status="open",
    )

    db.add_all([matter_1, matter_2])
    db.flush()

    # Create invoices linked to their respective matters
    invoice_1 = Invoice(
        firm_id=1,
        matter_id=matter_1.matter_id,
        status="pending_review",
        invoice_no="FIRM1-001",
        invoice_date=date(2026, 8, 1),
        total_amount=1000.00,

    )

    invoice_2 = Invoice(
        firm_id=2,
        matter_id=matter_2.matter_id,
        status="pending_review",
        invoice_no="FIRM2-001",
        invoice_date=date(2026, 8, 1),
        total_amount=2000.00,
    )

    db.add_all([invoice_1, invoice_2])
    db.commit()

    results = get_review_queue(
        db=db,
        firm_id=1,
    )

    assert all(
    invoice["firm_id"] == 1
    for invoice in results
)
    