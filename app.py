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
        .order("created_at", desc=True)
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
        region_sel = st.selectbox("Market Hub Region", ["Addis Ababa", "Oromia (Jimma)", "Amhara (Bahir Dar)", "Sidama (Hawassa)", "SNNPR (Wolaita Sodo)"])
        
        if st.button("Calculate Optimal Selling Price", type="primary"):
            with st.spinner("Analyzing real-time market data indexes..."):
                rec = recommend_price(crop_sel, region_sel)
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Fair Market Value", f"{rec['fair_price']:,} Birr/Qtl")
                col2.metric("Projected Ceiling Price", f"{rec['ceiling_price']:,} Birr/Qtl", "+3.5%")
                col3.metric("Suggested Floor Price", f"{rec['floor_price']:,} Birr/Qtl", "-2.1%")
                
                st.info(f"💡 **AI Insights:** {rec['insight_text']}")
                
                # Simple pricing trends plot
                dates = [datetime.date.today() - datetime.timedelta(days=x) for x in range(30, 0, -5)][::-1]
                base_p = rec['fair_price']
                prices = [base_p * (1 + (x * 0.005 if x % 2 == 0 else -x * 0.003)) for x in range(6)]
                trend_df = pd.DataFrame({"Date": dates, "Price (Birr)": prices}).set_index("Date")
                st.line_chart(trend_df)

    with tab3:
        st.subheader("Contracts and Purchase Requests")
        orders = safe_query(supabase.table("orders").select("*, profiles!orders_buyer_id_fkey(full_name, phone)").eq("seller_id", user_id))
        if orders:
            for o in orders:
                status_color = "orange" if o["status"] == "pending" else "green" if o["status"] == "confirmed" else "red"
                with st.container():
                    st.markdown(
                        f"""
                        <div style="border:1px solid #ddd; padding:15px; border-radius:5px; margin-bottom:10px;">
                            <h4>Order Reference #{o['id'][:8]} — <span style="color:{status_color};">{o['status'].upper()}</span></h4>
                            <p><b>Buyer:</b> {o.get('profiles', {}).get('full_name', 'Unknown')} ({o.get('profiles', {}).get('phone', 'N/A')})<br>
                            <b>Total Capital Committed:</b> {o['total_price_birr']:,} Birr<br>
                            <b>Quantity Requested:</b> {o['quantity_ordered']} units</p>
                        </div>
                        """, unsafe_html=True
                    )
                    if o["status"] == "pending":
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Accept Contract", key=f"acc_{o['id']}", use_container_width=True):
                            supabase.table("orders").update({"status": "confirmed"}).eq("id", o["id"]).execute()
                            # Notify Buyer
                            supabase.table("notifications").insert({"user_id": o["buyer_id"], "type": "order", "message": f"Your order #{o['id'][:8]} was accepted by the producer!"}).execute()
                            st.rerun()
                        if c2.button("❌ Decline", key=f"dec_{o['id']}", use_container_width=True):
                            supabase.table("orders").update({"status": "cancelled"}).eq("id", o["id"]).execute()
                            st.rerun()
        else:
            st.info("No incoming purchase orders found.")

