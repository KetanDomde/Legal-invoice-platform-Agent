import streamlit as st

from utils.theme import inject_base_css, render_banner
from utils.api_client import get_client, require_login, APIError

st.set_page_config(page_title="Firms & Matters | Konverge", page_icon="🏢", layout="wide")
inject_base_css()
require_login()
render_banner("Firms & Matters", subtitle="Outside-counsel firms and the matters billed against them.")

client = get_client()
user = st.session_state["user"]

try:
    firms = client.list_firms()
    matters = client.list_matters()
except APIError as e:
    st.error(f"Couldn't load firms/matters: {e.detail}")
    st.stop()

firm_names = {f["firm_id"]: f["name"] for f in firms}

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.markdown("##### Firms")
        for f in firms:
            st.markdown(f"**{f['name']}**  \n"
                        f"<span style='color:#807F85;font-size:0.85rem'>{f.get('contact_email') or 'no contact on file'} · {f['status']}</span>",
                        unsafe_allow_html=True)
            st.divider()
        if user["role"] == "admin":
            with st.expander("➕ Add a firm"):
                with st.form("new_firm", clear_on_submit=True):
                    name = st.text_input("Firm name")
                    contact = st.text_input("Contact email")
                    if st.form_submit_button("Create firm", type="primary"):
                        try:
                            client.create_firm(name=name, contact_email=contact or None)
                            st.success("Firm created.")
                            st.rerun()
                        except APIError as e:
                            st.error(e.detail)

with col2:
    with st.container(border=True):
        st.markdown("##### Matters")
        for m in matters:
            st.markdown(f"**{m['name']}**  \n"
                        f"<span style='color:#807F85;font-size:0.85rem'>{firm_names.get(m['firm_id'], '—')} · "
                        f"Owner: {m['owner']} · {m['status']}</span>", unsafe_allow_html=True)
            st.divider()
        if user["role"] in ("admin", "editor"):
            with st.expander("➕ Add a matter"):
                if not firms:
                    st.info("Create a firm first.")
                else:
                    firm_lookup = {f["name"]: f["firm_id"] for f in firms}
                    with st.form("new_matter", clear_on_submit=True):
                        firm_label = st.selectbox("Firm", list(firm_lookup.keys()))
                        name = st.text_input("Matter name")
                        owner = st.text_input("Owner")
                        if st.form_submit_button("Create matter", type="primary"):
                            try:
                                client.create_matter(firm_id=firm_lookup[firm_label], name=name, owner=owner)
                                st.success("Matter created.")
                                st.rerun()
                            except APIError as e:
                                st.error(e.detail)
