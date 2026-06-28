"""
AI-Powered Supply Chain System — Stage 5: Demand Forecasting
Wolaita Sodo University | Department of ECE
"""
import streamlit as st
import pandas as pd
from src.db import get_supabase_client
from src.matching_engine import rank_merchants
from src.price_engine import recommend_price
from src.fraud_engine import check_fraud_risk
from src.demand_engine import forecast_demand

# ── PAGE CONFIG ──────────────────────────────────────────────
st.set_page_config(
    page_title="Ethiopian AI Supply Chain",
    page_icon="🌾",
    layout="wide"
)

# ── SESSION STATE INIT ───────────────────────────────────────
for key in ["user", "profile", "edit_product_id", "show_pref_form",
            "agreement_product_id", "agreement_merchant"]:
    if key not in st.session_state:
        st.session_state[key] = None

try:
    supabase = get_supabase_client()
except ValueError as e:
    st.error(str(e))
    st.stop()


# ── HELPER FUNCTIONS ──────────────────────────────────────────
def get_profile(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    return res.data[0] if res.data else None

def sign_up(email, password, full_name, role, region, phone, merchant_prefs=None):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number."
    if not any(c.isalpha() for c in password):
        return False, "Password must contain at least one letter."
    try:
        auth_res = supabase.auth.sign_up({"email": email, "password": password})
        if auth_res.user is None:
            return False, "Sign up failed. Email may already be registered."
        user_id = auth_res.user.id
        profile_data = {"id": user_id, "full_name": full_name, "role": role,
                        "region": region, "phone": phone}
        if role == "merchant" and merchant_prefs:
            profile_data.update(merchant_prefs)
        supabase.table("profiles").insert(profile_data).execute()
        return True, "Account created! Please log in."
    except Exception as e:
        return False, f"Sign up failed: {str(e)}"

def sign_in(email, password):
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if auth_res.user:
            st.session_state.user = auth_res.user
            st.session_state.profile = get_profile(auth_res.user.id)
            return True, "Logged in successfully."
        return False, "Invalid credentials."
    except Exception as e:
        return False, f"Login failed: {e}"

def sign_out():
    supabase.auth.sign_out()
    for key in ["user", "profile", "edit_product_id", "show_pref_form",
                "agreement_product_id", "agreement_merchant"]:
        st.session_state[key] = None

REGIONS = ["Addis Ababa", "Oromia", "SNNPR", "Amhara", "Tigray", "Sidama", "Dire Dawa", "Harari"]
SECTORS = ["Agriculture", "Manufacturing", "Handicrafts", "Livestock", "Food Processing", "Textiles", "Services"]
UNITS   = ["quintal", "kg", "piece", "head", "unit", "meter", "service"]
GRADES  = ["A", "B", "C"]


# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.title("🌾 AI Supply Chain")
    st.caption("Ethiopian Multi-Sector Commerce")
    st.divider()

    if st.session_state.user is None:
        tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

        with tab_login:
            login_email = st.text_input("Email", key="login_email")
            login_pass  = st.text_input("Password", type="password", key="login_pass")
            if st.button("Log In", use_container_width=True):
                ok, msg = sign_in(login_email, login_pass)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with tab_signup:
            su_name   = st.text_input("Full Name", key="su_name")
            su_email  = st.text_input("Email", key="su_email")
            su_pass   = st.text_input("Password", type="password", key="su_pass",
                                      help="Min 8 chars, letters + numbers")
            su_role   = st.selectbox("I am a...", ["producer", "merchant", "customer"], key="su_role")
            su_region = st.selectbox("Region", REGIONS, key="su_region")
            su_phone  = st.text_input("Phone Number", key="su_phone")

            merchant_prefs = None
            if su_role == "merchant":
                st.caption("🏪 Buying preferences — powers AI matching")
                merchant_prefs = {
                    "preferred_sector":  st.selectbox("Preferred Sector", SECTORS, key="pref_sector"),
                    "preferred_product": st.text_input("Preferred Product", key="pref_product"),
                    "max_budget_birr":   st.number_input("Max Budget (Birr)", min_value=0.0, step=1000.0, key="pref_budget"),
                    "preferred_quality": st.selectbox("Preferred Quality", ["A", "B", "A or B", "Any"], key="pref_quality"),
                    "needs_delivery":    st.checkbox("I need delivery", key="pref_delivery"),
                    "payment_method":    st.selectbox("Payment Method", ["Cash", "Bank Transfer", "Mobile Money", "Credit"], key="pref_payment"),
                }

            if st.button("Create Account", use_container_width=True):
                if not su_name or not su_email or not su_pass:
                    st.warning("Please fill in all required fields.")
                else:
                    ok, msg = sign_up(su_email, su_pass, su_name, su_role, su_region, su_phone, merchant_prefs)
                    st.success(msg) if ok else st.error(msg)
    else:
        profile = st.session_state.profile
        st.success(f"Welcome, {profile['full_name'] if profile else 'User'}")
        st.caption(f"Role: {profile['role'].capitalize() if profile else 'N/A'}")
        st.caption(f"Region: {profile['region'] if profile else 'N/A'}")
        if st.button("Log Out", use_container_width=True):
            sign_out()
            st.rerun()


# ── MAIN ─────────────────────────────────────────────────────
if st.session_state.user is None:
    st.title("Welcome to the Ethiopian AI Supply Chain Platform")
    st.write("A unified marketplace connecting **producers**, **merchants**, and **customers** across Ethiopia.")
    st.info("Please log in or sign up using the sidebar to get started.")
    st.stop()

profile = st.session_state.profile
role    = profile["role"] if profile else None

# Build tabs based on role
if role == "producer":
    tabs = st.tabs(["📦 Browse", "➕ Add Product", "📋 My Listings", "⚙️ Profile"])
    tab_browse, tab_add, tab_listings, tab_profile = tabs
elif role == "merchant":
    tabs = st.tabs(["📦 Browse", "🛒 My Orders", "⚙️ Profile"])
    tab_browse, tab_orders, tab_profile = tabs
else:  # customer
    tabs = st.tabs(["📦 Browse", "🛒 My Orders", "⚙️ Profile"])
    tab_browse, tab_orders, tab_profile = tabs


# ════════════════════════════════════════════════════════════
# TAB: BROWSE PRODUCTS
# ════════════════════════════════════════════════════════════
with tab_browse:
    st.subheader("Browse Available Products")

    col1, col2, col3 = st.columns(3)
    with col1:
        filter_sector = st.selectbox("Sector", ["All"] + SECTORS, key="browse_sector")
    with col2:
        filter_region = st.selectbox("Region", ["All"] + REGIONS, key="browse_region")
    with col3:
        search_term = st.text_input("🔍 Search", key="browse_search")

    query = supabase.table("products").select("*, profiles(full_name, region)").eq("is_available", True)
    if filter_sector != "All":
        query = query.eq("sector", filter_sector)
    if filter_region != "All":
        query = query.eq("region", filter_region)

    try:
        products = query.execute().data
        if search_term:
            products = [p for p in products if search_term.lower() in p["product_name"].lower()]
    except Exception as e:
        st.error(f"Could not load products: {e}")
        products = []

    if not products:
        st.info("No products found.")
    else:
        for p in products:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(f"**{p['product_name']}** · {p['sector']} · Grade **{p['quality_grade']}**")
                    st.caption(p.get("description") or "No description")
                    seller = p.get("profiles")
                    if seller:
                        st.caption(f"👤 {seller.get('full_name', 'Unknown')} · 📍 {p['region']}")
                with c2:
                    st.metric("Price", f"{p['price_birr']:,.0f} Birr")
                    st.caption(f"Available: {p['quantity']} {p['unit']}")
                with c3:
                    if role in ("merchant", "customer"):
                        qty_to_order = st.number_input(
                            "Qty", min_value=1.0, max_value=float(p["quantity"]),
                            value=1.0, key=f"qty_{p['id']}"
                        )
                        total = qty_to_order * p["price_birr"]
                        st.caption(f"Total: **{total:,.0f} Birr**")

                        try:
                            risk = check_fraud_risk(
                                sector=p["sector"], product=p["product_name"],
                                region=p["region"], payment_method="Bank Transfer",
                                quantity=qty_to_order, agreed_price_birr=p["price_birr"],
                                market_price_birr=p["price_birr"],
                            )
                            badge = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}[risk["risk_level"]]
                            st.caption(f"{badge} Fraud Risk: **{risk['risk_level']}**")
                        except Exception:
                            risk = {"risk_level": "Unknown", "is_fraud": 0, "fraud_probability": 0.0}

                        if st.button("🛒 Place Order", key=f"order_{p['id']}"):
                            if risk["risk_level"] == "High":
                                st.warning("⚠️ High fraud risk — proceed with caution.")
                            try:
                                supabase.table("orders").insert({
                                    "product_id": p["id"],
                                    "buyer_id": st.session_state.user.id,
                                    "quantity_ordered": qty_to_order,
                                    "total_price_birr": total,
                                    "status": "pending",
                                    "fraud_risk_level": risk["risk_level"],
                                    "fraud_probability": risk["fraud_probability"],
                                }).execute()
                                st.success(f"✅ Order placed — {total:,.0f} Birr")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Order failed: {e}")
                    else:
                        st.caption("📍 " + p["region"])