# ════════════════════════════════════════════════════════════
# DASHBOARD ROLES: MERCHANT / WHOLESALER
# ════════════════════════════════════════════════════════════
def render_merchant_dashboard(user_id):
    st.title("🏬 Merchant / Processing Hub Dashboard")
    st.write("Source agricultural products directly from farmers, use the AI Matchmaking Engine, and run decentralized risk workflows.")
    
    tab1, tab2, tab3 = st.tabs(["🔍 AI Sourcing & Matchmaking", "💼 My Purchase Requests", "📉 Regional Market Demand Forecast"])
    
    with tab1:
        st.subheader("Smart Automated Matchmaker")
        st.write("Define your precise supply criteria to locate compatible and verified smallholder producers across Ethiopia automatically.")
        
        m_crop = st.text_input("Enter Desired Crop type (e.g. Teff)", "Teff")
        max_dist = st.slider("Maximum Logistical Distance Scope (Radius in KM)", 10, 500, 150)
        
        if st.button("Execute AI Matchmaking Algorithms", type="primary"):
            with st.spinner("Calculating optimization weights and routing metrics..."):
                all_inv = safe_query(supabase.table("inventory").select("*, profiles!inventory_user_id_fkey(full_name, location)").eq("status", "available"))
                # Basic matching filter
                matches = [i for i in all_inv if m_crop.lower() in i["product_name"].lower()]
                
                if matches:
                    ranked = rank_merchants(matches, preference={"max_dist": max_dist})
                    for idx, m in enumerate(ranked):
                        risk_score = check_fraud_risk(m['user_id'])
                        badge = "🟢 VERIFIED LOW RISK" if risk_score < 30 else "🟡 MEDIUM RISK" if risk_score < 70 else "🔴 HIGH RISK RISK INDEX"
                        
                        st.markdown(
                            f"""
                            <div style="border:1px solid #e0e0e0; padding:15px; border-radius:8px; margin-bottom:12px; background-color: #fafafa;">
                                <div style="display:flex; justify-content:space-between;">
                                    <h5>Rank #{idx+1}: {m['product_name']} ({m['category']})</h5>
                                    <b>{badge}</b>
                                </div>
                                <p><b>Farmer/Producer:</b> {m.get('profiles', {}).get('full_name', 'Independent Farmer')}<br>
                                <b>Location Hub:</b> {m.get('profiles', {}).get('location', 'Unknown Region')}<br>
                                <b>Volume Stored:</b> {m['quantity']} Qtl | <b>Asks:</b> {m['price_per_unit']} Birr/Unit</p>
                            </div>
                            """, unsafe_html=True
                        )
                        
                        # Inline ordering mechanism
                        with st.expander(f"Initiate Safe Procurement Contract for Rank #{idx+1}"):
                            order_qty = st.number_input("Procurement Volume Amount", min_value=1.0, max_value=float(m['quantity']), value=float(m['quantity']), key=f"mqty_{m['id']}")
                            notes = st.text_area("Delivery Terms / Logistics Requirements", key=f"mnotes_{m['id']}")
                            if st.button("🚀 Commit Escrow & Submit Request", key=f"mbtn_{m['id']}", use_container_width=True):
                                total_cost = order_qty * m['price_per_unit']
                                # Insert order
                                try:
                                    supabase.table("orders").insert({
                                        "buyer_id": user_id,
                                        "seller_id": m["user_id"],
                                        "inventory_id": m["id"],
                                        "quantity_ordered": order_qty,
                                        "total_price_birr": total_cost,
                                        "status": "pending",
                                        "notes": notes
                                    }).execute()
                                    
                                    # Create notification for seller
                                    supabase.table("notifications").insert({
                                        "user_id": m["user_id"],
                                        "type": "order",
                                        "message": f"A processing merchant submitted a contract request for {order_qty} units of your produce."
                                    }).execute()
                                    
                                    st.success("Transaction routing request submitted directly to producer's private dashboard ledger.")
                                except Exception as err:
                                    st.error(str(err))
                else:
                    st.warning("No active producer supply nodes currently matches your specified criteria filter.")

    with tab2:
        st.subheader("Active Bulk Purchase Commitments")
        my_orders = safe_query(supabase.table("orders").select("*, profiles!orders_seller_id_fkey(full_name)").eq("buyer_id", user_id))
        if my_orders:
            df_mo = pd.DataFrame(my_orders)
            st.dataframe(df_mo[["id", "quantity_ordered", "total_price_birr", "status", "notes", "created_at"]], use_container_width=True)
        else:
            st.info("You haven't initiated any sourcing agreements yet.")

    with tab3:
        st.subheader("Decentralized Demand Forecasting Model")
        st.write("Predict future volume requests dynamically by parsing global macro data inputs.")
        target_commodity = st.selectbox("Select Commodity to Forecast", ["White Teff", "Export Grade Coffee", "Red Pulses"])
        
        if st.button("Run Predictive Model Pipeline"):
            forecast_data = forecast_demand(target_commodity)
            st.success(f"Forecast Model successfully calibrated with confidence intervals of {forecast_data['confidence']}%")
            
            # Simple future line trend
            future_dates = [datetime.date.today() + datetime.timedelta(days=x) for x in range(0, 60, 10)]
            demand_index = forecast_data["projected_index_curve"]
            f_df = pd.DataFrame({"Timeline Edge": future_dates, "Aggregated Volume Demand": demand_index}).set_index("Timeline Edge")
            st.line_chart(f_df)

