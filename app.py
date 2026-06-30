"""
AI-Powered Supply Chain System — Stage 5: Demand Forecasting
Wolaita Sodo University | Department of ECE

"""
import io
import base64
import datetime
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

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
SESSION_KEYS = [
    "user", "profile", "edit_product_id", "show_pref_form",
    "agreement_product_id", "agreement_merchant",
    "agreement_pdf", "agreement_ref", "agreement_merchant_name",
    "agreement_pending_order_id", "agreement_preview_pdf",
    "agreement_preview_ref",
]
for key in SESSION_KEYS:
    if key not in st.session_state:
        st.session_state[key] = None

try:
    supabase = get_supabase_client()
except ValueError as e:
    st.error(str(e))
    st.stop()


# ── AGREEMENT TERMS (shared by PDF + in-app preview) ──────────
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


# ── PDF AGREEMENT GENERATOR ───────────────────────────────────
def generate_agreement_pdf(producer_name, producer_phone, producer_region,
                            merchant_name, merchant_phone, merchant_region,
                            product_name, sector, quality_grade,
                            quantity, unit, price_per_unit, total_price,
                            delivery_date, payment_method, notes,
                            agreement_id,
                            producer_confirmed=False,
                            merchant_confirmed=False):
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
        spaceBefore=14, spaceAfter=6,
        borderPad=4,
    )
    body_style = ParagraphStyle(
        "AgrBody", parent=styles["Normal"],
        fontSize=10, leading=16, spaceAfter=4
    )
    small_style = ParagraphStyle(
        "AgrSmall", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#666666"), leading=14
    )
    center_style = ParagraphStyle(
        "AgrCenter", parent=styles["Normal"],
        fontSize=10, alignment=TA_CENTER, leading=16
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
        ["Full Name",    producer_name,   merchant_name],
        ["Region",       producer_region, merchant_region],
        ["Phone",        producer_phone or "—", merchant_phone or "—"],
        ["Role",         "Producer / Seller", "Merchant / Buyer"],
    ]
    parties_table = Table(parties_data, colWidths=[3.5*cm, 8*cm, 6*cm])
    parties_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#1a5276")),
        ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",    (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("BACKGROUND",  (0,1), (-1,-1), colors.HexColor("#eaf2fb")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1),
         [colors.HexColor("#eaf2fb"), colors.white]),
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
        ["Product Name",      product_name],
        ["Sector",            sector],
        ["Quality Grade",     f"Grade {quality_grade}"],
        ["Quantity",          f"{quantity:,.1f} {unit}"],
        ["Price per Unit",    f"{price_per_unit:,.2f} Birr"],
        ["Total Contract Value", f"{total_price:,.2f} Birr"],
        ["Payment Method",   payment_method],
        ["Delivery Date",    str(delivery_date)],
    ]
    goods_table = Table(goods_data, colWidths=[5*cm, 12*cm])
    goods_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#117a65")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",     (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),
         [colors.HexColor("#e8f8f5"), colors.white]),
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

    if notes and notes.strip():
        story.append(Paragraph("3. ADDITIONAL NOTES & SPECIAL CONDITIONS", section_style))
        story.append(Paragraph(notes, body_style))
        story.append(Spacer(1, 10))
        next_section = 4
    else:
        next_section = 3

    story.append(Paragraph(f"{next_section}. GENERAL TERMS AND CONDITIONS", section_style))
    for i, (heading, text) in enumerate(AGREEMENT_TERMS, 1):
        story.append(Paragraph(f"<b>{next_section}.{i}  {heading}</b>", body_style))
        story.append(Paragraph(text, small_style))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 14))

    story.append(Paragraph(f"{next_section + 1}. CONFIRMATION STATUS", section_style))
    p_status = "✅ CONFIRMED" if producer_confirmed else "⏳ PENDING"
    m_status = "✅ CONFIRMED" if merchant_confirmed else "⏳ PENDING"
    both_status = "✅ FULLY EXECUTED" if (producer_confirmed and merchant_confirmed) else "⏳ AWAITING BOTH PARTIES"
    status_data = [
        ["Party", "Status"],
        ["Producer (Seller)", p_status],
        ["Merchant (Buyer)", m_status],
        ["Agreement Status", both_status],
    ]
    status_table = Table(status_data, colWidths=[7*cm, 10*cm])
    status_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",     (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),
         [colors.HexColor("#f2f3f4"), colors.white]),
        ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("BACKGROUND",  (0,3), (-1,3), colors.HexColor("#d5f5e3") if (producer_confirmed and merchant_confirmed) else colors.HexColor("#fdebd0")),
        ("FONTNAME",    (0,3), (-1,3), "Helvetica-Bold"),
    ]))
    story.append(status_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph(f"{next_section + 2}. SIGNATURES", section_style))
    story.append(Paragraph(
        "By signing below, both parties confirm they have read, understood, and agreed to all "
        "terms and conditions set forth in this agreement.",
        small_style
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
    story.append(Paragraph(
        f"This agreement was facilitated by the Ethiopian AI Supply Chain Platform | "
        f"Wolaita Sodo University — Department of ECE | "
        f"Generated: {datetime.datetime.now().strftime('%d %B %Y, %H:%M')} | "
        f"Ref: AGR-{agreement_id[:8].upper()}",
        ParagraphStyle("Footer", parent=styles["Normal"],
                       fontSize=7, textColor=colors.HexColor("#999999"),
                       alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def render_agreement_terms_inline(order_row, product_row, producer_profile, merchant_profile,
                                   container_key):
    """
    Renders a readable, in-app (non-PDF) view of an agreement's terms so either
    party can review everything without needing to download a file.
    """
    qty   = order_row.get("quantity_ordered", 0) or 0
    total = order_row.get("total_price_birr", 0) or 0
    unit_price = (total / qty) if qty else 0
    unit  = product_row.get("unit", "")
    delivery = order_row.get("agreement_delivery_date") or "Not yet set"
    payment  = order_row.get("agreement_payment_method") or "Not yet set"
    notes    = order_row.get("notes") or ""

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


# ── HELPER FUNCTIONS ──────────────────────────────────────────
def get_profile(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    return res.data[0] if res.data else None


def send_notification(recipient_id, title, message, notif_type="info", order_id=None):
    """
    Insert a notification row for a user.
    Uses the regular supabase client — works as long as the RLS INSERT policy
    is set to WITH CHECK (true), which allows authenticated users to insert
    notifications for any recipient_id.
    """
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
        # If insert returned no data, something went wrong silently
        if not result.data:
            st.toast(f"⚠️ Notification not saved (no data returned). Check RLS policy.", icon="⚠️")
    except Exception as e:
        # Show a non-blocking toast so the main flow never breaks
        st.toast(f"⚠️ Notification failed: {e}", icon="⚠️")


def get_unread_count(user_id):
    """Return count of unread notifications for badge display. Returns 0 on any error."""
    try:
        res = supabase.table("notifications") \
            .select("id", count="exact") \
            .eq("recipient_id", user_id) \
            .eq("is_read", False).execute()
        return res.count or 0
    except Exception:
        return 0


def get_fraud_risk(sector, product, region, payment_method, quantity, price_birr):
    """Shared fraud-risk lookup used by Browse / Best Matches / Place Order tabs."""
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
    """
    Single source of truth for how an order should be interpreted, used by
    both the producer's 'Incoming Orders' tab and the buyer's 'My Orders' tab.

    Returns a dict with:
      - is_agreement: a formal producer-drafted agreement (has delivery/payment terms)
      - is_producer_request: a producer-initiated order request awaiting the
        buyer's confirmation (not yet a formal agreement)
      - is_regular_order: a normal buyer-initiated order (browse / place order)
      - both_confirmed: both parties have signed off
      - awaiting_buyer: True when the ball is in the buyer's (merchant/customer) court
    """
    prod_confirmed  = bool(o.get("producer_confirmed"))
    merch_confirmed = bool(o.get("merchant_confirmed"))
    is_agreement    = bool(o.get("agreement_delivery_date"))

    # A producer-initiated request is any order the producer pre-confirmed
    # that hasn't been accepted by the buyer yet, and isn't a fully drafted
    # agreement. This stays true regardless of the order's "status" string so
    # the buyer always sees something actionable until they respond.
    is_producer_request = prod_confirmed and not merch_confirmed and not is_agreement
    is_regular_order     = not is_agreement and not prod_confirmed

    return {
        "prod_confirmed": prod_confirmed,
        "merch_confirmed": merch_confirmed,
        "is_agreement": is_agreement,
        "is_producer_request": is_producer_request,
        "is_regular_order": is_regular_order,
        "both_confirmed": prod_confirmed and merch_confirmed,
        "awaiting_buyer": is_producer_request or (is_agreement and prod_confirmed and not merch_confirmed),
    }

import re as _re

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
        profile_data = {
            "id": user_id, "full_name": full_name, "role": role,
            "region": region, "phone": phone
        }
        supabase.table("profiles").insert(profile_data).execute()
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

def download_pdf_link(pdf_bytes, filename, label="📄 Download Agreement PDF"):
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    href = (
        f'<a href="data:application/pdf;base64,{pdf_b64}" '
        f'download="{filename}" '
        f'style="display:inline-block;padding:10px 20px;background:#1a5276;'
        f'color:white;border-radius:6px;text-decoration:none;font-weight:bold;">'
        f'{label}</a>'
    )
    return href

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
            su_name   = st.text_input("Full Name", key="su_name")
            su_email  = st.text_input("Email", key="su_email")
            su_pass   = st.text_input("Password", type="password", key="su_pass",
                                      help="Min 8 chars, letters + numbers")
            su_role   = st.selectbox("I am a...", ["producer", "merchant", "customer"], key="su_role")
            su_region = st.selectbox("Region", REGIONS, key="su_region")
            su_phone  = st.text_input("Phone Number", key="su_phone")

            if st.button("Create Account", use_container_width=True):
                if not su_name or not su_email or not su_pass or not su_phone:
                    st.warning("Please fill in all required fields.")
                else:
                    ok, msg = sign_up(su_email, su_pass, su_name, su_role, su_region, su_phone)
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


# ── MAIN ─────────────────────────────────────────────────────
if st.session_state.user is None:
    st.title("Welcome to the Ethiopian AI Supply Chain Platform")
    st.write("A unified marketplace connecting **producers**, **merchants**, and **customers** across Ethiopia.")
    st.info("Please log in or sign up using the sidebar to get started.")
    st.stop()

profile = st.session_state.profile
role    = profile["role"] if profile else None

_unread = get_unread_count(st.session_state.user.id) if st.session_state.user else 0
_notif_label = f"🔔 Notifications ({_unread})" if _unread > 0 else "🔔 Notifications"

if role == "producer":
    tabs = st.tabs(["📦 Browse", "➕ Add Product", "📋 My Listings", "📬 Incoming Orders", _notif_label, "⚙️ Profile"])
    tab_browse, tab_add, tab_listings, tab_incoming, tab_notif, tab_profile = tabs
elif role == "merchant":
    tabs = st.tabs(["📦 Browse", "🤖 Best Matches", "🛒 My Orders", "🛍️ Place Order", _notif_label])
    tab_browse, tab_matches, tab_orders, tab_place, tab_notif = tabs
else:
    tabs = st.tabs(["📦 Browse", "🤖 Best Matches", "🛒 My Orders", _notif_label, "⚙️ Profile"])
    tab_browse, tab_matches, tab_orders, tab_notif, tab_profile = tabs


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
                        _qty_max = max(1.0, float(p["quantity"]))
                        qty_to_order = st.number_input(
                            "Qty", min_value=1.0, max_value=_qty_max,
                            value=min(1.0, _qty_max), key=f"qty_{p['id']}"
                        )
                        total = qty_to_order * p["price_birr"]
                        st.caption(f"Total: **{total:,.0f} Birr**")

                        risk = get_fraud_risk(
                            sector=p["sector"], product=p["product_name"], region=p["region"],
                            payment_method="Bank Transfer", quantity=qty_to_order, price_birr=p["price_birr"],
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
# TAB: BEST MATCHES (Merchant / Customer)
# ════════════════════════════════════════════════════════════
if role in ("merchant", "customer"):
    with tab_matches:
        st.subheader("🤖 AI-Recommended Products For You")
        st.caption("Based on your region, buying preferences and past activity")

        try:
            all_products = supabase.table("products") \
                .select("*, profiles(full_name, phone, region)") \
                .eq("is_available", True).execute().data
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
                if p.get("region") == buyer_region:
                    score += 30
                if pref_sector and p.get("sector") == pref_sector:
                    score += 25
                if pref_product and pref_product in p.get("product_name", "").lower():
                    score += 30
                if pref_quality and pref_quality != "Any":
                    if pref_quality == "A or B" and p.get("quality_grade") in ("A", "B"):
                        score += 10
                    elif p.get("quality_grade") == pref_quality:
                        score += 10
                if max_budget > 0 and p.get("price_birr", 0) <= max_budget:
                    score += 5
                return score

            scored      = sorted(all_products, key=score_product, reverse=True)
            top_products = scored[:10]

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
                        st.caption(f"👤 {seller.get('full_name', 'Unknown')} · 📍 {p['region']}")
                        match_color = "🟢" if pct >= 60 else ("🟡" if pct >= 30 else "🔴")
                        st.caption(f"{match_color} Match Score: **{pct}%**")
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

        # ── AGREEMENT FLOW (Producer side) ──────────────────
        if st.session_state.agreement_product_id and st.session_state.agreement_merchant:
            m   = st.session_state.agreement_merchant
            pid = st.session_state.agreement_product_id
            try:
                prod_res = supabase.table("products").select("*").eq("id", pid).execute()
                prod     = prod_res.data[0] if prod_res.data else {}
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
                    agr_qty      = st.number_input("Quantity",
                                                   min_value=0.1,
                                                   max_value=agr_qty_max,
                                                   value=min(10.0, agr_qty_max),
                                                   step=1.0, key="agr_qty")
                    agr_price    = st.number_input("Agreed Price per Unit (Birr)",
                                                   min_value=1.0,
                                                   value=float(prod.get("price_birr", 100)),
                                                   step=10.0, key="agr_price")
                    agr_delivery = st.date_input("Delivery Date", key="agr_delivery")
                    agr_payment  = st.selectbox("Payment Method",
                                                ["Cash", "Bank Transfer", "Mobile Money", "Credit"],
                                                key="agr_payment")
                    agr_notes    = st.text_area("Additional Notes (optional)", key="agr_notes")
                    agr_total    = agr_qty * agr_price
                    st.info(f"💰 Total: **{agr_total:,.0f} Birr**")

                if st.button("👁️ Preview Agreement PDF", use_container_width=True, key="preview_agr_btn"):
                    preview_pdf = generate_agreement_pdf(
                        producer_name    = profile.get("full_name", ""),
                        producer_phone   = profile.get("phone", ""),
                        producer_region  = profile.get("region", ""),
                        merchant_name    = m["name"],
                        merchant_phone   = m.get("phone", ""),
                        merchant_region  = m.get("region", ""),
                        product_name     = prod.get("product_name", ""),
                        sector           = prod.get("sector", ""),
                        quality_grade    = prod.get("quality_grade", ""),
                        quantity         = agr_qty,
                        unit             = prod.get("unit", ""),
                        price_per_unit   = agr_price,
                        total_price      = agr_total,
                        delivery_date    = agr_delivery,
                        payment_method   = agr_payment,
                        notes            = agr_notes,
                        agreement_id     = "PREVIEW00",
                        producer_confirmed=False,
                        merchant_confirmed=False,
                    )
                    st.markdown(download_pdf_link(preview_pdf, "Agreement-PREVIEW.pdf", "📄 Download Preview PDF"), unsafe_allow_html=True)
                    st.caption("⚠️ This is a preview only. Confirm below to create the official agreement.")

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
                                    f"Payment: {agr_payment}. "
                                    f"Delivery: {agr_delivery}. "
                                    f"{agr_notes}"
                                ),
                            }).execute()
                            order_id = order_res.data[0]["id"] if order_res.data else "N/A"

                            # ── Notify the merchant ──
                            send_notification(
                                recipient_id = m["id"],
                                title        = "🤝 New Agreement From Producer",
                                message      = f"**{profile.get('full_name', 'A producer')}** has sent you a " f"supply agreement for **{prod.get('product_name', 'a product')}** — " f"{agr_qty:,.1f} {prod.get('unit', '')} @ {agr_price:,.0f} Birr/unit " f"(Total: {agr_total:,.0f} Birr). " f"Go to 🛒 My Orders to accept or reject.",
                                notif_type   = "info",
                                order_id     = str(order_id),
                            )

                            pdf_bytes = generate_agreement_pdf(
                                producer_name    = profile.get("full_name", ""),
                                producer_phone   = profile.get("phone", ""),
                                producer_region  = profile.get("region", ""),
                                merchant_name    = m["name"],
                                merchant_phone   = m.get("phone", ""),
                                merchant_region  = m.get("region", ""),
                                product_name     = prod.get("product_name", ""),
                                sector           = prod.get("sector", ""),
                                quality_grade    = prod.get("quality_grade", ""),
                                quantity         = agr_qty,
                                unit             = prod.get("unit", ""),
                                price_per_unit   = agr_price,
                                total_price      = agr_total,
                                delivery_date    = agr_delivery,
                                payment_method   = agr_payment,
                                notes            = agr_notes,
                                agreement_id     = str(order_id),
                                producer_confirmed=True,
                                merchant_confirmed=False,
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

        # ── SHOW GENERATED AGREEMENT DOWNLOAD ──
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

        # ── PRODUCTS LIST ──
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
                                                    f"{r.get('region', 'N/A')} · "
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
                                                            recipient_id = r["id"],
                                                            title        = "📩 New Order Request From Producer",
                                                            message      = f"**{profile.get('full_name', 'A producer')}** wants to " f"sell you **{p['product_name']}** — " f"{req_qty:,.1f} {p['unit']} @ {p['price_birr']:,.0f} Birr/unit " f"(Total: {req_total:,.0f} Birr). " f"Go to 🛒 My Orders to confirm or decline. " f"No agreement is generated until you confirm.",
                                                            notif_type   = "info",
                                                            order_id     = str(new_order_id) if new_order_id else None,
                                                        )
                                                        st.success(f"📩 Order request sent to {r['name']}. They must confirm before an agreement can be made.")
                                                        st.rerun()
                                                    except Exception as e:
                                                        st.error(f"Failed: {e}")
                            except Exception as e:
                                st.error(f"Matching failed: {e}")

                    try:
                        fc = forecast_demand(p["product_name"], p["region"], weeks_ahead=4)
                    except Exception:
                        fc = None

                    if fc and "error" not in fc:
                        trend_icon = {"up": "🟢 ↑ Rising", "down": "🔴 ↓ Falling", "stable": "🟡 → Stable"}[fc["trend"]]
                        st.caption(f"📈 Demand Forecast | {trend_icon} | R²={fc['r2']:.2f} RMSE=±{fc['rmse']:,.0f}")
                        all_labels  = [f"W-{7-i}" for i in range(8)] + [f"+{w}w" for w in fc["weeks"]]
                        hist_series = fc["historical"] + [None] * 4
                        fc_series   = [None] * 7 + [fc["historical"][-1]] + fc["forecast"]
                        chart_data  = pd.DataFrame({"Actual": hist_series, "Forecast": fc_series}, index=all_labels)
                        st.line_chart(chart_data, color=["#4A90D9", "#F5A623"], height=180)
                    else:
                        st.caption("📈 Demand forecast unavailable.")


# ════════════════════════════════════════════════════════════
# TAB: INCOMING ORDERS (Producer only)
# ════════════════════════════════════════════════════════════
if role == "producer":
    with tab_incoming:
        st.subheader("📬 Incoming Orders from Merchants & Customers")
        st.caption("All orders placed on your products — confirm, deliver, or cancel them here")

        try:
            my_prod_ids_res = supabase.table("products").select("id") \
                .eq("producer_id", st.session_state.user.id).execute()
            my_prod_ids = [p["id"] for p in (my_prod_ids_res.data or [])]
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
                m2.metric("🟡 Pending", pending_count)
                m3.metric("🔵 Confirmed", confirmed_count)
                m4.metric("🟢 Delivered", delivered_count)
                m5.metric("💰 Confirmed Revenue", f"{total_rev:,.0f} Birr")
                st.divider()

                inc_status_filter = st.selectbox(
                    "Filter by Status",
                    ["All", "pending", "confirmed", "delivered", "cancelled"],
                    key="inc_status_filter"
                )
                filtered_incoming = incoming if inc_status_filter == "All" else \
                    [o for o in incoming if o["status"] == inc_status_filter]

                if not filtered_incoming:
                    st.info("No orders match this filter.")
                else:
                    st.markdown(f"**{len(filtered_incoming)} order(s):**")

                    for o in filtered_incoming:
                        prod        = o.get("products") or {}
                        buyer       = o.get("profiles") or {}
                        pname       = prod.get("product_name", "Unknown")
                        unit        = prod.get("unit", "")
                        buyer_name  = buyer.get("full_name", "Unknown buyer")
                        buyer_phone = buyer.get("phone", "N/A")
                        buyer_region= buyer.get("region", "N/A")

                        cls = classify_order(o)
                        is_agreement     = cls["is_agreement"]
                        prod_confirmed   = cls["prod_confirmed"]
                        merch_confirmed  = cls["merch_confirmed"]
                        both_confirmed   = cls["both_confirmed"]
                        is_producer_request = cls["is_producer_request"]

                        status_badge = {
                            "pending":   "🟡 Pending",
                            "confirmed": "🔵 Confirmed",
                            "delivered": "🟢 Delivered",
                            "cancelled": "🔴 Cancelled",
                        }.get(o["status"], o["status"])

                        if o["status"] == "pending":
                            st.markdown(
                                "<div style='border-left:4px solid #f39c12;"
                                "padding-left:8px;margin-bottom:4px;'>"
                                "🆕 <b>New Order Received</b></div>",
                                unsafe_allow_html=True
                            )

                        with st.container(border=True):
                            col_a, col_b, col_c = st.columns([3, 2, 2])

                            with col_a:
                                st.markdown(
                                    f"**{pname}** · {prod.get('sector','N/A')} · "
                                    f"Grade **{prod.get('quality_grade','N/A')}**"
                                )
                                st.caption(
                                    f"👤 Buyer: **{buyer_name}** · "
                                    f"📞 {buyer_phone} · 📍 {buyer_region}"
                                )
                                st.caption(
                                    f"Qty: **{o['quantity_ordered']} {unit}** · "
                                    f"Region: {prod.get('region','N/A')}"
                                )
                                if is_agreement:
                                    st.caption(
                                        f"📑 **Agreement Order** · "
                                        f"Delivery: {o.get('agreement_delivery_date','N/A')} · "
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
                                        dt = datetime.datetime.fromisoformat(
                                            created.replace("Z", "+00:00")
                                        )
                                        st.caption(f"🕐 {dt.strftime('%d %b %Y, %H:%M')}")
                                    except Exception:
                                        st.caption(f"🕐 {created[:16]}")
                                if is_agreement:
                                    if both_confirmed:
                                        st.success("🤝 Both Confirmed")
                                    elif prod_confirmed and not merch_confirmed:
                                        st.warning("⏳ Awaiting Merchant")
                                    elif not prod_confirmed:
                                        st.warning("⏳ Awaiting Your Action")
                                elif is_producer_request:
                                    st.info("⏳ Awaiting merchant confirmation")

                            with col_c:
                                ready_for_agreement = (
                                    is_producer_request and merch_confirmed
                                    and o["status"] == "confirmed"
                                )

                                if is_producer_request and not merch_confirmed:
                                    pass  # status already shown in col_b; nothing actionable yet

                                elif ready_for_agreement:
                                    if st.button("📝 Create Agreement", key=f"mk_agr_{o['id']}", use_container_width=True):
                                        st.session_state.agreement_pending_order_id = o["id"]
                                        st.rerun()

                                elif o["status"] == "pending" and cls["is_regular_order"]:
                                    if st.button(
                                        "✅ Confirm Order",
                                        key=f"inc_confirm_{o['id']}",
                                        use_container_width=True
                                    ):
                                        try:
                                            supabase.table("orders").update({
                                                "status": "confirmed",
                                                "producer_confirmed": True,
                                            }).eq("id", o["id"]).execute()

                                            prod_id     = o.get("product_id") or (prod.get("id") if prod else None)
                                            qty_ordered = float(o["quantity_ordered"])
                                            qty_msg     = ""
                                            if prod_id:
                                                prod_row = supabase.table("products").select("quantity").eq("id", prod_id).execute()
                                                if prod_row.data:
                                                    current_qty = float(prod_row.data[0]["quantity"])
                                                    new_qty     = max(0.0, current_qty - qty_ordered)
                                                    supabase.table("products").update({
                                                        "quantity":     new_qty,
                                                        "is_available": new_qty > 0,
                                                    }).eq("id", prod_id).execute()
                                                    qty_msg = (
                                                        f"Stock: {current_qty:,.1f} → {new_qty:,.1f} {unit}"
                                                        + (" · Sold out" if new_qty == 0 else "")
                                                    )

                                            # ── Notify buyer ──
                                            send_notification(
                                                recipient_id = o["buyer_id"],
                                                title        = "✅ Order Confirmed",
                                                message      = f"Your order for **{pname}** " f"({qty_ordered:,.1f} {unit}) " f"worth **{o['total_price_birr']:,.0f} Birr** " f"has been confirmed by the producer. " f"Prepare for delivery.",
                                                notif_type   = "success",
                                                order_id     = o["id"],
                                            )
                                            # ── Notify producer (self-receipt) ──
                                            send_notification(
                                                recipient_id = st.session_state.user.id,
                                                title        = "✅ You Confirmed an Order",
                                                message      = f"You confirmed **{buyer_name}**'s order for " f"**{pname}** — {qty_ordered:,.1f} {unit} · " f"{o['total_price_birr']:,.0f} Birr. " + (qty_msg or ""),
                                                notif_type   = "success",
                                                order_id     = o["id"],
                                            )

                                            st.success(
                                                f"✅ **Order Confirmed!**\n\n"
                                                f"👤 Buyer: **{buyer_name}**\n\n"
                                                f"📦 Product: **{pname}**\n\n"
                                                f"🔢 Qty: **{qty_ordered:,.1f} {unit}**\n\n"
                                                f"💰 Value: **{o['total_price_birr']:,.0f} Birr**\n\n"
                                                + (f"📉 {qty_msg}\n\n" if qty_msg else "")
                                                + f"🔔 Notification sent to **{buyer_name}**"
                                            )
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Failed: {e}")

                                    if st.button(
                                        "❌ Cancel Order",
                                        key=f"inc_cancel_{o['id']}",
                                        use_container_width=True
                                    ):
                                        try:
                                            supabase.table("orders").update({
                                                "status": "cancelled",
                                            }).eq("id", o["id"]).execute()

                                            send_notification(
                                                recipient_id = o["buyer_id"],
                                                title        = "🚫 Order Cancelled",
                                                message      = f"Your order for **{pname}** " f"({o['quantity_ordered']:,.1f} {unit} · " f"{o['total_price_birr']:,.0f} Birr) " f"was cancelled by the producer. " f"Please browse for alternative products.",
                                                notif_type   = "warning",
                                                order_id     = o["id"],
                                            )
                                            st.warning(
                                                f"🚫 **Order Cancelled**\n\n"
                                                f"👤 Buyer: **{buyer_name}** · "
                                                f"📦 **{pname}** · "
                                                f"💰 {o['total_price_birr']:,.0f} Birr\n\n"
                                                f"🔔 Buyer notified."
                                            )
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Failed: {e}")

                                elif o["status"] == "confirmed" and cls["is_regular_order"]:
                                    if st.button(
                                        "🚚 Mark as Delivered",
                                        key=f"inc_deliver_{o['id']}",
                                        use_container_width=True
                                    ):
                                        try:
                                            supabase.table("orders").update({
                                                "status": "delivered",
                                            }).eq("id", o["id"]).execute()

                                            send_notification(
                                                recipient_id = o["buyer_id"],
                                                title        = "🚚 Order Delivered!",
                                                message      = f"Your order for **{pname}** " f"({o['quantity_ordered']:,.1f} {unit} · " f"{o['total_price_birr']:,.0f} Birr) " f"has been marked as delivered by the producer. " f"Please confirm receipt.",
                                                notif_type   = "success",
                                                order_id     = o["id"],
                                            )
                                            send_notification(
                                                recipient_id = st.session_state.user.id,
                                                title        = "🚚 Delivery Recorded",
                                                message      = f"You marked **{pname}** " f"({o['quantity_ordered']:,.1f} {unit}) " f"as delivered to **{buyer_name}** — " f"{o['total_price_birr']:,.0f} Birr.",
                                                notif_type   = "success",
                                                order_id     = o["id"],
                                            )
                                            st.success(
                                                f"🚚 **Delivered!**\n\n"
                                                f"👤 Buyer: **{buyer_name}**\n\n"
                                                f"📦 **{pname}** — "
                                                f"{o['quantity_ordered']:,.1f} {unit}\n\n"
                                                f"💰 **{o['total_price_birr']:,.0f} Birr**\n\n"
                                                f"🔔 Delivery notification sent to **{buyer_name}**"
                                            )
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Failed: {e}")

                                if is_agreement:
                                    try:
                                        buyer_profile_res = supabase.table("profiles") \
                                            .select("*").eq("id", o["buyer_id"]).execute()
                                        buyer_profile = buyer_profile_res.data[0] \
                                            if buyer_profile_res.data else {}
                                    except Exception:
                                        buyer_profile = {}

                                    render_agreement_terms_inline(
                                        o, prod, profile, buyer_profile, container_key=f"inc_{o['id']}"
                                    )

                                    if st.button(
                                        "📄 Download Agreement PDF",
                                        key=f"inc_pdf_{o['id']}",
                                        use_container_width=True
                                    ):
                                        delivery_str = datetime.date.today()
                                        payment_str  = "Bank Transfer"
                                        if o.get("agreement_delivery_date"):
                                            try:
                                                delivery_str = datetime.date.fromisoformat(
                                                    o["agreement_delivery_date"]
                                                )
                                            except Exception:
                                                pass
                                        if o.get("agreement_payment_method"):
                                            payment_str = o["agreement_payment_method"]

                                        pdf_bytes = generate_agreement_pdf(
                                            producer_name      = profile.get("full_name", ""),
                                            producer_phone     = profile.get("phone", ""),
                                            producer_region    = profile.get("region", ""),
                                            merchant_name      = buyer_profile.get("full_name", buyer_name),
                                            merchant_phone     = buyer_profile.get("phone", ""),
                                            merchant_region    = buyer_profile.get("region", ""),
                                            product_name       = pname,
                                            sector             = prod.get("sector", ""),
                                            quality_grade      = prod.get("quality_grade", ""),
                                            quantity           = o["quantity_ordered"],
                                            unit               = unit,
                                            price_per_unit     = (
                                                o["total_price_birr"] / o["quantity_ordered"]
                                                if o["quantity_ordered"] else 0
                                            ),
                                            total_price        = o["total_price_birr"],
                                            delivery_date      = delivery_str,
                                            payment_method     = payment_str,
                                            notes              = o.get("notes", ""),
                                            agreement_id       = str(o["id"]),
                                            producer_confirmed = prod_confirmed,
                                            merchant_confirmed = merch_confirmed,
                                        )
                                        st.session_state.agreement_preview_pdf = pdf_bytes
                                        st.session_state.agreement_preview_ref = str(o["id"])
                                        st.rerun()

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
                    prod = o.get("products") or {}
                    buyer = o.get("profiles") or {}
                    st.divider()
                    st.markdown(f"### 📝 Build Agreement for confirmed order — {buyer.get('full_name','Merchant')}")
                    with st.container(border=True):
                        agr_delivery = st.date_input("Delivery Date", key=f"final_delivery_{oid}")
                        agr_payment  = st.selectbox("Payment Method", ["Cash", "Bank Transfer", "Mobile Money", "Credit"], key=f"final_payment_{oid}")
                        agr_notes    = st.text_area("Additional Notes (optional)", key=f"final_notes_{oid}")

                        if st.button("👁️ Preview Agreement PDF", key=f"final_preview_{oid}", use_container_width=True):
                            preview_pdf = generate_agreement_pdf(
                                producer_name=profile.get("full_name", ""), producer_phone=profile.get("phone", ""),
                                producer_region=profile.get("region", ""), merchant_name=buyer.get("full_name", ""),
                                merchant_phone=buyer.get("phone", ""), merchant_region=buyer.get("region", ""),
                                product_name=prod.get("product_name", ""), sector=prod.get("sector", ""),
                                quality_grade=prod.get("quality_grade", ""), quantity=o["quantity_ordered"],
                                unit=prod.get("unit", ""), price_per_unit=o["total_price_birr"] / o["quantity_ordered"] if o["quantity_ordered"] else 0,
                                total_price=o["total_price_birr"], delivery_date=agr_delivery, payment_method=agr_payment,
                                notes=agr_notes, agreement_id="PREVIEW00", producer_confirmed=True, merchant_confirmed=True,
                            )
                            st.markdown(download_pdf_link(preview_pdf, "Agreement-PREVIEW.pdf", "📄 Download Preview PDF"), unsafe_allow_html=True)
                            st.caption("⚠️ Preview only. Click Finalize below to save the official agreement.")

                        col_fin, col_cancel = st.columns(2)
                        with col_fin:
                            if st.button("✅ Finalize Agreement", key=f"final_send_{oid}", use_container_width=True):
                                try:
                                    supabase.table("orders").update({
                                        "agreement_delivery_date":  str(agr_delivery),
                                        "agreement_payment_method": agr_payment,
                                        "notes": agr_notes,
                                    }).eq("id", oid).execute()
                                    pdf_bytes = generate_agreement_pdf(
                                        producer_name=profile.get("full_name", ""), producer_phone=profile.get("phone", ""),
                                        producer_region=profile.get("region", ""), merchant_name=buyer.get("full_name", ""),
                                        merchant_phone=buyer.get("phone", ""), merchant_region=buyer.get("region", ""),
                                        product_name=prod.get("product_name", ""), sector=prod.get("sector", ""),
                                        quality_grade=prod.get("quality_grade", ""), quantity=o["quantity_ordered"],
                                        unit=prod.get("unit", ""), price_per_unit=o["total_price_birr"] / o["quantity_ordered"] if o["quantity_ordered"] else 0,
                                        total_price=o["total_price_birr"], delivery_date=agr_delivery, payment_method=agr_payment,
                                        notes=agr_notes, agreement_id=str(oid), producer_confirmed=True, merchant_confirmed=True,
                                    )
                                    send_notification(
                                        recipient_id=o["buyer_id"], title="🤝 Agreement Document Ready",
                                        message=f"The formal agreement for **{prod.get('product_name','')}** is ready. View it in 🛒 My Orders.",
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
                    ),
                    unsafe_allow_html=True
                )
                if st.button("✖ Close Preview", key="close_inc_preview_pdf"):
                    st.session_state.agreement_preview_pdf = None
                    st.session_state.agreement_preview_ref = None
                    st.rerun()


# ════════════════════════════════════════════════════════════
# TAB: MY ORDERS (Merchant / Customer)
# ════════════════════════════════════════════════════════════
if role in ("merchant", "customer"):
    with tab_orders:
        st.subheader("🛒 My Orders")

        if role == "merchant":
            has_prefs = profile.get("preferred_product") or profile.get("preferred_sector")
            if has_prefs:
                st.info(
                    f"🤖 AI Matching active — **{profile.get('preferred_product', 'N/A')}** "
                    f"in **{profile.get('preferred_sector', 'N/A')}** · "
                    f"Budget: **{profile.get('max_budget_birr', 0):,.0f} Birr** · "
                    f"Quality: **{profile.get('preferred_quality', 'Any')}** — "
                    f"update preferences in 🛍️ Place Order"
                )
            else:
                st.warning("⚠️ No buying preferences set yet — go to 🛍️ Place Order to enable AI matching.")
            st.divider()

        try:
            orders = supabase.table("orders") \
                .select("*, products(product_name, unit, region, sector, price_birr, quality_grade, producer_id, profiles(full_name, phone, region))") \
                .eq("buyer_id", st.session_state.user.id) \
                .order("created_at", desc=True).execute().data
            if orders is None:
                orders = []
        except Exception as e:
            st.error(f"Could not load orders: {e}")
            orders = []

        if not orders:
            st.info("You haven't placed any orders yet. Browse products to get started.")
            with st.expander("🔍 Debug: Check if orders exist in DB"):
                try:
                    raw = supabase.table("orders").select("id, buyer_id, status, created_at") \
                        .eq("buyer_id", st.session_state.user.id).execute()
                    st.write(f"Raw query returned {len(raw.data)} row(s):", raw.data)
                    if not raw.data:
                        st.error(
                            "No orders found for your user ID. Two possible causes:\n"
                            "1. You haven't placed any orders yet.\n"
                            "2. Supabase RLS is blocking the query. Run this SQL in Supabase SQL Editor:\n\n"
                            "```sql\n"
                            "ALTER TABLE orders ENABLE ROW LEVEL SECURITY;\n"
                            "CREATE POLICY \"buyer_select\" ON orders FOR SELECT\n"
                            "  USING (buyer_id = auth.uid());\n"
                            "CREATE POLICY \"buyer_insert\" ON orders FOR INSERT\n"
                            "  WITH CHECK (buyer_id = auth.uid());\n"
                            "CREATE POLICY \"buyer_update\" ON orders FOR UPDATE\n"
                            "  USING (buyer_id = auth.uid());\n"
                            "```"
                        )
                except Exception as dbg_e:
                    st.error(f"Debug query failed: {dbg_e}")
        else:
            total_spent = sum(o["total_price_birr"] for o in orders)
            pending     = sum(1 for o in orders if o["status"] == "pending")
            confirmed   = sum(1 for o in orders if o["status"] == "confirmed")
            delivered   = sum(1 for o in orders if o["status"] == "delivered")

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total Orders", len(orders))
            m2.metric("Total Spent", f"{total_spent:,.0f} Birr")
            m3.metric("Pending", pending)
            m4.metric("Confirmed", confirmed)
            m5.metric("Delivered", delivered)
            st.divider()

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                status_filter = st.selectbox(
                    "Filter by Status",
                    ["All", "pending", "confirmed", "delivered", "cancelled"],
                    key="order_status_filter"
                )
            with col_f2:
                all_sectors = sorted(set(
                    (o.get("products") or {}).get("sector", "Unknown")
                    for o in orders
                    if (o.get("products") or {}).get("sector")
                ))
                sector_filter = st.selectbox(
                    "Filter by Sector",
                    ["All"] + all_sectors,
                    key="order_sector_filter"
                )

            filtered_orders = orders
            if status_filter != "All":
                filtered_orders = [o for o in filtered_orders if o["status"] == status_filter]
            if sector_filter != "All":
                filtered_orders = [o for o in filtered_orders if (o.get("products") or {}).get("sector") == sector_filter]

            if not filtered_orders:
                st.info("No orders match your filter.")
            else:
                st.markdown(f"**Showing {len(filtered_orders)} order(s):**")

                for o in filtered_orders:
                    prod        = o.get("products") or {}
                    pname       = prod.get("product_name", "Unknown product")
                    unit        = prod.get("unit", "")
                    seller_info = prod.get("profiles") or {}
                    seller_name = seller_info.get("full_name", "Unknown seller")
                    seller_phone= seller_info.get("phone", "N/A")

                    status_badge = {
                        "pending":   "🟡 Pending",
                        "confirmed": "🔵 Confirmed",
                        "delivered": "🟢 Delivered",
                        "cancelled": "🔴 Cancelled",
                    }.get(o["status"], o["status"])

                    cls = classify_order(o)
                    prod_confirmed   = cls["prod_confirmed"]
                    merch_confirmed  = cls["merch_confirmed"]
                    is_agreement     = cls["is_agreement"]
                    both_confirmed   = cls["both_confirmed"]
                    is_regular_order = cls["is_regular_order"]
                    is_producer_request = cls["is_producer_request"]

                    with st.container(border=True):
                        col_a, col_b, col_c = st.columns([3, 2, 2])
                        with col_a:
                            st.markdown(f"**{pname}**")
                            st.caption(f"Seller: {seller_name} · 📞 {seller_phone}")
                            st.caption(f"📍 Region: {prod.get('region', 'N/A')} · Sector: {prod.get('sector', 'N/A')}")
                            st.caption(f"Qty: {o['quantity_ordered']} {unit} · Grade: {prod.get('quality_grade', 'N/A')}")
                            if o.get("notes"):
                                st.caption(f"📝 {o['notes']}")
                        with col_b:
                            st.metric("Total", f"{o['total_price_birr']:,.0f} Birr")
                            st.caption(status_badge)
                            risk_lvl = o.get("fraud_risk_level", "Unknown")
                            if risk_lvl and risk_lvl != "Unknown":
                                rb = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk_lvl, "⚪")
                                st.caption(f"{rb} Fraud Risk: **{risk_lvl}**")
                        with col_c:
                            # Producer-initiated order request, awaiting this buyer's response.
                            # Always shown regardless of the order's raw status string so the
                            # confirm/decline action never silently disappears.
                            if is_producer_request:
                                st.warning("📩 Order request from producer")
                                if st.button("✅ Confirm Order", key=f"confirm_req_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update({
                                            "merchant_confirmed": True,
                                            "status": "confirmed",
                                        }).eq("id", o["id"]).execute()
                                        prod_producer_id = prod.get("producer_id")
                                        if prod_producer_id:
                                            send_notification(
                                                recipient_id = prod_producer_id,
                                                title        = "✅ Order Request Confirmed",
                                                message      = f"**{profile.get('full_name','The merchant')}** confirmed your " f"order request for **{pname}** — {o['quantity_ordered']:,.1f} {unit} · " f"{o['total_price_birr']:,.0f} Birr. " f"You can now create the formal agreement in 📬 Incoming Orders.",
                                                notif_type   = "success",
                                                order_id     = o["id"],
                                            )
                                        st.success("✅ Confirmed. The producer can now generate the agreement.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed: {e}")
                                if st.button("❌ Decline", key=f"decline_req_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update({"status": "cancelled"}).eq("id", o["id"]).execute()
                                        prod_producer_id = prod.get("producer_id")
                                        if prod_producer_id:
                                            send_notification(
                                                recipient_id = prod_producer_id,
                                                title        = "❌ Order Request Declined",
                                                message      = f"**{profile.get('full_name','The merchant')}** declined your order request for **{pname}**.",
                                                notif_type   = "warning",
                                                order_id     = o["id"],
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
                                                "merchant_confirmed": True,
                                                "status": "confirmed",
                                            }).eq("id", o["id"]).execute()
                                            # Notify producer that merchant accepted
                                            prod_producer_id = prod.get("producer_id")
                                            if prod_producer_id:
                                                send_notification(
                                                    recipient_id = prod_producer_id,
                                                    title        = "🤝 Agreement Accepted!",
                                                    message      = f"**{profile.get('full_name', 'The merchant')}** " f"has accepted your supply agreement for " f"**{pname}** — " f"{o['quantity_ordered']:,.1f} {unit} · " f"{o['total_price_birr']:,.0f} Birr. " f"The agreement is now fully executed.",
                                                    notif_type   = "success",
                                                    order_id     = o["id"],
                                                )
                                            st.success("✅ Agreement accepted!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Failed: {e}")
                                    if st.button("❌ Reject Agreement", key=f"reject_agr_{o['id']}", use_container_width=True):
                                        try:
                                            supabase.table("orders").update({
                                                "merchant_confirmed": False,
                                                "status": "cancelled",
                                            }).eq("id", o["id"]).execute()
                                            # Notify producer that merchant rejected
                                            prod_producer_id = prod.get("producer_id")
                                            if prod_producer_id:
                                                send_notification(
                                                    recipient_id = prod_producer_id,
                                                    title        = "❌ Agreement Rejected",
                                                    message      = f"**{profile.get('full_name', 'The merchant')}** " f"has rejected your supply agreement for " f"**{pname}**. " f"You may reach out to discuss revised terms.",
                                                    notif_type   = "warning",
                                                    order_id     = o["id"],
                                                )
                                            st.error("Agreement rejected.")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Failed: {e}")

                            elif is_regular_order and o["status"] == "pending":
                                if st.button("❌ Cancel Order", key=f"cancel_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update(
                                            {"status": "cancelled"}
                                        ).eq("id", o["id"]).execute()
                                        st.success("Order cancelled.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Cancel failed: {e}")

                        # ── Inline, readable agreement terms + PDF download (for any agreement order) ──
                        if is_agreement:
                            try:
                                prod_profile_res = supabase.table("profiles").select("*").eq("id", prod.get("producer_id", "")).execute()
                                prod_profile = prod_profile_res.data[0] if prod_profile_res.data else {}
                            except Exception:
                                prod_profile = {}

                            render_agreement_terms_inline(
                                o, prod, prod_profile, profile, container_key=f"my_{o['id']}"
                            )

                            if st.button("📄 Download Agreement PDF", key=f"view_agr_pdf_{o['id']}", use_container_width=True):
                                notes_text   = o.get("notes", "")
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
                                    producer_name      = prod_profile.get("full_name", "Producer"),
                                    producer_phone     = prod_profile.get("phone", ""),
                                    producer_region    = prod_profile.get("region", ""),
                                    merchant_name      = profile.get("full_name", ""),
                                    merchant_phone     = profile.get("phone", ""),
                                    merchant_region    = profile.get("region", ""),
                                    product_name       = pname,
                                    sector             = prod.get("sector", ""),
                                    quality_grade      = prod.get("quality_grade", ""),
                                    quantity           = o["quantity_ordered"],
                                    unit               = unit,
                                    price_per_unit     = o["total_price_birr"] / o["quantity_ordered"] if o["quantity_ordered"] else 0,
                                    total_price        = o["total_price_birr"],
                                    delivery_date      = delivery_str,
                                    payment_method     = payment_str,
                                    notes              = notes_text,
                                    agreement_id       = str(o["id"]),
                                    producer_confirmed = prod_confirmed,
                                    merchant_confirmed = merch_confirmed,
                                )
                                st.session_state.agreement_preview_pdf = pdf_bytes
                                st.session_state.agreement_preview_ref = str(o["id"])
                                st.rerun()

                        can_update = o["status"] not in ("cancelled", "delivered") and (
                            is_regular_order or both_confirmed
                        )
                        expander_label = "✏️ Update Order" if is_regular_order else "✏️ Update Agreement Order"
                        if can_update:
                            with st.expander(expander_label):
                                upd_col1, upd_col2 = st.columns(2)
                                with upd_col1:
                                    new_qty = st.number_input(
                                        "New Quantity",
                                        min_value=0.1,
                                        value=float(o["quantity_ordered"]),
                                        step=1.0,
                                        key=f"upd_qty_{o['id']}"
                                    )
                                    new_status = st.selectbox(
                                        "Status",
                                        ["pending", "confirmed", "delivered", "cancelled"],
                                        index=["pending", "confirmed", "delivered", "cancelled"].index(o["status"]),
                                        key=f"upd_status_{o['id']}"
                                    )
                                with upd_col2:
                                    unit_price = o["total_price_birr"] / o["quantity_ordered"] if o["quantity_ordered"] else 0
                                    new_total  = new_qty * unit_price
                                    st.metric("New Total", f"{new_total:,.0f} Birr")
                                    new_notes = st.text_area(
                                        "Notes",
                                        value=o.get("notes") or "",
                                        key=f"upd_notes_{o['id']}"
                                    )
                                if st.button("💾 Save Changes", key=f"upd_save_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update({
                                            "quantity_ordered": new_qty,
                                            "total_price_birr": new_total,
                                            "notes":            new_notes,
                                            "status":           new_status,
                                        }).eq("id", o["id"]).execute()
                                        st.success("✅ Order updated!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Update failed: {e}")

        if st.session_state.get("agreement_preview_pdf"):
            st.divider()
            st.subheader("📄 Agreement Document")
            ref = st.session_state.get("agreement_preview_ref", "agreement")
            st.markdown(
                download_pdf_link(
                    st.session_state.agreement_preview_pdf,
                    f"Agreement-{ref[:8].upper()}.pdf",
                    f"📥 Download Agreement PDF (Ref: {ref[:8].upper()})"
                ),
                unsafe_allow_html=True
            )
            if st.button("✖ Close Preview", key="close_preview_pdf"):
                st.session_state.agreement_preview_pdf = None
                st.session_state.agreement_preview_ref = None
                st.rerun()


