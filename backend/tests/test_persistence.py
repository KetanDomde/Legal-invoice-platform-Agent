"""
Tests for the Invoice/LineItem models and the invoice_repository persistence layer.

REDESIGNED: invoice_id is now a system-generated integer primary key.
insert_invoice_with_line_items() creates a new invoice row and returns the
generated integer. Duplicate detection is enforced by invoice_no + matter_id.
"""
import uuid

import pytest

from app.database.invoice_repository import (
    InvoiceAlreadyExistsError,
    InvoiceNotFoundError,
    get_firm_id_for_matter,
    insert_invoice_with_line_items,
    invoice_exists,
    update_invoice_with_line_items,
)
from app.models.invoice import Invoice
from app.models.invoice_item import LineItem


SAMPLE_EXTRACTED = {
    "invoice_no": "INV-1001",
    "invoice_date": "2026-08-07",
    "billing_period_start": "2026-07-01",
    "billing_period_end": "2026-07-31",
    "total_amount": 4200.0,
    "line_items": [
        {"line_type": "fee", "timekeeper": "J. Smith", "role": "Partner", "hours": 4.5, "rate": 450.0, "amount": 2025.0, "description": None},
        {"line_type": "fee", "timekeeper": "A. Lee", "role": "Associate", "hours": 6.0, "rate": 250.0, "amount": 1500.0, "description": None},
        {"line_type": "expense", "timekeeper": None, "role": None, "hours": None, "rate": None, "amount": 150.0, "description": "Filing Fee"},
    ],
}


