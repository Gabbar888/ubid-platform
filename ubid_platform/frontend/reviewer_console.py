"""UBID Platform Console — Streamlit UI.

Government of Karnataka — Department of Commerce & Industries
Run: streamlit run frontend/reviewer_console.py
"""
from __future__ import annotations

import os
from datetime import datetime, date, timedelta

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UBID Platform | Karnataka Commerce & Industries",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Tricolor / Indian-government theme ────────────────────────────────────────
# Palette anchored to the Indian flag and government style guide:
#   Saffron  #FF9933   ·   White  #FFFFFF   ·   India Green  #138808
#   Ashoka navy  #000080   ·   Gov navy  #0B3D91   ·   Surface  #FAF7F2
st.markdown("""
<style>
    /* ── Global typography & background ─────────────────────────────────────── */
    :root {
        --saffron: #FF9933;
        --saffron-deep: #E8731E;
        --india-green: #138808;
        --green-deep: #0E6606;
        --gov-navy: #0B3D91;
        --gov-navy-dark: #062863;
        --ashoka: #000080;
        --surface: #FAF7F2;
        --surface-2: #F1ECE0;
        --ink: #1A1A1A;
        --ink-muted: #5C5C5C;
        --rule: #D9D2C5;
    }

    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        background-color: var(--surface) !important;
        color: var(--ink);
        font-family: 'Inter', 'Source Sans Pro', system-ui, -apple-system, Arial, sans-serif;
    }

    /* Tighter container, but room for the tricolor banner */
    .block-container { padding-top: 0.6rem !important; padding-bottom: 3rem; max-width: 1400px; }

    /* ── Government banner (top of every page) ──────────────────────────────── */
    .gov-banner {
        background: linear-gradient(135deg, var(--gov-navy-dark) 0%, var(--gov-navy) 100%);
        color: #fff;
        padding: 14px 26px;
        border-radius: 8px 8px 0 0;
        margin: -8px -8px 0 -8px;
        display: flex;
        align-items: center;
        gap: 18px;
        box-shadow: 0 2px 6px rgba(11, 61, 145, 0.18);
    }
    .gov-banner .crest {
        width: 52px; height: 52px;
        background: rgba(255,255,255,0.12);
        border: 2px solid rgba(255,255,255,0.4);
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 26px;
        flex-shrink: 0;
    }
    .gov-banner .titles { flex: 1; }
    .gov-banner .gov-name {
        font-size: 0.78rem; letter-spacing: 0.18em; text-transform: uppercase;
        opacity: 0.85; margin-bottom: 2px; font-weight: 500;
    }
    .gov-banner .platform {
        font-size: 1.55rem; font-weight: 700; letter-spacing: -0.01em;
        margin: 0; line-height: 1.1;
    }
    .gov-banner .dept {
        font-size: 0.85rem; opacity: 0.9; font-weight: 400; margin-top: 3px;
    }
    .gov-banner .meta {
        text-align: right; font-size: 0.75rem; opacity: 0.85;
        line-height: 1.4;
    }
    .gov-banner .meta b { font-weight: 600; opacity: 1; }

    /* Tricolor strip immediately under the banner */
    .tricolor {
        height: 5px; display: flex; margin: 0 -8px 22px -8px;
        border-radius: 0 0 6px 6px; overflow: hidden;
    }
    .tricolor .saffron { flex: 1; background: var(--saffron); }
    .tricolor .white   { flex: 1; background: #FFFFFF; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
    .tricolor .green   { flex: 1; background: var(--india-green); }

    /* Page title under the banner */
    h1 { color: var(--gov-navy-dark) !important; font-weight: 700 !important; letter-spacing: -0.01em; margin-bottom: 0.2rem !important; }
    h2 { color: var(--gov-navy-dark) !important; font-weight: 600 !important; border-bottom: 2px solid var(--saffron); padding-bottom: 0.25rem; margin-top: 1.5rem !important; }
    h3 { color: var(--gov-navy) !important; font-weight: 600 !important; }
    [data-testid="stCaptionContainer"], .stCaption { color: var(--ink-muted) !important; }

    /* ── Metric cards ──────────────────────────────────────────────────────── */
    [data-testid="stMetric"] {
        background: #fff;
        border: 1px solid var(--rule);
        border-left: 4px solid var(--saffron);
        padding: 14px 18px 10px 18px;
        border-radius: 4px;
        box-shadow: 0 1px 2px rgba(11, 61, 145, 0.04);
    }
    [data-testid="stMetricLabel"] {
        font-weight: 600 !important;
        color: var(--gov-navy) !important;
        font-size: 0.78rem !important;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.9rem !important;
        font-weight: 700 !important;
        color: var(--ink) !important;
    }
    [data-testid="stMetricDelta"] svg { display: none; }

    /* ── Verdict badges (flag-coloured) ─────────────────────────────────────── */
    .verdict-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 3px;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        border: 1px solid transparent;
    }
    .verdict-active           { background: #E8F5E9; color: var(--green-deep); border-color: #B8E0B5; }
    .verdict-dormant          { background: #FFF3E0; color: #B45309; border-color: #FFD9A8; }
    .verdict-closed           { background: #FFE5E5; color: #991B1B; border-color: #F5B5B5; }
    .verdict-closed_by_silence{ background: #FFE5E5; color: #991B1B; border-color: #F5B5B5; }
    .verdict-nascent          { background: #E3EAFF; color: var(--ashoka); border-color: #B8C4F0; }
    .verdict-unknown          { background: #ECEAE5; color: #4B5563; border-color: var(--rule); }

    /* ── Reviewer tier pills ────────────────────────────────────────────────── */
    .tier-junior { background: var(--saffron); color: #fff; padding: 3px 12px; border-radius: 3px; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.05em; }
    .tier-senior { background: var(--gov-navy); color: #fff; padding: 3px 12px; border-radius: 3px; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.05em; }

    /* ── Sidebar ───────────────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--gov-navy-dark) 0%, var(--gov-navy) 100%) !important;
        border-right: 3px solid var(--saffron);
    }
    section[data-testid="stSidebar"] * { color: #fff !important; }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li,
    section[data-testid="stSidebar"] label { color: #fff !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.18) !important; }

    /* Sidebar inputs */
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] [data-baseweb="select"] > div {
        background-color: rgba(255,255,255,0.95) !important;
        color: var(--ink) !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        border-radius: 3px !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] svg { color: var(--ink) !important; }

    /* Sidebar radio nav */
    section[data-testid="stSidebar"] [role="radiogroup"] > label {
        background: rgba(255,255,255,0.06);
        margin: 4px 0;
        padding: 9px 12px !important;
        border-radius: 4px;
        border-left: 3px solid transparent;
        transition: all 0.15s;
    }
    section[data-testid="stSidebar"] [role="radiogroup"] > label:hover {
        background: rgba(255,255,255,0.14);
        border-left-color: var(--saffron);
    }
    section[data-testid="stSidebar"] [role="radiogroup"] > label[data-checked="true"],
    section[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
        background: rgba(255, 153, 51, 0.25) !important;
        border-left-color: var(--saffron) !important;
        font-weight: 700;
    }

    /* Sidebar chakra wheel */
    .chakra {
        text-align: center; font-size: 1.6rem; opacity: 0.7;
        margin: 4px 0 2px 0; letter-spacing: 0.3em;
    }
    .sidebar-title {
        text-align: center;
        padding: 6px 0;
        border-top: 1px solid rgba(255,255,255,0.12);
        border-bottom: 1px solid rgba(255,255,255,0.12);
        margin: 6px 0 14px 0;
    }
    .sidebar-title .platform {
        font-size: 1.2rem; font-weight: 700; letter-spacing: 0.02em;
    }
    .sidebar-title .sub {
        font-size: 0.7rem; opacity: 0.85; letter-spacing: 0.12em; text-transform: uppercase;
    }

    /* ── Buttons ──────────────────────────────────────────────────────────── */
    .stButton > button {
        background: #fff;
        color: var(--gov-navy);
        border: 1px solid var(--gov-navy);
        border-radius: 3px;
        padding: 6px 16px;
        font-weight: 600;
        transition: all 0.15s;
    }
    .stButton > button:hover {
        background: var(--gov-navy);
        color: #fff;
        border-color: var(--gov-navy);
    }
    .stButton > button[kind="primary"], .stButton > button[data-testid="baseButton-primary"] {
        background: var(--saffron) !important;
        color: #fff !important;
        border-color: var(--saffron-deep) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--saffron-deep) !important;
    }
    .stFormSubmitButton > button {
        background: var(--saffron) !important;
        color: #fff !important;
        border: 1px solid var(--saffron-deep) !important;
        font-weight: 700;
    }

    /* ── Inputs / forms ───────────────────────────────────────────────────── */
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    [data-baseweb="select"] > div {
        border-radius: 3px !important;
        border-color: var(--rule) !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus,
    [data-baseweb="select"] > div:focus-within {
        border-color: var(--gov-navy) !important;
        box-shadow: 0 0 0 2px rgba(11, 61, 145, 0.15) !important;
    }

    /* ── Expanders / cards ────────────────────────────────────────────────── */
    [data-testid="stExpander"] {
        background: #fff;
        border: 1px solid var(--rule);
        border-radius: 4px;
        margin-bottom: 10px;
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        background: var(--surface-2);
        font-weight: 600;
        color: var(--gov-navy-dark);
        padding: 10px 14px !important;
    }
    [data-testid="stExpander"] summary:hover { background: #E7E1D2; }

    /* ── Tabs ─────────────────────────────────────────────────────────────── */
    .stTabs [role="tablist"] {
        gap: 2px; border-bottom: 2px solid var(--saffron);
    }
    .stTabs [role="tab"] {
        background: var(--surface-2);
        border-radius: 4px 4px 0 0 !important;
        padding: 8px 18px !important;
        font-weight: 600;
        color: var(--gov-navy);
        border: none !important;
    }
    .stTabs [role="tab"][aria-selected="true"] {
        background: var(--gov-navy) !important;
        color: #fff !important;
    }

    /* ── Dataframes ───────────────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--rule);
        border-radius: 4px;
    }

    /* ── Alerts ───────────────────────────────────────────────────────────── */
    [data-testid="stAlert"] {
        border-radius: 4px;
        border-left-width: 4px !important;
    }

    /* ── Cards (custom) ───────────────────────────────────────────────────── */
    .gov-card {
        background: #fff;
        border: 1px solid var(--rule);
        border-left: 4px solid var(--gov-navy);
        border-radius: 4px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .gov-card.saffron { border-left-color: var(--saffron); }
    .gov-card.green   { border-left-color: var(--india-green); }

    /* Help banners (toggleable) */
    .help-banner {
        background: linear-gradient(90deg, #FFF8E7 0%, #FEF3E0 100%);
        border-left: 4px solid var(--saffron);
        padding: 12px 16px;
        border-radius: 0 4px 4px 0;
        margin: 8px 0 16px 0;
        color: #5C3A11;
        font-size: 0.88rem;
        line-height: 1.5;
    }
    .help-banner b { color: var(--saffron-deep); }
    .help-banner .help-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: var(--saffron-deep);
        margin-bottom: 4px;
        display: block;
    }
    .help-banner ul { margin: 4px 0 0 16px; padding: 0; }
    .help-banner li { margin: 2px 0; }
    .help-banner code {
        background: rgba(255,153,51,0.18);
        padding: 1px 5px;
        border-radius: 3px;
        font-size: 0.83em;
        color: var(--saffron-deep);
    }

    /* Inline info icon (for use in markdown) */
    .info-icon {
        display: inline-block;
        width: 16px; height: 16px;
        background: var(--gov-navy);
        color: #fff !important;
        border-radius: 50%;
        text-align: center;
        font-size: 11px;
        font-weight: 700;
        line-height: 16px;
        cursor: help;
        margin-left: 4px;
        vertical-align: middle;
    }
    .info-icon:hover { background: var(--saffron); }

    /* Footer */
    .gov-footer {
        margin-top: 32px; padding: 16px 0;
        border-top: 2px solid var(--saffron);
        color: var(--ink-muted);
        font-size: 0.78rem;
        text-align: center;
    }

    /* Hide Streamlit chrome */
    #MainMenu, footer, [data-testid="stHeader"] { visibility: hidden; height: 0; }
    [data-testid="stToolbar"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Government banner (rendered at top of every page) ────────────────────────
def render_banner():
    today_str = datetime.now().strftime("%a, %d %b %Y")
    st.markdown(f"""
    <div class="gov-banner">
        <div class="crest">☸</div>
        <div class="titles">
            <div class="gov-name">सत्यमेव जयते &nbsp;·&nbsp; Government of Karnataka</div>
            <div class="platform">Unified Business Identifier Platform</div>
            <div class="dept">Department of Commerce &amp; Industries · Active Business Intelligence System</div>
        </div>
        <div class="meta">
            <b>Date:</b> {today_str}<br>
            <b>Build:</b> Round-2 prototype<br>
            <b>Endpoint:</b> {API_BASE}
        </div>
    </div>
    <div class="tricolor">
        <div class="saffron"></div>
        <div class="white"></div>
        <div class="green"></div>
    </div>
    """, unsafe_allow_html=True)


def render_footer():
    st.markdown("""
    <div class="gov-footer">
        Government of Karnataka · Department of Commerce &amp; Industries ·
        Unified Business Identifier &amp; Active Business Intelligence Platform<br>
        <span style="opacity: 0.7;">For official use within authorised review workflows.
        Every linkage decision is auditable, reversible, and reviewer-attributed.</span>
    </div>
    """, unsafe_allow_html=True)


render_banner()


# ── API helpers ───────────────────────────────────────────────────────────────
def api_get(path: str, params: dict | None = None, timeout: int = 30):
    try:
        r = httpx.get(f"{API_BASE}{path}", params=params or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        st.error(f"API error: {e}")
    return None


def api_post(path: str, body: dict | None = None, params: dict | None = None, timeout: int = 60):
    try:
        r = httpx.post(f"{API_BASE}{path}", json=body, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        st.error(f"API error: {e}")
    return None


def verdict_badge(verdict: str | None) -> str:
    v = (verdict or "unknown").lower()
    label = v.replace("_", " ")
    return f'<span class="verdict-badge verdict-{v}">{label}</span>'


# ── Help system ───────────────────────────────────────────────────────────────
def H(text: str) -> str | None:
    """Return tooltip text only if help mode is on. Pass to a widget's `help=`."""
    return text if st.session_state.get("help_mode", True) else None


def help_banner(title: str, body_html: str):
    """Render a saffron-bordered help card at the top of a page (toggleable)."""
    if not st.session_state.get("help_mode", True):
        return
    st.markdown(
        f'<div class="help-banner">'
        f'<span class="help-title">📖 {title}</span>'
        f'{body_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def info_icon(text: str) -> str:
    """Return an inline ⓘ icon with hover tooltip (for use in markdown)."""
    if not st.session_state.get("help_mode", True):
        return ""
    safe = text.replace('"', '&quot;')
    return f'<span class="info-icon" title="{safe}">ⓘ</span>'


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div class="chakra">☸</div>
<div class="sidebar-title">
    <div class="platform">UBID Platform</div>
    <div class="sub">Karnataka C&amp;I</div>
</div>
""", unsafe_allow_html=True)

PAGES = [
    "📊 Dashboard",
    "🔍 Browse UBIDs",
    "📋 Review Queue",
    "🧐 Audit Merges",
    "🧭 UBID Lookup",
    "📈 Activity Status",
    "🚧 Quarantine",
    "📜 Reviewer Log",
    "❓ Query Explorer",
    "📤 Ingest Data",
    "⚙️ Admin",
]

# Programmatic navigation hook: any callback that sets session_state["nav_to"]
# will pre-select the sidebar radio on the next rerun.
if "nav_to" in st.session_state:
    target = st.session_state.pop("nav_to")
    if target in PAGES:
        st.session_state["nav_radio"] = target

page = st.sidebar.radio("Navigation", PAGES, label_visibility="collapsed", key="nav_radio")

st.sidebar.markdown("<hr>", unsafe_allow_html=True)
st.sidebar.markdown("**Reviewer**")
reviewer_id = st.sidebar.text_input("ID", value="reviewer_001", label_visibility="collapsed")
reviewer_tier = st.sidebar.selectbox("Tier", ["junior", "senior"], label_visibility="collapsed")

st.sidebar.markdown("**Reference date** (for activity decay)")
ref_date = st.sidebar.date_input(
    "ref",
    value=date(2025, 5, 1),
    label_visibility="collapsed",
)
ref_date_str = ref_date.isoformat()

st.sidebar.markdown("<hr>", unsafe_allow_html=True)
help_mode = st.sidebar.checkbox(
    "📖 Show help tooltips",
    value=True,
    help="Hide once you're familiar with the UI.",
    key="help_mode",
)

st.sidebar.markdown("<hr>", unsafe_allow_html=True)
health = api_get("/health", timeout=3)
if health and health.get("status") == "ok":
    st.sidebar.markdown(
        f'<div style="color:#86efac;font-size:0.85rem;">● API live</div>'
        f'<div style="font-size:0.7rem;opacity:0.7;">{API_BASE}</div>',
        unsafe_allow_html=True,
    )
else:
    st.sidebar.markdown(
        '<div style="color:#fca5a5;">● API unreachable</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.title("Platform Dashboard")
    st.caption("Real-time view of UBID assignments, source ingest, and reviewer queue")

    help_banner("How to read this page", """
    The five metrics at the top are the platform's health indicators.
    <ul>
      <li><b>UBIDs</b> — number of unique businesses identified across all 4 source systems.</li>
      <li><b>Source records</b> — raw rows ingested from e-Karmika, FBIS, KSPCB, BESCOM.</li>
      <li><b>Review queue</b> — ambiguous matches awaiting reviewer judgement.</li>
      <li><b>Quarantine</b> — activity events that couldn't be joined to any UBID.</li>
    </ul>
    The <b>Verdict distribution</b> donut shows current Active / Dormant / Closed counts.
    The <b>Calibration</b> chart shows how well-calibrated the linkage model is — points should hug the diagonal.
    """)

    stats = api_get("/api/v1/query/stats")
    if not stats:
        st.stop()

    # Top metric row
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("UBIDs", stats.get("total_ubids", 0))
    col2.metric("Source records", stats.get("total_source_records", 0))
    col3.metric("Review queue", stats.get("queue", {}).get("pending", 0))
    col4.metric("Quarantine", stats.get("quarantine", {}).get("unresolved", 0))
    decided = stats.get("queue", {}).get("decided", 0)
    col5.metric("Decisions logged", decided)

    st.markdown("---")
    col_a, col_b = st.columns(2)

    # Verdict distribution donut — flag-coloured
    vd = stats.get("verdict_distribution", {}) or {}
    if vd:
        with col_a:
            st.subheader("Verdict distribution")
            colors = {
                "active": "#138808",            # India green
                "dormant": "#FF9933",           # saffron
                "closed": "#991B1B",            # deep red
                "closed_by_silence": "#C53030", # softer red
                "nascent": "#0B3D91",           # gov navy
            }
            fig = go.Figure(go.Pie(
                labels=[k.replace("_", " ") for k in vd.keys()],
                values=list(vd.values()),
                hole=0.55,
                marker_colors=[colors.get(k, "#94a3b8") for k in vd.keys()],
                textinfo="label+percent",
                textposition="outside",
                marker_line=dict(color="#FFFFFF", width=2),
            ))
            fig.update_layout(
                height=380,
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False,
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
                font=dict(color="#1A1A1A", size=12),
            )
            st.plotly_chart(fig, use_container_width=True, key="dash_verdict_pie")
    else:
        col_a.info("No verdicts computed yet — visit Admin → Refresh verdicts.")

    # Records by source bar
    by_source = stats.get("records_by_source", {}) or {}
    if by_source:
        with col_b:
            st.subheader("Source coverage")
            sorted_sources = sorted(by_source.items(), key=lambda x: x[1], reverse=True)
            fig = go.Figure(go.Bar(
                x=[s[1] for s in sorted_sources],
                y=[s[0] for s in sorted_sources],
                orientation="h",
                marker_color="#0B3D91",  # gov navy
                marker_line=dict(color="#FF9933", width=2),
                text=[s[1] for s in sorted_sources],
                textposition="outside",
                textfont=dict(color="#0B3D91", size=12),
            ))
            fig.update_layout(
                height=380,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="records",
                yaxis_title=None,
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FAF7F2",
                font=dict(color="#1A1A1A"),
            )
            st.plotly_chart(fig, use_container_width=True, key="dash_source_bar")

    st.markdown("---")

    # Calibration reliability strip
    st.subheader("Model calibration")
    cal_data = api_get("/api/v1/admin/calibration-report", params={"n_bins": 10})
    if cal_data and cal_data.get("reliability_diagram"):
        m = cal_data.get("metrics_at_0_95") or {}
        cm1, cm2, cm3, cm4 = st.columns(4)
        cm1.metric("Precision @ 0.95", f"{m.get('precision', 0):.3f}")
        cm2.metric("Recall @ 0.95", f"{m.get('recall', 0):.3f}")
        cm3.metric("Brier", f"{m.get('brier', 0):.4f}")
        cm4.metric("ECE", f"{m.get('ece', 0):.4f}",
                   delta="well-calibrated" if cal_data.get("is_well_calibrated") else "drifting")

        # Reliability diagram
        bins = [b for b in cal_data["reliability_diagram"] if b.get("avg_predicted") is not None]
        if bins:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=[0, 1], y=[0, 1],
                mode="lines",
                line=dict(dash="dash", color="#138808", width=2),  # India green
                name="ideal",
            ))
            fig.add_trace(go.Scatter(
                x=[b["avg_predicted"] for b in bins],
                y=[b["observed"] for b in bins],
                mode="markers+lines",
                line=dict(color="#0B3D91", width=3),  # gov navy
                marker=dict(
                    size=[max(10, min(34, b["n"] / 50)) for b in bins],
                    color="#FF9933",  # saffron
                    line=dict(color="#0B3D91", width=2),
                    opacity=0.9,
                ),
                name="model",
                hovertemplate="predicted=%{x:.3f}<br>observed=%{y:.3f}<extra></extra>",
            ))
            fig.update_layout(
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="Predicted probability",
                yaxis_title="Observed positive rate",
                xaxis=dict(range=[0, 1], gridcolor="#E5E5E5"),
                yaxis=dict(range=[0, 1], gridcolor="#E5E5E5"),
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FAF7F2",
                font=dict(color="#1A1A1A"),
            )
            st.plotly_chart(fig, use_container_width=True, key="dash_reliability")


# ═════════════════════════════════════════════════════════════════════════════
# BROWSE UBIDs
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Browse UBIDs":
    st.title("Browse UBIDs")
    st.caption("Every UBID in the system, filterable and paginated")

    help_banner("How to use this page", """
    A UBID is a Unified Business Identifier — one ID per real-world business, linking together every record from every department system that refers to it.
    <ul>
      <li>Use the <b>Filters</b> to narrow down (verdict, source mix, pin, district, name).</li>
      <li>Each row shows the verdict badge, continuity score, record count, and contributing sources.</li>
      <li>Click <code>Open</code> on any row to jump straight to its <b>Activity Status</b> page with full evidence.</li>
      <li>Use <code>⬇ Download all matching UBIDs as CSV</code> to export the filtered result.</li>
    </ul>
    """)

    with st.expander("Filters", expanded=True):
        f1, f2, f3 = st.columns(3)
        verdict_filter = f1.selectbox("Verdict",
            ["", "active", "dormant", "closed", "closed_by_silence", "nascent"])
        source_filter = f2.selectbox("Contains source",
            ["", "ekarmika", "fbis", "kspcb", "bescom"])
        min_records = f3.number_input("Min source records", min_value=1, value=1)

        f4, f5, f6 = st.columns(3)
        pin_filter = f4.text_input("Pin code")
        district_filter = f5.text_input("District")
        search = f6.text_input("Name search")

    page_size = 20
    pg = st.session_state.get("ubid_page", 0)

    params = {
        "limit": page_size,
        "offset": pg * page_size,
        "min_records": int(min_records),
    }
    if verdict_filter: params["verdict"] = verdict_filter
    if source_filter: params["source_system"] = source_filter
    if pin_filter: params["pin_code"] = pin_filter
    if district_filter: params["district"] = district_filter
    if search: params["search"] = search

    data = api_get("/api/v1/ubid", params=params)
    if not data:
        st.stop()

    total = data.get("total", 0)
    results = data.get("results", [])

    # Summary + pagination controls
    st.markdown(f"**{total}** UBIDs match — showing **{len(results)}** "
                f"(page {pg + 1} of {max(1, (total + page_size - 1) // page_size)})")

    pp1, pp2, pp3 = st.columns([1, 1, 6])
    if pp1.button("← Prev", disabled=(pg == 0)):
        st.session_state.ubid_page = max(0, pg - 1)
        st.rerun()
    if pp2.button("Next →", disabled=((pg + 1) * page_size >= total)):
        st.session_state.ubid_page = pg + 1
        st.rerun()

    # Table
    if results:
        df = pd.DataFrame([
            {
                "UBID": r["ubid"][:8] + "…",
                "Verdict": r["verdict"],
                "Score": round(r["continuity_score"], 3),
                "Records": r["record_count"],
                "Sources": ", ".join(r.get("sources") or []),
                "Pin": r.get("pin_code") or "—",
                "District": r.get("district") or "—",
                "Sample name": (r.get("sample_name") or "")[:40],
                "_full": r["ubid"],
            }
            for r in results
        ])

        # CSV export — fetch ALL matches, not just current page
        all_params = {**params, "limit": min(total, 5000), "offset": 0}
        full_data = api_get("/api/v1/ubid", params=all_params)
        if full_data and full_data.get("results"):
            export_df = pd.DataFrame(full_data["results"])
            csv_bytes = export_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇ Download all matching UBIDs as CSV",
                data=csv_bytes,
                file_name=f"ubids_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                key="dl_browse_ubids",
            )
        # Render as table with action button per row via expander
        for _, row in df.iterrows():
            with st.container():
                c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1.5, 1, 1, 2.5, 2, 1.5])
                c1.markdown(f"`{row['UBID']}`")
                c2.markdown(verdict_badge(row["Verdict"]), unsafe_allow_html=True)
                c3.markdown(f"**{row['Score']}**")
                c4.markdown(f"{row['Records']}×")
                c5.markdown(f"<small>{row['Sources']}</small>", unsafe_allow_html=True)
                c6.markdown(f"<small>{row['Sample name']}</small>", unsafe_allow_html=True)
                if c7.button("Open", key=f"open_{row['_full']}"):
                    st.session_state["selected_ubid"] = row["_full"]
                    st.session_state["nav_to"] = "📈 Activity Status"
                    st.rerun()
                st.markdown("<hr style='margin: 4px 0; border: 0; border-top: 1px solid #e5e7eb;'>",
                            unsafe_allow_html=True)
    else:
        st.info("No UBIDs match those filters.")


# ═════════════════════════════════════════════════════════════════════════════
# REVIEW QUEUE
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📋 Review Queue":
    st.title("Review Queue")
    badge = f'<span class="tier-{reviewer_tier}">{reviewer_tier} reviewer</span>'
    st.markdown(f"Logged in as **{reviewer_id}** {badge}", unsafe_allow_html=True)

    help_banner("How to use this page", """
    These are <b>ambiguous match candidates</b> — pairs the model isn't confident enough to auto-link, but not unconfident enough to reject. Your job is to decide.
    <ul>
      <li>The <b>SHAP chart</b> shows which features pushed the score up (green) or down (red).</li>
      <li><b>✅ Confirm match</b> — write a permanent must-link constraint and merge the two UBIDs.</li>
      <li><b>❌ Reject</b> — write a cannot-link constraint; if they were already merged, split them apart.</li>
      <li><b>⏫ Defer</b> — escalate to a senior reviewer (boosts queue priority).</li>
      <li><b>🚩 Flag</b> — mark for data-quality review (source record looks corrupt).</li>
    </ul>
    The <b>Bulk actions</b> section lets you confirm everything above a probability threshold in one click — useful for rapid triage.
    """)

    data = api_get("/api/v1/review/queue", params={"limit": 15, "reviewer_tier": reviewer_tier})
    if not data:
        st.stop()

    qs = data.get("stats", {})
    col1, col2, col3 = st.columns(3)
    col1.metric("Pending", qs.get("pending", 0))
    col2.metric("Decided", qs.get("decided", 0))
    col3.metric("Total queued", qs.get("total", 0))

    items = data.get("items", [])
    if not items:
        st.success("Queue is empty — all caught up!")
        st.stop()

    # ── Bulk actions ──────────────────────────────────────────────────────────
    st.markdown("### Bulk actions")
    bcol1, bcol2 = st.columns([3, 2])
    bulk_threshold = bcol1.slider(
        "Auto-confirm all items with calibrated probability ≥",
        0.55, 1.0, 0.92, 0.01,
        help="Submits confirm_match for every item in the visible queue at or above this threshold.",
    )
    qualifying = [i for i in items if i.get("calibrated_probability", 0) >= bulk_threshold]
    bcol2.metric("Items qualifying", len(qualifying))

    bbtn1, bbtn2, _ = st.columns([1, 1, 3])
    if bbtn1.button(f"✅ Confirm all {len(qualifying)} above {bulk_threshold:.2f}",
                     disabled=(len(qualifying) == 0), key="bulk_confirm"):
        ok = 0
        for it in qualifying:
            ra = it.get("record_a") or {}
            rb = it.get("record_b") or {}
            resp = api_post("/api/v1/review/decide", {
                "queue_id": it.get("queue_id"),
                "pair_id": it["pair_id"],
                "canonical_id_a": ra.get("canonical_id", ""),
                "canonical_id_b": rb.get("canonical_id", ""),
                "decision": "confirm_match",
                "reviewer_id": reviewer_id,
                "reviewer_tier": reviewer_tier,
                "notes": f"bulk auto-confirm at >= {bulk_threshold:.2f}",
            })
            if resp:
                ok += 1
        st.success(f"✓ {ok} pairs confirmed in bulk")
        st.rerun()

    if bbtn2.button("❌ Reject visible queue", key="bulk_reject"):
        st.session_state["confirm_bulk_reject"] = True

    if st.session_state.get("confirm_bulk_reject"):
        st.warning("Are you sure? This will reject every currently-visible item.")
        cc1, cc2 = st.columns(2)
        if cc1.button("Yes, reject all", type="primary", key="confirm_yes"):
            ok = 0
            for it in items:
                ra = it.get("record_a") or {}
                rb = it.get("record_b") or {}
                resp = api_post("/api/v1/review/decide", {
                    "queue_id": it.get("queue_id"),
                    "pair_id": it["pair_id"],
                    "canonical_id_a": ra.get("canonical_id", ""),
                    "canonical_id_b": rb.get("canonical_id", ""),
                    "decision": "reject",
                    "reviewer_id": reviewer_id,
                    "reviewer_tier": reviewer_tier,
                    "notes": "bulk reject",
                })
                if resp:
                    ok += 1
            st.session_state.pop("confirm_bulk_reject")
            st.success(f"✓ {ok} pairs rejected")
            st.rerun()
        if cc2.button("Cancel", key="confirm_no"):
            st.session_state.pop("confirm_bulk_reject")
            st.rerun()

    st.markdown(f"### Top {len(items)} items by priority")

    for item in items:
        prob = item.get("calibrated_probability", 0)
        priority = item.get("priority_score", 0)
        rec_a = item.get("record_a") or {}
        rec_b = item.get("record_b") or {}
        title_pri = "🔥" if priority > 0.85 else "⭐" if priority > 0.7 else "•"

        with st.expander(
            f"{title_pri} priority {priority:.3f}  ·  p={prob:.3f}  ·  "
            f"{rec_a.get('source_system','?')}/{rec_a.get('source_record_id','?')[:14]}  ⇄  "
            f"{rec_b.get('source_system','?')}/{rec_b.get('source_record_id','?')[:14]}",
            expanded=(priority > 0.85),
        ):
            col_a, col_b = st.columns(2)

            for col, rec, label in [(col_a, rec_a, "A"), (col_b, rec_b, "B")]:
                with col:
                    st.markdown(f"**Record {label}** · `{rec.get('source_system')}` · `{rec.get('source_record_id')}`")
                    st.markdown(f"**Name:** {rec.get('name_raw', '—')}")
                    st.markdown(f"**Address:** {rec.get('address_raw', '—')[:120]}")
                    badge_pin = f"📍 {rec.get('pin_code')}" if rec.get("pin_code") else "—"
                    badge_pan = f"🆔 {rec.get('pan')}" if rec.get("pan") else "no PAN"
                    badge_phone = f"☎ {rec.get('phone')}" if rec.get("phone") else "no phone"
                    st.caption(f"{badge_pin}  ·  {badge_pan}  ·  {badge_phone}")
                    if rec.get("sector_raw"):
                        st.caption(f"sector: {rec['sector_raw']}")

            # SHAP feature contributions
            shap = item.get("shap_contributions") or {}
            if shap:
                top = sorted(shap.items(), key=lambda x: abs(x[1]), reverse=True)[:8]
                fig = go.Figure(go.Bar(
                    x=[v for _, v in top],
                    y=[k for k, _ in top],
                    orientation="h",
                    marker_color=["#138808" if v > 0 else "#991B1B" for _, v in top],
                    marker_line=dict(color="#0B3D91", width=1),
                    text=[f"{v:+.3f}" for _, v in top],
                    textposition="auto",
                ))
                fig.update_layout(
                    height=260, margin=dict(l=0, r=0, t=10, b=0),
                    title_text="Feature contributions (SHAP)",
                    title_font_size=14,
                    title_font_color="#0B3D91",
                    showlegend=False,
                    xaxis_title="contribution to logit",
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FAF7F2",
                    font=dict(color="#1A1A1A"),
                )
                st.plotly_chart(fig, use_container_width=True, key=f"shap_{item['pair_id']}")

            shared = item.get("shared_blocks") or []
            if shared:
                st.info(f"Shared blocking keys: {', '.join(shared)}")
            if item.get("deterministic_tier_fired"):
                st.warning("Deterministic tier fired (PAN equality or hard non-match)")

            # Decision buttons
            queue_id = item.get("queue_id")
            pair_id = item["pair_id"]
            id_a = rec_a.get("canonical_id", "")
            id_b = rec_b.get("canonical_id", "")

            cols = st.columns(4)

            def submit(decision: str):
                resp = api_post("/api/v1/review/decide", {
                    "queue_id": queue_id, "pair_id": pair_id,
                    "canonical_id_a": id_a, "canonical_id_b": id_b,
                    "decision": decision,
                    "reviewer_id": reviewer_id,
                    "reviewer_tier": reviewer_tier,
                })
                if resp:
                    st.success(f"✓ {decision} recorded — UBID layer updated")
                    st.rerun()

            if cols[0].button("✅ Confirm match", key=f"m_{pair_id}", use_container_width=True):
                submit("confirm_match")
            if cols[1].button("❌ Reject", key=f"r_{pair_id}", use_container_width=True):
                submit("reject")
            if cols[2].button("⏫ Defer to senior", key=f"d_{pair_id}",
                              disabled=(reviewer_tier == "senior"), use_container_width=True):
                submit("defer")
            if cols[3].button("🚩 Flag quality", key=f"f_{pair_id}", use_container_width=True):
                submit("flag_quality")


# ═════════════════════════════════════════════════════════════════════════════
# AUDIT MERGES
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🧐 Audit Merges":
    st.title("Audit merge decisions")
    st.caption("Walk through every multi-record UBID one at a time. Decide whether the model "
               "grouped these records correctly. Approving writes a permanent must-link "
               "constraint; flagging an issue lets you peel the wrong record off into its own UBID.")

    help_banner("How to audit a merge", """
    The model has <i>already</i> auto-linked these records into one UBID. Your job is to verify it was correct.
    <ol>
      <li>Look at the <b>record cards</b> — do all of them appear to be the same business? Compare names, PANs, addresses.</li>
      <li>Check the <b>"Why these were grouped" table</b> — for each pair, you can see the model's calibrated probability and the top SHAP features that contributed.</li>
      <li><b>✅ Approve all merges</b> — locks in the cluster with permanent must-link constraints. Future re-clusterings can never split these records apart.</li>
      <li><b>⚠️ Issue — split off</b> — pick a record that doesn't belong; it gets peeled into a new UBID with a permanent cannot-link constraint.</li>
      <li><b>⏭️ Skip</b> — come back later. The UBID stays in the "Pending" filter.</li>
    </ol>
    Approved UBIDs disappear from the Pending filter so you always know what's left to review.
    """)

    # ── Filters ───────────────────────────────────────────────────────────────
    with st.expander("Filters", expanded=True):
        f1, f2, f3 = st.columns(3)
        audit_pick = f1.radio(
            "Status",
            ["Pending", "Approved", "All"],
            horizontal=True,
        )
        size_pick = f2.selectbox(
            "Cluster size",
            ["Any (≥2)", "Exactly 2", "3", "4", "5+"],
        )
        source_pick = f3.selectbox(
            "Contains source",
            ["", "ekarmika", "fbis", "kspcb", "bescom"],
        )

    audit_param = {"Pending": "pending", "Approved": "approved", "All": None}[audit_pick]

    # Fetch a batch of UBIDs matching the filters (one at a time UX)
    list_params = {"limit": 100, "offset": 0, "min_records": 2}
    if audit_param:
        list_params["audit_status"] = audit_param
    if source_pick:
        list_params["source_system"] = source_pick

    udata = api_get("/api/v1/ubid", params=list_params)
    if not udata:
        st.stop()

    candidates = udata.get("results", [])

    # Apply size filter client-side
    def size_ok(rc: int) -> bool:
        if size_pick == "Any (≥2)": return rc >= 2
        if size_pick == "Exactly 2": return rc == 2
        if size_pick == "3": return rc == 3
        if size_pick == "4": return rc == 4
        if size_pick == "5+": return rc >= 5
        return True
    candidates = [c for c in candidates if size_ok(c["record_count"])]

    if not candidates:
        st.success("No UBIDs match these filters — pending audits cleared!")
        st.stop()

    # ── Counter + navigation ─────────────────────────────────────────────────
    idx = st.session_state.get("audit_idx", 0)
    if idx >= len(candidates):
        idx = 0
    current = candidates[idx]

    nc1, nc2, nc3, nc4, nc5 = st.columns([1, 1, 3, 1, 1])
    nc1.metric("Position", f"{idx + 1} / {len(candidates)}")
    nc2.metric("Total matching", udata.get("total", len(candidates)))
    nc3.markdown(
        f"<div style='text-align:center; padding-top:14px;'>"
        f"<b>UBID</b> <code>{current['ubid'][:13]}…</code> · "
        f"<b>{current['record_count']}</b> records · "
        f"verdict {verdict_badge(current['verdict'])} · "
        f"<b>audit:</b> "
        f"{'✅ approved' if current.get('audit_status') == 'approved' else '⏳ pending'}"
        f"</div>",
        unsafe_allow_html=True,
    )
    if nc4.button("← Prev", disabled=(idx == 0)):
        st.session_state.audit_idx = max(0, idx - 1)
        st.rerun()
    if nc5.button("Next →", disabled=(idx + 1 >= len(candidates))):
        st.session_state.audit_idx = idx + 1
        st.rerun()

    st.markdown("---")

    # ── Detail of current UBID ────────────────────────────────────────────────
    detail = api_get(f"/api/v1/ubid/{current['ubid']}")
    if not detail:
        st.error("Could not load UBID detail.")
        st.stop()

    members = detail.get("source_records") or []

    st.subheader(f"Records in this UBID ({len(members)})")
    cols = st.columns(min(len(members), 4))
    for i, m in enumerate(members):
        with cols[i % len(cols)]:
            st.markdown(f"""
            <div class="gov-card saffron" style="font-size:0.85rem;">
              <b style="color:#0B3D91;">{m['source_system']}</b> /
              <code>{m['source_record_id']}</code>
              <hr style="margin:6px 0; border-top:1px solid #e0e0e0;">
              <div><b>{m.get('name_raw') or '—'}</b></div>
              <div style="color:#5C5C5C; font-size:0.78rem; margin-top:4px;">
                📍 pin {m.get('pin_code') or '—'}<br>
                🆔 PAN {m.get('pan') or '—'}<br>
                ☎ {m.get('phone') or '—'}
              </div>
              <div style="color:#5C5C5C; font-size:0.75rem; margin-top:6px; line-height:1.3;">
                {(m.get('address_raw') or '')[:90]}
              </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Pair-level evidence ───────────────────────────────────────────────────
    st.markdown("### Why these were grouped")
    pe = api_get(f"/api/v1/ubid/{current['ubid']}/pair-evidence")
    if pe and pe.get("pairs"):
        rows = []
        for p in pe["pairs"]:
            con = p.get("constraint")
            con_badge = "—"
            if con == "must_link":
                con_badge = "✅ must-link"
            elif con == "cannot_link":
                con_badge = "❌ cannot-link"
            top_str = " · ".join([f"{f['name']}:{f['contribution']:+.2f}"
                                   for f in (p.get("top_features") or [])[:3]])
            rows.append({
                "Pair": f"{p['record_a_label']}  ↔  {p['record_b_label']}",
                "p (calibrated)": (round(p["calibrated_probability"], 3)
                                    if p["calibrated_probability"] is not None else None),
                "Shared blocks": ", ".join(p.get("shared_blocks") or []) or "—",
                "Top SHAP features": top_str or "—",
                "Constraint": con_badge,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No pair-evidence available (may have been clustered transitively).")

    # ── Decision actions ──────────────────────────────────────────────────────
    st.markdown("### Reviewer decision")

    if current.get("audit_status") == "approved":
        st.success("✅ This UBID has been approved already. All member-pairs carry "
                   "must-link constraints. You can still split a member if the model is wrong.")
    else:
        st.warning("⏳ Pending audit — approve if every record really refers to the same business, "
                   "or split off any wrong record.")

    a1, a2 = st.columns([1, 1])

    with a1:
        notes_approve = st.text_input(
            "Approval note (optional)",
            placeholder="e.g. 'matching PAN, address, sector — all the same business'",
            key=f"approve_notes_{current['ubid']}",
        )
        if st.button("✅ Approve all merges", type="primary", key=f"approve_{current['ubid']}",
                      use_container_width=True):
            resp = api_post("/api/v1/review/approve-ubid", {
                "ubid": current["ubid"],
                "reviewer_id": reviewer_id,
                "reviewer_tier": reviewer_tier,
                "notes": notes_approve or None,
            })
            if resp:
                st.success(
                    f"✓ Approved · {resp.get('decisions_logged', 0)} pair decisions logged · "
                    f"{resp.get('new_constraints', 0)} new must-link constraints written"
                )
                # Auto-advance to next UBID
                st.session_state.audit_idx = min(idx + 1, len(candidates) - 1)
                st.rerun()

    with a2:
        if len(members) >= 2:
            opts = [f"{m['source_system']}/{m['source_record_id']}" for m in members]
            opt_to_id = {opt: m["canonical_id"] for opt, m in zip(opts, members)}

            keep = st.selectbox("Keep on this UBID", opts, key=f"keep_{current['ubid']}")
            split_off_choices = [o for o in opts if o != keep]
            split_off = st.selectbox("Peel off into new UBID",
                                       split_off_choices,
                                       key=f"peel_{current['ubid']}")
            split_notes = st.text_input(
                "Reason (optional)",
                placeholder="e.g. 'different proprietor / wrong PAN'",
                key=f"split_notes_{current['ubid']}",
            )

            if st.button("⚠️ Issue — split this record off",
                           key=f"split_{current['ubid']}",
                           use_container_width=True):
                resp = api_post("/api/v1/review/unmerge", {
                    "canonical_id_a": opt_to_id[keep],
                    "canonical_id_b": opt_to_id[split_off],
                    "reviewer_id": reviewer_id,
                    "reviewer_tier": reviewer_tier,
                    "notes": split_notes or "audit-merge split",
                })
                if resp:
                    st.success(f"✓ Split {split_off} into a new UBID. Cannot-link constraint stored.")
                    st.rerun()

    # Skip button
    if st.button("⏭️ Skip — review later", key=f"skip_{current['ubid']}"):
        st.session_state.audit_idx = min(idx + 1, len(candidates) - 1)
        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# UBID LOOKUP
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🧭 UBID Lookup":
    st.title("UBID Lookup")
    st.caption("Resolve any source-system identifier, PAN, or name+pin to a UBID")

    help_banner("How to use this page", """
    Three ways to find a UBID:
    <ul>
      <li><b>By source ID</b> — paste an e-Karmika number, FBIS licence, KSPCB consent number, or BESCOM RR.</li>
      <li><b>By PAN</b> — the Income Tax PAN of the legal entity (10 chars).</li>
      <li><b>By name + pin</b> — fuzzy match on business name within a pin code.</li>
    </ul>
    The result is a single UBID. Click <b>Open in Activity Status</b> to see the full record list, verdict, and lineage.
    """)

    tab1, tab2, tab3 = st.tabs(["By source ID", "By PAN", "By name + pin"])

    params = None
    with tab1:
        c1, c2 = st.columns(2)
        src = c1.selectbox("Source", ["ekarmika", "fbis", "kspcb", "bescom"], key="lk_src")
        rid = c2.text_input("Record ID", placeholder="SE-180042 / KA/FAC/BNG/00001 / …", key="lk_rid")
        if st.button("Lookup", key="lk1"):
            if rid:
                params = {"source": src, "id": rid}

    with tab2:
        pan = st.text_input("PAN (10 chars)", placeholder="ABCDE1234F", key="lk_pan")
        if st.button("Lookup", key="lk2"):
            if pan:
                params = {"pan": pan}

    with tab3:
        c1, c2 = st.columns(2)
        nm = c1.text_input("Business name", key="lk_nm")
        pn = c2.text_input("Pin code", key="lk_pn")
        if st.button("Lookup", key="lk3"):
            if nm and pn:
                params = {"name": nm, "pin": pn}

    if params:
        result = api_get("/api/v1/lookup", params=params)
        if result:
            ubid = result.get("ubid") or (result.get("ubids") or [None])[0]
            if isinstance(ubid, list):
                ubid = ubid[0] if ubid else None
            if ubid:
                st.success(f"Resolved → UBID `{ubid}`")
                if st.button("Open in Activity Status →"):
                    st.session_state["selected_ubid"] = ubid
                    st.session_state["nav_to"] = "📈 Activity Status"
                    st.rerun()
            with st.expander("Raw response"):
                st.json(result)


# ═════════════════════════════════════════════════════════════════════════════
# ACTIVITY STATUS
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📈 Activity Status":
    st.title("Activity Status")

    help_banner("How to use this page", """
    Everything we know about one UBID — who's linked to it, its verdict, its evidence, and its history.
    <ul>
      <li><b>Verdict</b> &amp; <b>continuity score</b> — Active / Dormant / Closed-by-silence based on cadence-aware decay of activity events.</li>
      <li><b>Linked source records</b> — every department row currently in this UBID.</li>
      <li><b>⚠️ Unmerge a member</b> (under records) — split off a record that was wrongly merged. Picks one to keep on this UBID and another to peel off into a new UBID with a permanent cannot-link constraint.</li>
      <li><b>Evidence timeline</b> — each dot is an activity event; size = magnitude of contribution, colour = positive (green) or negative (red).</li>
      <li><b>UBID lineage &amp; audit trail</b> — chronological log of every link, reviewer decision, and constraint that shaped this cluster.</li>
    </ul>
    Tip: Toggle <code>Force recompute</code> to bypass the verdict cache (useful after a re-ingest).
    """)

    # If we navigated here from another page (e.g. Browse UBIDs "Open"), use
    # that UBID as the default and auto-load. Pop it so a manual page revisit
    # doesn't keep auto-loading the same one.
    default_ubid = st.session_state.pop("selected_ubid", "")
    ubid_input = st.text_input("UBID", value=default_ubid, placeholder="e.g. f131c2a5-811f-4666-…")

    cols = st.columns([1, 1, 4])
    force = cols[0].checkbox("Force recompute")
    use_ref = cols[1].checkbox("Use reference date", value=True)

    auto_loaded = bool(default_ubid)
    submit = auto_loaded or st.button("Get status & detail", type="primary")

    if ubid_input and submit:
        # Detail view (records + verdict from DB)
        detail = api_get(f"/api/v1/ubid/{ubid_input}")
        # Live verdict (recomputes if force=true)
        params = {"force_recompute": force}
        if use_ref:
            params["reference_date"] = ref_date_str
        live = api_get(f"/api/v1/ubid/{ubid_input}/status", params=params)

        if not detail or not live:
            st.stop()

        verdict = live.get("verdict", "unknown")
        if hasattr(verdict, "value"):
            verdict = verdict.value
        verdict = str(verdict).replace("VerdictLabel.", "").lower()
        score = live.get("continuity_score", 0)

        st.markdown(f"### Verdict: {verdict_badge(verdict)} · score `{score:.4f}`",
                    unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Source records", detail.get("record_count", 0))
        m2.metric("Pin", detail.get("pin_code") or "—")
        m3.metric("District", detail.get("district") or "—")
        m4.metric("Sector", (detail.get("sector") or "—")[:18])

        overrides = live.get("deterministic_overrides") or []
        if overrides:
            st.warning("Deterministic override(s): " + " · ".join(overrides))

        st.markdown("---")
        col_left, col_right = st.columns([3, 2])

        # ── Linked source records ─────────────────────────────────────────────
        with col_left:
            st.subheader("Linked source records")
            members = detail.get("source_records") or []
            for r in members:
                with st.container():
                    st.markdown(
                        f"**{r['source_system']}** / `{r['source_record_id']}`  "
                        f"· *{r.get('linked_by','?')}*"
                    )
                    st.caption(
                        f"📛 {r.get('name_raw') or '—'}  ·  "
                        f"🆔 PAN {r.get('pan') or '—'}  ·  "
                        f"📍 pin {r.get('pin_code') or '—'}"
                    )
                    if r.get("address_raw"):
                        st.caption(r["address_raw"][:140])

            # ── Unmerge / split UBID ─────────────────────────────────────────
            if len(members) >= 2:
                st.markdown("---")
                st.markdown("##### ⚠️ Unmerge a member")
                st.caption("If a record was merged into this UBID by mistake, "
                           "split it off into its own UBID. This writes a permanent "
                           "cannot-link constraint that future ingestions will respect.")

                # Two-record selector
                opts = [
                    f"{r['source_system']}/{r['source_record_id']} · {(r.get('name_raw') or '')[:30]}"
                    for r in members
                ]
                opt_to_id = {opt: r["canonical_id"] for opt, r in zip(opts, members)}

                u_col1, u_col2 = st.columns(2)
                pick_a = u_col1.selectbox("Record A (stays on current UBID)", opts, key="unmerge_a")
                pick_b = u_col2.selectbox("Record B (peels off to a new UBID)",
                                           [o for o in opts if o != pick_a], key="unmerge_b")

                u_notes = st.text_input("Reason (optional, recorded in audit log)",
                                         key="unmerge_notes",
                                         placeholder="e.g. 'different proprietor' / 'shared pin only'")

                if st.button("🔓 Split (unmerge B from this UBID)", key="do_unmerge"):
                    resp = api_post("/api/v1/review/unmerge", {
                        "canonical_id_a": opt_to_id[pick_a],
                        "canonical_id_b": opt_to_id[pick_b],
                        "reviewer_id": reviewer_id,
                        "reviewer_tier": reviewer_tier,
                        "notes": u_notes or None,
                    })
                    if resp:
                        st.success(
                            f"✓ split UBID {resp['previous_shared_ubid'][:8]}… — "
                            f"record B peeled into a new UBID. "
                            "Refresh status to see the updated lineage."
                        )
                        st.rerun()

        # ── Evidence timeline chart ───────────────────────────────────────────
        with col_right:
            timeline = live.get("evidence_timeline") or []
            if timeline:
                st.subheader("Evidence timeline (decayed)")
                df = pd.DataFrame(timeline)
                df["event_date"] = pd.to_datetime(df["event_date"])
                df["contribution_signed"] = df["decayed_contribution"] * df["sign"]
                df = df.sort_values("event_date")
                # Custom diverging tricolor scale: red → white → green
                fig = go.Figure(go.Scatter(
                    x=df["event_date"],
                    y=df["contribution_signed"],
                    mode="markers",
                    marker=dict(
                        size=df["contribution_signed"].abs() * 30 + 8,
                        color=df["contribution_signed"],
                        colorscale=[[0, "#991B1B"], [0.5, "#FAF7F2"], [1, "#138808"]],
                        cmin=-1, cmax=1,
                        line=dict(color="#0B3D91", width=1.5),
                        showscale=False,
                    ),
                    text=df["event_type"],
                    hovertemplate="%{text}<br>%{x|%Y-%m-%d}<br>contribution=%{y:.4f}<extra></extra>",
                ))
                fig.update_layout(
                    height=420,
                    margin=dict(l=20, r=20, t=20, b=20),
                    yaxis_title="Decayed contribution",
                    xaxis_title=None,
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FAF7F2",
                    font=dict(color="#1A1A1A"),
                    xaxis=dict(gridcolor="#E5E5E5"),
                    yaxis=dict(gridcolor="#E5E5E5"),
                )
                fig.add_hline(y=0, line_dash="dot", line_color="#0B3D91", line_width=1.5)
                st.plotly_chart(fig, use_container_width=True, key="activity_timeline")

        # ── Full event log ────────────────────────────────────────────────────
        if timeline:
            with st.expander(f"Full evidence log ({len(timeline)} events)"):
                df_show = pd.DataFrame(timeline)[
                    ["event_date", "event_type", "source_system", "weight", "sign",
                     "days_ago", "decayed_contribution"]
                ]
                st.dataframe(df_show, use_container_width=True, height=400)
                csv_bytes = df_show.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇ Download evidence as CSV",
                    data=csv_bytes,
                    file_name=f"evidence_{ubid_input[:8]}.csv",
                    mime="text/csv",
                    key="dl_evidence",
                )

        # ── Audit trail ───────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("UBID lineage & audit trail")
        audit = api_get(f"/api/v1/ubid/{ubid_input}/audit")
        if audit:
            ac1, ac2, ac3 = st.columns(3)
            ac1.metric("Members", audit.get("current_member_count", 0))
            ac2.metric("Reviewer decisions", audit.get("decision_count", 0))
            ac3.metric("Constraints", audit.get("constraint_count", 0))

            # Timeline visualisation
            tl = audit.get("timeline") or []
            if tl:
                kind_colors = {
                    "link": "#138808",        # green
                    "decision": "#0B3D91",    # navy
                    "constraint": "#FF9933",  # saffron
                }
                tl_df = pd.DataFrame(tl)
                tl_df["ts_dt"] = pd.to_datetime(tl_df["ts"], errors="coerce")

                for evt in tl[:25]:
                    color = kind_colors.get(evt["kind"], "#5C5C5C")
                    icon = {"link": "🔗", "decision": "⚖", "constraint": "📌"}.get(evt["kind"], "•")
                    st.markdown(
                        f"""<div style="border-left: 3px solid {color};
                                       padding: 6px 12px; margin: 4px 0;
                                       background: #FFFFFF; border-radius: 0 4px 4px 0;
                                       font-size: 0.88rem;">
                          <span style="color: {color}; font-weight: 700;">{icon} {evt['kind'].upper()}</span>
                          &nbsp;·&nbsp;
                          <span style="color: #5C5C5C;">{evt['ts'][:19]}</span>
                          &nbsp;·&nbsp;
                          <span style="color: #1A1A1A;">{evt['summary']}</span>
                          <br>
                          <small style="color: #5C5C5C;">by {evt.get('actor','?')}</small>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                if len(tl) > 25:
                    st.caption(f"Showing 25 of {len(tl)} timeline events.")


# ═════════════════════════════════════════════════════════════════════════════
# QUARANTINE
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🚧 Quarantine":
    st.title("Quarantine queue")
    st.caption("Activity events that could not be joined to a UBID. Each event keeps its source identifier and is replayed when the linkage table updates.")

    help_banner("How to use this page", """
    Events arrive keyed by department-system identifiers. If we haven't seen the matching source record yet (or its UBID assignment changes), the event lands here.
    <ul>
      <li><b>⟳ Retry all</b> — re-checks the linkage table for every unresolved event. Run after a fresh ingestion or re-cluster.</li>
      <li><b>Retry this event</b> — try a single event again.</li>
      <li><b>Filters</b> let you switch between unresolved and resolved events.</li>
    </ul>
    Events stay here forever until either resolved or a senior reviewer purges them — we never silently drop activity data.
    """)

    filter_state = st.radio(
        "Status",
        ["Unresolved", "Resolved", "All"],
        horizontal=True,
        label_visibility="collapsed",
    )
    state_param = {"Unresolved": "no", "Resolved": "yes", "All": "all"}[filter_state]

    page_size = 25
    pg = st.session_state.get("quarantine_page", 0)
    qdata = api_get("/api/v1/events/quarantine", params={
        "resolved": state_param, "limit": page_size, "offset": pg * page_size,
    })
    if not qdata:
        st.stop()

    total = qdata.get("total", 0)
    items = qdata.get("items", [])

    m1, m2, m3 = st.columns(3)
    m1.metric(f"Quarantined ({filter_state.lower()})", total)
    m2.metric("Showing", f"{len(items)}")
    m3.metric("Page", f"{pg + 1} / {max(1, (total + page_size - 1) // page_size)}")

    # Action bar
    ab1, ab2, ab3, ab4 = st.columns([1, 1, 1, 5])
    if ab1.button("⟳ Retry all", type="primary"):
        with st.spinner("Re-checking linkage table…"):
            resp = api_post("/api/v1/events/quarantine/retry-all")
        if resp:
            st.success(
                f"Attempted {resp.get('source_records_attempted', 0)} source records — "
                f"resolved {resp.get('events_resolved', 0)} events"
            )
            st.rerun()
    if ab2.button("← Prev", disabled=(pg == 0)):
        st.session_state.quarantine_page = max(0, pg - 1)
        st.rerun()
    if ab3.button("Next →", disabled=((pg + 1) * page_size >= total)):
        st.session_state.quarantine_page = pg + 1
        st.rerun()

    if not items:
        st.success("Nothing here.")
    else:
        df = pd.DataFrame(items)
        # CSV export
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇ Download as CSV",
            data=csv_bytes,
            file_name=f"quarantine_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            key="dl_quarantine",
        )

        # Card list
        for it in items:
            badge_color = "#138808" if it["resolved"] else "#FF9933"
            badge_text = "RESOLVED" if it["resolved"] else "UNRESOLVED"
            with st.container():
                st.markdown(f"""
                <div class="gov-card saffron" style="border-left-color: {badge_color};">
                  <div style="display:flex; justify-content: space-between; align-items: center;">
                    <div>
                      <span style="color:#0B3D91; font-weight:700; font-size:0.95rem;">
                        {it['source_system']} / {it['source_record_id']}
                      </span>
                      &nbsp;·&nbsp;
                      <span style="color:#1A1A1A;">{it['event_type']}</span>
                      &nbsp;·&nbsp;
                      <span style="color:#5C5C5C; font-size:0.85rem;">{it['event_date']}</span>
                    </div>
                    <span style="background:{badge_color}; color:#fff; padding:3px 10px;
                                 border-radius:3px; font-size:0.72rem; font-weight:700;
                                 letter-spacing:0.05em;">{badge_text}</span>
                  </div>
                  <div style="color:#5C5C5C; font-size:0.82rem; margin-top:6px;">
                    {it['reason']}  ·
                    quarantined {it['quarantined_at'][:19]}  ·
                    retried {it['retry_count']}×
                    {'· resolved → ' + (it.get('resolved_ubid') or '')[:8] + '…' if it.get('resolved_ubid') else ''}
                  </div>
                </div>
                """, unsafe_allow_html=True)
                if not it["resolved"]:
                    if st.button(f"Retry this event", key=f"retry_{it['event_id']}"):
                        resp = api_post(f"/api/v1/events/quarantine/{it['event_id']}/retry")
                        if resp:
                            st.success(f"Resolved {resp.get('resolved_count_for_record', 0)} events for this source record")
                            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# REVIEWER LOG
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📜 Reviewer Log":
    st.title("Reviewer activity log")
    st.caption("Every reviewer decision, when it happened, and who made it.")

    help_banner("How to use this page", """
    Audit-trail of every reviewer decision. Useful for:
    <ul>
      <li>Verifying that a particular pair was decided by an authorised reviewer.</li>
      <li>Spotting reviewers who consistently confirm (or reject) — possible bias indicators.</li>
      <li>Exporting decision history for compliance / inter-departmental audits.</li>
    </ul>
    Filter by reviewer ID to see one person's history. The leaderboard shows total decisions per reviewer broken down by type.
    """)

    filt_col1, filt_col2 = st.columns([2, 5])
    filter_reviewer = filt_col1.text_input("Filter by reviewer ID (blank = all)")

    params = {"limit": 100, "offset": 0}
    if filter_reviewer:
        params["reviewer_id"] = filter_reviewer

    log = api_get("/api/v1/review/activity", params=params)
    if not log:
        st.stop()

    by_reviewer = log.get("by_reviewer") or {}

    # Per-reviewer summary
    if by_reviewer:
        st.subheader("Reviewer leaderboard")
        rows = []
        for rid, info in by_reviewer.items():
            rows.append({
                "Reviewer": rid,
                "Tier": info["tier"],
                "Total decisions": info["total"],
                **{k: v for k, v in info["counts"].items()},
            })
        ldf = pd.DataFrame(rows).fillna(0)
        st.dataframe(ldf, use_container_width=True, hide_index=True)

        # Bar chart
        if rows:
            fig = go.Figure()
            categories = list({k for r in rows for k in r if k not in ("Reviewer", "Tier", "Total decisions")})
            cat_color = {
                "confirm_match": "#138808",
                "reject": "#991B1B",
                "defer": "#FF9933",
                "flag_quality": "#0B3D91",
            }
            for cat in categories:
                fig.add_trace(go.Bar(
                    name=cat,
                    x=[r["Reviewer"] for r in rows],
                    y=[r.get(cat, 0) for r in rows],
                    marker_color=cat_color.get(cat, "#5C5C5C"),
                ))
            fig.update_layout(
                barmode="stack", height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor="#FFFFFF", plot_bgcolor="#FAF7F2",
                font=dict(color="#1A1A1A"),
                yaxis_title="decisions",
            )
            st.plotly_chart(fig, use_container_width=True, key="reviewer_leaderboard")

    st.markdown("---")
    st.subheader(f"Recent decisions ({log.get('total', 0)} total)")

    items = log.get("items") or []
    if items:
        df = pd.DataFrame([
            {
                "When": (i["decided_at"] or "")[:19],
                "Reviewer": i["reviewer_id"],
                "Tier": i["reviewer_tier"],
                "Decision": i["decision"],
                "p": round(i["calibrated_probability"] or 0, 3),
                "A": f"{i['record_a']['source_system']}/{i['record_a']['source_record_id']}",
                "B": f"{i['record_b']['source_system']}/{i['record_b']['source_record_id']}",
                "Name A": (i["record_a"].get("name_raw") or "")[:25],
                "Name B": (i["record_b"].get("name_raw") or "")[:25],
            }
            for i in items
        ])

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇ Download log as CSV",
            data=csv_bytes,
            file_name=f"reviewer_log_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            key="dl_reviewer_log",
        )

        st.dataframe(df, use_container_width=True, hide_index=True, height=460)
    else:
        st.info("No reviewer decisions yet.")


# ═════════════════════════════════════════════════════════════════════════════
# QUERY EXPLORER
# ═════════════════════════════════════════════════════════════════════════════
elif page == "❓ Query Explorer":
    st.title("Query Explorer")
    st.caption("The proposal's exemplar: *active factories in pin X with no inspection in last N months*")

    help_banner("How to use this page", """
    Run analytical queries over the UBID-keyed data warehouse — questions Karnataka C&amp;I cannot answer today.
    <ul>
      <li>Pick a <b>Verdict</b> (active, dormant, …).</li>
      <li>Optionally restrict by <b>pin code</b>, <b>district</b>, or <b>sector keyword</b>.</li>
      <li>The <b>"No event of type"</b> + <b>"in last N days"</b> filters surface UBIDs that haven't seen a particular kind of event recently — the exemplar query.</li>
    </ul>
    Click <code>Run query</code>. Results are exportable as CSV.
    """)

    with st.form("qf"):
        col1, col2 = st.columns(2)
        verdict = col1.selectbox("Verdict", ["active", "dormant", "closed", "nascent"])
        source = col1.selectbox("Source filter", ["", "ekarmika", "fbis", "kspcb", "bescom"])
        pin = col2.text_input("Pin code")
        district = col2.text_input("District")
        sector = st.text_input("Sector keyword (e.g. factory, textile)")

        c1, c2, c3 = st.columns(3)
        no_evt = c1.selectbox("No event of type",
            ["", "fac_inspection", "fac_form20_annual", "kspcb_compliance_report",
             "bescom_bill_paid", "se_renewal_pre2019"])
        no_days = c2.number_input("In last N days", min_value=0, value=540)
        limit = c3.slider("Limit", 10, 500, 50)

        run = st.form_submit_button("Run query", type="primary")

    if run:
        body = {
            "verdict": verdict,
            "pin_code": pin or None,
            "district": district or None,
            "sector_keyword": sector or None,
            "source_system": source or None,
            "no_event_type": no_evt or None,
            "no_event_since_days": int(no_days) if no_evt and no_days else None,
            "limit": int(limit),
            "offset": 0,
        }
        result = api_post("/api/v1/query/active-businesses", body)
        if result:
            st.success(f"Found **{result.get('total', 0)}** matching UBIDs")
            rows = result.get("results") or []
            if rows:
                df = pd.DataFrame(rows)
                df["ubid_short"] = df["ubid"].str[:8] + "…"
                cols_order = ["ubid_short", "verdict", "continuity_score", "pin_code",
                              "district", "sector", "source_record_count"]
                show = df[[c for c in cols_order if c in df.columns]]
                st.dataframe(show, use_container_width=True)

                # CSV export — include the full ubid column (not the truncated one)
                csv_bytes = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇ Download results as CSV",
                    data=csv_bytes,
                    file_name=f"query_results_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    key="dl_query",
                )

                with st.expander("Raw payload"):
                    st.json(result)


# ═════════════════════════════════════════════════════════════════════════════
# INGEST DATA
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📤 Ingest Data":
    st.title("Ingest Data")
    st.caption("Upload a CSV from any of the four department systems, or send activity events")

    help_banner("How to use this page", """
    Loads new source records or activity events through the live pipeline (canonicalize → block → score → cluster → assign UBID).
    <ul>
      <li>Pick the <b>source system</b> matching the CSV format (e-Karmika / FBIS / KSPCB / BESCOM).</li>
      <li>Drop a CSV — the response shows accepted records, auto-linked pairs, and review-queue items.</li>
      <li>For <b>activity events</b>, paste JSONL or upload a <code>.jsonl</code> file. Each event is joined to its UBID and appended to the warehouse.</li>
    </ul>
    """)

    src = st.selectbox("Source system", ["ekarmika", "fbis", "kspcb", "bescom"])
    uploaded = st.file_uploader("CSV file", type="csv")
    if uploaded is not None and st.button("Upload & ingest", type="primary"):
        with st.spinner("Ingesting…"):
            files = {"file": (uploaded.name, uploaded.getvalue(), "text/csv")}
            try:
                r = httpx.post(
                    f"{API_BASE}/api/v1/ingest/{src}/upload",
                    files=files,
                    timeout=600,
                )
                r.raise_for_status()
                resp = r.json()
                st.success("Ingest complete")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Accepted", resp.get("accepted", 0))
                m2.metric("Auto-linked", resp.get("auto_linked", 0))
                m3.metric("To review", resp.get("review_queued", 0))
                m4.metric("New UBIDs", resp.get("new_ubids", 0))
            except Exception as e:
                st.error(f"Ingest failed: {e}")

    st.markdown("---")
    st.subheader("Activity events")
    st.caption("Paste JSONL (one JSON event per line) or upload a `.jsonl` file")

    evt_file = st.file_uploader("Events JSONL", type=["jsonl", "json"], key="evt_file")
    evt_text = st.text_area("…or paste JSONL here", height=120)

    if st.button("Send events", type="secondary"):
        import json
        events = []
        if evt_file is not None:
            for line in evt_file.getvalue().decode("utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        if evt_text.strip():
            for line in evt_text.splitlines():
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        if not events:
            st.warning("No events parsed from input.")
        else:
            with st.spinner(f"Sending {len(events)} events…"):
                resp = api_post("/api/v1/events", {"events": events})
                if resp:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Accepted", resp.get("accepted", 0))
                    m2.metric("Joined", resp.get("joined", 0))
                    m3.metric("Quarantined", resp.get("quarantined", 0))
                    m4.metric("Errors", resp.get("errors", 0))


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN
# ═════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Admin":
    st.title("Admin")
    st.caption("Operational levers: model retraining, calibration, locality dictionary, verdicts")

    help_banner("How to use this page", """
    <ul>
      <li><b>Retrain model</b> — rebuilds LightGBM from accumulated reviewer labels (+ optional ground-truth seed). Reports A/B before/after metrics so you can verify the new model is at least as good as the old.</li>
      <li><b>Calibration</b> — reliability diagram + Brier score + ECE. A well-calibrated model has predicted probabilities that match observed positive rates.</li>
      <li><b>Locality synonyms</b> — when a reviewer notices two locality strings refer to the same place, add a synonym entry. The "apply" option also re-canonicalises existing records.</li>
      <li><b>Verdicts</b> — recompute Active/Dormant/Closed for every UBID using the current event warehouse and reference date.</li>
    </ul>
    """)

    a1, a2, a3, a4 = st.tabs(["Retrain model", "Calibration", "Locality synonyms", "Verdicts"])

    # ── Retrain ───────────────────────────────────────────────────────────────
    with a1:
        st.subheader("Retrain LightGBM scorer")
        st.caption("Rebuilds the model from the latest reviewer-confirmed labels "
                   "(plus optional ground-truth seeding) and reports A/B metrics.")

        c1, c2 = st.columns(2)
        include_gt = c1.checkbox("Include ground-truth seed", value=True)
        min_labels = c2.number_input("Minimum reviewer labels required", min_value=0, value=0)

        if st.button("Trigger retrain", type="primary"):
            with st.spinner("Training…"):
                resp = api_post("/api/v1/admin/retrain", {
                    "include_ground_truth": include_gt,
                    "min_reviewer_labels": int(min_labels),
                })
            if resp:
                st.success(f"✓ trained in {resp.get('duration_seconds')}s")
                st.markdown("**Reviewer labels:** "
                            f"{resp.get('n_reviewer_labels')}  ·  "
                            f"**Ground-truth pairs:** {resp.get('n_ground_truth_pairs')}  ·  "
                            f"**Total:** {resp.get('n_total_pairs')}")

                pre, post = resp.get("pre_train") or {}, resp.get("post_train") or {}
                cols = st.columns(2)
                cols[0].markdown("##### Pre-train")
                cols[0].metric("F1 @ 0.95", f"{pre.get('f1', 0):.3f}")
                cols[0].metric("Brier", f"{pre.get('brier', 0):.4f}")
                cols[0].metric("ECE", f"{pre.get('ece', 0):.4f}")

                cols[1].markdown("##### Post-train")
                cols[1].metric("F1 @ 0.95", f"{post.get('f1', 0):.3f}",
                               delta=f"{post.get('f1', 0) - pre.get('f1', 0):+.3f}")
                cols[1].metric("Brier", f"{post.get('brier', 0):.4f}",
                               delta=f"{post.get('brier', 0) - pre.get('brier', 0):+.4f}",
                               delta_color="inverse")
                cols[1].metric("ECE", f"{post.get('ece', 0):.4f}",
                               delta=f"{post.get('ece', 0) - pre.get('ece', 0):+.4f}",
                               delta_color="inverse")

    # ── Calibration ───────────────────────────────────────────────────────────
    with a2:
        st.subheader("Reliability diagram")
        n_bins = st.slider("Bins", 5, 20, 10)
        if st.button("Refresh report"):
            cal = api_get("/api/v1/admin/calibration-report", params={"n_bins": n_bins})
            if cal:
                m = cal.get("metrics_at_0_95") or {}
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("Pairs evaluated", cal.get("n_pairs", 0))
                r2.metric("Brier", f"{m.get('brier', 0):.4f}")
                r3.metric("ECE", f"{m.get('ece', 0):.4f}")
                r4.metric("Calibrated", "✓ yes" if cal.get("is_well_calibrated") else "✗ drift")

                bins = [b for b in (cal.get("reliability_diagram") or []) if b.get("avg_predicted") is not None]
                if bins:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                                              line=dict(dash="dash", color="#138808", width=2),
                                              name="ideal"))
                    fig.add_trace(go.Scatter(
                        x=[b["avg_predicted"] for b in bins],
                        y=[b["observed"] for b in bins],
                        mode="markers+lines",
                        marker=dict(size=[max(10, min(34, b["n"] / 50)) for b in bins],
                                    color="#FF9933",
                                    line=dict(color="#0B3D91", width=2),
                                    opacity=0.9),
                        line=dict(color="#0B3D91", width=3),
                        name="model",
                    ))
                    fig.update_layout(height=420, margin=dict(l=20, r=20, t=10, b=20),
                                      xaxis_title="predicted prob",
                                      yaxis_title="observed positive rate",
                                      xaxis=dict(range=[0, 1], gridcolor="#E5E5E5"),
                                      yaxis=dict(range=[0, 1], gridcolor="#E5E5E5"),
                                      paper_bgcolor="#FFFFFF",
                                      plot_bgcolor="#FAF7F2",
                                      font=dict(color="#1A1A1A"))
                    st.plotly_chart(fig, use_container_width=True, key="admin_reliability")

                with st.expander("Bucket details"):
                    st.dataframe(pd.DataFrame(cal.get("reliability_diagram") or []),
                                 use_container_width=True)

    # ── Locality synonyms ─────────────────────────────────────────────────────
    with a3:
        st.subheader("Add / apply locality synonym")
        c1, c2 = st.columns(2)
        variant = c1.text_input("Variant string (what appears in source data)",
                                placeholder="e.g. Bommasandra Indl")
        canonical = c2.text_input("Canonical form (what we want it to map to)",
                                  placeholder="e.g. bommasandra industrial area")
        also_recanonicalise = st.checkbox("Re-canonicalise existing records that contain this variant", value=True)
        if st.button("Add synonym", type="primary"):
            if not variant or not canonical:
                st.warning("Both fields required.")
            else:
                if also_recanonicalise:
                    resp = api_post("/api/v1/admin/synonyms/apply", {
                        "variant": variant, "canonical": canonical,
                        "reviewer_id": reviewer_id,
                    })
                else:
                    resp = api_post("/api/v1/review/synonyms", {
                        "variant": variant, "canonical": canonical,
                        "reviewer_id": reviewer_id,
                    })
                if resp:
                    st.success(f"Added: {resp}")

    # ── Verdicts ──────────────────────────────────────────────────────────────
    with a4:
        st.subheader("Refresh all activity verdicts")
        st.caption("Recomputes the verdict for every UBID using the current event "
                   "warehouse and the reference date set in the sidebar.")
        if st.button("Refresh all verdicts", type="primary"):
            with st.spinner("Recomputing verdicts…"):
                resp = api_post("/api/v1/admin/verdicts/refresh",
                                params={"reference_date": ref_date_str})
            if resp:
                st.success(f"✓ {resp.get('ubids_processed')} UBIDs processed "
                           f"({resp.get('failed', 0)} failures)")
                vd = resp.get("verdict_distribution") or {}
                if vd:
                    fig = go.Figure(go.Bar(
                        x=list(vd.keys()),
                        y=list(vd.values()),
                        marker_color=["#138808" if k == "active" else
                                      "#FF9933" if k == "dormant" else
                                      "#0B3D91" if k == "nascent" else
                                      "#991B1B" for k in vd.keys()],
                        marker_line=dict(color="#0B3D91", width=1.5),
                        text=list(vd.values()),
                        textposition="outside",
                        textfont=dict(color="#0B3D91"),
                    ))
                    fig.update_layout(height=300, margin=dict(l=20, r=20, t=10, b=20),
                                      xaxis_title=None, yaxis_title="count",
                                      paper_bgcolor="#FFFFFF",
                                      plot_bgcolor="#FAF7F2",
                                      font=dict(color="#1A1A1A"))
                    st.plotly_chart(fig, use_container_width=True, key="admin_verdict_dist")


# ═════════════════════════════════════════════════════════════════════════════
# Government footer
# ═════════════════════════════════════════════════════════════════════════════
render_footer()
