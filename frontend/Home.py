"""
Minimal test harness for the invoice pipeline — NOT the project's real
dashboard. frontend/Home.py was a 0-byte empty file; this fills it with
just enough to visually test what Bhushan's pipeline produces, since
"we can't test it" (no endpoint, no UI) was the actual blocker raised.

This is intentionally thin: file upload, matter/firm id inputs, a submit
button, and a raw view of what the API returns. It does NOT implement:
  - duplication-check UI (Trinkesh/Rajat's territory)
  - approve/reject actions (needs the review-queue table, not built yet)
  - budget dashboard (needs Rajat's real Matter/Budget, not built yet)
  - login / auth (Trinkesh's get_current_user doesn't exist yet)

Whoever picks up the real dashboard should feel free to replace this
entirely — it's a testing tool, not a deliverable UI.

Run with (from backend/, API server running separately):
    streamlit run ../frontend/Home.py
Requires: pip install streamlit requests
"""
import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Legal Invoice Pipeline — Test Harness", page_icon="🧪", layout="centered")

st.title("🧪 Legal Invoice Pipeline — Test Harness")
st.caption(
    "Minimal tool to manually test the extraction/persistence pipeline end-to-end. "
    "Not the real dashboard — see the docstring in this file for scope."
)

# --- API health check, so a confusing connection error doesn't look like a pipeline bug ---
with st.sidebar:
    st.subheader("API status")
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if r.status_code == 200:
            st.success(f"Connected — {API_BASE_URL}")
        else:
            st.error(f"API responded but with status {r.status_code}")
    except requests.exceptions.ConnectionError:
        st.error(
            f"Can't reach {API_BASE_URL}.\n\n"
            "Start the API first, in another terminal:\n"
            "`uvicorn app.main:app --reload`"
        )

tab_submit, tab_lookup, tab_list = st.tabs(["Submit Invoice", "Look Up Invoice", "All Invoices"])

# --- Submit ---
with tab_submit:
    st.subheader("Submit a new invoice")
    invoice_id = st.text_input("Invoice ID *", placeholder="e.g. INV-2026-001 or ABC123", help="Required. Alphanumeric. This IS the invoice's identity — never auto-generated.")
    matter_id = st.number_input("Matter ID *", min_value=1, value=1, step=1)

    uploaded_file = st.file_uploader("Invoice file (PDF)", type=["pdf", "txt"])

    can_submit = bool(invoice_id.strip()) and uploaded_file is not None
    if st.button("Submit invoice", type="primary", disabled=not can_submit):
        with st.spinner("Extracting, validating, and persisting..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                data = {"invoice_id": invoice_id.strip(), "matter_id": int(matter_id)}
                resp = requests.post(f"{API_BASE_URL}/invoices/submit", data=data, files=files, timeout=60)
            except requests.exceptions.ConnectionError:
                st.error("Couldn't reach the API — is uvicorn running?")
                resp = None

        if resp is not None:
            if resp.status_code == 409:
                st.error(f"🚫 Duplicate: {resp.json().get('detail')}")
            elif resp.status_code == 422:
                st.error(f"Invalid request: {resp.json().get('detail')}")
            elif resp.status_code == 200:
                result = resp.json()
                st.success(f"Done — invoice_id={result['invoice_id']}, status={result['final_status']}")

                if result.get("warning"):
                    st.warning(f"⚠️ {result['warning']}")

                c1, c2 = st.columns(2)
                c1.metric("Confidence", f"{result['confidence_score']:.2f}" if result["confidence_score"] is not None else "—")
                c2.metric("Status", result["final_status"])

                st.write("**Extracted fields**")
                st.json(result["extracted"])

                if result["extracted"].get("line_items"):
                    st.write("**Line items**")
                    st.table(result["extracted"]["line_items"])

                with st.expander("Full audit trail"):
                    for line in result["audit_trail"]:
                        st.text(line)
            else:
                st.error(f"API error {resp.status_code}: {resp.json().get('detail', resp.text)}")

# --- Look up ---
with tab_lookup:
    st.subheader("Look up a persisted invoice")
    lookup_id = st.text_input("Invoice ID", placeholder="e.g. INV-2026-001", key="lookup_id")
    if st.button("Fetch", disabled=not lookup_id.strip()):
        try:
            resp = requests.get(f"{API_BASE_URL}/invoices/{lookup_id.strip()}", timeout=10)
        except requests.exceptions.ConnectionError:
            st.error("Couldn't reach the API — is uvicorn running?")
            resp = None

        if resp is not None:
            if resp.status_code == 200:
                st.json(resp.json())
            elif resp.status_code == 404:
                st.warning(f"No invoice with id '{lookup_id.strip()}'")
            else:
                st.error(f"API error {resp.status_code}")

# --- List all ---
with tab_list:
    st.subheader("All invoices persisted so far")
    if st.button("Refresh list"):
        try:
            resp = requests.get(f"{API_BASE_URL}/invoices", timeout=10)
            if resp.status_code == 200:
                invoices = resp.json()
                if invoices:
                    st.table(invoices)
                else:
                    st.info("No invoices submitted yet.")
            else:
                st.error(f"API error {resp.status_code}")
        except requests.exceptions.ConnectionError:
            st.error("Couldn't reach the API — is uvicorn running?")