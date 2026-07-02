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
# CONSTANTS
# ════════════════════════════════════════════════════════════
REGIONS  = ["Addis Ababa", "Oromia", "SNNPR", "Amhara", "Tigray", "Sidama", "Dire Dawa", "Harari"]
SECTORS  = ["Agriculture", "Manufacturing", "Handicrafts", "Livestock", "Food Processing", "Textiles", "Services"]
UNITS    = ["quintal", "kg", "piece", "head", "unit", "meter", "service"]
GRADES   = ["A", "B", "C"]

SESSION_KEYS = [
    "user", "profile", "edit_product_id", "show_pref_form",
    "agreement_product_id", "agreement_merchant",
    "agreement_pdf", "agreement_ref", "agreement_merchant_name",
    "agreement_pending_order_id", "agreement_preview_pdf",
    "agreement_preview_ref",
]

AGREEMENT_TERMS = [
    ("Quality Assurance",
     "The Producer guarantees that goods delivered shall conform to the agreed quality grade "
     "as specified above. Any goods failing to meet this standard shall be rejected and replaced "
     "at the Producer's cost within 7 business days."),
    ("Payment Terms",
     "Payment shall be made via the agreed payment method upon delivery and confirmation of goods. "
     "Late payment beyond 14 days of delivery date shall attract a penalty of 2% per month "
     "on the outstanding amount."),
    ("Delivery & Transfer of Risk",
     "The Producer shall deliver goods by the agreed delivery date. Risk and title transfer to the "
     "Merchant upon successful delivery and written or verbal acceptance. Delivery delays "
     "exceeding 7 days without notice shall entitle the Merchant to cancel this agreement."),
    ("Dispute Resolution",
     "Any disputes arising from this agreement shall first be resolved through good-faith "
     "negotiation between the parties. Failing resolution within 30 days, disputes shall be "
     "referred to the Ethiopian Commercial Dispute Resolution Centre or relevant regional "
     "trade bureau."),
    ("Force Majeure",
     "Neither party shall be liable for delays or failures caused by circumstances beyond "
     "their reasonable control including natural disasters, government restrictions, or "
     "civil unrest, provided written notice is given within 5 days of such event."),
    ("Governing Law",
     "This agreement is governed by the Commercial Code of Ethiopia (Proclamation No. 1243/2021) "
     "and applicable regional trade regulations."),
]

# ════════════════════════════════════════════════════════════
# SESSION STATE INIT
# ════════════════════════════════════════════════════════════
for _k in SESSION_KEYS:
    if _k not in st.session_state:
        st.session_state[_k] = None

# ════════════════════════════════════════════════════════════
# SHARED HELPERS
# ════════════════════════════════════════════════════════════

def _sanitize_email(email: str) -> str:
    email = email.strip()
    email = _re.sub(r"^mailto:", "", email, flags=_re.IGNORECASE)
    email = _re.sub(r"[^ -~]", "", email)
    return email.strip()

def _valid_email(email: str) -> bool:
    return bool(_re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))

def sign_up(email, password, full_name, role, region, phone):
    email = _sanitize_email(email)
    if not _valid_email(email):
        return False, f"Invalid email address: '{email}'. Please check and try again."
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
        supabase.table("profiles").insert({
            "id": auth_res.user.id, "full_name": full_name,
            "role": role, "region": region, "phone": phone
        }).execute()
        return True, "Account created! Please log in."
    except Exception as e:
        return False, f"Sign up failed: {str(e)}"

def sign_in(email, password):
    email = _sanitize_email(email)
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if auth_res.user:
            st.session_state.user    = auth_res.user
            st.session_state.profile = get_profile(auth_res.user.id)
            return True, "Logged in successfully."
        return False, "Invalid credentials."
    except Exception as e:
        return False, f"Login failed: {e}"

def sign_out():
    supabase.auth.sign_out()
    for _k in SESSION_KEYS:
        st.session_state[_k] = None

