"""
AI-Powered Supply Chain System — Stage 5: Demand Forecasting
Wolaita Sodo University | Department of ECE
"""
import streamlit as st
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
if "user" not in st.session_state:
    st.session_state.user = None
if "profile" not in st.session_state:
    st.session_state.profile = None

try:
    supabase = get_supabase_client()
except ValueError as e:
    st.error(str(e))
    st.stop()


# ── HELPER FUNCTIONS ──────────────────────────────────────────
def get_profile(user_id: str):
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
        profile_data = {
            "id": user_id,
            "full_name": full_name,
            "role": role,
            "region": region,
            "phone": phone
        }
        if role == "merchant" and merchant_prefs:
            profile_data.update(merchant_prefs)
        supabase.table("profiles").insert(profile_data).execute()
        return True, "Account created! Please check your email to confirm, then log in."
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
    st.session_state.user = None
    st.session_state.profile = None


REGIONS = ["Addis Ababa", "Oromia", "SNNPR", "Amhara", "Tigray", "Sidama", "Dire Dawa", "Harari"]
SECTORS = ["Agriculture", "Manufacturing", "Handicrafts", "Livestock", "Food Processing", "Textiles", "Services"]


# ── SIDEBAR: AUTH ────────────────────────────────────────────
with st.sidebar:
    st.title("🌾 AI Supply Chain")
    st.caption("Ethiopian Multi-Sector Commerce")
    st.divider()

    if st.session_state.user is None:
        tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

        with tab_login:
            login_email = st.text_input("Email", key="login_email")
            login_pass = st.text_input("Password", type="password", key="login_pass")
            if st.button("Log In", use_container_width=True):
                ok, msg = sign_in(login_email, login_pass)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with tab_signup:
            su_name = st.text_input("Full Name", key="su_name")
            su_email = st.text_input("Email", key="su_email")
            su_pass = st.text_input("Password", type="password", key="su_pass",
                                    help="Min 8 characters, must include letters and numbers")
            su_role = st.selectbox("I am a...", ["producer", "merchant", "customer"], key="su_role")
            su_region = st.selectbox("Region", REGIONS, key="su_region")
            su_phone = st.text_input("Phone Number", key="su_phone")

            merchant_prefs = None
            if su_role == "merchant":
                st.caption("🏪 Tell us what you're looking to buy — this powers AI matching")
                pref_sector = st.selectbox("Preferred Sector", SECTORS, key="pref_sector")
                pref_product = st.text_input("Preferred Product (e.g. Teff, Coffee)", key="pref_product")
                pref_budget = st.number_input("Max Budget (Birr)", min_value=0.0, step=1000.0, key="pref_budget")
                pref_quality = st.selectbox("Preferred Quality", ["A", "B", "A or B", "Any"], key="pref_quality")
                pref_delivery = st.checkbox("I need delivery", key="pref_delivery")
                pref_payment = st.selectbox("Payment Method", ["Cash", "Bank Transfer", "Mobile Money", "Credit"], key="pref_payment")
                merchant_prefs = {
                    "preferred_sector": pref_sector,
                    "preferred_product": pref_product,
                    "max_budget_birr": pref_budget,
                    "preferred_quality": pref_quality,
                    "needs_delivery": pref_delivery,
                    "payment_method": pref_payment,
                }

            if st.button("Create Account", use_container_width=True):
                if not su_name or not su_email or not su_pass:
                    st.warning("Please fill in all required fields.")
                else:
                    ok, msg = sign_up(su_email, su_pass, su_name, su_role, su_region, su_phone, merchant_prefs)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
    else:
        profile = st.session_state.profile
        st.success(f"Welcome, {profile['full_name'] if profile else 'User'}")
        st.caption(f"Role: {profile['role'].capitalize() if profile else 'N/A'}")
        st.caption(f"Region: {profile['region'] if profile else 'N/A'}")
        if st.button("Log Out", use_container_width=True):
            sign_out()
            st.rerun()


# ── MAIN AREA ─────────────────────────────────────────────────
if st.session_state.user is None:
    st.title("Welcome to the Ethiopian AI Supply Chain Platform")
    st.write(
        "A unified marketplace connecting **producers**, **merchants**, and **customers** "
        "across Ethiopia's agriculture, manufacturing, handicrafts, livestock, and service sectors."
    )
    st.info("Please log in or sign up using the sidebar to get started.")

