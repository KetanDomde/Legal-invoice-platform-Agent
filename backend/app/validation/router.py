CONFIDENCE_THRESHOLD = 0.90

def route_invoice(
    confidence_score: float,
    validation: dict,
) -> str:
    """
    Decide whether an invoice should be
    automatically approved or sent to
    human review.
    """

    budget_ok = validation["budget_ok"]
    duplicate = validation["duplicate"]

    high_confidence = (
        confidence_score >= CONFIDENCE_THRESHOLD
    )

    if (
        high_confidence
        and budget_ok
        and not duplicate
    ):
        return "auto_approve"

    return "human_review"



def make_decision(
    confidence_score: float,
    validation: dict,
) -> dict:
    """
    Produce an explainable routing decision.
    """

    reasons = list(
        validation.get("reasons", [])
    )

    if confidence_score < CONFIDENCE_THRESHOLD:

        reasons.append(
            f"Confidence score "
            f"{confidence_score:.2f} is below "
            f"threshold "
            f"{CONFIDENCE_THRESHOLD:.2f}."
        )

    if not validation["budget_ok"]:

        reasons.append(
            "Invoice exceeds remaining budget."
        )

    if validation["duplicate"]:

        reasons.append(
            "Duplicate invoice detected."
        )

    decision = route_invoice(
        confidence_score=confidence_score,
        validation=validation,
    )

    return {
        "decision": decision,
        "confidence_score": confidence_score,
        "confidence_threshold": (
            CONFIDENCE_THRESHOLD
        ),
        "reasons": reasons,
    }

### code chnage from here 

from dataclasses import dataclass


@dataclass
class RoutingResult:
    decision: str
    reasons: list[str]


AUTO_APPROVE = "auto_approved"
HUMAN_REVIEW = "pending_review"


def route_invoice(
    confidence_score: float | None,
    budget_valid: bool | None,
    duplicate_flag: bool,
) -> RoutingResult:

    reasons = []

    # --------------------------------------------------
    # Confidence check
    # --------------------------------------------------

    if confidence_score is not None:

        if confidence_score < 0.85:
            reasons.append(
                "Extraction confidence is below threshold"
            )

    # --------------------------------------------------
    # Budget check
    # --------------------------------------------------

    if budget_valid is False:
        reasons.append(
            "Invoice failed budget validation"
        )

    # --------------------------------------------------
    # Duplicate check
    # --------------------------------------------------

    if duplicate_flag:
        reasons.append(
            "Possible duplicate invoice detected"
        )

    # --------------------------------------------------
    # Routing decision
    # --------------------------------------------------

    if reasons:

        return RoutingResult(
            decision=HUMAN_REVIEW,
            reasons=reasons,
        )

    return RoutingResult(
        decision=AUTO_APPROVE,
        reasons=[
            "All validation checks passed"
        ],
    )