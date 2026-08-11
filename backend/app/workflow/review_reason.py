def build_review_reasons(invoice):

    reasons = []

    if invoice.confidence_score is not None:
        if invoice.confidence_score < 0.85:
            reasons.append(
                "Extraction confidence is below threshold"
            )

    if invoice.budget_valid is False:
        reasons.append(
            "Invoice failed budget validation"
        )

    if invoice.duplicate_flag:
        reasons.append(
            "Possible duplicate invoice detected"
        )

    if not reasons:
        reasons.append(
            "Invoice requires manual review"
        )

    return reasons