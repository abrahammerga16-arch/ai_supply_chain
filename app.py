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
    with st.expander("📋 Read Agreement Terms", expanded=False, key=f"terms_{container_key}"):
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
    # If not logged in, landing page handles auth in main area
    if st.session_state.get("user") is None:
        return None, None

    with st.sidebar:
        st.title("🌾 AI Supply Chain")
        st.caption("Ethiopian Multi-Sector Commerce")
        st.divider()

        profile = st.session_state.get("profile") or get_profile(st.session_state.user.id)
        st.session_state.profile = profile
        role = profile["role"] if profile else None

        st.success(f"👤 {profile['full_name'] if profile else 'User'}")
        st.caption(f"Role: {profile['role'].capitalize() if profile else 'N/A'}")
        st.caption(f"Region: {profile['region'] if profile else 'N/A'}")

        unread = get_unread_count(st.session_state.user.id)
        if unread:
            st.info(f"🔔 {unread} unread notification(s)")

        st.divider()
        if st.button("🚪 Log Out", use_container_width=True, key="sb_logout_btn"):
            sign_out()
            st.rerun()

        return profile, role


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
                background: var(--mist) !important;
            }
            .stTextInput > div > div > input:focus {
                border-color: var(--canopy) !important;
                box-shadow: 0 0 0 3px rgba(64,145,108,0.15) !important;
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
# PRODUCER DASHBOARD
# ════════════════════════════════════════════════════════════

def show_producer(profile):
    role = "producer"
    _unread = get_unread_count(st.session_state.user.id)
    _notif_label = f"🔔 Notifications ({_unread})" if _unread > 0 else "🔔 Notifications"

    tab_browse, tab_add, tab_listings, tab_incoming, tab_notif, tab_profile = st.tabs([
        "📦 Browse", "➕ Add Product", "📋 My Listings",
        "📬 Incoming Orders", _notif_label, "⚙️ Profile"
    ])

    # ── BROWSE ────────────────────────────────────────────────
    with tab_browse:
        render_browse_tab(role, profile)

    # ── ADD PRODUCT ───────────────────────────────────────────
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
                st.info(
                    f'💰 AI Suggested Price: **{rec["recommended_price"]:,.0f} Birr** '
                    f'(range: {rec["min_price"]:,.0f} – {rec["max_price"]:,.0f} Birr)'
                )
            except Exception:
                pass
        with st.form("add_product_form"):
            p_qty   = st.number_input("Quantity", min_value=0.1, step=1.0,  key="add_qty")
            p_unit  = st.selectbox("Unit", UNITS, key="add_unit")
            p_price = st.number_input("Price per Unit (Birr)", min_value=1.0, step=10.0, key="add_price")
            p_desc  = st.text_area("Description (optional)", key="add_desc")
            if st.form_submit_button("✅ Submit Listing", use_container_width=True):
                if not p_name or p_qty <= 0 or p_price <= 0:
                    st.warning("Fill in product name, quantity, and price.")
                else:
                    try:
                        supabase.table("products").insert({
                            "producer_id": st.session_state.user.id,
                            "sector": p_sector, "product_name": p_name,
                            "quantity": p_qty, "unit": p_unit,
                            "price_birr": p_price, "quality_grade": p_quality,
                            "region": p_region, "description": p_desc,
                            "is_available": True,
                        }).execute()
                        st.success(f"✅ '{p_name}' listed successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to list product: {e}")

    # ── MY LISTINGS ───────────────────────────────────────────
    with tab_listings:
        st.subheader("📋 My Listings")

        # Agreement draft flow (from merchant-match button)
        if st.session_state.agreement_product_id and st.session_state.agreement_merchant:
            m   = st.session_state.agreement_merchant
            pid = st.session_state.agreement_product_id
            try:
                prod_row = supabase.table("products").select("*").eq("id", pid).execute().data
                prod_row = prod_row[0] if prod_row else {}
            except Exception:
                prod_row = {}

            st.markdown(f'### 🤝 Draft Agreement with **{m["name"]}**')
            with st.container(border=True):
                col_contact, col_terms = st.columns(2)
                with col_contact:
                    st.markdown("#### 📞 Merchant Contact")
                    st.markdown(f'**Name:** {m["name"]}')
                    st.markdown(f"**Region:** {m.get('region','N/A')}")
                    st.markdown(f"**Phone:** {m.get('phone') or 'Not provided'}")
                    st.markdown(f"**Preferred Product:** {m.get('preferred_product') or 'N/A'}")
                    st.markdown(f"**Payment Method:** {m.get('payment_method') or 'N/A'}")
                    st.markdown(f"**Max Budget:** {m.get('max_budget_birr',0):,.0f} Birr")
                with col_terms:
                    st.markdown("#### 📝 Agreement Terms")
                    agr_qty_max  = max(0.1, float(prod_row.get("quantity",1000)))
                    agr_qty      = st.number_input("Quantity", min_value=0.1, max_value=agr_qty_max,
                                                   value=min(10.0, agr_qty_max), step=1.0, key="agr_qty")
                    agr_price    = st.number_input("Agreed Price per Unit (Birr)", min_value=1.0,
                                                   value=float(prod_row.get("price_birr",100)), step=10.0, key="agr_price")
                    agr_delivery = st.date_input("Delivery Date", key="agr_delivery")
                    agr_payment  = st.selectbox("Payment Method",
                                                ["Cash","Bank Transfer","Mobile Money","Credit"], key="agr_payment")
                    agr_notes    = st.text_area("Additional Notes (optional)", key="agr_notes")
                    agr_total    = agr_qty * agr_price
                    st.info(f"💰 Total: **{agr_total:,.0f} Birr**")

            if st.button("👁️ Preview Agreement PDF", use_container_width=True, key="preview_agr_btn"):
                preview_pdf = generate_agreement_pdf(
                    producer_name=profile.get("full_name",""), producer_phone=profile.get("phone",""),
                    producer_region=profile.get("region",""), merchant_name=m["name"],
                    merchant_phone=m.get("phone",""), merchant_region=m.get("region",""),
                    product_name=prod_row.get("product_name",""), sector=prod_row.get("sector",""),
                    quality_grade=prod_row.get("quality_grade",""), quantity=agr_qty,
                    unit=prod_row.get("unit",""), price_per_unit=agr_price, total_price=agr_total,
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
                            "product_id": pid, "buyer_id": m["id"],
                            "quantity_ordered": agr_qty, "total_price_birr": agr_total,
                            "status": "pending", "fraud_risk_level": "Low", "fraud_probability": 0.05,
                            "producer_confirmed": True, "merchant_confirmed": False,
                            "agreement_delivery_date": str(agr_delivery),
                            "agreement_payment_method": agr_payment,
                            "notes": f"Producer-initiated agreement. Payment: {agr_payment}. Delivery: {agr_delivery}. {agr_notes}",
                        }).execute()
                        order_id = order_res.data[0]["id"] if order_res.data else "N/A"
                        send_notification(
                            recipient_id=m["id"],
                            title="🤝 New Agreement From Producer",
                            message=(
                                f"**{profile.get('full_name','A producer')}** has sent you a supply agreement "
                                f"for **{prod_row.get('product_name','a product')}** — "
                                f"{agr_qty:,.1f} {prod_row.get('unit','')} @ {agr_price:,.0f} Birr/unit "
                                f"(Total: {agr_total:,.0f} Birr). Go to 🛒 My Orders to accept or reject."
                            ),
                            notif_type="info", order_id=str(order_id),
                        )
                        pdf_bytes = generate_agreement_pdf(
                            producer_name=profile.get("full_name",""), producer_phone=profile.get("phone",""),
                            producer_region=profile.get("region",""), merchant_name=m["name"],
                            merchant_phone=m.get("phone",""), merchant_region=m.get("region",""),
                            product_name=prod_row.get("product_name",""), sector=prod_row.get("sector",""),
                            quality_grade=prod_row.get("quality_grade",""), quantity=agr_qty,
                            unit=prod_row.get("unit",""), price_per_unit=agr_price, total_price=agr_total,
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

        # Show generated agreement download
        if st.session_state.get("agreement_pdf"):
            st.success(
                f"✅ Agreement sent to **{st.session_state.get('agreement_merchant_name','')}**! "
                "They must now accept it in their My Orders tab. Download your copy below."
            )
            ref = st.session_state.get("agreement_ref","agreement")
            st.markdown(
                download_pdf_link(st.session_state.agreement_pdf, f"Agreement-{ref[:8].upper()}.pdf"),
                unsafe_allow_html=True
            )
            if st.button("✖ Dismiss", key="dismiss_pdf"):
                st.session_state.agreement_pdf = None
                st.session_state.agreement_ref = None
                st.rerun()
            st.divider()

        # Products list
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
                        st.markdown(f'**{p["product_name"]}** · {p["sector"]} · Grade {p["quality_grade"]}')
                        st.caption(f'{p["quantity"]} {p["unit"]} @ {p["price_birr"]:,.0f} Birr | {p["region"]}')
                        st.caption(p.get("description") or "")
                    with c2:
                        st.caption("🟢 Active" if p["is_available"] else "🔴 Inactive")

                    col_toggle, col_edit, col_delete = st.columns(3)
                    with col_toggle:
                        label = "⏸ Deactivate" if p["is_available"] else "▶ Activate"
                        if st.button(label, key=f'toggle_{p["id"]}', use_container_width=True):
                            try:
                                supabase.table("products").update(
                                    {"is_available": not p["is_available"]}
                                ).eq("id", p["id"]).execute()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Update failed: {e}")
                    with col_edit:
                        if st.button("✏️ Edit", key=f'edit_btn_{p["id"]}', use_container_width=True):
                            st.session_state.edit_product_id = p["id"]
                    with col_delete:
                        if st.button("🗑️ Delete", key=f'del_{p["id"]}', use_container_width=True):
                            try:
                                supabase.table("products").delete().eq("id", p["id"]).execute()
                                st.success("'{}' deleted.".format(p["product_name"]))
                                st.rerun()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")

                    if st.session_state.edit_product_id == p["id"]:
                        st.markdown("---")
                        st.markdown("**✏️ Edit Product**")
                        with st.form(f'edit_form_{p["id"]}'):
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
                                        "product_name": e_name, "sector": e_sector,
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
                    if st.button("🤖 Find Best Merchant Matches", key=f'match_{p["id"]}', use_container_width=True):
                        with st.spinner("Scoring merchants..."):
                            try:
                                merchants_raw = supabase.table("profiles").select("*").eq("role","merchant").execute().data
                                listing_data  = {
                                    "sector": p["sector"], "product_name": p["product_name"],
                                    "price_birr": p["price_birr"], "quantity": p["quantity"],
                                    "quality_grade": p["quality_grade"], "region": p["region"],
                                    "is_verified": 1, "delivery_available": 1,
                                    "producer_rating": 4.0, "producer_experience": 3,
                                    "producer_tx": 0, "return_rate": 0.05,
                                }
                                merchant_list = [{
                                    "id": m["id"], "name": m["full_name"], "phone": m.get("phone"),
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
                                                    f'{badge} **{r["name"]}** — {pct:.1f}% match · '
                                                    f"{r.get('region','N/A')} · "
                                                    f"wants {r.get('preferred_product') or 'N/A'} · "
                                                    f"📞 {r.get('phone') or 'N/A'}"
                                                )
                                            with mcol2:
                                                req_qty = st.number_input(
                                                    "Qty", min_value=0.1,
                                                    max_value=max(0.1, float(p["quantity"])),
                                                    value=min(10.0, max(0.1, float(p["quantity"]))),
                                                    step=1.0, key=f'reqqty_{p["id"]}_{r["id"]}'
                                                )
                                                if st.button("📩 Send Order Request",
                                                             key=f'agr_{p["id"]}_{r["id"]}',
                                                             use_container_width=True):
                                                    try:
                                                        req_total = req_qty * p["price_birr"]
                                                        order_res = supabase.table("orders").insert({
                                                            "product_id": p["id"], "buyer_id": r["id"],
                                                            "quantity_ordered": req_qty,
                                                            "total_price_birr": req_total,
                                                            "status": "pending",
                                                            "fraud_risk_level": "Low",
                                                            "fraud_probability": 0.05,
                                                            "producer_confirmed": True,
                                                            "merchant_confirmed": False,
                                                            "notes": (
                                                                f"Producer-initiated order request for "
                                                                f'{p["product_name"]}. No agreement yet — '
                                                                f"awaiting merchant confirmation."
                                                            ),
                                                        }).execute()
                                                        new_order_id = order_res.data[0]["id"] if order_res.data else None
                                                        send_notification(
                                                            recipient_id=r["id"],
                                                            title="📩 New Order Request From Producer",
                                                            message=(
                                                                f"**{profile.get('full_name','A producer')}** wants to sell you "
                                                                f'**{p["product_name"]}** — {req_qty:,.1f} {p["unit"]} @ '
                                                                f'{p["price_birr"]:,.0f} Birr/unit (Total: {req_total:,.0f} Birr). '
                                                                f"Go to 🛒 My Orders to confirm or decline."
                                                            ),
                                                            notif_type="info",
                                                            order_id=str(new_order_id) if new_order_id else None,
                                                        )
                                                        st.success(f'📩 Order request sent to {r["name"]}.')
                                                        st.rerun()
                                                    except Exception as e:
                                                        st.error(f"Failed: {e}")
                            except Exception as e:
                                st.error(f"Matching failed: {e}")

                    # Demand forecast
                    try:
                        fc = forecast_demand(p["product_name"], p["region"], weeks_ahead=4)
                    except Exception:
                        fc = None
                    if fc and "error" not in fc:
                        trend_icon  = {"up":"🟢 ↑ Rising","down":"🔴 ↓ Falling","stable":"🟡 → Stable"}[fc["trend"]]
                        all_labels  = [f"W-{7-i}" for i in range(8)] + [f"+{w}w" for w in fc["weeks"]]
                        hist_series = fc["historical"] + [None] * 4
                        fc_series   = [None] * 7 + [fc["historical"][-1]] + fc["forecast"]
                        chart_data  = pd.DataFrame({"Actual": hist_series, "Forecast": fc_series}, index=all_labels)
                        st.caption(f'📈 Demand Forecast | {trend_icon} | R²={fc["r2"]:.2f} RMSE=±{fc["rmse"]:,.0f}')
                        st.line_chart(chart_data, color=["#4A90D9","#F5A623"], height=180)
                    else:
                        st.caption("📈 Demand forecast unavailable.")

    # ── INCOMING ORDERS ───────────────────────────────────────
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

                inc_status_filter = st.selectbox("Filter by Status",
                    ["All","pending","confirmed","delivered","cancelled"], key="inc_status_filter")
                filtered = incoming if inc_status_filter == "All" else \
                    [o for o in incoming if o["status"] == inc_status_filter]

                if not filtered:
                    st.info("No orders match this filter.")
                else:
                    st.markdown(f"**{len(filtered)} order(s):**")
                    for o in filtered:
                        prod         = o.get("products") or {}
                        buyer        = o.get("profiles") or {}
                        pname        = prod.get("product_name","Unknown")
                        unit         = prod.get("unit","")
                        buyer_name   = buyer.get("full_name","Unknown buyer")
                        buyer_phone  = buyer.get("phone","N/A")
                        buyer_region = buyer.get("region","N/A")
                        cls                 = classify_order(o)
                        is_agreement        = cls["is_agreement"]
                        prod_confirmed      = cls["prod_confirmed"]
                        merch_confirmed     = cls["merch_confirmed"]
                        both_confirmed      = cls["both_confirmed"]
                        is_producer_request = cls["is_producer_request"]

                        status_badge = {"pending":"🟡 Pending","confirmed":"🔵 Confirmed",
                                        "delivered":"🟢 Delivered","cancelled":"🔴 Cancelled"}.get(o["status"], o["status"])

                        if o["status"] == "pending":
                            st.markdown(
                                "<div style='border-left:4px solid #f39c12;padding-left:8px;margin-bottom:4px;'>"
                                "🆕 <b>New Order Received</b></div>", unsafe_allow_html=True)

                        with st.container(border=True):
                            col_a, col_b, col_c = st.columns([3, 2, 2])
                            with col_a:
                                st.markdown(f"**{pname}** · {prod.get('sector','N/A')} · Grade **{prod.get('quality_grade','N/A')}**")
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
                                    st.caption(f'📝 {o["notes"]}')
                                risk_lvl = o.get("fraud_risk_level","Unknown")
                                if risk_lvl and risk_lvl != "Unknown":
                                    rb = {"Low":"🟢","Medium":"🟡","High":"🔴"}.get(risk_lvl,"⚪")
                                    st.caption(f"{rb} Fraud Risk: **{risk_lvl}**")
                            with col_b:
                                st.metric("Order Value", f'{o["total_price_birr"]:,.0f} Birr')
                                st.caption(status_badge)
                                created = o.get("created_at","")
                                if created:
                                    try:
                                        dt = datetime.datetime.fromisoformat(created.replace("Z","+00:00"))
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
                                    if st.button("📝 Create Agreement", key=f'mk_agr_{o["id"]}', use_container_width=True):
                                        st.session_state.agreement_pending_order_id = o["id"]
                                        st.rerun()
                                elif o["status"] == "pending" and cls["is_regular_order"]:
                                    if st.button("✅ Confirm Order", key=f'inc_confirm_{o["id"]}', use_container_width=True):
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
                                                    f'worth **{o["total_price_birr"]:,.0f} Birr** has been confirmed.'
                                                ),
                                                notif_type="success", order_id=o["id"],
                                            )
                                            st.success(f"✅ Order Confirmed! {qty_msg}")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Failed: {e}")
                                    if st.button("❌ Cancel Order", key=f'inc_cancel_{o["id"]}', use_container_width=True):
                                        try:
                                            supabase.table("orders").update({"status":"cancelled"}).eq("id",o["id"]).execute()
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
                                    if st.button("🚚 Mark as Delivered", key=f'inc_deliver_{o["id"]}', use_container_width=True):
                                        try:
                                            supabase.table("orders").update({"status":"delivered"}).eq("id",o["id"]).execute()
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
                                render_agreement_terms_inline(o, prod, profile, buyer_profile, f'inc_{o["id"]}')
                                if st.button("📄 Download Agreement PDF", key=f'inc_pdf_{o["id"]}', use_container_width=True):
                                    delivery_str = datetime.date.today()
                                    payment_str  = "Bank Transfer"
                                    if o.get("agreement_delivery_date"):
                                        try: delivery_str = datetime.date.fromisoformat(o["agreement_delivery_date"])
                                        except Exception: pass
                                    if o.get("agreement_payment_method"):
                                        payment_str = o["agreement_payment_method"]
                                    pdf_bytes = generate_agreement_pdf(
                                        producer_name=profile.get("full_name",""), producer_phone=profile.get("phone",""),
                                        producer_region=profile.get("region",""),
                                        merchant_name=buyer_profile.get("full_name", buyer_name),
                                        merchant_phone=buyer_profile.get("phone",""), merchant_region=buyer_profile.get("region",""),
                                        product_name=pname, sector=prod.get("sector",""), quality_grade=prod.get("quality_grade",""),
                                        quantity=o["quantity_ordered"], unit=unit,
                                        price_per_unit=o["total_price_birr"]/o["quantity_ordered"] if o["quantity_ordered"] else 0,
                                        total_price=o["total_price_birr"], delivery_date=delivery_str,
                                        payment_method=payment_str, notes=o.get("notes",""),
                                        agreement_id=str(o["id"]), producer_confirmed=prod_confirmed, merchant_confirmed=merch_confirmed,
                                    )
                                    st.session_state.agreement_preview_pdf = pdf_bytes
                                    st.session_state.agreement_preview_ref = str(o["id"])
                                    st.rerun()

        # Finalize agreement (after merchant confirmed request)
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
                prod_  = o.get("products") or {}
                buyer_ = o.get("profiles") or {}
                st.divider()
                st.markdown(f"### 📝 Build Agreement for confirmed order — {buyer_.get('full_name','Merchant')}")
                with st.container(border=True):
                    agr_delivery = st.date_input("Delivery Date", key=f"final_delivery_{oid}")
                    agr_payment  = st.selectbox("Payment Method",
                                                 ["Cash","Bank Transfer","Mobile Money","Credit"],
                                                 key=f"final_payment_{oid}")
                    agr_notes    = st.text_area("Additional Notes (optional)", key=f"final_notes_{oid}")
                    col_fin, col_cancel_fin = st.columns(2)
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
                                    merchant_name=buyer_.get("full_name",""), merchant_phone=buyer_.get("phone",""),
                                    merchant_region=buyer_.get("region",""),
                                    product_name=prod_.get("product_name",""), sector=prod_.get("sector",""),
                                    quality_grade=prod_.get("quality_grade",""), quantity=o["quantity_ordered"],
                                    unit=prod_.get("unit",""),
                                    price_per_unit=o["total_price_birr"]/o["quantity_ordered"] if o["quantity_ordered"] else 0,
                                    total_price=o["total_price_birr"], delivery_date=agr_delivery,
                                    payment_method=agr_payment, notes=agr_notes,
                                    agreement_id=str(oid), producer_confirmed=True, merchant_confirmed=True,
                                )
                                send_notification(
                                    recipient_id=o["buyer_id"], title="🤝 Agreement Document Ready",
                                    message=f"The formal agreement for **{prod_.get('product_name','')}** is ready.",
                                    notif_type="success", order_id=oid,
                                )
                                st.session_state.agreement_pdf = pdf_bytes
                                st.session_state.agreement_ref = str(oid)
                                st.session_state.agreement_merchant_name = buyer_.get("full_name","")
                                st.session_state.agreement_pending_order_id = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                    with col_cancel_fin:
                        if st.button("✖ Cancel", key=f"final_cancel_{oid}", use_container_width=True):
                            st.session_state.agreement_pending_order_id = None
                            st.rerun()

        if st.session_state.get("agreement_preview_pdf"):
            st.divider()
            st.subheader("📄 Agreement Document")
            ref = st.session_state.get("agreement_preview_ref","agreement")
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

    # ── NOTIFICATIONS ─────────────────────────────────────────
    with tab_notif:
        render_notifications_tab(st.session_state.user.id)

    # ── PROFILE ───────────────────────────────────────────────
    with tab_profile:
        st.subheader("⚙️ My Profile")
        st.caption(f'**{profile["full_name"]}** · Producer · {profile["region"]}')
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


