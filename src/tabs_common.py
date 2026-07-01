"""
tabs_common.py — Shared tab renderers used across multiple role pages.

Exported functions:
    render_browse_tab(role, profile)
    render_notifications_tab(user_id)
"""

import datetime
import streamlit as st

from src.shared import (
    supabase, REGIONS, SECTORS,
    get_fraud_risk, render_fraud_badge,
)


# ════════════════════════════════════════════════════════════
# BROWSE TAB  (all roles see this)
# ════════════════════════════════════════════════════════════
def render_browse_tab(role: str, profile: dict):
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
        return

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
                    _qty_max = max(1.0, float(p["quantity"]))
                    qty_to_order = st.number_input(
                        "Qty", min_value=1.0, max_value=_qty_max,
                        value=min(1.0, _qty_max), key=f"qty_{p['id']}"
                    )
                    total = qty_to_order * p["price_birr"]
                    st.caption(f"Total: **{total:,.0f} Birr**")
                    risk = get_fraud_risk(
                        sector=p["sector"], product=p["product_name"],
                        region=p["region"], payment_method="Bank Transfer",
                        quantity=qty_to_order, price_birr=p["price_birr"],
                    )
                    render_fraud_badge(risk)
                    if st.button("🛒 Place Order", key=f"order_{p['id']}"):
                        if risk["risk_level"] == "High":
                            st.warning("⚠️ High fraud risk — proceed with caution.")
                        try:
                            supabase.table("orders").insert({
                                "product_id":        p["id"],
                                "buyer_id":          st.session_state.user.id,
                                "quantity_ordered":  qty_to_order,
                                "total_price_birr":  total,
                                "status":            "pending",
                                "fraud_risk_level":  risk["risk_level"],
                                "fraud_probability": risk["fraud_probability"],
                            }).execute()
                            st.success(f"✅ Order placed — {total:,.0f} Birr")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Order failed: {e}")
                else:
                    st.caption("📍 " + p["region"])


# ════════════════════════════════════════════════════════════
# NOTIFICATIONS TAB  (all roles see this)
# ════════════════════════════════════════════════════════════
def render_notifications_tab(user_id: str):
    hcol1, hcol2 = st.columns([3, 1])
    with hcol1:
        st.subheader("🔔 Notifications")
        st.caption("Order confirmations, deliveries, and updates appear here")
    with hcol2:
        if st.button("✅ Mark All Read", use_container_width=True, key="mark_all_read"):
            try:
                supabase.table("notifications") \
                    .update({"is_read": True}) \
                    .eq("recipient_id", user_id) \
                    .eq("is_read", False).execute()
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    try:
        notifs = supabase.table("notifications") \
            .select("*") \
            .eq("recipient_id", user_id) \
            .order("created_at", desc=True) \
            .limit(50).execute().data or []
    except Exception as e:
        st.error(f"Could not load notifications: {e}")
        notifs = []

    if not notifs:
        st.info("No notifications yet. Notifications appear here when orders are confirmed, delivered, or cancelled.")
        return

    icon_map   = {"success": "✅", "warning": "🚫", "error": "❌", "info": "ℹ️"}
    bg_map     = {"success": "#e8f8f5", "warning": "#fef9e7", "error": "#fdedec", "info": "#eaf2fb"}
    border_map = {"success": "117a65", "warning": "f39c12",   "error": "e74c3c",  "info": "1a5276"}

    unread_notifs = [n for n in notifs if not n.get("is_read")]
    read_notifs   = [n for n in notifs if n.get("is_read")]

    def _fmt_dt(s):
        try:
            return datetime.datetime.fromisoformat(
                s.replace("Z", "+00:00")
            ).strftime("%d %b %Y, %H:%M") if s else ""
        except Exception:
            return str(s)[:16]

    if unread_notifs:
        st.markdown(f"### 🔴 Unread ({len(unread_notifs)})")
        for n in unread_notifs:
            ntype = n.get("type", "info")
            st.markdown(
                f"<div style='background:{bg_map.get(ntype,'#eaf2fb')};border-radius:8px;"
                f"padding:14px 16px;margin-bottom:10px;"
                f"border-left:4px solid #{border_map.get(ntype,'1a5276')};'>"
                f"<b>{icon_map.get(ntype,'🔔')} {n['title']}</b><br>"
                f"{n['message']}<br>"
                f"<small style='color:#888;'>{_fmt_dt(n.get('created_at',''))}</small></div>",
                unsafe_allow_html=True
            )
            ncol1, _ = st.columns([1, 5])
            with ncol1:
                if st.button("✓ Read", key=f"read_{n['id']}", use_container_width=True):
                    try:
                        supabase.table("notifications").update(
                            {"is_read": True}
                        ).eq("id", n["id"]).execute()
                        st.rerun()
                    except Exception:
                        pass

    if read_notifs:
        with st.expander(f"📂 Read notifications ({len(read_notifs)})", expanded=False):
            for n in read_notifs:
                ntype = n.get("type", "info")
                st.markdown(
                    f"<div style='background:#f8f9fa;border-radius:6px;"
                    f"padding:10px 14px;margin-bottom:6px;opacity:0.75;'>"
                    f"<b>{icon_map.get(ntype,'🔔')} {n.get('title','N/A')}</b><br>"
                    f"<span style='color:#555;'>{n.get('message','')}</span><br>"
                    f"<small style='color:#aaa;'>{_fmt_dt(n.get('created_at',''))}</small></div>",
                    unsafe_allow_html=True
                )

    st.divider()
    if st.button("🗑️ Clear All Notifications", key="clear_all_notifs"):
        try:
            supabase.table("notifications").delete().eq("recipient_id", user_id).execute()
            st.success("All notifications cleared.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")
