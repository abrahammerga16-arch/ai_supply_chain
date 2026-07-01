"""
Producer.py — Producer Dashboard
Ethiopian AI Supply Chain | Wolaita Sodo University — ECE

Tabs: Browse · Add Product · My Listings · Incoming Orders · Notifications · Profile
"""

import datetime
import streamlit as st
import pandas as pd

from src.shared import (
    supabase, REGIONS, SECTORS, UNITS, GRADES,
    SESSION_KEYS, get_profile,
    send_notification, get_unread_count,
    get_fraud_risk, render_fraud_badge, classify_order,
    generate_agreement_pdf, render_agreement_terms_inline,
    download_pdf_link,
)
from src.price_engine import recommend_price
from src.matching_engine import rank_merchants
from src.demand_engine import forecast_demand
from src.sidebar import render_sidebar
from src.tabs_common import render_browse_tab, render_notifications_tab

# ── PAGE CONFIG ───────────────────────────────────────────────
st.set_page_config(page_title="Producer — AI Supply Chain", page_icon="🌾", layout="wide")

# ── SESSION STATE INIT ────────────────────────────────────────
for key in SESSION_KEYS:
    if key not in st.session_state:
        st.session_state[key] = None

# ── SIDEBAR ───────────────────────────────────────────────────
profile, role = render_sidebar()

if profile is None:
    st.title("🌾 Ethiopian AI Supply Chain — Producer")
    st.info("Please log in using the sidebar.")
    st.stop()

if role != "producer":
    st.error(f"❌ This page is for producers only. You are logged in as **{role}**.")
    st.info("Navigate to your role's page from the sidebar.")
    st.stop()

# ── NOTIFICATION BADGE ────────────────────────────────────────
_unread = get_unread_count(st.session_state.user.id)
_notif_label = f"🔔 Notifications ({_unread})" if _unread > 0 else "🔔 Notifications"

# ── TABS ──────────────────────────────────────────────────────
tab_browse, tab_add, tab_listings, tab_incoming, tab_notif, tab_profile = st.tabs([
    "📦 Browse", "➕ Add Product", "📋 My Listings",
    "📬 Incoming Orders", _notif_label, "⚙️ Profile"
])


# ════════════════════════════════════════════════════════════
# TAB: BROWSE
# ════════════════════════════════════════════════════════════
with tab_browse:
    render_browse_tab(role, profile)