# ════════════════════════════════════════════════════════════
# MERCHANT DASHBOARD
# ════════════════════════════════════════════════════════════

def show_merchant(profile):
    role = "merchant"
    _unread = get_unread_count(st.session_state.user.id)
    _notif_label = f"🔔 Notifications ({_unread})" if _unread > 0 else "🔔 Notifications"

    tab_browse, tab_matches, tab_orders, tab_place, tab_notif = st.tabs([
        "📦 Browse", "🤖 Best Matches", "🛒 My Orders", "🛍️ Place Order", _notif_label
    ])

    # ── BROWSE ────────────────────────────────────────────────
    with tab_browse:
        render_browse_tab(role, profile)

    # ── BEST MATCHES ──────────────────────────────────────────
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
            buyer_region = profile.get("region","")
            pref_sector  = profile.get("preferred_sector","")
            pref_product = (profile.get("preferred_product") or "").lower()
            pref_quality = profile.get("preferred_quality","Any")
            max_budget   = float(profile.get("max_budget_birr") or 0)

            def score_product_m(p):
                score = 0.0
                if p.get("region") == buyer_region:                score += 30
                if pref_sector and p.get("sector") == pref_sector: score += 25
                if pref_product and pref_product in p.get("product_name","").lower(): score += 30
                if pref_quality and pref_quality != "Any":
                    if pref_quality == "A or B" and p.get("quality_grade") in ("A","B"): score += 10
                    elif p.get("quality_grade") == pref_quality:                          score += 10
                if max_budget > 0 and p.get("price_birr",0) <= max_budget:               score += 5
                return score

            top_products = sorted(all_products, key=score_product_m, reverse=True)[:10]
            st.markdown(f"**Showing top {len(top_products)} matches for you:**")
            for p in top_products:
                pct    = min(int(score_product_m(p)), 100)
                seller = p.get("profiles") or {}
                mc     = "🟢" if pct >= 60 else ("🟡" if pct >= 30 else "🔴")
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    with c1:
                        st.markdown(f'**{p["product_name"]}** · {p["sector"]} · Grade **{p["quality_grade"]}**')
                        st.caption(p.get("description") or "No description")
                        st.caption(f"👤 {seller.get('full_name','Unknown')} · 📍 {p['region']}")
                        st.caption(f"{mc} Match Score: **{pct}%**")
                    with c2:
                        st.metric("Price", f'{p["price_birr"]:,.0f} Birr')
                        st.caption(f'Available: {p["quantity"]} {p["unit"]}')
                    with c3:
                        _qty_max = max(1.0, float(p["quantity"]))
                        qty_to_order = st.number_input(
                            "Qty", min_value=1.0, max_value=_qty_max,
                            value=min(1.0, _qty_max), key=f'match_qty_{p["id"]}'
                        )
                        total = qty_to_order * p["price_birr"]
                        st.caption(f"Total: **{total:,.0f} Birr**")
                        if st.button("🛒 Order Now", key=f'match_order_{p["id"]}'):
                            risk = get_fraud_risk(
                                sector=p["sector"], product=p["product_name"], region=p["region"],
                                payment_method="Bank Transfer", quantity=qty_to_order, price_birr=p["price_birr"],
                            )
                            try:
                                supabase.table("orders").insert({
                                    "product_id": p["id"], "buyer_id": st.session_state.user.id,
                                    "quantity_ordered": qty_to_order, "total_price_birr": total,
                                    "status": "pending", "fraud_risk_level": risk["risk_level"],
                                    "fraud_probability": risk.get("fraud_probability",0.0),
                                }).execute()
                                st.success(f"✅ Order placed — {total:,.0f} Birr")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Order failed: {e}")

    # ── MY ORDERS ─────────────────────────────────────────────
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
                    prod         = o.get("products") or {}
                    pname        = prod.get("product_name","Unknown product")
                    unit         = prod.get("unit","")
                    seller_info  = prod.get("profiles") or {}
                    seller_name  = seller_info.get("full_name","Unknown seller")
                    seller_phone = seller_info.get("phone","N/A")
                    cls                 = classify_order(o)
                    prod_confirmed      = cls["prod_confirmed"]
                    merch_confirmed     = cls["merch_confirmed"]
                    is_agreement        = cls["is_agreement"]
                    both_confirmed      = cls["both_confirmed"]
                    is_regular_order    = cls["is_regular_order"]
                    is_producer_request = cls["is_producer_request"]

                    status_badge = {"pending":"🟡 Pending","confirmed":"🔵 Confirmed",
                                    "delivered":"🟢 Delivered","cancelled":"🔴 Cancelled"}.get(o["status"], o["status"])

                    with st.container(border=True):
                        col_a, col_b, col_c = st.columns([3, 2, 2])
                        with col_a:
                            st.markdown(f"**{pname}**")
                            st.caption(f"Seller: {seller_name} · 📞 {seller_phone}")
                            st.caption(f"📍 {prod.get('region','N/A')} · {prod.get('sector','N/A')}")
                            st.caption(f"Qty: {o['quantity_ordered']} {unit} · Grade: {prod.get('quality_grade','N/A')}")
                            if o.get("notes"):
                                st.caption(f'📝 {o["notes"]}')
                        with col_b:
                            st.metric("Total", f'{o["total_price_birr"]:,.0f} Birr')
                            st.caption(status_badge)
                            risk_lvl = o.get("fraud_risk_level","Unknown")
                            if risk_lvl and risk_lvl != "Unknown":
                                rb = {"Low":"🟢","Medium":"🟡","High":"🔴"}.get(risk_lvl,"⚪")
                                st.caption(f"{rb} Fraud Risk: **{risk_lvl}**")
                        with col_c:
                            if is_producer_request:
                                st.warning("📩 Order request from producer")
                                if st.button("✅ Confirm Order", key=f'confirm_req_{o["id"]}', use_container_width=True):
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
                                if st.button("❌ Decline", key=f'decline_req_{o["id"]}', use_container_width=True):
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
                                    if st.button("✅ Accept Agreement", key=f'accept_agr_{o["id"]}', use_container_width=True):
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
                                    if st.button("❌ Reject Agreement", key=f'reject_agr_{o["id"]}', use_container_width=True):
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
                                if st.button("❌ Cancel Order", key=f'cancel_{o["id"]}', use_container_width=True):
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
                            render_agreement_terms_inline(o, prod, prod_profile, profile, f'my_{o["id"]}')
                            if st.button("📄 Download Agreement PDF", key=f'view_agr_pdf_{o["id"]}', use_container_width=True):
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
                                                                  value=float(o["quantity_ordered"]), step=1.0,
                                                                  key=f'upd_qty_{o["id"]}')
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
                                        st.success("Order updated.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error updating order: {e}")


    # ── PLACE ORDER / PREFERENCES ─────────────────────────────
    with tab_place:
        st.subheader("🛍️ Place Order & Set Buying Preferences")
        st.caption("Set your preferences so AI can recommend the best products for you")

        with st.form("pref_form"):
            pf_sector  = st.selectbox("Preferred Sector", [""] + SECTORS,
                index=([""] + SECTORS).index(profile.get("preferred_sector","") or "") if profile.get("preferred_sector") in ([""] + SECTORS) else 0,
                key="pf_sector")
            pf_product = st.text_input("Preferred Product", value=profile.get("preferred_product") or "", key="pf_product")
            pf_quality = st.selectbox("Preferred Quality Grade", ["Any", "A", "B", "C", "A or B"],
                index=["Any","A","B","C","A or B"].index(profile.get("preferred_quality","Any")) if profile.get("preferred_quality") in ["Any","A","B","C","A or B"] else 0,
                key="pf_quality")
            pf_budget  = st.number_input("Max Budget per Order (Birr)", min_value=0.0,
                value=float(profile.get("max_budget_birr") or 0), step=1000.0, key="pf_budget")
            pf_payment = st.selectbox("Preferred Payment Method", ["Cash","Bank Transfer","Mobile Money","Credit"],
                key="pf_payment")
            pf_delivery = st.checkbox("I need delivery", value=bool(profile.get("needs_delivery")), key="pf_delivery")
            if st.form_submit_button("💾 Save Preferences", use_container_width=True):
                try:
                    supabase.table("profiles").update({
                        "preferred_sector":   pf_sector or None,
                        "preferred_product":  pf_product or None,
                        "preferred_quality":  pf_quality,
                        "max_budget_birr":    pf_budget,
                        "payment_method":     pf_payment,
                        "needs_delivery":     pf_delivery,
                    }).eq("id", st.session_state.user.id).execute()
                    st.success("✅ Preferences saved! AI matching is now active.")
                    st.session_state.profile = None  # force reload
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save: {e}")

    # ── NOTIFICATIONS ─────────────────────────────────────────
    with tab_notif:
        render_notifications_tab(st.session_state.user.id)


