"""
Tests for extract_text_from_pdf and extract_with_groq_call — the two
functions from Bhushan's original task assignment. Covers every case
manually verified over the course of building this, so it stays
regression-tested instead of "verified once, trust forever."
"""
from app.workflows.legal_invoice_platform_agent import (
    extract_text_from_pdf,
    extract_with_groq_call,
    extract_invoice_fields_mock,
)


class TestExtractTextFromPdf:
    def test_native_pdf_extracts_real_content(self, sample_native_pdf):
        text = extract_text_from_pdf(sample_native_pdf)
        assert "INV-1001" in text
        assert "J. Smith" in text
        assert "4200" in text or "4,200" in text

    def test_scanned_pdf_falls_back_to_ocr(self, sample_scanned_pdf):
        """The scanned sample has NO text layer at all — if this passes,
        OCR genuinely ran, not native extraction."""
        text = extract_text_from_pdf(sample_scanned_pdf)
        assert "INV-1001" in text
        assert "Smith" in text  # OCR is not always pixel-perfect on punctuation/spacing

    def test_missing_file_returns_empty_string_not_fake_data(self):
        """Per FR-8: a malformed/unreadable PDF must be flagged for human
        review, not silently papered over with invented placeholder text."""
        text = extract_text_from_pdf("does_not_exist_anywhere.pdf")
        assert text == ""

    def test_non_pdf_extension_reads_as_plain_text(self, tmp_path):
        txt_file = tmp_path / "sample.txt"
        txt_file.write_text("Invoice No: INV-9999\nDate: 2026-01-01\nTotal: $100.00")
        text = extract_text_from_pdf(str(txt_file))
        assert "INV-9999" in text


    def test_normalizer_preserves_null_timekeeper_for_expenses(self, monkeypatch):
        """Direct test of the normalizer bug: previously `li.get("timekeeper")
        or "UNKNOWN"` silently replaced None with "UNKNOWN" even when the
        model correctly returned null."""
        from app.workflows.legal_invoice_platform_agent import _normalize_extracted_fields

        raw = {
            "invoice_no": "INV-1001",
            "invoice_date": "2026-08-07",
            "total_amount": 4200.0,
            "line_items": [
                {"line_type": "fee", "timekeeper": "J. Smith", "hours": 4.5, "rate": 450.0, "amount": 2025.0},
                {"line_type": "expense", "timekeeper": None, "amount": 150.0, "description": "Filing Fee"},
            ],
        }
        fields = _normalize_extracted_fields(raw)
        fee_line = fields["line_items"][0]
        expense_line = fields["line_items"][1]

        assert fee_line["line_type"] == "fee"
        assert fee_line["timekeeper"] == "J. Smith"

        assert expense_line["line_type"] == "expense"
        assert expense_line["timekeeper"] is None  # NOT "UNKNOWN" — this is the actual regression check
        assert expense_line["description"] == "Filing Fee"

    def test_normalizer_infers_line_type_when_model_omits_it(self):
        """If a model response doesn't include line_type at all (schema
        drift, older cached response, etc.), infer it from timekeeper
        presence rather than defaulting everything to "fee"."""
        from app.workflows.legal_invoice_platform_agent import _normalize_extracted_fields

        raw = {
            "invoice_no": "INV-1001",
            "invoice_date": "2026-08-07",
            "total_amount": 100.0,
            "line_items": [
                {"timekeeper": "A. Lee", "hours": 1.0, "rate": 100.0, "amount": 100.0},  # no line_type key at all
                {"timekeeper": None, "amount": 50.0, "description": "Courier"},          # no line_type key at all
            ],
        }
        fields = _normalize_extracted_fields(raw)
        assert fields["line_items"][0]["line_type"] == "fee"
        assert fields["line_items"][1]["line_type"] == "expense"


