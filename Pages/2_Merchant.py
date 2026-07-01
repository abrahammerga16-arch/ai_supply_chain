"""
Merchant.py — Merchant Dashboard
Ethiopian AI Supply Chain | Wolaita Sodo University — ECE

Tabs: Browse · Best Matches · My Orders · Place Order · Notifications
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import datetime
import streamlit as st

from src.shared import (
    supabase, REGIONS, SECTORS, UNITS, GRADES,
    SESSION_KEYS, get_profile,
    send_notification, get_unread_count,
    get_fraud_risk, render_fraud_badge, classify_order,
    generate_agreement_pdf, render_agreement_terms_inline,
    download_pdf_link,
)
from src.sidebar import render_sidebar
from src.tabs_common import render_browse_tab, render_notifications_tab

# ── PAGE CONFIG ───────────────────────────────────────────────
st.set_page_config(page_title="Merchant — AI Supply Chain", page_icon="🏪", layout="wide")

for key in SESSION_KEYS:
    if key not in st.session_state:
        st.session_state[key] = None

profile, role = render_sidebar()

if profile is None:
    st.title("🏪 Ethiopian AI Supply Chain — Merchant")
    st.info("Please log in using the sidebar.")
    st.stop()

if role != "merchant":
    st.error(f"❌ This page is for merchants only. You are logged in as **{role}**.")
    st.stop()

_unread = get_unread_count(st.session_state.user.id)
_notif_label = f"🔔 Notifications ({_unread})" if _unread > 0 else "🔔 Notifications"

tab_browse, tab_matches, tab_orders, tab_place, tab_notif = st.tabs([
    "📦 Browse", "🤖 Best Matches", "🛒 My Orders", "🛍️ Place Order", _notif_label
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
    st.caption("Based on your region, buying preferences and past activity")

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
            if pref_product and pref_product in p.get("product_name", "").lower(): score += 30
            if pref_quality and pref_quality != "Any":
                if pref_quality == "A or B" and p.get("quality_grade") in ("A", "B"): score += 10
                elif p.get("quality_grade") == pref_quality:                           score += 10
            if max_budget > 0 and p.get("price_birr", 0) <= max_budget:               score += 5
            return score

        top_products = sorted(all_products, key=score_product, reverse=True)[:10]
        st.markdown(f"**Showing top {len(top_products)} matches for you:**")

        for p in top_products:
            sc     = score_product(p)
            pct    = min(int(sc), 100)
            seller = p.get("profiles") or {}
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(f"**{p['product_name']}** · {p['sector']} · Grade **{p['quality_grade']}**")
                    st.caption(p.get("description") or "No description")
                    st.caption(f"👤 {seller.get('full_name','Unknown')} · 📍 {p['region']}")
                    mc = "🟢" if pct >= 60 else ("🟡" if pct >= 30 else "🔴")
                    st.caption(f"{mc} Match Score: **{pct}%**")
                with c2:
                    st.metric("Price", f"{p['price_birr']:,.0f} Birr")
                    st.caption(f"Available: {p['quantity']} {p['unit']}")
                with c3:
                    _qty_max = max(1.0, float(p["quantity"]))
                    qty_to_order = st.number_input(
                        "Qty", min_value=1.0, max_value=_qty_max,
                        value=min(1.0, _qty_max), key=f"match_qty_{p['id']}"
                    )
                    total = qty_to_order * p["price_birr"]
                    st.caption(f"Total: **{total:,.0f} Birr**")
                    if st.button("🛒 Order Now", key=f"match_order_{p['id']}"):
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

    has_prefs = profile.get("preferred_product") or profile.get("preferred_sector")
    if has_prefs:
        st.info(
            f"🤖 AI Matching active — **{profile.get('preferred_product','N/A')}** "
            f"in **{profile.get('preferred_sector','N/A')}** · "
            f"Budget: **{profile.get('max_budget_birr',0):,.0f} Birr** · "
            f"Quality: **{profile.get('preferred_quality','Any')}** — "
            f"update preferences in 🛍️ Place Order"
        )
    else:
        st.warning("⚠️ No buying preferences set yet — go to 🛍️ Place Order to enable AI matching.")
    st.divider()

    try:
        orders = supabase.table("orders") \
            .select("*, products(product_name, unit, region, sector, price_birr, quality_grade, producer_id, profiles(full_name, phone, region))") \
            .eq("buyer_id", st.session_state.user.id) \
            .order("created_at", desc=True).execute().data or []
    except Exception as e:
        st.error(f"Could not load orders: {e}")
        orders = []

    if not orders:
        st.info("You haven't placed any orders yet.")
    else:
        total_spent = sum(o["total_price_birr"] for o in orders)
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Orders", len(orders))
        m2.metric("Total Spent",  f"{total_spent:,.0f} Birr")
        m3.metric("Pending",   sum(1 for o in orders if o["status"] == "pending"))
        m4.metric("Confirmed", sum(1 for o in orders if o["status"] == "confirmed"))
        m5.metric("Delivered", sum(1 for o in orders if o["status"] == "delivered"))
        st.divider()

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            status_filter = st.selectbox("Filter by Status",
                ["All","pending","confirmed","delivered","cancelled"], key="order_status_filter")
        with col_f2:
            all_sectors = sorted(set(
                (o.get("products") or {}).get("sector","Unknown")
                for o in orders if (o.get("products") or {}).get("sector")
            ))
            sector_filter = st.selectbox("Filter by Sector", ["All"] + all_sectors, key="order_sector_filter")

        filtered = orders
        if status_filter != "All":
            filtered = [o for o in filtered if o["status"] == status_filter]
        if sector_filter != "All":
            filtered = [o for o in filtered if (o.get("products") or {}).get("sector") == sector_filter]

        if not filtered:
            st.info("No orders match your filter.")
        else:
            st.markdown(f"**Showing {len(filtered)} order(s):**")
            for o in filtered:
                prod        = o.get("products") or {}
                pname       = prod.get("product_name", "Unknown product")
                unit        = prod.get("unit", "")
                seller_info = prod.get("profiles") or {}
                seller_name = seller_info.get("full_name", "Unknown seller")
                seller_phone= seller_info.get("phone", "N/A")

                cls = classify_order(o)
                prod_confirmed      = cls["prod_confirmed"]
                merch_confirmed     = cls["merch_confirmed"]
                is_agreement        = cls["is_agreement"]
                both_confirmed      = cls["both_confirmed"]
                is_regular_order    = cls["is_regular_order"]
                is_producer_request = cls["is_producer_request"]

                status_badge = {"pending":"🟡 Pending","confirmed":"🔵 Confirmed",
                                "delivered":"🟢 Delivered","cancelled":"🔴 Cancelled"}.get(o["status"],o["status"])

                with st.container(border=True):
                    col_a, col_b, col_c = st.columns([3, 2, 2])
                    with col_a:
                        st.markdown(f"**{pname}**")
                        st.caption(f"Seller: {seller_name} · 📞 {seller_phone}")
                        st.caption(f"📍 {prod.get('region','N/A')} · {prod.get('sector','N/A')}")
                        st.caption(f"Qty: {o['quantity_ordered']} {unit} · Grade: {prod.get('quality_grade','N/A')}")
                        if o.get("notes"):
                            st.caption(f"📝 {o['notes']}")
                    with col_b:
                        st.metric("Total", f"{o['total_price_birr']:,.0f} Birr")
                        st.caption(status_badge)
                        risk_lvl = o.get("fraud_risk_level", "Unknown")
                        if risk_lvl and risk_lvl != "Unknown":
                            rb = {"Low":"🟢","Medium":"🟡","High":"🔴"}.get(risk_lvl,"⚪")
                            st.caption(f"{rb} Fraud Risk: **{risk_lvl}**")
                    with col_c:
                        if is_producer_request:
                            st.warning("📩 Order request from producer")
                            if st.button("✅ Confirm Order", key=f"confirm_req_{o['id']}", use_container_width=True):
                                try:
                                    supabase.table("orders").update({
                                        "merchant_confirmed": True, "status": "confirmed",
                                    }).eq("id", o["id"]).execute()
                                    prod_producer_id = prod.get("producer_id")
                                    if prod_producer_id:
                                        send_notification(
                                            recipient_id=prod_producer_id,
                                            title="✅ Order Request Confirmed",
                                            message=(
                                                f"**{profile.get('full_name','The merchant')}** confirmed your "
                                                f"order request for **{pname}**. You can now create the formal agreement."
                                            ),
                                            notif_type="success", order_id=o["id"],
                                        )
                                    st.success("✅ Confirmed. The producer can now generate the agreement.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")
                            if st.button("❌ Decline", key=f"decline_req_{o['id']}", use_container_width=True):
                                try:
                                    supabase.table("orders").update({"status":"cancelled"}).eq("id",o["id"]).execute()
                                    prod_producer_id = prod.get("producer_id")
                                    if prod_producer_id:
                                        send_notification(
                                            recipient_id=prod_producer_id,
                                            title="❌ Order Request Declined",
                                            message=f"**{profile.get('full_name','The merchant')}** declined your request for **{pname}**.",
                                            notif_type="warning", order_id=o["id"],
                                        )
                                    st.error("Declined.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")

                        elif is_agreement:
                            if both_confirmed:
                                st.success("🤝 Agreement Fully Signed")
                            elif prod_confirmed and not merch_confirmed:
                                st.warning("⏳ Awaiting Your Acceptance")
                                if st.button("✅ Accept Agreement", key=f"accept_agr_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update({
                                            "merchant_confirmed": True, "status": "confirmed",
                                        }).eq("id", o["id"]).execute()
                                        prod_producer_id = prod.get("producer_id")
                                        if prod_producer_id:
                                            send_notification(
                                                recipient_id=prod_producer_id,
                                                title="🤝 Agreement Accepted!",
                                                message=f"**{profile.get('full_name','')}** accepted your agreement for **{pname}**.",
                                                notif_type="success", order_id=o["id"],
                                            )
                                        st.success("✅ Agreement accepted!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed: {e}")
                                if st.button("❌ Reject Agreement", key=f"reject_agr_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update({
                                            "merchant_confirmed": False, "status": "cancelled",
                                        }).eq("id", o["id"]).execute()
                                        prod_producer_id = prod.get("producer_id")
                                        if prod_producer_id:
                                            send_notification(
                                                recipient_id=prod_producer_id,
                                                title="❌ Agreement Rejected",
                                                message=f"**{profile.get('full_name','')}** rejected your agreement for **{pname}**.",
                                                notif_type="warning", order_id=o["id"],
                                            )
                                        st.error("Agreement rejected.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed: {e}")

                        elif is_regular_order and o["status"] == "pending":
                            if st.button("❌ Cancel Order", key=f"cancel_{o['id']}", use_container_width=True):
                                try:
                                    supabase.table("orders").update({"status":"cancelled"}).eq("id",o["id"]).execute()
                                    st.success("Order cancelled.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Cancel failed: {e}")

                    if is_agreement:
                        try:
                            prod_profile = supabase.table("profiles").select("*") \
                                .eq("id", prod.get("producer_id","")).execute().data
                            prod_profile = prod_profile[0] if prod_profile else {}
                        except Exception:
                            prod_profile = {}

                        render_agreement_terms_inline(o, prod, prod_profile, profile, f"my_{o['id']}")

                        if st.button("📄 Download Agreement PDF", key=f"view_agr_pdf_{o['id']}", use_container_width=True):
                            delivery_str = datetime.date.today()
                            payment_str  = "Bank Transfer"
                            if o.get("agreement_delivery_date"):
                                try: delivery_str = datetime.date.fromisoformat(o["agreement_delivery_date"])
                                except Exception: pass
                            if o.get("agreement_payment_method"):
                                payment_str = o["agreement_payment_method"]

                            pdf_bytes = generate_agreement_pdf(
                                producer_name=prod_profile.get("full_name","Producer"),
                                producer_phone=prod_profile.get("phone",""),
                                producer_region=prod_profile.get("region",""),
                                merchant_name=profile.get("full_name",""),
                                merchant_phone=profile.get("phone",""),
                                merchant_region=profile.get("region",""),
                                product_name=pname, sector=prod.get("sector",""),
                                quality_grade=prod.get("quality_grade",""),
                                quantity=o["quantity_ordered"], unit=unit,
                                price_per_unit=o["total_price_birr"]/o["quantity_ordered"] if o["quantity_ordered"] else 0,
                                total_price=o["total_price_birr"], delivery_date=delivery_str,
                                payment_method=payment_str, notes=o.get("notes",""),
                                agreement_id=str(o["id"]),
                                producer_confirmed=prod_confirmed, merchant_confirmed=merch_confirmed,
                            )
                            st.session_state.agreement_preview_pdf = pdf_bytes
                            st.session_state.agreement_preview_ref = str(o["id"])
                            st.rerun()

                    can_update = o["status"] not in ("cancelled","delivered") and (is_regular_order or both_confirmed)
                    if can_update:
                        with st.expander("✏️ Update Order"):
                            upd_col1, upd_col2 = st.columns(2)
                            with upd_col1:
                                new_qty    = st.number_input("New Quantity", min_value=0.1,
                                                              value=float(o["quantity_ordered"]), step=1.0, key=f"upd_qty_{o['id']}")
                                new_status = st.selectbox("Status", ["pending","confirmed","delivered","cancelled"],
                                                           index=["pending","confirmed","delivered","cancelled"].index(o["status"]),
                                                           key=f"upd_status_{o['id']}")
                            with upd_col2:
                                unit_price = o["total_price_birr"] / o["quantity_ordered"] if o["quantity_ordered"] else 0
                                new_total  = new_qty * unit_price
                                st.metric("New Total", f"{new_total:,.0f} Birr")
                                new_notes  = st.text_area("Notes", value=o.get("notes") or "", key=f"upd_notes_{o['id']}")
                            if st.button("💾 Save Changes", key=f"upd_save_{o['id']}", use_container_width=True):
                                try:
                                    supabase.table("orders").update({
                                        "quantity_ordered": new_qty, "total_price_birr": new_total,
                                        "notes": new_notes, "status": new_status,
                                    }).eq("id", o["id"]).execute()
                                    st.success("✅ Order updated!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Update failed: {e}")

    if st.session_state.get("agreement_preview_pdf"):
        st.divider()
        ref = st.session_state.get("agreement_preview_ref", "agreement")
        st.markdown(
            download_pdf_link(
                st.session_state.agreement_preview_pdf,
                f"Agreement-{ref[:8].upper()}.pdf",
                f"📥 Download Agreement PDF (Ref: {ref[:8].upper()})"
            ), unsafe_allow_html=True
        )
        if st.button("✖ Close Preview", key="close_preview_pdf"):
            st.session_state.agreement_preview_pdf = None
            st.session_state.agreement_preview_ref = None
            st.rerun()


# ════════════════════════════════════════════════════════════
# TAB: PLACE ORDER
# ════════════════════════════════════════════════════════════
with tab_place:
    st.subheader("🛍️ Place Order")
    st.caption(f"Logged in as **{profile['full_name']}** · {profile['region']}")
    st.divider()

    st.markdown("### 🏪 Buying Preferences")
    pf_col1, pf_col2 = st.columns(2)
    with pf_col1:
        pref_sector   = st.selectbox("Preferred Sector", SECTORS,
            index=SECTORS.index(profile.get("preferred_sector")) if profile.get("preferred_sector") in SECTORS else 0,
            key="edit_pref_sector")
        pref_product  = st.text_input("Preferred Product", value=profile.get("preferred_product") or "", key="edit_pref_product")
        pref_budget   = st.number_input("Max Budget (Birr)", min_value=0.0, step=1000.0,
            value=float(profile.get("max_budget_birr") or 0), key="edit_pref_budget")
    with pf_col2:
        pref_quality  = st.selectbox("Preferred Quality", ["A","B","A or B","Any"],
            index=["A","B","A or B","Any"].index(profile.get("preferred_quality") or "Any"),
            key="edit_pref_quality")
        pref_delivery = st.checkbox("I need delivery", value=profile.get("needs_delivery") or False, key="edit_pref_delivery")
        pref_payment  = st.selectbox("Payment Method", ["Cash","Bank Transfer","Mobile Money","Credit"],
            index=["Cash","Bank Transfer","Mobile Money","Credit"].index(profile.get("payment_method") or "Cash"),
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

    st.divider()
    st.markdown("### 🛒 Place a New Order")

    po_col1, po_col2, po_col3 = st.columns(3)
    with po_col1:
        po_sector = st.selectbox("Sector", ["All"] + SECTORS, key="po_sector")
    with po_col2:
        po_region = st.selectbox("Region", ["All"] + REGIONS, key="po_region")
    with po_col3:
        po_search = st.text_input("🔍 Search Product", key="po_search")

    try:
        po_query = supabase.table("products").select("*, profiles(full_name, phone, region)").eq("is_available", True)
        if po_sector != "All":
            po_query = po_query.eq("sector", po_sector)
        if po_region != "All":
            po_query = po_query.eq("region", po_region)
        po_products = po_query.execute().data or []
        if po_search:
            po_products = [p for p in po_products if po_search.lower() in p["product_name"].lower()]
    except Exception as e:
        st.error(f"Could not load products: {e}")
        po_products = []

    if not po_products:
        st.info("No products found.")
    else:
        st.markdown(f"**{len(po_products)} product(s) available:**")
        for p in po_products:
            seller = p.get("profiles") or {}
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(f"**{p['product_name']}** · {p['sector']} · Grade **{p['quality_grade']}**")
                    st.caption(p.get("description") or "No description")
                    st.caption(f"👤 {seller.get('full_name','Unknown')} · 📍 {p['region']} · 📞 {seller.get('phone','N/A')}")
                with c2:
                    st.metric("Price / Unit", f"{p['price_birr']:,.0f} Birr")
                    st.caption(f"Available: {p['quantity']} {p['unit']}")
                with c3:
                    _max_qty = max(1.0, float(p["quantity"]))
                    po_qty   = st.number_input("Quantity", min_value=1.0, max_value=_max_qty,
                                               value=min(1.0, _max_qty), step=1.0, key=f"po_qty_{p['id']}")
                    po_total = po_qty * p["price_birr"]
                    st.caption(f"Total: **{po_total:,.0f} Birr**")
                    risk = get_fraud_risk(
                        sector=p["sector"], product=p["product_name"], region=p["region"],
                        payment_method=pref_payment, quantity=po_qty, price_birr=p["price_birr"],
                    )
                    render_fraud_badge(risk)
                    if st.button("🛒 Place Order", key=f"po_order_{p['id']}", use_container_width=True):
                        try:
                            supabase.table("orders").insert({
                                "product_id":        p["id"],
                                "buyer_id":          st.session_state.user.id,
                                "quantity_ordered":  po_qty,
                                "total_price_birr":  po_total,
                                "status":            "pending",
                                "fraud_risk_level":  risk.get("risk_level","Unknown"),
                                "fraud_probability": risk.get("fraud_probability",0.0),
                            }).execute()
                            st.success(f"✅ Order placed — {po_total:,.0f} Birr!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Order failed: {e}")


# ════════════════════════════════════════════════════════════
# TAB: NOTIFICATIONS
# ════════════════════════════════════════════════════════════
with tab_notif:
    render_notifications_tab(st.session_state.user.id)
