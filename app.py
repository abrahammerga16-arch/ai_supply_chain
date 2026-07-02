"""
app.py — Ethiopian AI Supply Chain Platform (Single-File)
Wolaita Sodo University | Department of ECE

All pages (Landing, Producer, Merchant, Customer, Admin) are merged here.
Navigation uses st.session_state role-based routing — no multi-page files needed.
Remove the pages/ directory entirely; this file replaces app.py + all page files.
"""

import io
import re as _re
import base64
import datetime
import sys, os

import streamlit as st
import pandas as pd

# ── Keep src/ imports working ────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from src.db import get_supabase_client
from src.matching_engine import rank_merchants
from src.price_engine import recommend_price
from src.fraud_engine import check_fraud_risk
from src.demand_engine import forecast_demand

# ════════════════════════════════════════════════════════════
# PAGE CONFIG (called once, before any st.* output)
# ════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AI Supply Chain Platform",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="auto",
)

# ════════════════════════════════════════════════════════════
# SUPABASE CLIENT
# ════════════════════════════════════════════════════════════
try:
    supabase = get_supabase_client()
except ValueError as e:
    st.error(str(e))
    st.stop()

# ════════════════════════════════════════════════════════════
# HELPER FUNCTIONS & AUTH UTILS
# ════════════════════════════════════════════════════════════
def safe_query(query_builder):
    try:
        res = query_builder.execute()
        return res.data if res else []
    except Exception as e:
        st.error(f"Database error: {e}")
        return []

def get_user_profile(user_id):
    if not user_id:
        return None
    data = safe_query(supabase.table("profiles").select("*").eq("id", user_id))
    return data[0] if data else None

def handle_logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.success("Logged out successfully!")
    st.rerun()

# ════════════════════════════════════════════════════════════
# NOTIFICATION SYSTEM
# ════════════════════════════════════════════════════════════
def fetch_notifications(user_id):
    return safe_query(
        supabase.table("notifications")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", descend=True)
    )

def render_notifications_sidebar(user_id):
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔔 Notifications")
    notifs = fetch_notifications(user_id)
    if not notifs:
        st.sidebar.info("No new notifications.")
        return
        
    icon_map = {
        "order": "📦",
        "price": "📈",
        "fraud": "⚠️",
        "matching": "🤝",
        "system": "⚙️"
    }
    
    for n in notifs[:5]:
        ntype = n.get("type", "system")
        icon = icon_map.get(ntype, "🔔")
        status_color = "#ff4b4b" if not n.get("is_read") else "#777777"
        
        st.sidebar.markdown(
            f"""
            <div style="padding:10px; border-radius:5px; background-color:#f0f2f6; margin-bottom:8px; border-left:4px solid {status_color}">
                <small style="color:#888;">{n.get('created_at', '')[:16]}</small><br>
                <b>{icon}</b> {n.get('message', '')}<br>
            </div>
            """, 
            unsafe_html=True
        )
        
    if st.sidebar.button("Clear All Notifications", key="clear_notifs"):
        try:
            supabase.table("notifications").update({"is_read": True}).eq("user_id", user_id).execute()
            st.rerun()
        except Exception:
            pass

# ════════════════════════════════════════════════════════════
# VIEWS: LOGIN / REGISTRATION
# ════════════════════════════════════════════════════════════
def render_login_form():
    st.subheader("Sign In")
    with st.form("login_form"):
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)
        
        if submitted:
            if not email or not password:
                st.error("Please fill in all fields.")
                return
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.user:
                    st.session_state["user_id"] = res.user.id
                    profile = get_user_profile(res.user.id)
                    if profile:
                        st.session_state["role"] = profile.get("role", "customer")
                        st.session_state["full_name"] = profile.get("full_name", "User")
                    else:
                        st.session_state["role"] = "customer"
                    st.success("Welcome back!")
                    st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")

def render_register_form():
    st.subheader("Create an Account")
    with st.form("register_form"):
        full_name = st.text_input("Full Name")
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        role = st.selectbox("I am a...", ["customer", "producer", "merchant", "admin"])
        phone = st.text_input("Phone Number (Optional)")
        location = st.text_input("Location / Region (Optional)")
        submitted = st.form_submit_button("Create Account", use_container_width=True)
        
        if submitted:
            if not full_name or not email or not password:
                st.error("Name, Email, and Password are required.")
                return
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                if res.user:
                    uid = res.user.id
                    supabase.table("profiles").insert({
                        "id": uid,
                        "full_name": full_name,
                        "role": role,
                        "phone": phone,
                        "location": location
                    }).execute()
                    st.success("Account created successfully! Please log in above.")
            except Exception as e:
                st.error(f"Registration failed: {e}")

# ════════════════════════════════════════════════════════════
# DASHBOARD ROLES: PRODUCER
# ════════════════════════════════════════════════════════════
def render_producer_dashboard(user_id):
    st.title("🚜 Producer Dashboard")
    st.write("Manage your agricultural products, view price recommendations, and fulfill contracts.")
    
    tab1, tab2, tab3 = st.tabs(["🌾 My Inventory", "📈 Smart Pricing AI", "📦 Incoming Orders"])
    
    with tab1:
        st.subheader("Add New Produce List")
        with st.form("add_product_form"):
            p_name = st.text_input("Crop/Product Name (e.g., Teff, Coffee, Haricot Beans)")
            p_category = st.selectbox("Category", ["Cereals", "Pulses", "Coffee & Oilseeds", "Vegetables", "Livestock"])
            p_qty = st.number_input("Available Quantity (Quintals / KG)", min_value=1.0, step=1.0)
            p_price = st.number_input("Target Price per Unit (Birr)", min_value=1.0, step=5.0)
            p_desc = st.text_area("Product Specifications / Quality metrics")
            p_submit = st.form_submit_button("Publish to Marketplace")
            
            if p_submit and p_name:
                try:
                    supabase.table("inventory").insert({
                        "user_id": user_id,
                        "product_name": p_name,
                        "category": p_category,
                        "quantity": p_qty,
                        "price_per_unit": p_price,
                        "description": p_desc,
                        "status": "available"
                    }).execute()
                    st.success(f"Published {p_name} to the active marketplace!")
                except Exception as e:
                    st.error(str(e))
                    
        st.markdown("---")
        st.subheader("My Listed Inventory")
        inv_data = safe_query(supabase.table("inventory").select("*").eq("user_id", user_id))
        if inv_data:
            df_inv = pd.DataFrame(inv_data)
            st.dataframe(df_inv[["id", "product_name", "category", "quantity", "price_per_unit", "status", "created_at"]], use_container_width=True)
        else:
            st.info("You haven't listed any items yet.")

    with tab2:
        st.subheader("AI Price Prediction & Analytics")
        st.write("Get regional machine-learning-driven recommendations on current agricultural prices based on historical trends, weather patterns, and local market demand.")
        
        crop_sel = st.selectbox("Select Crop for AI Valuation Analysis", ["Teff (White)", "Teff (Brown)", "Coffee (Arabica)", "Wheat", "Maize", "Haricot Beans"])
        region_sel = st.selectbox("Market Hub Region",