# ════════════════════════════════════════════════════════════
# TAB: ADD PRODUCT (Producer only)
# ════════════════════════════════════════════════════════════
if role == "producer":
    with tab_add:
        st.subheader("➕ Add New Product")

        p_sector  = st.selectbox("Sector", SECTORS, key="add_sector")
        p_name    = st.text_input("Product Name", key="add_name")
        p_quality = st.selectbox("Quality Grade", GRADES, key="add_quality")
        p_region  = st.selectbox("Region", REGIONS,
                        index=REGIONS.index(profile["region"]) if profile.get("region") in REGIONS else 0,
                        key="add_region")

        if p_name:
            try:
                rec = recommend_price(sector=p_sector, product=p_name, region=p_region, quality_grade=p_quality)
                st.info(f"💰 AI Suggested Price: **{rec['recommended_price']:,.0f} Birr** "
                        f"(range: {rec['min_price']:,.0f} – {rec['max_price']:,.0f} Birr)")
            except Exception:
                pass

        with st.form("add_product_form"):
            p_qty   = st.number_input("Quantity", min_value=0.1, step=1.0, key="add_qty")
            p_unit  = st.selectbox("Unit", UNITS, key="add_unit")
            p_price = st.number_input("Price per Unit (Birr)", min_value=1.0, step=10.0, key="add_price")
            p_desc  = st.text_area("Description (optional)", key="add_desc")

            if st.form_submit_button("✅ Submit Listing", use_container_width=True):
                if not p_name or p_qty <= 0 or p_price <= 0:
                    st.warning("Fill in product name, quantity, and price.")
                else:
                    try:
                        supabase.table("products").insert({
                            "producer_id":   st.session_state.user.id,
                            "sector":        p_sector,
                            "product_name":  p_name,
                            "quantity":      p_qty,
                            "unit":          p_unit,
                            "price_birr":    p_price,
                            "quality_grade": p_quality,
                            "region":        p_region,
                            "description":   p_desc,
                            "is_available":  True
                        }).execute()
                        st.success(f"✅ '{p_name}' listed successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to list product: {e}")


