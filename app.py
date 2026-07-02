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


# Add model loading status check
@st.cache_resource
def check_models_loaded():
    """Check if all models are loaded successfully"""
    status = {}
    try:
        from src.demand_engine import load_demand_models
        load_demand_models()
        status["demand"] = True
    except Exception as e:
        status["demand"] = str(e)
    
    try:
        from src.fraud_engine import load_fraud_model
        load_fraud_model()
        status["fraud"] = True
    except Exception as e:
        status["fraud"] = str(e)
    
    try:
        from src.matching_engine import load_matching_model
        load_matching_model()
        status["matching"] = True
    except Exception as e:
        status["matching"] = str(e)
    
    return status

# Add to sidebar or landing page
if st.session_state.get("user"):
    model_status = check_models_loaded()
    with st.sidebar.expander("🤖 AI Models Status"):
        for model, status in model_status.items():
            if status is True:
                st.success(f"✅ {model.capitalize()} model loaded")
            else:
                st.error(f"❌ {model.capitalize()}: {status}")
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

def reduce_product_stock(product_id, qty_sold):
    """
    Decrease a product's available quantity after an order is placed.
    Marks the product as unavailable (is_available=False) once stock hits 0.
    Called immediately after every successful order insert.
    """
    try:
        res = supabase.table("products").select("quantity").eq("id", product_id).execute()
        if not res.data:
            return
        current_qty = float(res.data[0].get("quantity") or 0)
        new_qty = max(0.0, current_qty - float(qty_sold))
        update_payload = {"quantity": new_qty}
        if new_qty <= 0:
            update_payload["is_available"] = False
        supabase.table("products").update(update_payload).eq("id", product_id).execute()
    except Exception as e:
        st.toast(f"⚠️ Stock update failed: {e}", icon="⚠️")

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
                            reduce_product_stock(p["id"], qty_to_order)
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
    st.caption(f"Welcome, {profile.get('full_name','Producer')} · {profile.get('region','')}")
    st.divider()

    tab_products, tab_incoming, tab_match, tab_agree, tab_history, tab_notif = st.tabs(["📦 My Products", "📬 Incoming Orders", "🤝 AI Matching", "📄 Agreements", "📜 History", "🔔 Notifications"])

    # ── MY PRODUCTS ───────────────────────────────────────────
    with tab_products:
        st.subheader("📦 My Products")

        # ── Load producer's products ──
        try:
            my_products = supabase.table("products") \
                .select("*") \
                .eq("producer_id", st.session_state.user.id) \
                .order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Could not load products: {e}")
            my_products = []

        # ── Summary metrics ──
        if my_products:
            total_val = sum(p["price_birr"] * p["quantity"] for p in my_products)
            active    = sum(1 for p in my_products if p.get("is_available"))
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Listed", len(my_products))
            m2.metric("Active / Available", active)
            m3.metric("Total Est. Value", f"{total_val:,.0f} Birr")
            st.divider()

        # ── ADD NEW PRODUCT form ──
        with st.expander("➕ Add New Product", expanded=not bool(my_products)):
            with st.form("add_product_form", clear_on_submit=True):
                st.markdown("#### New Product Details")
                c1, c2 = st.columns(2)
                with c1:
                    new_name    = st.text_input("Product Name *", placeholder="e.g. Teff, Coffee, Honey")
                    new_sector  = st.selectbox("Sector *", SECTORS)
                    new_grade   = st.selectbox("Quality Grade *", GRADES)
                    new_region  = st.selectbox("Region *", REGIONS,
                                               index=REGIONS.index(profile.get("region", REGIONS[0]))
                                               if profile.get("region") in REGIONS else 0)
                with c2:
                    new_qty     = st.number_input("Quantity *", min_value=0.1, value=1.0, step=1.0)
                    new_unit    = st.selectbox("Unit *", UNITS)
                    new_price   = st.number_input("Price per Unit (Birr) *", min_value=1.0, value=100.0, step=10.0)
                    new_avail   = st.checkbox("Available for sale", value=True)
                new_desc = st.text_area("Description (optional)", placeholder="Describe quality, harvest date, storage…", height=80)

                # AI price suggestion
                st.caption("💡 Use AI to suggest a price:")
                ai_col1, ai_col2 = st.columns([3, 1])
                with ai_col1:
                    st.caption(f"Sector: **{new_sector}** · Region: **{new_region}** · Grade: **{new_grade}**")
                with ai_col2:
                    get_ai_price = st.form_submit_button("🤖 AI Price", use_container_width=True)

                submitted = st.form_submit_button("✅ Add Product", type="primary", use_container_width=True)

            # Handle AI price (outside form so it doesn't block)
            if get_ai_price:
                try:
                    ai = recommend_price(
                        sector=new_sector, product=new_name or "unknown",
                        region=new_region, quality_grade=new_grade,
                        quantity=new_qty
                    )
                    suggested = ai.get("recommended_price_birr") or ai.get("price") or 0
                    st.info(f"🤖 AI suggested price: **{suggested:,.0f} Birr / {new_unit}**")
                except Exception as e:
                    st.warning(f"AI price unavailable: {e}")

            if submitted:
                if not new_name.strip():
                    st.error("Product name is required.")
                else:
                    try:
                        supabase.table("products").insert({
                            "producer_id":   st.session_state.user.id,
                            "product_name":  new_name.strip(),
                            "sector":        new_sector,
                            "quality_grade": new_grade,
                            "region":        new_region,
                            "quantity":      new_qty,
                            "unit":          new_unit,
                            "price_birr":    new_price,
                            "is_available":  new_avail,
                            "description":   new_desc.strip() or None,
                        }).execute()
                        st.success(f"✅ '{new_name}' listed successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to add product: {e}")

        # ── PRODUCT LIST ──
        if not my_products:
            st.info("You have no products listed yet. Use the form above to add your first product.")
        else:
            st.markdown(f"**{len(my_products)} product(s) listed:**")
            for p in my_products:
                avail_badge = "🟢 Available" if p.get("is_available") else "🔴 Unavailable"
                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 2, 2])

                    with c1:
                        st.markdown(f"**{p['product_name']}** · {p['sector']} · Grade **{p['quality_grade']}**")
                        st.caption(p.get("description") or "No description")
                        st.caption(f"📍 {p['region']}  ·  {avail_badge}")

                    with c2:
                        st.metric("Price", f"{p['price_birr']:,.0f} Birr")
                        st.caption(f"Qty: {p['quantity']} {p['unit']}")

                    with c3:
                        # Toggle availability
                        toggle_label = "🔴 Mark Unavailable" if p.get("is_available") else "🟢 Mark Available"
                        if st.button(toggle_label, key=f"tog_{p['id']}", use_container_width=True):
                            try:
                                supabase.table("products").update(
                                    {"is_available": not p.get("is_available")}
                                ).eq("id", p["id"]).execute()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")

                        # Edit button — sets session state to show edit form
                        if st.button("✏️ Edit", key=f"edit_btn_{p['id']}", use_container_width=True):
                            st.session_state.edit_product_id = p["id"]
                            st.rerun()

                        if st.button("🗑️ Delete", key=f"del_{p['id']}", use_container_width=True):
                            try:
                                supabase.table("products").delete().eq("id", p["id"]).execute()
                                st.success(f"Deleted '{p['product_name']}'.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")

                    # ── Inline edit form ──
                    if st.session_state.get("edit_product_id") == p["id"]:
                        st.divider()
                        st.markdown("##### ✏️ Edit Product")
                        with st.form(f"edit_form_{p['id']}"):
                            ec1, ec2 = st.columns(2)
                            with ec1:
                                e_name   = st.text_input("Product Name",  value=p["product_name"])
                                e_sector = st.selectbox("Sector", SECTORS,
                                                        index=SECTORS.index(p["sector"]) if p["sector"] in SECTORS else 0)
                                e_grade  = st.selectbox("Quality Grade", GRADES,
                                                        index=GRADES.index(p["quality_grade"]) if p["quality_grade"] in GRADES else 0)
                                e_region = st.selectbox("Region", REGIONS,
                                                        index=REGIONS.index(p["region"]) if p["region"] in REGIONS else 0)
                            with ec2:
                                e_qty    = st.number_input("Quantity",  min_value=0.1, value=float(p["quantity"]))
                                e_unit   = st.selectbox("Unit", UNITS,
                                                        index=UNITS.index(p["unit"]) if p["unit"] in UNITS else 0)
                                e_price  = st.number_input("Price (Birr)", min_value=1.0, value=float(p["price_birr"]))
                                e_avail  = st.checkbox("Available", value=bool(p.get("is_available")))
                            e_desc = st.text_area("Description", value=p.get("description") or "", height=80)
                            save_col, cancel_col = st.columns(2)
                            with save_col:
                                save = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
                            with cancel_col:
                                cancel = st.form_submit_button("✖ Cancel", use_container_width=True)

                        if save:
                            try:
                                supabase.table("products").update({
                                    "product_name":  e_name.strip(),
                                    "sector":        e_sector,
                                    "quality_grade": e_grade,
                                    "region":        e_region,
                                    "quantity":      e_qty,
                                    "unit":          e_unit,
                                    "price_birr":    e_price,
                                    "is_available":  e_avail,
                                    "description":   e_desc.strip() or None,
                                }).eq("id", p["id"]).execute()
                                st.session_state.edit_product_id = None
                                st.success("✅ Product updated.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Update failed: {e}")
                        if cancel:
                            st.session_state.edit_product_id = None
                            st.rerun()

    # ── INCOMING ORDERS ───────────────────────────────────────
    with tab_incoming:
        st.subheader("📬 Incoming Orders")
        st.caption("Orders placed on your products — confirm, deliver, or cancel them here.")

        try:
            my_prod_ids = [
                p["id"] for p in
                supabase.table("products").select("id")
                .eq("producer_id", st.session_state.user.id).execute().data or []
            ]
        except Exception as e:
            st.error(f"Could not load your products: {e}")
            my_prod_ids = []

        if not my_prod_ids:
            st.info("You have no listed products yet. Add products first to receive orders.")
        else:
            try:
                incoming = supabase.table("orders")                     .select("*, products(product_name, unit, sector, quality_grade, region), profiles(full_name, phone, region)")                     .in_("product_id", my_prod_ids)                     .order("created_at", desc=True).execute().data or []
            except Exception as e:
                st.error(f"Could not load orders: {e}")
                incoming = []

            if not incoming:
                st.info("No orders received yet.")
            else:
                total_rev       = sum(o["total_price_birr"] for o in incoming if o["status"] == "confirmed")
                pending_count   = sum(1 for o in incoming if o["status"] == "pending")
                confirmed_count = sum(1 for o in incoming if o["status"] == "confirmed")
                delivered_count = sum(1 for o in incoming if o["status"] == "delivered")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Orders",   len(incoming))
                m2.metric("Pending",        pending_count)
                m3.metric("Confirmed",      confirmed_count)
                m4.metric("Delivered",      delivered_count)
                st.divider()

                status_filter = st.selectbox(
                    "Filter by Status",
                    ["All", "pending", "confirmed", "delivered", "cancelled"],
                    key="inc_status_filter"
                )
                filtered = incoming if status_filter == "All" else [
                    o for o in incoming if o["status"] == status_filter
                ]

                if not filtered:
                    st.info(f"No orders with status: {status_filter}")
                else:
                    for o in filtered:
                        prod   = o.get("products") or {}
                        buyer  = o.get("profiles") or {}
                        status = o.get("status", "pending")
                        status_icon = {"pending":"🟡","confirmed":"🟢","delivered":"✅","cancelled":"🔴"}.get(status,"⚪")

                        with st.container(border=True):
                            c1, c2, c3 = st.columns([4, 2, 2])

                            with c1:
                                st.markdown(
                                    f"**{prod.get('product_name','Unknown')}** · "
                                    f"{prod.get('sector','')} · Grade **{prod.get('quality_grade','')}**"
                                )
                                st.caption(
                                    f"👤 Buyer: **{buyer.get('full_name','Unknown')}** · "
                                    f"📞 {buyer.get('phone','N/A')} · 📍 {buyer.get('region','N/A')}"
                                )
                                st.caption(
                                    f"📅 Ordered: {o.get('created_at','')[:10]}  ·  "
                                    f"{status_icon} **{status.capitalize()}**"
                                )
                                if o.get("notes"):
                                    st.caption(f"📝 {o['notes']}")

                            with c2:
                                st.metric("Qty",   f"{o.get('quantity_ordered',0):,.1f} {prod.get('unit','')}")
                                st.metric("Total", f"{o.get('total_price_birr',0):,.0f} Birr")

                            # Detect merchant-initiated agreement orders
                        is_merch_initiated = (
                            bool(o.get("agreement_delivery_date"))
                            and bool(o.get("merchant_confirmed"))
                            and not bool(o.get("producer_confirmed"))
                        )

                        # Show agreement preview for merchant-initiated pending orders
                        if is_merch_initiated and status == "pending":
                            agr_delivery = o.get("agreement_delivery_date", "")[:10]
                            agr_payment  = o.get("agreement_payment_method", "N/A")
                            agr_notes    = o.get("notes") or ""
                            qty          = float(o.get("quantity_ordered", 0))
                            total        = float(o.get("total_price_birr", 0))
                            unit_price   = (total / qty) if qty else 0
                            st.info(
                                f"📋 **Merchant-initiated agreement order**\n\n"
                                f"🗓 Delivery: **{agr_delivery}** · 💳 Payment: **{agr_payment}**"
                                + (f"\n\n📝 Notes: {agr_notes}" if agr_notes else ""),
                            )

                        with c3:
                                if status == "pending":
                                    if is_merch_initiated:
                                        # Accept → sets producer_confirmed=True, both confirmed → confirmed status
                                        if st.button("✅ Accept Agreement", key=f"inc_accept_{o['id']}", use_container_width=True, type="primary"):
                                            try:
                                                supabase.table("orders").update({
                                                    "status": "confirmed",
                                                    "producer_confirmed": True,
                                                }).eq("id", o["id"]).execute()
                                                send_notification(
                                                    recipient_id=o["buyer_id"],
                                                    title="✅ Agreement Accepted by Producer",
                                                    message=(
                                                        f"Your supply agreement for **{prod.get('product_name','')}** "
                                                        f"({o.get('quantity_ordered',0):,.1f} {prod.get('unit','')}) "
                                                        f"has been accepted. Delivery by {o.get('agreement_delivery_date','')[:10]}. "
                                                        f"Total: {o.get('total_price_birr',0):,.0f} Birr."
                                                    ),
                                                    notif_type="success",
                                                    order_id=str(o["id"]),
                                                )
                                                st.success("Agreement accepted — order confirmed.")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Failed: {e}")

                                        if st.button("❌ Decline Agreement", key=f"inc_decline_{o['id']}", use_container_width=True):
                                            try:
                                                supabase.table("orders").update(
                                                    {"status": "cancelled"}
                                                ).eq("id", o["id"]).execute()
                                                send_notification(
                                                    recipient_id=o["buyer_id"],
                                                    title="❌ Agreement Declined by Producer",
                                                    message=(
                                                        f"Your supply agreement request for "
                                                        f"**{prod.get('product_name','')}** "
                                                        f"has been declined by the producer."
                                                    ),
                                                    notif_type="warning",
                                                    order_id=str(o["id"]),
                                                )
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Failed: {e}")
                                    else:
                                        # Regular order — original Confirm / Cancel
                                        if st.button("✅ Confirm", key=f"inc_confirm_{o['id']}", use_container_width=True):
                                            try:
                                                supabase.table("orders").update({
                                                    "status": "confirmed",
                                                    "producer_confirmed": True,
                                                }).eq("id", o["id"]).execute()
                                                send_notification(
                                                    recipient_id=o["buyer_id"],
                                                    title="✅ Order Confirmed by Producer",
                                                    message=(
                                                        f"Your order for **{prod.get('product_name','')}** "
                                                        f"({o.get('quantity_ordered',0):,.1f} {prod.get('unit','')}) "
                                                        f"has been confirmed. Total: {o.get('total_price_birr',0):,.0f} Birr."
                                                    ),
                                                    notif_type="success",
                                                    order_id=str(o["id"]),
                                                )
                                                st.success("Order confirmed.")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Failed: {e}")

                                        if st.button("❌ Cancel", key=f"inc_cancel_{o['id']}", use_container_width=True):
                                            try:
                                                supabase.table("orders").update(
                                                    {"status": "cancelled"}
                                                ).eq("id", o["id"]).execute()
                                                send_notification(
                                                    recipient_id=o["buyer_id"],
                                                    title="❌ Order Cancelled by Producer",
                                                    message=(
                                                        f"Your order for **{prod.get('product_name','')}** "
                                                        f"has been cancelled by the producer."
                                                    ),
                                                    notif_type="warning",
                                                    order_id=str(o["id"]),
                                                )
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Failed: {e}")

                                elif status == "confirmed":
                                    if st.button("🚚 Mark Delivered", key=f"inc_deliver_{o['id']}", use_container_width=True):
                                        try:
                                            supabase.table("orders").update(
                                                {"status": "delivered"}
                                            ).eq("id", o["id"]).execute()
                                            send_notification(
                                                recipient_id=o["buyer_id"],
                                                title="🚚 Order Delivered",
                                                message=(
                                                    f"Your order for **{prod.get('product_name','')}** "
                                                    f"has been marked as delivered. Please confirm receipt."
                                                ),
                                                notif_type="success",
                                                order_id=str(o["id"]),
                                            )
                                            st.success("Marked as delivered.")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Failed: {e}")
                                else:
                                    st.caption(f"No actions for **{status}** orders.")

    # ── AI MERCHANT MATCHING ──────────────────────────────────
    with tab_match:
        st.subheader("🤝 AI Merchant Matching")
        st.caption("Select one of your products — the AI will rank the best-fit merchants to send an order request.")

        # Load producer's products for selection
        try:
            my_products_m = supabase.table("products").select("*")                 .eq("producer_id", st.session_state.user.id)                 .eq("is_available", True).execute().data or []
        except Exception as e:
            st.error(f"Could not load products: {e}")
            my_products_m = []

        if not my_products_m:
            st.info("You have no available products listed. Add and mark products as available first.")
        else:
            product_names = [p["product_name"] for p in my_products_m]
            selected_name = st.selectbox("Select Product to Match", product_names, key="match_product_select")
            p = next((x for x in my_products_m if x["product_name"] == selected_name), None)

            if p:
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Price", f"{p['price_birr']:,.0f} Birr/{p['unit']}")
                mc2.metric("Qty Available", f"{p['quantity']} {p['unit']}")
                mc3.metric("Grade", p.get("quality_grade",""))

                if st.button("🤖 Find Best Merchants", type="primary", use_container_width=True, key="run_match"):
                    try:
                        merchants_raw = supabase.table("profiles").select("*").eq("role", "merchant").execute().data or []
                        if not merchants_raw:
                            st.warning("No merchants registered in the system yet.")
                        else:
                            listing_data = {
                                "sector":               p["sector"],
                                "product_name":         p["product_name"],
                                "price_birr":           p["price_birr"],
                                "quantity":             p["quantity"],
                                "quality_grade":        p["quality_grade"],
                                "region":               p["region"],
                                "is_verified":          1,
                                "delivery_available":   1,
                                "producer_rating":      4.0,
                                "producer_experience":  3,
                                "producer_tx":          0,
                                "return_rate":          0.05,
                            }
                            merchant_list = [{
                                "id":                 m["id"],
                                "name":               m["full_name"],
                                "phone":              m.get("phone"),
                                "region":             m.get("region"),
                                "preferred_sector":   m.get("preferred_sector"),
                                "preferred_product":  m.get("preferred_product"),
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

                            ranked     = rank_merchants(listing_data, merchant_list)
                            top_matches = [r for r in ranked if r["match_probability"] > 0.1][:5]
                            st.session_state["match_results"]  = top_matches
                            st.session_state["match_product"]  = p
                    except Exception as e:
                        st.error(f"Matching failed: {e}")

                # Show results if available
                results = st.session_state.get("match_results")
                match_p = st.session_state.get("match_product")

                if results is not None and match_p and match_p["id"] == p["id"]:
                    if not results:
                        st.info("No strong merchant matches found for this product.")
                    else:
                        st.markdown(f"**Top {len(results)} merchant matches for {p['product_name']}:**")
                        st.divider()
                        for r in results:
                            pct   = r["match_probability"] * 100
                            badge = "🟢" if pct >= 60 else ("🟡" if pct >= 30 else "🔴")

                            with st.container(border=True):
                                rc1, rc2, rc3 = st.columns([4, 2, 2])

                                with rc1:
                                    st.markdown(f"{badge} **{r['name']}** — {pct:.1f}% match")
                                    st.caption(f"📍 {r.get('region','N/A')}  ·  📞 {r.get('phone') or 'N/A'}")
                                    wants = r.get("preferred_product") or r.get("preferred_sector") or "N/A"
                                    budget = r.get("max_budget_birr") or 0
                                    st.caption(f"Wants: **{wants}**  ·  Budget: **{budget:,.0f} Birr**")

                                with rc2:
                                    req_qty = st.number_input(
                                        "Qty to send",
                                        min_value=0.1,
                                        max_value=max(0.1, float(p["quantity"])),
                                        value=min(10.0, max(0.1, float(p["quantity"]))),
                                        step=1.0,
                                        key=f'reqqty_{p["id"]}_{r["id"]}'
                                    )
                                    req_total = req_qty * p["price_birr"]
                                    st.caption(f"Total: **{req_total:,.0f} Birr**")

                                with rc3:
                                    if st.button("📩 Send Request", key=f'send_{p["id"]}_{r["id"]}', use_container_width=True):
                                        try:
                                            order_res = supabase.table("orders").insert({
                                                "product_id":        p["id"],
                                                "buyer_id":          r["id"],
                                                "quantity_ordered":  req_qty,
                                                "total_price_birr":  req_total,
                                                "status":            "pending",
                                                "fraud_risk_level":  "Low",
                                                "fraud_probability": 0.05,
                                                "producer_confirmed":  True,
                                                "merchant_confirmed":  False,
                                                "notes": f"Producer-initiated request for {p['product_name']}. Awaiting merchant confirmation.",
                                            }).execute()
                                            new_order_id = order_res.data[0]["id"] if order_res.data else None
                                            reduce_product_stock(p["id"], req_qty)

                                            # Generate agreement PDF
                                            try:
                                                import datetime as _dt
                                                delivery_date = (_dt.date.today() + _dt.timedelta(days=14)).strftime("%d %B %Y")
                                                pdf_bytes = generate_agreement_pdf(
                                                    producer_name=profile.get("full_name","Producer"),
                                                    producer_phone=profile.get("phone",""),
                                                    producer_region=profile.get("region",""),
                                                    merchant_name=r.get("name","Merchant"),
                                                    merchant_phone=r.get("phone",""),
                                                    merchant_region=r.get("region",""),
                                                    product_name=p["product_name"],
                                                    sector=p.get("sector",""),
                                                    quality_grade=p.get("quality_grade",""),
                                                    quantity=req_qty,
                                                    unit=p.get("unit",""),
                                                    price_per_unit=p["price_birr"],
                                                    total_price=req_total,
                                                    delivery_date=delivery_date,
                                                    payment_method="Bank Transfer",
                                                    notes="Producer-initiated order. Awaiting merchant confirmation.",
                                                    agreement_id=str(new_order_id) if new_order_id else "DRAFT",
                                                    producer_confirmed=True,
                                                    merchant_confirmed=False,
                                                )
                                                fname = f'agreement_{p["product_name"].replace(" ","_")}_{r["name"].replace(" ","_")}.pdf'
                                                st.success(f'📩 Request sent to {r["name"]}!')
                                                st.download_button(
                                                    label="📄 Download Agreement PDF",
                                                    data=pdf_bytes,
                                                    file_name=fname,
                                                    mime="application/pdf",
                                                    key=f'dl_{p["id"]}_{r["id"]}',
                                                    use_container_width=True,
                                                )
                                            except Exception as pdf_err:
                                                st.success(f'📩 Request sent to {r["name"]}!')
                                                st.warning(f"PDF generation failed: {pdf_err}")

                                            send_notification(
                                                recipient_id=r["id"],
                                                title="📩 New Order Request from Producer",
                                                message=(
                                                    f"**{profile.get('full_name','A producer')}** wants to sell you "
                                                    f"**{p['product_name']}** — {req_qty:,.1f} {p['unit']} @ "
                                                    f"{p['price_birr']:,.0f} Birr/unit "
                                                    f"(Total: {req_total:,.0f} Birr). "
                                                    f"A supply agreement has been prepared. Go to My Orders to confirm."
                                                ),
                                                notif_type="info",
                                                order_id=str(new_order_id) if new_order_id else None,
                                            )
                                        except Exception as e:
                                            st.error(f"Failed to send request: {e}")

    # ── NOTIFICATIONS ─────────────────────────────────────────
    with tab_notif:
        st.subheader("🔔 Notifications")
        st.caption("Order confirmations, deliveries, and updates from the platform.")

        uid = st.session_state.user.id

        ncol1, ncol2 = st.columns([3, 1])
        with ncol2:
            if st.button("✅ Mark All Read", use_container_width=True, key="prod_mark_all_read"):
                try:
                    supabase.table("notifications").update({"is_read": True}) \
                        .eq("recipient_id", uid).eq("is_read", False).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

        try:
            notifs = supabase.table("notifications").select("*") \
                .eq("recipient_id", uid) \
                .order("created_at", desc=True).limit(50).execute().data or []
        except Exception as e:
            st.error(f"Could not load notifications: {e}")
            notifs = []

        if not notifs:
            st.info("No notifications yet.")
        else:
            unread = [n for n in notifs if not n.get("is_read")]
            read   = [n for n in notifs if n.get("is_read")]

            with ncol1:
                st.caption(f"**{len(unread)} unread** · {len(read)} read")

            icon_map  = {"success": "✅", "warning": "⚠️", "error": "❌", "info": "ℹ️"}
            color_map = {"success": "#e8f8f5", "warning": "#fef9e7", "error": "#fdedec", "info": "#eaf2fb"}
            border_map = {"success": "#117a65", "warning": "#f39c12", "error": "#e74c3c", "info": "#1a5276"}

            def _fmt_dt(s):
                try:
                    import datetime as _dt
                    return _dt.datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M")
                except Exception:
                    return str(s)[:16]

            def _render_notif(n):
                ntype  = n.get("type", "info")
                icon   = icon_map.get(ntype, "ℹ️")
                bg     = color_map.get(ntype, "#eaf2fb")
                border = border_map.get(ntype, "#1a5276")
                bold   = "font-weight:700;" if not n.get("is_read") else ""
                html = (
                    "<div style=\"background:" + bg + ";border-left:4px solid " + border + ";"
                    "border-radius:8px;padding:12px 16px;margin-bottom:8px;\">"
                    "<div style=\"" + bold + "font-size:14px;\">" + icon + " " + n.get("title","") + "</div>"
                    "<div style=\"font-size:13px;color:#333;margin-top:4px;\">" + n.get("message","") + "</div>"
                    "<div style=\"font-size:11px;color:#888;margin-top:6px;\">🕐 " + _fmt_dt(n.get("created_at","")) + "</div>"
                    "</div>"
                )
                st.markdown(html, unsafe_allow_html=True)
                if not n.get("is_read"):
                    if st.button("Mark read", key=f"prod_read_{n['id']}", use_container_width=False):
                        try:
                            supabase.table("notifications").update({"is_read": True}).eq("id", n["id"]).execute()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")

            if unread:
                st.markdown(f"### 🔴 Unread ({len(unread)})")
                for n in unread:
                    _render_notif(n)

            if read:
                with st.expander(f"📂 Read notifications ({len(read)})"):
                    for n in read:
                        _render_notif(n)


    # ── SUPPLY AGREEMENTS ─────────────────────────────────────
    with tab_agree:
        st.subheader("📄 Supply Agreements")
        st.caption("Generate a formal PDF agreement for any confirmed order.")

        # Load confirmed/delivered orders for this producer's products
        try:
            my_prod_ids_a = [
                p["id"] for p in
                supabase.table("products").select("id")
                .eq("producer_id", st.session_state.user.id).execute().data or []
            ]
        except Exception as e:
            st.error(f"Could not load products: {e}")
            my_prod_ids_a = []

        if not my_prod_ids_a:
            st.info("No products found. Add products first.")
        else:
            try:
                agree_orders = supabase.table("orders") \
                    .select("*, products(product_name, unit, sector, quality_grade, region), profiles(full_name, phone, region)") \
                    .in_("product_id", my_prod_ids_a) \
                    .in_("status", ["confirmed", "delivered"]) \
                    .order("created_at", desc=True).execute().data or []
            except Exception as e:
                st.error(f"Could not load orders: {e}")
                agree_orders = []

            if not agree_orders:
                st.info("No confirmed or delivered orders yet. Confirm incoming orders first to generate agreements.")
            else:
                st.markdown(f"**{len(agree_orders)} order(s) eligible for agreements:**")
                st.divider()

                for o in agree_orders:
                    prod   = o.get("products") or {}
                    buyer  = o.get("profiles") or {}
                    status = o.get("status", "")
                    status_icon = "✅" if status == "delivered" else "🟢"

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([4, 2, 2])

                        with c1:
                            st.markdown(
                                f"**{prod.get('product_name','Unknown')}** · "
                                f"Grade **{prod.get('quality_grade','')}** · "
                                f"{prod.get('sector','')}"
                            )
                            st.caption(
                                f"👤 Buyer: **{buyer.get('full_name','Unknown')}** · "
                                f"📞 {buyer.get('phone','N/A')} · 📍 {buyer.get('region','N/A')}"
                            )
                            st.caption(
                                f"📅 {o.get('created_at','')[:10]}  ·  "
                                f"{status_icon} {status.capitalize()}"
                            )

                        with c2:
                            st.metric("Qty",   f"{o.get('quantity_ordered',0):,.1f} {prod.get('unit','')}")
                            st.metric("Total", f"{o.get('total_price_birr',0):,.0f} Birr")

                        with c3:
                            # Delivery date input per order
                            import datetime as _dt
                            default_delivery = _dt.date.today() + _dt.timedelta(days=14)
                            delivery_date = st.date_input(
                                "Delivery Date",
                                value=default_delivery,
                                key=f"agree_date_{o['id']}",
                            )
                            payment_method = st.selectbox(
                                "Payment",
                                ["Bank Transfer", "Cash on Delivery", "Mobile Money", "Letter of Credit"],
                                key=f"agree_pay_{o['id']}",
                            )

                        notes_val = st.text_input(
                            "Additional notes (optional)",
                            value=o.get("notes") or "",
                            key=f"agree_notes_{o['id']}",
                            placeholder="Special conditions, packaging requirements…"
                        )

                        if st.button(
                            "📄 Generate & Download Agreement PDF",
                            key=f"gen_pdf_{o['id']}",
                            type="primary",
                            use_container_width=True,
                        ):
                            try:
                                qty   = float(o.get("quantity_ordered", 0))
                                total = float(o.get("total_price_birr", 0))
                                unit_price = (total / qty) if qty else 0

                                pdf_bytes = generate_agreement_pdf(
                                    producer_name=profile.get("full_name", "Producer"),
                                    producer_phone=profile.get("phone", ""),
                                    producer_region=profile.get("region", ""),
                                    merchant_name=buyer.get("full_name", "Merchant"),
                                    merchant_phone=buyer.get("phone", ""),
                                    merchant_region=buyer.get("region", ""),
                                    product_name=prod.get("product_name", ""),
                                    sector=prod.get("sector", ""),
                                    quality_grade=prod.get("quality_grade", ""),
                                    quantity=qty,
                                    unit=prod.get("unit", ""),
                                    price_per_unit=unit_price,
                                    total_price=total,
                                    delivery_date=delivery_date.strftime("%d %B %Y"),
                                    payment_method=payment_method,
                                    notes=notes_val.strip(),
                                    agreement_id=str(o["id"]),
                                    producer_confirmed=bool(o.get("producer_confirmed")),
                                    merchant_confirmed=bool(o.get("merchant_confirmed")),
                                )
                                prod_name_safe  = prod.get("product_name","product").replace(" ","_")
                                buyer_name_safe = buyer.get("full_name","buyer").replace(" ","_")
                                fname = f"agreement_{prod_name_safe}_{buyer_name_safe}_{o['id'][:8]}.pdf"
                                st.download_button(
                                    label="⬇️ Click to Download PDF",
                                    data=pdf_bytes,
                                    file_name=fname,
                                    mime="application/pdf",
                                    key=f"dl_pdf_{o['id']}",
                                    use_container_width=True,
                                )
                                st.success("Agreement PDF ready — click above to download.")
                            except Exception as e:
                                st.error(f"PDF generation failed: {e}")


    # ── HISTORY TAB ───────────────────────────────────────────
    with tab_history:
        st.subheader("📜 Delivery History")
        st.caption("All orders that have been delivered — your complete fulfillment record.")

        try:
            hist_prod_ids = [
                p["id"] for p in
                supabase.table("products").select("id")
                .eq("producer_id", st.session_state.user.id).execute().data or []
            ]
        except Exception as e:
            st.error(f"Could not load your products: {e}")
            hist_prod_ids = []

        if not hist_prod_ids:
            st.info("No products found. Add products to start receiving orders.")
        else:
            try:
                hist_orders = supabase.table("orders") \
                    .select("*, products(product_name, unit, sector, quality_grade, region), profiles(full_name, phone, region)") \
                    .in_("product_id", hist_prod_ids) \
                    .eq("status", "delivered") \
                    .order("created_at", desc=True).execute().data or []
            except Exception as e:
                st.error(f"Could not load history: {e}")
                hist_orders = []

            if not hist_orders:
                st.info("No delivered orders yet. Once you mark orders as delivered they will appear here.")
            else:
                # ── Summary metrics ──
                total_rev   = sum(float(o.get("total_price_birr") or 0) for o in hist_orders)
                total_qty   = sum(float(o.get("quantity_ordered") or 0) for o in hist_orders)
                buyer_set   = {o.get("buyer_id") for o in hist_orders}
                hm1, hm2, hm3, hm4 = st.columns(4)
                hm1.metric("Total Deliveries", len(hist_orders))
                hm2.metric("Unique Buyers", len(buyer_set))
                hm3.metric("Total Units Sold", f"{total_qty:,.1f}")
                hm4.metric("Total Revenue", f"{total_rev:,.0f} Birr")
                st.divider()

                # ── Filters ──
                hf1, hf2 = st.columns(2)
                with hf1:
                    h_search = st.text_input("🔍 Search product or buyer", key="ph_search")
                with hf2:
                    h_sort = st.selectbox("Sort by", ["Newest first", "Oldest first", "Highest value", "Lowest value"], key="ph_sort")

                filtered_h = hist_orders
                if h_search:
                    kw = h_search.lower()
                    filtered_h = [
                        o for o in filtered_h
                        if kw in (o.get("products") or {}).get("product_name", "").lower()
                        or kw in (o.get("profiles") or {}).get("full_name", "").lower()
                    ]
                if h_sort == "Oldest first":
                    filtered_h = sorted(filtered_h, key=lambda o: o.get("created_at", ""))
                elif h_sort == "Highest value":
                    filtered_h = sorted(filtered_h, key=lambda o: float(o.get("total_price_birr") or 0), reverse=True)
                elif h_sort == "Lowest value":
                    filtered_h = sorted(filtered_h, key=lambda o: float(o.get("total_price_birr") or 0))

                st.markdown(f"**{len(filtered_h)} delivered order(s):**")

                for o in filtered_h:
                    prod  = o.get("products") or {}
                    buyer = o.get("profiles") or {}
                    both_confirmed = bool(o.get("producer_confirmed")) and bool(o.get("merchant_confirmed"))

                    with st.container(border=True):
                        hc1, hc2, hc3 = st.columns([4, 2, 2])
                        with hc1:
                            st.markdown(
                                f"✅ **{prod.get('product_name','Unknown')}** · "
                                f"{prod.get('sector','')} · Grade **{prod.get('quality_grade','')}**"
                            )
                            st.caption(
                                f"👤 Buyer: **{buyer.get('full_name','Unknown')}** · "
                                f"📞 {buyer.get('phone','N/A')} · 📍 {buyer.get('region','N/A')}"
                            )
                            st.caption(f"📅 Ordered: {o.get('created_at','')[:10]}")
                            if o.get("agreement_delivery_date"):
                                st.caption(f"🗓 Agreed Delivery: {o.get('agreement_delivery_date','')[:10]} · 💳 {o.get('agreement_payment_method','N/A')}")
                            if o.get("notes"):
                                st.caption(f"📝 {o['notes']}")
                        with hc2:
                            st.metric("Qty",   f"{o.get('quantity_ordered',0):,.1f} {prod.get('unit','')}")
                            st.metric("Total", f"{o.get('total_price_birr',0):,.0f} Birr")
                        with hc3:
                            if both_confirmed:
                                st.success("✅ Fully Confirmed")
                            else:
                                st.info("🚚 Delivered · Awaiting buyer confirmation")
                            risk_lvl = o.get("fraud_risk_level", "Unknown")
                            badge = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk_lvl, "⚪")
                            st.caption(f"Fraud Risk: {badge} {risk_lvl}")

                # ── Export to CSV ──
                st.divider()
                if st.button("📥 Export History to CSV", key="ph_export_csv"):
                    rows = []
                    for o in hist_orders:
                        prod  = o.get("products") or {}
                        buyer = o.get("profiles") or {}
                        rows.append({
                            "Order ID":          str(o.get("id",""))[:8],
                            "Product":           prod.get("product_name",""),
                            "Sector":            prod.get("sector",""),
                            "Grade":             prod.get("quality_grade",""),
                            "Buyer":             buyer.get("full_name",""),
                            "Buyer Region":      buyer.get("region",""),
                            "Quantity":          o.get("quantity_ordered",""),
                            "Unit":              prod.get("unit",""),
                            "Total (Birr)":      o.get("total_price_birr",""),
                            "Payment Method":    o.get("agreement_payment_method",""),
                            "Delivery Date":     (o.get("agreement_delivery_date","") or "")[:10],
                            "Date Ordered":      (o.get("created_at","") or "")[:10],
                            "Fraud Risk":        o.get("fraud_risk_level",""),
                            "Fully Confirmed":   "Yes" if (bool(o.get("producer_confirmed")) and bool(o.get("merchant_confirmed"))) else "No",
                        })
                    df_export = pd.DataFrame(rows)
                    csv_bytes = df_export.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv_bytes,
                        file_name="producer_delivery_history.csv",
                        mime="text/csv",
                        key="ph_dl_csv",
                        use_container_width=True,
                    )


