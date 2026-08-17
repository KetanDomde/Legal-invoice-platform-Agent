import streamlit as st

from utils.theme import inject_base_css, render_banner, role_badge, kpi_tile, money
from utils.api_client import get_client, APIError, DEFAULT_BASE_URL
from utils.submit_result import render_persisted_submit_result, render_persisted_submit_error, RESULT_KEY, ERROR_KEY

st.set_page_config(page_title="Konverge | Legal Invoice Platform", page_icon="⚖️", layout="wide")
inject_base_css()

if "base_url" not in st.session_state:
    st.session_state["base_url"] = DEFAULT_BASE_URL

with st.sidebar:
    st.markdown("##### ⚙️ Connection")
    st.session_state["base_url"] = st.text_input(
        "API base URL", value=st.session_state["base_url"],
        help="Point this at your FastAPI server. Defaults to your local backend.",
    )

    # Health check — surfaces a clear "backend's not running" message
    # instead of a confusing connection error further down the page.
    client_probe = get_client()
    try:
        client_probe.health()
        st.success("API connected")
    except APIError as e:
        st.error(f"API unreachable: {e.detail}")

    if st.session_state.get("user"):
        u = st.session_state["user"]
        st.markdown(
            f"""<div class="kv-sidebar-card">
                    <b>{u['name']}</b><br/>{role_badge(u['role'])}
                    <div style="color:#807F85;font-size:0.8rem;margin-top:4px;">{u['email']}</div>
                </div>""",
            unsafe_allow_html=True,
        )
        if st.button("Log out", use_container_width=True):
            st.session_state.pop("token", None)
            st.session_state.pop("user", None)
            st.rerun()

render_banner(
    "Legal Invoice Tracking & Spend Management",
    subtitle="AI-assisted invoice review, budget tracking, and audit trail — built for outside-counsel spend.",
)

if not st.session_state.get("token"):
    if st.session_state.pop("session_expired", False):
        st.info("Your session has expired. Please log in again.")

    left, mid, right = st.columns([1, 1.1, 1])
    with mid:
        with st.container(border=True):
            st.markdown("#### Sign in")
            email = st.text_input("Email", placeholder="you@konverge.ai")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.button("Log in", type="primary", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Enter both email and password.")
            else:
                client = get_client()
                try:
                    token_data = client.login(email, password)
                    st.session_state["token"] = token_data["access_token"]
                    client.token = token_data["access_token"]
                    st.session_state["user"] = client.get_me()
                    st.rerun()
                except APIError as e:
                    st.error(f"Login failed: {e.detail}")
    st.stop()

user = st.session_state["user"]
st.markdown(f"### Welcome back, {user['name'].split()[0]} 👋")
st.caption(
    "Permissions are enforced by the backend on every request — the buttons you see here are just "
    "a convenience that match your role."
)

client = get_client()
try:
    invoices = client.list_invoices() or []
    review_q = client.review_queue() if user["role"] in ("admin", "editor") else []
    alerts = client.list_alerts() or []
except APIError as e:
    invoices, review_q, alerts = [], [], []
    st.warning(f"Couldn't load a quick summary: {e.detail}")

c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi_tile("Total invoices", str(len(invoices)))
with c2:
    kpi_tile("Total spend", money(sum(i.get("total_amount", 0) for i in invoices)) if invoices else "$0.00")
with c3:
    kpi_tile("Pending review", str(len(review_q)))
with c4:
    kpi_tile("Active alerts", str(len(alerts)))

st.markdown("&nbsp;")

# --- Upload Invoice: wired to the real, confirmed-working pipeline endpoint ---
if user["role"] in ("admin", "editor"):
    render_persisted_submit_result()
    render_persisted_submit_error()

    with st.expander("📤 Submit Invoice for Processing", expanded=False):
        uploaded_file = st.file_uploader("Invoice file", type=["pdf", "txt"])

        can_submit = uploaded_file is not None
        if st.button("Submit invoice", type="primary", disabled=not can_submit):
            with st.spinner("Extracting, validating, and persisting..."):
                try:
                    result = client.submit_invoice(uploaded_file)
                except APIError as e:
                    if e.status_code == 409:
                        st.session_state[ERROR_KEY] = {
                            "label": "Duplicate",
                            "detail": e.detail,
                            "inv_changes": getattr(e, "inv_changes", None),
                        }
                    elif e.status_code == 422:
                        st.error(f"Invalid request: {e.detail}")
                    else:
                        st.error(f"API error {e.status_code}: {e.detail}")
                    result = None

            if result is not None:
                st.session_state[RESULT_KEY] = result
                st.rerun()
            elif ERROR_KEY in st.session_state:
                st.rerun()

st.markdown("Use the pages in the sidebar to navigate: **Dashboard**, **Invoices**, **Review Queue**, "
            "**Firms & Matters**, **Budgets & Alerts**, **Audit Log**, and (Admin only) **Admin Users**.")