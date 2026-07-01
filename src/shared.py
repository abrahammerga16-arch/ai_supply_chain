"""
shared.py — Shared utilities for the Ethiopian AI Supply Chain Platform
Wolaita Sodo University | Department of ECE

Import this in every role page:
    from src.shared import (
        supabase, REGIONS, SECTORS, UNITS, GRADES, AGREEMENT_TERMS,
        get_profile, send_notification, get_unread_count,
        get_fraud_risk, render_fraud_badge, classify_order,
        download_pdf_link, generate_agreement_pdf,
        render_agreement_terms_inline,
        sign_up, sign_in, sign_out,
        SESSION_KEYS,
    )
"""

import io
import re as _re
import base64
import datetime

import streamlit as st

from src.db import get_supabase_client
from src.matching_engine import rank_merchants
from src.price_engine import recommend_price
from src.fraud_engine import check_fraud_risk

# ── SUPABASE CLIENT ───────────────────────────────────────────
try:
    supabase = get_supabase_client()
except ValueError as e:
    st.error(str(e))
    st.stop()

# ── CONSTANTS ─────────────────────────────────────────────────
REGIONS = ["Addis Ababa", "Oromia", "SNNPR", "Amhara", "Tigray", "Sidama", "Dire Dawa", "Harari"]
SECTORS = ["Agriculture", "Manufacturing", "Handicrafts", "Livestock", "Food Processing", "Textiles", "Services"]
UNITS   = ["quintal", "kg", "piece", "head", "unit", "meter", "service"]
GRADES  = ["A", "B", "C"]

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


# ── AUTH HELPERS ──────────────────────────────────────────────
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
        user_id = auth_res.user.id
        supabase.table("profiles").insert({
            "id": user_id, "full_name": full_name, "role": role,
            "region": region, "phone": phone
        }).execute()
        return True, "Account created! Please log in."
    except Exception as e:
        return False, f"Sign up failed: {str(e)}"

def sign_in(email, password):
    email = _sanitize_email(email)
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
    for key in SESSION_KEYS:
        st.session_state[key] = None