# ════════════════════════════════════════════════════════════
# TAB: MY LISTINGS (Producer only)
# ════════════════════════════════════════════════════════════
if role == "producer":
    with tab_listings:
        st.subheader("📋 My Listings")

        # ── INCOMING ORDERS TO ACCEPT/REJECT ────────────────
        try:
            incoming_orders = supabase.table("orders") \
                .select("*, products(product_name, unit, price_birr), profiles(full_name, phone, region)") \
                .eq("status", "pending") \
                .execute().data

            # Filter to only orders for THIS producer's products
            my_product_ids = []
            try:
                my_prods_raw = supabase.table("products").select("id") \
                    .eq("producer_id", st.session_state.user.id).execute().data
                my_product_ids = [p["id"] for p in my_prods_raw]
            except Exception:
                pass

            incoming_orders = [o for o in incoming_orders if o["product_id"] in my_product_ids]
        except Exception as e:
            incoming_orders = []

        if incoming_orders:
            st.markdown("### 📬 Incoming Orders")
            for o in incoming_orders:
                prod        = o.get("products") or {}
                buyer       = o.get("profiles") or {}
                pname       = prod.get("product_name", "Unknown")
                unit        = prod.get("unit", "")
                buyer_name  = buyer.get("full_name", "Unknown buyer")
                buyer_phone = buyer.get("phone", "N/A")
                buyer_region = buyer.get("region", "N/A")

                with st.container(border=True):
                    st.markdown(f"🛒 **Order for {pname}**")
                    col_info, col_actions = st.columns([3, 2])
                    with col_info:
                        st.caption(f"👤 Buyer: **{buyer_name}** · 📍 {buyer_region}")
                        st.caption(f"📞 Phone: {buyer_phone}")
                        st.caption(f"Qty: {o['quantity_ordered']} {unit} · Total: **{o['total_price_birr']:,.0f} Birr**")
                        risk_lvl = o.get("fraud_risk_level", "Unknown")
                        rb = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk_lvl, "⚪")
                        st.caption(f"{rb} Fraud Risk: **{risk_lvl}**")
                    with col_actions:
                        col_acc, col_rej = st.columns(2)
                        with col_acc:
                            if st.button("✅ Accept", key=f"accept_order_{o['id']}", use_container_width=True):
                                try:
                                    supabase.table("orders").update(
                                        {"status": "confirmed"}
                                    ).eq("id", o["id"]).execute()
                                    st.success(f"Order accepted! Contact {buyer_name} at {buyer_phone}.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")
                        with col_rej:
                            if st.button("❌ Reject", key=f"reject_order_{o['id']}", use_container_width=True):
                                try:
                                    supabase.table("orders").update(
                                        {"status": "cancelled"}
                                    ).eq("id", o["id"]).execute()
                                    st.info("Order rejected.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")
            st.divider()

        # ── AGREEMENT MODAL ──────────────────────────────────
        if st.session_state.agreement_product_id and st.session_state.agreement_merchant:
            m   = st.session_state.agreement_merchant
            pid = st.session_state.agreement_product_id
            try:
                prod_res = supabase.table("products").select("*").eq("id", pid).execute()
                prod     = prod_res.data[0] if prod_res.data else {}
            except Exception:
                prod = {}

            st.markdown("---")
            st.markdown(f"### 🤝 Make Agreement with **{m['name']}**")

            with st.container(border=True):
                col_contact, col_agreement = st.columns(2)

                with col_contact:
                    st.markdown("#### 📞 Contact Details")
                    st.markdown(f"**Name:** {m['name']}")
                    st.markdown(f"**Region:** {m.get('region', 'N/A')}")
                    phone = m.get("phone") or "Not provided"
                    st.markdown(f"**Phone:** {phone}")
                    st.markdown(f"**Preferred Product:** {m.get('preferred_product') or 'N/A'}")
                    st.markdown(f"**Payment Method:** {m.get('payment_method') or 'N/A'}")
                    st.markdown(f"**Max Budget:** {m.get('max_budget_birr', 0):,.0f} Birr")

                with col_agreement:
                    st.markdown("#### 📝 Agreement Terms")
                    agr_qty   = st.number_input("Quantity to Agree",
                                                min_value=0.1,
                                                max_value=float(prod.get("quantity", 1000)),
                                                value=min(10.0, float(prod.get("quantity", 10))),
                                                step=1.0, key="agr_qty")
                    agr_price = st.number_input("Agreed Price per Unit (Birr)",
                                                min_value=1.0,
                                                value=float(prod.get("price_birr", 100)),
                                                step=10.0, key="agr_price")
                    agr_delivery = st.date_input("Delivery Date", key="agr_delivery")
                    agr_payment  = st.selectbox("Payment Method",
                                                ["Cash", "Bank Transfer", "Mobile Money", "Credit"],
                                                key="agr_payment")
                    agr_notes = st.text_area("Additional Notes (optional)", key="agr_notes")

                    agr_total = agr_qty * agr_price
                    st.info(f"💰 Agreement Total: **{agr_total:,.0f} Birr**")

                col_send, col_cancel = st.columns(2)
                with col_send:
                    if st.button("✅ Send Agreement & Create Order", use_container_width=True, key="send_agreement"):
                        try:
                            supabase.table("orders").insert({
                                "product_id":        pid,
                                "buyer_id":          m["id"],
                                "quantity_ordered":  agr_qty,
                                "total_price_birr":  agr_total,
                                "status":            "confirmed",
                                "fraud_risk_level":  "Low",
                                "fraud_probability": 0.05,
                                "notes": (
                                    f"Producer-initiated agreement. "
                                    f"Payment: {agr_payment}. "
                                    f"Delivery: {agr_delivery}. "
                                    f"{agr_notes}"
                                ),
                            }).execute()
                            st.success(
                                f"✅ Agreement sent to **{m['name']}**! "
                                f"Contact them at **{phone}** to confirm delivery."
                            )
                            st.session_state.agreement_product_id = None
                            st.session_state.agreement_merchant   = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to create agreement: {e}")
                with col_cancel:
                    if st.button("✖ Cancel", use_container_width=True, key="cancel_agreement"):
                        st.session_state.agreement_product_id = None
                        st.session_state.agreement_merchant   = None
                        st.rerun()
            st.markdown("---")

        # ── PRODUCT LISTINGS ─────────────────────────────────
        try:
            my_products = supabase.table("products").select("*") \
                .eq("producer_id", st.session_state.user.id) \
                .order("created_at", desc=True).execute().data
        except Exception as e:
            st.error(f"Could not load listings: {e}")
            my_products = []

        if not my_products:
            st.info("You haven't listed any products yet. Go to ➕ Add Product.")
        else:
            for p in my_products:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{p['product_name']}** · {p['sector']} · Grade {p['quality_grade']}")
                        st.caption(f"{p['quantity']} {p['unit']} @ {p['price_birr']:,.0f} Birr | {p['region']}")
                        st.caption(p.get("description") or "")
                    with c2:
                        st.caption("🟢 Active" if p["is_available"] else "🔴 Inactive")

                    col_toggle, col_edit, col_delete = st.columns(3)

                    # ── TOGGLE STATUS ──
                    with col_toggle:
                        label = "⏸ Deactivate" if p["is_available"] else "▶ Activate"
                        if st.button(label, key=f"toggle_{p['id']}", use_container_width=True):
                            try:
                                supabase.table("products").update(
                                    {"is_available": not p["is_available"]}
                                ).eq("id", p["id"]).execute()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Update failed: {e}")

                    # ── EDIT ──
                    with col_edit:
                        if st.button("✏️ Edit", key=f"edit_btn_{p['id']}", use_container_width=True):
                            st.session_state.edit_product_id = p["id"]

                    # ── DELETE ──
                    with col_delete:
                        if st.button("🗑️ Delete", key=f"del_{p['id']}", use_container_width=True):
                            try:
                                supabase.table("products").delete().eq("id", p["id"]).execute()
                                st.success(f"'{p['product_name']}' deleted.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")

                    # ── EDIT FORM (inline) ──
                    if st.session_state.edit_product_id == p["id"]:
                        st.markdown("---")
                        st.markdown("**✏️ Edit Product**")
                        with st.form(f"edit_form_{p['id']}"):
                            e_name    = st.text_input("Product Name", value=p["product_name"])
                            e_sector  = st.selectbox("Sector", SECTORS, index=SECTORS.index(p["sector"]) if p["sector"] in SECTORS else 0)
                            e_quality = st.selectbox("Grade", GRADES, index=GRADES.index(p["quality_grade"]) if p["quality_grade"] in GRADES else 0)
                            e_region  = st.selectbox("Region", REGIONS, index=REGIONS.index(p["region"]) if p["region"] in REGIONS else 0)
                            e_qty     = st.number_input("Quantity", min_value=0.1, value=float(p["quantity"]), step=1.0)
                            e_unit    = st.selectbox("Unit", UNITS, index=UNITS.index(p["unit"]) if p["unit"] in UNITS else 0)
                            e_price   = st.number_input("Price (Birr)", min_value=1.0, value=float(p["price_birr"]), step=10.0)
                            e_desc    = st.text_area("Description", value=p.get("description") or "")

                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                save = st.form_submit_button("💾 Save Changes", use_container_width=True)
                            with col_cancel:
                                cancel = st.form_submit_button("✖ Cancel", use_container_width=True)

                            if save:
                                try:
                                    supabase.table("products").update({
                                        "product_name":  e_name,
                                        "sector":        e_sector,
                                        "quality_grade": e_quality,
                                        "region":        e_region,
                                        "quantity":      e_qty,
                                        "unit":          e_unit,
                                        "price_birr":    e_price,
                                        "description":   e_desc,
                                    }).eq("id", p["id"]).execute()
                                    st.success("Product updated!")
                                    st.session_state.edit_product_id = None
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Update failed: {e}")
                            if cancel:
                                st.session_state.edit_product_id = None
                                st.rerun()

                    # ── AI MATCHING ──
                    st.markdown("---")
                    if st.button("🤖 Find Best Merchant Matches", key=f"match_{p['id']}", use_container_width=True):
                        with st.spinner("Scoring merchants..."):
                            try:
                                merchants_raw = supabase.table("profiles").select("*").eq("role", "merchant").execute().data
                                listing_data  = {
                                    "sector": p["sector"], "product_name": p["product_name"],
                                    "price_birr": p["price_birr"], "quantity": p["quantity"],
                                    "quality_grade": p["quality_grade"], "region": p["region"],
                                    "is_verified": 1, "delivery_available": 1,
                                    "producer_rating": 4.0, "producer_experience": 3,
                                    "producer_tx": 0, "return_rate": 0.05,
                                }
                                merchant_list = [{
                                    "id": m["id"],
                                    "name": m["full_name"],
                                    "phone": m.get("phone"),
                                    "preferred_sector":    m.get("preferred_sector"),
                                    "preferred_product":   m.get("preferred_product"),
                                    "region":              m.get("region"),
                                    "max_budget_birr":     m.get("max_budget_birr") or 0,
                                    "preferred_quality":   m.get("preferred_quality") or "Any",
                                    "needs_delivery":      m.get("needs_delivery") or False,
                                    "is_verified":         m.get("is_verified", True),
                                    "rating":              m.get("rating") or 4.0,
                                    "total_transactions":  m.get("total_transactions") or 0,
                                    "years_in_business":   m.get("years_in_business") or 1,
                                    "return_rate":         m.get("return_rate") or 0.05,
                                    "payment_method":      m.get("payment_method"),
                                } for m in merchants_raw]

                                if not merchant_list:
                                    st.warning("No merchants registered yet.")
                                else:
                                    ranked      = rank_merchants(listing_data, merchant_list)
                                    top_matches = [r for r in ranked if r["match_probability"] > 0.1][:5]
                                    if not top_matches:
                                        st.info("No strong matches found.")
                                    else:
                                        st.markdown("**Top Matched Merchants:**")
                                        for r in top_matches:
                                            pct   = r["match_probability"] * 100
                                            badge = "🟢" if r["is_match"] == 1 else "🟡"

                                            mcol1, mcol2 = st.columns([3, 1])
                                            with mcol1:
                                                st.write(
                                                    f"{badge} **{r['name']}** — {pct:.1f}% match · "
                                                    f"{r['region']} · wants {r.get('preferred_product') or 'N/A'} · "
                                                    f"📞 {r.get('phone') or 'N/A'}"
                                                )
                                            with mcol2:
                                                if st.button(
                                                    "🤝 Make Agreement",
                                                    key=f"agr_{p['id']}_{r['id']}",
                                                    use_container_width=True
                                                ):
                                                    st.session_state.agreement_product_id = p["id"]
                                                    st.session_state.agreement_merchant   = r
                                                    st.rerun()
                            except Exception as e:
                                st.error(f"Matching failed: {e}")

                    # ── DEMAND FORECAST ──
                    try:
                        fc = forecast_demand(p["product_name"], p["region"], weeks_ahead=4)
                    except Exception:
                        fc = None

                    if fc and "error" not in fc:
                        trend_icon  = {"up": "🟢 ↑ Rising", "down": "🔴 ↓ Falling", "stable": "🟡 → Stable"}[fc["trend"]]
                        st.caption(f"📈 Demand Forecast | {trend_icon} | R²={fc['r2']:.2f} RMSE=±{fc['rmse']:,.0f}")
                        all_labels  = [f"W-{7-i}" for i in range(8)] + [f"+{w}w" for w in fc["weeks"]]
                        hist_series = fc["historical"] + [None] * 4
                        fc_series   = [None] * 7 + [fc["historical"][-1]] + fc["forecast"]
                        chart_data  = pd.DataFrame({"Actual": hist_series, "Forecast": fc_series}, index=all_labels)
                        st.line_chart(chart_data, color=["#4A90D9", "#F5A623"], height=180)
                    else:
                        st.caption("📈 Demand forecast unavailable.")