# ════════════════════════════════════════════════════════════
# CUSTOMER DASHBOARD
# ════════════════════════════════════════════════════════════

def show_customer(profile):
    _unread = get_unread_count(st.session_state.user.id)
    _notif_label = f"🔔 Notifications ({_unread})" if _unread > 0 else "🔔 Notifications"

    tab_browse, tab_orders, tab_notif, tab_profile = st.tabs([
        "🛒 Browse Products", "📦 My Orders", _notif_label, "⚙️ Profile"
    ])

    with tab_browse:
        render_browse_tab("customer", profile)

    with tab_orders:
        st.subheader("📦 My Orders")
        try:
            orders = supabase.table("orders") \
                .select("*, products(product_name, unit, sector, quality_grade, region, producer_id)") \
                .eq("buyer_id", st.session_state.user.id) \
                .order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Failed to load orders: {e}")
            orders = []

        if not orders:
            st.info("You haven't placed any orders yet. Browse products to get started.")
        else:
            for o in orders:
                prod = o.get("products") or {}
                pname = prod.get("product_name", "Unknown Product")
                unit  = prod.get("unit", "unit")
                status_map = {"pending":"🟡 Pending","confirmed":"🟢 Confirmed",
                              "delivered":"✅ Delivered","cancelled":"🔴 Cancelled"}
                status_badge = status_map.get(o.get("status","pending"), o.get("status",""))
                with st.container(border=True):
                    col_a, col_b = st.columns([3, 2])
                    with col_a:
                        st.markdown(f"**{pname}**")
                        st.caption(f"📍 {prod.get('region','N/A')} · {prod.get('sector','N/A')}")
                        st.caption(f"Qty: {o['quantity_ordered']} {unit} · Grade: {prod.get('quality_grade','N/A')}")
                        if o.get("notes"):
                            st.caption(f"📝 {o['notes']}")
                    with col_b:
                        st.metric("Total", f"{o['total_price_birr']:,.0f} Birr")
                        st.caption(status_badge)
                    if o.get("status") == "pending":
                        if st.button("❌ Cancel Order", key=f"cust_cancel_{o['id']}", use_container_width=True):
                            try:
                                supabase.table("orders").update({"status": "cancelled"}).eq("id", o["id"]).execute()
                                st.success("Order cancelled.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")

    with tab_notif:
        render_notifications_tab(st.session_state.user.id)

    with tab_profile:
        st.subheader("⚙️ My Profile")
        st.write(f"**Name:** {profile.get('full_name','N/A')}")
        st.write(f"**Role:** {profile.get('role','N/A').capitalize()}")
        st.write(f"**Region:** {profile.get('region','N/A')}")
        st.write(f"**Phone:** {profile.get('phone','N/A')}")