def show_merchant(profile):
    st.title("🏬 Merchant Dashboard")
    st.caption(f"Welcome, {profile.get('full_name', 'Merchant')} · 📍 {profile.get('region', 'N/A')}")

    unread = get_unread_count(st.session_state.user.id)
    notif_label = f"🔔 Notifications ({unread} new)" if unread else "🔔 Notifications"

    tab_browse, tab_orders, tab_agree, tab_history, tab_pref, tab_notif = st.tabs([
        "🛒 Browse Products",
        "📋 My Orders",
        "📄 Agreements",
        "📜 History",
        "⚙️ Preferences",
        notif_label,
    ])

    # ── TAB 1: BROWSE PRODUCTS ────────────────────────────────
    with tab_browse:
        st.subheader("🛒 Browse & Order Products")
        st.caption("Discover available products from Ethiopian producers. Place orders directly.")

        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            f_sector = st.selectbox("Sector", ["All"] + SECTORS, key="m_browse_sector")
        with fc2:
            f_region = st.selectbox("Region", ["All"] + REGIONS, key="m_browse_region")
        with fc3:
            f_search = st.text_input("🔍 Search product name", key="m_browse_search")

        f_grade = st.radio("Grade", ["All", "A", "B", "C"], horizontal=True, key="m_browse_grade")

        try:
            q = supabase.table("products").select(
                "*, profiles(full_name, phone, region)"
            ).eq("is_available", True)
            if f_sector != "All":
                q = q.eq("sector", f_sector)
            if f_region != "All":
                q = q.eq("region", f_region)
            if f_grade != "All":
                q = q.eq("quality_grade", f_grade)
            products = q.order("created_at", desc=True).execute().data or []
            if f_search:
                products = [p for p in products if f_search.lower() in p["product_name"].lower()]
        except Exception as e:
            st.error(f"Could not load products: {e}")
            products = []

        if not products:
            st.info("No products match your filters.")
        else:
            st.markdown(f"**{len(products)} product(s) available:**")
            st.divider()
            for p in products:
                seller = p.get("profiles") or {}
                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 2, 2])
                    with c1:
                        st.markdown(
                            f"**{p['product_name']}** · {p['sector']} · Grade **{p['quality_grade']}**"
                        )
                        st.caption(p.get("description") or "No description provided.")
                        st.caption(
                            f"👤 {seller.get('full_name','Unknown Producer')} · "
                            f"📞 {seller.get('phone','N/A')} · 📍 {p.get('region','N/A')}"
                        )
                    with c2:
                        st.metric("Price / Unit", f"{p['price_birr']:,.0f} Birr")
                        st.caption(f"Available: {p['quantity']:,.1f} {p['unit']}")
                    with c3:
                        _max_qty = max(1.0, float(p["quantity"]))
                        qty_order = st.number_input(
                            "Qty to order",
                            min_value=1.0,
                            max_value=_max_qty,
                            value=min(1.0, _max_qty),
                            key=f"m_qty_{p['id']}",
                        )
                        total_birr = qty_order * p["price_birr"]
                        st.caption(f"Total: **{total_birr:,.0f} Birr**")

                        risk = get_fraud_risk(
                            sector=p["sector"], product=p["product_name"],
                            region=p["region"], payment_method="Bank Transfer",
                            quantity=qty_order, price_birr=p["price_birr"],
                        )
                        render_fraud_badge(risk)

                    # ── Agreement fields (full width, below columns) ──
                    import datetime as _dt
                    with st.expander("📋 Agreement Details (required before placing order)", expanded=False):
                        ag1, ag2 = st.columns(2)
                        with ag1:
                            default_delivery = _dt.date.today() + _dt.timedelta(days=14)
                            browse_delivery = st.date_input(
                                "Requested Delivery Date",
                                value=default_delivery,
                                min_value=_dt.date.today() + _dt.timedelta(days=1),
                                key=f"m_browse_delivery_{p['id']}",
                            )
                        with ag2:
                            browse_payment = st.selectbox(
                                "Payment Method",
                                ["Bank Transfer", "Cash on Delivery", "Mobile Money", "Letter of Credit"],
                                key=f"m_browse_payment_{p['id']}",
                            )
                        browse_notes = st.text_input(
                            "Special conditions (optional)",
                            placeholder="e.g. Grade A only, deliver to warehouse gate…",
                            key=f"m_browse_notes_{p['id']}",
                        )

                    if st.button("🛒 Place Order with Agreement", key=f"m_order_{p['id']}", use_container_width=True):
                        if risk["risk_level"] == "High":
                            st.warning("⚠️ High fraud risk detected — order still placed but proceed with caution.")
                        try:
                            supabase.table("orders").insert({
                                "product_id": p["id"],
                                "buyer_id": st.session_state.user.id,
                                "quantity_ordered": qty_order,
                                "total_price_birr": total_birr,
                                "status": "pending",
                                "fraud_risk_level": risk["risk_level"],
                                "fraud_probability": risk["fraud_probability"],
                                "merchant_confirmed": True,
                                "producer_confirmed": False,
                                "agreement_delivery_date": browse_delivery.isoformat(),
                                "agreement_payment_method": browse_payment,
                                "notes": browse_notes.strip() or None,
                            }).execute()
                            reduce_product_stock(p["id"], qty_order)
                            send_notification(
                                recipient_id=p["producer_id"],
                                title="📋 New Order with Agreement Received",
                                message=(
                                    f"{profile.get('full_name','A merchant')} ordered "
                                    f"{qty_order:,.1f} {p['unit']} of {p['product_name']} "
                                    f"({total_birr:,.0f} Birr) with a supply agreement. "
                                    f"Delivery: {browse_delivery.strftime('%d %b %Y')} · "
                                    f"Payment: {browse_payment}. Please Accept or Decline in Incoming Orders."
                                ),
                                notif_type="info",
                            )
                            st.success(f"✅ Order placed — {total_birr:,.0f} Birr. Producer notified.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Order failed: {e}")

    # ── TAB 2: MY ORDERS ─────────────────────────────────────
    with tab_orders:
        st.subheader("📋 My Orders")
        st.caption("Track all orders you have placed with producers.")

        try:
            my_orders = supabase.table("orders").select(
                "*, products(product_name, sector, quality_grade, unit, region, price_birr, producer_id),"
                "profiles!orders_buyer_id_fkey(full_name, phone, region)"
            ).eq("buyer_id", st.session_state.user.id) \
             .order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Could not load orders: {e}")
            my_orders = []

        if not my_orders:
            st.info("You have not placed any orders yet. Go to Browse Products to get started.")
        else:
            total_orders   = len(my_orders)
            pending_cnt    = sum(1 for o in my_orders if o.get("status") == "pending")
            confirmed_cnt  = sum(1 for o in my_orders if o.get("status") == "confirmed")
            delivered_cnt  = sum(1 for o in my_orders if o.get("status") == "delivered")
            total_spent    = sum(float(o.get("total_price_birr") or 0) for o in my_orders if o.get("status") != "cancelled")

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total Orders", total_orders)
            m2.metric("Pending", pending_cnt)
            m3.metric("Confirmed", confirmed_cnt)
            m4.metric("Delivered", delivered_cnt)
            m5.metric("Total Spent", f"{total_spent:,.0f} Birr")
            st.divider()

            status_filter = st.selectbox(
                "Filter by status",
                ["All", "pending", "confirmed", "delivered", "cancelled"],
                key="m_order_filter",
            )
            filtered = my_orders if status_filter == "All" else [
                o for o in my_orders if o.get("status") == status_filter
            ]

            STATUS_ICON = {
                "pending": "🟡", "confirmed": "🟢", "delivered": "✅", "cancelled": "❌"
            }

            for o in filtered:
                prod   = o.get("products") or {}
                status = o.get("status", "pending")
                clsf   = classify_order(o)

                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 2, 2])
                    with c1:
                        st.markdown(
                            f"**{prod.get('product_name','Unknown')}** · "
                            f"{prod.get('sector','')} · Grade **{prod.get('quality_grade','')}**"
                        )
                        st.caption(f"📍 {prod.get('region','N/A')}")
                        st.caption(f"📅 Ordered: {o.get('created_at','')[:10]}")
                        if clsf.get("awaiting_buyer"):
                            st.info("📩 Producer sent an order request — check Agreements to confirm.")
                    with c2:
                        st.metric("Qty", f"{o.get('quantity_ordered',0):,.1f} {prod.get('unit','')}")
                        st.metric("Total", f"{o.get('total_price_birr',0):,.0f} Birr")
                    with c3:
                        st.markdown(f"**Status:** {STATUS_ICON.get(status,'⚪')} {status.capitalize()}")
                        risk_lvl = o.get("fraud_risk_level", "Unknown")
                        badge = {"Low":"🟢","Medium":"🟡","High":"🔴"}.get(risk_lvl,"⚪")
                        st.caption(f"Fraud Risk: {badge} {risk_lvl}")

                        if status == "delivered" and not o.get("merchant_confirmed"):
                            if st.button(
                                "✅ Confirm Receipt",
                                key=f"m_confirm_{o['id']}",
                                use_container_width=True,
                                type="primary",
                            ):
                                try:
                                    supabase.table("orders").update({
                                        "merchant_confirmed": True
                                    }).eq("id", o["id"]).execute()
                                    producer_id = prod.get("producer_id")
                                    if producer_id:
                                        send_notification(
                                            recipient_id=producer_id,
                                            title="Delivery Confirmed",
                                            message=(
                                                f"{profile.get('full_name','Merchant')} confirmed receipt of "
                                                f"{prod.get('product_name','the product')}. "
                                                f"Order is now fully complete."
                                            ),
                                            notif_type="success",
                                            order_id=o["id"],
                                        )
                                    st.success("✅ Receipt confirmed. Producer notified.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")

                        if status == "pending":
                            if st.button(
                                "❌ Cancel Order",
                                key=f"m_cancel_{o['id']}",
                                use_container_width=True,
                            ):
                                try:
                                    supabase.table("orders").update({"status": "cancelled"}).eq("id", o["id"]).execute()
                                    producer_id = prod.get("producer_id")
                                    if producer_id:
                                        send_notification(
                                            recipient_id=producer_id,
                                            title="Order Cancelled",
                                            message=(
                                                f"{profile.get('full_name','Merchant')} cancelled their order for "
                                                f"{prod.get('product_name','a product')}."
                                            ),
                                            notif_type="warning",
                                            order_id=o["id"],
                                        )
                                    st.success("Order cancelled.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")

    # ── TAB 3: AGREEMENTS ─────────────────────────────────────
    with tab_agree:
        st.subheader("📄 Supply Agreements")
        st.caption("View and confirm agreements from producers. Download formal PDFs.")

        try:
            agree_orders = supabase.table("orders").select(
                "*, products(product_name, sector, quality_grade, unit, region, producer_id),"
                "profiles!orders_buyer_id_fkey(full_name, phone, region)"
            ).eq("buyer_id", st.session_state.user.id) \
             .in_("status", ["confirmed", "delivered"]) \
             .order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Could not load agreements: {e}")
            agree_orders = []

        # Also check for producer-initiated requests (producer_confirmed=True, merchant not yet confirmed)
        try:
            producer_requests = supabase.table("orders").select(
                "*, products(product_name, sector, quality_grade, unit, region, producer_id),"
                "profiles!orders_buyer_id_fkey(full_name, phone, region)"
            ).eq("buyer_id", st.session_state.user.id) \
             .eq("producer_confirmed", True) \
             .eq("merchant_confirmed", False) \
             .execute().data or []
        except Exception as e:
            producer_requests = []

        if producer_requests:
            st.markdown("### 📩 Pending Agreement Requests from Producers")
            st.caption("Producers have sent you order requests. Review and confirm to proceed.")
            for o in producer_requests:
                prod   = o.get("products") or {}
                status = o.get("status", "")
                with st.container(border=True):
                    st.markdown(
                        f"**{prod.get('product_name','Unknown')}** · "
                        f"{prod.get('sector','')} · Grade **{prod.get('quality_grade','')}**"
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption(f"📍 Region: {prod.get('region','N/A')}")
                        st.caption(f"📅 Date: {o.get('created_at','')[:10]}")
                        st.caption(f"💰 Total: {o.get('total_price_birr',0):,.0f} Birr")
                    with c2:
                        st.caption(f"📦 Qty: {o.get('quantity_ordered',0):,.1f} {prod.get('unit','')}")
                        pay = o.get("agreement_payment_method") or "Not set"
                        dlv = o.get("agreement_delivery_date") or "Not set"
                        st.caption(f"💳 Payment: {pay}")
                        st.caption(f"🚚 Delivery by: {dlv}")

                    # Fetch producer profile for agreement preview
                    producer_id = prod.get("producer_id")
                    prod_profile = {}
                    if producer_id:
                        try:
                            res = supabase.table("profiles").select("*").eq("id", producer_id).execute()
                            prod_profile = res.data[0] if res.data else {}
                        except Exception:
                            pass

                    render_agreement_terms_inline(
                        order_row=o,
                        product_row=prod,
                        producer_profile=prod_profile,
                        merchant_profile=profile,
                        container_key=f"agree_preview_{o['id']}",
                    )

                    ba1, ba2 = st.columns(2)
                    with ba1:
                        if st.button(
                            "✅ Accept & Confirm Agreement",
                            key=f"m_accept_{o['id']}",
                            type="primary",
                            use_container_width=True,
                        ):
                            try:
                                supabase.table("orders").update({
                                    "merchant_confirmed": True,
                                    "status": "confirmed",
                                }).eq("id", o["id"]).execute()
                                if producer_id:
                                    send_notification(
                                        recipient_id=producer_id,
                                        title="Agreement Accepted",
                                        message=(
                                            f"{profile.get('full_name','Merchant')} accepted your supply agreement "
                                            f"for {prod.get('product_name','the product')}. "
                                            f"Proceed with delivery."
                                        ),
                                        notif_type="success",
                                        order_id=o["id"],
                                    )
                                st.success("✅ Agreement confirmed. Producer notified.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                    with ba2:
                        if st.button(
                            "❌ Decline",
                            key=f"m_decline_{o['id']}",
                            use_container_width=True,
                        ):
                            try:
                                supabase.table("orders").update({"status": "cancelled"}).eq("id", o["id"]).execute()
                                if producer_id:
                                    send_notification(
                                        recipient_id=producer_id,
                                        title="Agreement Declined",
                                        message=(
                                            f"{profile.get('full_name','Merchant')} declined your supply agreement "
                                            f"for {prod.get('product_name','the product')}."
                                        ),
                                        notif_type="warning",
                                        order_id=o["id"],
                                    )
                                st.warning("Agreement declined.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")

            st.divider()

        if not agree_orders:
            st.info("No confirmed or delivered orders yet. Place orders and confirm with producers to generate agreements.")
        else:
            st.markdown(f"### 📄 Confirmed Agreements ({len(agree_orders)})")
            for o in agree_orders:
                prod   = o.get("products") or {}
                status = o.get("status", "")
                status_icon = "✅" if status == "delivered" else "🟢"
                producer_id = prod.get("producer_id")

                # Fetch producer profile for PDF
                prod_profile = {}
                if producer_id:
                    try:
                        res = supabase.table("profiles").select("*").eq("id", producer_id).execute()
                        prod_profile = res.data[0] if res.data else {}
                    except Exception:
                        pass

                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 2, 2])
                    with c1:
                        st.markdown(
                            f"**{prod.get('product_name','Unknown')}** · "
                            f"Grade **{prod.get('quality_grade','')}** · {prod.get('sector','')}"
                        )
                        st.caption(
                            f"👤 Producer: **{prod_profile.get('full_name','N/A')}** · "
                            f"📞 {prod_profile.get('phone','N/A')} · 📍 {prod_profile.get('region','N/A')}"
                        )
                        st.caption(
                            f"📅 {o.get('created_at','')[:10]}  ·  "
                            f"{status_icon} {status.capitalize()}"
                        )
                    with c2:
                        st.metric("Qty",   f"{o.get('quantity_ordered',0):,.1f} {prod.get('unit','')}")
                        st.metric("Total", f"{o.get('total_price_birr',0):,.0f} Birr")
                    with c3:
                        import datetime as _dt
                        default_delivery = _dt.date.today() + _dt.timedelta(days=14)
                        delivery_date = st.date_input(
                            "Delivery Date",
                            value=default_delivery,
                            key=f"m_agree_date_{o['id']}",
                        )
                        payment_method = st.selectbox(
                            "Payment",
                            ["Bank Transfer", "Cash on Delivery", "Mobile Money", "Letter of Credit"],
                            key=f"m_agree_pay_{o['id']}",
                        )

                    if st.button(
                        "📄 Generate & Download Agreement PDF",
                        key=f"m_gen_pdf_{o['id']}",
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            qty   = float(o.get("quantity_ordered", 0))
                            total = float(o.get("total_price_birr", 0))
                            unit_price = (total / qty) if qty else 0
                            pdf_bytes = generate_agreement_pdf(
                                producer_name=prod_profile.get("full_name", "Producer"),
                                producer_phone=prod_profile.get("phone", ""),
                                producer_region=prod_profile.get("region", ""),
                                merchant_name=profile.get("full_name", "Merchant"),
                                merchant_phone=profile.get("phone", ""),
                                merchant_region=profile.get("region", ""),
                                product_name=prod.get("product_name", ""),
                                sector=prod.get("sector", ""),
                                quality_grade=prod.get("quality_grade", ""),
                                quantity=qty,
                                unit=prod.get("unit", ""),
                                price_per_unit=unit_price,
                                total_price=total,
                                delivery_date=delivery_date.strftime("%d %B %Y"),
                                payment_method=payment_method,
                                notes="",
                                agreement_id=str(o["id"]),
                                producer_confirmed=bool(o.get("producer_confirmed")),
                                merchant_confirmed=bool(o.get("merchant_confirmed")),
                            )
                            prod_name_safe = prod.get("product_name", "product").replace(" ", "_")
                            fname = f"agreement_{prod_name_safe}_{o['id'][:8]}.pdf"
                            st.download_button(
                                label="⬇️ Click to Download PDF",
                                data=pdf_bytes,
                                file_name=fname,
                                mime="application/pdf",
                                key=f"m_dl_pdf_{o['id']}",
                                use_container_width=True,
                            )
                            st.success("Agreement PDF ready — click above to download.")
                        except Exception as e:
                            st.error(f"PDF generation failed: {e}")

    # ── TAB 4: HISTORY ───────────────────────────────────────
    with tab_history:
        st.subheader("📜 Purchase History")
        st.caption("All orders that have been delivered to you — your complete procurement record.")

        try:
            mh_orders = supabase.table("orders").select(
                "*, products(product_name, sector, quality_grade, unit, region, producer_id),"
                "profiles!orders_buyer_id_fkey(full_name, phone, region)"
            ).eq("buyer_id", st.session_state.user.id) \
             .eq("status", "delivered") \
             .order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Could not load history: {e}")
            mh_orders = []

        if not mh_orders:
            st.info("No delivered orders yet. Once producers mark your orders as delivered they will appear here.")
        else:
            # ── Summary metrics ──
            mh_total_spent = sum(float(o.get("total_price_birr") or 0) for o in mh_orders)
            mh_total_qty   = sum(float(o.get("quantity_ordered") or 0) for o in mh_orders)
            mh_products    = {(o.get("products") or {}).get("product_name","") for o in mh_orders}
            mhm1, mhm2, mhm3, mhm4 = st.columns(4)
            mhm1.metric("Total Deliveries",    len(mh_orders))
            mhm2.metric("Unique Products",      len(mh_products))
            mhm3.metric("Total Units Received", f"{mh_total_qty:,.1f}")
            mhm4.metric("Total Spent",          f"{mh_total_spent:,.0f} Birr")
            st.divider()

            # ── Filters ──
            mhf1, mhf2 = st.columns(2)
            with mhf1:
                mh_search = st.text_input("🔍 Search product or sector", key="mh_search")
            with mhf2:
                mh_sort = st.selectbox("Sort by", ["Newest first", "Oldest first", "Highest value", "Lowest value"], key="mh_sort")

            filtered_mh = mh_orders
            if mh_search:
                kw = mh_search.lower()
                filtered_mh = [
                    o for o in filtered_mh
                    if kw in (o.get("products") or {}).get("product_name", "").lower()
                    or kw in (o.get("products") or {}).get("sector", "").lower()
                ]
            if mh_sort == "Oldest first":
                filtered_mh = sorted(filtered_mh, key=lambda o: o.get("created_at", ""))
            elif mh_sort == "Highest value":
                filtered_mh = sorted(filtered_mh, key=lambda o: float(o.get("total_price_birr") or 0), reverse=True)
            elif mh_sort == "Lowest value":
                filtered_mh = sorted(filtered_mh, key=lambda o: float(o.get("total_price_birr") or 0))

            st.markdown(f"**{len(filtered_mh)} delivered order(s):**")

            for o in filtered_mh:
                prod = o.get("products") or {}
                both_confirmed = bool(o.get("producer_confirmed")) and bool(o.get("merchant_confirmed"))

                with st.container(border=True):
                    mhc1, mhc2, mhc3 = st.columns([4, 2, 2])
                    with mhc1:
                        st.markdown(
                            f"✅ **{prod.get('product_name','Unknown')}** · "
                            f"{prod.get('sector','')} · Grade **{prod.get('quality_grade','')}**"
                        )
                        st.caption(f"📍 Producer Region: {prod.get('region','N/A')}")
                        st.caption(f"📅 Ordered: {o.get('created_at','')[:10]}")
                        if o.get("agreement_delivery_date"):
                            st.caption(
                                f"🗓 Agreed Delivery: {o.get('agreement_delivery_date','')[:10]} · "
                                f"💳 {o.get('agreement_payment_method','N/A')}"
                            )
                        if o.get("notes"):
                            st.caption(f"📝 {o['notes']}")
                    with mhc2:
                        st.metric("Qty",   f"{o.get('quantity_ordered',0):,.1f} {prod.get('unit','')}")
                        st.metric("Total", f"{o.get('total_price_birr',0):,.0f} Birr")
                    with mhc3:
                        if both_confirmed:
                            st.success("✅ Fully Confirmed")
                        else:
                            st.warning("⏳ Awaiting your confirmation")
                            if st.button("✅ Confirm Receipt", key=f"mh_confirm_{o['id']}", use_container_width=True, type="primary"):
                                try:
                                    supabase.table("orders").update({"merchant_confirmed": True}).eq("id", o["id"]).execute()
                                    producer_id = prod.get("producer_id")
                                    if producer_id:
                                        send_notification(
                                            recipient_id=producer_id,
                                            title="✅ Delivery Confirmed by Merchant",
                                            message=(
                                                f"{profile.get('full_name','Merchant')} confirmed receipt of "
                                                f"{prod.get('product_name','the product')}. "
                                                f"Order is now fully complete."
                                            ),
                                            notif_type="success",
                                            order_id=o["id"],
                                        )
                                    st.success("Receipt confirmed. Producer notified.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")
                        risk_lvl = o.get("fraud_risk_level", "Unknown")
                        badge = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk_lvl, "⚪")
                        st.caption(f"Fraud Risk: {badge} {risk_lvl}")

            # ── Export to CSV ──
            st.divider()
            if st.button("📥 Export History to CSV", key="mh_export_csv"):
                rows = []
                for o in mh_orders:
                    prod = o.get("products") or {}
                    rows.append({
                        "Order ID":          str(o.get("id",""))[:8],
                        "Product":           prod.get("product_name",""),
                        "Sector":            prod.get("sector",""),
                        "Grade":             prod.get("quality_grade",""),
                        "Producer Region":   prod.get("region",""),
                        "Quantity":          o.get("quantity_ordered",""),
                        "Unit":              prod.get("unit",""),
                        "Total (Birr)":      o.get("total_price_birr",""),
                        "Payment Method":    o.get("agreement_payment_method",""),
                        "Delivery Date":     (o.get("agreement_delivery_date","") or "")[:10],
                        "Date Ordered":      (o.get("created_at","") or "")[:10],
                        "Fraud Risk":        o.get("fraud_risk_level",""),
                        "Fully Confirmed":   "Yes" if (bool(o.get("producer_confirmed")) and bool(o.get("merchant_confirmed"))) else "No",
                    })
                df_mh = pd.DataFrame(rows)
                csv_mh = df_mh.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv_mh,
                    file_name="merchant_purchase_history.csv",
                    mime="text/csv",
                    key="mh_dl_csv",
                    use_container_width=True,
                )

    # ── TAB 5: PREFERENCES ────────────────────────────────────
    with tab_pref:
        st.subheader("⚙️ Buying Preferences")
        st.caption("Set your preferences so producers can match you with the right products.")

        try:
            pref_res = supabase.table("merchant_preferences").select("*") \
                .eq("merchant_id", st.session_state.user.id).execute()
            existing_pref = pref_res.data[0] if pref_res.data else None
        except Exception as e:
            st.warning(f"Could not load preferences: {e}")
            existing_pref = None

        with st.container(border=True):
            st.markdown("**What do you buy?**")
            pc1, pc2 = st.columns(2)
            with pc1:
                pref_sectors = st.multiselect(
                    "Preferred Sectors",
                    SECTORS,
                    default=(existing_pref.get("preferred_sectors") or []) if existing_pref else [],
                    key="m_pref_sectors",
                )
                pref_grades = st.multiselect(
                    "Accepted Grades",
                    ["A", "B", "C"],
                    default=(existing_pref.get("preferred_grades") or []) if existing_pref else ["A", "B"],
                    key="m_pref_grades",
                )
                pref_regions = st.multiselect(
                    "Preferred Regions",
                    REGIONS,
                    default=(existing_pref.get("preferred_regions") or []) if existing_pref else [],
                    key="m_pref_regions",
                )
            with pc2:
                max_budget = st.number_input(
                    "Max Budget per Order (Birr)",
                    min_value=0.0,
                    value=float(existing_pref.get("max_budget_birr") or 50000) if existing_pref else 50000.0,
                    step=1000.0,
                    key="m_pref_budget",
                )
                min_qty = st.number_input(
                    "Minimum Quantity per Order",
                    min_value=0.0,
                    value=float(existing_pref.get("min_quantity") or 1) if existing_pref else 1.0,
                    step=1.0,
                    key="m_pref_min_qty",
                )
                pref_payment = st.selectbox(
                    "Preferred Payment Method",
                    ["Bank Transfer", "Cash on Delivery", "Mobile Money", "Letter of Credit"],
                    index=["Bank Transfer", "Cash on Delivery", "Mobile Money", "Letter of Credit"].index(
                        existing_pref.get("preferred_payment") or "Bank Transfer"
                    ) if existing_pref and existing_pref.get("preferred_payment") else 0,
                    key="m_pref_payment",
                )

            notes_pref = st.text_area(
                "Additional Notes (optional)",
                value=(existing_pref.get("notes") or "") if existing_pref else "",
                placeholder="e.g. Only organic produce, need weekly delivery, bulk orders preferred…",
                key="m_pref_notes",
            )

            if st.button("💾 Save Preferences", type="primary", use_container_width=True, key="m_save_pref"):
                pref_payload = {
                    "merchant_id": st.session_state.user.id,
                    "preferred_sectors": pref_sectors,
                    "preferred_grades": pref_grades,
                    "preferred_regions": pref_regions,
                    "max_budget_birr": max_budget,
                    "min_quantity": min_qty,
                    "preferred_payment": pref_payment,
                    "notes": notes_pref.strip(),
                }
                try:
                    if existing_pref:
                        supabase.table("merchant_preferences").update(pref_payload) \
                            .eq("merchant_id", st.session_state.user.id).execute()
                    else:
                        supabase.table("merchant_preferences").insert(pref_payload).execute()
                    st.success("✅ Preferences saved! Producers can now match you with relevant products.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")

        if existing_pref:
            st.divider()
            st.markdown("**Current Preferences Summary:**")
            sp1, sp2, sp3 = st.columns(3)
            with sp1:
                sectors_str = ", ".join(existing_pref.get("preferred_sectors") or []) or "Any"
                grades_str  = ", ".join(existing_pref.get("preferred_grades") or []) or "Any"
                st.caption(f"🏭 Sectors: **{sectors_str}**")
                st.caption(f"⭐ Grades: **{grades_str}**")
            with sp2:
                regions_str = ", ".join(existing_pref.get("preferred_regions") or []) or "Any"
                st.caption(f"📍 Regions: **{regions_str}**")
                st.caption(f"💳 Payment: **{existing_pref.get('preferred_payment','N/A')}**")
            with sp3:
                st.caption(f"💰 Max Budget: **{existing_pref.get('max_budget_birr',0):,.0f} Birr**")
                st.caption(f"📦 Min Qty: **{existing_pref.get('min_quantity',0):,.1f}**")

    # ── TAB 5: NOTIFICATIONS ──────────────────────────────────
    with tab_notif:
        render_notifications_tab(st.session_state.user.id)

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
