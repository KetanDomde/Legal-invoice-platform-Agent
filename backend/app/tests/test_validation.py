def test_validate_invoice(db):
    from app.models.matter import Matter
    from app.models.budget import Budget
    from app.validation.validation_service import validate_invoice
    # Create a matter
    matter = Matter(
        firm_id=1,
        name="Test Matter",
        owner="Test Owner",
        status="open",
    )

    db.add(matter)
    db.flush()

    # Create a budget for the matter
    budget = Budget(
        matter_id=matter.matter_id,
        allocated_amt=10000.00,
        threshold_pct=80,
    )

    db.add(budget)
    db.flush()

    # Validate invoice
    result = validate_invoice(
        db=db,
        matter_id=matter.matter_id,
        firm_id=1,
        invoice_no="INV-001",
        total_amount=5000,
    )

    assert result is not None
    assert result["budget_ok"] is True
    assert result["remaining_budget"] == 10000.00
    assert result["duplicate"] is False
    assert result["validation_passed"] is True