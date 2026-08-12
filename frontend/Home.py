import streamlit as st

from utils.theme import inject_base_css, render_banner, role_badge
from utils.api_client import get_client, APIError, DEFAULT_BASE_URL

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
    invoices = client.list_invoices()
    review_q = client.review_queue() if user["role"] in ("admin", "editor") and user["firm_id"] else []
    alerts = client.list_alerts()
except APIError as e:
    invoices, review_q, alerts = [], [], []
    st.warning(f"Couldn't load a quick summary: {e.detail}")

c1, c2, c3, c4 = st.columns(4)
from utils.theme import kpi_tile, money
with c1:
    kpi_tile("Total invoices", str(len(invoices)))
with c2:
    kpi_tile("Total spend", money(sum(i["total_amount"] for i in invoices)) if invoices else "$0.00")
with c3:
    kpi_tile("Pending review", str(len(review_q)))
with c4:
    kpi_tile("Active alerts", str(len(alerts)))

st.markdown("&nbsp;")
st.markdown("Use the pages in the sidebar to navigate: **Dashboard**, **Invoices**, **Review Queue**, "
            "**Firms & Matters**, **Budgets & Alerts**, **Audit Log**, and (Admin only) **Admin Users**.")