# ════════════════════════════════════════════════════════════
# TAB: MY ORDERS (Merchant / Customer)
# ════════════════════════════════════════════════════════════
if role in ("merchant", "customer"):
    with tab_orders:
        st.subheader("🛒 My Orders")

        # ── MERCHANT BUYING PREFERENCES DASHBOARD ───────────
        if role == "merchant":
            has_prefs = profile.get("preferred_product") or profile.get("preferred_sector")
            if not has_prefs:
                st.warning("⚠️ You haven't set your buying preferences yet. Set them below to enable AI matching.")
                with st.expander("🏪 Set Buying Preferences", expanded=True):
                    pref_sector   = st.selectbox("Preferred Sector", SECTORS, key="dash_pref_sector")
                    pref_product  = st.text_input("Preferred Product (e.g. Teff, Coffee)", key="dash_pref_product")
                    pref_budget   = st.number_input("Max Budget (Birr)", min_value=0.0, step=1000.0, key="dash_pref_budget")
                    pref_quality  = st.selectbox("Preferred Quality", ["A", "B", "A or B", "Any"], key="dash_pref_quality")
                    pref_delivery = st.checkbox("I need delivery", key="dash_pref_delivery")
                    pref_payment  = st.selectbox("Payment Method", ["Cash", "Bank Transfer", "Mobile Money", "Credit"], key="dash_pref_payment")

                    if st.button("💾 Save Preferences", use_container_width=True, key="dash_save_prefs"):
                        try:
                            supabase.table("profiles").update({
                                "preferred_sector":  pref_sector,
                                "preferred_product": pref_product,
                                "max_budget_birr":   pref_budget,
                                "preferred_quality": pref_quality,
                                "needs_delivery":    pref_delivery,
                                "payment_method":    pref_payment,
                            }).eq("id", st.session_state.user.id).execute()
                            st.success("✅ Preferences saved! AI matching is now active.")
                            st.session_state.profile = get_profile(st.session_state.user.id)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to save: {e}")
            else:
                st.info(
                    f"🤖 AI Matching active — looking for **{profile.get('preferred_product', 'N/A')}** "
                    f"in **{profile.get('preferred_sector', 'N/A')}** · "
                    f"Budget: **{profile.get('max_budget_birr', 0):,.0f} Birr** · "
                    f"Quality: **{profile.get('preferred_quality', 'Any')}**"
                )
                if st.button("✏️ Update Preferences", key="dash_update_prefs"):
                    st.session_state.show_pref_form = True

                if st.session_state.get("show_pref_form"):
                    with st.expander("🏪 Update Buying Preferences", expanded=True):
                        pref_sector   = st.selectbox("Preferred Sector", SECTORS,
                            index=SECTORS.index(profile.get("preferred_sector")) if profile.get("preferred_sector") in SECTORS else 0,
                            key="upd_pref_sector")
                        pref_product  = st.text_input("Preferred Product", value=profile.get("preferred_product") or "", key="upd_pref_product")
                        pref_budget   = st.number_input("Max Budget (Birr)", min_value=0.0, step=1000.0,
                            value=float(profile.get("max_budget_birr") or 0), key="upd_pref_budget")
                        pref_quality  = st.selectbox("Preferred Quality", ["A", "B", "A or B", "Any"],
                            index=["A", "B", "A or B", "Any"].index(profile.get("preferred_quality") or "Any"),
                            key="upd_pref_quality")
                        pref_delivery = st.checkbox("I need delivery", value=profile.get("needs_delivery") or False, key="upd_pref_delivery")
                        pref_payment  = st.selectbox("Payment Method", ["Cash", "Bank Transfer", "Mobile Money", "Credit"],
                            index=["Cash", "Bank Transfer", "Mobile Money", "Credit"].index(profile.get("payment_method") or "Cash"),
                            key="upd_pref_payment")

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("💾 Save", use_container_width=True, key="upd_save"):
                                try:
                                    supabase.table("profiles").update({
                                        "preferred_sector":  pref_sector,
                                        "preferred_product": pref_product,
                                        "max_budget_birr":   pref_budget,
                                        "preferred_quality": pref_quality,
                                        "needs_delivery":    pref_delivery,
                                        "payment_method":    pref_payment,
                                    }).eq("id", st.session_state.user.id).execute()
                                    st.success("✅ Preferences updated!")
                                    st.session_state.profile = get_profile(st.session_state.user.id)
                                    st.session_state.show_pref_form = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to save: {e}")
                        with col2:
                            if st.button("✖ Cancel", use_container_width=True, key="upd_cancel"):
                                st.session_state.show_pref_form = False
                                st.rerun()

            st.divider()

        # ── ORDERS LIST ─────────────────────────────────────
        try:
            orders = supabase.table("orders") \
                .select("*, products(product_name, unit, region, profiles(full_name))") \
                .eq("buyer_id", st.session_state.user.id) \
                .order("created_at", desc=True).execute().data
        except Exception as e:
            st.error(f"Could not load orders: {e}")
            orders = []

        if not orders:
            st.info("You haven't placed any orders yet. Browse products to get started.")
        else:
            total_spent = sum(o["total_price_birr"] for o in orders)
            pending     = sum(1 for o in orders if o["status"] == "pending")

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Orders", len(orders))
            m2.metric("Total Spent", f"{total_spent:,.0f} Birr")
            m3.metric("Pending", pending)
            st.divider()

            status_filter   = st.selectbox("Filter by Status", ["All", "pending", "confirmed", "delivered", "cancelled"])
            filtered_orders = orders if status_filter == "All" else [o for o in orders if o["status"] == status_filter]

            for o in filtered_orders:
                prod        = o.get("products") or {}
                pname       = prod.get("product_name", "Unknown product")
                unit        = prod.get("unit", "")
                seller_name = (prod.get("profiles") or {}).get("full_name", "Unknown seller")

                status_badge = {
                    "pending":   "🟡 Pending",
                    "confirmed": "🔵 Confirmed",
                    "delivered": "🟢 Delivered",
                    "cancelled": "🔴 Cancelled",
                }.get(o["status"], o["status"])

                with st.container(border=True):
                    col_a, col_b, col_c = st.columns([3, 2, 2])
                    with col_a:
                        st.markdown(f"**{pname}**")
                        st.caption(f"Seller: {seller_name} · Region: {prod.get('region', 'N/A')}")
                        st.caption(f"Qty: {o['quantity_ordered']} {unit}")
                        if o.get("notes"):
                            st.caption(f"📝 {o['notes']}")
                    with col_b:
                        st.metric("Total", f"{o['total_price_birr']:,.0f} Birr")
                        st.caption(status_badge)
                    with col_c:
                        risk_lvl = o.get("fraud_risk_level", "Unknown")
                        if risk_lvl != "Unknown":
                            rb = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk_lvl, "⚪")
                            st.caption(f"{rb} Fraud Risk: **{risk_lvl}**")
                        if o["status"] == "pending":
                            if st.button("❌ Cancel", key=f"cancel_{o['id']}"):
                                try:
                                    supabase.table("orders").update(
                                        {"status": "cancelled"}
                                    ).eq("id", o["id"]).execute()
                                    st.success("Order cancelled.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Cancel failed: {e}")