def get_profile(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    return res.data[0] if res.data else None

def send_notification(recipient_id, title, message, notif_type="info", order_id=None):
    try:
        payload = {
            "recipient_id": str(recipient_id),
            "title": title, "message": message,
            "type": notif_type, "is_read": False,
        }
        if order_id:
            payload["order_id"] = str(order_id)
        result = supabase.table("notifications").insert(payload).execute()
        if not result.data:
            st.toast("⚠️ Notification not saved. Check RLS policy.", icon="⚠️")
    except Exception as e:
        st.toast(f"⚠️ Notification failed: {e}", icon="⚠️")

def get_unread_count(user_id):
    try:
        res = supabase.table("notifications") \
            .select("id", count="exact") \
            .eq("recipient_id", user_id) \
            .eq("is_read", False).execute()
        return res.count or 0
    except Exception:
        return 0

def get_fraud_risk(sector, product, region, payment_method, quantity, price_birr):
    try:
        return check_fraud_risk(
            sector=sector, product=product, region=region,
            payment_method=payment_method, quantity=quantity,
            agreed_price_birr=price_birr, market_price_birr=price_birr,
        )
    except Exception:
        return {"risk_level": "Unknown", "is_fraud": 0, "fraud_probability": 0.0}

def render_fraud_badge(risk):
    badge = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk.get("risk_level"), "⚪")
    st.caption(f"{badge} Fraud Risk: **{risk.get('risk_level', 'Unknown')}**")

def classify_order(o):
    prod_confirmed  = bool(o.get("producer_confirmed"))
    merch_confirmed = bool(o.get("merchant_confirmed"))
    is_agreement    = bool(o.get("agreement_delivery_date"))
    is_producer_request = prod_confirmed and not merch_confirmed and not is_agreement
    is_regular_order    = not is_agreement and not prod_confirmed
    return {
        "prod_confirmed":      prod_confirmed,
        "merch_confirmed":     merch_confirmed,
        "is_agreement":        is_agreement,
        "is_producer_request": is_producer_request,
        "is_regular_order":    is_regular_order,
        "both_confirmed":      prod_confirmed and merch_confirmed,
        "awaiting_buyer":      is_producer_request or (is_agreement and prod_confirmed and not merch_confirmed),
    }

def download_pdf_link(pdf_bytes, filename, label="📄 Download Agreement PDF"):
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    return (
        f'<a href="data:application/pdf;base64,{pdf_b64}" '
        f'download="{filename}" '
        f'style="display:inline-block;padding:10px 20px;background:#1a5276;'
        f'color:white;border-radius:6px;text-decoration:none;font-weight:bold;">'
        f'{label}</a>'
    )

