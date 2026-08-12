"""Backfill missing `matter_name` on invoices by re-running the extractor
against files in `backend/uploaded_invoices/`.

Run with: PYTHONPATH=backend python backend/scripts/backfill_matter_name.py
"""
from pathlib import Path
from sqlalchemy import create_engine, text

from app.database.database import RESOLVED_DATABASE_URL
from app.workflows.legal_invoice_platform_agent import extract_text_from_pdf, extract_invoice_fields_mock


UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploaded_invoices"


def main() -> None:
    print("Backfill: DB=", RESOLVED_DATABASE_URL)
    engine = create_engine(RESOLVED_DATABASE_URL, connect_args={"check_same_thread": False})

    # Build a lookup of invoice_no -> list of (matter_id, matter_name) seen in files
    lookup = {}
    if UPLOAD_DIR.exists():
        for p in sorted(UPLOAD_DIR.iterdir()):
            if not p.is_file():
                continue
            raw = extract_text_from_pdf(str(p))
            extracted = extract_invoice_fields_mock(raw)
            inv_no = extracted.get("invoice_no")
            matter_name = extracted.get("matter_name")
            # try to pick up a matter id printed on the file too
            matter_id = None
            if raw:
                m = None
                import re

                m = re.search(r"Matter[:]?\s*([A-Za-z0-9-]+)", raw)
                if m:
                    matter_id = m.group(1)

            if not inv_no:
                continue
            key = inv_no
            lookup.setdefault(key, []).append((matter_id, matter_name, str(p)))

    updated = 0
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT invoice_id, invoice_no, matter_id FROM invoices WHERE matter_name IS NULL OR matter_name=''")).all()
        print(f"Found {len(rows)} invoices missing matter_name")
        for invoice_id, invoice_no, invoice_matter_id in rows:
            candidates = lookup.get(invoice_no) or []
            chosen = None
            # Prefer candidate where matter_id matches
            for mid, mname, path in candidates:
                if mid and invoice_matter_id and mid == invoice_matter_id and mname:
                    chosen = mname
                    break
            if not chosen:
                # Fall back to first non-null matter_name
                for mid, mname, path in candidates:
                    if mname:
                        chosen = mname
                        break

            if chosen:
                conn.execute(text("UPDATE invoices SET matter_name = :mname WHERE invoice_id = :iid"), {"mname": chosen, "iid": invoice_id})
                print(f"Updated invoice_id={invoice_id} invoice_no={invoice_no} -> matter_name={chosen}")
                updated += 1

    print(f"Backfill complete: {updated} rows updated")


if __name__ == "__main__":
    main()
