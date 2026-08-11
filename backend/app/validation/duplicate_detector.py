from sqlalchemy.orm import Session

from app.models.invoice import Invoice


def find_duplicate_invoice(
    db: Session,
    firm_id: int,
    invoice_no: str,
    total_amount: float,
    exclude_invoice_id: int | None = None,
):
    
    """
    Find an existing invoice with the same:
        firm_id
        invoice_no
        total_amount
    This follows FR-10.
    
    """

    query = (
        db.query(Invoice)
        .filter(
            Invoice.firm_id == firm_id,
            Invoice.invoice_no == invoice_no,
            Invoice.total_amount == total_amount,
        )
    )

    if exclude_invoice_id is not None:
        query = query.filter(
            Invoice.invoice_id != exclude_invoice_id
        )

    return query.first()


# def check_duplicate(
#     db: Session,
#     firm_id: int,
#     invoice_no: str,
#     total_amount: float,
#     exclude_invoice_id: int | None = None,
# ) -> dict:
#     """
#     Return duplicate detection result.
#     """

#     duplicate = find_duplicate_invoice(
#         db=db,
#         firm_id=firm_id,
#         invoice_no=invoice_no,
#         total_amount=total_amount,
#         exclude_invoice_id=exclude_invoice_id,
#     )

#     if duplicate:

#         return {
#             "duplicate": True,
#             "duplicate_invoice_id": duplicate.invoice_id,
#             "reason": (
#                 "Duplicate invoice detected: "
#                 "same firm, invoice number and amount."
#             ),
#         }

#     return {
#         "duplicate": False,
#         "duplicate_invoice_id": None,
#         "reason": "No duplicate invoice found.",
#     }



def check_duplicate(
    db: Session,
    firm_id: int,
    invoice_no: str,
    total_amount: float,
    exclude_invoice_id: int | None = None,
) -> dict:
    """
    Check whether an invoice with the same invoice number and amount
    already exists for this firm.

    A duplicate is defined as: same firm_id + same invoice_no + same
    total_amount. Matching on amount too avoids false positives when
    invoice numbers get legitimately reused (e.g. after a correction).
    """

    query = db.query(Invoice).filter(
        Invoice.firm_id == firm_id,
        Invoice.invoice_no == invoice_no,
        Invoice.total_amount == total_amount,
    )

    if exclude_invoice_id is not None:
        query = query.filter(Invoice.invoice_id != exclude_invoice_id)

    existing = query.first()

    if existing:
        return {
            "duplicate": True,
            "duplicate_invoice_id": existing.invoice_id,
            "reason": (
                f"Duplicate invoice detected: invoice_no '{invoice_no}' "
                f"for amount {total_amount} already exists "
                f"(invoice_id={existing.invoice_id})"
            ),
        }

    return {
        "duplicate": False,
        "duplicate_invoice_id": None,
        "reason": None,
    }