def generate_agreement_pdf(
    producer_name, producer_phone, producer_region,
    merchant_name, merchant_phone, merchant_region,
    product_name, sector, quality_grade,
    quantity, unit, price_per_unit, total_price,
    delivery_date, payment_method, notes,
    agreement_id, producer_confirmed=False, merchant_confirmed=False
):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style    = ParagraphStyle("T", parent=styles["Title"],  fontSize=18,
                                    textColor=colors.HexColor("#1a5276"), alignment=TA_CENTER, spaceAfter=6)
    subtitle_style = ParagraphStyle("S", parent=styles["Normal"], fontSize=10,
                                    textColor=colors.HexColor("#555555"), alignment=TA_CENTER, spaceAfter=4)
    section_style  = ParagraphStyle("H", parent=styles["Heading2"], fontSize=12,
                                    textColor=colors.HexColor("#1a5276"), spaceBefore=14, spaceAfter=6)
    body_style     = ParagraphStyle("B", parent=styles["Normal"], fontSize=10, leading=16, spaceAfter=4)
    small_style    = ParagraphStyle("Sm", parent=styles["Normal"], fontSize=9,
                                    textColor=colors.HexColor("#666666"), leading=14)
    footer_style   = ParagraphStyle("F", parent=styles["Normal"], fontSize=7,
                                    textColor=colors.HexColor("#999999"), alignment=TA_CENTER)

    story = []
    story.append(Paragraph("FEDERAL DEMOCRATIC REPUBLIC OF ETHIOPIA", subtitle_style))
    story.append(Paragraph("Ethiopian AI Supply Chain Platform", subtitle_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a5276")))
    story.append(Spacer(1, 8))
    story.append(Paragraph("COMMERCIAL SUPPLY AGREEMENT", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a5276")))
    story.append(Spacer(1, 10))

    ref_table = Table(
        [["Agreement Reference:", f"AGR-{agreement_id[:8].upper()}",
          "Date:", datetime.date.today().strftime("%d %B %Y")]],
        colWidths=[4*cm, 6*cm, 2.5*cm, 4.5*cm]
    )
    ref_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#1a5276")),
        ("TEXTCOLOR", (2,0), (2,-1), colors.HexColor("#1a5276")),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(ref_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("1. PARTIES TO THE AGREEMENT", section_style))
    parties_table = Table(
        [["", "PRODUCER (Seller)", "MERCHANT (Buyer)"],
         ["Full Name", producer_name, merchant_name],
         ["Region", producer_region, merchant_region],
         ["Phone", producer_phone or "—", merchant_phone or "—"],
         ["Role", "Producer / Seller", "Merchant / Buyer"]],
        colWidths=[3.5*cm, 8*cm, 6*cm]
    )
    parties_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a5276")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#eaf2fb"), colors.white]),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("2. SUBJECT MATTER — GOODS & TERMS", section_style))
    goods_table = Table([
        ["Field", "Details"],
        ["Product Name", product_name], ["Sector", sector],
        ["Quality Grade", f"Grade {quality_grade}"],
        ["Quantity", f"{quantity:,.1f} {unit}"],
        ["Price per Unit", f"{price_per_unit:,.2f} Birr"],
        ["Total Contract Value", f"{total_price:,.2f} Birr"],
        ["Payment Method", payment_method], ["Delivery Date", str(delivery_date)],
    ], colWidths=[5*cm, 12*cm])
    goods_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#117a65")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#e8f8f5"), colors.white]),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("BACKGROUND", (0,6), (-1,6), colors.HexColor("#d5f5e3")),
        ("FONTNAME", (0,6), (-1,6), "Helvetica-Bold"),
        ("TEXTCOLOR", (1,6), (1,6), colors.HexColor("#117a65")),
        ("FONTSIZE", (1,6), (1,6), 11),
    ]))
    story.append(goods_table)
    story.append(Spacer(1, 14))

    next_section = 3
    if notes and notes.strip():
        story.append(Paragraph("3. ADDITIONAL NOTES & SPECIAL CONDITIONS", section_style))
        story.append(Paragraph(notes, body_style))
        story.append(Spacer(1, 10))
        next_section = 4

    story.append(Paragraph(f"{next_section}. GENERAL TERMS AND CONDITIONS", section_style))
    for i, (heading, text) in enumerate(AGREEMENT_TERMS, 1):
        story.append(Paragraph(f"<b>{next_section}.{i}  {heading}</b>", body_style))
        story.append(Paragraph(text, small_style))
        story.append(Spacer(1, 4))
    story.append(Spacer(1, 14))

    p_status    = "✅ CONFIRMED" if producer_confirmed else "⏳ PENDING"
    m_status    = "✅ CONFIRMED" if merchant_confirmed else "⏳ PENDING"
    both_status = "✅ FULLY EXECUTED" if (producer_confirmed and merchant_confirmed) else "⏳ AWAITING BOTH PARTIES"
    story.append(Paragraph(f"{next_section + 1}. CONFIRMATION STATUS", section_style))
    status_table = Table([
        ["Party", "Status"],
        ["Producer (Seller)", p_status], ["Merchant (Buyer)", m_status],
        ["Agreement Status", both_status],
    ], colWidths=[7*cm, 10*cm])
    status_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#f2f3f4"), colors.white]),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("BACKGROUND", (0,3), (-1,3),
         colors.HexColor("#d5f5e3") if (producer_confirmed and merchant_confirmed) else colors.HexColor("#fdebd0")),
        ("FONTNAME", (0,3), (-1,3), "Helvetica-Bold"),
    ]))
    story.append(status_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph(f"{next_section + 2}. SIGNATURES", section_style))
    story.append(Paragraph(
        "By signing below, both parties confirm they have read, understood, and agreed to all "
        "terms and conditions set forth in this agreement.", small_style))
    story.append(Spacer(1, 16))
    sig_table = Table([
        ["PRODUCER (Seller)", "", "MERCHANT (Buyer)", ""],
        [f"Name: {producer_name}", "", f"Name: {merchant_name}", ""],
        ["", "", "", ""],
        ["Signature: ____________________", "", "Signature: ____________________", ""],
        ["", "", "", ""],
        ["Date: ____________________", "", "Date: ____________________", ""],
        ["", "", "", ""],
        [f"Phone: {producer_phone or '_______________'}", "",
         f"Phone: {merchant_phone or '_______________'}", ""],
        [f"Region: {producer_region}", "", f"Region: {merchant_region}", ""],
    ], colWidths=[7.5*cm, 1*cm, 7.5*cm, 1*cm])
    sig_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,0), colors.HexColor("#1a5276")),
        ("TEXTCOLOR", (2,0), (2,0), colors.HexColor("#117a65")),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("BOX", (0,0), (0,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("BOX", (2,0), (2,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("BACKGROUND", (0,0), (0,0), colors.HexColor("#eaf2fb")),
        ("BACKGROUND", (2,0), (2,0), colors.HexColor("#e8f8f5")),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"This agreement was facilitated by the Ethiopian AI Supply Chain Platform | "
        f"Wolaita Sodo University — Department of ECE | "
        f"Generated: {datetime.datetime.now().strftime('%d %B %Y, %H:%M')} | "
        f"Ref: AGR-{agreement_id[:8].upper()}", footer_style))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def render_agreement_terms_inline(order_row, product_row, producer_profile, merchant_profile, container_key):
    qty       = order_row.get("quantity_ordered", 0) or 0
    total     = order_row.get("total_price_birr", 0) or 0
    unit_price = (total / qty) if qty else 0
    unit      = product_row.get("unit", "")
    delivery  = order_row.get("agreement_delivery_date") or "Not yet set"
    payment   = order_row.get("agreement_payment_method") or "Not yet set"
    notes     = order_row.get("notes") or ""
    with st.expander("📋 Read Agreement Terms", expanded=False):
        st.markdown("#### Parties")
        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown(f"**Producer (Seller):** {producer_profile.get('full_name', 'N/A')}")
            st.caption(f"📍 {producer_profile.get('region', 'N/A')} · 📞 {producer_profile.get('phone') or 'N/A'}")
        with pc2:
            st.markdown(f"**Merchant (Buyer):** {merchant_profile.get('full_name', 'N/A')}")
            st.caption(f"📍 {merchant_profile.get('region', 'N/A')} · 📞 {merchant_profile.get('phone') or 'N/A'}")
        st.markdown("#### Goods & Terms")
        st.markdown(
            f"- **Product:** {product_row.get('product_name','N/A')} "
            f"({product_row.get('sector','N/A')}, Grade {product_row.get('quality_grade','N/A')})\n"
            f"- **Quantity:** {qty:,.1f} {unit}\n"
            f"- **Price per Unit:** {unit_price:,.2f} Birr\n"
            f"- **Total Contract Value:** {total:,.2f} Birr\n"
            f"- **Payment Method:** {payment}\n"
            f"- **Delivery Date:** {delivery}"
        )
        if notes.strip():
            st.markdown("#### Additional Notes")
            st.write(notes)
        st.markdown("#### General Terms and Conditions")
        for heading, text in AGREEMENT_TERMS:
            st.markdown(f"**{heading}**")
            st.caption(text)

# ════════════════════════════════════════════════════════════
# SHARED TAB RENDERERS
# ════════════════════════════════════════════════════════════

def render_browse_tab(role, profile):
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
                st.markdown(f'**{p["product_name"]}** · {p["sector"]} · Grade **{p["quality_grade"]}**')
                st.caption(p.get("description") or "No description")
                seller = p.get("profiles")
                if seller:
                    st.caption(f'👤 {seller.get("full_name","Unknown")} · 📍 {p["region"]}')
            with c2:
                st.metric("Price", f'{p["price_birr"]:,.0f} Birr')
                st.caption(f'Available: {p["quantity"]} {p["unit"]}')
            with c3:
                if role in ("merchant", "customer"):
                    _qty_max = max(1.0, float(p["quantity"]))
                    qty_to_order = st.number_input(
                        "Qty", min_value=1.0, max_value=_qty_max,
                        value=min(1.0, _qty_max), key=f'qty_{p["id"]}'
                    )
                    total = qty_to_order * p["price_birr"]
                    st.caption(f"Total: **{total:,.0f} Birr**")
                    risk = get_fraud_risk(
                        sector=p["sector"], product=p["product_name"],
                        region=p["region"], payment_method="Bank Transfer",
                        quantity=qty_to_order, price_birr=p["price_birr"],
                    )
                    render_fraud_badge(risk)
                    if st.button("🛒 Place Order", key=f'order_{p["id"]}'):
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


def render_notifications_tab(user_id):
    hcol1, hcol2 = st.columns([3, 1])
    with hcol1:
        st.subheader("🔔 Notifications")
        st.caption("Order confirmations, deliveries, and updates appear here")
    with hcol2:
        if st.button("✅ Mark All Read", use_container_width=True, key="mark_all_read"):
            try:
                supabase.table("notifications").update({"is_read": True}) \
                    .eq("recipient_id", user_id).eq("is_read", False).execute()
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")
    try:
        notifs = supabase.table("notifications").select("*") \
            .eq("recipient_id", user_id).order("created_at", desc=True).limit(50).execute().data or []
    except Exception as e:
        st.error(f"Could not load notifications: {e}")
        notifs = []

    if not notifs:
        st.info("No notifications yet.")
        return

    icon_map   = {"success":"✅","warning":"🚫","error":"❌","info":"ℹ️"}
    bg_map     = {"success":"#e8f8f5","warning":"#fef9e7","error":"#fdedec","info":"#eaf2fb"}
    border_map = {"success":"117a65","warning":"f39c12","error":"e74c3c","info":"1a5276"}

    def _fmt_dt(s):
        try:
            return datetime.datetime.fromisoformat(s.replace("Z","+00:00")).strftime("%d %b %Y, %H:%M") if s else ""
        except Exception:
            return str(s)[:16]

    unread_notifs = [n for n in notifs if not n.get("is_read")]
    read_notifs   = [n for n in notifs if n.get("is_read")]

    if unread_notifs:
        st.markdown(f"### 🔴 Unread ({len(unread_notifs)})")
        for n in unread_notifs:
            ntype = n.get("type","info")
            st.markdown(
                f"<div style='background:{bg_map.get(ntype,'#eaf2fb')};border-radius:8px;"
                f"padding:14px 16px;margin-bottom:10px;"
                f"border-left:4px solid #{border_map.get(ntype,'1a5276')};'>"
                f"<b>{icon_map.get(ntype, '🔔')}</b><br>"
                f'{n["message"]}<br>'
                f"<small style='color:#888;'>{_fmt_dt(n.get('created_at',''))}</small></div>",
                unsafe_allow_html=True
            )
            ncol1, _ = st.columns([1, 5])
            with ncol1:
                if st.button("✓ Read", key=f'read_{n["id"]}', use_container_width=True):
                    try:
                        supabase.table("notifications").update({"is_read":True}).eq("id",n["id"]).execute()
                        st.rerun()
                    except Exception:
                        pass

    if read_notifs:
        with st.expander(f"📂 Read notifications ({len(read_notifs)})", expanded=False):
            for n in read_notifs:
                ntype = n.get("type","info")
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


# ════════════════════════════════════════════════════════════
# SIDEBAR — login / user info (used by all role pages)
# ════════════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        st.title("🌾 AI Supply Chain")
        st.caption("Ethiopian Multi-Sector Commerce")
        st.divider()

        if st.session_state.get("user") is None:
            tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])
            with tab_login:
                login_email = st.text_input("Email",    key="sb_login_email")
                login_pass  = st.text_input("Password", type="password", key="sb_login_pass")
                if st.button("Log In", use_container_width=True, key="sb_login_btn"):
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
                su_name   = st.text_input("Full Name", key="sb_su_name")
                su_email  = st.text_input("Email",     key="sb_su_email")
                su_pass   = st.text_input("Password",  type="password", key="sb_su_pass",
                                          help="Min 8 chars, letters + numbers")
                su_role   = st.selectbox("I am a...", ["producer","merchant","customer"], key="sb_su_role")
                su_region = st.selectbox("Region", REGIONS, key="sb_su_region")
                su_phone  = st.text_input("Phone Number", key="sb_su_phone")
                if st.button("Create Account", use_container_width=True, key="sb_signup_btn"):
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
            role = profile["role"] if profile else None
            st.success(f"Welcome, {profile['full_name'] if profile else 'User'}")
            st.caption(f'Role: {profile["role"].capitalize() if profile else 'N/A'}')
            st.caption(f'Region: {profile["region"] if profile else 'N/A'}')
            unread = get_unread_count(st.session_state.user.id)
            if unread:
                st.info(f"🔔 {unread} unread notification(s)")
            if st.button("Log Out", use_container_width=True, key="sb_logout_btn"):
                sign_out()
                st.rerun()
            return profile, role


