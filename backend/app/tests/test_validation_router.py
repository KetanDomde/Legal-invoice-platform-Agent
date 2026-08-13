from app.validation.router import (
    route_invoice,
)


def test_valid_invoice_is_auto_approved():

    result = route_invoice(
        confidence_score=0.95,
        budget_valid=True,
        duplicate_flag=False,
    )

    assert result.decision == "auto_approved"

    assert (
        "All validation checks passed"
        in result.reasons
    )


def test_low_confidence_goes_to_review():

    result = route_invoice(
        confidence_score=0.60,
        budget_valid=True,
        duplicate_flag=False,
    )

    assert result.decision == "pending_review"

    assert (
        "Extraction confidence is below threshold"
        in result.reasons
    )


def test_budget_failure_goes_to_review():

    result = route_invoice(
        confidence_score=0.95,
        budget_valid=False,
        duplicate_flag=False,
    )

    assert result.decision == "pending_review"


def test_duplicate_goes_to_review():

    result = route_invoice(
        confidence_score=0.95,
        budget_valid=True,
        duplicate_flag=True,
    )

    assert result.decision == "pending_review"


def test_multiple_failures_go_to_review():

    result = route_invoice(
        confidence_score=0.50,
        budget_valid=False,
        duplicate_flag=True,
    )

    assert result.decision == "pending_review"

    assert len(result.reasons) == 3