class TestExtractWithGroqCall:
    def test_empty_text_returns_zero_confidence(self):
        """Empty raw_text (extraction totally failed upstream) must route
        to human_review — confidence 0.0 guarantees that via the router's
        threshold check, without ever calling the Groq API."""
        fields, confidence = extract_with_groq_call("")
        assert confidence == 0.0
        assert fields["invoice_no"] == "UNKNOWN"
        assert fields["line_items"] == []

    def test_whitespace_only_text_also_returns_zero_confidence(self):
        fields, confidence = extract_with_groq_call("   \n\n   ")
        assert confidence == 0.0

    def test_no_api_key_uses_deterministic_mock(self, monkeypatch):
        """With GROQ_API_KEY unset/placeholder, must never attempt a real
        API call — falls back to the regex-based mock instead."""
        monkeypatch.setenv("GROQ_API_KEY", "your_groq_api_key_here")
        raw_text = (
            "Invoice No: INV-2002\nDate: 2026-05-01\n"
            "Total: $500.00"
        )
        fields, confidence = extract_with_groq_call(raw_text)
        assert fields["invoice_no"] == "INV-2002"
        assert fields["total_amount"] == 500.0
        assert confidence == 0.60  # deliberately below auto-approve threshold

    def test_mock_populates_line_items_from_dash_format(self):
        """This was a TODO left in the original stub (mock always
        returned line_items=[]) — confirms it's actually fixed now."""
        raw_text = (
            "Invoice No: INV-1001\nDate: 2026-08-07\n"
            "Line items:\n"
            "- J. Smith, Partner, 4.5 hrs @ $450/hr = $2025.00\n"
            "- A. Lee, Associate, 6.0 hrs @ $250/hr = $1500.00\n"
            "Total: $3525.00"
        )
        fields = extract_invoice_fields_mock(raw_text)
        assert len(fields["line_items"]) == 2
        assert fields["line_items"][0]["timekeeper"] == "J. Smith"
        assert fields["line_items"][0]["hours"] == 4.5
        assert fields["line_items"][0]["rate"] == 450.0
        assert fields["line_items"][0]["amount"] == 2025.0

    def test_mock_line_items_sum_matches_total(self):
        """Sanity check on the mock's own regex output — not a Groq
        accuracy test, just confirms the mock's fixture text is internally
        consistent (useful as a canary if someone edits the regex)."""
        raw_text = (
            "Invoice No: INV-1001\nDate: 2026-08-07\n"
            "Line items:\n"
            "- J. Smith, Partner, 4.5 hrs @ $450/hr = $2025.00\n"
            "- A. Lee, Associate, 6.0 hrs @ $250/hr = $1500.00\n"
            "Total: $3525.00"
        )
        fields = extract_invoice_fields_mock(raw_text)
        line_sum = sum(li["amount"] for li in fields["line_items"])
        assert line_sum == fields["total_amount"]

    def test_real_pdf_through_mock_extracts_top_level_fields(self, sample_native_pdf):
        """End-to-end: real PDF -> real extraction -> mock field parsing
        (no API key needed for this test to be deterministic in CI)."""
        raw_text = extract_text_from_pdf(sample_native_pdf)
        fields, confidence = extract_with_groq_call(raw_text)
        assert fields["invoice_no"] == "INV-1001"
        assert fields["total_amount"] == 4200.0
        assert confidence == 0.60


class TestGroqRetryBackoff:
    """
    The retry/backoff path (Architecture Doc NFR: "must retry with
    backoff on rate-limit/transient errors rather than crash the
    pipeline") had never actually been exercised — only reasoned
    through. No live Groq account needed here: a fake client simulates
    transient failures so this is deterministic and fast in CI.
    """

    def _fake_response(self, content: str):
        from unittest.mock import MagicMock
        resp = MagicMock()
        resp.choices = [MagicMock(message=MagicMock(content=content))]
        return resp

    def test_retries_then_succeeds_after_transient_failures(self, monkeypatch):
        from unittest.mock import MagicMock
        import time as time_module
        import groq
        import app.workflows.legal_invoice_platform_agent as wf

        monkeypatch.setenv("GROQ_API_KEY", "fake-real-looking-key-not-the-placeholder")
        sleep_calls = []
        monkeypatch.setattr(time_module, "sleep", lambda seconds: sleep_calls.append(seconds))

        good_json = (
            '{"invoice_no": "INV-RETRY", "invoice_date": "2026-01-01", '
            '"total_amount": 100.0, "line_items": [], "confidence": 0.9}'
        )
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = [
            RuntimeError("simulated transient error #1 (e.g. rate limit)"),
            RuntimeError("simulated transient error #2"),
            self._fake_response(good_json),
        ]
        monkeypatch.setattr(groq, "Groq", lambda api_key=None: fake_client)

        fields, confidence = wf.extract_with_groq_call("some real invoice text, long enough to look real")

        assert fake_client.chat.completions.create.call_count == 3, "should fail twice, succeed on the 3rd attempt"
        assert fields["invoice_no"] == "INV-RETRY"
        assert confidence > 0  # blended model confidence (0.9) + completeness heuristic
        # Confirms it's actually backing off, not busy-looping — two sleeps
        # (before attempt 2 and attempt 3), second longer than the first.
        assert len(sleep_calls) == 2
        assert sleep_calls[1] > sleep_calls[0]

    def test_falls_back_to_mock_after_all_retries_exhausted(self, monkeypatch):
        from unittest.mock import MagicMock
        import time as time_module
        import groq
        import app.workflows.legal_invoice_platform_agent as wf

        monkeypatch.setenv("GROQ_API_KEY", "fake-real-looking-key-not-the-placeholder")
        monkeypatch.setattr(time_module, "sleep", lambda seconds: None)

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError("Groq is down")
        monkeypatch.setattr(groq, "Groq", lambda api_key=None: fake_client)

        raw_text = "Invoice No: INV-9001\nDate: 2026-01-01\nTotal: $999.00"
        fields, confidence = wf.extract_with_groq_call(raw_text)

        # Exactly GROQ_MAX_RETRIES attempts — not more (no infinite retry),
        # not fewer (didn't give up early).
        assert fake_client.chat.completions.create.call_count == wf.GROQ_MAX_RETRIES
        # Degrades to the mock extractor rather than raising/crashing the pipeline.
        assert fields["invoice_no"] == "INV-9001"
        assert confidence == 0.5  # the "gave up, degraded" confidence value, distinct from the no-key mock's 0.60