"""
End-to-end tests: the full LangGraph pipeline, ingest -> extract ->
validate -> route -> persist, run via run_pipeline() exactly as both the
CLI and the FastAPI endpoint call it.

REDESIGNED: run_pipeline() now accepts only matter_id and a file path;
the backend generates a numeric invoice_id and returns it in the final
state.
"""
import uuid

import pytest

from app.database.invoice_repository import InvoiceAlreadyExistsError
from app.models.invoice import Invoice
from app.workflows.legal_invoice_platform_agent import run_pipeline


def _unique_matter_id(prefix="M-TEST"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestFullPipeline:
    def test_native_pdf_persists_a_real_invoice(self, sample_native_pdf, db_session):
        matter_id = _unique_matter_id()
        result = run_pipeline(sample_native_pdf, matter_id, firm_id=1)

        assert isinstance(result["invoice_id"], int)
        assert result["final_status"] in ("approved", "pending_review")

        invoice = db_session.query(Invoice).filter(Invoice.invoice_id == result["invoice_id"]).first()
        assert invoice is not None
        assert invoice.invoice_no == "INV-1001"

    def test_scanned_pdf_persists_a_real_invoice(self, sample_scanned_pdf, db_session):
        matter_id = _unique_matter_id()
        result = run_pipeline(sample_scanned_pdf, matter_id, firm_id=1)
        assert isinstance(result["invoice_id"], int)
        invoice = db_session.query(Invoice).filter(Invoice.invoice_id == result["invoice_id"]).first()
        assert invoice is not None

    def test_missing_file_does_not_crash_and_routes_to_review(self):
        matter_id = _unique_matter_id()
        result = run_pipeline("does_not_exist.pdf", matter_id, firm_id=1)
        assert result["final_status"] == "pending_review"
        assert result["confidence_score"] == 0.0
        assert isinstance(result["invoice_id"], int)

    def test_audit_trail_is_populated(self, sample_native_pdf):
        result = run_pipeline(sample_native_pdf, _unique_matter_id(), firm_id=1)
        assert len(result["audit_trail"]) >= 4
        assert any("ingest_invoice" in line for line in result["audit_trail"])
        assert any("extract_with_groq" in line for line in result["audit_trail"])

    def test_billing_period_is_extracted_and_persisted(self, sample_native_pdf, db_session):
        matter_id = _unique_matter_id()
        result = run_pipeline(sample_native_pdf, matter_id, firm_id=1)
        invoice = db_session.query(Invoice).filter(Invoice.invoice_id == result["invoice_id"]).first()
        assert hasattr(invoice, "billing_period_start")
        assert hasattr(invoice, "billing_period_end")

    def test_same_invoice_no_and_matter_submitted_twice_raises(self, sample_native_pdf):
        matter_id = _unique_matter_id()
        first = run_pipeline(sample_native_pdf, matter_id, firm_id=1)
        assert isinstance(first["invoice_id"], int)

        with pytest.raises(InvoiceAlreadyExistsError):
            run_pipeline(sample_native_pdf, matter_id, firm_id=1)