# ════════════════════════════════════════════════════════════
# TAB: PLACE ORDER (Merchant only)
# ════════════════════════════════════════════════════════════
if role == "merchant":
    with tab_place:
        st.subheader("🛍️ Place Order")
        st.caption(f"Logged in as **{profile['full_name']}** · {profile['region']}")
        st.divider()

        st.markdown("### 🏪 Buying Preferences")
        st.caption("Set your preferences to power AI product matching in Best Matches tab")

        pf_col1, pf_col2 = st.columns(2)
        with pf_col1:
            pref_sector   = st.selectbox("Preferred Sector", SECTORS,
                index=SECTORS.index(profile.get("preferred_sector")) if profile.get("preferred_sector") in SECTORS else 0,
                key="edit_pref_sector")
            pref_product  = st.text_input("Preferred Product", value=profile.get("preferred_product") or "", key="edit_pref_product")
            pref_budget   = st.number_input("Max Budget (Birr)", min_value=0.0, step=1000.0,
                value=float(profile.get("max_budget_birr") or 0), key="edit_pref_budget")
        with pf_col2:
            pref_quality  = st.selectbox("Preferred Quality", ["A", "B", "A or B", "Any"],
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

        st.divider()

        st.markdown("### 🛒 Place a New Order")
        st.caption("Search and order any available product directly")

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
            st.info("No products found. Try adjusting your filters.")
        else:
            st.markdown(f"**{len(po_products)} product(s) available:**")
            for p in po_products:
                seller = p.get("profiles") or {}
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    with c1:
                        st.markdown(f"**{p['product_name']}** · {p['sector']} · Grade **{p['quality_grade']}**")
                        st.caption(p.get("description") or "No description")
                        st.caption(f"👤 {seller.get('full_name', 'Unknown')} · 📍 {p['region']} · 📞 {seller.get('phone', 'N/A')}")
                    with c2:
                        st.metric("Price / Unit", f"{p['price_birr']:,.0f} Birr")
                        st.caption(f"Available: {p['quantity']} {p['unit']}")
                    with c3:
                        _max_qty = max(1.0, float(p["quantity"]))
                        po_qty = st.number_input(
                            "Quantity", min_value=1.0, max_value=_max_qty,
                            value=min(1.0, _max_qty), step=1.0,
                            key=f"po_qty_{p['id']}"
                        )
                        po_total = po_qty * p["price_birr"]
                        st.caption(f"Total: **{po_total:,.0f} Birr**")

                        risk = get_fraud_risk(
                            sector=p["sector"], product=p["product_name"], region=p["region"],
                            payment_method=pref_payment, quantity=po_qty, price_birr=p["price_birr"],
                        )
                        render_fraud_badge(risk)

                        if st.button("🛒 Place Order", key=f"po_order_{p['id']}", use_container_width=True):
                            if risk.get("risk_level") == "High":
                                st.warning("⚠️ High fraud risk — proceed with caution.")
                            try:
                                supabase.table("orders").insert({
                                    "product_id":        p["id"],
                                    "buyer_id":          st.session_state.user.id,
                                    "quantity_ordered":  po_qty,
                                    "total_price_birr":  po_total,
                                    "status":            "pending",
                                    "fraud_risk_level":  risk.get("risk_level", "Unknown"),
                                    "fraud_probability": risk.get("fraud_probability", 0.0),
                                }).execute()
                                st.success(f"✅ Order placed for **{p['product_name']}** — {po_total:,.0f} Birr! Check My Orders tab.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Order failed: {e}")


# ════════════════════════════════════════════════════════════
# TAB: NOTIFICATIONS (All roles)
# ════════════════════════════════════════════════════════════
with tab_notif:
    uid = st.session_state.user.id

    hcol1, hcol2 = st.columns([3, 1])
    with hcol1:
        st.subheader("🔔 Notifications")
        st.caption("Order confirmations, deliveries, and updates appear here")
    with hcol2:
        if st.button("✅ Mark All Read", use_container_width=True, key="mark_all_read"):
            try:
                supabase.table("notifications") \
                    .update({"is_read": True}) \
                    .eq("recipient_id", uid) \
                    .eq("is_read", False).execute()
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    try:
        notifs = supabase.table("notifications") \
            .select("*") \
            .eq("recipient_id", uid) \
            .order("created_at", desc=True) \
            .limit(50).execute().data or []
    except Exception as e:
        st.error(f"Could not load notifications: {e}")
        notifs = []

    if not notifs:
        st.info("No notifications yet. Notifications appear here when orders are confirmed, delivered, or cancelled.")
    else:
        unread_notifs = [n for n in notifs if not n.get("is_read")]
        read_notifs   = [n for n in notifs if n.get("is_read")]

        if unread_notifs:
            st.markdown(f"### 🔴 Unread ({len(unread_notifs)})")
            for n in unread_notifs:
                _icon = {
                    "success": "✅",
                    "warning": "🚫",
                    "error":   "❌",
                    "info":    "ℹ️",
                }.get(n.get("type", "info"), "🔔")

                _bg = {
                    "success": "#e8f8f5",
                    "warning": "#fef9e7",
                    "error":   "#fdedec",
                    "info":    "#eaf2fb",
                }.get(n.get("type", "info"), "#eaf2fb")

                _border = {
                    "success": "117a65",
                    "warning": "f39c12",
                    "error":   "e74c3c",
                    "info":    "1a5276",
                }.get(n.get("type", "info"), "1a5276")

                created_str = ""
                if n.get("created_at"):
                    try:
                        created_str = datetime.datetime.fromisoformat(
                            n["created_at"].replace("Z", "+00:00")
                        ).strftime("%d %b %Y, %H:%M")
                    except Exception:
                        pass

                st.markdown(
                    f"<div style='background:{_bg};border-radius:8px;"
                    f"padding:14px 16px;margin-bottom:10px;"
                    f"border-left:4px solid #{_border};'>"
                    f"<b>{_icon} {n['title']}</b><br>"
                    f"{n['message']}<br>"
                    f"<small style='color:#888;'>{created_str}</small></div>",
                    unsafe_allow_html=True
                )
                ncol1, ncol2 = st.columns([1, 5])
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
                    _icon = {
                        "success": "✅",
                        "warning": "🚫",
                        "error":   "❌",
                        "info":    "ℹ️",
                    }.get(n.get("type", "info"), "🔔")
                    created = ""
                    if n.get("created_at"):
                        try:
                            created = datetime.datetime.fromisoformat(
                                n["created_at"].replace("Z", "+00:00")
                            ).strftime("%d %b %Y, %H:%M")
                        except Exception:
                            pass
                    st.markdown(
                        f"<div style='background:#f8f9fa;border-radius:6px;"
                        f"padding:10px 14px;margin-bottom:6px;opacity:0.75;'>"
                        f"<b>{_icon} {n['title']}</b><br>"
                        f"<span style='color:#555;'>{n['message']}</span><br>"
                        f"<small style='color:#aaa;'>{created}</small></div>",
                        unsafe_allow_html=True
                    )

        if notifs:
            st.divider()
            if st.button("🗑️ Clear All Notifications", key="clear_all_notifs", use_container_width=False):
                try:
                    supabase.table("notifications") \
                        .delete() \
                        .eq("recipient_id", uid).execute()
                    st.success("All notifications cleared.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")


# ════════════════════════════════════════════════════════════
# TAB: PROFILE (Producer & Customer only)
# ════════════════════════════════════════════════════════════
if role == "producer":
    with tab_profile:
        st.subheader("⚙️ My Profile")
        st.caption(f"**{profile['full_name']}** · Producer · {profile['region']}")
        st.divider()
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

elif role == "customer":
    with tab_profile:
        st.subheader("⚙️ My Profile")
        st.caption(f"**{profile['full_name']}** · Customer · {profile['region']}")
        st.divider()
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
