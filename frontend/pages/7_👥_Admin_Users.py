import streamlit as st

from utils.theme import inject_base_css, render_banner, role_badge
from utils.api_client import get_client, require_role, APIError

st.set_page_config(page_title="Admin · Users | Konverge", page_icon="👥", layout="wide")
inject_base_css()
require_role("admin")
render_banner("Admin · User Management", subtitle="Create accounts, change roles, and deactivate access.")

client = get_client()

with st.expander("➕ Create a user", expanded=False):
    try:
        firms = client.list_firms()
    except APIError as e:
        firms = []
        st.warning(f"Couldn't load firms: {e.detail}")
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
