"""
Thin wrapper around the FastAPI backend used by every Streamlit page.

Endpoint shapes here mirror the real backend exactly (backend/app/api/*.py,
backend/app/schemas/*.py) — not a guess. Point API_BASE_URL at the real
server (default http://localhost:8000) once the frontend is wired in for
real; it also works unchanged against the mock preview server.
"""
import requests
import streamlit as st

DEFAULT_BASE_URL = "http://localhost:8000"


class APIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code}: {detail}")


class APIClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self):
        h = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _call(self, method: str, path: str, **kwargs):
        try:
            resp = requests.request(method, f"{self.base_url}{path}", headers=self._headers(), timeout=10, **kwargs)
        except requests.exceptions.ConnectionError:
            raise APIError(0, f"Can't reach the API at {self.base_url}. Is the backend running?")
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise APIError(resp.status_code, str(detail))
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # --- auth -------------------------------------------------------------
    def login(self, email: str, password: str):
        return self._call("POST", "/auth/login", json={"email": email, "password": password})

    def get_me(self):
        return self._call("GET", "/users/me")

    # --- users --------------------------------------------------------------
    def list_users(self, firm_id: int | None = None):
        return self._call("GET", "/users/", params={"firm_id": firm_id})

    def admin_create_user(self, name, email, password, role, firm_id=None):
        return self._call("POST", "/admin/users", json={
            "name": name, "email": email, "password": password, "role": role, "firm_id": firm_id})

    def admin_deactivate_user(self, user_id: int):
        return self._call("PATCH", f"/admin/users/{user_id}/deactivate")

    def admin_change_role(self, user_id: int, role: str):
        return self._call("PATCH", f"/admin/users/{user_id}/role", json={"role": role})

    # --- firms / matters / budgets ------------------------------------------
    def list_firms(self):
        return self._call("GET", "/firms")

    def create_firm(self, name, contact_email=None, status="active"):
        return self._call("POST", "/firms", json={"name": name, "contact_email": contact_email, "status": status})

    def list_matters(self, firm_id: int | None = None):
        return self._call("GET", "/matters", params={"firm_id": firm_id})

    def create_matter(self, firm_id, name, owner, status="open"):
        return self._call("POST", "/matters", json={"firm_id": firm_id, "name": name, "owner": owner, "status": status})

    def list_budgets(self):
        return self._call("GET", "/budgets")

    def create_budget(self, matter_id, allocated_amt, threshold_pct=80):
        return self._call("POST", "/budgets", json={
            "matter_id": matter_id, "allocated_amt": allocated_amt, "threshold_pct": threshold_pct})

    # --- invoices / line items ----------------------------------------------
    def list_invoices(self, matter_id=None, firm_id=None):
        return self._call("GET", "/invoices", params={"matter_id": matter_id, "firm_id": firm_id})

    def get_invoice(self, invoice_id: int):
        return self._call("GET", f"/invoices/{invoice_id}")

    def create_invoice(self, matter_id, firm_id, invoice_no, total_amount, invoice_date=None):
        return self._call("POST", "/invoices", json={
            "matter_id": matter_id, "firm_id": firm_id, "invoice_no": invoice_no,
            "invoice_date": str(invoice_date) if invoice_date else None, "total_amount": total_amount})

    def list_line_items(self, invoice_id: int | None = None):
        return self._call("GET", "/line-items", params={"invoice_id": invoice_id})

    def create_line_item(self, invoice_id, amount, timekeeper=None, hours=None, rate=None):
        return self._call("POST", "/line-items", json={
            "invoice_id": invoice_id, "timekeeper": timekeeper, "hours": hours, "rate": rate, "amount": amount})

    # --- budget ledger / alerts ----------------------------------------------
    def list_budget_ledger(self, budget_id=None, invoice_id=None):
        return self._call("GET", "/budget-ledger", params={"budget_id": budget_id, "invoice_id": invoice_id})

    def list_alerts(self, budget_id=None):
        return self._call("GET", "/alerts", params={"budget_id": budget_id})

    # --- review workflow -----------------------------------------------------
    def review_queue(self):
        return self._call("GET", "/review/queue")

    def approve(self, invoice_id: int, notes: str | None = None):
        return self._call("POST", f"/review/{invoice_id}/approve", params={"notes": notes})

    def reject(self, invoice_id: int, reason: str):
        return self._call("POST", f"/review/{invoice_id}/reject", params={"reason": reason})

    def clarify(self, invoice_id: int, reason: str):
        return self._call("POST", f"/review/{invoice_id}/clarify", params={"reason": reason})

    # --- validation ------------------------------------------------------------
    def validate_invoice(self, invoice_id, budget_valid=None, duplicate_flag=False, confidence_score=None):
        return self._call("POST", f"/validation/{invoice_id}", params={
            "budget_valid": budget_valid, "duplicate_flag": duplicate_flag, "confidence_score": confidence_score})

    # --- audit logs ---------------------------------------------------------------
    def list_audit_logs(self, invoice_id=None, user_id=None):
        return self._call("GET", "/audit-logs/", params={"invoice_id": invoice_id, "user_id": user_id})


def get_client() -> APIClient:
    base_url = st.session_state.get("base_url", DEFAULT_BASE_URL)
    token = st.session_state.get("token")
    return APIClient(base_url, token)


def require_login():
    """Call at the top of every page except Home. Stops the page if not logged in."""
    if not st.session_state.get("token") or not st.session_state.get("user"):
        st.warning("Please log in from the **Home** page first.")
        st.stop()


def require_role(*roles):
    require_login()
    user = st.session_state["user"]
    if user["role"] not in roles:
        st.error(
            f"This page is available to **{', '.join(r.title() for r in roles)}** only. "
            f"Your role is **{user['role'].title()}**. "
            "(This is a UI convenience — the backend enforces the same rule on every request.)"
        )
        st.stop()
