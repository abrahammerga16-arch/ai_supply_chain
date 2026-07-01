import sys
import os

# 1. Clear out the bad folder mapping that breaks 'from src.db ...'
_current_dir = os.path.dirname(os.path.abspath(__file__)) # This equals .../src/src
_root_dir = os.path.dirname(_current_dir)                 # This equals .../src

if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

import streamlit as st
from src.db import get_supabase_client
from src.shared import sign_in, sign_up, get_profile, SESSION_KEYS, REGIONS

st.set_page_config(
    page_title="AI Supply Chain Platform",
    page_icon="🌾",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Hide sidebar on landing/auth page
st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="collapsedControl"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# ── Session defaults ──────────────────────────────────────────
for key in SESSION_KEYS:
    if key not in st.session_state:
        st.session_state[key] = None

# ── Already logged in → redirect to role page ─────────────────
if st.session_state.get("user") and st.session_state.get("profile"):
    role = st.session_state.profile.get("role", "").lower()
    
    # 2. Add fallback path logic to handle the nested deployment directory
    role_map = {
        "producer": "pages/1_Producer.py",
        "merchant": "pages/2_Merchant.py",
        "customer": "pages/3_Customer.py",
        "admin":    "pages/4_Admin.py",
    }
    
    if role in role_map:
        try:
            # First try the standard path
            st.switch_page(role_map[role])
        except Exception:
            try:
                # If nested, try matching with the execution prefix
                st.switch_page(f"src/{role_map[role]}")
            except Exception as e:
                st.error(f"Could not load dashboard page: {e}. Check folder configuration.")
    else:
        st.error(f"Unknown role: '{role}'. Contact admin.")
