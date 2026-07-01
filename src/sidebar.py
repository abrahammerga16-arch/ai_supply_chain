"""
sidebar.py — Shared sidebar: auth widget + user info
Import and call render_sidebar() at the top of every role page.

Returns the current (profile, role) tuple, or (None, None) if not logged in.
"""

import streamlit as st
from src.shared import (
    supabase, REGIONS, SESSION_KEYS,
    sign_in, sign_up, sign_out, get_profile, get_unread_count,
)


def render_sidebar() -> tuple:
    """
    Renders the sidebar login/signup/logout widget.
    Returns (profile, role) — both None if user is not authenticated.
    """
    with st.sidebar:
        st.title("🌾 AI Supply Chain")
        st.caption("Ethiopian Multi-Sector Commerce")
        st.divider()

        if st.session_state.get("user") is None:
            tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

            with tab_login:
                login_email = st.text_input("Email", key="login_email")
                login_pass  = st.text_input("Password", type="password", key="login_pass")
                if st.button("Log In", use_container_width=True):
                    if not login_email or not login_pass:
                        st.warning("Please enter your email and password.")
                    else:
                        ok, msg = sign_in(login_email, login_pass)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            with tab_signup:
                su_name   = st.text_input("Full Name",    key="su_name")
                su_email  = st.text_input("Email",        key="su_email")
                su_pass   = st.text_input("Password", type="password", key="su_pass",
                                          help="Min 8 chars, letters + numbers")
                su_role   = st.selectbox("I am a...", ["producer", "merchant", "customer"], key="su_role")
                su_region = st.selectbox("Region", REGIONS, key="su_region")
                su_phone  = st.text_input("Phone Number", key="su_phone")
                if st.button("Create Account", use_container_width=True):
                    if not su_name or not su_email or not su_pass or not su_phone:
                        st.warning("Please fill in all required fields.")
                    else:
                        ok, msg = sign_up(su_email, su_pass, su_name, su_role, su_region, su_phone)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
            return None, None

        else:
            profile = st.session_state.get("profile") or get_profile(st.session_state.user.id)
            st.session_state.profile = profile
            role    = profile["role"] if profile else None

            st.success(f"Welcome, {profile['full_name'] if profile else 'User'}")
            st.caption(f"Role: {profile['role'].capitalize() if profile else 'N/A'}")
            st.caption(f"Region: {profile['region'] if profile else 'N/A'}")
            unread = get_unread_count(st.session_state.user.id)
            if unread:
                st.info(f"🔔 {unread} unread notification(s)")
            if st.button("Log Out", use_container_width=True):
                sign_out()
                st.rerun()

            return profile, role