# ════════════════════════════════════════════════════════════
# DASHBOARD ROLES: CUSTOMER / CONSUMER LOGIC
# ════════════════════════════════════════════════════════════
def render_customer_dashboard(user_id):
    st.title("🛒 End Consumer / Retail Marketplace")
    st.write("Browse certified high-quality commodities ready for direct institutional or personal delivery.")
    
    # Active inventory listing cards
    all_items = safe_query(supabase.table("inventory").select("*, profiles!inventory_user_id_fkey(full_name)").eq("status", "available"))
    
    if not all_items:
        st.info("No retail commodities currently open on the open market.")
        return
        
    st.subheader("Available Commodities Listing")
    
    # Setup grid formatting layout 
    for item in all_items:
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"#### 🌾 {item['product_name']} ({item['category']})")
                st.write(f"**Origin Farmer Nod:** {item.get('profiles', {}).get('full_name', 'Verified Supplier')}")
                st.write(f"**Detailed Batch Metrics:** {item.get('description', 'No descriptive specifications provided.')}")
            with col2:
                st.markdown(f"### {item['price_per_unit']:,} Birr")
                st.write(f"Available Quantity: {item['quantity']} Qtl")
                
                # Order overlay dialog box inside expander
                with st.expander("🛒 Place Order"):
                    c_qty = st.number_input("Order Volume Needed", min_value=1.0, max_value=float(item['quantity']), key=f"cqty_{item['id']}")
                    if st.button("Confirm Purchase", key=f"cbtn_{item['id']}", type="primary", use_container_width=True):
                        total_cost = c_qty * item['price_per_unit']
                        try:
                            supabase.table("orders").insert({
                                "buyer_id": user_id,
                                "seller_id": item["user_id"],
                                "inventory_id": item["id"],
                                "quantity_ordered": c_qty,
                                "total_price_birr": total_cost,
                                "status": "pending"
                            }).execute()
                            
                            # Log safe automated warning risk verification
                            risk = check_fraud_risk(user_id)
                            if risk > 65:
                                supabase.table("notifications").insert({"user_id": item["user_id"], "type": "fraud", "message": "High high frequency risk signal anomaly flagged on incoming user purchase."}).execute()
                            
                            st.success("Order dispatched directly into the seller's secure fulfillment stack.")
                        except Exception as ex:
                            st.error(str(ex))
            st.markdown("---")