# ════════════════════════════════════════════════════════════
# TAB: ADD PRODUCT
# ════════════════════════════════════════════════════════════
with tab_add:
    st.subheader("➕ Add New Product")

    p_sector  = st.selectbox("Sector", SECTORS, key="add_sector")
    p_name    = st.text_input("Product Name", key="add_name")
    p_quality = st.selectbox("Quality Grade", GRADES, key="add_quality")
    p_region  = st.selectbox(
        "Region", REGIONS,
        index=REGIONS.index(profile["region"]) if profile.get("region") in REGIONS else 0,
        key="add_region"
    )

    if p_name:
        try:
            rec = recommend_price(sector=p_sector, product=p_name, region=p_region, quality_grade=p_quality)
            st.info(
                f"💰 AI Suggested Price: **{rec['recommended_price']:,.0f} Birr** "
                f"(range: {rec['min_price']:,.0f} – {rec['max_price']:,.0f} Birr)"
            )
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
# TAB: MY LISTINGS
# ════════════════════════════════════════════════════════════
with tab_listings:
    st.subheader("📋 My Listings")

    # ── AGREEMENT DRAFT FLOW ──────────────────────────────
    if st.session_state.agreement_product_id and st.session_state.agreement_merchant:
        m   = st.session_state.agreement_merchant
        pid = st.session_state.agreement_product_id
        try:
            prod = supabase.table("products").select("*").eq("id", pid).execute().data
            prod = prod[0] if prod else {}
        except Exception:
            prod = {}

        st.markdown(f"### 🤝 Draft Agreement with **{m['name']}**")
        with st.container(border=True):
            col_contact, col_terms = st.columns(2)
            with col_contact:
                st.markdown("#### 📞 Merchant Contact")
                st.markdown(f"**Name:** {m['name']}")
                st.markdown(f"**Region:** {m.get('region', 'N/A')}")
                st.markdown(f"**Phone:** {m.get('phone') or 'Not provided'}")
                st.markdown(f"**Preferred Product:** {m.get('preferred_product') or 'N/A'}")
                st.markdown(f"**Payment Method:** {m.get('payment_method') or 'N/A'}")
                st.markdown(f"**Max Budget:** {m.get('max_budget_birr', 0):,.0f} Birr")

            with col_terms:
                st.markdown("#### 📝 Agreement Terms")
                agr_qty_max  = max(0.1, float(prod.get("quantity", 1000)))
                agr_qty      = st.number_input("Quantity", min_value=0.1, max_value=agr_qty_max,
                                               value=min(10.0, agr_qty_max), step=1.0, key="agr_qty")
                agr_price    = st.number_input("Agreed Price per Unit (Birr)", min_value=1.0,
                                               value=float(prod.get("price_birr", 100)), step=10.0, key="agr_price")
                agr_delivery = st.date_input("Delivery Date", key="agr_delivery")
                agr_payment  = st.selectbox("Payment Method",
                                            ["Cash", "Bank Transfer", "Mobile Money", "Credit"], key="agr_payment")
                agr_notes    = st.text_area("Additional Notes (optional)", key="agr_notes")
                agr_total    = agr_qty * agr_price
                st.info(f"💰 Total: **{agr_total:,.0f} Birr**")

            if st.button("👁️ Preview Agreement PDF", use_container_width=True, key="preview_agr_btn"):
                preview_pdf = generate_agreement_pdf(
                    producer_name=profile.get("full_name", ""), producer_phone=profile.get("phone", ""),
                    producer_region=profile.get("region", ""), merchant_name=m["name"],
                    merchant_phone=m.get("phone", ""), merchant_region=m.get("region", ""),
                    product_name=prod.get("product_name", ""), sector=prod.get("sector", ""),
                    quality_grade=prod.get("quality_grade", ""), quantity=agr_qty,
                    unit=prod.get("unit", ""), price_per_unit=agr_price, total_price=agr_total,
                    delivery_date=agr_delivery, payment_method=agr_payment, notes=agr_notes,
                    agreement_id="PREVIEW00", producer_confirmed=False, merchant_confirmed=False,
                )
                st.markdown(download_pdf_link(preview_pdf, "Agreement-PREVIEW.pdf", "📄 Download Preview PDF"),
                            unsafe_allow_html=True)
                st.caption("⚠️ Preview only. Confirm below to create the official agreement.")

            col_send, col_cancel = st.columns(2)
            with col_send:
                if st.button("✅ Confirm & Send to Merchant", use_container_width=True, key="send_agreement"):
                    try:
                        order_res = supabase.table("orders").insert({
                            "product_id":               pid,
                            "buyer_id":                 m["id"],
                            "quantity_ordered":         agr_qty,
                            "total_price_birr":         agr_total,
                            "status":                   "pending",
                            "fraud_risk_level":         "Low",
                            "fraud_probability":        0.05,
                            "producer_confirmed":       True,
                            "merchant_confirmed":       False,
                            "agreement_delivery_date":  str(agr_delivery),
                            "agreement_payment_method": agr_payment,
                            "notes": (
                                f"Producer-initiated agreement. "
                                f"Payment: {agr_payment}. Delivery: {agr_delivery}. {agr_notes}"
                            ),
                        }).execute()
                        order_id = order_res.data[0]["id"] if order_res.data else "N/A"

                        send_notification(
                            recipient_id=m["id"],
                            title="🤝 New Agreement From Producer",
                            message=(
                                f"**{profile.get('full_name', 'A producer')}** has sent you a "
                                f"supply agreement for **{prod.get('product_name', 'a product')}** — "
                                f"{agr_qty:,.1f} {prod.get('unit', '')} @ {agr_price:,.0f} Birr/unit "
                                f"(Total: {agr_total:,.0f} Birr). Go to 🛒 My Orders to accept or reject."
                            ),
                            notif_type="info", order_id=str(order_id),
                        )

                        pdf_bytes = generate_agreement_pdf(
                            producer_name=profile.get("full_name", ""), producer_phone=profile.get("phone", ""),
                            producer_region=profile.get("region", ""), merchant_name=m["name"],
                            merchant_phone=m.get("phone", ""), merchant_region=m.get("region", ""),
                            product_name=prod.get("product_name", ""), sector=prod.get("sector", ""),
                            quality_grade=prod.get("quality_grade", ""), quantity=agr_qty,
                            unit=prod.get("unit", ""), price_per_unit=agr_price, total_price=agr_total,
                            delivery_date=agr_delivery, payment_method=agr_payment, notes=agr_notes,
                            agreement_id=str(order_id), producer_confirmed=True, merchant_confirmed=False,
                        )
                        st.session_state.agreement_pdf           = pdf_bytes
                        st.session_state.agreement_ref           = str(order_id)
                        st.session_state.agreement_merchant_name = m["name"]
                        st.session_state.agreement_product_id    = None
                        st.session_state.agreement_merchant      = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
            with col_cancel:
                if st.button("✖ Cancel", use_container_width=True, key="cancel_agreement"):
                    st.session_state.agreement_product_id = None
                    st.session_state.agreement_merchant   = None
                    st.rerun()
        st.markdown("---")

    # ── SHOW GENERATED AGREEMENT DOWNLOAD ────────────────
    if st.session_state.get("agreement_pdf"):
        st.success(
            f"✅ Agreement sent to **{st.session_state.get('agreement_merchant_name', '')}**! "
            "They must now accept it in their My Orders tab. Download your copy below."
        )
        ref = st.session_state.get("agreement_ref", "agreement")
        st.markdown(
            download_pdf_link(st.session_state.agreement_pdf, f"Agreement-{ref[:8].upper()}.pdf"),
            unsafe_allow_html=True
        )
        if st.button("✖ Dismiss", key="dismiss_pdf"):
            st.session_state.agreement_pdf = None
            st.session_state.agreement_ref = None
            st.rerun()
        st.divider()

    # ── PRODUCTS LIST ─────────────────────────────────────
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

                with col_edit:
                    if st.button("✏️ Edit", key=f"edit_btn_{p['id']}", use_container_width=True):
                        st.session_state.edit_product_id = p["id"]

                with col_delete:
                    if st.button("🗑️ Delete", key=f"del_{p['id']}", use_container_width=True):
                        try:
                            supabase.table("products").delete().eq("id", p["id"]).execute()
                            st.success(f"'{p['product_name']}' deleted.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Delete failed: {e}")

                if st.session_state.edit_product_id == p["id"]:
                    st.markdown("---")
                    st.markdown("**✏️ Edit Product**")
                    with st.form(f"edit_form_{p['id']}"):
                        e_name    = st.text_input("Product Name", value=p["product_name"])
                        e_sector  = st.selectbox("Sector", SECTORS,
                                                  index=SECTORS.index(p["sector"]) if p["sector"] in SECTORS else 0)
                        e_quality = st.selectbox("Grade", GRADES,
                                                  index=GRADES.index(p["quality_grade"]) if p["quality_grade"] in GRADES else 0)
                        e_region  = st.selectbox("Region", REGIONS,
                                                  index=REGIONS.index(p["region"]) if p["region"] in REGIONS else 0)
                        e_qty     = st.number_input("Quantity", min_value=0.1, value=float(p["quantity"]), step=1.0)
                        e_unit    = st.selectbox("Unit", UNITS,
                                                  index=UNITS.index(p["unit"]) if p["unit"] in UNITS else 0)
                        e_price   = st.number_input("Price (Birr)", min_value=1.0, value=float(p["price_birr"]), step=10.0)
                        e_desc    = st.text_area("Description", value=p.get("description") or "")

                        col_save, col_cancel_e = st.columns(2)
                        with col_save:
                            save = st.form_submit_button("💾 Save Changes", use_container_width=True)
                        with col_cancel_e:
                            cancel = st.form_submit_button("✖ Cancel", use_container_width=True)

                        if save:
                            try:
                                supabase.table("products").update({
                                    "product_name":  e_name, "sector": e_sector,
                                    "quality_grade": e_quality, "region": e_region,
                                    "quantity": e_qty, "unit": e_unit,
                                    "price_birr": e_price, "description": e_desc,
                                }).eq("id", p["id"]).execute()
                                st.success("Product updated!")
                                st.session_state.edit_product_id = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Update failed: {e}")
                        if cancel:
                            st.session_state.edit_product_id = None
                            st.rerun()

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
                                "id":                 m["id"],
                                "name":               m["full_name"],
                                "phone":              m.get("phone"),
                                "preferred_sector":   m.get("preferred_sector"),
                                "preferred_product":  m.get("preferred_product"),
                                "region":             m.get("region"),
                                "max_budget_birr":    m.get("max_budget_birr") or 0,
                                "preferred_quality":  m.get("preferred_quality") or "Any",
                                "needs_delivery":     m.get("needs_delivery") or False,
                                "is_verified":        m.get("is_verified", True),
                                "rating":             m.get("rating") or 4.0,
                                "total_transactions": m.get("total_transactions") or 0,
                                "years_in_business":  m.get("years_in_business") or 1,
                                "return_rate":        m.get("return_rate") or 0.05,
                                "payment_method":     m.get("payment_method"),
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
                                                f"{r.get('region','N/A')} · "
                                                f"wants {r.get('preferred_product') or 'N/A'} · "
                                                f"📞 {r.get('phone') or 'N/A'}"
                                            )
                                        with mcol2:
                                            req_qty = st.number_input(
                                                "Qty", min_value=0.1,
                                                max_value=max(0.1, float(p["quantity"])),
                                                value=min(10.0, max(0.1, float(p["quantity"]))),
                                                step=1.0, key=f"reqqty_{p['id']}_{r['id']}"
                                            )
                                            if st.button(
                                                "📩 Send Order Request",
                                                key=f"agr_{p['id']}_{r['id']}",
                                                use_container_width=True
                                            ):
                                                try:
                                                    req_total = req_qty * p["price_birr"]
                                                    order_res = supabase.table("orders").insert({
                                                        "product_id":         p["id"],
                                                        "buyer_id":           r["id"],
                                                        "quantity_ordered":   req_qty,
                                                        "total_price_birr":   req_total,
                                                        "status":             "pending",
                                                        "fraud_risk_level":   "Low",
                                                        "fraud_probability":  0.05,
                                                        "producer_confirmed": True,
                                                        "merchant_confirmed": False,
                                                        "notes": (
                                                            f"Producer-initiated order request for "
                                                            f"{p['product_name']}. No agreement yet — "
                                                            f"awaiting merchant confirmation."
                                                        ),
                                                    }).execute()
                                                    new_order_id = order_res.data[0]["id"] if order_res.data else None
                                                    send_notification(
                                                        recipient_id=r["id"],
                                                        title="📩 New Order Request From Producer",
                                                        message=(
                                                            f"**{profile.get('full_name','A producer')}** wants to sell you "
                                                            f"**{p['product_name']}** — {req_qty:,.1f} {p['unit']} @ "
                                                            f"{p['price_birr']:,.0f} Birr/unit (Total: {req_total:,.0f} Birr). "
                                                            f"Go to 🛒 My Orders to confirm or decline."
                                                        ),
                                                        notif_type="info",
                                                        order_id=str(new_order_id) if new_order_id else None,
                                                    )
                                                    st.success(f"📩 Order request sent to {r['name']}.")
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Failed: {e}")
                        except Exception as e:
                            st.error(f"Matching failed: {e}")

                # ── DEMAND FORECAST ───────────────────────
                try:
                    fc = forecast_demand(p["product_name"], p["region"], weeks_ahead=4)
                except Exception:
                    fc = None

                if fc and "error" not in fc:
                    trend_icon  = {"up": "🟢 ↑ Rising", "down": "🔴 ↓ Falling", "stable": "🟡 → Stable"}[fc["trend"]]
                    all_labels  = [f"W-{7-i}" for i in range(8)] + [f"+{w}w" for w in fc["weeks"]]
                    hist_series = fc["historical"] + [None] * 4
                    fc_series   = [None] * 7 + [fc["historical"][-1]] + fc["forecast"]
                    chart_data  = pd.DataFrame({"Actual": hist_series, "Forecast": fc_series}, index=all_labels)
                    st.caption(f"📈 Demand Forecast | {trend_icon} | R²={fc['r2']:.2f} RMSE=±{fc['rmse']:,.0f}")
                    st.line_chart(chart_data, color=["#4A90D9", "#F5A623"], height=180)
                else:
                    st.caption("📈 Demand forecast unavailable.")


