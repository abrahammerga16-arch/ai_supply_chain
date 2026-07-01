
"""
Ethiopian AI Supply Chain — Admin Dashboard
Wolaita Sodo University | Department of ECE

Run alongside app.py. Access via Streamlit multipage or as a standalone page.
Add to .streamlit/pages/ or run: streamlit run admin.py

Admin credentials are stored in Supabase `profiles` table with role = 'admin'.
To create the first admin, run in Supabase SQL Editor:
    UPDATE profiles SET role = 'admin' WHERE id = '<your-user-uuid>';
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import datetime
import streamlit as st
import pandas as pd

from src.db import get_supabase_client

# ── PAGE CONFIG ──────────────────────────────────────────────
st.set_page_config(
    page_title="Admin — Ethiopian AI Supply Chain",
    page_icon="🛡️",
    layout="wide",
)

# ── THEME CONSTANTS ──────────────────────────────────────────
ADMIN_COLOR  = "#1a5276"
DANGER_COLOR = "#c0392b"
SUCCESS_COLOR = "#117a65"

# ── CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
    .admin-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-left: 6px;
    }
    .badge-admin    { background: #1a5276; color: white; }
    .badge-producer { background: #117a65; color: white; }
    .badge-merchant { background: #784212; color: white; }
    .badge-customer { background: #515a5a; color: white; }
    .stat-card {
        background: #f4f6f7;
        border-radius: 10px;
        padding: 18px 20px;
        border-left: 4px solid #1a5276;
        margin-bottom: 8px;
    }
    .danger-zone {
        border: 1.5px solid #c0392b;
        border-radius: 8px;
        padding: 16px;
        background: #fdedec;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ── SUPABASE ─────────────────────────────────────────────────
try:
    supabase = get_supabase_client()
except ValueError as e:
    st.error(str(e))
    st.stop()

# ── SESSION KEYS ─────────────────────────────────────────────
for key in ["admin_user", "admin_profile"]:
    if key not in st.session_state:
        st.session_state[key] = None


# ── HELPERS ──────────────────────────────────────────────────
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
        supabase.table("notifications").insert(payload).execute()
    except Exception as e:
        st.toast(f"⚠️ Notification failed: {e}", icon="⚠️")


def role_badge(role):
    cls = {
        "admin":    "badge-admin",
        "producer": "badge-producer",
        "merchant": "badge-merchant",
        "customer": "badge-customer",
    }.get(role, "badge-customer")
    return f'<span class="admin-badge {cls}">{role.capitalize()}</span>'


def fmt_birr(v):
    try:
        return f"{float(v):,.0f} Birr"
    except Exception:
        return "—"


def fmt_dt(s):
    if not s:
        return "—"
    try:
        return datetime.datetime.fromisoformat(
            str(s).replace("Z", "+00:00")
        ).strftime("%d %b %Y, %H:%M")
    except Exception:
        return str(s)[:16]


# ── SIDEBAR / AUTH ───────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ Admin Panel")
    st.caption("Ethiopian AI Supply Chain")
    st.divider()

    if st.session_state.admin_user is None:
        st.markdown("### Sign In")
        a_email = st.text_input("Email", key="admin_email")
        a_pass  = st.text_input("Password", type="password", key="admin_pass")
        if st.button("Sign In", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": a_email, "password": a_pass})
                if res.user:
                    p = get_profile(res.user.id)
                    if p and p.get("role") == "admin":
                        st.session_state.admin_user    = res.user
                        st.session_state.admin_profile = get_profile(res.user.id)
                        st.success("Welcome, Admin.")
                        st.rerun()
                    else:
                        supabase.auth.sign_out()
                        st.error("Access denied — admin accounts only.")
                else:
                    st.error("Invalid credentials.")
            except Exception as e:
                st.error(f"Login failed: {e}")
    else:
        p = st.session_state.admin_profile
        st.success(f"🛡️ {p['full_name']}")
        st.caption(f"Role: Admin · {p['region']}")
        st.divider()
        st.markdown("**Quick Nav**")
        st.markdown("- 📊 Overview\n- 👥 Users\n- 📦 Products\n- 🧾 Orders\n- 🔔 Notifications\n- 📈 Analytics\n- ⚙️ Settings")
        st.divider()
        if st.button("Sign Out", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.admin_user    = None
            st.session_state.admin_profile = None
            st.rerun()

# ── GUARD ────────────────────────────────────────────────────
if st.session_state.admin_user is None:
    st.title("🛡️ Admin Access Required")
    st.info("Sign in with an admin account using the sidebar.")
    st.stop()

# ── LOAD ALL DATA ────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_all():
    users    = supabase.table("profiles").select("*").order("created_at", desc=True).execute().data or []
    products = supabase.table("products").select("*").order("created_at", desc=True).execute().data or []
    orders   = supabase.table("orders").select(
        "*, products(product_name, unit, sector), profiles(full_name, role, region)"
    ).order("created_at", desc=True).execute().data or []
    notifs   = supabase.table("notifications").select("*").order("created_at", desc=True).execute().data or []
    return users, products, orders, notifs

users, products, orders, notifs = load_all()

# ── HEADER ───────────────────────────────────────────────────
st.markdown(f"# 🛡️ Admin Dashboard")
st.caption(f"Ethiopian AI Supply Chain Platform · {datetime.date.today().strftime('%d %B %Y')}")
st.divider()

# ── TABS ─────────────────────────────────────────────────────
tabs = st.tabs([
    "📊 Overview",
    "👥 Users",
    "📦 Products",
    "🧾 Orders",
    "🔔 Notifications",
    "📈 Analytics",
    "⚙️ Settings",
])
tab_overview, tab_users, tab_products, tab_orders, tab_notifs, tab_analytics, tab_settings = tabs


# ════════════════════════════════════════════════════════════
# TAB: OVERVIEW
# ════════════════════════════════════════════════════════════
with tab_overview:
    st.subheader("Platform Overview")

    total_revenue   = sum(o["total_price_birr"] for o in orders if o["status"] == "confirmed")
    delivered_rev   = sum(o["total_price_birr"] for o in orders if o["status"] == "delivered")
    pending_orders  = sum(1 for o in orders if o["status"] == "pending")
    high_risk       = sum(1 for o in orders if o.get("fraud_risk_level") == "High")
    active_products = sum(1 for p in products if p.get("is_available"))
    unread_notifs   = sum(1 for n in notifs if not n.get("is_read"))

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r1c1.metric("👥 Total Users",     len(users))
    r1c2.metric("📦 Active Products", active_products)
    r1c3.metric("🧾 Total Orders",    len(orders))
    r1c4.metric("💰 Confirmed Revenue", fmt_birr(total_revenue))

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    r2c1.metric("🟡 Pending Orders",  pending_orders)
    r2c2.metric("🟢 Delivered Revenue", fmt_birr(delivered_rev))
    r2c3.metric("🔴 High Fraud Risk", high_risk)
    r2c4.metric("🔔 Unread Notifs",   unread_notifs)

    st.divider()
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 👥 Users by Role")
        role_counts = {}
        for u in users:
            r = u.get("role", "unknown")
            role_counts[r] = role_counts.get(r, 0) + 1
        df_roles = pd.DataFrame(list(role_counts.items()), columns=["Role", "Count"])
        st.dataframe(df_roles, use_container_width=True, hide_index=True)

    with col_right:
        st.markdown("#### 🧾 Orders by Status")
        status_counts = {}
        for o in orders:
            s = o.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1
        df_status = pd.DataFrame(list(status_counts.items()), columns=["Status", "Count"])
        st.dataframe(df_status, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 🕐 Recent Activity (Last 10 Orders)")
    recent = sorted(orders, key=lambda x: x.get("created_at", ""), reverse=True)[:10]
    for o in recent:
        prod    = o.get("products") or {}
        buyer   = o.get("profiles") or {}
        status  = o.get("status", "unknown")
        badge   = {"pending": "🟡", "confirmed": "🔵", "delivered": "🟢", "cancelled": "🔴"}.get(status, "⚪")
        st.caption(
            f"{badge} **{prod.get('product_name', 'N/A')}** — "
            f"{buyer.get('full_name', 'N/A')} · "
            f"{fmt_birr(o['total_price_birr'])} · "
            f"{fmt_dt(o.get('created_at'))}"
        )


# ════════════════════════════════════════════════════════════
# TAB: USERS
# ════════════════════════════════════════════════════════════
with tab_users:
    st.subheader("👥 User Management")

    col_search, col_role_f = st.columns(2)
    with col_search:
        user_search = st.text_input("🔍 Search by name, email, or region", key="user_search")
    with col_role_f:
        role_filter = st.selectbox("Filter by Role", ["All", "admin", "producer", "merchant", "customer"], key="role_filter")

    filtered_users = users
    if user_search:
        q = user_search.lower()
        filtered_users = [
            u for u in filtered_users
            if q in (u.get("full_name") or "").lower()
            or q in (u.get("region") or "").lower()
            or q in str(u.get("id", "")).lower()
        ]
    if role_filter != "All":
        filtered_users = [u for u in filtered_users if u.get("role") == role_filter]

    st.caption(f"Showing {len(filtered_users)} of {len(users)} users")

    for u in filtered_users:
        with st.container(border=True):
            col_a, col_b, col_c = st.columns([3, 2, 2])
            with col_a:
                st.markdown(
                    f"**{u.get('full_name', 'N/A')}** "
                    + role_badge(u.get("role", "unknown")),
                    unsafe_allow_html=True
                )
                st.caption(f"📍 {u.get('region', 'N/A')} · 📞 {u.get('phone') or 'N/A'}")
                st.caption(f"ID: `{u['id']}`")
            with col_b:
                u_orders = [o for o in orders if (o.get("profiles") or {}).get("full_name") == u.get("full_name")]
                u_spent  = sum(o["total_price_birr"] for o in u_orders)
                st.metric("Orders", len(u_orders), label_visibility="visible")
                if u.get("role") == "merchant":
                    st.caption(f"Spent: {fmt_birr(u_spent)}")
                elif u.get("role") == "producer":
                    u_products = [p for p in products if p.get("producer_id") == u["id"]]
                    st.caption(f"Products: {len(u_products)}")
            with col_c:
                new_role = st.selectbox(
                    "Change Role",
                    ["producer", "merchant", "customer", "admin"],
                    index=["producer", "merchant", "customer", "admin"].index(u.get("role", "customer"))
                    if u.get("role") in ["producer", "merchant", "customer", "admin"] else 2,
                    key=f"role_{u['id']}"
                )
                col_save, col_notify = st.columns(2)
                with col_save:
                    if st.button("💾 Save Role", key=f"save_role_{u['id']}", use_container_width=True):
                        try:
                            supabase.table("profiles").update({"role": new_role}).eq("id", u["id"]).execute()
                            st.success(f"Role → {new_role}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                with col_notify:
                    if st.button("📣 Notify", key=f"notify_user_{u['id']}", use_container_width=True):
                        st.session_state[f"notify_open_{u['id']}"] = True

            if st.session_state.get(f"notify_open_{u['id']}"):
                with st.expander("Send Notification", expanded=True):
                    n_title = st.text_input("Title", key=f"n_title_{u['id']}")
                    n_msg   = st.text_area("Message", key=f"n_msg_{u['id']}")
                    n_type  = st.selectbox("Type", ["info", "success", "warning", "error"], key=f"n_type_{u['id']}")
                    if st.button("Send", key=f"send_n_{u['id']}"):
                        if n_title and n_msg:
                            send_notification(u["id"], n_title, n_msg, n_type)
                            st.success("Notification sent.")
                            st.session_state[f"notify_open_{u['id']}"] = False
                            st.rerun()
                        else:
                            st.warning("Enter title and message.")

    st.divider()
    st.markdown("#### ➕ Create New Admin Account")
    with st.expander("Create Admin User"):
        na_name   = st.text_input("Full Name", key="na_name")
        na_email  = st.text_input("Email", key="na_email")
        na_pass   = st.text_input("Password (min 8 chars + number)", type="password", key="na_pass")
        na_region = st.selectbox("Region", [
            "Addis Ababa", "Oromia", "SNNPR", "Amhara",
            "Tigray", "Sidama", "Dire Dawa", "Harari"
        ], key="na_region")
        na_phone  = st.text_input("Phone", key="na_phone")
        if st.button("✅ Create Admin", key="create_admin"):
            if not na_name or not na_email or not na_pass or not na_phone:
                st.warning("Fill all fields.")
            elif len(na_pass) < 8 or not any(c.isdigit() for c in na_pass):
                st.warning("Password must be ≥8 chars and contain a number.")
            else:
                try:
                    res = supabase.auth.sign_up({"email": na_email, "password": na_pass})
                    if res.user:
                        supabase.table("profiles").insert({
                            "id":        res.user.id,
                            "full_name": na_name,
                            "role":      "admin",
                            "region":    na_region,
                            "phone":     na_phone,
                        }).execute()
                        st.success(f"Admin '{na_name}' created.")
                        st.rerun()
                    else:
                        st.error("Sign-up failed — email may already exist.")
                except Exception as e:
                    st.error(f"Failed: {e}")


# ════════════════════════════════════════════════════════════
# TAB: PRODUCTS
# ════════════════════════════════════════════════════════════
with tab_products:
    st.subheader("📦 Product Management")

    col_ps, col_pa = st.columns(2)
    with col_ps:
        prod_search = st.text_input("🔍 Search product name", key="prod_search")
    with col_pa:
        avail_filter = st.selectbox("Availability", ["All", "Active", "Inactive"], key="avail_filter")

    fp = products
    if prod_search:
        fp = [p for p in fp if prod_search.lower() in (p.get("product_name") or "").lower()]
    if avail_filter == "Active":
        fp = [p for p in fp if p.get("is_available")]
    elif avail_filter == "Inactive":
        fp = [p for p in fp if not p.get("is_available")]

    st.caption(f"Showing {len(fp)} of {len(products)} products")

    # Summary row
    sm1, sm2, sm3 = st.columns(3)
    sm1.metric("Total Products",  len(products))
    sm2.metric("Active",  sum(1 for p in products if p.get("is_available")))
    sm3.metric("Inactive", sum(1 for p in products if not p.get("is_available")))
    st.divider()

    for p in fp:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                status_dot = "🟢" if p.get("is_available") else "🔴"
                st.markdown(f"{status_dot} **{p['product_name']}** · {p.get('sector','N/A')} · Grade {p.get('quality_grade','N/A')}")
                st.caption(f"📍 {p.get('region','N/A')} · {p.get('quantity',0)} {p.get('unit','')} · {fmt_birr(p.get('price_birr',0))}/unit")
                st.caption(f"Producer ID: `{p.get('producer_id','N/A')}`")
                if p.get("description"):
                    st.caption(p["description"])
            with c2:
                prod_orders = [o for o in orders if o.get("product_id") == p.get("id")]
                st.metric("Orders", len(prod_orders))
                order_rev = sum(o["total_price_birr"] for o in prod_orders if o.get("status") == "confirmed")
                st.caption(f"Confirmed Rev: {fmt_birr(order_rev)}")
            with c3:
                btn_label = "⏸ Deactivate" if p.get("is_available") else "▶ Activate"
                if st.button(btn_label, key=f"admin_toggle_{p['id']}", use_container_width=True):
                    try:
                        supabase.table("products").update(
                            {"is_available": not p.get("is_available")}
                        ).eq("id", p["id"]).execute()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
                if st.button("🗑️ Delete", key=f"admin_del_prod_{p['id']}", use_container_width=True):
                    try:
                        supabase.table("products").delete().eq("id", p["id"]).execute()
                        st.success(f"'{p['product_name']}' deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

    if fp:
        st.divider()
        st.markdown("#### 📥 Export Products as CSV")
        df_prod = pd.DataFrame([{
            "Product":      p.get("product_name"),
            "Sector":       p.get("sector"),
            "Quality":      p.get("quality_grade"),
            "Region":       p.get("region"),
            "Quantity":     p.get("quantity"),
            "Unit":         p.get("unit"),
            "Price (Birr)": p.get("price_birr"),
            "Available":    p.get("is_available"),
            "Created":      fmt_dt(p.get("created_at")),
        } for p in products])
        st.download_button(
            "⬇️ Download products.csv",
            data=df_prod.to_csv(index=False),
            file_name="products.csv",
            mime="text/csv",
        )


# ════════════════════════════════════════════════════════════
# TAB: ORDERS
# ════════════════════════════════════════════════════════════
with tab_orders:
    st.subheader("🧾 Order Management")

    co1, co2, co3 = st.columns(3)
    with co1:
        ord_status_f = st.selectbox("Status", ["All", "pending", "confirmed", "delivered", "cancelled"], key="ord_status_f")
    with co2:
        ord_risk_f = st.selectbox("Fraud Risk", ["All", "High", "Medium", "Low", "Unknown"], key="ord_risk_f")
    with co3:
        ord_search = st.text_input("🔍 Search product name", key="ord_search")

    fo = orders
    if ord_status_f != "All":
        fo = [o for o in fo if o.get("status") == ord_status_f]
    if ord_risk_f != "All":
        fo = [o for o in fo if o.get("fraud_risk_level") == ord_risk_f]
    if ord_search:
        fo = [o for o in fo if ord_search.lower() in ((o.get("products") or {}).get("product_name") or "").lower()]

    total_fo_rev = sum(o["total_price_birr"] for o in fo if o["status"] in ("confirmed", "delivered"))
    st.caption(f"Showing {len(fo)} orders · Revenue: {fmt_birr(total_fo_rev)}")
    st.divider()

    for o in fo:
        prod   = o.get("products") or {}
        buyer  = o.get("profiles") or {}
        status = o.get("status", "unknown")
        risk   = o.get("fraud_risk_level", "Unknown")

        status_badge = {"pending": "🟡", "confirmed": "🔵", "delivered": "🟢", "cancelled": "🔴"}.get(status, "⚪")
        risk_badge   = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(risk, "⚪")

        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(f"**{prod.get('product_name', 'N/A')}** · {prod.get('sector','N/A')}")
                st.caption(f"👤 Buyer: {buyer.get('full_name','N/A')} ({buyer.get('role','N/A')}) · 📍 {buyer.get('region','N/A')}")
                st.caption(f"Qty: {o.get('quantity_ordered',0)} {prod.get('unit','')} · {fmt_dt(o.get('created_at'))}")
                if o.get("notes"):
                    st.caption(f"📝 {o['notes']}")
                if o.get("agreement_delivery_date"):
                    st.caption(f"📑 Agreement · Delivery: {o['agreement_delivery_date']} · Payment: {o.get('agreement_payment_method','N/A')}")
            with c2:
                st.metric("Value", fmt_birr(o["total_price_birr"]))
                st.caption(f"{status_badge} {status.capitalize()}")
                st.caption(f"{risk_badge} Fraud: {risk}")
                st.caption(f"Prob: {(o.get('fraud_probability') or 0):.1%}")
            with c3:
                new_status = st.selectbox(
                    "Change Status",
                    ["pending", "confirmed", "delivered", "cancelled"],
                    index=["pending", "confirmed", "delivered", "cancelled"].index(status)
                    if status in ["pending", "confirmed", "delivered", "cancelled"] else 0,
                    key=f"admin_ord_status_{o['id']}"
                )
                if st.button("💾 Update Status", key=f"admin_ord_save_{o['id']}", use_container_width=True):
                    try:
                        supabase.table("orders").update({"status": new_status}).eq("id", o["id"]).execute()
                        # Notify buyer of admin status change
                        send_notification(
                            recipient_id=o["buyer_id"],
                            title="📋 Order Status Updated (Admin)",
                            message=f"Your order for **{prod.get('product_name','N/A')}** status changed to **{new_status}** by platform admin.",
                            notif_type="info",
                            order_id=o["id"],
                        )
                        st.success(f"Status → {new_status}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
                if st.button("🗑️ Delete Order", key=f"admin_del_ord_{o['id']}", use_container_width=True):
                    try:
                        supabase.table("orders").delete().eq("id", o["id"]).execute()
                        st.success("Order deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

    st.divider()
    st.markdown("#### 📥 Export Orders as CSV")
    df_orders = pd.DataFrame([{
        "Order ID":      o.get("id"),
        "Product":       (o.get("products") or {}).get("product_name"),
        "Buyer":         (o.get("profiles") or {}).get("full_name"),
        "Buyer Role":    (o.get("profiles") or {}).get("role"),
        "Qty":           o.get("quantity_ordered"),
        "Total (Birr)":  o.get("total_price_birr"),
        "Status":        o.get("status"),
        "Fraud Risk":    o.get("fraud_risk_level"),
        "Fraud Prob":    o.get("fraud_probability"),
        "Producer Conf": o.get("producer_confirmed"),
        "Merchant Conf": o.get("merchant_confirmed"),
        "Created":       fmt_dt(o.get("created_at")),
    } for o in orders])
    st.download_button(
        "⬇️ Download orders.csv",
        data=df_orders.to_csv(index=False),
        file_name="orders.csv",
        mime="text/csv",
    )


# ════════════════════════════════════════════════════════════
# TAB: NOTIFICATIONS
# ════════════════════════════════════════════════════════════
with tab_notifs:
    st.subheader("🔔 Notification Center")

    col_nb1, col_nb2 = st.columns(2)
    with col_nb1:
        st.metric("Total Notifications", len(notifs))
    with col_nb2:
        st.metric("Unread", sum(1 for n in notifs if not n.get("is_read")))

    st.divider()

    # Broadcast to all or a role
    st.markdown("### 📣 Broadcast Notification")
    bc_col1, bc_col2 = st.columns(2)
    with bc_col1:
        bc_role  = st.selectbox("Send To", ["All Users", "Producers", "Merchants", "Customers"], key="bc_role")
        bc_title = st.text_input("Title", key="bc_title")
    with bc_col2:
        bc_msg  = st.text_area("Message", key="bc_msg")
        bc_type = st.selectbox("Type", ["info", "success", "warning", "error"], key="bc_type")

    if st.button("📣 Send Broadcast", use_container_width=True, key="bc_send"):
        if not bc_title or not bc_msg:
            st.warning("Enter title and message.")
        else:
            role_map = {
                "All Users":  None,
                "Producers":  "producer",
                "Merchants":  "merchant",
                "Customers":  "customer",
            }
            target_role = role_map[bc_role]
            targets = [u for u in users if target_role is None or u.get("role") == target_role]
            count = 0
            for u in targets:
                send_notification(u["id"], bc_title, bc_msg, bc_type)
                count += 1
            st.success(f"✅ Broadcast sent to {count} user(s).")
            st.rerun()

    st.divider()
    st.markdown("### 📋 All Notifications (Last 50)")

    notif_user_filter = st.text_input("🔍 Filter by recipient ID or title", key="notif_filter")
    fn = notifs[:50]
    if notif_user_filter:
        q = notif_user_filter.lower()
        fn = [n for n in fn if q in (n.get("title") or "").lower() or q in str(n.get("recipient_id","")).lower()]

    for n in fn:
        _icon = {"success": "✅", "warning": "🚫", "error": "❌", "info": "ℹ️"}.get(n.get("type","info"), "🔔")
        read_label = "Read" if n.get("is_read") else "**Unread**"
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"{_icon} **{n.get('title','N/A')}** · {read_label}")
                st.caption(n.get("message", ""))
                st.caption(f"To: `{n.get('recipient_id','')}` · {fmt_dt(n.get('created_at'))}")
            with c2:
                if st.button("🗑️", key=f"del_notif_{n['id']}"):
                    try:
                        supabase.table("notifications").delete().eq("id", n["id"]).execute()
                        st.rerun()
                    except Exception as e:
                        st.error(f"{e}")

    st.divider()
    if st.button("🗑️ Clear ALL Notifications (Platform-Wide)", key="clear_all_notifs_admin"):
        try:
            supabase.table("notifications").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            st.success("All notifications cleared.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")


# ════════════════════════════════════════════════════════════
# TAB: ANALYTICS
# ════════════════════════════════════════════════════════════
with tab_analytics:
    st.subheader("📈 Platform Analytics")

    # Revenue by sector
    st.markdown("#### 💰 Revenue by Sector")
    sector_rev = {}
    for o in orders:
        if o.get("status") in ("confirmed", "delivered"):
            s = (o.get("products") or {}).get("sector", "Unknown")
            sector_rev[s] = sector_rev.get(s, 0) + o["total_price_birr"]
    if sector_rev:
        df_sr = pd.DataFrame(list(sector_rev.items()), columns=["Sector", "Revenue (Birr)"])
        df_sr = df_sr.sort_values("Revenue (Birr)", ascending=False)
        st.bar_chart(df_sr.set_index("Sector"))
        st.dataframe(df_sr, use_container_width=True, hide_index=True)
    else:
        st.info("No confirmed revenue data yet.")

    st.divider()

    # Orders over time (by day)
    st.markdown("#### 📅 Orders Over Time")
    orders_by_day = {}
    for o in orders:
        raw = o.get("created_at", "")
        if raw:
            try:
                day = datetime.datetime.fromisoformat(
                    raw.replace("Z", "+00:00")
                ).strftime("%Y-%m-%d")
                orders_by_day[day] = orders_by_day.get(day, 0) + 1
            except Exception:
                pass
    if orders_by_day:
        df_obt = pd.DataFrame(
            sorted(orders_by_day.items()),
            columns=["Date", "Orders"]
        ).set_index("Date")
        st.line_chart(df_obt)
    else:
        st.info("No order data yet.")

    st.divider()

    # Fraud risk breakdown
    st.markdown("#### 🔴 Fraud Risk Distribution")
    risk_counts = {}
    for o in orders:
        r = o.get("fraud_risk_level", "Unknown")
        risk_counts[r] = risk_counts.get(r, 0) + 1
    if risk_counts:
        df_risk = pd.DataFrame(list(risk_counts.items()), columns=["Risk Level", "Orders"])
        st.dataframe(df_risk, use_container_width=True, hide_index=True)
        st.bar_chart(df_risk.set_index("Risk Level"))

    st.divider()

    # Top buyers
    st.markdown("#### 🏆 Top 5 Buyers by Spend")
    buyer_spend = {}
    for o in orders:
        if o.get("status") in ("confirmed", "delivered"):
            buyer_name = (o.get("profiles") or {}).get("full_name", "Unknown")
            buyer_spend[buyer_name] = buyer_spend.get(buyer_name, 0) + o["total_price_birr"]
    if buyer_spend:
        top_buyers = sorted(buyer_spend.items(), key=lambda x: x[1], reverse=True)[:5]
        df_buyers = pd.DataFrame(top_buyers, columns=["Buyer", "Total Spent (Birr)"])
        st.dataframe(df_buyers, use_container_width=True, hide_index=True)

    st.divider()

    # Top products
    st.markdown("#### 📦 Top 5 Products by Order Volume")
    prod_counts = {}
    for o in orders:
        pname = (o.get("products") or {}).get("product_name", "Unknown")
        prod_counts[pname] = prod_counts.get(pname, 0) + o.get("quantity_ordered", 0)
    if prod_counts:
        top_prods = sorted(prod_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        df_prods = pd.DataFrame(top_prods, columns=["Product", "Total Quantity Ordered"])
        st.dataframe(df_prods, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════
# TAB: SETTINGS
# ════════════════════════════════════════════════════════════
with tab_settings:
    st.subheader("⚙️ Platform Settings")

    st.markdown("### 🛡️ My Admin Profile")
    ap = st.session_state.admin_profile
    with st.container(border=True):
        s1, s2 = st.columns(2)
        with s1:
            new_name  = st.text_input("Full Name",    value=ap.get("full_name", ""), key="settings_name")
            new_phone = st.text_input("Phone Number", value=ap.get("phone") or "", key="settings_phone")
        with s2:
            REGIONS   = ["Addis Ababa", "Oromia", "SNNPR", "Amhara", "Tigray", "Sidama", "Dire Dawa", "Harari"]
            new_region = st.selectbox(
                "Region", REGIONS,
                index=REGIONS.index(ap.get("region")) if ap.get("region") in REGIONS else 0,
                key="settings_region"
            )
        if st.button("💾 Update Profile", key="update_admin_profile"):
            try:
                supabase.table("profiles").update({
                    "full_name": new_name,
                    "phone":     new_phone,
                    "region":    new_region,
                }).eq("id", st.session_state.admin_user.id).execute()
                st.session_state.admin_profile = get_profile(st.session_state.admin_user.id)
                st.success("Profile updated.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    st.divider()
    st.markdown("### 📊 Platform Stats Summary")
    with st.container(border=True):
        cs1, cs2, cs3, cs4 = st.columns(4)
        cs1.metric("Total Users",    len(users))
        cs2.metric("Total Products", len(products))
        cs3.metric("Total Orders",   len(orders))
        cs4.metric("Notifications",  len(notifs))

        total_platform_rev = sum(
            o["total_price_birr"] for o in orders
            if o.get("status") in ("confirmed", "delivered")
        )
        st.metric("Total Platform Revenue", fmt_birr(total_platform_rev))

    st.divider()
    st.markdown("### 🔴 Danger Zone")
    st.markdown('<div class="danger-zone">', unsafe_allow_html=True)
    st.warning("⚠️ These actions are **irreversible**. Use with extreme caution.")

    col_dz1, col_dz2 = st.columns(2)
    with col_dz1:
        if st.button("🗑️ Delete ALL Cancelled Orders", key="del_cancelled", use_container_width=True):
            try:
                supabase.table("orders").delete().eq("status", "cancelled").execute()
                st.success("All cancelled orders deleted.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")
    with col_dz2:
        if st.button("🗑️ Delete ALL Inactive Products", key="del_inactive_prod", use_container_width=True):
            try:
                supabase.table("products").delete().eq("is_available", False).execute()
                st.success("All inactive products deleted.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