else:
    profile = st.session_state.profile
    role = profile["role"] if profile else None

    page = st.tabs(
        ["📦 Browse Products", "🛒 My Orders", "⚙️ My Profile"] +
        (["➕ List a Product", "📋 My Listings"] if role == "producer" else [])
    )

    # ── BROWSE PRODUCTS ──────────────────────────────────────
    with page[0]:
        st.subheader("Browse Available Products")

        col1, col2, col3 = st.columns(3)
        with col1:
            filter_sector = st.selectbox("Filter by Sector", ["All"] + SECTORS)
        with col2:
            filter_region = st.selectbox("Filter by Region", ["All"] + REGIONS)
        with col3:
            search_term = st.text_input("Search product name")

        query = supabase.table("products").select("*, profiles(full_name, region)").eq("is_available", True)
        if filter_sector != "All":
            query = query.eq("sector", filter_sector)
        if filter_region != "All":
            query = query.eq("region", filter_region)

        products = query.execute().data

        if search_term:
            products = [p for p in products if search_term.lower() in p["product_name"].lower()]

        if not products:
            st.info("No products found matching your filters.")
        else:
            for p in products:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    with c1:
                        st.markdown(f"**{p['product_name']}** · {p['sector']}")
                        st.caption(p.get("description", "") or "No description")
                    with c2:
                        st.metric("Price", f"{p['price_birr']:,.0f} Birr")
                        st.caption(f"Qty: {p['quantity']} {p['unit']} | Grade {p['quality_grade']}")
                    with c3:
                        st.caption(f"📍 {p['region']}")
                        if role in ("merchant", "customer"):
                            qty_to_order = st.number_input(
                                "Quantity", min_value=1.0, max_value=float(p["quantity"]),
                                value=1.0, key=f"qty_{p['id']}"
                            )
                            total_preview = qty_to_order * p["price_birr"]
                            try:
                                risk = check_fraud_risk(
                                    sector=p["sector"], product=p["product_name"],
                                    region=p["region"], payment_method="Bank Transfer",
                                    quantity=qty_to_order, agreed_price_birr=p["price_birr"],
                                    market_price_birr=p["price_birr"],
                                )
                                badge = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}[risk["risk_level"]]
                                st.caption(f"{badge} Fraud Risk: **{risk['risk_level']}** ({risk['fraud_probability']*100:.0f}%)")
                            except Exception:
                                risk = {"risk_level": "Unknown", "is_fraud": 0, "fraud_probability": 0.0}

                            if st.button("Place Order", key=f"order_{p['id']}"):
                                if risk["risk_level"] == "High":
                                    st.warning(
                                        "⚠️ This transaction was flagged as **High Risk** by our fraud "
                                        "detection system. Please proceed with caution."
                                    )
                                try:
                                    supabase.table("orders").insert({
                                        "product_id": p["id"],
                                        "buyer_id": st.session_state.user.id,
                                        "quantity_ordered": qty_to_order,
                                        "total_price_birr": total_preview,
                                        "status": "pending",
                                        "fraud_risk_level": risk["risk_level"],
                                        "fraud_probability": risk["fraud_probability"],
                                    }).execute()
                                    st.success(f"Order placed for {qty_to_order} {p['unit']} — {total_preview:,.0f} Birr")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Order failed: {e}")

    # ── MY ORDERS ──────────────────────────────────────────────
    with page[1]:
        st.subheader("My Orders")
        try:
            orders = supabase.table("orders").select("*, products(product_name, region)") \
                .eq("buyer_id", st.session_state.user.id).order("created_at", desc=True).execute().data
            if not orders:
                st.info("You haven't placed any orders yet.")
            else:
                for o in orders:
                    with st.container(border=True):
                        pname = o["products"]["product_name"] if o.get("products") else "Unknown product"
                        st.markdown(f"**{pname}** — {o['quantity_ordered']} units")
                        st.caption(f"Total: {o['total_price_birr']:,.0f} Birr | Status: `{o['status']}`")
                        risk_lvl = o.get("fraud_risk_level", "Unknown")
                        if risk_lvl != "Unknown":
                            badge = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk_lvl, "⚪")
                            st.caption(f"{badge} Fraud Risk at time of order: **{risk_lvl}**")
        except Exception as e:
            st.error(f"Could not load orders: {e}")

    # ── MY PROFILE ──────────────────────────────────────────────
    with page[2]:
        st.subheader("My Profile")
        st.caption(f"**{profile['full_name']}** · {profile['role'].capitalize()} · {profile['region']}")
        st.divider()

        if role == "merchant":
            st.markdown("### 🏪 Buying Preferences")
            st.caption("Update what you're looking to buy — this powers AI matching")

            pref_sector = st.selectbox("Preferred Sector", SECTORS,
                index=SECTORS.index(profile.get("preferred_sector")) if profile.get("preferred_sector") in SECTORS else 0,
                key="edit_pref_sector")
            pref_product = st.text_input("Preferred Product", value=profile.get("preferred_product") or "", key="edit_pref_product")
            pref_budget = st.number_input("Max Budget (Birr)", min_value=0.0, step=1000.0,
                value=float(profile.get("max_budget_birr") or 0), key="edit_pref_budget")
            pref_quality = st.selectbox("Preferred Quality", ["A", "B", "A or B", "Any"],
                index=["A", "B", "A or B", "Any"].index(profile.get("preferred_quality") or "Any"),
                key="edit_pref_quality")
            pref_delivery = st.checkbox("I need delivery", value=profile.get("needs_delivery") or False, key="edit_pref_delivery")
            pref_payment = st.selectbox("Payment Method", ["Cash", "Bank Transfer", "Mobile Money", "Credit"],
                index=["Cash", "Bank Transfer", "Mobile Money", "Credit"].index(profile.get("payment_method") or "Cash"),
                key="edit_pref_payment")

            if st.button("💾 Save Preferences", use_container_width=True):
                try:
                    supabase.table("profiles").update({
                        "preferred_sector": pref_sector,
                        "preferred_product": pref_product,
                        "max_budget_birr": pref_budget,
                        "preferred_quality": pref_quality,
                        "needs_delivery": pref_delivery,
                        "payment_method": pref_payment,
                    }).eq("id", st.session_state.user.id).execute()
                    st.success("Preferences saved!")
                    st.session_state.profile = get_profile(st.session_state.user.id)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save: {e}")
        else:
            st.info("Profile settings for producers and customers coming soon.")

    # ── PRODUCER-ONLY: LIST A PRODUCT ───────────────────────────
    if role == "producer":
        with page[3]:
            st.subheader("List a New Product")

            p_sector = st.selectbox("Sector", SECTORS, key="new_p_sector")
            p_name = st.text_input("Product Name", key="new_p_name")
            p_quality = st.selectbox("Quality Grade", ["A", "B", "C"], key="new_p_quality")
            p_region = st.selectbox(
                "Region", REGIONS,
                index=REGIONS.index(profile["region"]) if profile["region"] in REGIONS else 0,
                key="new_p_region"
            )

            if p_name:
                try:
                    rec = recommend_price(
                        sector=p_sector, product=p_name,
                        region=p_region, quality_grade=p_quality
                    )
                    st.info(
                        f"💰 **AI Suggested Price:** {rec['recommended_price']:,.0f} Birr  "
                        f"(range: {rec['min_price']:,.0f} – {rec['max_price']:,.0f} Birr)"
                    )
                except Exception:
                    st.caption("Price suggestion unavailable for this product.")

            with st.form("new_product_form"):
                p_qty = st.number_input("Quantity Available", min_value=0.0, step=1.0)
                p_unit = st.selectbox("Unit", ["quintal", "kg", "piece", "head", "unit", "meter", "service"])
                p_price = st.number_input("Price per Unit (Birr)", min_value=0.0, step=10.0)
                p_desc = st.text_area("Description (optional)")
                submitted = st.form_submit_button("Submit Listing")

                if submitted:
                    if not p_name or p_qty <= 0 or p_price <= 0:
                        st.warning("Please fill in product name, quantity, and price.")
                    else:
                        try:
                            supabase.table("products").insert({
                                "producer_id": st.session_state.user.id,
                                "sector": p_sector,
                                "product_name": p_name,
                                "quantity": p_qty,
                                "unit": p_unit,
                                "price_birr": p_price,
                                "quality_grade": p_quality,
                                "region": p_region,
                                "description": p_desc,
                                "is_available": True
                            }).execute()
                            st.success(f"'{p_name}' listed successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to list product: {e}")

        # ── PRODUCER-ONLY: MY LISTINGS ──────────────────────────
        with page[4]:
            st.subheader("My Listings")
            try:
                my_products = supabase.table("products").select("*") \
                    .eq("producer_id", st.session_state.user.id).order("created_at", desc=True).execute().data
                if not my_products:
                    st.info("You haven't listed any products yet.")
                else:
                    for p in my_products:
                        with st.container(border=True):
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                st.markdown(f"**{p['product_name']}** · {p['sector']} · Grade {p['quality_grade']}")
                                st.caption(f"{p['quantity']} {p['unit']} @ {p['price_birr']:,.0f} Birr | {p['region']}")
                            with c2:
                                status = "🟢 Active" if p["is_available"] else "🔴 Inactive"
                                st.caption(status)
                                if st.button("Toggle Status", key=f"toggle_{p['id']}"):
                                    try:
                                        supabase.table("products").update(
                                            {"is_available": not p["is_available"]}
                                        ).eq("id", p["id"]).execute()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Update failed: {e}")

                            if st.button("🤖 Find Best Matches", key=f"match_{p['id']}"):
                                with st.spinner("Scoring compatibility with all merchants..."):
                                    try:
                                        merchants_raw = supabase.table("profiles") \
                                            .select("*").eq("role", "merchant").execute().data

                                        listing_data = {
                                            "sector": p["sector"],
                                            "product_name": p["product_name"],
                                            "price_birr": p["price_birr"],
                                            "quantity": p["quantity"],
                                            "quality_grade": p["quality_grade"],
                                            "region": p["region"],
                                            "is_verified": 1,
                                            "delivery_available": 1,
                                            "producer_rating": 4.0,
                                            "producer_experience": 3,
                                            "producer_tx": 0,
                                            "return_rate": 0.05,
                                        }

                                        merchant_list = []
                                        for m in merchants_raw:
                                            merchant_list.append({
                                                "id": m["id"],
                                                "name": m["full_name"],
                                                "preferred_sector": m.get("preferred_sector"),
                                                "preferred_product": m.get("preferred_product"),
                                                "region": m.get("region"),
                                                "max_budget_birr": m.get("max_budget_birr") or 0,
                                                "preferred_quality": m.get("preferred_quality") or "Any",
                                                "needs_delivery": m.get("needs_delivery") or False,
                                                "is_verified": m.get("is_verified", True),
                                                "rating": m.get("rating") or 4.0,
                                                "total_transactions": m.get("total_transactions") or 0,
                                                "years_in_business": m.get("years_in_business") or 1,
                                                "return_rate": m.get("return_rate") or 0.05,
                                                "payment_method": m.get("payment_method"),
                                            })

                                        if not merchant_list:
                                            st.warning("No merchants registered yet.")
                                        else:
                                            ranked = rank_merchants(listing_data, merchant_list)
                                            top_matches = [r for r in ranked if r["match_probability"] > 0.1][:5]
                                            if not top_matches:
                                                st.info("No strong matches found yet.")
                                            else:
                                                st.markdown("**Top AI-Matched Merchants:**")
                                                for r in top_matches:
                                                    pct = r["match_probability"] * 100
                                                    badge = "🟢" if r["is_match"] == 1 else "🟡"
                                                    st.write(f"{badge} **{r['name']}** — {pct:.1f}% match · {r['region']} · wants {r['preferred_product'] or 'N/A'}")
                                    except Exception as e:
                                        st.error(f"Matching failed: {e}")

                            st.markdown("---")
                            with st.spinner("Loading demand forecast..."):
                                try:
                                    fc = forecast_demand(p["product_name"], p["region"], weeks_ahead=4)
                                except Exception:
                                    fc = None

                            if fc and "error" not in fc:
                                trend_color = {"up": "🟢", "down": "🔴", "stable": "🟡"}[fc["trend"]]
                                trend_label = {"up": "↑ Rising", "down": "↓ Falling", "stable": "→ Stable"}
                                st.caption(
                                    f"📈 **Demand Forecast** — {p['region']}  "
                                    f"| {trend_color} {trend_label[fc['trend']]}  "
                                    f"| Model R²={fc['r2']:.2f}  RMSE=±{fc['rmse']:,.0f} units"
                                )
                                import pandas as pd
                                all_labels = [f"W-{7-i}" for i in range(8)] + [f"+{w}w" for w in fc["weeks"]]
                                hist_series = fc["historical"] + [None] * 4
                                fc_series   = [None] * 7 + [fc["historical"][-1]] + fc["forecast"]
                                chart_data  = pd.DataFrame({
                                    "Week":     all_labels,
                                    "Actual":   hist_series,
                                    "Forecast": fc_series,
                                }).set_index("Week")
                                st.line_chart(chart_data, color=["#4A90D9", "#F5A623"], height=200)
                            else:
                                st.caption("📈 Demand forecast unavailable for this product-region.")
            except Exception as e:
                st.error(f"Could not load listings: {e}")