# ════════════════════════════════════════════════════════════
# TAB: INCOMING ORDERS
# ════════════════════════════════════════════════════════════
with tab_incoming:
    st.subheader("📬 Incoming Orders from Merchants & Customers")
    st.caption("All orders placed on your products — confirm, deliver, or cancel them here")

    try:
        my_prod_ids = [
            p["id"] for p in
            supabase.table("products").select("id").eq("producer_id", st.session_state.user.id).execute().data or []
        ]
    except Exception as e:
        st.error(f"Could not load your products: {e}")
        my_prod_ids = []

    if not my_prod_ids:
        st.info("You have no listed products yet. Add products first to receive orders.")
    else:
        try:
            incoming = supabase.table("orders") \
                .select("*, products(product_name, unit, sector, quality_grade, region, producer_id), profiles(full_name, phone, region)") \
                .in_("product_id", my_prod_ids) \
                .order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Could not load incoming orders: {e}")
            incoming = []

        if not incoming:
            st.info("No orders received yet.")
        else:
            total_rev       = sum(o["total_price_birr"] for o in incoming if o["status"] == "confirmed")
            pending_count   = sum(1 for o in incoming if o["status"] == "pending")
            confirmed_count = sum(1 for o in incoming if o["status"] == "confirmed")
            delivered_count = sum(1 for o in incoming if o["status"] == "delivered")

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total Orders", len(incoming))
            m2.metric("🟡 Pending",   pending_count)
            m3.metric("🔵 Confirmed", confirmed_count)
            m4.metric("🟢 Delivered", delivered_count)
            m5.metric("💰 Revenue",   f"{total_rev:,.0f} Birr")
            st.divider()

            inc_status_filter = st.selectbox(
                "Filter by Status",
                ["All", "pending", "confirmed", "delivered", "cancelled"],
                key="inc_status_filter"
            )
            filtered = incoming if inc_status_filter == "All" else \
                [o for o in incoming if o["status"] == inc_status_filter]

            if not filtered:
                st.info("No orders match this filter.")
            else:
                st.markdown(f"**{len(filtered)} order(s):**")
                for o in filtered:
                    prod        = o.get("products") or {}
                    buyer       = o.get("profiles") or {}
                    pname       = prod.get("product_name", "Unknown")
                    unit        = prod.get("unit", "")
                    buyer_name  = buyer.get("full_name", "Unknown buyer")
                    buyer_phone = buyer.get("phone", "N/A")
                    buyer_region= buyer.get("region", "N/A")
                    cls         = classify_order(o)
                    is_agreement        = cls["is_agreement"]
                    prod_confirmed      = cls["prod_confirmed"]
                    merch_confirmed     = cls["merch_confirmed"]
                    both_confirmed      = cls["both_confirmed"]
                    is_producer_request = cls["is_producer_request"]

                    status_badge = {"pending": "🟡 Pending", "confirmed": "🔵 Confirmed",
                                    "delivered": "🟢 Delivered", "cancelled": "🔴 Cancelled"}.get(o["status"], o["status"])

                    if o["status"] == "pending":
                        st.markdown(
                            "<div style='border-left:4px solid #f39c12;padding-left:8px;margin-bottom:4px;'>"
                            "🆕 <b>New Order Received</b></div>", unsafe_allow_html=True
                        )

                    with st.container(border=True):
                        col_a, col_b, col_c = st.columns([3, 2, 2])
                        with col_a:
                            st.markdown(
                                f"**{pname}** · {prod.get('sector','N/A')} · Grade **{prod.get('quality_grade','N/A')}**"
                            )
                            st.caption(f"👤 Buyer: **{buyer_name}** · 📞 {buyer_phone} · 📍 {buyer_region}")
                            st.caption(f"Qty: **{o['quantity_ordered']} {unit}** · Region: {prod.get('region','N/A')}")
                            if is_agreement:
                                st.caption(
                                    f"📑 **Agreement Order** · Delivery: {o.get('agreement_delivery_date','N/A')} · "
                                    f"Payment: {o.get('agreement_payment_method','N/A')}"
                                )
                            elif is_producer_request:
                                st.caption("📩 **Order request you sent** · awaiting merchant response")
                            if o.get("notes"):
                                st.caption(f"📝 {o['notes']}")
                            risk_lvl = o.get("fraud_risk_level", "Unknown")
                            if risk_lvl and risk_lvl != "Unknown":
                                rb = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk_lvl, "⚪")
                                st.caption(f"{rb} Fraud Risk: **{risk_lvl}**")

                        with col_b:
                            st.metric("Order Value", f"{o['total_price_birr']:,.0f} Birr")
                            st.caption(status_badge)
                            created = o.get("created_at", "")
                            if created:
                                try:
                                    dt = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
                                    st.caption(f"🕐 {dt.strftime('%d %b %Y, %H:%M')}")
                                except Exception:
                                    st.caption(f"🕐 {created[:16]}")
                            if is_agreement:
                                if both_confirmed:
                                    st.success("🤝 Both Confirmed")
                                elif prod_confirmed and not merch_confirmed:
                                    st.warning("⏳ Awaiting Merchant")
                            elif is_producer_request:
                                st.info("⏳ Awaiting merchant confirmation")

                        with col_c:
                            ready_for_agreement = (
                                is_producer_request and merch_confirmed and o["status"] == "confirmed"
                            )

                            if ready_for_agreement:
                                if st.button("📝 Create Agreement", key=f"mk_agr_{o['id']}", use_container_width=True):
                                    st.session_state.agreement_pending_order_id = o["id"]
                                    st.rerun()

                            elif o["status"] == "pending" and cls["is_regular_order"]:
                                if st.button("✅ Confirm Order", key=f"inc_confirm_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update({
                                            "status": "confirmed", "producer_confirmed": True,
                                        }).eq("id", o["id"]).execute()
                                        prod_id     = o.get("product_id")
                                        qty_ordered = float(o["quantity_ordered"])
                                        qty_msg = ""
                                        if prod_id:
                                            prod_row = supabase.table("products").select("quantity").eq("id", prod_id).execute()
                                            if prod_row.data:
                                                current_qty = float(prod_row.data[0]["quantity"])
                                                new_qty     = max(0.0, current_qty - qty_ordered)
                                                supabase.table("products").update({
                                                    "quantity": new_qty, "is_available": new_qty > 0,
                                                }).eq("id", prod_id).execute()
                                                qty_msg = f"Stock: {current_qty:,.1f} → {new_qty:,.1f} {unit}"
                                        send_notification(
                                            recipient_id=o["buyer_id"], title="✅ Order Confirmed",
                                            message=(
                                                f"Your order for **{pname}** ({qty_ordered:,.1f} {unit}) "
                                                f"worth **{o['total_price_birr']:,.0f} Birr** has been confirmed."
                                            ),
                                            notif_type="success", order_id=o["id"],
                                        )
                                        st.success(f"✅ Order Confirmed! {qty_msg}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed: {e}")

                                if st.button("❌ Cancel Order", key=f"inc_cancel_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update({"status": "cancelled"}).eq("id", o["id"]).execute()
                                        send_notification(
                                            recipient_id=o["buyer_id"], title="🚫 Order Cancelled",
                                            message=f"Your order for **{pname}** was cancelled by the producer.",
                                            notif_type="warning", order_id=o["id"],
                                        )
                                        st.warning("🚫 Order cancelled. Buyer notified.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed: {e}")

                            elif o["status"] == "confirmed" and cls["is_regular_order"]:
                                if st.button("🚚 Mark as Delivered", key=f"inc_deliver_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update({"status": "delivered"}).eq("id", o["id"]).execute()
                                        send_notification(
                                            recipient_id=o["buyer_id"], title="🚚 Order Delivered!",
                                            message=f"Your order for **{pname}** has been marked as delivered.",
                                            notif_type="success", order_id=o["id"],
                                        )
                                        st.success("🚚 Delivered! Buyer notified.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed: {e}")

                            if is_agreement:
                                try:
                                    buyer_profile_res = supabase.table("profiles").select("*").eq("id", o["buyer_id"]).execute()
                                    buyer_profile = buyer_profile_res.data[0] if buyer_profile_res.data else {}
                                except Exception:
                                    buyer_profile = {}

                                render_agreement_terms_inline(o, prod, profile, buyer_profile, f"inc_{o['id']}")

                                if st.button("📄 Download Agreement PDF", key=f"inc_pdf_{o['id']}", use_container_width=True):
                                    delivery_str = datetime.date.today()
                                    payment_str  = "Bank Transfer"
                                    if o.get("agreement_delivery_date"):
                                        try:
                                            delivery_str = datetime.date.fromisoformat(o["agreement_delivery_date"])
                                        except Exception:
                                            pass
                                    if o.get("agreement_payment_method"):
                                        payment_str = o["agreement_payment_method"]

                                    pdf_bytes = generate_agreement_pdf(
                                        producer_name=profile.get("full_name",""), producer_phone=profile.get("phone",""),
                                        producer_region=profile.get("region",""),
                                        merchant_name=buyer_profile.get("full_name", buyer_name),
                                        merchant_phone=buyer_profile.get("phone",""), merchant_region=buyer_profile.get("region",""),
                                        product_name=pname, sector=prod.get("sector",""), quality_grade=prod.get("quality_grade",""),
                                        quantity=o["quantity_ordered"], unit=unit,
                                        price_per_unit=o["total_price_birr"] / o["quantity_ordered"] if o["quantity_ordered"] else 0,
                                        total_price=o["total_price_birr"], delivery_date=delivery_str,
                                        payment_method=payment_str, notes=o.get("notes",""),
                                        agreement_id=str(o["id"]), producer_confirmed=prod_confirmed, merchant_confirmed=merch_confirmed,
                                    )
                                    st.session_state.agreement_preview_pdf = pdf_bytes
                                    st.session_state.agreement_preview_ref = str(o["id"])
                                    st.rerun()

        # ── FINALIZE AGREEMENT (after merchant confirmed request) ──
        if st.session_state.get("agreement_pending_order_id"):
            oid = st.session_state.agreement_pending_order_id
            try:
                o_res = supabase.table("orders").select(
                    "*, products(product_name, unit, sector, quality_grade, region, producer_id), profiles(full_name, phone, region)"
                ).eq("id", oid).execute()
                o = o_res.data[0] if o_res.data else None
            except Exception:
                o = None

            if o:
                prod  = o.get("products") or {}
                buyer = o.get("profiles") or {}
                st.divider()
                st.markdown(f"### 📝 Build Agreement for confirmed order — {buyer.get('full_name','Merchant')}")
                with st.container(border=True):
                    agr_delivery = st.date_input("Delivery Date", key=f"final_delivery_{oid}")
                    agr_payment  = st.selectbox("Payment Method",
                                                 ["Cash", "Bank Transfer", "Mobile Money", "Credit"],
                                                 key=f"final_payment_{oid}")
                    agr_notes    = st.text_area("Additional Notes (optional)", key=f"final_notes_{oid}")

                    col_fin, col_cancel = st.columns(2)
                    with col_fin:
                        if st.button("✅ Finalize Agreement", key=f"final_send_{oid}", use_container_width=True):
                            try:
                                supabase.table("orders").update({
                                    "agreement_delivery_date":  str(agr_delivery),
                                    "agreement_payment_method": agr_payment,
                                    "notes":                    agr_notes,
                                }).eq("id", oid).execute()
                                pdf_bytes = generate_agreement_pdf(
                                    producer_name=profile.get("full_name",""), producer_phone=profile.get("phone",""),
                                    producer_region=profile.get("region",""),
                                    merchant_name=buyer.get("full_name",""), merchant_phone=buyer.get("phone",""),
                                    merchant_region=buyer.get("region",""),
                                    product_name=prod.get("product_name",""), sector=prod.get("sector",""),
                                    quality_grade=prod.get("quality_grade",""), quantity=o["quantity_ordered"],
                                    unit=prod.get("unit",""),
                                    price_per_unit=o["total_price_birr"]/o["quantity_ordered"] if o["quantity_ordered"] else 0,
                                    total_price=o["total_price_birr"], delivery_date=agr_delivery,
                                    payment_method=agr_payment, notes=agr_notes,
                                    agreement_id=str(oid), producer_confirmed=True, merchant_confirmed=True,
                                )
                                send_notification(
                                    recipient_id=o["buyer_id"], title="🤝 Agreement Document Ready",
                                    message=f"The formal agreement for **{prod.get('product_name','')}** is ready.",
                                    notif_type="success", order_id=oid,
                                )
                                st.session_state.agreement_pdf = pdf_bytes
                                st.session_state.agreement_ref = str(oid)
                                st.session_state.agreement_merchant_name = buyer.get("full_name", "")
                                st.session_state.agreement_pending_order_id = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                    with col_cancel:
                        if st.button("✖ Cancel", key=f"final_cancel_{oid}", use_container_width=True):
                            st.session_state.agreement_pending_order_id = None
                            st.rerun()

        if st.session_state.get("agreement_preview_pdf"):
            st.divider()
            st.subheader("📄 Agreement Document")
            ref = st.session_state.get("agreement_preview_ref", "agreement")
            st.markdown(
                download_pdf_link(
                    st.session_state.agreement_preview_pdf,
                    f"Agreement-{ref[:8].upper()}.pdf",
                    f"📥 Download Agreement PDF (Ref: {ref[:8].upper()})"
                ), unsafe_allow_html=True
            )
            if st.button("✖ Close Preview", key="close_inc_preview_pdf"):
                st.session_state.agreement_preview_pdf = None
                st.session_state.agreement_preview_ref = None
                st.rerun()


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
    st.caption(f"**{profile['full_name']}** · Producer · {profile['region']}")
    st.divider()
    st.markdown("### 📊 My Stats")
    try:
        my_products = supabase.table("products").select("*") \
            .eq("producer_id", st.session_state.user.id).execute().data or []
        active   = sum(1 for p in my_products if p["is_available"])
        inactive = len(my_products) - active
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Listings", len(my_products))
        c2.metric("Active",   active)
        c3.metric("Inactive", inactive)
    except Exception as e:
        st.error(f"Could not load stats: {e}")
