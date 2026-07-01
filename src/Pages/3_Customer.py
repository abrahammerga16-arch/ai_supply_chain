"""
Customer.py — Customer Dashboard
Ethiopian AI Supply Chain | Wolaita Sodo University — ECE

Tabs: Browse · Best Matches · My Orders · Notifications · Profile
"""

import streamlit as st

from src.shared import (
    supabase, REGIONS, SECTORS,
    SESSION_KEYS, get_profile,
    send_notification, get_unread_count,
    get_fraud_risk, render_fraud_badge, classify_order,
)
from src.sidebar import render_sidebar
from src.tabs_common import render_browse_tab, render_notifications_tab

# ── PAGE CONFIG ───────────────────────────────────────────────
st.set_page_config(page_title="Customer — AI Supply Chain", page_icon="🛒", layout="wide")

for key in SESSION_KEYS:
    if key not in st.session_state:
        st.session_state[key] = None

profile, role = render_sidebar()

if profile is None:
    st.title("🛒 Ethiopian AI Supply Chain — Customer")
    st.info("Please log in using the sidebar.")
    st.stop()

if role != "customer":
    st.error(f"❌ This page is for customers only. You are logged in as **{role}**.")
    st.stop()

_unread = get_unread_count(st.session_state.user.id)
_notif_label = f"🔔 Notifications ({_unread})" if _unread > 0 else "🔔 Notifications"

tab_browse, tab_matches, tab_orders, tab_notif, tab_profile = st.tabs([
    "📦 Browse", "🤖 Best Matches", "🛒 My Orders", _notif_label, "⚙️ Profile"
])


# ════════════════════════════════════════════════════════════
# TAB: BROWSE
# ════════════════════════════════════════════════════════════
with tab_browse:
    render_browse_tab(role, profile)


# ════════════════════════════════════════════════════════════
# TAB: BEST MATCHES
# ════════════════════════════════════════════════════════════
with tab_matches:
    st.subheader("🤖 AI-Recommended Products For You")
    st.caption("Tailored to your region and past preferences")

    try:
        all_products = supabase.table("products") \
            .select("*, profiles(full_name, phone, region)") \
            .eq("is_available", True).execute().data or []
    except Exception as e:
        st.error(f"Could not load products: {e}")
        all_products = []

    if not all_products:
        st.info("No products available for matching.")
    else:
        buyer_region = profile.get("region", "")
        pref_sector  = profile.get("preferred_sector", "")
        pref_product = (profile.get("preferred_product") or "").lower()
        pref_quality = profile.get("preferred_quality", "Any")
        max_budget   = float(profile.get("max_budget_birr") or 0)

        def score_product(p):
            score = 0.0
            if p.get("region") == buyer_region:               score += 30
            if pref_sector and p.get("sector") == pref_sector: score += 25
            if pref_product and pref_product in p.get("product_name","").lower(): score += 30
            if pref_quality and pref_quality != "Any":
                if pref_quality == "A or B" and p.get("quality_grade") in ("A","B"): score += 10
                elif p.get("quality_grade") == pref_quality:                          score += 10
            if max_budget > 0 and p.get("price_birr", 0) <= max_budget:              score += 5
            return score

        top_products = sorted(all_products, key=score_product, reverse=True)[:10]
        st.markdown(f"**Showing top {len(top_products)} matches:**")

        for p in top_products:
            pct    = min(int(score_product(p)), 100)
            seller = p.get("profiles") or {}
            mc     = "🟢" if pct >= 60 else ("🟡" if pct >= 30 else "🔴")

            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(f"**{p['product_name']}** · {p['sector']} · Grade **{p['quality_grade']}**")
                    st.caption(p.get("description") or "No description")
                    st.caption(f"👤 {seller.get('full_name','Unknown')} · 📍 {p['region']}")
                    st.caption(f"{mc} Match Score: **{pct}%**")
                with c2:
                    st.metric("Price", f"{p['price_birr']:,.0f} Birr")
                    st.caption(f"Available: {p['quantity']} {p['unit']}")
                with c3:
                    _qty_max = max(1.0, float(p["quantity"]))
                    qty_to_order = st.number_input(
                        "Qty", min_value=1.0, max_value=_qty_max,
                        value=min(1.0, _qty_max), key=f"cust_match_qty_{p['id']}"
                    )
                    total = qty_to_order * p["price_birr"]
                    st.caption(f"Total: **{total:,.0f} Birr**")
                    if st.button("🛒 Order Now", key=f"cust_match_order_{p['id']}"):
                        risk = get_fraud_risk(
                            sector=p["sector"], product=p["product_name"], region=p["region"],
                            payment_method="Bank Transfer", quantity=qty_to_order, price_birr=p["price_birr"],
                        )
                        try:
                            supabase.table("orders").insert({
                                "product_id":        p["id"],
                                "buyer_id":          st.session_state.user.id,
                                "quantity_ordered":  qty_to_order,
                                "total_price_birr":  total,
                                "status":            "pending",
                                "fraud_risk_level":  risk["risk_level"],
                                "fraud_probability": risk.get("fraud_probability", 0.0),
                            }).execute()
                            st.success(f"✅ Order placed — {total:,.0f} Birr")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Order failed: {e}")


