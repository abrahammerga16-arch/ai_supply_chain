import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from src.auth import init_supabase, login_user, register_user

st.set_page_config(
    page_title="AI Supply Chain Platform",
    page_icon="🌾",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Hide sidebar on landing page
st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="collapsedControl"] { display: none; }
    </style>
""", unsafe_allow_html=True)

supabase = init_supabase()

# ── Session defaults ──────────────────────────────────────────
if "user" not in st.session_state:
    st.session_state.user = None
if "profile" not in st.session_state:
    st.session_state.profile = None
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# ── Already logged in → redirect to role page ─────────────────
if st.session_state.user and st.session_state.profile:
    role = st.session_state.profile.get("role", "").lower()
    role_map = {
        "producer": "pages/1_Producer.py",
        "merchant": "pages/2_Merchant.py",
        "customer": "pages/3_Customer.py",
        "admin":    "pages/4_Admin.py",
    }
    if role in role_map:
        st.switch_page(role_map[role])
    else:
        st.error(f"Unknown role: '{role}'. Contact support.")
    st.stop()

# ── Landing UI ────────────────────────────────────────────────
st.title("🌾 AI Supply Chain Platform")
st.caption("Wolaita Sodo University · Department of ECE")
st.divider()

tab_login, tab_register = st.tabs(["Login", "Register"])

# ── Login tab ─────────────────────────────────────────────────
with tab_login:
    st.subheader("Sign In")
    email    = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", use_container_width=True, type="primary"):
        if not email or not password:
            st.warning("Please fill in all fields.")
        else:
            with st.spinner("Signing in…"):
                user, profile, error = login_user(supabase, email, password)
            if error:
                st.error(f"Login failed: {error}")
            else:
                st.session_state.user    = user
                st.session_state.profile = profile
                st.rerun()

# ── Register tab ──────────────────────────────────────────────
with tab_register:
    st.subheader("Create Account")
    reg_name     = st.text_input("Full Name",        key="reg_name")
    reg_email    = st.text_input("Email",            key="reg_email")
    reg_password = st.text_input("Password",         type="password", key="reg_password")
    reg_role     = st.selectbox("Role", ["producer", "merchant", "customer"], key="reg_role")
    reg_phone    = st.text_input("Phone (optional)", key="reg_phone")

    if st.button("Register", use_container_width=True, type="primary"):
        if not all([reg_name, reg_email, reg_password]):
            st.warning("Name, email, and password are required.")
        else:
            with st.spinner("Creating account…"):
                user, profile, error = register_user(
                    supabase, reg_email, reg_password,
                    reg_name, reg_role, reg_phone
                )
            if error:
                st.error(f"Registration failed: {error}")
            else:
                st.session_state.user    = user
                st.session_state.profile = profile
                st.success("Account created! Redirecting…")
                st.rerun()
