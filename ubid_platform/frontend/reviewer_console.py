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
import plotly.io as pio
import streamlit as st

# ── Plotly: high-contrast default template (slate-700 axis text on white) ────
# Set this once globally so every chart inherits readable axis/tick colours.
pio.templates["ubid"] = pio.templates["plotly_white"]
_t = pio.templates["ubid"]
_t.layout.font = dict(color="#334155", family="'Inter', sans-serif", size=12)
_t.layout.title.font = dict(color="#0F172A", size=15)
_t.layout.paper_bgcolor = "#FFFFFF"
_t.layout.plot_bgcolor = "#FFFFFF"
_t.layout.xaxis = dict(
    color="#334155",
    tickfont=dict(color="#334155", size=12),
    title_font=dict(color="#0F172A", size=13),
    gridcolor="#E2E8F0",
    zerolinecolor="#CBD5E1",
    linecolor="#CBD5E1",
)
_t.layout.yaxis = dict(
    color="#334155",
    tickfont=dict(color="#334155", size=12),
    title_font=dict(color="#0F172A", size=13),
    gridcolor="#E2E8F0",
    zerolinecolor="#CBD5E1",
    linecolor="#CBD5E1",
)
_t.layout.legend = dict(
    font=dict(color="#334155"),
    bordercolor="#CBD5E1",
)
pio.templates.default = "ubid"

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UBID Platform | Karnataka Commerce & Industries",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Tricolor / Indian-government theme — REDESIGNED MAY 2026 ──────────────────
# Palette anchored to the Indian flag with WCAG-AAA contrast ratios:
#   Saffron #FF9933 · White #FFFFFF · India Green #15803D
#   Gov navy #1E3A8A · Ashoka navy #1E3A8A · Surface #FFFFFF (pure)
# Text: #0F172A primary / #334155 secondary / #475569 muted (all ≥ 7:1 contrast)
st.markdown("""
<style>
    /* ── Color tokens (high-contrast, flag-themed) ──────────────────────── */
    :root {
        --saffron:        #FF9933;
        --saffron-deep:   #E8731E;
        --india-green:    #15803D;
        --green-deep:     #166534;
        --gov-navy:       #1E3A8A;
        --gov-navy-dark:  #1E2D6E;
        --ashoka:         #1E3A8A;

        --bg:             #FFFFFF;   /* page background, pure white */
        --surface:        #F8FAFC;   /* subtle alt rows / hover */
        --surface-2:      #F1F5F9;   /* deeper alt */
        --ink:            #0F172A;   /* primary text — slate-900 */
        --ink-secondary:  #334155;   /* secondary — slate-700 (≥11:1 on white) */
        --ink-muted:      #475569;   /* muted floor — slate-600 (≥7:1) */
        --rule:           #CBD5E1;   /* primary border — slate-300 */
        --rule-light:     #E2E8F0;   /* subtle border — slate-200 */
        --ring:           rgba(30, 58, 138, 0.18);   /* navy/15% focus ring */
        --shadow-sm:      0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
        --shadow-md:      0 4px 8px rgba(15, 23, 42, 0.08), 0 2px 4px rgba(15, 23, 42, 0.04);
    }

    /* Hide the (now unused) sidebar entirely */
    section[data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        background-color: var(--bg) !important;
        color: var(--ink);
        font-family: 'Inter', 'Source Sans Pro', system-ui, -apple-system, Arial, sans-serif;
    }

    /* Container — full-width header, then content centered */
    .block-container { padding-top: 0.4rem !important; padding-bottom: 3rem; max-width: 1440px; }

    /* ── Top header bar (richer, more government-formal) ─────────────────── */
    .gov-header {
        background:
          radial-gradient(circle at 25% 30%, rgba(255,153,51,0.10) 0%, transparent 40%),
          radial-gradient(circle at 80% 70%, rgba(21,128,61,0.10) 0%, transparent 40%),
          linear-gradient(90deg, #0F1F4F 0%, var(--gov-navy) 50%, #0F1F4F 100%);
        color: #fff;
        padding: 18px 32px;
        margin: -8px -8px 0 -8px;
        display: flex;
        align-items: center;
        gap: 24px;
        box-shadow: 0 6px 18px rgba(15, 31, 79, 0.25);
        border-bottom: 2px solid var(--saffron);
        position: relative;
    }
    .gov-header::before {
        /* Subtle gold/navy braid pattern bottom edge */
        content: "";
        position: absolute;
        left: 0; right: 0; bottom: -2px; height: 2px;
        background: repeating-linear-gradient(
            90deg, var(--saffron) 0 8px, var(--gov-navy) 8px 16px
        );
        opacity: 0.7;
    }
    .gov-header .crest {
        width: 64px; height: 64px;
        flex-shrink: 0;
        filter: drop-shadow(0 2px 6px rgba(0,0,0,0.35));
    }
    .gov-header .crest svg { width: 100%; height: 100%; }
    .gov-header .titles { flex: 1; min-width: 0; }
    .gov-header .gov-tagline {
        font-size: 0.78rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        opacity: 1;
        margin-bottom: 4px;
        font-weight: 600;
        color: #FFFFFF;
    }
    .gov-header .gov-tagline .kannada {
        font-family: 'Noto Serif Kannada', serif;
        font-weight: 500;
        letter-spacing: 0.05em;
        margin-right: 8px;
        color: var(--saffron);
        text-transform: none;
    }
    .gov-header .gov-tagline .gok-en {
        color: #FFFFFF;
        text-transform: uppercase;
    }
    .gov-header .platform {
        font-size: 1.55rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        margin: 0;
        line-height: 1.1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: #fff;
        text-shadow: 0 1px 2px rgba(0,0,0,0.25);
    }
    .gov-header .platform-kn {
        font-size: 0.85rem;
        opacity: 0.85;
        font-weight: 500;
        margin-top: 2px;
        letter-spacing: 0.02em;
    }
    .gov-header .dept {
        font-size: 0.83rem;
        opacity: 0.92;
        font-weight: 400;
        margin-top: 6px;
        padding-top: 6px;
        border-top: 1px solid rgba(255,255,255,0.18);
        max-width: 720px;
    }
    .gov-header .dept b { color: var(--saffron); font-weight: 600; }

    /* ── Force light text inside the header (override the aggressive
         `[data-testid="stMarkdownContainer"] *` dark-text rule below) ─── */
    [data-testid="stMarkdownContainer"] .gov-header,
    [data-testid="stMarkdownContainer"] .gov-header *,
    [data-testid="stMarkdownContainer"] .gov-header p,
    [data-testid="stMarkdownContainer"] .gov-header span,
    [data-testid="stMarkdownContainer"] .gov-header div,
    [data-testid="stMarkdownContainer"] .gov-header b,
    [data-testid="stMarkdownContainer"] .gov-header strong {
        color: inherit !important;
    }
    [data-testid="stMarkdownContainer"] .gov-header .gov-tagline,
    [data-testid="stMarkdownContainer"] .gov-header .gov-tagline .gok-en {
        color: #FFFFFF !important;
    }
    [data-testid="stMarkdownContainer"] .gov-header .gov-tagline .kannada,
    [data-testid="stMarkdownContainer"] .gov-header .dept b {
        color: var(--saffron) !important;
    }
    [data-testid="stMarkdownContainer"] .gov-header .platform {
        color: #FFFFFF !important;
    }
    [data-testid="stMarkdownContainer"] .gov-header .platform-kn,
    [data-testid="stMarkdownContainer"] .gov-header .dept,
    [data-testid="stMarkdownContainer"] .gov-header .dept * {
        color: rgba(255, 255, 255, 0.92) !important;
    }
    /* Tricolor strip is decorative — the inner divs are background only */
    [data-testid="stMarkdownContainer"] .tricolor div {
        color: transparent !important;
    }
    /* Crest image styling */
    .gov-header .crest img {
        width: 100%; height: 100%;
        object-fit: contain;
        border-radius: 50%;
        background: rgba(255,255,255,0.08);
    }
    .gov-header .crest img.real-logo {
        background: #FFFFFF;
        padding: 4px;
    }

    /* Tricolor strip directly under the header */
    .tricolor {
        height: 4px;
        display: flex;
        margin: 0 -8px 0 -8px;
        overflow: hidden;
    }
    .tricolor .saffron { flex: 1; background: var(--saffron); }
    .tricolor .white   { flex: 1; background: #FFFFFF; border-bottom: 1px solid var(--rule-light); }
    .tricolor .green   { flex: 1; background: var(--india-green); }

    /* ── Reviewer-control bar (just under tricolor, before top nav) ─────── */
    .control-bar {
        background: var(--surface);
        margin: 0 -8px 0 -8px;
        padding: 10px 28px 12px 28px;
        display: flex;
        align-items: center;
        gap: 18px;
        border-bottom: 1px solid var(--rule-light);
    }
    .control-bar .label {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--ink-muted);
        margin-bottom: 2px;
    }

    /* ── Pill-style application nav (replaces the radio look) ───────────── */
    [role="radiogroup"][aria-orientation="horizontal"] {
        background: #FFFFFF;
        margin: 0 -8px 0 -8px !important;
        padding: 14px 28px 14px 28px;
        gap: 4px !important;
        overflow-x: auto;
        flex-wrap: nowrap !important;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
        position: relative;
        scrollbar-width: thin;
        scrollbar-color: var(--rule) transparent;
        align-items: center !important;
    }
    /* Saffron rail at the very top of the nav strip (extends from header) */
    [role="radiogroup"][aria-orientation="horizontal"]::before {
        content: "";
        position: absolute;
        left: 0; right: 0; top: 0; height: 1px;
        background: linear-gradient(90deg,
            transparent 0%, rgba(255,153,51,0.4) 30%,
            rgba(255,153,51,0.4) 70%, transparent 100%);
    }
    /* Bottom edge — subtle tricolor underline */
    [role="radiogroup"][aria-orientation="horizontal"]::after {
        content: "";
        position: absolute;
        left: 0; right: 0; bottom: 0; height: 3px;
        background: linear-gradient(
            90deg,
            var(--saffron)      0%,
            var(--saffron)      33.33%,
            #FFFFFF             33.33%,
            #FFFFFF             66.66%,
            var(--india-green)  66.66%,
            var(--india-green)  100%
        );
        pointer-events: none;
    }
    [role="radiogroup"][aria-orientation="horizontal"]::-webkit-scrollbar { height: 6px; }
    [role="radiogroup"][aria-orientation="horizontal"]::-webkit-scrollbar-thumb {
        background: var(--rule); border-radius: 3px;
    }

    /* Each pill tab */
    [role="radiogroup"][aria-orientation="horizontal"] > label {
        background: #F8FAFC !important;
        color: var(--ink-secondary) !important;
        padding: 9px 16px !important;
        margin: 0 !important;
        border-radius: 8px !important;
        border: 1px solid var(--rule-light) !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        white-space: nowrap;
        transition: all 0.16s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        letter-spacing: 0.01em;
        position: relative;
        line-height: 1.2;
        min-height: 36px;
        display: flex !important;
        align-items: center;
    }
    /* Hover: warm saffron-tinted pill */
    [role="radiogroup"][aria-orientation="horizontal"] > label:hover {
        background: #FFF7ED !important;
        color: var(--gov-navy-dark) !important;
        border-color: rgba(255, 153, 51, 0.5) !important;
        transform: translateY(-1px);
        box-shadow: 0 2px 6px rgba(255, 153, 51, 0.12);
    }
    /* Active pill: solid navy with white text and saffron glow ring */
    [role="radiogroup"][aria-orientation="horizontal"] > label[data-checked="true"],
    [role="radiogroup"][aria-orientation="horizontal"] > label:has(input:checked) {
        color: #FFFFFF !important;
        background: linear-gradient(135deg,
            var(--gov-navy) 0%,
            var(--gov-navy-dark) 100%) !important;
        border-color: var(--saffron) !important;
        font-weight: 700 !important;
        box-shadow:
            0 0 0 2px rgba(255, 153, 51, 0.25),
            0 4px 12px rgba(30, 58, 138, 0.30);
        transform: translateY(0);
    }
    /* Pull the active label text colour through nested elements too */
    [role="radiogroup"][aria-orientation="horizontal"] > label:has(input:checked) *,
    [role="radiogroup"][aria-orientation="horizontal"] > label[data-checked="true"] * {
        color: #FFFFFF !important;
    }
    /* Hide the radio dot, render label content cleanly */
    [role="radiogroup"][aria-orientation="horizontal"] > label > div:first-child {
        display: none !important;
    }
    [role="radiogroup"][aria-orientation="horizontal"] > label > div:nth-child(2) {
        display: flex !important;
        align-items: center;
        gap: 6px;
    }

    /* ── Page context strip (under the nav, above content) ──────────────── */
    .page-context {
        background: linear-gradient(90deg,
            #F8FAFC 0%,
            #FFFFFF 50%,
            #F8FAFC 100%);
        margin: 0 -8px 22px -8px;
        padding: 14px 32px 14px 32px;
        border-bottom: 1px solid var(--rule-light);
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .page-context .pc-icon {
        font-size: 1.6rem;
        line-height: 1;
        flex-shrink: 0;
        filter: drop-shadow(0 1px 2px rgba(0,0,0,0.12));
    }
    .page-context .pc-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--gov-navy-dark);
        letter-spacing: -0.01em;
        line-height: 1.2;
    }
    .page-context .pc-subtitle {
        font-size: 0.82rem;
        color: var(--ink-muted);
        font-weight: 500;
        margin-top: 2px;
    }
    .page-context .pc-spacer { flex: 1; }
    .page-context .pc-meta {
        font-size: 0.78rem;
        color: var(--ink-muted);
        font-weight: 500;
        text-align: right;
    }
    .page-context .pc-meta b {
        color: var(--gov-navy);
        font-weight: 700;
    }

    /* ── Typography ─────────────────────────────────────────────────────── */
    h1 {
        color: var(--ink) !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em;
        margin-bottom: 0.3rem !important;
        font-size: 2rem !important;
    }
    h2 {
        color: var(--ink) !important;
        font-weight: 700 !important;
        border-bottom: 2px solid var(--saffron);
        padding-bottom: 0.4rem;
        margin-top: 1.8rem !important;
        font-size: 1.45rem !important;
    }
    h3 {
        color: var(--gov-navy) !important;
        font-weight: 600 !important;
        font-size: 1.15rem !important;
    }
    p, li, label, .stMarkdown { color: var(--ink-secondary) !important; }
    /* Captions need stronger contrast than default */
    [data-testid="stCaptionContainer"], .stCaption,
    [data-testid="stCaptionContainer"] p {
        color: var(--ink-secondary) !important;
        font-size: 0.92rem !important;
    }
    small { color: var(--ink-muted) !important; }
    code {
        background: var(--surface-2);
        color: var(--gov-navy);
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 0.88em;
    }

    /* ── Metric cards (bigger, clearer) ─────────────────────────────────── */
    [data-testid="stMetric"] {
        background: #fff;
        border: 1px solid var(--rule-light);
        border-left: 4px solid var(--saffron);
        padding: 16px 20px 14px 20px;
        border-radius: 8px;
        box-shadow: var(--shadow-sm);
        transition: all 0.15s ease;
    }
    [data-testid="stMetric"]:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-1px);
    }
    [data-testid="stMetricLabel"] {
        font-weight: 700 !important;
        color: var(--gov-navy) !important;
        font-size: 0.74rem !important;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        line-height: 1.2;
    }
    [data-testid="stMetricLabel"] p {
        color: var(--gov-navy) !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        color: var(--ink) !important;
        line-height: 1.1;
        margin-top: 4px;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        color: var(--ink-secondary) !important;
    }
    [data-testid="stMetricDelta"] svg { display: none; }

    /* ── Verdict badges (flag-coloured) ─────────────────────────────────────── */
    .verdict-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 0.74rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: #FFFFFF !important;
        line-height: 1.4;
        white-space: nowrap;
    }
    .verdict-active            { background: var(--india-green); }
    .verdict-dormant           { background: var(--saffron); }
    .verdict-closed            { background: #991B1B; }
    .verdict-closed_by_silence { background: #C53030; }
    .verdict-nascent           { background: var(--gov-navy); }
    .verdict-unknown           { background: var(--ink-muted); }

    /* ── Reviewer tier pills ────────────────────────────────────────────────── */
    .tier-junior, .tier-senior {
        padding: 3px 12px;
        border-radius: 4px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        color: #fff !important;
        text-transform: uppercase;
    }
    .tier-junior { background: var(--saffron); }
    .tier-senior { background: var(--gov-navy); }

    /* ── Buttons ────────────────────────────────────────────────────────── */
    .stButton > button, .stDownloadButton > button {
        background: #fff;
        color: var(--gov-navy);
        border: 1.5px solid var(--gov-navy);
        border-radius: 6px;
        padding: 9px 20px;
        font-weight: 600;
        font-size: 0.92rem;
        height: auto;
        min-height: 42px;
        transition: all 0.15s ease;
        box-shadow: var(--shadow-sm);
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background: var(--gov-navy);
        color: #fff;
        border-color: var(--gov-navy);
        box-shadow: var(--shadow-md);
        transform: translateY(-1px);
    }
    .stButton > button:active { transform: translateY(0); }
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"],
    .stDownloadButton > button[kind="primary"] {
        background: var(--saffron) !important;
        color: #fff !important;
        border-color: var(--saffron-deep) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--saffron-deep) !important;
        border-color: var(--saffron-deep) !important;
    }
    .stButton > button:disabled,
    .stButton > button[disabled] {
        background: var(--surface-2) !important;
        color: var(--ink-muted) !important;
        border-color: var(--rule) !important;
        cursor: not-allowed;
        box-shadow: none !important;
        transform: none !important;
    }
    .stFormSubmitButton > button {
        background: var(--saffron) !important;
        color: #fff !important;
        border: 1.5px solid var(--saffron-deep) !important;
        font-weight: 700 !important;
        min-height: 42px;
    }
    .stFormSubmitButton > button:hover { background: var(--saffron-deep) !important; }

    /* ── Form inputs (high-contrast borders, larger height) ─────────────── */
    .stTextInput label, .stNumberInput label, .stTextArea label,
    .stSelectbox label, .stDateInput label, .stRadio label, .stCheckbox label {
        color: var(--ink) !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
    }
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    [data-baseweb="select"] > div, [data-baseweb="input"] input {
        border-radius: 6px !important;
        border: 1.5px solid var(--rule) !important;
        background: #fff !important;
        color: var(--ink) !important;
        font-size: 0.95rem !important;
    }
    .stTextInput input, .stNumberInput input,
    [data-baseweb="select"] > div, [data-baseweb="input"] input {
        min-height: 42px !important;
    }
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: #94A3B8 !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus,
    .stTextArea textarea:focus,
    [data-baseweb="select"] > div:focus-within {
        border-color: var(--gov-navy) !important;
        box-shadow: 0 0 0 3px var(--ring) !important;
        outline: none !important;
    }

    /* ── Expanders ──────────────────────────────────────────────────────── */
    [data-testid="stExpander"] {
        background: #fff;
        border: 1px solid var(--rule-light);
        border-radius: 8px;
        margin-bottom: 12px;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
    }
    [data-testid="stExpander"] summary {
        background: var(--surface);
        font-weight: 700 !important;
        color: var(--ink) !important;
        padding: 12px 18px !important;
        font-size: 0.95rem !important;
    }
    [data-testid="stExpander"] summary:hover { background: var(--surface-2); }
    [data-testid="stExpander"] summary p { color: var(--ink) !important; }

    /* ── In-page tabs (st.tabs widget) ──────────────────────────────────── */
    .stTabs [role="tablist"] {
        gap: 2px;
        border-bottom: 2px solid var(--saffron);
        background: transparent;
    }
    .stTabs [role="tab"] {
        background: var(--surface) !important;
        border-radius: 6px 6px 0 0 !important;
        padding: 10px 22px !important;
        font-weight: 600 !important;
        color: var(--ink-secondary) !important;
        border: 1px solid var(--rule-light) !important;
        border-bottom: none !important;
    }
    .stTabs [role="tab"]:hover { background: var(--surface-2) !important; }
    .stTabs [role="tab"][aria-selected="true"] {
        background: var(--gov-navy) !important;
        color: #fff !important;
        border-color: var(--gov-navy) !important;
    }
    .stTabs [role="tab"][aria-selected="true"] p { color: #fff !important; }

    /* ── Dataframes (table styling) ─────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--rule-light);
        border-radius: 8px;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
    }
    [data-testid="stDataFrame"] thead tr th {
        background: var(--gov-navy) !important;
        color: #fff !important;
        font-weight: 700 !important;
    }

    /* ── Alerts ─────────────────────────────────────────────────────────── */
    [data-testid="stAlert"] {
        border-radius: 8px;
        border-left-width: 4px !important;
        font-size: 0.92rem;
    }

    /* ── Cards ──────────────────────────────────────────────────────────── */
    .gov-card {
        background: #fff;
        border: 1px solid var(--rule-light);
        border-left: 4px solid var(--gov-navy);
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 12px;
        box-shadow: var(--shadow-sm);
        transition: box-shadow 0.15s ease;
        color: var(--ink);
    }
    .gov-card:hover { box-shadow: var(--shadow-md); }
    .gov-card.saffron { border-left-color: var(--saffron); }
    .gov-card.green   { border-left-color: var(--india-green); }
    .gov-card b, .gov-card strong { color: var(--ink) !important; }

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

    /* ── Tooltip popover (the `?` help-icon hover content) ─────────────── */
    /* The Streamlit `help=...` parameter renders a BaseWeb tooltip — by
       default it has poor contrast. Force navy bg + white text so it's
       always readable. */
    [data-baseweb="tooltip"] {
        background: var(--gov-navy) !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        box-shadow: var(--shadow-md) !important;
        padding: 10px 14px !important;
        max-width: 360px !important;
        font-size: 0.86rem !important;
        line-height: 1.5 !important;
        font-weight: 500 !important;
        z-index: 9999 !important;
    }
    [data-baseweb="tooltip"] *,
    [data-baseweb="tooltip"] p,
    [data-baseweb="tooltip"] span,
    [data-baseweb="tooltip"] div {
        color: #FFFFFF !important;
        background: transparent !important;
    }
    /* Tooltip arrow */
    [data-baseweb="tooltip"] [data-popper-arrow] {
        background: var(--gov-navy) !important;
    }

    /* ── Contrast overrides for Streamlit defaults ──────────────────────── */
    /* Streamlit ships with several rgba(49,51,63,0.4–0.6) light-gray defaults.
       These read poorly on white. Force every "muted" element to at least
       our --ink-muted floor (#475569, 7:1 contrast on white). */
    .stMarkdown small, .stMarkdown small *,
    .stTooltipIcon, .stTooltipIcon *,
    [data-testid="stTooltipIcon"], [data-testid="stTooltipIcon"] *,
    [data-baseweb="form-control-caption"],
    [data-baseweb="form-control-caption"] * {
        color: var(--ink-muted) !important;
    }
    /* Help-icon `?` next to widget labels */
    [data-testid="stTooltipHoverTarget"] svg,
    [data-testid="stTooltipIcon"] svg {
        fill: var(--gov-navy) !important;
        color: var(--gov-navy) !important;
    }
    /* Streamlit's <p>, <li>, <span> in the main content default to slate-700-ish but
       on some elements they fall to lighter — re-assert. */
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span:not(.verdict-badge):not(.tier-junior):not(.tier-senior):not(.info-icon) {
        color: var(--ink) !important;
    }
    /* Bold inside markdown should be ink, not gray */
    [data-testid="stMarkdownContainer"] strong,
    [data-testid="stMarkdownContainer"] b {
        color: var(--ink) !important;
    }
    /* Empty-state placeholders inside text inputs */
    ::placeholder { color: #94A3B8 !important; opacity: 1; }
    /* Glide Data Grid (st.data_editor) cell text — when used, force readable colour.
       (Note: we now mostly avoid data_editor; this is a safety net.) */
    [data-testid="stDataFrame"] canvas { background: #fff !important; }

    /* ── Side-by-side comparison table (custom) ─────────────────────────── */
    table.compare-table {
        width: 100%;
        border-collapse: collapse;
        background: #fff;
        border: 1px solid var(--rule-light);
        border-radius: 8px;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
        font-size: 0.92rem;
    }
    table.compare-table thead th {
        background: var(--gov-navy);
        color: #fff;
        font-weight: 700;
        padding: 10px 14px;
        text-align: left;
        font-size: 0.85rem;
        letter-spacing: 0.04em;
    }
    table.compare-table tbody td {
        padding: 10px 14px;
        border-top: 1px solid var(--rule-light);
        color: var(--ink);
        vertical-align: top;
    }
    table.compare-table tbody td.field-label {
        background: var(--surface);
        color: var(--ink-secondary);
        font-weight: 700;
        width: 110px;
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    table.compare-table tbody tr.match td.value-a,
    table.compare-table tbody tr.match td.value-b {
        background: #ECFDF5;     /* very light green */
        color: #065F46;
        font-weight: 600;
    }
    table.compare-table tbody tr.mismatch td.value-a,
    table.compare-table tbody tr.mismatch td.value-b {
        background: #FEF3C7;     /* very light amber */
        color: #78350F;
        font-weight: 600;
    }
    table.compare-table tbody tr.missing td.value-a,
    table.compare-table tbody tr.missing td.value-b {
        background: #F8FAFC;
        color: var(--ink-muted);
        font-style: italic;
    }
    table.compare-table td.verdict-col { width: 56px; text-align: center; font-size: 1.1rem; }

    /* ── Sortable record row (replaces data_editor) ─────────────────────── */
    .record-row {
        display: grid;
        grid-template-columns: 110px 110px 1.6fr 1fr 110px 130px 200px;
        gap: 12px;
        align-items: center;
        padding: 10px 14px;
        background: #fff;
        border: 1px solid var(--rule-light);
        border-left-width: 4px;
        border-radius: 6px;
        margin-bottom: 6px;
        font-size: 0.9rem;
        color: var(--ink);
        transition: box-shadow 0.12s ease, transform 0.12s ease;
    }
    .record-row:hover { box-shadow: var(--shadow-sm); }
    .record-row .group-pill {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #fff;
        padding: 3px 10px;
        border-radius: 12px;
        text-align: center;
        white-space: nowrap;
    }
    .record-row .src {
        font-weight: 700;
        color: var(--gov-navy);
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .record-row .name { font-weight: 600; }
    .record-row .pan, .record-row .pin {
        font-family: 'Roboto Mono', monospace;
        font-size: 0.85rem;
        color: var(--ink-secondary);
    }
    .record-row .id-cell {
        font-family: 'Roboto Mono', monospace;
        font-size: 0.82rem;
        color: var(--ink-secondary);
        word-break: break-all;
    }

    /* ── BaseWeb dropdown popover (selectbox + date picker open state) ──── */
    /* Fixes the dark-on-grey unreadable dropdown */
    [data-baseweb="popover"] {
        background: #fff !important;
        border: 1px solid var(--rule) !important;
        border-radius: 8px !important;
        box-shadow: var(--shadow-md) !important;
        color: var(--ink) !important;
    }
    [data-baseweb="popover"] [role="listbox"],
    [data-baseweb="popover"] ul[role="listbox"],
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"] {
        background: #fff !important;
        color: var(--ink) !important;
        padding: 4px !important;
    }
    [data-baseweb="popover"] [role="option"],
    [data-baseweb="popover"] li,
    [data-baseweb="menu"] li {
        background: #fff !important;
        color: var(--ink) !important;
        padding: 8px 14px !important;
        border-radius: 4px !important;
        margin: 1px 2px !important;
        font-size: 0.92rem !important;
    }
    [data-baseweb="popover"] [role="option"]:hover,
    [data-baseweb="popover"] li:hover,
    [data-baseweb="menu"] li:hover {
        background: var(--surface-2) !important;
        color: var(--gov-navy) !important;
        cursor: pointer;
    }
    [data-baseweb="popover"] [aria-selected="true"],
    [data-baseweb="popover"] li[aria-selected="true"] {
        background: var(--gov-navy) !important;
        color: #fff !important;
    }
    /* The text inside option items (some Streamlit versions wrap in span) */
    [data-baseweb="popover"] [role="option"] *,
    [data-baseweb="popover"] li * {
        color: inherit !important;
    }
    /* Calendar (date picker) */
    [data-baseweb="calendar"] {
        background: #fff !important;
        color: var(--ink) !important;
        border-radius: 8px !important;
    }
    [data-baseweb="calendar"] * { color: var(--ink) !important; }
    [data-baseweb="calendar"] button {
        background: transparent !important;
        color: var(--ink) !important;
    }
    [data-baseweb="calendar"] button:hover {
        background: var(--surface-2) !important;
    }
    [data-baseweb="calendar"] [aria-selected="true"] {
        background: var(--gov-navy) !important;
        color: #fff !important;
    }

    /* ── Help banners ───────────────────────────────────────────────────── */
    /* (overrides above to bump contrast) */
    .help-banner {
        background: #FFFBEB !important;
        border-left: 4px solid var(--saffron) !important;
        color: #78350F !important;
    }
    .help-banner b, .help-banner strong { color: #78350F !important; }
    .help-banner .help-title { color: var(--saffron-deep) !important; }
    .help-banner code {
        background: rgba(255,153,51,0.18) !important;
        color: var(--saffron-deep) !important;
    }

    /* Footer */
    .gov-footer {
        margin-top: 36px; padding: 18px 0;
        border-top: 3px solid var(--saffron);
        color: var(--ink-secondary);
        font-size: 0.85rem;
        text-align: center;
        line-height: 1.6;
    }
    .gov-footer b, .gov-footer strong { color: var(--ink) !important; }

    /* Hide Streamlit chrome */
    #MainMenu, footer, [data-testid="stHeader"] { visibility: hidden; height: 0; }
    [data-testid="stToolbar"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Top header (gov bar + tricolor + reviewer controls + nav tabs) ───────────
_HEADER_CREST_CACHE: str | None = None


def _load_header_crest() -> str:
    """Look for a real Karnataka logo file in frontend/assets/. If found,
    encode it as a data URI. Otherwise fall back to the hand-drawn SVG.

    Operator drops a file at:
      frontend/assets/karnataka_logo.{svg,png,jpg}    (preferred)
      frontend/assets/logo.{svg,png,jpg}              (generic fallback)
    """
    global _HEADER_CREST_CACHE
    if _HEADER_CREST_CACHE is not None:
        return _HEADER_CREST_CACHE

    import base64
    from pathlib import Path

    asset_dir = Path(__file__).resolve().parent / "assets"
    candidates = [
        ("karnataka_logo.svg", "image/svg+xml"),
        ("karnataka_logo.png", "image/png"),
        ("karnataka_logo.jpg", "image/jpeg"),
        ("karnataka_logo.jpeg", "image/jpeg"),
        ("logo.svg", "image/svg+xml"),
        ("logo.png", "image/png"),
        ("logo.jpg", "image/jpeg"),
    ]
    for name, mime in candidates:
        path = asset_dir / name
        if path.exists() and path.is_file():
            data = path.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            _HEADER_CREST_CACHE = (
                f'<img src="data:{mime};base64,{b64}" '
                f'alt="Karnataka emblem" class="real-logo" />'
            )
            return _HEADER_CREST_CACHE

    # Fallback: hand-drawn Gandaberunda SVG
    crest_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <defs>
    <radialGradient id="discGrad" cx="0.35" cy="0.30" r="0.80">
      <stop offset="0%" stop-color="#FFB870"/>
      <stop offset="60%" stop-color="#FF9933"/>
      <stop offset="100%" stop-color="#D8650F"/>
    </radialGradient>
    <linearGradient id="ringGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#FFD68A"/>
      <stop offset="100%" stop-color="#B47015"/>
    </linearGradient>
  </defs>
  <circle cx="50" cy="50" r="48" fill="url(#ringGrad)"/>
  <circle cx="50" cy="50" r="44" fill="url(#discGrad)"/>
  <circle cx="50" cy="50" r="40" fill="none" stroke="#FFFFFF" stroke-width="0.5" opacity="0.55"/>
  <circle cx="50" cy="6"  r="1.6" fill="#FFFFFF"/>
  <circle cx="50" cy="94" r="1.6" fill="#FFFFFF"/>
  <circle cx="6"  cy="50" r="1.6" fill="#15803D"/>
  <circle cx="94" cy="50" r="1.6" fill="#15803D"/>
  <g fill="#FFFFFF" stroke="#1E3A8A" stroke-width="0.6" stroke-linejoin="round">
    <path d="M40 20 L42 14 L46 19 L50 12 L54 19 L58 14 L60 20 L60 24 L40 24 Z"/>
    <circle cx="50" cy="17" r="1.4" fill="#FF9933" stroke="none"/>
    <path d="M42 26 Q38 27 36 31 Q35 36 38 39 L42 42 L46 38 L46 32 Q46 27 42 26 Z"/>
    <path d="M36 31 L29 33 L36 35 Z" fill="#FF9933" stroke="#1E3A8A"/>
    <circle cx="40" cy="31" r="1.1" fill="#1E3A8A" stroke="none"/>
    <path d="M58 26 Q62 27 64 31 Q65 36 62 39 L58 42 L54 38 L54 32 Q54 27 58 26 Z"/>
    <path d="M64 31 L71 33 L64 35 Z" fill="#FF9933" stroke="#1E3A8A"/>
    <circle cx="60" cy="31" r="1.1" fill="#1E3A8A" stroke="none"/>
    <path d="M44 40 Q42 46 43 56 L46 65 L54 65 L57 56 Q58 46 56 40 L52 38 L48 38 Z"/>
    <path d="M46 46 L50 50 L54 46 L52 54 L48 54 Z" fill="#FF9933" stroke="#1E3A8A" stroke-width="0.4"/>
    <path d="M44 44 Q34 46 26 56 Q22 62 24 66 Q30 64 36 60 Q42 56 46 52 Z"/>
    <path d="M30 58 L36 60 M28 62 L34 63 M32 54 L38 56" stroke="#1E3A8A" stroke-width="0.4" fill="none"/>
    <path d="M56 44 Q66 46 74 56 Q78 62 76 66 Q70 64 64 60 Q58 56 54 52 Z"/>
    <path d="M70 58 L64 60 M72 62 L66 63 M68 54 L62 56" stroke="#1E3A8A" stroke-width="0.4" fill="none"/>
    <path d="M44 64 L42 78 L46 73 L48 80 L50 73 L52 80 L54 73 L58 78 L56 64 Z"/>
    <path d="M48 70 L48 78 M50 70 L50 80 M52 70 L52 78" stroke="#1E3A8A" stroke-width="0.4" fill="none"/>
    <path d="M46 65 L43 70 L46 70 M54 65 L57 70 L54 70" stroke="#1E3A8A" stroke-width="0.6" fill="none"/>
  </g>
</svg>"""

    crest_b64 = base64.b64encode(crest_svg.encode("utf-8")).decode("ascii")
    _HEADER_CREST_CACHE = (
        f'<img src="data:image/svg+xml;base64,{crest_b64}" '
        f'alt="Karnataka emblem (fallback)" class="fallback-logo" />'
    )
    return _HEADER_CREST_CACHE


def render_header():
    """Government banner with the Karnataka emblem (real file from
    frontend/assets/ if present, hand-drawn fallback otherwise)."""
    crest_img = _load_header_crest()

    st.markdown(
        f"""
    <div class="gov-header">
        <div class="crest">{crest_img}</div>
        <div class="titles">
            <div class="gov-tagline">
              <span class="kannada">ಕರ್ನಾಟಕ ಸರ್ಕಾರ</span>
              <span class="gok-en">· Government of Karnataka</span>
            </div>
            <div class="platform">Unified Business Identifier Platform</div>
            <div class="platform-kn">ಏಕೀಕೃತ ವ್ಯಾಪಾರ ಗುರುತಿಸುವಿಕೆ ವೇದಿಕೆ</div>
            <div class="dept">
              <b>Department of Commerce &amp; Industries</b> ·
              Active Business Intelligence System ·
              ವಾಣಿಜ್ಯ ಮತ್ತು ಕೈಗಾರಿಕೆ ಇಲಾಖೆ
            </div>
        </div>
    </div>
    <div class="tricolor">
        <div class="saffron"></div>
        <div class="white"></div>
        <div class="green"></div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_footer():
    st.markdown("""
    <div class="gov-footer">
        <b>Government of Karnataka · Department of Commerce &amp; Industries</b><br>
        Unified Business Identifier &amp; Active Business Intelligence Platform<br>
        <span style="color: var(--ink-muted);">For official use within authorised review workflows.
        Every linkage decision is auditable, reversible, and reviewer-attributed.</span>
    </div>
    """, unsafe_allow_html=True)


render_header()


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


# ── Reviewer-control bar (just under the tricolor) ────────────────────────────
# Pulled out of the sidebar; rendered as a row of compact widgets.
ctrl_cols = st.columns([1.4, 1, 1.2, 0.9, 1.5])
reviewer_id = ctrl_cols[0].text_input(
    "Reviewer ID",
    value=st.session_state.get("reviewer_id", "reviewer_001"),
    key="reviewer_id",
    help=H("Used to attribute every reviewer decision in the audit log."),
)
reviewer_tier = ctrl_cols[1].selectbox(
    "Tier",
    ["junior", "senior"],
    index=["junior", "senior"].index(st.session_state.get("reviewer_tier", "junior")),
    key="reviewer_tier",
    help=H("Senior reviewers see deferred items first; their decisions become precedents."),
)
ref_date = ctrl_cols[2].date_input(
    "Reference date",
    value=date(2025, 5, 1),
    key="ref_date",
    help=H("Treated as 'today' for activity-decay computation. Default 2025-05-01 because synthetic events end April 2025."),
)
ref_date_str = ref_date.isoformat()
help_mode = ctrl_cols[3].checkbox(
    "📖 Help",
    value=True,
    key="help_mode",
    help="Toggle in-page guidance and tooltips on/off.",
)
# API status
health = api_get("/health", timeout=3)
if health and health.get("status") == "ok":
    ctrl_cols[4].markdown(
        f'<div style="padding-top:32px; font-size:0.8rem; color:var(--india-green); font-weight:600;">'
        f'● API live'
        f'</div>'
        f'<div style="font-size:0.7rem; color:var(--ink-muted);">{API_BASE}</div>',
        unsafe_allow_html=True,
    )
else:
    ctrl_cols[4].markdown(
        '<div style="padding-top:32px; color:#991B1B; font-weight:600;">● API unreachable</div>',
        unsafe_allow_html=True,
    )

# ── Top tab navigation ────────────────────────────────────────────────────────
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
    "ℹ️ About",
]

# Programmatic navigation hook: any callback that sets session_state["nav_to"]
# will pre-select the nav radio on the next rerun.
if "nav_to" in st.session_state:
    target = st.session_state.pop("nav_to")
    if target in PAGES:
        st.session_state["nav_radio"] = target

page = st.radio(
    "Navigation",
    PAGES,
    horizontal=True,
    label_visibility="collapsed",
    key="nav_radio",
)


# ── Page-context strip (subtitle + meta below the nav) ───────────────────────
def render_page_context(page_name: str):
    """Render a contextual strip below the nav describing the current page.
    Helps the reviewer orient — what page they're on, what it's for, and one
    relevant live stat."""
    # Map page → (icon, short title, one-line description)
    contexts = {
        "ℹ️ About":         ("ℹ", "About this platform",
                              "How the UBID platform works · architecture · proposal compliance · glossary"),
        "📊 Dashboard":     ("📊", "Platform Dashboard",
                              "Live overview of UBIDs, source records, queue size, and model calibration"),
        "🔍 Browse UBIDs":  ("🔍", "Browse UBIDs",
                              "Search, filter and open every Unified Business Identifier in the system"),
        "📋 Review Queue":  ("📋", "Review Queue",
                              "Ambiguous match candidates awaiting reviewer decision"),
        "🧐 Audit Merges":  ("🧐", "Audit Merge Decisions",
                              "Verify auto-merged UBIDs · sort records into groups · feeds future training"),
        "🧭 UBID Lookup":   ("🧭", "UBID Lookup",
                              "Resolve any source identifier, PAN, or name+pin to a UBID"),
        "📈 Activity Status": ("📈", "Activity Status",
                                "Verdict, evidence timeline, lineage and unmerge controls for one UBID"),
        "🚧 Quarantine":    ("🚧", "Quarantine Queue",
                              "Activity events that could not be joined to a UBID"),
        "📜 Reviewer Log":  ("📜", "Reviewer Activity Log",
                              "Decision history per reviewer · audit trail · throughput chart"),
        "❓ Query Explorer":("❓", "Analytical Query Explorer",
                              "Run the proposal's exemplar queries against the UBID-keyed warehouse"),
        "📤 Ingest Data":   ("📤", "Ingest Data",
                              "Upload CSV records or activity events through the live pipeline"),
        "⚙️ Admin":         ("⚙", "Administration",
                              "Model retraining · re-scoring · calibration · synonyms · verdicts"),
    }
    icon, title, subtitle = contexts.get(
        page_name, ("•", page_name, "")
    )

    # Try to fetch a small live stat (cheap, cached for this render)
    meta_html = ""
    try:
        s = api_get("/api/v1/query/stats", timeout=2) or {}
        n_ubids = s.get("total_ubids", 0)
        n_pending = (s.get("queue") or {}).get("pending", 0)
        meta_html = (
            f'<b>{n_ubids}</b> UBIDs · '
            f'<b>{n_pending}</b> pending review · '
            f'reference date <b>{ref_date_str}</b>'
        )
    except Exception:
        pass

    st.markdown(f"""
    <div class="page-context">
      <div class="pc-icon">{icon}</div>
      <div>
        <div class="pc-title">{title}</div>
        <div class="pc-subtitle">{subtitle}</div>
      </div>
      <div class="pc-spacer"></div>
      <div class="pc-meta">{meta_html}</div>
    </div>
    """, unsafe_allow_html=True)


render_page_context(page)


# ═════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════
# ═════════════════════════════════════════════════════════════════════════════
# ABOUT — How it works
# ═════════════════════════════════════════════════════════════════════════════
if page == "ℹ️ About":
    st.title("Unified Business Identifier Platform")
    st.markdown(
        '<p style="font-size:1.05rem; color:var(--ink-secondary); '
        'line-height:1.6; max-width:880px;">'
        'Karnataka has 40+ State department systems holding business records, '
        'each with its own schema and identifiers. The same business shows up '
        'as <i>different</i> rows in different databases. This platform sits '
        '<b>alongside</b> those systems (no source-system changes), '
        '<b>links</b> matching records across them, and <b>infers</b> whether '
        'each business is currently active, dormant, or closed — with every '
        'decision auditable and reversible.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Live metric strip ──────────────────────────────────────────────────
    stats = api_get("/api/v1/query/stats") or {}
    cal = api_get("/api/v1/admin/calibration-report", params={"n_bins": 10}) or {}
    history = api_get("/api/v1/admin/retrain-history", params={"limit": 1}) or {"runs": []}
    budget = api_get("/api/v1/admin/labels-since-last-retrain") or {}

    cal_metrics = cal.get("metrics_at_0_95") or {}
    last_run = (history.get("runs") or [{}])[0]
    post = last_run.get("post") or {}

    st.markdown("### Platform at a glance")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("UBIDs", stats.get("total_ubids", 0))
    m2.metric("Source records", stats.get("total_source_records", 0))
    m3.metric("Pairwise F1 @ 0.95", f"{cal_metrics.get('f1', 0):.3f}")
    m4.metric("Brier score", f"{cal_metrics.get('brier', 0):.4f}",
                help=H("Lower is better. Below 0.05 = excellent calibration."))

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Reviewer labels", budget.get("total_labels", 0))
    m6.metric("Pending review", stats.get("queue", {}).get("pending", 0))
    m7.metric("Quarantined events", stats.get("quarantine", {}).get("unresolved", 0))
    m8.metric("Last retrain Δ F1",
                f"{(post.get('f1', 0) - (last_run.get('pre') or {}).get('f1', 0)):+.3f}"
                if last_run else "—",
                help=H("Improvement from the most recent retrain on a held-out set."))

    # ── Architecture diagram ───────────────────────────────────────────────
    st.markdown("### How it works")
    st.markdown("""
    <div class="gov-card" style="background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
                                  padding: 18px 24px;">
      <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px;">
        <div style="background:#E0F2FE; border:1px solid #7DD3FC; border-radius:8px;
                    padding:12px; text-align:center; font-size:0.85rem;">
          <div style="font-weight:700; color:#075985;">e-Karmika</div>
          <div style="color:#0C4A6E; font-size:0.75rem;">Shop &amp; Establishment</div>
        </div>
        <div style="background:#E0F2FE; border:1px solid #7DD3FC; border-radius:8px;
                    padding:12px; text-align:center; font-size:0.85rem;">
          <div style="font-weight:700; color:#075985;">FBIS</div>
          <div style="color:#0C4A6E; font-size:0.75rem;">Factories</div>
        </div>
        <div style="background:#E0F2FE; border:1px solid #7DD3FC; border-radius:8px;
                    padding:12px; text-align:center; font-size:0.85rem;">
          <div style="font-weight:700; color:#075985;">KSPCB</div>
          <div style="color:#0C4A6E; font-size:0.75rem;">Pollution consents</div>
        </div>
        <div style="background:#E0F2FE; border:1px solid #7DD3FC; border-radius:8px;
                    padding:12px; text-align:center; font-size:0.85rem;">
          <div style="font-weight:700; color:#075985;">BESCOM</div>
          <div style="color:#0C4A6E; font-size:0.75rem;">Electricity</div>
        </div>
      </div>
      <div style="text-align:center; color:#1E3A8A; font-size:1.4rem; margin: 4px 0;">▼</div>
      <div style="background:#FFF7ED; border-left:4px solid #FF9933; padding:10px 14px;
                  border-radius:0 6px 6px 0; margin-bottom:10px;">
        <b style="color:#9A3412;">1. Canonicalise</b>
        <span style="color:#451A03; font-size:0.88rem;">
          — strip "Pvt Ltd / M/s", normalise addresses, transliterate Kannada,
          extract PAN entity-type, derive PAN from GSTIN.
        </span>
      </div>
      <div style="background:#FFF7ED; border-left:4px solid #FF9933; padding:10px 14px;
                  border-radius:0 6px 6px 0; margin-bottom:10px;">
        <b style="color:#9A3412;">2. Block</b>
        <span style="color:#451A03; font-size:0.88rem;">
          — OpenSearch union-blocking on PAN, derived-PAN, pin+name-prefix,
          pin+door, phone, trigram name-similarity.
        </span>
      </div>
      <div style="background:#FFF7ED; border-left:4px solid #FF9933; padding:10px 14px;
                  border-radius:0 6px 6px 0; margin-bottom:10px;">
        <b style="color:#9A3412;">3. Score</b>
        <span style="color:#451A03; font-size:0.88rem;">
          — LightGBM on 25 hand-crafted features + isotonic calibration. SHAP per pair.
          Two tiers: deterministic (PAN equality) + probabilistic.
        </span>
      </div>
      <div style="background:#FFF7ED; border-left:4px solid #FF9933; padding:10px 14px;
                  border-radius:0 6px 6px 0; margin-bottom:10px;">
        <b style="color:#9A3412;">4. Cluster</b>
        <span style="color:#451A03; font-size:0.88rem;">
          — union-find with reviewer-supplied must-link / cannot-link constraints.
          Each connected component = 1 UBID.
        </span>
      </div>
      <div style="text-align:center; color:#1E3A8A; font-size:1.4rem; margin: 4px 0;">▼</div>
      <div style="background:#ECFDF5; border:2px solid #15803D; border-radius:8px;
                  padding:14px; text-align:center; margin: 8px 0;">
        <div style="font-weight:700; color:#065F46; font-size:1.1rem;">
          UBID  ·  Unified Business Identifier
        </div>
        <div style="color:#065F46; font-size:0.85rem;">
          One ID per real-world business, joining every record across the 4 systems
        </div>
      </div>
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px;">
        <div style="background:#F0FDFA; border:1px solid #5EEAD4; border-radius:8px;
                    padding:12px; font-size:0.85rem;">
          <b style="color:#0F766E;">Activity engine</b><br>
          <span style="color:#134E4A;">
            Cadence-aware decay over BESCOM bills, factory returns,
            KSPCB compliance reports, S&amp;E renewals →
            <b>Active / Dormant / Closed</b> with evidence timeline.
          </span>
        </div>
        <div style="background:#FEF3F2; border:1px solid #FCA5A5; border-radius:8px;
                    padding:12px; font-size:0.85rem;">
          <b style="color:#991B1B;">Reviewer console</b><br>
          <span style="color:#7F1D1D;">
            Ambiguous matches → human review queue.
            Audit Merges → verify auto-linked clusters.
            Every decision becomes a training label for the next retrain.
          </span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Proposal compliance checklist ──────────────────────────────────────
    st.markdown("### Proposal compliance")
    st.markdown("""
    <div class="gov-card" style="border-left-color: #15803D;">
      <table style="width:100%; border-collapse:collapse; font-size:0.92rem;">
        <tr><td style="padding:6px 0; width:30px;">✅</td>
            <td style="padding:6px 0;"><b>No source-system changes</b> — pull-based ingest, every adapter is read-only</td></tr>
        <tr><td style="padding:6px 0;">✅</td>
            <td style="padding:6px 0;"><b>Wrong merge &gt; missed merge</b> — auto-link threshold 0.95, cannot-link constraints persist</td></tr>
        <tr><td style="padding:6px 0;">✅</td>
            <td style="padding:6px 0;"><b>Every decision explainable</b> — SHAP per pair, evidence timeline per verdict, deterministic-tier rules visible</td></tr>
        <tr><td style="padding:6px 0;">✅</td>
            <td style="padding:6px 0;"><b>Every decision reversible</b> — Sorting Mat, Unmerge button, full audit trail per UBID</td></tr>
        <tr><td style="padding:6px 0;">✅</td>
            <td style="padding:6px 0;"><b>No hosted LLMs</b> — LightGBM + rapidfuzz + curated dictionaries, all local</td></tr>
        <tr><td style="padding:6px 0;">✅</td>
            <td style="padding:6px 0;"><b>Synthetic-data safe</b> — model trains on structural features, never memorises</td></tr>
        <tr><td style="padding:6px 0;">✅</td>
            <td style="padding:6px 0;"><b>Human-in-the-loop reviewer workflow</b> — queue, audit, decisions feed retraining</td></tr>
        <tr><td style="padding:6px 0;">✅</td>
            <td style="padding:6px 0;"><b>Calibrated confidence</b> — isotonic regression, ECE = """ + f"{cal_metrics.get('ece', 0):.4f}" + """ on held-out</td></tr>
        <tr><td style="padding:6px 0;">✅</td>
            <td style="padding:6px 0;"><b>Hierarchical UBID model</b> — Legal Entity → UBID (establishment) → Source Records → BESCOM connections</td></tr>
        <tr><td style="padding:6px 0;">✅</td>
            <td style="padding:6px 0;"><b>Quarantine never silently drops events</b> — replayed when linkage updates</td></tr>
      </table>
    </div>
    """, unsafe_allow_html=True)

    # ── Glossary ──────────────────────────────────────────────────────────
    st.markdown("### Glossary")
    glossary = [
        ("UBID", "Unified Business Identifier — one UUID per real-world business establishment, "
                  "joining every record across all 4 source systems."),
        ("PAN", "Permanent Account Number — 10-character ID from the Income Tax Department. "
                  "The 4th character encodes entity type (P=proprietorship, C=company, etc.)."),
        ("GSTIN", "Goods & Services Tax ID — 15 chars: [state:2][PAN:10][entity:1][Z][checksum:1]. "
                   "We extract chars 3–12 to derive the legal-entity PAN."),
        ("Calibrated probability", "After fitting LightGBM, we apply isotonic regression so that "
                                     "a score of 0.85 actually means 85% of pairs scored 0.85 are true matches."),
        ("Brier score", "Mean squared error between predicted probability and the true label. "
                          "Lower is better; below 0.05 is excellent."),
        ("ECE", "Expected Calibration Error — average gap between predicted probability and observed "
                  "match rate across probability buckets. Below 0.05 = well-calibrated."),
        ("B3 metric", "Cluster-level evaluation: per-record, what fraction of fellow cluster-members "
                        "are true co-members (precision) and what fraction of true co-members are in the same "
                        "cluster (recall). F1 of those two."),
        ("Decay", "Activity events lose weight over time. Contribution = w·exp(−Δt / α·τ) where w is the "
                    "event's signal strength, τ is its expected cadence, α controls forgiveness."),
        ("Must-link", "Reviewer-supplied constraint: these two records MUST be in the same UBID. "
                        "Survives future re-clusterings."),
        ("Cannot-link", "Reviewer-supplied constraint: these two records MUST NOT be in the same UBID. "
                          "Persistent."),
        ("Auto-link threshold", "Calibrated probability ≥ 0.95 → records auto-merge into one UBID. "
                                  "Below 0.55 → keep separate. Between → human reviewer decides."),
        ("Sorting Mat", "Audit-merges UI: sort each multi-record UBID into N groups + Solos. Every "
                          "grouping decision becomes a training label."),
    ]
    for term, definition in glossary:
        with st.expander(term):
            st.markdown(
                f'<span style="color:var(--ink-secondary); font-size:0.92rem;">{definition}</span>',
                unsafe_allow_html=True,
            )

    # ── Tech stack ─────────────────────────────────────────────────────────
    st.markdown("### Tech stack")
    st.markdown("""
    <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
      <div class="gov-card" style="border-left-color:#1E3A8A;">
        <b style="color:#1E3A8A;">API</b><br>
        <span style="color:var(--ink-secondary); font-size:0.85rem;">FastAPI + uvicorn</span>
      </div>
      <div class="gov-card" style="border-left-color:#1E3A8A;">
        <b style="color:#1E3A8A;">Database</b><br>
        <span style="color:var(--ink-secondary); font-size:0.85rem;">PostgreSQL 16</span>
      </div>
      <div class="gov-card" style="border-left-color:#1E3A8A;">
        <b style="color:#1E3A8A;">Search / Blocking</b><br>
        <span style="color:var(--ink-secondary); font-size:0.85rem;">OpenSearch 2.16</span>
      </div>
      <div class="gov-card" style="border-left-color:#1E3A8A;">
        <b style="color:#1E3A8A;">Entity graph</b><br>
        <span style="color:var(--ink-secondary); font-size:0.85rem;">Neo4j 5.24</span>
      </div>
      <div class="gov-card" style="border-left-color:#1E3A8A;">
        <b style="color:#1E3A8A;">Cache</b><br>
        <span style="color:var(--ink-secondary); font-size:0.85rem;">Redis 7</span>
      </div>
      <div class="gov-card" style="border-left-color:#1E3A8A;">
        <b style="color:#1E3A8A;">Stream queue</b><br>
        <span style="color:var(--ink-secondary); font-size:0.85rem;">Kafka 7.7 (KRaft)</span>
      </div>
      <div class="gov-card" style="border-left-color:#FF9933;">
        <b style="color:#9A3412;">Event warehouse</b><br>
        <span style="color:var(--ink-secondary); font-size:0.85rem;">DuckDB + Parquet</span>
      </div>
      <div class="gov-card" style="border-left-color:#FF9933;">
        <b style="color:#9A3412;">ML scorer</b><br>
        <span style="color:var(--ink-secondary); font-size:0.85rem;">LightGBM + isotonic calibration</span>
      </div>
      <div class="gov-card" style="border-left-color:#FF9933;">
        <b style="color:#9A3412;">UI</b><br>
        <span style="color:var(--ink-secondary); font-size:0.85rem;">Streamlit + Plotly</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption(
        f"API endpoint: {API_BASE} · "
        f"Backend tested @ B3 F1 = 0.92, pairwise F1 = "
        f"{cal_metrics.get('f1', 0):.3f}, Brier = {cal_metrics.get('brier', 0):.4f}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📊 Dashboard":
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
                font=dict(color="#334155", size=12),
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
                plot_bgcolor="#FFFFFF",
                font=dict(color="#334155"),
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
                xaxis=dict(range=[0, 1], gridcolor="#E2E8F0"),
                yaxis=dict(range=[0, 1], gridcolor="#E2E8F0"),
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
                font=dict(color="#334155"),
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
        help=H("Submits confirm_match for every item in the visible queue at or above this threshold. "
                "Use this when you trust the model on high-confidence pairs and want to clear the queue fast."),
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
                    plot_bgcolor="#FFFFFF",
                    font=dict(color="#334155"),
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

            if cols[0].button("✅ Confirm match", key=f"m_{pair_id}", use_container_width=True,
                              help=H("Writes a must-link constraint and merges the two records into one UBID.")):
                submit("confirm_match")
            if cols[1].button("❌ Reject", key=f"r_{pair_id}", use_container_width=True,
                              help=H("Writes a cannot-link constraint. If the records are already in the same UBID, splits them.")):
                submit("reject")
            if cols[2].button("⏫ Defer to senior", key=f"d_{pair_id}",
                              disabled=(reviewer_tier == "senior"), use_container_width=True,
                              help=H("Boosts the queue priority; senior reviewer sees it first.")):
                submit("defer")
            if cols[3].button("🚩 Flag quality", key=f"f_{pair_id}", use_container_width=True,
                              help=H("Marks one of the source records as suspicious for data-quality review.")):
                submit("flag_quality")


# ═════════════════════════════════════════════════════════════════════════════
# AUDIT MERGES
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🧐 Audit Merges":
    st.title("Audit merge decisions")
    st.caption("Sort the records inside each multi-record UBID into groups. Records in the "
               "same group share one UBID; each record marked `Solo` becomes its own UBID. "
               "Every decision becomes a training label for the next model retrain.")

    help_banner("How to use the Sorting Mat", """
    The model has <i>already</i> auto-linked these records into one UBID. Your job is to verify the grouping — and split it if wrong.
    <ol>
      <li>Look at the records below and decide which ones are actually the same business.</li>
      <li><b>Default</b>: everyone is in <code>Group 1</code>. If you click <b>Apply</b> right now, this is equivalent to "approve the merge as-is".</li>
      <li>If the cluster contains <b>two distinct businesses</b>, click <b>+ Add Group 2</b> at the top, then change the <b>Group</b> column for the records that belong to the second business.</li>
      <li>For records that don't belong with anyone (e.g. landlord BESCOM connection), set their group to <code>Solo</code> — each Solo record becomes its own brand-new UBID.</li>
      <li>For very large clusters, use the <b>filter + bulk assign</b> row above the table to move many records at once.</li>
      <li>The <b>preview</b> at the bottom shows exactly what will happen on submit.</li>
    </ol>
    <b>What gets stored:</b> must-link constraints (within-group pairs), cannot-link constraints (cross-group + Solo), reviewer-decision rows, and training labels — all consumed by the next <code>/admin/retrain</code>.
    """)

    # ── Filters ───────────────────────────────────────────────────────────────
    with st.expander("Filters (which UBIDs to audit)", expanded=False):
        f1, f2, f3 = st.columns(3)
        audit_pick = f1.radio("Status", ["Pending", "Approved", "All"], horizontal=True,
                                help=H("Pending = at least one member-pair lacks a must-link constraint."))
        size_pick = f2.selectbox("Cluster size",
            ["Any (≥2)", "Exactly 2", "3", "4–5", "6–10", "11+"],
            help=H("Larger clusters often need manual sorting; small clusters usually approve as-is."))
        source_pick = f3.selectbox("Contains source",
            ["", "ekarmika", "fbis", "kspcb", "bescom"])

    audit_param = {"Pending": "pending", "Approved": "approved", "All": None}[audit_pick]

    list_params = {"limit": 200, "offset": 0, "min_records": 2}
    if audit_param: list_params["audit_status"] = audit_param
    if source_pick: list_params["source_system"] = source_pick

    udata = api_get("/api/v1/ubid", params=list_params)
    if not udata:
        st.stop()

    candidates = udata.get("results", [])

    def size_ok(rc: int) -> bool:
        if size_pick == "Any (≥2)": return rc >= 2
        if size_pick == "Exactly 2": return rc == 2
        if size_pick == "3": return rc == 3
        if size_pick == "4–5": return 4 <= rc <= 5
        if size_pick == "6–10": return 6 <= rc <= 10
        if size_pick == "11+": return rc >= 11
        return True
    candidates = [c for c in candidates if size_ok(c["record_count"])]

    if not candidates:
        st.success("No UBIDs match these filters — audits clear for this slice!")
        st.stop()

    # ── Counter + navigation ─────────────────────────────────────────────────
    idx = st.session_state.get("audit_idx", 0)
    if idx >= len(candidates):
        idx = 0
    current = candidates[idx]
    cur_ubid = current["ubid"]

    nc1, nc2, nc3, nc4, nc5 = st.columns([1, 1, 3.5, 1, 1])
    nc1.metric("Position", f"{idx + 1} / {len(candidates)}")
    nc2.metric("Records", current["record_count"])
    nc3.markdown(
        f"<div style='padding-top:14px;'>"
        f"<b>UBID</b> <code>{cur_ubid[:13]}…</code> &nbsp;·&nbsp; "
        f"verdict {verdict_badge(current['verdict'])} &nbsp;·&nbsp; "
        f"<b>audit:</b> "
        f"{'✅ approved' if current.get('audit_status') == 'approved' else '⏳ pending'}"
        f"</div>",
        unsafe_allow_html=True,
    )
    if nc4.button("← Prev", disabled=(idx == 0), key="audit_prev"):
        st.session_state.audit_idx = max(0, idx - 1)
        # Reset per-UBID state when navigating
        for k in list(st.session_state.keys()):
            if k.startswith(f"grp_{cur_ubid}_") or k.startswith(f"sort_{cur_ubid}_"):
                del st.session_state[k]
        st.rerun()
    if nc5.button("Next →", disabled=(idx + 1 >= len(candidates)), key="audit_next"):
        st.session_state.audit_idx = idx + 1
        for k in list(st.session_state.keys()):
            if k.startswith(f"grp_{cur_ubid}_") or k.startswith(f"sort_{cur_ubid}_"):
                del st.session_state[k]
        st.rerun()

    st.markdown("---")

    # ── Load UBID detail ─────────────────────────────────────────────────────
    detail = api_get(f"/api/v1/ubid/{cur_ubid}")
    if not detail:
        st.error("Could not load UBID detail.")
        st.stop()

    members = detail.get("source_records") or []
    member_by_id = {m["canonical_id"]: m for m in members}

    # ── Group manager ────────────────────────────────────────────────────────
    GROUP_COLORS = ["#FF9933", "#15803D", "#1E3A8A", "#9333EA", "#0891B2", "#DB2777", "#F59E0B", "#0E7490"]
    SOLO_COLOR = "#991B1B"

    n_groups_key = f"n_groups_{cur_ubid}"
    if n_groups_key not in st.session_state:
        st.session_state[n_groups_key] = 1
    n_groups = st.session_state[n_groups_key]

    # Initialise per-record group state to "Group 1" if not set
    for m in members:
        gkey = f"grp_{cur_ubid}_{m['canonical_id']}"
        if gkey not in st.session_state:
            st.session_state[gkey] = "Group 1"

    # Compute current group counts
    group_counts: dict[str, int] = {}
    for m in members:
        g = st.session_state.get(f"grp_{cur_ubid}_{m['canonical_id']}", "Group 1")
        group_counts[g] = group_counts.get(g, 0) + 1

    # Build available group labels (always show all created groups + Solo)
    group_labels = [f"Group {i+1}" for i in range(n_groups)] + ["Solo"]

    st.markdown("### 🎯 Groups")
    pills_html = "<div style='display:flex; gap:8px; flex-wrap:wrap; margin: 6px 0 14px 0;'>"
    for i in range(n_groups):
        gname = f"Group {i+1}"
        color = GROUP_COLORS[i % len(GROUP_COLORS)]
        cnt = group_counts.get(gname, 0)
        pills_html += (
            f'<span style="background:{color}; color:#fff; padding:5px 14px; '
            f'border-radius:14px; font-weight:700; font-size:0.85rem; '
            f'box-shadow: 0 1px 3px rgba(15,23,42,0.1);">'
            f'● {gname} ({cnt})</span>'
        )
    solo_cnt = group_counts.get("Solo", 0)
    pills_html += (
        f'<span style="background:{SOLO_COLOR}; color:#fff; padding:5px 14px; '
        f'border-radius:14px; font-weight:700; font-size:0.85rem; '
        f'box-shadow: 0 1px 3px rgba(15,23,42,0.1);">'
        f'⚠ Solo ({solo_cnt})</span>'
    )
    pills_html += "</div>"
    st.markdown(pills_html, unsafe_allow_html=True)

    gm1, gm2, gm3, gm4 = st.columns([1, 1, 1, 4])
    if gm1.button(f"+ Add Group {n_groups + 1}", key=f"add_grp_{cur_ubid}",
                    help=H("Adds another group label to the dropdown for every record.")):
        st.session_state[n_groups_key] = n_groups + 1
        st.rerun()
    if gm2.button("↺ Reset all", key=f"reset_grp_{cur_ubid}",
                    help=H("Puts every record back in Group 1 and removes extra groups.")):
        st.session_state[n_groups_key] = 1
        for m in members:
            st.session_state[f"grp_{cur_ubid}_{m['canonical_id']}"] = "Group 1"
        st.rerun()
    if gm3.button("⚠ All Solo", key=f"all_solo_{cur_ubid}",
                    help=H("Marks every record as Solo. Each will become its own UBID.")):
        for m in members:
            st.session_state[f"grp_{cur_ubid}_{m['canonical_id']}"] = "Solo"
        st.rerun()

    # ── Optional: pair-evidence collapsed (helpful but takes vertical space) ─
    with st.expander(f"📊 Why the model grouped these {len(members)} records (pair evidence)",
                       expanded=(len(members) <= 5)):
        pe = api_get(f"/api/v1/ubid/{cur_ubid}/pair-evidence")
        if pe and pe.get("pairs"):
            rows = []
            for p in pe["pairs"]:
                con = p.get("constraint")
                con_badge = "—"
                if con == "must_link": con_badge = "✅ must-link"
                elif con == "cannot_link": con_badge = "❌ cannot-link"
                top_str = " · ".join([f"{f['name']}:{f['contribution']:+.2f}"
                                       for f in (p.get("top_features") or [])[:3]])
                rows.append({
                    "Pair": f"{p['record_a_label']} ↔ {p['record_b_label']}",
                    "p": (round(p["calibrated_probability"], 3)
                          if p["calibrated_probability"] is not None else None),
                    "Shared blocks": ", ".join(p.get("shared_blocks") or []) or "—",
                    "Top SHAP": top_str or "—",
                    "Constraint": con_badge,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No pair-evidence available (may have been clustered transitively).")

    # ── 🔍 Side-by-side comparison ───────────────────────────────────────────
    st.markdown("### 🔍 Compare two records")
    if len(members) >= 2:
        cmp_options = ["—"] + [
            f"{m['source_system']} / {m['source_record_id']}"
            for m in members
        ]
        cmp_to_record = {
            f"{m['source_system']} / {m['source_record_id']}": m for m in members
        }
        cc1, cc2 = st.columns(2)
        pick_a = cc1.selectbox(
            "Record A",
            cmp_options,
            key=f"cmp_a_{cur_ubid}",
            help=H("Pick a record to compare on the left side."),
        )
        # Default Record B to a different record so the comparison shows immediately
        b_default = 0
        if pick_a != "—" and len(cmp_options) > 2:
            for i, opt in enumerate(cmp_options):
                if opt != "—" and opt != pick_a:
                    b_default = i
                    break
        pick_b = cc2.selectbox(
            "Record B",
            cmp_options,
            index=b_default,
            key=f"cmp_b_{cur_ubid}",
            help=H("Pick a record to compare on the right side."),
        )

        if pick_a != "—" and pick_b != "—" and pick_a != pick_b:
            ra = cmp_to_record[pick_a]
            rb = cmp_to_record[pick_b]

            def _norm(v):
                if v is None or v == "" or v == "—":
                    return None
                return str(v).strip()

            def _row_class(va, vb):
                a, b = _norm(va), _norm(vb)
                if a is None and b is None:
                    return ("missing", "⚪")
                if a is None or b is None:
                    return ("missing", "⚪")
                if a.lower() == b.lower():
                    return ("match", "✓")
                # partial match — substring
                la, lb = a.lower(), b.lower()
                if la in lb or lb in la:
                    return ("mismatch", "≈")
                return ("mismatch", "⚠")

            FIELDS = [
                ("Name",      "name_raw"),
                ("PAN",       "pan"),
                ("GSTIN",     "gstin"),
                ("Pin",       "pin_code"),
                ("District",  "district"),
                ("Address",   "address_raw"),
                ("Phone",     "phone"),
                ("Sector",    "sector_raw"),
                ("Legal form","legal_form"),
                ("Employees", "employee_count"),
                ("Reg date",  "registration_date"),
            ]

            rows_html = []
            n_match = n_mismatch = n_missing = 0
            for label, key in FIELDS:
                va = ra.get(key)
                vb = rb.get(key)
                cls, icon = _row_class(va, vb)
                if cls == "match": n_match += 1
                elif cls == "mismatch": n_mismatch += 1
                else: n_missing += 1
                a_disp = (str(va) if va not in (None, "") else "—")[:80]
                b_disp = (str(vb) if vb not in (None, "") else "—")[:80]
                rows_html.append(
                    f'<tr class="{cls}">'
                    f'  <td class="field-label">{label}</td>'
                    f'  <td class="value-a">{a_disp}</td>'
                    f'  <td class="value-b">{b_disp}</td>'
                    f'  <td class="verdict-col">{icon}</td>'
                    f'</tr>'
                )

            st.markdown(f"""
            <table class="compare-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Record A · {ra['source_system']}/{ra['source_record_id']}</th>
                  <th>Record B · {rb['source_system']}/{rb['source_record_id']}</th>
                  <th>≡</th>
                </tr>
              </thead>
              <tbody>
                {''.join(rows_html)}
              </tbody>
            </table>
            """, unsafe_allow_html=True)

            sm1, sm2, sm3, sm4 = st.columns(4)
            sm1.metric("✓ Matches", n_match)
            sm2.metric("⚠ Mismatches", n_mismatch)
            sm3.metric("⚪ Missing", n_missing)
            # Quick action: assign these two to same group or split apart
            sm4_action = sm4.selectbox(
                "Quick action",
                ["—", "Both → Group 1", "Both → Group 2", "A→Group1, B→Group2", "Both → Solo"],
                key=f"cmp_action_{cur_ubid}",
                label_visibility="collapsed",
                help=H("Apply a quick group assignment to these two records."),
            )
            if sm4_action != "—":
                ka = f"grp_{cur_ubid}_{ra['canonical_id']}"
                kb = f"grp_{cur_ubid}_{rb['canonical_id']}"
                if sm4_action == "Both → Group 1":
                    st.session_state[ka] = "Group 1"
                    st.session_state[kb] = "Group 1"
                elif sm4_action == "Both → Group 2":
                    if n_groups < 2:
                        st.session_state[n_groups_key] = 2
                    st.session_state[ka] = "Group 2"
                    st.session_state[kb] = "Group 2"
                elif sm4_action == "A→Group1, B→Group2":
                    if n_groups < 2:
                        st.session_state[n_groups_key] = 2
                    st.session_state[ka] = "Group 1"
                    st.session_state[kb] = "Group 2"
                elif sm4_action == "Both → Solo":
                    st.session_state[ka] = "Solo"
                    st.session_state[kb] = "Solo"
                # Clear the action so it doesn't keep firing
                st.session_state[f"cmp_action_{cur_ubid}"] = "—"
                st.rerun()
        elif pick_a != "—" and pick_a == pick_b:
            st.info("Pick two **different** records to compare.")
        else:
            st.caption("Pick two records above to see their fields side-by-side with match indicators.")

    # ── 🗂 Sort records into groups ──────────────────────────────────────────
    st.markdown("### 🗂 Sort records into groups")
    sources_present = sorted({m["source_system"] for m in members})
    bf1, bf2, bf3, bf4 = st.columns([1.4, 2, 1.5, 1.5])
    src_filter = bf1.selectbox(
        "Filter by source",
        ["All"] + list(sources_present),
        key=f"sort_{cur_ubid}_src",
        help=H("Show only records from one source system."),
    )
    name_search = bf2.text_input(
        "Search name / PAN",
        key=f"sort_{cur_ubid}_search",
        placeholder="e.g. 'sharma' or 'ABCDE1234F'",
        help=H("Substring match on the record's name or PAN."),
    )
    bulk_target = bf3.selectbox(
        "Bulk move to",
        group_labels,
        key=f"sort_{cur_ubid}_bulk",
        help=H("Pick a target group; click 'Apply to filtered' to move every "
                "record matching the filter above into that group at once."),
    )
    if bf4.button(
        "Apply to filtered",
        key=f"sort_{cur_ubid}_apply_bulk",
        help=H("Moves every visible (filtered) record into the chosen group."),
    ):
        for m in members:
            if src_filter != "All" and m["source_system"] != src_filter: continue
            if name_search:
                hay = (m.get("name_raw") or "").lower() + " " + (m.get("pan") or "").lower()
                if name_search.lower() not in hay: continue
            st.session_state[f"grp_{cur_ubid}_{m['canonical_id']}"] = bulk_target
        st.rerun()

    # Filter the visible records
    visible_members = []
    for m in members:
        if src_filter != "All" and m["source_system"] != src_filter: continue
        if name_search:
            hay = (m.get("name_raw") or "").lower() + " " + (m.get("pan") or "").lower()
            if name_search.lower() not in hay: continue
        visible_members.append(m)

    if not visible_members:
        st.info("No records match the filter. Clear the filter above to see all members.")
    else:
        st.caption(f"Showing {len(visible_members)} of {len(members)} records.")

        # Vertical record list — each row uses themed selectbox for group assignment
        for m in visible_members:
            cid = m["canonical_id"]
            gkey = f"grp_{cur_ubid}_{cid}"
            current_group = st.session_state.get(gkey, "Group 1")
            color = (SOLO_COLOR if current_group == "Solo"
                     else GROUP_COLORS[(int(current_group.split()[1]) - 1) % len(GROUP_COLORS)]
                     if current_group.startswith("Group ")
                     else "#94A3B8")

            row_cols = st.columns([0.6, 1, 1.2, 2, 1, 1.5, 1.4])

            row_cols[0].markdown(
                f'<div style="background:{color}; color:#fff; padding:5px 0; '
                f'border-radius:12px; font-size:0.7rem; font-weight:700; '
                f'text-align:center; text-transform:uppercase; letter-spacing:0.05em; '
                f'margin-top:14px;">●</div>',
                unsafe_allow_html=True,
            )
            row_cols[1].markdown(
                f'<div style="margin-top:14px; font-weight:700; color:var(--gov-navy); '
                f'font-size:0.85rem; text-transform:uppercase; letter-spacing:0.04em;">'
                f'{m["source_system"]}</div>',
                unsafe_allow_html=True,
            )
            row_cols[2].markdown(
                f'<div style="margin-top:14px; font-family:monospace; font-size:0.82rem; '
                f'color:var(--ink-secondary); word-break:break-all;">'
                f'{m["source_record_id"]}</div>',
                unsafe_allow_html=True,
            )
            row_cols[3].markdown(
                f'<div style="margin-top:11px; line-height:1.3;">'
                f'<div style="font-weight:600; color:var(--ink);">{(m.get("name_raw") or "—")[:50]}</div>'
                f'<div style="font-size:0.78rem; color:var(--ink-muted);">{(m.get("address_raw") or "")[:90]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            row_cols[4].markdown(
                f'<div style="margin-top:14px; font-family:monospace; font-size:0.82rem; '
                f'color:var(--ink-secondary);">'
                f'{m.get("pan") or "—"}</div>',
                unsafe_allow_html=True,
            )
            row_cols[5].markdown(
                f'<div style="margin-top:11px; line-height:1.3;">'
                f'<div style="font-size:0.82rem; color:var(--ink-secondary);">'
                f'📍 {m.get("pin_code") or "—"}</div>'
                f'<div style="font-size:0.78rem; color:var(--ink-muted);">'
                f'☎ {m.get("phone") or "—"}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # The themed selectbox for group assignment
            try:
                idx = group_labels.index(current_group)
            except ValueError:
                idx = 0
            new_group = row_cols[6].selectbox(
                "Group",
                group_labels,
                index=idx,
                key=f"sb_{cur_ubid}_{cid}",
                label_visibility="collapsed",
            )
            if new_group != current_group:
                st.session_state[gkey] = new_group
                st.rerun()

    # Recompute group counts after potential edits
    group_counts = {}
    for m in members:
        g = st.session_state.get(f"grp_{cur_ubid}_{m['canonical_id']}", "Group 1")
        group_counts[g] = group_counts.get(g, 0) + 1

    # ── Preview ──────────────────────────────────────────────────────────────
    st.markdown("### 📊 Preview")

    non_empty_groups = {g: c for g, c in group_counts.items() if c > 0}
    n_solo = group_counts.get("Solo", 0)
    n_real_groups = sum(1 for g, c in non_empty_groups.items() if g != "Solo")
    n_resulting_ubids = n_real_groups + n_solo  # each Solo = own UBID

    # Counts for must-link / cannot-link
    must_links = 0
    cannot_links = 0
    cids = list(member_by_id.keys())
    cid_groups = {cid: st.session_state.get(f"grp_{cur_ubid}_{cid}", "Group 1") for cid in cids}
    for i in range(len(cids)):
        for j in range(i + 1, len(cids)):
            ga, gb = cid_groups[cids[i]], cid_groups[cids[j]]
            same = (ga == gb and ga != "Solo")
            if same: must_links += 1
            else: cannot_links += 1

    if n_resulting_ubids == 1 and n_solo == 0:
        st.success(
            f"**Approve as-is** — all {len(members)} records stay in the current UBID. "
            f"Will write {must_links} must-link constraints + decision rows."
        )
    else:
        bullets = []
        for g in sorted(non_empty_groups.keys(), key=lambda x: (x == "Solo", x)):
            cnt = non_empty_groups[g]
            if g == "Solo":
                bullets.append(f"  • <b>{cnt} Solo record(s)</b> → each becomes its own brand-new UBID")
            elif cnt == 1:
                bullets.append(f"  • <b>{g}</b> (1 record) → new UBID")
            else:
                bullets.append(f"  • <b>{g}</b> ({cnt} records) → 1 UBID")
        bullets_html = "<br>".join(bullets)
        st.markdown(f"""
        <div class="gov-card">
          <b>Result of applying:</b><br>
          {bullets_html}
          <hr style="margin: 8px 0; border-top: 1px solid var(--rule-light);">
          <b>{must_links}</b> must-link constraint(s) + <b>{cannot_links}</b> cannot-link constraint(s)
          + <b>{must_links + cannot_links}</b> reviewer-decision rows
          + <b>{must_links + cannot_links}</b> training-label rows<br>
          <i style="color: var(--ink-muted); font-size:0.85rem;">
            (every constraint + label feeds the next /admin/retrain)
          </i>
        </div>
        """, unsafe_allow_html=True)

    # ── Action buttons ───────────────────────────────────────────────────────
    notes = st.text_input(
        "Notes (optional, recorded in audit log)",
        placeholder="e.g. 'Sharma Traders is one business; Sharma Solutions is separate; landlord BESCOM record isolated'",
        key=f"notes_{cur_ubid}",
    )

    act1, act2, act3 = st.columns([2, 1.4, 1])
    if act1.button("✅ Apply grouping", type="primary",
                     key=f"apply_{cur_ubid}",
                     use_container_width=True,
                     help=H("Submits the grouping. Splits the UBID, writes constraints, "
                             "training labels, decision rows, and refreshes verdict caches.")):
        groupings = {cid: cid_groups[cid] for cid in cids}
        with st.spinner("Applying grouping…"):
            resp = api_post("/api/v1/review/regroup", {
                "ubid": cur_ubid,
                "groupings": groupings,
                "reviewer_id": reviewer_id,
                "reviewer_tier": reviewer_tier,
                "notes": notes or None,
            })
        if resp:
            st.success(
                f"✓ {resp.get('status', 'done')} · "
                f"{resp.get('new_ubids_created', 0)} new UBIDs · "
                f"{resp.get('records_moved', 0)} records moved · "
                f"{resp.get('must_links_added', 0)} must-link + {resp.get('cannot_links_added', 0)} cannot-link constraints · "
                f"{resp.get('training_labels_written', 0)} training labels written"
            )
            # Clear per-UBID state and advance
            for k in list(st.session_state.keys()):
                if k.startswith(f"grp_{cur_ubid}_") or k.startswith(f"sort_{cur_ubid}_") or k == n_groups_key or k == f"notes_{cur_ubid}":
                    del st.session_state[k]
            st.session_state.audit_idx = min(idx + 1, len(candidates) - 1)
            st.rerun()

    if act2.button("⏭️ Skip — review later",
                     key=f"skip_{cur_ubid}",
                     use_container_width=True,
                     help=H("Move on without saving. Comes back next time you visit Pending.")):
        for k in list(st.session_state.keys()):
            if k.startswith(f"grp_{cur_ubid}_") or k.startswith(f"sort_{cur_ubid}_") or k == n_groups_key:
                del st.session_state[k]
        st.session_state.audit_idx = min(idx + 1, len(candidates) - 1)
        st.rerun()

    if act3.button("↺ Reset",
                     key=f"reset2_{cur_ubid}",
                     use_container_width=True,
                     help=H("Reset all groupings on this UBID back to default (one group).")):
        st.session_state[n_groups_key] = 1
        for m in members:
            st.session_state[f"grp_{cur_ubid}_{m['canonical_id']}"] = "Group 1"
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

                help_banner("How to split (unmerge) records", """
                Use this when the model wrongly merged two records that aren't actually the same business.
                <ol>
                  <li>In <b>Record A</b>, pick the record that <i>stays</i> on this UBID.</li>
                  <li>In <b>Record B</b>, pick the record that should be <i>peeled off</i> into its own new UBID.</li>
                  <li>(Optional) Add a <b>reason</b> — gets stored in the audit log so others can see why you split.</li>
                  <li>Click <b>🔓 Split</b>.</li>
                </ol>
                <b>What happens:</b>
                <ul>
                  <li>A new UBID is created for record B.</li>
                  <li>A permanent <code>cannot-link</code> constraint is written so future ingestions / re-clusters will never re-merge them.</li>
                  <li>Both UBIDs' verdict caches are invalidated.</li>
                  <li>The decision shows up in <b>📜 Reviewer Log</b> and the <b>UBID lineage &amp; audit trail</b> below.</li>
                </ul>
                <b>Reversible:</b> If you split by mistake, go to the new UBID's Activity Status and use the same Unmerge UI in reverse — except since cannot-link constraints are persistent, you'd first need to override via a <b>confirm_match</b> in the Review Queue, or in this UI re-run by selecting the same two records and choosing "Confirm" instead.
                """)

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
                pick_a = u_col1.selectbox(
                    "Record A (stays on current UBID)",
                    opts,
                    key="unmerge_a",
                    help=H("This record will keep the current UBID."),
                )
                pick_b = u_col2.selectbox(
                    "Record B (peels off to a new UBID)",
                    [o for o in opts if o != pick_a],
                    key="unmerge_b",
                    help=H("This record will be moved to a brand-new UBID. "
                            "A cannot-link constraint will permanently prevent re-merging."),
                )

                u_notes = st.text_input(
                    "Reason (optional, recorded in audit log)",
                    key="unmerge_notes",
                    placeholder="e.g. 'different proprietor' / 'shared pin only'",
                    help=H("Any free-text note. Stored in the reviewer_decisions table "
                            "and visible in the UBID lineage."),
                )

                if st.button(
                    "🔓 Split (unmerge B from this UBID)",
                    key="do_unmerge",
                    type="primary",
                    help=H("Submits the split. A new UBID is created for record B and "
                            "a permanent cannot-link constraint is written."),
                ):
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
                    plot_bgcolor="#FFFFFF",
                    font=dict(color="#334155"),
                    xaxis=dict(gridcolor="#E2E8F0"),
                    yaxis=dict(gridcolor="#E2E8F0"),
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
                paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                font=dict(color="#334155"),
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

    a1, a2, a3, a4, a5 = st.tabs([
        "Retrain model", "Re-score pairs", "Calibration", "Locality synonyms", "Verdicts"
    ])

    # ── Retrain ───────────────────────────────────────────────────────────────
    with a1:
        st.subheader("Retrain LightGBM scorer")
        st.caption("Rebuilds the model from the latest reviewer-confirmed labels "
                   "(plus optional ground-truth seeding) and reports A/B metrics.")

        # ── Label budget ────────────────────────────────────────────────────
        budget = api_get("/api/v1/admin/labels-since-last-retrain")
        if budget:
            new_count = budget.get("labels_since_last_retrain", 0)
            total = budget.get("total_labels", 0)
            last_at = budget.get("last_retrain_at")

            # Status colour: red ≤0, amber <50, green ≥50
            if new_count == 0:
                status_color = "#475569"
            elif new_count < 20:
                status_color = "#991B1B"
            elif new_count < 50:
                status_color = "#B45309"
            else:
                status_color = "#15803D"

            st.markdown(f"""
            <div class="gov-card" style="border-left-color:{status_color};">
              <div style="display:flex; align-items:baseline; gap:18px; flex-wrap:wrap;">
                <div>
                  <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase;
                              letter-spacing:0.08em; color:var(--gov-navy);">
                    Label budget
                  </div>
                  <div style="font-size:2rem; font-weight:700; color:{status_color};">
                    {new_count}
                  </div>
                  <div style="font-size:0.78rem; color:var(--ink-muted);">
                    new reviewer labels since last retrain
                  </div>
                </div>
                <div style="border-left: 1px solid var(--rule-light); padding-left:18px;">
                  <div style="font-size:0.78rem; color:var(--ink-muted);">Total labels</div>
                  <div style="font-size:1.2rem; font-weight:700;">{total}</div>
                </div>
                <div style="border-left: 1px solid var(--rule-light); padding-left:18px;">
                  <div style="font-size:0.78rem; color:var(--ink-muted);">Last retrain</div>
                  <div style="font-size:0.95rem; color:var(--ink);">
                    {(last_at or 'never')[:19]}
                  </div>
                </div>
              </div>
              <div style="margin-top:8px; padding-top:8px; border-top: 1px solid var(--rule-light);
                          color:var(--ink-secondary); font-size:0.88rem;">
                💡 {budget.get('recommendation','')}
              </div>
            </div>
            """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        include_gt = c1.checkbox("Include ground-truth seed", value=True,
                                  help=H("Adds the synthetic ground-truth pairs (~1700) on top of "
                                          "the reviewer labels. Always recommended unless you have "
                                          "tens of thousands of reviewer labels of your own."))
        min_labels = c2.number_input("Minimum reviewer labels required", min_value=0, value=0,
                                       help=H("Refuse to train unless at least this many reviewer "
                                               "labels exist. Set ≥50 for production prudence."))

        if st.button("Trigger retrain", type="primary",
                       help=H("Pulls every reviewer-confirmed label (and optionally the ground-truth seed), "
                               "re-fits LightGBM, recalibrates with isotonic regression, and reports A/B metrics. "
                               "Also logs the run to retrain history.")):
            with st.spinner("Training…"):
                resp = api_post("/api/v1/admin/retrain", {
                    "include_ground_truth": include_gt,
                    "min_reviewer_labels": int(min_labels),
                })
            if resp:
                st.success(f"✓ trained in {resp.get('duration_seconds')}s · run "
                            f"`{resp.get('run_id', '')[:8]}…` saved to history")
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

        # ── Retrain history ────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("##### Retrain history")
        history = api_get("/api/v1/admin/retrain-history", params={"limit": 20})
        if history and history.get("runs"):
            runs = list(reversed(history["runs"]))   # oldest → newest
            xs = [r["started_at"][:16] if r.get("started_at") else "" for r in runs]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=xs,
                y=[(r.get("post") or {}).get("f1") for r in runs],
                mode="lines+markers",
                name="Post-train F1 @ 0.95",
                line=dict(color="#15803D", width=3),
                marker=dict(size=10, color="#15803D",
                             line=dict(color="#0F172A", width=1.5)),
            ))
            fig.add_trace(go.Scatter(
                x=xs,
                y=[(r.get("pre") or {}).get("f1") for r in runs],
                mode="lines+markers",
                name="Pre-train F1 @ 0.95",
                line=dict(color="#94A3B8", width=2, dash="dot"),
                marker=dict(size=7, color="#94A3B8"),
            ))
            fig.update_layout(
                height=280,
                margin=dict(l=20, r=20, t=10, b=40),
                yaxis=dict(range=[0, 1.02], title="F1 @ 0.95"),
                xaxis=dict(title=None, tickangle=-30),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            )
            st.plotly_chart(fig, use_container_width=True, key="retrain_history_chart")

            # Compact table of runs
            tbl = pd.DataFrame([
                {
                    "When": (r["started_at"] or "")[:19],
                    "Labels": r.get("n_reviewer_labels", 0),
                    "Total pairs": r.get("n_total_pairs", 0),
                    "Pre F1": f"{(r.get('pre') or {}).get('f1', 0):.3f}",
                    "Post F1": f"{(r.get('post') or {}).get('f1', 0):.3f}",
                    "Δ F1": f"{((r.get('post') or {}).get('f1', 0) - (r.get('pre') or {}).get('f1', 0)):+.3f}",
                    "Pre Brier": f"{(r.get('pre') or {}).get('brier', 0):.4f}",
                    "Post Brier": f"{(r.get('post') or {}).get('brier', 0):.4f}",
                    "Duration": f"{r.get('duration_seconds', 0):.2f}s",
                }
                for r in history["runs"]
            ])
            st.dataframe(tbl, use_container_width=True, hide_index=True)
        else:
            st.info("No retrain runs logged yet. Trigger your first retrain above.")

    # ── Re-score pairs ────────────────────────────────────────────────────────
    with a2:
        st.subheader("Re-score linkage pairs with the latest model")
        st.caption("After retraining, the saved pairs in the database still carry their old scores. "
                   "Re-scoring updates them so reviewers see fresh probabilities and the next "
                   "clustering pass uses the new model's confidence.")

        help_banner("Smart vs full mode", """
        <ul>
          <li><b>Smart</b> (default) — only re-scores pairs that <i>matter</i>:
            <ul>
              <li>Pairs in the review queue (so reviewers see fresh probabilities).</li>
              <li>Boundary pairs in the [0.20, 0.97] probability range — the ones whose auto-link / review / reject bucket might actually change.</li>
            </ul>
            Pairs already firmly classified (p ≥ 0.97 or ≤ 0.20) are skipped because their bucket won't move.
          </li>
          <li><b>Full</b> — re-scores every single pair. Slower at scale, only useful if you've made a major model change and want every prediction refreshed.</li>
        </ul>
        At 10 M records and 5 M linkage pairs, smart mode would touch ~10 k pairs (~10 s). Full would touch all 5 M (~minutes-hours).
        """)

        rs_mode = st.radio("Mode", ["smart", "full"], horizontal=True,
                            help=H("Smart re-scores only the boundary + queue pairs. "
                                    "Full re-scores everything."))
        if st.button("Re-score now", type="primary", key="rescore_btn",
                       help=H("Runs the model over the chosen pair set and updates "
                               "their calibrated probabilities in the linkage_pairs table.")):
            with st.spinner(f"Re-scoring (mode={rs_mode})…"):
                resp = api_post("/api/v1/admin/rescore", params={"mode": rs_mode})
            if resp:
                st.success(
                    f"✓ {resp.get('pairs_rescored', 0)} pairs re-scored in "
                    f"{resp.get('duration_seconds', 0)}s "
                    f"({resp.get('skipped_missing_records', 0)} skipped)"
                )

    # ── Calibration ───────────────────────────────────────────────────────────
    with a3:
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
                                      xaxis=dict(range=[0, 1], gridcolor="#E2E8F0"),
                                      yaxis=dict(range=[0, 1], gridcolor="#E2E8F0"),
                                      paper_bgcolor="#FFFFFF",
                                      plot_bgcolor="#FFFFFF",
                                      font=dict(color="#334155"))
                    st.plotly_chart(fig, use_container_width=True, key="admin_reliability")

                with st.expander("Bucket details"):
                    st.dataframe(pd.DataFrame(cal.get("reliability_diagram") or []),
                                 use_container_width=True)

    # ── Locality synonyms ─────────────────────────────────────────────────────
    with a4:
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
    with a5:
        st.subheader("Refresh all activity verdicts")
        st.caption("Recomputes the verdict for every UBID using the current event "
                   "warehouse and the reference date set in the sidebar.")
        if st.button("Refresh all verdicts", type="primary",
                       help=H("Recomputes Active/Dormant/Closed for every UBID using the current event "
                               "warehouse and the reference date set in the sidebar. Run after re-ingesting events.")):
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
                                      plot_bgcolor="#FFFFFF",
                                      font=dict(color="#334155"))
                    st.plotly_chart(fig, use_container_width=True, key="admin_verdict_dist")


# ═════════════════════════════════════════════════════════════════════════════
# Government footer
# ═════════════════════════════════════════════════════════════════════════════
render_footer()
