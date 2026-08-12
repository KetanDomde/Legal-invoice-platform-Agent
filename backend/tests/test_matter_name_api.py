from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def setup_module(module):
    # Ensure the test DB has a couple of invoices with matter_name filled
    from app.database.database import SessionLocal
    from app.models.invoice import Invoice

    session = SessionLocal()
    try:
        session.query(Invoice).delete()
        session.add_all([
            Invoice(matter_id="MAT-771B", matter_name="Nova Retail v. Green Market", invoice_no="HBR-A24-0098", total_amount=100.0, status="pending_review", confidence_score=0.5),
            Invoice(matter_id="MAT-TEST", matter_name="Nova Retail v. Green Market", invoice_no="HBR-A24-0098", total_amount=100.0, status="approved", confidence_score=0.88),
        ])
        session.commit()
    finally:
        session.close()


def test_invoice_matter_name_present_by_id():
    resp = client.get("/invoices/1")
    assert resp.status_code == 200
    data = resp.json()
    assert "matter_name" in data and data["matter_name"], f"matter_name missing for invoice 1: {data}"


def test_list_invoices_have_matter_name():
    resp = client.get("/invoices")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(inv.get("matter_name") for inv in data), "No invoices with matter_name in list"