def _unique_matter_id(prefix="M-PERSIST"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestInvoiceExists:
    def test_no_prior_submission_returns_false(self):
        assert invoice_exists(999999) is False

    def test_existing_invoice_id_is_flagged(self):
        invoice_id = insert_invoice_with_line_items(
            matter_id=_unique_matter_id(),
            firm_id=1,
            extracted=SAMPLE_EXTRACTED,
            confidence_score=0.9,
            status="approved",
        )
        assert invoice_exists(invoice_id) is True

    def test_settings_database_url_is_resolved_to_absolute_path(self):
        from app.core.config import settings
        from app.database.database import engine

        assert settings.DATABASE_URL.startswith("sqlite:///"), "DATABASE_URL must remain a sqlite URL"
        assert settings.DATABASE_URL.count("/") >= 4, "DATABASE_URL should be absolute"
        assert str(engine.url).startswith("sqlite:////"), "Engine URL should use absolute sqlite path"

    def test_settings_database_url_is_resolved_to_absolute_path(self):
        from app.core.config import settings
        from app.database.database import engine

        assert settings.DATABASE_URL.startswith("sqlite:///"), "DATABASE_URL must remain a sqlite URL"
        assert settings.DATABASE_URL.count("/") >= 4, "DATABASE_URL should be absolute"
        assert str(engine.url).startswith("sqlite:////"), "Engine URL should use absolute sqlite path"

    def test_alphanumeric_matter_id_works(self):
        matter_id = f"M-ABC{uuid.uuid4().hex[:6].upper()}"
        invoice_id = insert_invoice_with_line_items(
            matter_id=matter_id,
            firm_id=1,
            extracted=SAMPLE_EXTRACTED,
            confidence_score=0.9,
            status="approved",
        )
        assert isinstance(invoice_id, int)
        assert invoice_exists(invoice_id) is True

    def test_db_error_fails_open_not_closed(self, monkeypatch):
        import app.database.invoice_repository as repo

        class BrokenSessionLocal:
            def __call__(self):
                raise RuntimeError("simulated DB connection failure")

        monkeypatch.setattr(repo, "SessionLocal", BrokenSessionLocal())
        assert repo.invoice_exists(999999) is False


class TestInsertInvoiceWithLineItems:
    def test_insert_and_read_back(self, db_session):
        invoice_id = insert_invoice_with_line_items(
            matter_id=_unique_matter_id(),
            firm_id=1,
            extracted=SAMPLE_EXTRACTED,
            confidence_score=0.95,
            status="approved",
        )
        assert isinstance(invoice_id, int)

        invoice = db_session.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        assert invoice is not None
        assert invoice.invoice_id == invoice_id
        assert invoice.invoice_no == "INV-1001"
        assert invoice.total_amount == 4200.0
        assert invoice.status == "approved"
        assert invoice.billing_period_start == "2026-07-01"
        assert invoice.billing_period_end == "2026-07-31"

        line_items = db_session.query(LineItem).filter(LineItem.invoice_id == invoice_id).all()
        assert len(line_items) == 3
        expense_line = next(li for li in line_items if li.description == "Filing Fee")
        assert expense_line.timekeeper is None

    def test_duplicate_invoice_no_and_matter_raises(self, db_session):
        matter_id = _unique_matter_id()
        insert_invoice_with_line_items(
            matter_id=matter_id,
            firm_id=1,
            extracted=SAMPLE_EXTRACTED,
            confidence_score=0.9,
            status="approved",
        )
        with pytest.raises(InvoiceAlreadyExistsError):
            insert_invoice_with_line_items(
                matter_id=matter_id,
                firm_id=1,
                extracted=SAMPLE_EXTRACTED,
                confidence_score=0.9,
                status="approved",
            )

        count = db_session.query(Invoice).filter(Invoice.invoice_no == "INV-1001", Invoice.matter_id == matter_id).count()
        assert count == 1

    def test_invoice_ids_are_generated_integers(self, db_session):
        first_id = insert_invoice_with_line_items(
            matter_id=_unique_matter_id(),
            firm_id=1,
            extracted=SAMPLE_EXTRACTED,
            confidence_score=0.9,
            status="approved",
        )
        second_id = insert_invoice_with_line_items(
            matter_id=_unique_matter_id(),
            firm_id=1,
            extracted={**SAMPLE_EXTRACTED, "invoice_no": "INV-1002"},
            confidence_score=0.9,
            status="approved",
        )
        assert isinstance(first_id, int)
        assert isinstance(second_id, int)
        assert first_id != second_id

    def test_missing_line_items_does_not_error(self, db_session):
        invoice_id = insert_invoice_with_line_items(
            matter_id=_unique_matter_id(),
            firm_id=1,
            extracted={**SAMPLE_EXTRACTED, "line_items": []},
            confidence_score=0.5,
            status="pending_review",
        )
        items = db_session.query(LineItem).filter(LineItem.invoice_id == invoice_id).all()
        assert items == []


class TestUpdateInvoiceWithLineItems:
    def test_update_existing_invoice_keeps_same_id(self, db_session):
        matter_id = _unique_matter_id()
        invoice_id = insert_invoice_with_line_items(
            matter_id=matter_id,
            firm_id=1,
            extracted=SAMPLE_EXTRACTED,
            confidence_score=0.6,
            status="pending_review",
        )
        updated_extracted = {**SAMPLE_EXTRACTED, "total_amount": 9999.0}
        result_id = update_invoice_with_line_items(
            invoice_id=invoice_id,
            matter_id=matter_id,
            firm_id=1,
            extracted=updated_extracted,
            confidence_score=0.95,
            status="approved",
        )
        assert result_id == invoice_id

        count = db_session.query(Invoice).filter(Invoice.invoice_id == invoice_id).count()
        assert count == 1

        invoice = db_session.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        assert invoice.total_amount == 9999.0
        assert invoice.status == "approved"
        assert invoice.confidence_score == 0.95

    def test_update_replaces_line_items_not_appends(self, db_session):
        matter_id = _unique_matter_id()
        invoice_id = insert_invoice_with_line_items(
            matter_id=matter_id,
            firm_id=1,
            extracted=SAMPLE_EXTRACTED,
            confidence_score=0.6,
            status="pending_review",
        )
        single_item_extracted = {
            **SAMPLE_EXTRACTED,
            "line_items": [{"line_type": "fee", "timekeeper": "New Person", "role": "Partner", "hours": 1.0, "rate": 100.0, "amount": 100.0, "description": None}],
        }
        update_invoice_with_line_items(
            invoice_id=invoice_id,
            matter_id=matter_id,
            firm_id=1,
            extracted=single_item_extracted,
            confidence_score=0.9,
            status="pending_review",
        )
        items = db_session.query(LineItem).filter(LineItem.invoice_id == invoice_id).all()
        assert len(items) == 1
        assert items[0].timekeeper == "New Person"

    def test_update_nonexistent_invoice_raises_not_found(self):
        with pytest.raises(InvoiceNotFoundError):
            update_invoice_with_line_items(
                invoice_id=999999,
                matter_id=_unique_matter_id(),
                firm_id=1,
                extracted=SAMPLE_EXTRACTED,
                confidence_score=0.9,
                status="approved",
            )


class TestGetFirmIdForMatter:
    def test_nonexistent_matter_returns_none_not_error(self):
        assert get_firm_id_for_matter("M-UNKNOWN") is None
