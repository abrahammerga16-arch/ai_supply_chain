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

# ── SESSION STATE — ALL KEYS INITIALIZED FIRST ───────────────
_DEFAULTS = {
    "user":                    None,
    "profile":                 None,
    "edit_product_id":         None,
    "show_pref_form":          False,
    "agreement_product_id":    None,
    "agreement_merchant":      None,
    "agreement_pdf":           None,
    "agreement_ref":           None,
    "agreement_merchant_name": None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── SUPABASE ─────────────────────────────────────────────────
try:
    supabase = get_supabase_client()
except ValueError as e:
    st.error(str(e))
    st.stop()


# ── PDF AGREEMENT GENERATOR ───────────────────────────────────
def generate_agreement_pdf(
    producer_name, producer_phone, producer_region,
    merchant_name, merchant_phone, merchant_region,
    product_name, sector, quality_grade,
    quantity, unit, price_per_unit, total_price,
    delivery_date, payment_method, notes, agreement_id
):
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

    # Header
    story.append(Paragraph("FEDERAL DEMOCRATIC REPUBLIC OF ETHIOPIA", subtitle_style))
    story.append(Paragraph("Ethiopian AI Supply Chain Platform", subtitle_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a5276")))
    story.append(Spacer(1, 8))
    story.append(Paragraph("COMMERCIAL SUPPLY AGREEMENT", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a5276")))
    story.append(Spacer(1, 10))

    ref_id = str(agreement_id)[:8].upper()
    ref_data = [[
        "Agreement Reference:", f"AGR-{ref_id}",
        "Date:", datetime.date.today().strftime("%d %B %Y")
    ]]
    ref_table = Table(ref_data, colWidths=[4*cm, 6*cm, 2.5*cm, 4.5*cm])
    ref_table.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",     (0, 0), (0, -1),  colors.HexColor("#1a5276")),
        ("TEXTCOLOR",     (2, 0), (2, -1),  colors.HexColor("#1a5276")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(ref_table)
    story.append(Spacer(1, 14))

    # Parties
    story.append(Paragraph("1. PARTIES TO THE AGREEMENT", section_style))
    parties_data = [
        ["",          "PRODUCER (Seller)", "MERCHANT (Buyer)"],
        ["Full Name", producer_name,       merchant_name],
        ["Region",    producer_region,     merchant_region],
        ["Phone",     producer_phone or "—", merchant_phone or "—"],
        ["Role",      "Producer / Seller", "Merchant / Buyer"],
    ]
    parties_table = Table(parties_data, colWidths=[3.5*cm, 8*cm, 6*cm])
    parties_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#1a5276")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1),
         [colors.HexColor("#eaf2fb"), colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#aaaaaa")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 14))

    # Goods
    story.append(Paragraph("2. SUBJECT MATTER — GOODS & TERMS", section_style))
    goods_data = [
        ["Field",                "Details"],
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
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#117a65")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1),
         [colors.HexColor("#e8f8f5"), colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#aaaaaa")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("BACKGROUND",    (0, 6), (-1, 6),  colors.HexColor("#d5f5e3")),
        ("FONTNAME",      (0, 6), (-1, 6),  "Helvetica-Bold"),
        ("TEXTCOLOR",     (1, 6), (1, 6),   colors.HexColor("#117a65")),
        ("FONTSIZE",      (1, 6), (1, 6),   11),
    ]))
    story.append(goods_table)
    story.append(Spacer(1, 14))

    ns = 3
    if notes and notes.strip():
        story.append(Paragraph("3. ADDITIONAL NOTES & SPECIAL CONDITIONS", section_style))
        story.append(Paragraph(notes, body_style))
        story.append(Spacer(1, 10))
        ns = 4

    story.append(Paragraph(f"{ns}. GENERAL TERMS AND CONDITIONS", section_style))
    terms = [
        ("Quality Assurance",
         "The Producer guarantees goods delivered shall conform to the agreed quality grade. "
         "Any non-conforming goods shall be replaced at the Producer's cost within 7 business days."),
        ("Payment Terms",
         f"Payment shall be made via {payment_method} upon delivery and confirmation. "
         "Late payment beyond 14 days shall attract a penalty of 2% per month on the outstanding amount."),
        ("Delivery & Transfer of Risk",
         f"The Producer shall deliver goods by {delivery_date}. Risk and title transfer upon acceptance. "
         "Delivery delays exceeding 7 days without notice entitle the Merchant to cancel this agreement."),
        ("Dispute Resolution",
         "Disputes shall first be resolved through good-faith negotiation. Failing that within 30 days, "
         "disputes are referred to the Ethiopian Commercial Dispute Resolution Centre."),
        ("Force Majeure",
         "Neither party is liable for delays caused by circumstances beyond reasonable control, "
         "provided written notice is given within 5 days of such event."),
        ("Governing Law",
         "This agreement is governed by the Commercial Code of Ethiopia (Proclamation No. 1243/2021) "
         "and applicable regional trade regulations."),
    ]
    for i, (heading, text) in enumerate(terms, 1):
        story.append(Paragraph(f"<b>{ns}.{i}  {heading}</b>", body_style))
        story.append(Paragraph(text, small_style))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 14))
    story.append(Paragraph(f"{ns+1}. SIGNATURES", section_style))
    story.append(Paragraph(
        "By signing below, both parties confirm they have read and agreed to all terms herein.",
        small_style
    ))
    story.append(Spacer(1, 16))

    sig_data = [
        ["PRODUCER (Seller)", "",  "MERCHANT (Buyer)", ""],
        [f"Name: {producer_name}", "", f"Name: {merchant_name}", ""],
        ["", "", "", ""],
        ["Signature: ____________________", "", "Signature: ____________________", ""],
        ["", "", "", ""],
        ["Date: ____________________", "", "Date: ____________________", ""],
        [f"Phone: {producer_phone or '_______________'}", "",
         f"Phone: {merchant_phone or '_______________'}", ""],
        [f"Region: {producer_region}", "", f"Region: {merchant_region}", ""],
    ]
    sig_table = Table(sig_data, colWidths=[7.5*cm, 1*cm, 7.5*cm, 1*cm])
    sig_table.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",     (0, 0), (0, 0),   colors.HexColor("#1a5276")),
        ("TEXTCOLOR",     (2, 0), (2, 0),   colors.HexColor("#117a65")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX",           (0, 0), (0, -1),  0.5, colors.HexColor("#aaaaaa")),
        ("BOX",           (2, 0), (2, -1),  0.5, colors.HexColor("#aaaaaa")),
        ("BACKGROUND",    (0, 0), (0, 0),   colors.HexColor("#eaf2fb")),
        ("BACKGROUND",    (2, 0), (2, 0),   colors.HexColor("#e8f8f5")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 20))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated by the Ethiopian AI Supply Chain Platform | Wolaita Sodo University — Dept. of ECE | "
        f"{datetime.datetime.now().strftime('%d %B %Y, %H:%M')} | Ref: AGR-{ref_id}",
        ParagraphStyle("Footer", parent=styles["Normal"],
                       fontSize=7, textColor=colors.HexColor("#999999"),
                       alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ── HELPERS ───────────────────────────────────────────────────
def get_profile(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    return res.data[0] if res.data else None

def sign_up(email, password, full_name, role, region, phone):
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
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if auth_res.user:
            st.session_state["user"]    = auth_res.user
            st.session_state["profile"] = get_profile(auth_res.user.id)
            return True, "Logged in successfully."
        return False, "Invalid credentials."
    except Exception as e:
        return False, f"Login failed: {e}"

def sign_out():
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v

REGIONS = ["Addis Ababa", "Oromia", "SNNPR", "Amhara", "Tigray", "Sidama", "Dire Dawa", "Harari"]
SECTORS = ["Agriculture", "Manufacturing", "Handicrafts", "Livestock", "Food Processing", "Textiles", "Services"]
UNITS   = ["quintal", "kg", "piece", "head", "unit", "meter", "service"]
GRADES  = ["A", "B", "C"]


# ════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("🌾 AI Supply Chain")
    st.caption("Ethiopian Multi-Sector Commerce")
    st.divider()

    if st.session_state["user"] is None:
        tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

        with tab_login:
            login_email = st.text_input("Email", key="login_email")
            login_pass  = st.text_input("Password", type="password", key="login_pass")
            if st.button("Log In", use_container_width=True):
                if not login_email.strip() or not login_pass.strip():
                    st.warning("Please enter your email and password.")
                else:
                    ok, msg = sign_in(login_email.strip(), login_pass)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        with tab_signup:
            su_name   = st.text_input("Full Name",    key="su_name")
            su_email  = st.text_input("Email",        key="su_email")
            su_pass   = st.text_input("Password", type="password", key="su_pass",
                                      help="Min 8 chars, must include letters and numbers")
            su_role   = st.selectbox("I am a...", ["producer", "merchant", "customer"], key="su_role")
            su_region = st.selectbox("Region", REGIONS, key="su_region")
            su_phone  = st.text_input("Phone Number", key="su_phone")

            if st.button("Create Account", use_container_width=True):
                missing = [f for f, v in [
                    ("Full Name", su_name), ("Email", su_email),
                    ("Password", su_pass),  ("Phone", su_phone)
                ] if not v.strip()]
                if missing:
                    st.warning(f"Please fill in: {', '.join(missing)}")
                else:
                    ok, msg = sign_up(
                        su_email.strip(), su_pass,
                        su_name.strip(), su_role, su_region, su_phone.strip()
                    )
                    st.success(msg) if ok else st.error(msg)
    else:
        _p = st.session_state["profile"]
        st.success(f"Welcome, {_p['full_name'] if _p else 'User'}")
        st.caption(f"Role: {_p['role'].capitalize() if _p else 'N/A'}")
        st.caption(f"Region: {_p['region'] if _p else 'N/A'}")
        if st.button("Log Out", use_container_width=True):
            sign_out()
            st.rerun()


# ════════════════════════════════════════════════════════════
# GATE: stop here if not logged in
# ════════════════════════════════════════════════════════════
if st.session_state["user"] is None:
    st.title("Welcome to the Ethiopian AI Supply Chain Platform")
    st.write("A unified marketplace connecting **producers**, **merchants**, and **customers** across Ethiopia.")
    st.info("Please log in or sign up using the sidebar to get started.")
    st.stop()

# From here on, user is guaranteed to be logged in
profile = st.session_state["profile"]
if profile is None:
    st.error("Profile not found. Please log out and log in again.")
    st.stop()

role = profile.get("role")


# ════════════════════════════════════════════════════════════
# BUILD TABS
# ════════════════════════════════════════════════════════════
if role == "producer":
    tab_browse, tab_add, tab_listings, tab_profile = st.tabs(
        ["📦 Browse", "➕ Add Product", "📋 My Listings", "⚙️ Profile"]
    )
elif role == "merchant":
    tab_browse, tab_matches, tab_orders, tab_profile = st.tabs(
        ["📦 Browse", "🤖 Best Matches", "🛒 My Orders", "⚙️ Profile"]
    )
else:  # customer
    tab_browse, tab_matches, tab_orders, tab_profile = st.tabs(
        ["📦 Browse", "🤖 Best Matches", "🛒 My Orders", "⚙️ Profile"]
    )


# ════════════════════════════════════════════════════════════
# TAB: BROWSE
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

    q = supabase.table("products").select("*, profiles(full_name, region)").eq("is_available", True)
    if filter_sector != "All":
        q = q.eq("sector", filter_sector)
    if filter_region != "All":
        q = q.eq("region", filter_region)

    try:
        products = q.execute().data or []
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
                    seller = p.get("profiles") or {}
                    st.caption(f"👤 {seller.get('full_name', 'Unknown')} · 📍 {p['region']}")
                with c2:
                    st.metric("Price", f"{p['price_birr']:,.0f} Birr")
                    st.caption(f"Available: {p['quantity']} {p['unit']}")
                with c3:
                    if role in ("merchant", "customer"):
                        qty_to_order = st.number_input(
                            "Qty", min_value=1.0, max_value=float(p["quantity"]),
                            value=1.0, key=f"qty_{p['id']}"
                        )
                        total = qty_to_order * p["price_birr"]
                        st.caption(f"Total: **{total:,.0f} Birr**")
                        try:
                            risk = check_fraud_risk(
                                sector=p["sector"], product=p["product_name"],
                                region=p["region"], payment_method="Bank Transfer",
                                quantity=qty_to_order, agreed_price_birr=p["price_birr"],
                                market_price_birr=p["price_birr"],
                            )
                        except Exception:
                            risk = {"risk_level": "Unknown", "is_fraud": 0, "fraud_probability": 0.0}
                        rb = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk["risk_level"], "⚪")
                        st.caption(f"{rb} Fraud Risk: **{risk['risk_level']}**")
                        if st.button("🛒 Place Order", key=f"order_{p['id']}"):
                            if risk["risk_level"] == "High":
                                st.warning("⚠️ High fraud risk — proceed with caution.")
                            try:
                                supabase.table("orders").insert({
                                    "product_id":        p["id"],
                                    "buyer_id":          st.session_state["user"].id,
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
                    else:
                        st.caption("📍 " + p["region"])


# ════════════════════════════════════════════════════════════
# TAB: BEST MATCHES (Merchant / Customer)
# ════════════════════════════════════════════════════════════
if role in ("merchant", "customer"):
    with tab_matches:
        st.subheader("🤖 AI-Recommended Products For You")
        st.caption("Ranked by your region, preferences, and buying history")

        try:
            all_products = supabase.table("products") \
                .select("*, profiles(full_name, phone, region)") \
                .eq("is_available", True).execute().data or []
        except Exception as e:
            st.error(f"Could not load products: {e}")
            all_products = []

        if not all_products:
            st.info("No products available right now.")
        else:
            buyer_region = profile.get("region", "")
            pref_sector  = profile.get("preferred_sector", "")
            pref_product = (profile.get("preferred_product") or "").lower()
            pref_quality = profile.get("preferred_quality", "Any")
            max_budget   = float(profile.get("max_budget_birr") or 0)

            def score_product(p):
                s = 0.0
                if p.get("region") == buyer_region:                                       s += 30
                if pref_sector and p.get("sector") == pref_sector:                        s += 25
                if pref_product and pref_product in p.get("product_name", "").lower():    s += 30
                if pref_quality and pref_quality != "Any":
                    if pref_quality == "A or B" and p.get("quality_grade") in ("A", "B"): s += 10
                    elif p.get("quality_grade") == pref_quality:                           s += 10
                if max_budget > 0 and p.get("price_birr", 0) <= max_budget:               s += 5
                return s

            top_products = sorted(all_products, key=score_product, reverse=True)[:10]
            st.markdown(f"**Top {len(top_products)} matches for you:**")

            for p in top_products:
                pct    = min(int(score_product(p)), 100)
                seller = p.get("profiles") or {}
                mc     = "🟢" if pct >= 60 else ("🟡" if pct >= 30 else "🔴")

                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    with c1:
                        st.markdown(f"**{p['product_name']}** · {p['sector']} · Grade **{p['quality_grade']}**")
                        st.caption(p.get("description") or "No description")
                        st.caption(f"👤 {seller.get('full_name', 'Unknown')} · 📍 {p['region']}")
                        st.caption(f"{mc} Match Score: **{pct}%**")
                    with c2:
                        st.metric("Price", f"{p['price_birr']:,.0f} Birr")
                        st.caption(f"Available: {p['quantity']} {p['unit']}")
                    with c3:
                        qty = st.number_input(
                            "Qty", min_value=1.0, max_value=float(p["quantity"]),
                            value=1.0, key=f"match_qty_{p['id']}"
                        )
                        total = qty * p["price_birr"]
                        st.caption(f"Total: **{total:,.0f} Birr**")
                        if st.button("🛒 Order Now", key=f"match_order_{p['id']}"):
                            try:
                                risk = check_fraud_risk(
                                    sector=p["sector"], product=p["product_name"],
                                    region=p["region"], payment_method="Bank Transfer",
                                    quantity=qty, agreed_price_birr=p["price_birr"],
                                    market_price_birr=p["price_birr"],
                                )
                            except Exception:
                                risk = {"risk_level": "Unknown", "is_fraud": 0, "fraud_probability": 0.0}
                            try:
                                supabase.table("orders").insert({
                                    "product_id":        p["id"],
                                    "buyer_id":          st.session_state["user"].id,
                                    "quantity_ordered":  qty,
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
                st.info(
                    f"💰 AI Suggested Price: **{rec['recommended_price']:,.0f} Birr** "
                    f"(range: {rec['min_price']:,.0f} – {rec['max_price']:,.0f} Birr)"
                )
            except Exception:
                pass

        with st.form("add_product_form"):
            p_qty   = st.number_input("Quantity", min_value=0.1, step=1.0)
            p_unit  = st.selectbox("Unit", UNITS)
            p_price = st.number_input("Price per Unit (Birr)", min_value=1.0, step=10.0)
            p_desc  = st.text_area("Description (optional)")

            if st.form_submit_button("✅ Submit Listing", use_container_width=True):
                if not p_name or p_qty <= 0 or p_price <= 0:
                    st.warning("Fill in product name, quantity, and price.")
                else:
                    try:
                        supabase.table("products").insert({
                            "producer_id":   st.session_state["user"].id,
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

        # Incoming orders
        try:
            my_prod_ids = [
                p["id"] for p in
                supabase.table("products").select("id")
                .eq("producer_id", st.session_state["user"].id).execute().data
            ]
        except Exception:
            my_prod_ids = []

        if my_prod_ids:
            try:
                incoming = [
                    o for o in
                    supabase.table("orders")
                    .select("*, products(id, product_name, unit, price_birr, quantity), profiles(full_name, phone, region)")
                    .eq("status", "pending").execute().data
                    if o["product_id"] in my_prod_ids
                ]
            except Exception:
                incoming = []

            if incoming:
                st.markdown("### 📬 Incoming Orders")
                for o in incoming:
                    prod  = o.get("products") or {}
                    buyer = o.get("profiles") or {}
                    with st.container(border=True):
                        st.markdown(f"🛒 **Order for {prod.get('product_name', 'Unknown')}**")
                        ci, ca = st.columns([3, 2])
                        with ci:
                            st.caption(f"👤 **{buyer.get('full_name','?')}** · 📍 {buyer.get('region','?')}")
                            st.caption(f"📞 {buyer.get('phone','N/A')}")
                            st.caption(
                                f"Qty: {o['quantity_ordered']} {prod.get('unit','')} · "
                                f"Total: **{o['total_price_birr']:,.0f} Birr**"
                            )
                            rb = {"Low":"🟢","Medium":"🟡","High":"🔴"}.get(o.get("fraud_risk_level"),"⚪")
                            st.caption(f"{rb} Fraud Risk: **{o.get('fraud_risk_level','N/A')}**")
                        with ca:
                            a1, a2 = st.columns(2)
                            with a1:
                                if st.button("✅ Accept", key=f"acc_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update({"status": "confirmed"}).eq("id", o["id"]).execute()
                                        new_qty = float(prod.get("quantity", 0)) - float(o["quantity_ordered"])
                                        if new_qty <= 0:
                                            supabase.table("products").update({"quantity": 0, "is_available": False}).eq("id", o["product_id"]).execute()
                                        else:
                                            supabase.table("products").update({"quantity": new_qty}).eq("id", o["product_id"]).execute()
                                        st.success(f"Accepted! Contact {buyer.get('full_name','buyer')} at {buyer.get('phone','N/A')}.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed: {e}")
                            with a2:
                                if st.button("❌ Reject", key=f"rej_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("orders").update({"status": "cancelled"}).eq("id", o["id"]).execute()
                                        st.info("Order rejected.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed: {e}")
                st.divider()

        # Agreement panel
        if st.session_state["agreement_product_id"] and st.session_state["agreement_merchant"]:
            m   = st.session_state["agreement_merchant"]
            pid = st.session_state["agreement_product_id"]
            try:
                prod = supabase.table("products").select("*").eq("id", pid).execute().data[0]
            except Exception:
                prod = {}

            st.markdown(f"### 🤝 Agreement with **{m['name']}**")
            with st.container(border=True):
                cc, ct = st.columns(2)
                with cc:
                    st.markdown("#### 📞 Merchant Contact")
                    st.markdown(f"**Name:** {m['name']}")
                    st.markdown(f"**Region:** {m.get('region','N/A')}")
                    st.markdown(f"**Phone:** {m.get('phone') or 'Not provided'}")
                    st.markdown(f"**Preferred Product:** {m.get('preferred_product') or 'N/A'}")
                    st.markdown(f"**Payment Method:** {m.get('payment_method') or 'N/A'}")
                    st.markdown(f"**Max Budget:** {m.get('max_budget_birr', 0):,.0f} Birr")
                with ct:
                    st.markdown("#### 📝 Agreement Terms")
                    agr_qty      = st.number_input("Quantity",
                                    min_value=0.1,
                                    max_value=float(prod.get("quantity", 1000)),
                                    value=min(10.0, float(prod.get("quantity", 10))),
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

                cs, cc2 = st.columns(2)
                with cs:
                    if st.button("✅ Confirm & Generate PDF", use_container_width=True, key="send_agreement"):
                        try:
                            order_res = supabase.table("orders").insert({
                                "product_id":        pid,
                                "buyer_id":          m["id"],
                                "quantity_ordered":  agr_qty,
                                "total_price_birr":  agr_total,
                                "status":            "confirmed",
                                "fraud_risk_level":  "Low",
                                "fraud_probability": 0.05,
                                "notes": (
                                    f"Agreement. Payment: {agr_payment}. "
                                    f"Delivery: {agr_delivery}. {agr_notes}"
                                ),
                            }).execute()
                            order_id = order_res.data[0]["id"] if order_res.data else "N/A"

                            new_qty = float(prod.get("quantity", 0)) - agr_qty
                            if new_qty <= 0:
                                supabase.table("products").update({"quantity": 0, "is_available": False}).eq("id", pid).execute()
                            else:
                                supabase.table("products").update({"quantity": new_qty}).eq("id", pid).execute()

                            pdf_bytes = generate_agreement_pdf(
                                producer_name   = profile.get("full_name", ""),
                                producer_phone  = profile.get("phone", ""),
                                producer_region = profile.get("region", ""),
                                merchant_name   = m["name"],
                                merchant_phone  = m.get("phone", ""),
                                merchant_region = m.get("region", ""),
                                product_name    = prod.get("product_name", ""),
                                sector          = prod.get("sector", ""),
                                quality_grade   = prod.get("quality_grade", ""),
                                quantity        = agr_qty,
                                unit            = prod.get("unit", ""),
                                price_per_unit  = agr_price,
                                total_price     = agr_total,
                                delivery_date   = agr_delivery,
                                payment_method  = agr_payment,
                                notes           = agr_notes,
                                agreement_id    = str(order_id),
                            )
                            st.session_state["agreement_pdf"]           = pdf_bytes
                            st.session_state["agreement_ref"]           = str(order_id)
                            st.session_state["agreement_merchant_name"] = m["name"]
                            st.session_state["agreement_product_id"]    = None
                            st.session_state["agreement_merchant"]      = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                with cc2:
                    if st.button("✖ Cancel", use_container_width=True, key="cancel_agreement"):
                        st.session_state["agreement_product_id"] = None
                        st.session_state["agreement_merchant"]   = None
                        st.rerun()
            st.markdown("---")

        # PDF download banner
        if st.session_state["agreement_pdf"] is not None:
            mname = st.session_state["agreement_merchant_name"] or ""
            ref   = st.session_state["agreement_ref"] or "agreement"
            st.success(f"✅ Agreement confirmed with **{mname}**! Download the formal document below.")
            pdf_b64 = base64.b64encode(st.session_state["agreement_pdf"]).decode()
            href = (
                f'<a href="data:application/pdf;base64,{pdf_b64}" '
                f'download="Agreement-{str(ref)[:8].upper()}.pdf" '
                f'style="display:inline-block;padding:10px 22px;background:#1a5276;'
                f'color:white;border-radius:6px;text-decoration:none;font-weight:bold;">'
                f'📄 Download Formal Agreement PDF</a>'
            )
            st.markdown(href, unsafe_allow_html=True)
            if st.button("✖ Dismiss", key="dismiss_pdf"):
                st.session_state["agreement_pdf"] = None
                st.session_state["agreement_ref"] = None
                st.rerun()
            st.divider()

        # Product list
        try:
            my_products = supabase.table("products").select("*") \
                .eq("producer_id", st.session_state["user"].id) \
                .order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Could not load listings: {e}")
            my_products = []

        if not my_products:
            st.info("No listings yet. Go to ➕ Add Product.")
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

                    ct, ce, cd = st.columns(3)
                    with ct:
                        lbl = "⏸ Deactivate" if p["is_available"] else "▶ Activate"
                        if st.button(lbl, key=f"toggle_{p['id']}", use_container_width=True):
                            try:
                                supabase.table("products").update({"is_available": not p["is_available"]}).eq("id", p["id"]).execute()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                    with ce:
                        if st.button("✏️ Edit", key=f"edit_btn_{p['id']}", use_container_width=True):
                            st.session_state["edit_product_id"] = p["id"]
                    with cd:
                        if st.button("🗑️ Delete", key=f"del_{p['id']}", use_container_width=True):
                            try:
                                supabase.table("products").delete().eq("id", p["id"]).execute()
                                st.success(f"'{p['product_name']}' deleted.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")

                    if st.session_state["edit_product_id"] == p["id"]:
                        st.markdown("---")
                        st.markdown("**✏️ Edit Product**")
                        with st.form(f"edit_form_{p['id']}"):
                            e_name    = st.text_input("Product Name",  value=p["product_name"])
                            e_sector  = st.selectbox("Sector", SECTORS, index=SECTORS.index(p["sector"]) if p["sector"] in SECTORS else 0)
                            e_quality = st.selectbox("Grade",  GRADES,  index=GRADES.index(p["quality_grade"]) if p["quality_grade"] in GRADES else 0)
                            e_region  = st.selectbox("Region", REGIONS, index=REGIONS.index(p["region"]) if p["region"] in REGIONS else 0)
                            e_qty     = st.number_input("Quantity", min_value=0.1, value=float(p["quantity"]), step=1.0)
                            e_unit    = st.selectbox("Unit", UNITS, index=UNITS.index(p["unit"]) if p["unit"] in UNITS else 0)
                            e_price   = st.number_input("Price (Birr)", min_value=1.0, value=float(p["price_birr"]), step=10.0)
                            e_desc    = st.text_area("Description", value=p.get("description") or "")
                            sv, cn    = st.columns(2)
                            with sv:
                                save = st.form_submit_button("💾 Save", use_container_width=True)
                            with cn:
                                cancel = st.form_submit_button("✖ Cancel", use_container_width=True)
                            if save:
                                try:
                                    supabase.table("products").update({
                                        "product_name": e_name, "sector": e_sector,
                                        "quality_grade": e_quality, "region": e_region,
                                        "quantity": e_qty, "unit": e_unit,
                                        "price_birr": e_price, "description": e_desc,
                                    }).eq("id", p["id"]).execute()
                                    st.success("Updated!")
                                    st.session_state["edit_product_id"] = None
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")
                            if cancel:
                                st.session_state["edit_product_id"] = None
                                st.rerun()

                    # AI Matching
                    st.markdown("---")
                    if st.button("🤖 Find Best Merchant Matches", key=f"match_{p['id']}", use_container_width=True):
                        with st.spinner("Scoring merchants..."):
                            try:
                                merchants_raw = supabase.table("profiles").select("*").eq("role", "merchant").execute().data or []
                                listing_data  = {
                                    "sector": p["sector"], "product_name": p["product_name"],
                                    "price_birr": p["price_birr"], "quantity": p["quantity"],
                                    "quality_grade": p["quality_grade"], "region": p["region"],
                                    "is_verified": 1, "delivery_available": 1,
                                    "producer_rating": 4.0, "producer_experience": 3,
                                    "producer_tx": 0, "return_rate": 0.05,
                                }
                                merchant_list = [{
                                    "id": m["id"], "name": m["full_name"],
                                    "phone": m.get("phone"),
                                    "preferred_sector":   m.get("preferred_sector"),
                                    "preferred_product":  m.get("preferred_product"),
                                    "region":             m.get("region"),
                                    "max_budget_birr":    m.get("max_budget_birr") or 0,
                                    "preferred_quality":  m.get("preferred_quality") or "Any",
                                    "needs_delivery":     m.get("needs_delivery") or False,
                                    "is_verified":        True,
                                    "rating":             m.get("rating") or 4.0,
                                    "total_transactions": m.get("total_transactions") or 0,
                                    "years_in_business":  m.get("years_in_business") or 1,
                                    "return_rate":        m.get("return_rate") or 0.05,
                                    "payment_method":     m.get("payment_method"),
                                } for m in merchants_raw]

                                if not merchant_list:
                                    st.warning("No merchants registered yet.")
                                else:
                                    ranked = rank_merchants(listing_data, merchant_list)
                                    top5   = [r for r in ranked if r["match_probability"] > 0.1][:5]
                                    if not top5:
                                        st.info("No strong matches found.")
                                    else:
                                        st.markdown("**Top Matched Merchants:**")
                                        for r in top5:
                                            pct   = r["match_probability"] * 100
                                            badge = "🟢" if r["is_match"] == 1 else "🟡"
                                            mc1, mc2 = st.columns([3, 1])
                                            with mc1:
                                                st.write(
                                                    f"{badge} **{r['name']}** — {pct:.1f}% match · "
                                                    f"{r.get('region','N/A')} · "
                                                    f"wants {r.get('preferred_product') or 'N/A'} · "
                                                    f"📞 {r.get('phone') or 'N/A'}"
                                                )
                                            with mc2:
                                                if st.button("🤝 Agreement", key=f"agr_{p['id']}_{r['id']}", use_container_width=True):
                                                    st.session_state["agreement_product_id"] = p["id"]
                                                    st.session_state["agreement_merchant"]   = r
                                                    st.rerun()
                            except Exception as e:
                                st.error(f"Matching failed: {e}")

                    # Demand forecast
                    try:
                        fc = forecast_demand(p["product_name"], p["region"], weeks_ahead=4)
                    except Exception:
                        fc = None
                    if fc and "error" not in fc:
                        trend_icon = {"up": "🟢 ↑ Rising", "down": "🔴 ↓ Falling", "stable": "🟡 → Stable"}[fc["trend"]]
                        st.caption(f"📈 {trend_icon} | R²={fc['r2']:.2f} RMSE=±{fc['rmse']:,.0f}")
                        all_labels  = [f"W-{7-i}" for i in range(8)] + [f"+{w}w" for w in fc["weeks"]]
                        hist_series = fc["historical"] + [None] * 4
                        fc_series   = [None] * 7 + [fc["historical"][-1]] + fc["forecast"]
                        chart_data  = pd.DataFrame({"Actual": hist_series, "Forecast": fc_series}, index=all_labels)
                        st.line_chart(chart_data, color=["#4A90D9", "#F5A623"], height=180)
                    else:
                        st.caption("📈 Demand forecast unavailable.")


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
                    f"🤖 AI Matching active — **{profile.get('preferred_product','N/A')}** "
                    f"in **{profile.get('preferred_sector','N/A')}** · "
                    f"Budget: **{profile.get('max_budget_birr', 0):,.0f} Birr** · "
                    f"Quality: **{profile.get('preferred_quality','Any')}** — update in ⚙️ Profile"
                )
            else:
                st.warning("⚠️ No buying preferences set — go to ⚙️ Profile to enable AI matching.")
            st.divider()

        try:
            orders = supabase.table("orders") \
                .select("*, products(product_name, unit, region, profiles(full_name))") \
                .eq("buyer_id", st.session_state["user"].id) \
                .order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Could not load orders: {e}")
            orders = []

        if not orders:
            st.info("No orders yet. Browse products to get started.")
        else:
            total_spent = sum(o["total_price_birr"] for o in orders)
            pending_cnt = sum(1 for o in orders if o["status"] == "pending")
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Orders", len(orders))
            m2.metric("Total Spent",  f"{total_spent:,.0f} Birr")
            m3.metric("Pending",      pending_cnt)
            st.divider()

            sf = st.selectbox("Filter by Status", ["All", "pending", "confirmed", "delivered", "cancelled"])
            filtered = orders if sf == "All" else [o for o in orders if o["status"] == sf]

            for o in filtered:
                prod        = o.get("products") or {}
                pname       = prod.get("product_name", "Unknown product")
                unit        = prod.get("unit", "")
                seller_name = (prod.get("profiles") or {}).get("full_name", "Unknown seller")
                sbadge      = {
                    "pending": "🟡 Pending", "confirmed": "🔵 Confirmed",
                    "delivered": "🟢 Delivered", "cancelled": "🔴 Cancelled",
                }.get(o["status"], o["status"])

                with st.container(border=True):
                    ca, cb, cc = st.columns([3, 2, 2])
                    with ca:
                        st.markdown(f"**{pname}**")
                        st.caption(f"Seller: {seller_name} · Region: {prod.get('region','N/A')}")
                        st.caption(f"Qty: {o['quantity_ordered']} {unit}")
                        if o.get("notes"):
                            st.caption(f"📝 {o['notes']}")
                    with cb:
                        st.metric("Total", f"{o['total_price_birr']:,.0f} Birr")
                        st.caption(sbadge)
                    with cc:
                        rl = o.get("fraud_risk_level", "Unknown")
                        if rl != "Unknown":
                            rb = {"Low":"🟢","Medium":"🟡","High":"🔴"}.get(rl,"⚪")
                            st.caption(f"{rb} Fraud Risk: **{rl}**")
                        if o["status"] == "pending":
                            if st.button("❌ Cancel", key=f"cancel_{o['id']}"):
                                try:
                                    supabase.table("orders").update({"status": "cancelled"}).eq("id", o["id"]).execute()
                                    st.success("Order cancelled.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")


# ════════════════════════════════════════════════════════════
# TAB: PROFILE (defined ONCE for all roles)
# ════════════════════════════════════════════════════════════
with tab_profile:
    st.subheader("⚙️ My Profile")
    st.caption(f"**{profile['full_name']}** · {profile['role'].capitalize()} · {profile['region']}")
    st.divider()

    if role == "merchant":
        st.markdown("### 🏪 Buying Preferences")
        st.caption("Set preferences to power AI product matching and Best Matches tab")

        pref_sector   = st.selectbox("Preferred Sector", SECTORS,
            index=SECTORS.index(profile.get("preferred_sector")) if profile.get("preferred_sector") in SECTORS else 0,
            key="edit_pref_sector")
        pref_product  = st.text_input("Preferred Product", value=profile.get("preferred_product") or "", key="edit_pref_product")
        pref_budget   = st.number_input("Max Budget (Birr)", min_value=0.0, step=1000.0,
            value=float(profile.get("max_budget_birr") or 0), key="edit_pref_budget")
        pref_quality  = st.selectbox("Preferred Quality", ["A", "B", "A or B", "Any"],
            index=["A", "B", "A or B", "Any"].index(profile.get("preferred_quality") or "Any"),
            key="edit_pref_quality")
        pref_delivery = st.checkbox("I need delivery", value=bool(profile.get("needs_delivery")), key="edit_pref_delivery")
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
                }).eq("id", st.session_state["user"].id).execute()
                st.success("✅ Preferences saved!")
                st.session_state["profile"] = get_profile(st.session_state["user"].id)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    elif role == "producer":
        st.markdown("### 📊 My Stats")
        try:
            my_products = supabase.table("products").select("*") \
                .eq("producer_id", st.session_state["user"].id).execute().data or []
            active   = sum(1 for p in my_products if p["is_available"])
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Listings", len(my_products))
            c2.metric("Active",   active)
            c3.metric("Inactive", len(my_products) - active)
        except Exception as e:
            st.error(f"Could not load stats: {e}")

    else:  # customer
        st.markdown("### 📊 My Stats")
        try:
            my_orders   = supabase.table("orders").select("*") \
                .eq("buyer_id", st.session_state["user"].id).execute().data or []
            total_spent = sum(o["total_price_birr"] for o in my_orders)
            c1, c2 = st.columns(2)
            c1.metric("Total Orders", len(my_orders))
            c2.metric("Total Spent",  f"{total_spent:,.0f} Birr")
        except Exception as e:
            st.error(f"Could not load stats: {e}")
ENDOFFILE
echo "Lines: $(wc -l < /home/claude/app.py)"
