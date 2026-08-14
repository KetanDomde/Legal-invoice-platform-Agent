"""
Quick manual smoke-test entry point for the LangGraph pipeline, bypassing
the FastAPI layer entirely.

Was previously calling call_run_invoice_graph() with no arguments, but
that function requires (filepath, matter_id) — this has never actually
run successfully. Defaults below point at the sample native-text PDF and
matter_id=1, which matches app/database/seed_matter_budget.py's seeded
Matter row, so `python run_graph.py` works out of the box after seeding.
Override via CLI args for a different file/matter: `python run_graph.py <path> <matter_id>`.
"""
import sys
from pathlib import Path

from app.workflow.graph import call_run_invoice_graph

DEFAULT_FILE = Path(__file__).resolve().parent / "test_invoices" / "sample_invoice_native.pdf"
DEFAULT_MATTER_ID = 1

if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_FILE)
    matter_id = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MATTER_ID
    call_run_invoice_graph(filepath, matter_id)