# ── PROFILE & NOTIFICATION HELPERS ───────────────────────────
def get_profile(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    return res.data[0] if res.data else None

def send_notification(recipient_id, title, message, notif_type="info", order_id=None):
    try:
        payload = {
            "recipient_id": str(recipient_id),
            "title":        title,
            "message":      message,
            "type":         notif_type,
            "is_read":      False,
        }
        if order_id:
            payload["order_id"] = str(order_id)
        result = supabase.table("notifications").insert(payload).execute()
        if not result.data:
            st.toast("⚠️ Notification not saved (no data returned). Check RLS policy.", icon="⚠️")
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


# ── FRAUD HELPERS ─────────────────────────────────────────────
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


# ── ORDER CLASSIFICATION ─────────────────────────────────────
def classify_order(o):
    prod_confirmed  = bool(o.get("producer_confirmed"))
    merch_confirmed = bool(o.get("merchant_confirmed"))
    is_agreement    = bool(o.get("agreement_delivery_date"))
    is_producer_request = prod_confirmed and not merch_confirmed and not is_agreement
    is_regular_order    = not is_agreement and not prod_confirmed
    return {
        "prod_confirmed":       prod_confirmed,
        "merch_confirmed":      merch_confirmed,
        "is_agreement":         is_agreement,
        "is_producer_request":  is_producer_request,
        "is_regular_order":     is_regular_order,
        "both_confirmed":       prod_confirmed and merch_confirmed,
        "awaiting_buyer":       is_producer_request or (is_agreement and prod_confirmed and not merch_confirmed),
    }


# ── PDF AGREEMENT GENERATOR ───────────────────────────────────
def generate_agreement_pdf(producer_name, producer_phone, producer_region,
                            merchant_name, merchant_phone, merchant_region,
                            product_name, sector, quality_grade,
                            quantity, unit, price_per_unit, total_price,
                            delivery_date, payment_method, notes,
                            agreement_id,
                            producer_confirmed=False,
                            merchant_confirmed=False):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "AgrTitle", parent=styles["Title"],
        fontSize=18, textColor=colors.HexColor("#1a5276"),
        spaceAfter=6, alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        "AgrSub", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#555555"),
        alignment=TA_CENTER, spaceAfter=4
    )
    section_style = ParagraphStyle(
        "AgrSection", parent=styles["Heading2"],
        fontSize=12, textColor=colors.HexColor("#1a5276"),
        spaceBefore=14, spaceAfter=6, borderPad=4,
    )
    body_style = ParagraphStyle(
        "AgrBody", parent=styles["Normal"],
        fontSize=10, leading=16, spaceAfter=4
    )
    small_style = ParagraphStyle(
        "AgrSmall", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#666666"), leading=14
    )

    story = []

    story.append(Paragraph("FEDERAL DEMOCRATIC REPUBLIC OF ETHIOPIA", subtitle_style))
    story.append(Paragraph("Ethiopian AI Supply Chain Platform", subtitle_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a5276")))
    story.append(Spacer(1, 8))
    story.append(Paragraph("COMMERCIAL SUPPLY AGREEMENT", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a5276")))
    story.append(Spacer(1, 10))

    ref_data = [
        ["Agreement Reference:", f"AGR-{agreement_id[:8].upper()}",
         "Date:", datetime.date.today().strftime("%d %B %Y")],
    ]
    ref_table = Table(ref_data, colWidths=[4*cm, 6*cm, 2.5*cm, 4.5*cm])
    ref_table.setStyle(TableStyle([
        ("FONTNAME",    (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("TEXTCOLOR",  (0,0), (0,-1), colors.HexColor("#1a5276")),
        ("TEXTCOLOR",  (2,0), (2,-1), colors.HexColor("#1a5276")),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(ref_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("1. PARTIES TO THE AGREEMENT", section_style))
    parties_data = [
        ["", "PRODUCER (Seller)", "MERCHANT (Buyer)"],
        ["Full Name",  producer_name,   merchant_name],
        ["Region",     producer_region, merchant_region],
        ["Phone",      producer_phone or "—", merchant_phone or "—"],
        ["Role",       "Producer / Seller", "Merchant / Buyer"],
    ]
    parties_table = Table(parties_data, colWidths=[3.5*cm, 8*cm, 6*cm])
    parties_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#1a5276")),
        ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",    (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#eaf2fb"), colors.white]),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("ALIGN",       (0,0), (-1,-1), "LEFT"),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("2. SUBJECT MATTER — GOODS & TERMS", section_style))
    goods_data = [
        ["Field", "Details"],
        ["Product Name",         product_name],
        ["Sector",               sector],
        ["Quality Grade",        f"Grade {quality_grade}"],
        ["Quantity",             f"{quantity:,.1f} {unit}"],
        ["Price per Unit",       f"{price_per_unit:,.2f} Birr"],
        ["Total Contract Value", f"{total_price:,.2f} Birr"],
        ["Payment Method",       payment_method],
        ["Delivery Date",        str(delivery_date)],
    ]
    goods_table = Table(goods_data, colWidths=[5*cm, 12*cm])
    goods_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#117a65")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",     (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#e8f8f5"), colors.white]),
        ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("ALIGN",        (0,0), (-1,-1), "LEFT"),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("BACKGROUND",  (0,6), (-1,6), colors.HexColor("#d5f5e3")),
        ("FONTNAME",    (0,6), (-1,6), "Helvetica-Bold"),
        ("TEXTCOLOR",   (1,6), (1,6),  colors.HexColor("#117a65")),
        ("FONTSIZE",    (1,6), (1,6),  11),
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

    story.append(Paragraph(f"{next_section + 1}. CONFIRMATION STATUS", section_style))
    p_status    = "✅ CONFIRMED" if producer_confirmed else "⏳ PENDING"
    m_status    = "✅ CONFIRMED" if merchant_confirmed else "⏳ PENDING"
    both_status = "✅ FULLY EXECUTED" if (producer_confirmed and merchant_confirmed) else "⏳ AWAITING BOTH PARTIES"
    status_data = [
        ["Party", "Status"],
        ["Producer (Seller)", p_status],
        ["Merchant (Buyer)",  m_status],
        ["Agreement Status",  both_status],
    ]
    status_table = Table(status_data, colWidths=[7*cm, 10*cm])
    status_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",     (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f2f3f4"), colors.white]),
        ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("BACKGROUND",  (0,3), (-1,3),
         colors.HexColor("#d5f5e3") if (producer_confirmed and merchant_confirmed) else colors.HexColor("#fdebd0")),
        ("FONTNAME",    (0,3), (-1,3), "Helvetica-Bold"),
    ]))
    story.append(status_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph(f"{next_section + 2}. SIGNATURES", section_style))
    story.append(Paragraph(
        "By signing below, both parties confirm they have read, understood, and agreed to all "
        "terms and conditions set forth in this agreement.", small_style
    ))
    story.append(Spacer(1, 16))

    sig_data = [
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
    ]
    sig_table = Table(sig_data, colWidths=[7.5*cm, 1*cm, 7.5*cm, 1*cm])
    sig_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,0), colors.HexColor("#1a5276")),
        ("TEXTCOLOR", (2,0), (2,0), colors.HexColor("#117a65")),
        ("TOPPADDING",(0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("BOX",       (0,0), (0,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("BOX",       (2,0), (2,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("BACKGROUND",(0,0), (0,0), colors.HexColor("#eaf2fb")),
        ("BACKGROUND",(2,0), (2,0), colors.HexColor("#e8f8f5")),
        ("LEFTPADDING",(0,0),(-1,-1), 8),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 20))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 6))

    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=7, textColor=colors.HexColor("#999999"), alignment=TA_CENTER
    )
    story.append(Paragraph(
        f"This agreement was facilitated by the Ethiopian AI Supply Chain Platform | "
        f"Wolaita Sodo University — Department of ECE | "
        f"Generated: {datetime.datetime.now().strftime('%d %B %Y, %H:%M')} | "
        f"Ref: AGR-{agreement_id[:8].upper()}",
        footer_style
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def render_agreement_terms_inline(order_row, product_row, producer_profile, merchant_profile,
                                   container_key):
    qty       = order_row.get("quantity_ordered", 0) or 0
    total     = order_row.get("total_price_birr", 0) or 0
    unit_price= (total / qty) if qty else 0
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
            f"- **Product:** {product_row.get('product_name', 'N/A')} "
            f"({product_row.get('sector', 'N/A')}, Grade {product_row.get('quality_grade', 'N/A')})\n"
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


def download_pdf_link(pdf_bytes, filename, label="📄 Download Agreement PDF"):
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    return (
        f'<a href="data:application/pdf;base64,{pdf_b64}" '
        f'download="{filename}" '
        f'style="display:inline-block;padding:10px 20px;background:#1a5276;'
        f'color:white;border-radius:6px;text-decoration:none;font-weight:bold;">'
        f'{label}</a>'
    )