# ════════════════════════════════════════════════════════════
# LANDING / AUTH PAGE
# ════════════════════════════════════════════════════════════

def show_landing():
    st.markdown("""
        <style>
            /* ── Hide Streamlit chrome on landing ── */
            [data-testid="stSidebar"]        { display: none; }
            [data-testid="collapsedControl"] { display: none; }
            #MainMenu, footer, header        { visibility: hidden; }

            /* ── Design tokens ── */
            :root {
                --forest:   #1B4332;
                --leaf:     #2D6A4F;
                --canopy:   #40916C;
                --sprout:   #74C69D;
                --wheat:    #D4A017;
                --gold:     #F4C430;
                --cream:    #FBF7EE;
                --charcoal: #1C1C1E;
                --mist:     #F0F4F1;
            }

            /* ── Global page background ── */
            .stApp { background: var(--cream) !important; }
            [data-testid="stAppViewContainer"] > .main { background: var(--cream) !important; }

            /* ── Hero banner ── */
            .hero-wrap {
                background: linear-gradient(135deg, var(--forest) 0%, var(--leaf) 55%, var(--canopy) 100%);
                border-radius: 20px;
                padding: 52px 48px 44px;
                margin-bottom: 36px;
                position: relative;
                overflow: hidden;
            }
            .hero-wrap::before {
                content: "";
                position: absolute;
                inset: 0;
                background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.04'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
            }
            .hero-eyebrow {
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 3px;
                text-transform: uppercase;
                color: var(--gold);
                margin-bottom: 14px;
                font-family: 'Inter', sans-serif;
            }
            .hero-title {
                font-size: clamp(28px, 4vw, 46px);
                font-weight: 800;
                color: #ffffff;
                line-height: 1.15;
                margin: 0 0 16px;
                font-family: 'Georgia', serif;
            }
            .hero-title span { color: var(--gold); }
            .hero-sub {
                font-size: 15px;
                color: rgba(255,255,255,0.82);
                line-height: 1.7;
                max-width: 560px;
                margin: 0 0 28px;
                font-family: 'Inter', sans-serif;
            }
            .hero-badges { display: flex; gap: 10px; flex-wrap: wrap; }
            .badge {
                background: rgba(255,255,255,0.12);
                border: 1px solid rgba(255,255,255,0.22);
                color: #fff;
                padding: 5px 14px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 500;
                backdrop-filter: blur(4px);
            }
            .badge-gold {
                background: var(--wheat);
                border-color: var(--gold);
                color: var(--forest);
                font-weight: 700;
            }

            /* ── Stats strip ── */
            .stats-strip {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
                margin-bottom: 32px;
            }
            .stat-card {
                background: #fff;
                border: 1px solid #e8ede9;
                border-radius: 14px;
                padding: 22px 20px;
                text-align: center;
                box-shadow: 0 2px 8px rgba(27,67,50,0.06);
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }
            .stat-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(27,67,50,0.12); }
            .stat-num {
                font-size: 28px;
                font-weight: 800;
                color: var(--forest);
                font-family: 'Georgia', serif;
                display: block;
            }
            .stat-label {
                font-size: 12px;
                color: #6b7c6e;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-top: 4px;
                display: block;
            }

            /* ── Role cards ── */
            .roles-row {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 14px;
                margin-bottom: 36px;
            }
            .role-card {
                background: #fff;
                border: 2px solid #e0e9e2;
                border-radius: 14px;
                padding: 22px 18px 18px;
                transition: border-color 0.2s, transform 0.15s;
            }
            .role-card:hover { border-color: var(--canopy); transform: translateY(-3px); }
            .role-icon  { font-size: 28px; margin-bottom: 10px; display: block; }
            .role-name  { font-size: 14px; font-weight: 700; color: var(--forest); margin-bottom: 5px; font-family: 'Inter', sans-serif; }
            .role-desc  { font-size: 12px; color: #6b7c6e; line-height: 1.6; }

            /* ── Auth panel ── */
            .auth-panel {
                background: #fff;
                border: 1px solid #dde8de;
                border-radius: 20px;
                padding: 32px 30px 28px;
                box-shadow: 0 4px 24px rgba(27,67,50,0.08);
            }
            .auth-heading {
                font-size: 20px;
                font-weight: 700;
                color: var(--forest);
                font-family: 'Georgia', serif;
                margin-bottom: 4px;
            }
            .auth-sub {
                font-size: 13px;
                color: #7a8c7c;
                margin-bottom: 24px;
            }
            .divider-text {
                text-align: center;
                color: #aabba1;
                font-size: 12px;
                letter-spacing: 1px;
                margin: 8px 0;
                position: relative;
            }
            .divider-text::before, .divider-text::after {
                content: "";
                position: absolute;
                top: 50%;
                width: 38%;
                height: 1px;
                background: #dde8de;
            }
            .divider-text::before { left: 0; }
            .divider-text::after  { right: 0; }

            /* ── Streamlit widget overrides ── */
            .stTextInput > label, .stSelectbox > label { color: var(--forest) !important; font-weight: 600 !important; font-size: 13px !important; }
            .stTextInput > div > div > input {
                border: 1.5px solid #c8d9c9 !important;
                border-radius: 10px !important;
                background: #ffffff !important;
                color: #1C1C1E !important;
            }
            .stTextInput > div > div > input::placeholder {
                color: #9aab9c !important;
                opacity: 1 !important;
            }
            .stTextInput > div > div > input:focus {
                border-color: var(--canopy) !important;
                box-shadow: 0 0 0 3px rgba(64,145,108,0.15) !important;
                color: #1C1C1E !important;
            }
            [data-testid="stTabs"] [data-baseweb="tab-list"] {
                gap: 0;
                background: var(--mist);
                border-radius: 10px;
                padding: 4px;
                margin-bottom: 20px;
            }
            [data-testid="stTabs"] [data-baseweb="tab"] {
                border-radius: 8px !important;
                font-weight: 600 !important;
                font-size: 13px !important;
                color: #5a7060 !important;
            }
            [data-testid="stTabs"] [aria-selected="true"] {
                background: var(--forest) !important;
                color: #fff !important;
            }
            .stButton > button[kind="primary"] {
                background: linear-gradient(135deg, var(--forest), var(--canopy)) !important;
                border: none !important;
                border-radius: 10px !important;
                font-weight: 700 !important;
                letter-spacing: 0.5px !important;
                height: 44px !important;
                font-size: 14px !important;
                transition: opacity 0.15s !important;
            }
            .stButton > button[kind="primary"]:hover { opacity: 0.88 !important; }

            /* ── Footer strip ── */
            .landing-footer {
                text-align: center;
                font-size: 11px;
                color: #9aab9c;
                padding: 24px 0 8px;
                letter-spacing: 0.5px;
            }
            .landing-footer a { color: var(--canopy); text-decoration: none; }
        </style>

        <!-- ══ HERO ══ -->
        <div class="hero-wrap">
            <p class="hero-eyebrow">🌍 Wolaita Sodo University · Department of ECE</p>
            <h1 class="hero-title">Ethiopian <span>AI Supply Chain</span><br>Platform</h1>
            <p class="hero-sub">
                Connecting smallholder farmers, processing hubs, and consumers
                through machine-learning–powered matching, real-time price intelligence,
                and fraud-resistant trade agreements.
            </p>
            <div class="hero-badges">
                <span class="badge badge-gold">⚡ AI Price Engine</span>
                <span class="badge">🤝 Smart Matchmaking</span>
                <span class="badge">🛡️ Fraud Detection</span>
                <span class="badge">📈 Demand Forecasting</span>
            </div>
        </div>

        <!-- ══ STATS ══ -->
        <div class="stats-strip">
            <div class="stat-card">
                <span class="stat-num">13+</span>
                <span class="stat-label">Crop Categories</span>
            </div>
            <div class="stat-card">
                <span class="stat-num">11</span>
                <span class="stat-label">Ethiopian Regions</span>
            </div>
            <div class="stat-card">
                <span class="stat-num">3</span>
                <span class="stat-label">AI Engines Active</span>
            </div>
        </div>

        <!-- ══ ROLE CARDS ══ -->
        <div class="roles-row">
            <div class="role-card">
                <span class="role-icon">🚜</span>
                <div class="role-name">Producers</div>
                <div class="role-desc">List crops, get AI price recommendations, and accept purchase contracts directly from merchants.</div>
            </div>
            <div class="role-card">
                <span class="role-icon">🏬</span>
                <div class="role-name">Merchants</div>
                <div class="role-desc">Source verified produce via AI matchmaking, run demand forecasts, and manage bulk procurement.</div>
            </div>
            <div class="role-card">
                <span class="role-icon">🛒</span>
                <div class="role-name">Customers</div>
                <div class="role-desc">Browse certified commodities and order directly from verified farmers at fair market prices.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Auth panel rendered inside styled wrapper ──
    st.markdown('<div class="auth-panel">', unsafe_allow_html=True)
    st.markdown('<div class="auth-heading">Access Your Account</div>', unsafe_allow_html=True)
    st.markdown('<div class="auth-sub">Sign in to your dashboard or register a new entity below.</div>', unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔐  Sign In", "📝  Register"])

    with tab_login:
        email    = st.text_input("Email Address", key="login_email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", key="login_password", placeholder="••••••••")
        if st.button("Sign In →", use_container_width=True, type="primary", key="login_btn"):
            if not email or not password:
                st.warning("Please enter your email and password.")
            else:
                with st.spinner("Authenticating…"):
                    ok, msg = sign_in(email, password)
                if ok:
                    st.rerun()
                else:
                    st.error(msg)

    with tab_register:
        reg_name     = st.text_input("Full Name",        key="reg_name",     placeholder="Abebe Girma")
        reg_email    = st.text_input("Email Address",    key="reg_email",    placeholder="abebe@example.com")
        reg_password = st.text_input("Password",         type="password",    key="reg_password", placeholder="Min. 8 characters")
        col_r, col_reg = st.columns(2)
        with col_r:
            reg_role   = st.selectbox("I am a…", ["producer", "merchant", "customer"], key="reg_role")
        with col_reg:
            reg_region = st.selectbox("Region", REGIONS, key="reg_region")
        reg_phone  = st.text_input("Phone (optional)", key="reg_phone", placeholder="+251 9xx xxx xxx")
        if st.button("Create Account →", use_container_width=True, type="primary", key="reg_btn"):
            if not all([reg_name, reg_email, reg_password]):
                st.warning("Name, email, and password are required.")
            else:
                with st.spinner("Creating your account…"):
                    ok, msg = sign_up(reg_email, reg_password, reg_name, reg_role, reg_region, reg_phone)
                if ok:
                    st.success(msg)
                    st.info("Account created — please go to Sign In to continue.")
                else:
                    st.error(msg)

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
        <div class="landing-footer">
            Ethiopian AI Supply Chain Platform &nbsp;·&nbsp; Wolaita Sodo University, Dept. of ECE &nbsp;·&nbsp;
            Built with Streamlit + Supabase
        </div>
    """, unsafe_allow_html=True)



