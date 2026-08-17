"""
Thin wrapper around the FastAPI backend used by every Streamlit page.

Endpoint shapes here mirror the real backend exactly (backend/app/api/*.py,
backend/app/schemas/*.py). Point API_BASE_URL / base_url at the real
server (default http://localhost:8000).
"""
import requests
import streamlit as st

DEFAULT_BASE_URL = "http://localhost:8000"


class APIError(Exception):
    def __init__(self, status_code: int, detail: str, inv_changes: dict|None=None):
        self.status_code = status_code
        self.detail = detail
        self.inv_changes = inv_changes
        super().__init__(
            f"{status_code}: {detail}"
            f"{inv_changes}"
        )


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
            resp = requests.request(
                method, f"{self.base_url}{path}",
                headers=self._headers(), timeout=kwargs.pop("timeout", 10), **kwargs
            )
        except requests.exceptions.ConnectionError:
            raise APIError(0, f"Can't reach the API at {self.base_url}. Is the backend running?")
        # A 401 while a bearer token was sent means that token is invalid/expired
        # (as opposed to /auth/login's own 401 for bad credentials, sent with no
        # token at all) — bounce back to the login page instead of leaving the
        # user stuck on a page full of failed requests.
        if resp.status_code == 401 and self.token:
            _handle_session_expired()
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except Exception:
                payload = {}
            detail = payload.get("detail", resp.text)
            inv_changes = payload.get("inv_changes")
            raise APIError(resp.status_code, str(detail), inv_changes)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # --- health ---------------------------------------------------------
    def health(self):
        return self._call("GET", "/health")

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

    # --- invoices -------------------------------------------------------
    # Matter/firm are no longer supplied by the caller on submit — they're
    # resolved (and auto-created if needed) server-side from matter_no/
    # matter_name extracted straight off the invoice text. matter_no and
    # firm_name here are optional manual overrides only, for when
    # extraction can't find an identifier or you want to route a new
    # matter to a specific firm. invoice_id is always server-generated.
    def submit_invoice(self, file, matter_no: str | None = None, firm_name: str | None = None):
        """
        Upload a PDF/TXT to the extraction/validation pipeline. Creates a
        NEW invoice. `file` is a Streamlit UploadedFile (has .name and
        .getvalue()). Raises APIError(422) if no matter identifier could
        be extracted and no matter_no override was supplied, or
        APIError(409, inv_changes={...}) if it's a duplicate of an
        existing invoice for the resolved matter.
        """
        files = {"file": (file.name, file.getvalue(), file.type or "application/pdf")}
        data = {}
        if matter_no:
            data["matter_no"] = matter_no
        if firm_name:
            data["firm_name"] = firm_name
        return self._call("POST", "/invoices/submit", data=data, files=files, timeout=60)

    def update_invoice_file(self, invoice_id: int, matter_id, file, matter_name: str | None = None):
        """
        Re-extracts an EXISTING invoice from a corrected file (PUT). Always
        routes the result back to pending_review, never auto-re-approves.
        Unlike submit, this still takes an explicit numeric matter_id —
        PUT hasn't been moved onto the auto-resolve-from-extraction path.
        """
        files = {"file": (file.name, file.getvalue(), file.type or "application/pdf")}
        data = {"matter_id": str(matter_id)}
        if matter_name:
            data["matter_name"] = matter_name
        return self._call("PUT", f"/invoices/{invoice_id}", data=data, files=files, timeout=60)

    def get_invoice(self, invoice_id: int):
        return self._call("GET", f"/invoices/{invoice_id}")

    def list_invoices(self, matter_id=None, firm_id=None):
        params = {}
        if matter_id is not None:
            params["matter_id"] = matter_id
        if firm_id is not None:
            params["firm_id"] = firm_id
        return self._call("GET", "/invoices", params=params or None)
    
    
    def list_line_items(self, invoice_id=None):
        return self._call("GET", "/line-items", params={"invoice_id": invoice_id})

    # --- budget ledger / alerts ----------------------------------------------
    def list_budget_ledger(self, budget_id=None, invoice_id=None):
        return self._call("GET", "/budget-ledger", params={"budget_id": budget_id, "invoice_id": invoice_id})

    def list_alerts(self, budget_id=None):
        return self._call("GET", "/alerts", params={"budget_id": budget_id})

    # --- review workflow -----------------------------------------------------
    def review_queue(self):
        return self._call("GET", "/review/queue")

    def get_review_invoice(self, invoice_id: int):
        return self._call("GET", f"/review/{invoice_id}")

    def approve(self, invoice_id, notes: str | None = None):
        return self._call("POST", f"/review/{invoice_id}/approve", params={"notes": notes})

    def reject(self, invoice_id, reason: str):
        return self._call("POST", f"/review/{invoice_id}/reject", params={"reason": reason})

    def clarify(self, invoice_id, reason: str):
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


def _handle_session_expired():
    st.session_state.pop("token", None)
    st.session_state.pop("user", None)
    st.session_state["session_expired"] = True
    st.switch_page("Home.py")


def require_login():
    """Call at the top of every page except Home. Redirects to Home (the
    login form) if not logged in, instead of stopping mid-page."""
    if not st.session_state.get("token") or not st.session_state.get("user"):
        st.switch_page("Home.py")


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