# ════════════════════════════════════════════════════════════
# TAB: PROFILE (All roles) — defined ONCE
# ════════════════════════════════════════════════════════════
with tab_profile:
    st.subheader("⚙️ My Profile")
    st.caption(f"**{profile['full_name']}** · {profile['role'].capitalize()} · {profile['region']}")
    st.divider()

    if role == "merchant":
        st.markdown("### 🏪 Buying Preferences")
        st.caption("Update your preferences — this improves AI matching results")

        pref_sector  = st.selectbox("Preferred Sector", SECTORS,
            index=SECTORS.index(profile.get("preferred_sector")) if profile.get("preferred_sector") in SECTORS else 0,
            key="edit_pref_sector")
        pref_product = st.text_input("Preferred Product", value=profile.get("preferred_product") or "", key="edit_pref_product")
        pref_budget  = st.number_input("Max Budget (Birr)", min_value=0.0, step=1000.0,
            value=float(profile.get("max_budget_birr") or 0), key="edit_pref_budget")
        pref_quality = st.selectbox("Preferred Quality", ["A", "B", "A or B", "Any"],
            index=["A", "B", "A or B", "Any"].index(profile.get("preferred_quality") or "Any"),
            key="edit_pref_quality")
        pref_delivery = st.checkbox("I need delivery", value=profile.get("needs_delivery") or False, key="edit_pref_delivery")
        pref_payment  = st.selectbox("Payment Method", ["Cash", "Bank Transfer", "Mobile Money", "Credit"],
            index=["Cash", "Bank Transfer", "Mobile Money", "Credit"].index(profile.get("payment_method") or "Cash"),
            key="edit_pref_payment")

        if st.button("💾 Save Preferences", use_container_width=True, key="prof_save_merchant"):
            try:
                supabase.table("profiles").update({
                    "preferred_sector":  pref_sector,
                    "preferred_product": pref_product,
                    "max_budget_birr":   pref_budget,
                    "preferred_quality": pref_quality,
                    "needs_delivery":    pref_delivery,
                    "payment_method":    pref_payment,
                }).eq("id", st.session_state.user.id).execute()
                st.success("✅ Preferences saved!")
                st.session_state.profile = get_profile(st.session_state.user.id)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save: {e}")

    elif role == "producer":
        st.markdown("### 📊 My Stats")
        try:
            my_products = supabase.table("products").select("*") \
                .eq("producer_id", st.session_state.user.id).execute().data
            active   = sum(1 for p in my_products if p["is_available"])
            inactive = len(my_products) - active
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Listings", len(my_products))
            c2.metric("Active", active)
            c3.metric("Inactive", inactive)
        except Exception as e:
            st.error(f"Could not load stats: {e}")

    else:  # customer
        st.markdown("### 📊 My Stats")
        try:
            my_orders = supabase.table("orders").select("*") \
                .eq("buyer_id", st.session_state.user.id).execute().data
            total_spent = sum(o["total_price_birr"] for o in my_orders)
            c1, c2 = st.columns(2)
            c1.metric("Total Orders", len(my_orders))
            c2.metric("Total Spent", f"{total_spent:,.0f} Birr")
        except Exception as e:
            st.error(f"Could not load stats: {e}")