# ════════════════════════════════════════════════════════════
# DASHBOARD ROLES: ADMIN SUPER-VISOR CONTROL PANEL
# ════════════════════════════════════════════════════════════
def render_admin_dashboard():
    st.title("🛡️ Central System Administration Ledger")
    st.write("Cross-network operations auditing view monitor.")
    
    m_tab1, m_tab2 = st.tabs(["🔒 Global Escrow Orders Ledger", "👥 Platform Profiles Administration"])
    
    with m_tab1:
        st.subheader("Audit Log Control Matrix")
        all_orders = safe_query(supabase.table("orders").select("*"))
        if all_orders:
            for o in all_orders:
                with st.expander(f"Modify Order Node Record #{o['id'][:8]}"):
                    upd_col1, upd_col2 = st.columns(2)
                    with upd_col1:
                        new_qty    = st.number_input("Quantity", value=float(o["quantity_ordered"]), key=f'upd_qty_{o["id"]}')
                        new_status = st.selectbox("Status", ["pending","confirmed","delivered","cancelled"],
                                                               index=["pending","confirmed","delivered","cancelled"].index(o["status"]),
                                                               key=f'upd_status_{o["id"]}')
                    with upd_col2:
                        unit_price = o["total_price_birr"] / o["quantity_ordered"] if o["quantity_ordered"] else 0
                        new_total  = new_qty * unit_price
                        st.metric("New Total", f"{new_total:,.0f} Birr")
                        new_notes  = st.text_area("Notes", value=o.get("notes") or "", key=f'upd_notes_{o["id"]}')
                    if st.button("💾 Save Changes", key=f'upd_save_{o["id"]}', use_container_width=True):
                        try:
                            supabase.table("orders").update({
                                 "quantity_ordered": new_qty,
                                 "total_price_birr": new_total,
                                 "notes": new_notes, 
                                 "status": new_status,
                            }).eq("id", o["id"]).execute() 
                            st.success("System ledger update committed successfully.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating order: {e}")
        else:
            st.info("No transaction orders logged globally on data schema arrays.")
            
    with m_tab2:
        st.subheader("Registered Platform Entities")
        profiles = safe_query(supabase.table("profiles").select("*"))
        if profiles:
            st.dataframe(pd.DataFrame(profiles), use_container_width=True)

# ════════════════════════════════════════════════════════════
# CORE CONTROLLER ROUTER ARCHITECTURE
# ════════════════════════════════════════════════════════════
def main():
    # Session state validation properties Initialization
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = None
    if "role" not in st.session_state:
        st.session_state["role"] = "guest"
    if "full_name" not in st.session_state:
        st.session_state["full_name"] = None

    user_id = st.session_state["user_id"]
    role = st.session_state["role"]

    # Top Navigation Layout Header bar
    col_t1, col_t2 = st.columns([4, 1])
    with col_t1:
        st.markdown("# 🌾 Agro-Chain Intelligence Platform")
        st.caption("Decentralized AI Optimization Sourcing Platform | Wolaita Sodo University Department of ECE")
    with col_t2:
        if user_id:
            st.write(f"👤 {st.session_state['full_name']}")
            st.caption(f"Role Badge: {role.upper()}")
            if st.button("🚪 Leave Session", use_container_width=True):
                handle_logout()
        else:
            st.caption("🔐 Public Guest Secure Entry Node")

    # Render Active System Alerts Sidebar context if user authenticated
    if user_id:
        render_notifications_sidebar(user_id)

    st.markdown("---")

    # Primary Navigation Conditional Branching Switch Routing Logic Matrix
    if role == "producer":
        render_producer_dashboard(user_id)
    elif role == "merchant":
        render_merchant_dashboard(user_id)
    elif role == "customer":
        render_customer_dashboard(user_id)
    elif role == "admin":
        render_admin_dashboard()
    else:
        # Fallback view for unauthenticated users / "guest" role
        st.title("🌾 Welcome to the Ethiopian AI Supply Chain Platform")
        st.markdown(
            """
            This platform leverages machine learning and real-time market indexing to optimize the 
            agricultural supply chain, enabling seamless direct trading connections between smallholder farmers, 
            commercial processing hubs, and consumers.
            """
        )
        
        # Display authentication panels so users can log in or register
        auth_tab1, auth_tab2 = st.tabs(["🔐 Sign In to Account", "📝 Register New Entity"])
        
        with auth_tab1:
            render_login_form()
            
        with auth_tab2:
            render_register_form()

if __name__ == "__main__":
    main()