# ════════════════════════════════════════════════════════════
# ROLE PAGES — stubs (built step by step)
# ════════════════════════════════════════════════════════════

def show_producer(profile):
    st.title(f"🚜 Producer Dashboard")
    st.info("Producer dashboard coming soon.")

def show_merchant(profile):
    st.title("🏬 Merchant Dashboard")
    st.info("Merchant dashboard coming soon.")

def show_customer(profile):
    st.title("🛒 Customer Dashboard")
    st.info("Customer dashboard coming soon.")

def show_admin(profile):
    st.title("🛡️ Admin Panel")
    st.info("Admin panel coming soon.")


# ════════════════════════════════════════════════════════════
# MAIN ROUTER
# ════════════════════════════════════════════════════════════

profile, role = render_sidebar()

if st.session_state.get("user") is None:
    show_landing()
elif profile is None:
    fetched = get_profile(st.session_state.user.id)
    if fetched:
        st.session_state.profile = fetched
        st.rerun()
    else:
        st.error("Could not load your profile. Please sign out and try again.")
        if st.button("Sign Out"):
            sign_out()
            st.rerun()
elif role == "producer":
    show_producer(profile)
elif role == "merchant":
    show_merchant(profile)
elif role == "customer":
    show_customer(profile)
elif role == "admin":
    show_admin(profile)
else:
    st.warning("Unknown role. Please contact support.")