# ════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ════════════════════════════════════════════════════════════

def show_admin(profile):
    st.title("🛡️ Admin Control Panel")

    tab_orders, tab_users, tab_products = st.tabs(["📋 All Orders", "👥 All Users", "📦 All Products"])

    with tab_orders:
        st.subheader("All Orders")
        try:
            all_orders = supabase.table("orders").select("*").order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Failed: {e}")
            all_orders = []
        if all_orders:
            import pandas as pd
            df = pd.DataFrame(all_orders)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No orders found.")

    with tab_users:
        st.subheader("Registered Users")
        try:
            users = supabase.table("profiles").select("*").execute().data or []
        except Exception as e:
            st.error(f"Failed: {e}")
            users = []
        if users:
            import pandas as pd
            st.dataframe(pd.DataFrame(users), use_container_width=True)
        else:
            st.info("No users found.")

    with tab_products:
        st.subheader("All Listed Products")
        try:
            products = supabase.table("products").select("*").order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Failed: {e}")
            products = []
        if products:
            import pandas as pd
            st.dataframe(pd.DataFrame(products), use_container_width=True)
        else:
            st.info("No products listed.")


# ════════════════════════════════════════════════════════════
# MAIN ROUTER — entry point
# ════════════════════════════════════════════════════════════

profile, role = render_sidebar()

if st.session_state.get("user") is None:
    show_landing()
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

