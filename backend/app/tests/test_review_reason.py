from app.workflow.review_reason import (
    build_review_reasons,
)


def test_low_confidence_reason():

    invoice = type(
        "Invoice",
        (),
        {
            "confidence_score": 0.60,
            "budget_valid": True,
            "duplicate_flag": False,
        },
    )()

    reasons = build_review_reasons(
        invoice
    )

    assert (
        "Extraction confidence is below threshold"
        in reasons
    )


def test_budget_failure_reason():

    invoice = type(
        "Invoice",
        (),
        {
            "confidence_score": 0.95,
            "budget_valid": False,
            "duplicate_flag": False,
        },
    )()

    reasons = build_review_reasons(
        invoice
    )

    assert (
        "Invoice failed budget validation"
        in reasons
    )


def test_duplicate_reason():

    invoice = type(
        "Invoice",
        (),
        {
            "confidence_score": 0.95,
            "budget_valid": True,
            "duplicate_flag": True,
        },
    )()

    reasons = build_review_reasons(
        invoice
    )

    assert (
        "Possible duplicate invoice detected"
        in reasons
    )