# ════════════════════════════════════════════════════════════
# TAB: MY ORDERS
# ════════════════════════════════════════════════════════════
with tab_orders:
    st.subheader("🛒 My Orders")

    try:
        orders = supabase.table("orders") \
            .select("*, products(product_name, unit, region, sector, price_birr, quality_grade, producer_id, profiles(full_name, phone, region))") \
            .eq("buyer_id", st.session_state.user.id) \
            .order("created_at", desc=True).execute().data or []
    except Exception as e:
        st.error(f"Could not load orders: {e}")
        orders = []

    if not orders:
        st.info("You haven't placed any orders yet. Browse products to get started.")
    else:
        total_spent = sum(o["total_price_birr"] for o in orders)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Orders", len(orders))
        m2.metric("Total Spent",  f"{total_spent:,.0f} Birr")
        m3.metric("Pending",      sum(1 for o in orders if o["status"] == "pending"))
        m4.metric("Delivered",    sum(1 for o in orders if o["status"] == "delivered"))
        st.divider()

        status_filter = st.selectbox("Filter by Status",
            ["All","pending","confirmed","delivered","cancelled"], key="cust_order_status_filter")
        filtered = orders if status_filter == "All" else [o for o in orders if o["status"] == status_filter]

        if not filtered:
            st.info("No orders match this filter.")
        else:
            st.markdown(f"**{len(filtered)} order(s):**")
            for o in filtered:
                prod        = o.get("products") or {}
                pname       = prod.get("product_name", "Unknown")
                unit        = prod.get("unit", "")
                seller_info = prod.get("profiles") or {}

                status_badge = {"pending":"🟡 Pending","confirmed":"🔵 Confirmed",
                                "delivered":"🟢 Delivered","cancelled":"🔴 Cancelled"}.get(o["status"], o["status"])
                cls = classify_order(o)

                with st.container(border=True):
                    col_a, col_b, col_c = st.columns([3, 2, 2])
                    with col_a:
                        st.markdown(f"**{pname}**")
                        st.caption(f"Seller: {seller_info.get('full_name','Unknown')} · 📞 {seller_info.get('phone','N/A')}")
                        st.caption(f"📍 {prod.get('region','N/A')} · {prod.get('sector','N/A')}")
                        st.caption(f"Qty: {o['quantity_ordered']} {unit} · Grade: {prod.get('quality_grade','N/A')}")
                    with col_b:
                        st.metric("Total", f"{o['total_price_birr']:,.0f} Birr")
                        st.caption(status_badge)
                        risk_lvl = o.get("fraud_risk_level","Unknown")
                        if risk_lvl and risk_lvl != "Unknown":
                            rb = {"Low":"🟢","Medium":"🟡","High":"🔴"}.get(risk_lvl,"⚪")
                            st.caption(f"{rb} Fraud Risk: **{risk_lvl}**")
                    with col_c:
                        if cls["is_regular_order"] and o["status"] == "pending":
                            if st.button("❌ Cancel Order", key=f"cust_cancel_{o['id']}", use_container_width=True):
                                try:
                                    supabase.table("orders").update({"status":"cancelled"}).eq("id",o["id"]).execute()
                                    st.success("Order cancelled.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Cancel failed: {e}")


# ════════════════════════════════════════════════════════════
# TAB: NOTIFICATIONS
# ════════════════════════════════════════════════════════════
with tab_notif:
    render_notifications_tab(st.session_state.user.id)


# ════════════════════════════════════════════════════════════
# TAB: PROFILE
# ════════════════════════════════════════════════════════════
with tab_profile:
    st.subheader("⚙️ My Profile")
    st.caption(f"**{profile['full_name']}** · Customer · {profile['region']}")
    st.divider()
    st.markdown("### 📊 My Stats")
    try:
        my_orders = supabase.table("orders").select("*") \
            .eq("buyer_id", st.session_state.user.id).execute().data or []
        total_spent = sum(o["total_price_birr"] for o in my_orders)
        c1, c2 = st.columns(2)
        c1.metric("Total Orders", len(my_orders))
        c2.metric("Total Spent",  f"{total_spent:,.0f} Birr")
    except Exception as e:
        st.error(f"Could not load stats: {e}")
