import streamlit as st

from utils.theme import inject_base_css, page_header, role_badge, sidebar_brand
from utils.api_client import get_client, require_login, APIError

st.set_page_config(page_title="Admin Control | Konverge", page_icon="🛠️", layout="wide")
inject_base_css()
sidebar_brand()
require_login()

client = get_client()
user = st.session_state["user"]

page_header(10, "Admin Control", "Firms, matters, and user management — the cross-entity control room for this platform.")

tab_firms, tab_users = st.tabs(["Firms & Matters", "Users"])

try:
    firms = client.list_firms()
    matters = client.list_matters()
except APIError as e:
    st.error(f"Couldn't load firms/matters: {e.detail}")
    st.stop()

firm_names = {f["firm_id"]: f["name"] for f in firms}

with tab_firms:
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("##### Firms")
            for f in firms:
                st.markdown(f"**{f['name']}**  \n"
                            f"<span style='font-size:0.85rem;opacity:.75'>{f.get('contact_email') or 'no contact on file'} · {f['status']}</span>",
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
                            f"<span style='font-size:0.85rem;opacity:.75'>{firm_names.get(m['firm_id'], '—')} · "
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

with tab_users:
    if user["role"] != "admin":
        st.info("Admin role required for user management.")
    else:
        with st.expander("➕ Create a user", expanded=False):
            firm_lookup = {"(no firm — global user)": None, **{f["name"]: f["firm_id"] for f in firms}}
            with st.form("new_user", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Name")
                    email = st.text_input("Email")
                with c2:
                    password = st.text_input("Temporary password", type="password")
                    role = st.selectbox("Role", ["admin", "editor", "viewer"], index=2)
                firm_label = st.selectbox("Firm", list(firm_lookup.keys()))
                if st.form_submit_button("Create user", type="primary"):
                    if not (name and email and password):
                        st.error("Name, email, and password are required.")
                    else:
                        try:
                            client.admin_create_user(name=name, email=email, password=password,
                                                      role=role, firm_id=firm_lookup[firm_label])
                            st.success(f"User {email} created.")
                            st.rerun()
                        except APIError as e:
                            st.error(e.detail)

        st.markdown("&nbsp;")
        st.markdown("##### All users")
        try:
            users = client.list_users()
        except APIError as e:
            st.error(f"Couldn't load users: {e.detail}")
            st.stop()

        for u in users:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 1, 1.3, 1.3])
                with c1:
                    st.markdown(f"**{u['name']}**")
                    st.caption(u["email"])
                with c2:
                    st.markdown(role_badge(u["role"]), unsafe_allow_html=True)
                    if not u["is_active"]:
                        st.caption("🔒 Deactivated")
                with c3:
                    new_role = st.selectbox("Change role", ["admin", "editor", "viewer"],
                                             index=["admin", "editor", "viewer"].index(u["role"]),
                                             key=f"role_{u['user_id']}", label_visibility="collapsed")
                    if new_role != u["role"] and st.button("Save role", key=f"save_role_{u['user_id']}"):
                        try:
                            client.admin_change_role(u["user_id"], new_role)
                            st.rerun()
                        except APIError as e:
                            st.error(e.detail)
                with c4:
                    if u["is_active"] and st.button("Deactivate", key=f"deact_{u['user_id']}"):
                        try:
                            client.admin_deactivate_user(u["user_id"])
                            st.rerun()
                        except APIError as e:
                            st.error(e.detail)
