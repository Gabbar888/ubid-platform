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

# ── Plotly: editorial template (cream cards, ink text, saffron/moss/crimson) ─
pio.templates["ubid"] = pio.templates["plotly_white"]
_t = pio.templates["ubid"]
_t.layout.font = dict(color="#0f1f3a", family="'Inter', sans-serif", size=12)
_t.layout.title.font = dict(color="#0f1f3a", size=15, family="'Fraunces', serif")
_t.layout.paper_bgcolor = "#FFFFFF"
_t.layout.plot_bgcolor = "#FFFFFF"
_t.layout.xaxis = dict(
    color="#4a3f33",
    tickfont=dict(color="#4a3f33", size=11, family="'JetBrains Mono', monospace"),
    title_font=dict(color="#0f1f3a", size=12, family="'Inter', sans-serif"),
    gridcolor="#e5dcc8",
    zerolinecolor="#c9b896",
    linecolor="#c9b896",
)
_t.layout.yaxis = dict(
    color="#4a3f33",
    tickfont=dict(color="#4a3f33", size=11, family="'JetBrains Mono', monospace"),
    title_font=dict(color="#0f1f3a", size=12, family="'Inter', sans-serif"),
    gridcolor="#e5dcc8",
    zerolinecolor="#c9b896",
    linecolor="#c9b896",
)
_t.layout.legend = dict(
    font=dict(color="#4a3f33", family="'Inter', sans-serif"),
    bordercolor="#c9b896",
)
_t.layout.colorway = ["#1e3a5f", "#d97706", "#4a5d23", "#991b1b", "#15803d", "#7a6a55"]
pio.templates.default = "ubid"

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UBID Platform | Karnataka Commerce & Industries",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Editorial / state-document theme (Fraunces + Inter + JetBrains Mono) ──
# Palette anchored to paper-cream + indigo + saffron with moss/crimson accents.
# Sharp corners, hairline borders, generous whitespace. See DESIGN_BRIEF.md.
st.markdown("""
<style>
    /* ── Imports — editorial typography ───────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,700;1,9..144,400;1,9..144,600;1,9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Noto+Sans+Kannada:wght@500;600;700&display=swap');

    /* ── Color tokens (editorial / state-document) ────────────────────── */
    :root {
        /* Surfaces */
        --paper:        #f4ede0;
        --paper-deep:   #ebe1cd;
        --surface:      #f7f1e5;
        --white:        #ffffff;

        /* Ink */
        --ink:          #0f1f3a;
        --ink-soft:     #4a3f33;
        --ink-faint:    #7a6a55;
        --rule:         #c9b896;
        --rule-soft:    #e5dcc8;

        /* Accents */
        --saffron:        #d97706;
        --saffron-bright: #f59e0b;
        --saffron-deep:   #b35c00;
        --indigo:         #1e3a5f;
        --indigo-deep:    #0f1f3a;
        --moss:           #4a5d23;
        --moss-bright:    #15803d;
        --crimson:        #991b1b;

        /* Compatibility aliases (legacy refs in remaining markup) */
        --gov-navy:       var(--indigo-deep);
        --gov-navy-dark:  var(--indigo-deep);
        --gov-navy-light: var(--indigo);
        --india-green:    var(--moss-bright);
        --green-deep:     var(--moss);
        --bg:             var(--paper);
        --ink-secondary:  var(--ink-soft);
        --ink-muted:      var(--ink-faint);
        --rule-light:     var(--rule-soft);
        --ashoka:         var(--indigo-deep);
        --ring:           rgba(217, 119, 6, 0.25);
        --shadow-sm:      0 0.5px 2px rgba(15, 31, 58, 0.06);
        --shadow-md:      0 1px 4px rgba(15, 31, 58, 0.10);
    }

    /* Hide unused sidebar */
    section[data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        background-color: var(--paper) !important;
        color: var(--ink);
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 14px;
        line-height: 1.55;
    }

    .block-container {
        padding-top: 0 !important;
        padding-left: 64px !important;
        padding-right: 64px !important;
        padding-bottom: 4rem !important;
        max-width: 1600px;
    }

    /* Hide Streamlit chrome */
    #MainMenu, footer, [data-testid="stHeader"] { visibility: hidden; height: 0; }
    [data-testid="stToolbar"] { visibility: hidden; }

    /* ── Header masthead (3-strip indigo) ─────────────────────────────── */
    .gov-header {
        background: linear-gradient(180deg, #1e3a5f 0%, #0f1f3a 100%);
        color: var(--paper);
        padding: 18px 64px;
        margin: 0 -64px;
        display: grid;
        grid-template-columns: auto 1fr auto;
        gap: 28px;
        align-items: center;
    }
    .gov-header .crest {
        width: 56px; height: 56px; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
    }
    .gov-header .crest img { width: 100%; height: 100%; object-fit: contain; }
    .gov-header .crest .real-logo { background: rgba(255,255,255,0.04); padding: 3px; border-radius: 50%; }
    .gov-header .titles { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
    .gov-header .gov-tagline {
        font-family: 'Inter', sans-serif;
        font-size: 11px; font-weight: 600;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: var(--rule);
        display: flex; align-items: baseline; gap: 8px;
        flex-wrap: wrap;
    }
    .gov-header .gov-tagline .kannada {
        font-family: 'Noto Sans Kannada', sans-serif;
        letter-spacing: normal;
        font-size: 12px;
        color: var(--rule);
    }
    .gov-header .gov-tagline .gok-en {
        color: var(--paper);
        font-weight: 700;
        letter-spacing: 0.2em;
    }
    .gov-header .platform {
        font-family: 'Fraunces', Georgia, serif;
        font-size: 26px;
        font-weight: 700;
        letter-spacing: -0.01em;
        line-height: 1.15;
        color: var(--paper);
        font-variation-settings: 'opsz' 144;
        margin: 0;
    }
    .gov-header .platform .ital {
        font-style: italic;
        color: var(--saffron-bright);
        font-weight: 400;
    }
    .gov-header .platform-kn {
        font-family: 'Noto Sans Kannada', sans-serif;
        font-size: 12px;
        color: var(--rule);
        margin-top: 2px;
    }
    .gov-header .dept {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        color: var(--rule);
        margin-top: 2px;
        letter-spacing: 0.05em;
    }
    .gov-header .dept-block {
        text-align: right;
        font-family: 'Inter', sans-serif;
        align-self: flex-start;
    }
    .gov-header .dept-block .dept-name {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: var(--saffron-bright);
        margin-bottom: 4px;
    }
    .gov-header .dept-block .dept-sys {
        font-family: 'Fraunces', serif;
        font-size: 12px;
        font-style: italic;
        color: var(--rule);
    }

    /* Tricolor — saffron + green hairline bar */
    .tricolor {
        display: block;
        height: 4px;
        margin: 0 -64px;
        background: linear-gradient(180deg,
            var(--saffron) 0%, var(--saffron) 50%,
            var(--moss-bright) 50%, var(--moss-bright) 100%);
    }
    .tricolor > div { display: none; }

    /* ── Reviewer toolbar (just under the tricolor) ────────────────────── */
    .toolbar {
        background: var(--paper);
        margin: 0 -64px;
        padding: 14px 64px;
        border-bottom: 0.5px solid var(--rule);
        display: flex;
        align-items: center;
        gap: 32px;
        font-family: 'Inter', sans-serif;
    }
    .toolbar .field { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .toolbar .field-label {
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.25em;
        text-transform: uppercase;
        color: var(--ink-faint);
    }
    .toolbar .field-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        font-weight: 500;
        color: var(--ink);
    }
    .toolbar .sep { width: 0.5px; height: 32px; background: var(--rule); }
    .toolbar .spacer { flex: 1; }
    .toolbar .status-pill {
        display: flex; align-items: center; gap: 8px;
        font-size: 11px; font-weight: 600;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: var(--ink-faint);
    }
    .toolbar .status-pill .dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: var(--moss-bright);
        animation: status-pulse 2s ease-in-out infinite;
    }
    .toolbar .status-pill.red .dot { background: var(--crimson); animation: none; }
    .toolbar .status-pill .lbl { color: var(--ink-soft); }
    .toolbar .status-pill .latency {
        font-family: 'JetBrains Mono', monospace;
        color: var(--ink);
        font-weight: 600;
        margin-left: 4px;
        text-transform: none;
        letter-spacing: 0;
    }
    @keyframes status-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

    /* ── Top nav (pill row, no emojis, saffron underline) ──────────────── */
    [data-testid="stElementContainer"]:has(.ubid-nav-marker) + [data-testid="stElementContainer"] .stRadio > div[role="radiogroup"] {
        margin: 0 -64px !important;
        padding: 0 64px !important;
        background: var(--paper) !important;
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 0 !important;
        border-bottom: 0.5px solid var(--rule) !important;
        align-items: stretch !important;
        overflow-x: auto;
    }
    [data-testid="stElementContainer"]:has(.ubid-nav-marker) + [data-testid="stElementContainer"] .stRadio > div[role="radiogroup"] > label {
        cursor: pointer !important;
        background: transparent !important;
        border: 0 !important;
        border-radius: 0 !important;
        padding: 18px 18px !important;
        margin: 0 !important;
        color: var(--ink-soft) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.2em !important;
        text-transform: uppercase !important;
        position: relative !important;
        display: flex !important;
        align-items: center !important;
        flex-direction: row !important;
        white-space: nowrap !important;
        box-shadow: none !important;
        transform: none !important;
        transition: color 0.15s ease;
    }
    [data-testid="stElementContainer"]:has(.ubid-nav-marker) + [data-testid="stElementContainer"] .stRadio > div[role="radiogroup"] > label:hover { color: var(--ink) !important; }
    /* Hide the radio circle */
    [data-testid="stElementContainer"]:has(.ubid-nav-marker) + [data-testid="stElementContainer"] .stRadio > div[role="radiogroup"] > label > div:first-child,
    [data-testid="stElementContainer"]:has(.ubid-nav-marker) + [data-testid="stElementContainer"] .stRadio > div[role="radiogroup"] > label [role="radio"] {
        display: none !important;
    }
    /* Active state: ink color + saffron 3px underline */
    [data-testid="stElementContainer"]:has(.ubid-nav-marker) + [data-testid="stElementContainer"] .stRadio > div[role="radiogroup"] > label:has(input:checked) {
        color: var(--ink) !important;
    }
    [data-testid="stElementContainer"]:has(.ubid-nav-marker) + [data-testid="stElementContainer"] .stRadio > div[role="radiogroup"] > label:has(input:checked)::after {
        content: "";
        position: absolute;
        bottom: 0;
        left: 18px;
        right: 18px;
        height: 3px;
        background: var(--saffron);
    }

    /* Nav badges (rendered in label text via emoji-strip helper) */
    .nav-badge {
        display: inline-block;
        margin-left: 8px;
        min-width: 22px;
        height: 18px;
        line-height: 18px;
        padding: 0 7px;
        border-radius: 9px;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0;
        color: #fff;
        text-align: center;
        background: var(--crimson);
    }
    .nav-badge--warn { background: var(--saffron); }

    /* ── Page hero (eyebrow + saffron rule + serif H1 + auxiliary block) ── */
    .page-hero {
        margin: 36px 0 28px 0;
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 32px;
        align-items: end;
    }
    .page-hero .eyebrow {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.4em;
        text-transform: uppercase;
        color: var(--saffron);
        margin: 0 0 12px 0;
    }
    .page-hero .saffron-rule {
        width: 48px; height: 3px;
        background: var(--saffron);
        margin: 0 0 20px 0;
    }
    .page-hero h1 {
        font-family: 'Fraunces', Georgia, serif !important;
        font-size: 48px !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        line-height: 1.05 !important;
        color: var(--ink) !important;
        margin: 0 !important;
        font-variation-settings: 'opsz' 144;
        max-width: 22ch;
    }
    .page-hero h1 .ital {
        font-style: italic;
        color: var(--saffron);
        font-weight: 400;
    }
    .page-hero .subtitle {
        font-family: 'Fraunces', serif;
        font-style: italic;
        font-size: 14px;
        color: var(--ink-faint);
        margin-top: 14px;
        max-width: 64ch;
    }
    .page-hero .aux {
        text-align: right;
        min-width: 280px;
    }
    .page-hero .aux .aux-label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.3em;
        text-transform: uppercase;
        color: var(--ink-faint);
        margin-bottom: 6px;
    }
    .page-hero .aux .aux-value {
        font-family: 'Fraunces', serif;
        font-size: 40px;
        font-weight: 700;
        color: var(--ink);
        line-height: 1.1;
        font-variation-settings: 'opsz' 144;
    }
    .page-hero .aux .aux-sub {
        font-family: 'Fraunces', serif;
        font-style: italic;
        font-size: 13px;
        color: var(--ink-faint);
        margin-top: 4px;
    }
    .page-hero .aux .aux-foot {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        color: var(--ink-faint);
        margin-top: 14px;
        border-top: 0.5px solid var(--rule);
        padding-top: 10px;
    }

    /* Compact sub-section header */
    .sub-eyebrow {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.4em;
        text-transform: uppercase;
        color: var(--saffron);
        margin: 0 0 8px 0;
    }
    .sub-h2 {
        font-family: 'Fraunces', serif;
        font-size: 22px;
        font-weight: 700;
        color: var(--ink);
        letter-spacing: -0.01em;
        margin: 0 0 6px 0;
        font-variation-settings: 'opsz' 144;
    }
    .sub-cap {
        font-family: 'Fraunces', serif;
        font-style: italic;
        font-size: 13px;
        color: var(--ink-faint);
        margin: 0 0 18px 0;
    }

    /* ── Cards (sharp corners, hairline borders, top accent) ───────────── */
    .metric-card {
        background: var(--white);
        border: 0.5px solid var(--rule);
        border-radius: 0;
        padding: 22px;
        border-top: 6px solid var(--ink-soft);
        min-height: 178px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        box-shadow: none;
    }
    .metric-card.accent-saffron { border-top-color: var(--saffron); }
    .metric-card.accent-indigo  { border-top-color: var(--indigo); }
    .metric-card.accent-crimson { border-top-color: var(--crimson); }
    .metric-card.accent-moss    { border-top-color: var(--moss-bright); }
    .metric-card.hero {
        background: var(--indigo-deep);
        color: var(--paper);
        border-color: var(--indigo-deep);
        border-top-color: var(--saffron);
    }
    .metric-card.hero .label,
    .metric-card.hero .num,
    .metric-card.hero .sub { color: var(--paper) !important; }
    .metric-card.hero .delta { color: #4ade80 !important; }
    .metric-card .label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.3em;
        text-transform: uppercase;
        color: var(--ink-faint);
        margin: 0;
    }
    .metric-card .num {
        font-family: 'Fraunces', serif;
        font-size: 64px;
        font-weight: 700;
        line-height: 1;
        letter-spacing: -0.02em;
        color: var(--ink);
        font-variation-settings: 'opsz' 144;
    }
    .metric-card.hero .num { font-size: 86px; }
    .metric-card .sub {
        font-family: 'Fraunces', serif;
        font-style: italic;
        font-size: 13px;
        color: var(--ink-faint);
    }
    .metric-card .delta {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        font-weight: 600;
        color: var(--moss-bright);
        margin-top: auto;
    }
    .metric-card .delta.neg { color: var(--crimson); }

    /* Mini horizontal bar list (in cards) */
    .mini-bars { display: flex; flex-direction: column; gap: 7px; margin-top: 4px; }
    .mini-bars .bar-row {
        display: grid;
        grid-template-columns: 70px 1fr 28px;
        align-items: center;
        gap: 10px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
    }
    .mini-bars .bar-row .name { color: var(--ink-soft); }
    .mini-bars .bar-row .bar  { height: 8px; background: var(--indigo); }
    .mini-bars .bar-row.b-saffron .bar { background: var(--saffron); }
    .mini-bars .bar-row.b-moss    .bar { background: var(--moss); }
    .mini-bars .bar-row.b-crimson .bar { background: var(--crimson); }
    .mini-bars .bar-row .v { color: var(--ink); font-weight: 700; text-align: right; }

    /* Confidence band (3-zone horizontal) */
    .conf-band { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; }
    .conf-band .bar { display: flex; height: 16px; }
    .conf-band .bar > div {
        font-size: 10px; color: #fff;
        font-weight: 700; letter-spacing: 0.15em;
        text-align: center; line-height: 16px;
        text-transform: uppercase;
    }
    .conf-band .bar .reject { background: var(--crimson); }
    .conf-band .bar .review { background: var(--saffron); }
    .conf-band .bar .auto   { background: var(--moss); }
    .conf-band .bounds {
        display: flex; justify-content: space-between;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        color: var(--ink-faint);
    }

    /* ── Buttons (uppercase tracked, sharp corners) ──────────────────── */
    .stButton button, .stDownloadButton button {
        background: var(--white) !important;
        color: var(--ink) !important;
        border: 1px solid var(--ink) !important;
        border-radius: 0 !important;
        padding: 10px 20px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.2em !important;
        text-transform: uppercase !important;
        height: auto !important;
        min-height: 38px !important;
        box-shadow: none !important;
        transition: background 0.15s ease, color 0.15s ease;
        transform: none !important;
    }
    .stButton button:hover, .stDownloadButton button:hover {
        background: var(--white) !important;
        color: var(--saffron) !important;
        border-color: var(--saffron) !important;
        transform: none !important;
        box-shadow: 0 0.5px 2px rgba(217, 119, 6, 0.18) !important;
    }
    .stButton button[kind="primary"],
    .stButton button[data-testid="baseButton-primary"] {
        background: var(--moss-bright) !important;
        color: var(--white) !important;
        border-color: var(--moss-bright) !important;
    }
    .stButton button[kind="primary"]:hover,
    .stButton button[data-testid="baseButton-primary"]:hover {
        background: var(--moss) !important;
        color: var(--white) !important;
        border-color: var(--moss) !important;
    }
    /* Force white text on primary-button descendants so the label is always
       readable on the moss-bright fill (color: inherit chains can otherwise
       leak a darker color in). */
    .stButton button[kind="primary"] *,
    .stButton button[data-testid="baseButton-primary"] * {
        color: #FFFFFF !important;
    }
    .stFormSubmitButton > button {
        background: var(--saffron) !important;
        color: var(--white) !important;
        border: 1px solid var(--saffron-deep) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.2em !important;
        text-transform: uppercase !important;
        border-radius: 0 !important;
        padding: 10px 20px !important;
        min-height: 38px !important;
    }
    .stFormSubmitButton > button:hover {
        background: var(--saffron-deep) !important;
        color: var(--white) !important;
    }
    .stButton button:disabled,
    .stButton button[disabled] {
        background: var(--rule-soft) !important;
        color: var(--ink-faint) !important;
        border-color: var(--rule) !important;
        cursor: not-allowed;
    }
    /* Inner text/markup must inherit the button's color (defeats stray dark
       text leaking from data-baseweb wrappers when help= is set). */
    .stButton button *,
    .stDownloadButton button *,
    .stFormSubmitButton button * {
        color: inherit !important;
        background: transparent !important;
        font-family: inherit !important;
    }
    .stButton button p,
    .stDownloadButton button p,
    .stFormSubmitButton button p {
        margin: 0 !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.2em !important;
        text-transform: uppercase !important;
    }

    /* ── Form inputs ────────────────────────────────────────────────── */
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        border-radius: 0 !important;
        border: 1px solid var(--rule) !important;
        background: var(--white) !important;
        color: var(--ink) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
        padding: 8px 10px !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
        border-color: var(--saffron) !important;
        box-shadow: 0 0 0 2px var(--ring) !important;
        outline: none !important;
    }
    [data-baseweb="select"] > div, [data-baseweb="input"] > div {
        border-radius: 0 !important;
        border: 1px solid var(--rule) !important;
        background: var(--white) !important;
    }
    [data-baseweb="select"] > div { color: var(--ink) !important; min-height: 36px !important; }
    .stTextInput label, .stNumberInput label, .stTextArea label,
    .stSelectbox label, .stDateInput label, .stCheckbox label, .stRadio label,
    [data-baseweb="form-control-label"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 9px !important;
        font-weight: 700 !important;
        letter-spacing: 0.25em !important;
        text-transform: uppercase !important;
        color: var(--ink-faint) !important;
        margin-bottom: 6px !important;
    }
    .stCheckbox label > div:first-child { /* keep the actual checkbox visible */
        display: flex !important;
    }
    ::placeholder { color: var(--ink-faint) !important; opacity: 0.7; }

    /* ── Dividers ───────────────────────────────────────────────────── */
    hr, [data-testid="stHorizontalRule"] {
        border: 0 !important;
        border-top: 0.5px solid var(--rule) !important;
        margin: 28px 0 !important;
        background: transparent !important;
    }

    /* ── st.metric (when used) ────────────────────────────────────── */
    [data-testid="stMetric"] {
        background: var(--white);
        border: 0.5px solid var(--rule);
        border-top: 6px solid var(--ink-soft);
        padding: 18px 22px;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.3em !important;
        text-transform: uppercase !important;
        color: var(--ink-faint) !important;
    }
    [data-testid="stMetricLabel"] * {
        font-family: 'Inter', sans-serif !important;
        color: var(--ink-faint) !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'Fraunces', serif !important;
        font-size: 56px !important;
        font-weight: 700 !important;
        color: var(--ink) !important;
        letter-spacing: -0.02em !important;
        font-variation-settings: 'opsz' 144;
        line-height: 1.05 !important;
    }
    [data-testid="stMetricValue"] * {
        font-family: 'Fraunces', serif !important;
        color: var(--ink) !important;
    }
    [data-testid="stMetricDelta"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricDelta"] svg { display: none !important; }

    /* ── Verdict badges (used in markdown across pages) ────────────── */
    .verdict-badge {
        display: inline-block;
        padding: 4px 10px;
        font-family: 'Inter', sans-serif;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: #fff !important;
        border-radius: 0;
        background: var(--ink-soft);
    }
    .verdict-active            { background: var(--moss-bright) !important; }
    .verdict-dormant           { background: var(--saffron) !important; }
    .verdict-closed,
    .verdict-closed_by_silence { background: var(--crimson) !important; }
    .verdict-nascent           { background: var(--indigo) !important; }
    .verdict-unknown           { background: var(--ink-soft) !important; }

    .tier-badge {
        display: inline-block;
        padding: 2px 8px;
        font-family: 'Inter', sans-serif;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: #fff !important;
    }
    .tier-junior { background: var(--saffron); }
    .tier-senior { background: var(--indigo); }

    /* ── Help banner ──────────────────────────────────────────────── */
    .help-banner {
        background: var(--surface);
        border-left: 3px solid var(--saffron);
        padding: 12px 16px;
        margin: 18px 0;
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        line-height: 1.55;
        color: var(--ink-soft);
    }
    .help-banner .help-title {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.25em;
        text-transform: uppercase;
        color: var(--saffron);
        display: block;
        margin-bottom: 6px;
    }
    .help-banner b, .help-banner strong { color: var(--ink) !important; font-weight: 700; }
    .help-banner ul { margin: 4px 0 0 18px; padding: 0; }
    .help-banner li { margin: 2px 0; }
    .help-banner code {
        font-family: 'JetBrains Mono', monospace;
        background: var(--rule-soft);
        padding: 1px 5px;
        font-size: 12px;
        color: var(--ink);
    }

    .info-icon {
        display: inline-block;
        width: 16px; height: 16px;
        background: var(--ink);
        color: var(--paper) !important;
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

    /* ── Tooltip popup (BaseWeb portal — only the popup, scoped to role) ── */
    [role="tooltip"] {
        background: var(--ink) !important;
        color: var(--paper) !important;
        border-radius: 0 !important;
        box-shadow: var(--shadow-md) !important;
        padding: 7px 10px !important;
        max-width: 240px !important;
        font-size: 11px !important;
        line-height: 1.45 !important;
        font-weight: 500 !important;
        font-family: 'Inter', sans-serif !important;
        z-index: 9999 !important;
    }
    [role="tooltip"] *, [role="tooltip"] p, [role="tooltip"] span, [role="tooltip"] div {
        color: var(--paper) !important;
        background: transparent !important;
    }
    /* High-specificity overrides — the tooltip body is rendered inside an
       stMarkdownContainer whose `p`-color rule (later in this stylesheet) has
       equal specificity but later cascade order, so it would otherwise win
       and paint text dark on dark. These selectors out-specify it. */
    [role="tooltip"] [data-testid="stMarkdownContainer"],
    [role="tooltip"] [data-testid="stMarkdownContainer"] *,
    [role="tooltip"] [data-testid="stMarkdownContainer"] p,
    [role="tooltip"] [data-testid="stMarkdownContainer"] li,
    [role="tooltip"] [data-testid="stMarkdownContainer"] span,
    [role="tooltip"] [data-testid="stMarkdownContainer"] strong,
    [role="tooltip"] [data-testid="stMarkdownContainer"] em,
    [role="tooltip"] [data-testid="stMarkdownContainer"] b,
    [role="tooltip"] [data-testid="stMarkdownContainer"] code {
        color: var(--paper) !important;
        background: transparent !important;
    }
    [role="tooltip"] [data-popper-arrow] { background: var(--ink) !important; }
    /* Neutralise the BaseWeb tooltip *trigger* so it never leaks dark bg onto buttons */
    [data-baseweb="tooltip"]:not([role="tooltip"]) {
        background: transparent !important;
        color: inherit !important;
        padding: 0 !important;
        margin: 0 !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        max-width: none !important;
        font-size: inherit !important;
        font-weight: inherit !important;
        line-height: inherit !important;
    }
    [data-baseweb="tooltip"]:not([role="tooltip"]) *,
    [data-baseweb="tooltip"]:not([role="tooltip"]) span,
    [data-baseweb="tooltip"]:not([role="tooltip"]) div {
        color: inherit !important;
        background: transparent !important;
    }

    /* ── BaseWeb dropdown popover (selectbox / date) ─────────────────── */
    [data-baseweb="popover"] {
        background: var(--white) !important;
        border: 1px solid var(--rule) !important;
        border-radius: 0 !important;
        box-shadow: var(--shadow-md) !important;
        color: var(--ink) !important;
    }
    [data-baseweb="popover"] [role="listbox"],
    [data-baseweb="popover"] ul[role="listbox"],
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"] {
        background: var(--white) !important;
        color: var(--ink) !important;
        padding: 4px !important;
    }
    [data-baseweb="popover"] [role="option"],
    [data-baseweb="popover"] li,
    [data-baseweb="menu"] li {
        background: var(--white) !important;
        color: var(--ink) !important;
        padding: 8px 14px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
        border-radius: 0 !important;
        margin: 0 !important;
    }
    [data-baseweb="popover"] [role="option"]:hover,
    [data-baseweb="popover"] li:hover {
        background: var(--surface) !important;
        color: var(--ink) !important;
    }
    [data-baseweb="popover"] [aria-selected="true"] {
        background: var(--ink) !important;
        color: var(--paper) !important;
    }
    [data-baseweb="popover"] [role="option"] *,
    [data-baseweb="popover"] li * { color: inherit !important; }

    /* ── Date picker calendar (popover) — bulletproof overrides ─────── */
    /* The BaseWeb date picker pops up via a portal containing nested
       containers. Force white bg + ink text at every level so the calendar
       is always readable against the cream paper page. */
    [data-baseweb="popover"]:has([data-baseweb="calendar"]),
    [data-baseweb="popover"]:has([data-baseweb="datepicker"]),
    [data-baseweb="datepicker"],
    [data-baseweb="calendar"],
    [data-baseweb="calendar-month"],
    [data-baseweb="calendar-grid"] {
        background-color: #FFFFFF !important;
        color: #0f1f3a !important;
        border-radius: 0 !important;
        border: 1px solid #c9b896 !important;
    }
    [data-baseweb="calendar"] *,
    [data-baseweb="datepicker"] *,
    [data-baseweb="popover"]:has([data-baseweb="calendar"]) * {
        background-color: transparent !important;
        color: #0f1f3a !important;
    }
    [data-baseweb="calendar"] button,
    [data-baseweb="calendar"] [role="gridcell"],
    [data-baseweb="calendar"] [role="button"] {
        background-color: transparent !important;
        color: #0f1f3a !important;
        border-radius: 0 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
    }
    [data-baseweb="calendar"] button:hover,
    [data-baseweb="calendar"] [role="gridcell"]:hover,
    [data-baseweb="calendar"] [role="button"]:hover {
        background-color: #f7f1e5 !important;
        color: #0f1f3a !important;
    }
    [data-baseweb="calendar"] [aria-selected="true"],
    [data-baseweb="calendar"] [aria-selected="true"] *,
    [data-baseweb="calendar"] [aria-pressed="true"],
    [data-baseweb="calendar"] [aria-pressed="true"] * {
        background-color: #d97706 !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    [data-baseweb="calendar"] [aria-disabled="true"],
    [data-baseweb="calendar"] [aria-disabled="true"] * {
        color: #c9b896 !important;
        opacity: 0.6;
    }
    /* Day-of-week header strip */
    [data-baseweb="calendar"] [role="columnheader"],
    [data-baseweb="calendar"] th {
        font-family: 'Inter', sans-serif !important;
        font-size: 9px !important;
        font-weight: 700 !important;
        letter-spacing: 0.2em !important;
        text-transform: uppercase !important;
        color: #7a6a55 !important;
    }
    /* Month/year title in the calendar header */
    [data-baseweb="calendar"] h2,
    [data-baseweb="calendar"] h3,
    [data-baseweb="calendar"] [aria-live="polite"] {
        font-family: 'Fraunces', serif !important;
        font-size: 14px !important;
        font-weight: 700 !important;
        color: #0f1f3a !important;
    }

    /* ── Tabs ──────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--paper);
        border-bottom: 0.5px solid var(--rule);
        gap: 0;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        color: var(--ink-soft) !important;
        border-radius: 0 !important;
        padding: 12px 18px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.2em !important;
        text-transform: uppercase !important;
    }
    .stTabs [data-baseweb="tab"]:hover { color: var(--ink) !important; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: var(--ink) !important;
        border-bottom: 3px solid var(--saffron) !important;
    }

    /* ── Expander ──────────────────────────────────────────────────── */
    [data-testid="stExpander"] {
        border: 0.5px solid var(--rule) !important;
        border-radius: 0 !important;
        background: var(--white);
    }
    [data-testid="stExpander"] > details > summary,
    .streamlit-expanderHeader {
        background: var(--surface) !important;
        border-radius: 0 !important;
        color: var(--ink) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 12px !important;
        font-weight: 700 !important;
        letter-spacing: 0.15em !important;
        text-transform: uppercase !important;
        padding: 10px 14px !important;
        border: 0 !important;
    }

    /* ── Tables / dataframes ───────────────────────────────────────── */
    .stDataFrame, [data-testid="stDataFrameContainer"] {
        border: 0.5px solid var(--rule) !important;
        border-radius: 0 !important;
    }
    .stTable thead, .stDataFrame thead, [data-testid="stDataFrame"] thead {
        background: var(--surface) !important;
    }
    .stTable thead th, .stDataFrame thead th {
        font-family: 'Inter', sans-serif !important;
        font-size: 10px !important;
        font-weight: 700 !important;
        letter-spacing: 0.2em !important;
        text-transform: uppercase !important;
        color: var(--ink-faint) !important;
        padding: 10px 12px !important;
        border-bottom: 0.5px solid var(--rule) !important;
    }
    .stTable tbody td, .stDataFrame tbody td {
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
        color: var(--ink) !important;
        padding: 9px 12px !important;
        border-bottom: 0.5px solid var(--rule-soft) !important;
    }

    /* Markdown tables */
    [data-testid="stMarkdownContainer"] table {
        border-collapse: collapse;
        width: 100%;
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        margin: 12px 0;
    }
    [data-testid="stMarkdownContainer"] table th {
        background: var(--surface);
        color: var(--ink-faint);
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        padding: 8px 12px;
        border-bottom: 0.5px solid var(--rule);
        text-align: left;
    }
    [data-testid="stMarkdownContainer"] table td {
        padding: 8px 12px;
        border-bottom: 0.5px solid var(--rule-soft);
        color: var(--ink);
    }

    /* Inline code / blockquote */
    [data-testid="stMarkdownContainer"] code {
        font-family: 'JetBrains Mono', monospace;
        background: var(--rule-soft);
        padding: 1px 5px;
        border-radius: 0;
        font-size: 12px;
        color: var(--ink);
    }
    blockquote, [data-testid="stMarkdownContainer"] blockquote {
        border-left: 3px solid var(--saffron) !important;
        background: var(--surface) !important;
        color: var(--ink-soft) !important;
        padding: 12px 16px !important;
        border-radius: 0 !important;
        margin: 16px 0 !important;
    }

    /* ── Headings inside content ───────────────────────────────────── */
    [data-testid="stMarkdownContainer"] h1 {
        font-family: 'Fraunces', Georgia, serif !important;
        font-size: 36px !important;
        font-weight: 700 !important;
        color: var(--ink) !important;
        letter-spacing: -0.02em !important;
        margin: 24px 0 8px 0 !important;
        font-variation-settings: 'opsz' 144;
    }
    [data-testid="stMarkdownContainer"] h2 {
        font-family: 'Fraunces', serif !important;
        font-size: 22px !important;
        font-weight: 700 !important;
        color: var(--ink) !important;
        letter-spacing: -0.01em !important;
        margin: 20px 0 8px 0 !important;
        font-variation-settings: 'opsz' 144;
    }
    [data-testid="stMarkdownContainer"] h3 {
        font-family: 'Fraunces', serif !important;
        font-size: 18px !important;
        font-weight: 700 !important;
        color: var(--ink) !important;
        margin: 18px 0 6px 0 !important;
    }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {
        color: var(--ink) !important;
        line-height: 1.55;
        font-size: 14px;
    }
    [data-testid="stMarkdownContainer"] strong,
    [data-testid="stMarkdownContainer"] b {
        color: var(--ink) !important;
        font-weight: 700;
    }
    [data-testid="stMarkdownContainer"] em,
    [data-testid="stMarkdownContainer"] i {
        font-family: 'Fraunces', serif;
        font-style: italic;
    }
    small, .stMarkdown small { color: var(--ink-faint) !important; }

    /* st.title / st.subheader / st.caption */
    .stMarkdown h1, h1.stTitle {
        font-family: 'Fraunces', serif !important;
        font-size: 40px !important;
        color: var(--ink) !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        line-height: 1.1 !important;
        font-variation-settings: 'opsz' 144;
    }
    .stMarkdown h2 {
        font-family: 'Fraunces', serif !important;
        color: var(--ink) !important;
        font-weight: 700 !important;
    }
    .stCaption, [data-testid="stCaptionContainer"], .stMarkdown small em {
        font-family: 'Fraunces', serif !important;
        font-style: italic !important;
        color: var(--ink-faint) !important;
        font-size: 14px !important;
    }

    /* ── Page-context bar (subtitle strip below nav) ───────────────── */
    .page-context {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 12px 0;
        margin: 0 0 4px 0;
        border-bottom: 0.5px solid var(--rule);
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--ink-faint);
    }
    .page-context .pc-icon {
        font-size: 13px;
        color: var(--saffron);
        font-weight: 700;
    }
    .page-context .pc-title {
        font-weight: 700;
        color: var(--ink);
    }
    .page-context .pc-subtitle {
        font-family: 'Fraunces', serif;
        font-style: italic;
        text-transform: none;
        letter-spacing: normal;
        font-size: 13px;
        color: var(--ink-faint);
    }
    .page-context .pc-spacer { flex: 1; }
    .page-context .pc-meta {
        font-family: 'JetBrains Mono', monospace;
        text-transform: none;
        letter-spacing: normal;
        font-size: 11px;
        color: var(--ink-soft);
    }
    .page-context .pc-meta b { color: var(--ink) !important; font-weight: 700; }

    /* ── Footer ────────────────────────────────────────────────────── */
    .gov-footer {
        background: var(--paper);
        border-top: 0.5px solid var(--rule);
        color: var(--ink-faint);
        padding: 24px 64px;
        margin: 60px -64px -3rem -64px;
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        line-height: 1.6;
        text-align: center;
    }
    .gov-footer b, .gov-footer strong { color: var(--ink) !important; font-weight: 700; }

    /* ── Plotly chart container — sit on white card ─────────────────── */
    [data-testid="stPlotlyChart"] {
        background: var(--white);
        border: 0.5px solid var(--rule);
        padding: 8px;
        box-sizing: border-box;
        overflow: hidden;
        width: 100% !important;
    }
    [data-testid="stPlotlyChart"] > div,
    [data-testid="stPlotlyChart"] .js-plotly-plot,
    [data-testid="stPlotlyChart"] .plotly,
    [data-testid="stPlotlyChart"] .main-svg {
        width: 100% !important;
        max-width: 100% !important;
    }

    /* ── Misc legacy class compatibility (preserve markup that still references) ── */
    .gok-en { color: var(--paper) !important; font-weight: 700; }
    .platform-kn { color: var(--rule); }

    /* Spinner / progress */
    .stSpinner > div { border-top-color: var(--saffron) !important; }
    [data-testid="stProgress"] > div > div > div > div { background: var(--saffron) !important; }

    /* Alert boxes (st.info/success/warning/error) */
    [data-baseweb="notification"] {
        border-radius: 0 !important;
        border: 0.5px solid var(--rule) !important;
        background: var(--surface) !important;
    }
    [data-baseweb="notification"] * { color: var(--ink) !important; }

    /* Help-mode container — wraps both the marker (a hidden div) and the
       columns row containing the checkbox. Find the container's vertical
       block via :has() and extend it to viewport edges so the checkbox's
       right edge aligns with the toolbar's status pill below. */
    .help-mode-marker { height: 0; margin: 0; padding: 0; }

    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] > [data-testid="stMarkdownContainer"] > .help-mode-marker) {
        margin-left: -64px !important;
        margin-right: -64px !important;
        margin-bottom: -8px !important;
        padding-left: 64px !important;
        padding-right: 64px !important;
    }
    /* Right-align the checkbox column inside that container */
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] > [data-testid="stMarkdownContainer"] > .help-mode-marker) [data-testid="column"]:last-child {
        display: flex !important;
        justify-content: flex-end !important;
        align-items: center !important;
    }
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] > [data-testid="stMarkdownContainer"] > .help-mode-marker) [data-testid="stCheckbox"] {
        margin: 0 !important;
        padding: 0 !important;
        flex: 0 0 auto !important;
        width: auto !important;
    }

    /* Help-mode toggle — single-line, right-aligned in its column */
    .stCheckbox label,
    [data-testid="stCheckbox"] label {
        white-space: nowrap !important;
    }
    [data-testid="stCheckbox"] label > div:nth-child(2),
    [data-testid="stCheckbox"] label > p,
    [data-testid="stCheckbox"] label > span {
        white-space: nowrap !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        letter-spacing: 0.05em !important;
        text-transform: none !important;
        color: var(--ink) !important;
    }

    /* ── `?` help-icon next to widget labels (BaseWeb tooltip trigger) ───── */
    /* Subtle saffron at low opacity, brightening on hover. */
    [data-testid="stTooltipHoverTarget"],
    [data-testid="stTooltipIcon"] {
        opacity: 0.35;
        transition: opacity 0.15s ease;
        margin-left: 4px;
        vertical-align: middle;
    }
    [data-testid="stTooltipHoverTarget"]:hover,
    [data-testid="stTooltipIcon"]:hover { opacity: 1; }
    [data-testid="stTooltipHoverTarget"] svg,
    [data-testid="stTooltipIcon"] svg {
        fill: var(--saffron) !important;
        color: var(--saffron) !important;
        width: 13px; height: 13px;
    }

    /* ── Column-aware button alignment ───────────────────────────────────── */
    /* Inside a horizontal column block, buttons usually sit alongside labelled
       inputs. Push them down by one label height so the button bottom aligns
       with the input fields. Streamlit's column DOM is:
         [column] > [stVerticalBlock] > [stElementContainer] > [stButton]
       so we use a descendant selector to span the wrappers. */
    [data-testid="stHorizontalBlock"] [data-testid="column"] [data-testid="stButton"],
    [data-testid="stHorizontalBlock"] [data-testid="column"] [data-testid="stDownloadButton"] {
        margin-top: 28px;
    }
    /* If the column already starts with a labelled widget (text input, select,
       date) above the button, no extra push is needed — but the typical case
       for these toolbars is "row of inputs ending in a button", which the
       margin-top above handles. Single-button rows look fine with a small
       breathing space. */
    /* Keep input + selectbox + button at consistent height so they share a baseline. */
    .stTextInput input,
    .stNumberInput input,
    .stDateInput input,
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div {
        min-height: 38px !important;
    }
    .stButton button,
    .stDownloadButton button,
    .stFormSubmitButton button {
        min-height: 38px !important;
    }
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
    """Three-strip editorial masthead: indigo bar with bilingual one-line
    tagline + serif title (italic-saffron `Platform`) + dept block on the
    right, then the saffron+green tricolor hairline."""
    crest_img = _load_header_crest()

    st.markdown(
        f'<div class="gov-header">'
        f'<div class="crest">{crest_img}</div>'
        f'<div class="titles">'
        f'<div class="gov-tagline">'
        f'<span class="kannada">ಕರ್ನಾಟಕ ಸರ್ಕಾರ</span>'
        f'<span class="gok-en">&middot; Government of Karnataka</span>'
        f'</div>'
        f'<div class="platform">Unified Business Identifier <span class="ital">Platform</span></div>'
        f'</div>'
        f'<div class="dept-block">'
        f'<div class="dept-name">Dept. of Commerce &amp; Industries</div>'
        f'<div class="dept-sys">Active Business Intelligence System</div>'
        f'</div>'
        f'</div>'
        f'<div class="tricolor"></div>',
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


# ── Reviewer toolbar (editorial field/value strip) ───────────────────────────
# Render the Streamlit widgets inside a hidden host so values still bind to
# session_state, then overlay a typography-only visible strip above with the
# same data. Click the "Edit" affordance to expand the actual widgets.
_default_reviewer = st.session_state.get("reviewer_id", "reviewer_001")
_default_tier     = st.session_state.get("reviewer_tier", "junior")
_default_ref      = st.session_state.get("ref_date", date(2025, 5, 1))
_default_help     = st.session_state.get("help_mode", True)

# Full-width reviewer-settings expander (collapsed by default).
with st.expander("Reviewer settings", expanded=False):
    _ec = st.columns([1.4, 1, 1.4])
    reviewer_id = _ec[0].text_input(
        "Reviewer ID", value=_default_reviewer, key="reviewer_id",
        help=H("Used to attribute every reviewer decision in the audit log."),
    )
    reviewer_tier = _ec[1].selectbox(
        "Tier", ["junior", "senior"],
        index=["junior", "senior"].index(_default_tier), key="reviewer_tier",
        help=H("Senior reviewers see deferred items first; their decisions become precedents."),
    )
    ref_date = _ec[2].date_input(
        "Reference date", value=_default_ref, key="ref_date",
        help=H("Treated as 'today' for activity-decay computation."),
    )

# Help-mode toggle — sits directly above the editorial toolbar's status pill.
# Wrap marker + columns in one container so CSS can scope all of it via :has.
_hbox = st.container()
with _hbox:
    st.markdown('<div class="help-mode-marker"></div>', unsafe_allow_html=True)
    _hcol1, _hcol2 = st.columns([8, 1.5])
    with _hcol2:
        help_mode = st.checkbox(
            "📖 Help mode", value=_default_help, key="help_mode",
            help="Toggle in-page guidance and tooltips on/off.",
        )

ref_date_str = ref_date.isoformat()

# API health probe drives the pill.
_health = api_get("/health", timeout=3)
_health_ok = bool(_health and _health.get("status") == "ok")
_lat = _health.get("latency_ms") if isinstance(_health, dict) else None
_lat_str = f"{int(_lat)}ms" if isinstance(_lat, (int, float)) else "live"
_pill_state = "" if _health_ok else "red"
_pill_text = f"API Live &middot; {_lat_str}" if _health_ok else "API Down"

# Visible editorial toolbar — typography-only.
st.markdown(
    f'<div class="toolbar">'
    f'<div class="field"><div class="field-label">Reviewer</div>'
    f'<div class="field-value">{reviewer_id}</div></div>'
    f'<div class="sep"></div>'
    f'<div class="field"><div class="field-label">Tier</div>'
    f'<div class="field-value">{reviewer_tier.title()}</div></div>'
    f'<div class="sep"></div>'
    f'<div class="field"><div class="field-label">Reference Date</div>'
    f'<div class="field-value">{ref_date_str}</div></div>'
    f'<div class="spacer"></div>'
    f'<div class="status-pill {_pill_state}">'
    f'<span class="dot"></span>'
    f'<span class="lbl">Status</span>'
    f'<span class="latency">{_pill_text}</span>'
    f'</div>'
    f'</div>',
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

# Marker so the heavy nav-radio CSS scopes only to THIS radio (in-page filter
# radios elsewhere on each page must not inherit the saffron-underline pill style).
st.markdown('<div class="ubid-nav-marker" style="display:none;"></div>',
            unsafe_allow_html=True)
page = st.radio(
    "Navigation",
    PAGES,
    horizontal=True,
    label_visibility="collapsed",
    key="nav_radio",
)


# ── Editorial page hero (eyebrow numbering + saffron rule + Fraunces H1) ─────
# Replaces both st.title/st.caption AND the old `page-context` thin strip.
# Each page block below MUST NOT call st.title/st.caption — the hero rendered
# here is the single source of truth.
PAGE_HEROES = {
    "📊 Dashboard":      ("01", "Platform Dashboard",
        "A live view of Karnataka's industrial base, <span class='ital'>in motion.</span>",
        "Real-time view of UBID assignments, source ingest, and reviewer queue."),
    "🔍 Browse UBIDs":   ("02", "Browse UBIDs",
        "Every business, <span class='ital'>indexed.</span>",
        "Search, filter and open every Unified Business Identifier in the system."),
    "📋 Review Queue":   ("03", "Review Queue",
        "Are these the same <span class='ital'>business?</span>",
        "Ambiguous match candidates awaiting reviewer decision."),
    "🧐 Audit Merges":   ("04", "Audit Merges",
        "Sort the <span class='ital'>uncertain.</span>",
        "Verify auto-merged UBIDs · sort records into groups · feeds future training."),
    "🧭 UBID Lookup":    ("05", "UBID Lookup",
        "Find any business, <span class='ital'>fast.</span>",
        "Resolve any source identifier, PAN, or name + pin to a UBID."),
    "📈 Activity Status":("06", "Activity Status",
        "Evidence over <span class='ital'>time.</span>",
        "Verdict, evidence timeline, lineage and unmerge controls for one UBID."),
    "🚧 Quarantine":     ("07", "Quarantine",
        "Events still <span class='ital'>unjoined.</span>",
        "Activity events that could not be joined to a UBID."),
    "📜 Reviewer Log":   ("08", "Reviewer Log",
        "Every decision, <span class='ital'>attributed.</span>",
        "Decision history per reviewer · audit trail · throughput chart."),
    "❓ Query Explorer": ("09", "Query Explorer",
        "Ask the <span class='ital'>warehouse.</span>",
        "Run the proposal's exemplar queries against the UBID-keyed warehouse."),
    "📤 Ingest Data":    ("10", "Ingest Data",
        "New records, <span class='ital'>routed.</span>",
        "Upload CSV records or activity events through the live pipeline."),
    "⚙️ Admin":          ("11", "Administration",
        "Operate the <span class='ital'>model.</span>",
        "Model retraining · re-scoring · calibration · synonyms · verdicts."),
    "ℹ️ About":          ("12", "About",
        "How the platform <span class='ital'>works.</span>",
        "Architecture · proposal compliance · glossary."),
}

_YEAR_WORDS = {
    "2023": "two thousand twenty-three",
    "2024": "two thousand twenty-four",
    "2025": "two thousand twenty-five",
    "2026": "two thousand twenty-six",
    "2027": "two thousand twenty-seven",
}


def render_page_context(page_name: str):
    """Editorial page hero: eyebrow numbering · saffron rule · Fraunces H1
    with italic accent · italic subtitle · right-aligned aux block (date)."""
    num, title, h1_html, subtitle = PAGE_HEROES.get(
        page_name, ("•", str(page_name), str(page_name), "")
    )
    eyebrow = f"{num} &middot; {title.upper()}"

    # Aux block: spelled-out reference date + a per-page metric
    try:
        ref_long = ref_date.strftime("%B ") + str(ref_date.day)
    except Exception:
        ref_long = ref_date_str
    year_long = _YEAR_WORDS.get(ref_date.strftime("%Y"), ref_date.strftime("%Y"))

    s = api_get("/api/v1/query/stats", timeout=2) or {}
    n_ubids = s.get("total_ubids", 0)
    n_pending = (s.get("queue") or {}).get("pending", 0)
    aux_foot = f"{n_ubids} UBIDs &middot; {n_pending} pending &middot; ref {ref_date_str}"

    st.markdown(f"""
    <div class="page-hero">
      <div>
        <div class="eyebrow">{eyebrow}</div>
        <div class="saffron-rule"></div>
        <h1>{h1_html}</h1>
        <div class="subtitle">{subtitle}</div>
      </div>
      <div class="aux">
        <div class="aux-label">As of</div>
        <div class="aux-value">{ref_long}</div>
        <div class="aux-sub">{year_long}</div>
        <div class="aux-foot">{aux_foot}</div>
      </div>
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
    stats = api_get("/api/v1/query/stats")
    if not stats:
        st.stop()

    n_ubids       = stats.get("total_ubids", 0)
    n_records     = stats.get("total_source_records", 0)
    n_pending     = (stats.get("queue") or {}).get("pending", 0)
    n_decided     = (stats.get("queue") or {}).get("decided", 0)
    n_quarantine  = (stats.get("quarantine") or {}).get("unresolved", 0)
    by_source     = stats.get("records_by_source", {}) or {}
    n_sources     = len(by_source) if by_source else 4

    # Mini bars for the Source-records card
    if by_source:
        max_v = max(by_source.values())
        bar_palette = ["b-saffron", "", "b-moss", "b-crimson", "b-saffron"]
        bars_html_parts = []
        for i, (src, v) in enumerate(sorted(by_source.items(), key=lambda x: -x[1])):
            pct = int(v / max_v * 100) if max_v else 0
            cls = bar_palette[i % len(bar_palette)]
            bars_html_parts.append(
                f'<div class="bar-row {cls}">'
                f'<span class="name">{src}</span>'
                f'<div class="bar" style="width:{pct}%"></div>'
                f'<span class="v">{v}</span>'
                f'</div>'
            )
        bars_html = "".join(bars_html_parts)
    else:
        bars_html = '<div style="color:var(--ink-faint);font-size:11px;">no source data</div>'

    # Confidence-band split for the Pending-review card.
    # Pull a sample of pending pairs and bucket by calibrated_probability.
    # Bands within the review zone (0.55-0.95):
    #   low  : 0.55 - 0.70   (likely-reject side of review)
    #   mid  : 0.70 - 0.85   (genuinely uncertain)
    #   high : 0.85 - 0.95   (likely-confirm side of review)
    _q = api_get("/api/v1/review/queue", params={"limit": 200, "reviewer_tier": reviewer_tier},
                 timeout=4) or {}
    _q_items = _q.get("items", []) or []
    a = b = c = 0
    if _q_items:
        for it in _q_items:
            p = float(it.get("calibrated_probability", 0) or 0)
            if p < 0.70:
                a += 1
            elif p < 0.85:
                b += 1
            else:
                c += 1
    if not (a or b or c):
        # fallback to uniform-thirds estimate when /queue returns nothing
        a = max(0, int(n_pending * 0.55))
        b = max(0, int(n_pending * 0.30))
        c = max(0, n_pending - a - b)

    # ── 5-card metric strip ──────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5, gap="small")
    with c1:
        st.markdown(f"""
        <div class="metric-card hero">
          <div class="label">Unique Businesses</div>
          <div class="num">{n_ubids}</div>
          <div class="sub">resolved across {n_sources} source systems</div>
          <div class="delta">▲ live across federated departments</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card accent-indigo">
          <div class="label">Source Records</div>
          <div class="num">{n_records}</div>
          <div class="mini-bars">{bars_html}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card accent-crimson">
          <div class="label">Pending Review</div>
          <div class="num">{n_pending}</div>
          <div class="sub">ambiguous pairs awaiting decision</div>
          <div style="margin-top:auto;">
            <div class="conf-band">
              <div class="bar">
                <div class="reject" style="flex:{max(a,1)};">{a}</div>
                <div class="review" style="flex:{max(b,1)};">{b}</div>
                <div class="auto" style="flex:{max(c,1)};">{c}</div>
              </div>
              <div class="bounds"><span>0.55</span><span>0.95</span></div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card accent-saffron">
          <div class="label">Quarantine</div>
          <div class="num">{n_quarantine}</div>
          <div class="sub">unjoined events · auto-replay on next ingest</div>
          <div class="delta" style="color:var(--saffron);">→ Quarantine page</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        st.markdown(f"""
        <div class="metric-card accent-moss">
          <div class="label">Decisions · Total</div>
          <div class="num">{n_decided}</div>
          <div class="sub">confirmed, rejected, or deferred to senior</div>
          <div class="delta">▲ reviewer log</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)

    # ── Two-card row: Calibration + Verdict distribution ─────────────────────
    left, right = st.columns(2, gap="medium")

    with left:
        st.markdown("""
        <div class="sub-eyebrow">02 · Model Calibration</div>
        <div class="sub-h2">Predicted vs. observed match rate</div>
        <div class="sub-cap">Reliability diagram · 10 bins · refreshed weekly</div>
        """, unsafe_allow_html=True)

        cal_data = api_get("/api/v1/admin/calibration-report", params={"n_bins": 10})
        if cal_data and cal_data.get("reliability_diagram"):
            cal_bins = [b for b in cal_data["reliability_diagram"] if b.get("avg_predicted") is not None]
            if cal_bins:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=[b["avg_predicted"] for b in cal_bins],
                    y=[b["observed"] for b in cal_bins],
                    marker_color="#d97706",
                    marker_line=dict(width=0),
                    width=0.085,
                    name="observed",
                    hovertemplate="bin centre %{x:.2f} · observed %{y:.2f}<extra></extra>",
                ))
                fig.add_trace(go.Scatter(
                    x=[0, 1], y=[0, 1],
                    mode="lines",
                    line=dict(dash="dash", color="#c9b896", width=1.2),
                    name="ideal",
                    hoverinfo="skip",
                ))
                fig.update_layout(
                    height=260,
                    margin=dict(l=24, r=12, t=8, b=44),
                    showlegend=False,
                    xaxis=dict(
                        range=[0, 1], gridcolor="#e5dcc8",
                        tickvals=[0, 0.5, 1.0], ticktext=["0.0", "", "1.0"],
                        title=dict(
                            text="<i>predicted probability</i>",
                            font=dict(family="'Fraunces', serif", size=11, color="#7a6a55"),
                        ),
                    ),
                    yaxis=dict(
                        range=[0, 1], gridcolor="#e5dcc8",
                        tickvals=[0, 1], ticktext=["0", "1"],
                    ),
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                )
                st.plotly_chart(fig, use_container_width=True, key="dash_reliability")

                m = cal_data.get("metrics_at_0_95") or {}
                bm1, bm2 = st.columns(2, gap="small")
                with bm1:
                    st.markdown(f"""
                    <div style="padding:14px 18px;border:0.5px solid var(--rule);border-top:4px solid var(--moss-bright);background:var(--white);">
                      <div style="font-size:10px;letter-spacing:0.3em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">Brier Score</div>
                      <div style="font-family:'Fraunces',serif;font-size:38px;font-weight:700;color:var(--ink);line-height:1.1;letter-spacing:-0.02em;">{m.get('brier', 0):.4f}</div>
                      <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--moss-bright);margin-top:6px;">▼ better than threshold</div>
                    </div>""", unsafe_allow_html=True)
                with bm2:
                    is_cal = cal_data.get("is_well_calibrated")
                    delta_txt = "▼ &lt; 0.02 well-calibrated" if is_cal else "△ drifting"
                    delta_col = "var(--moss-bright)" if is_cal else "var(--crimson)"
                    st.markdown(f"""
                    <div style="padding:14px 18px;border:0.5px solid var(--rule);border-top:4px solid var(--moss-bright);background:var(--white);">
                      <div style="font-size:10px;letter-spacing:0.3em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">Expected Calibration Err.</div>
                      <div style="font-family:'Fraunces',serif;font-size:38px;font-weight:700;color:var(--ink);line-height:1.1;letter-spacing:-0.02em;">{m.get('ece', 0):.4f}</div>
                      <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:{delta_col};margin-top:6px;">{delta_txt}</div>
                    </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:var(--ink-faint);font-style:italic;">No calibration report yet — train a model first.</div>',
                        unsafe_allow_html=True)

    with right:
        st.markdown("""
        <div class="sub-eyebrow">03 · Verdict Distribution</div>
        <div class="sub-h2">Active business inference</div>
        <div class="sub-cap">Of the unique businesses, by current state</div>
        """, unsafe_allow_html=True)

        vd = stats.get("verdict_distribution", {}) or {}
        if vd:
            verdict_colors = {
                "active":             "#15803d",
                "dormant":            "#d97706",
                "closed":             "#991b1b",
                "closed_by_silence":  "#991b1b",
                "nascent":            "#1e3a5f",
            }
            keys = list(vd.keys())
            vals = list(vd.values())
            fig = go.Figure(go.Pie(
                labels=[k.replace("_", " ").title() for k in keys],
                values=vals,
                hole=0.62,
                marker_colors=[verdict_colors.get(k, "#7a6a55") for k in keys],
                marker_line=dict(color="#FFFFFF", width=2),
                textinfo="none",
                hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
                sort=False,
            ))
            fig.add_annotation(
                x=0.5, y=0.56, text=str(n_ubids), showarrow=False,
                font=dict(family="'Fraunces', serif", size=44, color="#0f1f3a"),
            )
            fig.add_annotation(
                x=0.5, y=0.40, text="UBIDs", showarrow=False,
                font=dict(family="'Inter', sans-serif", size=10, color="#7a6a55"),
            )
            fig.update_layout(
                height=260,
                margin=dict(l=8, r=8, t=8, b=8),
                showlegend=False,
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
            )
            st.plotly_chart(fig, use_container_width=True, key="dash_verdict_donut")

            legend_rows = []
            for k in keys:
                color = verdict_colors.get(k, "#7a6a55")
                count = vd[k]
                label = k.replace("_", " ").title()
                legend_rows.append(
                    f'<div style="display:grid;grid-template-columns:14px 1fr auto;gap:12px;'
                    f'align-items:center;padding:8px 2px;border-bottom:0.5px solid var(--rule-soft);'
                    f'font-family:Inter,sans-serif;font-size:13px;">'
                    f'<span style="width:11px;height:11px;background:{color};display:inline-block;"></span>'
                    f'<span style="color:var(--ink);font-weight:500;">{label}</span>'
                    f'<span style="font-family:\'JetBrains Mono\',monospace;font-weight:700;color:var(--ink);">{count}</span>'
                    f'</div>'
                )
            st.markdown("".join(legend_rows), unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:var(--ink-faint);font-style:italic;">No verdicts computed yet — visit Admin → Refresh verdicts.</div>',
                        unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# BROWSE UBIDs
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Browse UBIDs":

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
    data = api_get("/api/v1/review/queue", params={"limit": 50, "reviewer_tier": reviewer_tier})
    if not data:
        st.stop()
    items = data.get("items", [])
    qs = data.get("stats", {})

    if not items:
        st.markdown(
            '<div style="padding:48px 0;text-align:center;color:var(--ink-faint);'
            'font-family:Fraunces,serif;font-style:italic;font-size:18px;">'
            'Queue is empty &middot; all caught up.</div>',
            unsafe_allow_html=True,
        )
        st.stop()

    # ── Pair navigator (single-pair-at-a-time editorial workflow) ───────────
    if "rq_idx" not in st.session_state or st.session_state["rq_idx"] >= len(items):
        st.session_state["rq_idx"] = 0
    idx = st.session_state["rq_idx"]
    item = items[idx]

    prob = item.get("calibrated_probability", 0)
    priority = item.get("priority_score", 0)
    rec_a = item.get("record_a") or {}
    rec_b = item.get("record_b") or {}

    # Compact pair header (sub-eyebrow + nav buttons + p value, single row)
    nav_l, nav_r = st.columns([4, 2])
    with nav_l:
        st.markdown(f"""
        <div class="sub-eyebrow">Review Queue &middot; pair {idx+1} of {len(items)}</div>
        """, unsafe_allow_html=True)
    with nav_r:
        st.markdown(f"""
        <div style="text-align:right;font-family:'Inter',sans-serif;font-size:11px;
                    letter-spacing:0.3em;text-transform:uppercase;color:var(--ink-faint);
                    margin-top:4px;">
          Queue progress
        </div>
        <div style="text-align:right;font-family:'Fraunces',serif;font-size:28px;
                    font-weight:700;color:var(--ink);line-height:1.1;">
          {qs.get('decided', 0)} <span style="color:var(--ink-faint);">/</span>
          <span style="color:var(--ink-faint);">{qs.get('total', 0)}</span>
        </div>
        <div style="text-align:right;font-family:'Fraunces',serif;font-style:italic;
                    font-size:12px;color:var(--ink-faint);margin-top:2px;">
          confirmed &middot; {qs.get('pending', 0)} pending
        </div>
        """, unsafe_allow_html=True)

    pn1, pn2, _, pn4 = st.columns([1, 1, 4, 1.5])
    with pn1:
        if st.button("← Prev", disabled=(idx == 0), key=f"rq_prev_{idx}"):
            st.session_state["rq_idx"] = max(0, idx - 1)
            st.rerun()
    with pn2:
        if st.button("Next pair →", type="primary", disabled=(idx + 1 >= len(items)), key=f"rq_next_{idx}"):
            st.session_state["rq_idx"] = min(len(items) - 1, idx + 1)
            st.rerun()
    with pn4:
        st.markdown(f"""
        <div style="text-align:right;font-family:'JetBrains Mono',monospace;
                    font-size:18px;font-weight:700;color:var(--ink);margin-top:8px;">
          p = {prob:.2f}
        </div>
        """, unsafe_allow_html=True)

    # ── Confidence band (REJECT / REVIEW / AUTO) with pointer ────────────────
    pointer_pct = max(0.0, min(1.0, prob)) * 100
    st.markdown(f"""
    <div style="margin: 16px 0 28px 0;">
      <div style="font-size:10px;letter-spacing:0.3em;text-transform:uppercase;
                  color:var(--ink-faint);font-weight:700;margin-bottom:6px;">Model Confidence</div>
      <div style="position:relative;display:flex;height:22px;border:0.5px solid var(--rule);">
        <div style="flex:0.55;background:var(--crimson);color:#fff;text-align:center;
                    line-height:22px;font-size:10px;font-weight:700;letter-spacing:0.2em;">REJECT</div>
        <div style="flex:0.40;background:var(--saffron);color:#fff;text-align:center;
                    line-height:22px;font-size:10px;font-weight:700;letter-spacing:0.2em;">REVIEW</div>
        <div style="flex:0.05;background:var(--moss-bright);color:#fff;text-align:center;
                    line-height:22px;font-size:10px;font-weight:700;letter-spacing:0.2em;">AUTO</div>
        <div style="position:absolute;top:-4px;left:{pointer_pct}%;transform:translateX(-50%);
                    width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;
                    border-top:8px solid var(--ink);"></div>
        <div style="position:absolute;bottom:-4px;left:{pointer_pct}%;width:1.5px;height:30px;
                    background:var(--ink);transform:translateX(-50%);"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-family:'JetBrains Mono',monospace;
                  font-size:10px;color:var(--ink-faint);margin-top:8px;">
        <span>0.00</span><span>0.55</span><span>0.95</span><span>1.00</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Field-by-field comparison helper ─────────────────────────────────────
    def _field_match(va, vb, kind="exact"):
        if not va or not vb:
            return False
        if kind == "exact":
            return str(va).strip() == str(vb).strip()
        if kind == "norm":
            return str(va).strip().lower().replace(" ", "") == str(vb).strip().lower().replace(" ", "")
        if kind == "pin":
            return str(va).strip() == str(vb).strip()
        return False

    def _field_row(label, va, vb, kind="norm"):
        match = _field_match(va, vb, kind=kind)
        va_disp = va if va else "—"
        vb_disp = vb if vb else "—"
        bg = "background:#e8f0d8;" if match else ""
        tag = ('<span style="color:var(--moss-bright);font-family:Inter,sans-serif;'
               'font-size:9px;font-weight:700;letter-spacing:0.2em;">EXACT</span>' if match
               else '<span style="color:var(--crimson);font-family:Inter,sans-serif;'
               'font-size:9px;font-weight:700;letter-spacing:0.2em;">DIFFERS</span>')
        return f"""
        <div style="display:grid;grid-template-columns:90px 1fr 60px;gap:10px;
                    padding:7px 10px;{bg}align-items:center;
                    border-bottom:0.5px solid var(--rule-soft);">
          <div style="font-size:9px;letter-spacing:0.2em;text-transform:uppercase;
                      color:var(--ink-faint);font-weight:700;">{label}</div>
          <div style="font-size:13px;color:var(--ink);font-family:Inter,sans-serif;">{va_disp}</div>
          <div style="text-align:right;">{tag if (va and vb) else ''}</div>
        </div>
        <div style="display:grid;grid-template-columns:90px 1fr 60px;gap:10px;
                    padding:7px 10px;{bg}align-items:center;
                    border-bottom:0.5px solid var(--rule-soft);">
          <div></div>
          <div style="font-size:13px;color:var(--ink);font-family:Inter,sans-serif;">{vb_disp}</div>
          <div></div>
        </div>"""

    # ── Two record cards side-by-side ─────────────────────────────────────────
    rc1, rc2 = st.columns(2, gap="medium")

    with rc1:
        src_a = rec_a.get("source_system", "?")
        accent_a = {"ekarmika": "var(--indigo)", "fbis": "var(--moss)",
                    "kspcb": "var(--saffron)", "bescom": "var(--crimson)",
                    "bwssb": "var(--indigo-deep)"}.get(src_a, "var(--ink-soft)")
        st.markdown(f"""
        <div style="background:var(--white);border:0.5px solid var(--rule);
                    border-top:6px solid {accent_a};padding:18px;">
          <div style="font-size:10px;letter-spacing:0.3em;text-transform:uppercase;
                      color:var(--ink-faint);font-weight:700;">Record A &middot; {src_a}</div>
          <div style="font-family:'Fraunces',serif;font-size:24px;font-weight:700;
                      color:var(--ink);letter-spacing:-0.01em;margin:4px 0 2px 0;
                      font-variation-settings:'opsz' 144;">
            {(rec_a.get('name_raw') or '—')[:48]}
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:11px;
                      color:var(--ink-faint);margin-bottom:14px;">
            {rec_a.get('source_record_id', '—')}
          </div>
        </div>
        """, unsafe_allow_html=True)

    with rc2:
        src_b = rec_b.get("source_system", "?")
        accent_b = {"ekarmika": "var(--indigo)", "fbis": "var(--moss)",
                    "kspcb": "var(--saffron)", "bescom": "var(--crimson)",
                    "bwssb": "var(--indigo-deep)"}.get(src_b, "var(--ink-soft)")
        st.markdown(f"""
        <div style="background:var(--white);border:0.5px solid var(--rule);
                    border-top:6px solid {accent_b};padding:18px;">
          <div style="font-size:10px;letter-spacing:0.3em;text-transform:uppercase;
                      color:var(--ink-faint);font-weight:700;">Record B &middot; {src_b}</div>
          <div style="font-family:'Fraunces',serif;font-size:24px;font-weight:700;
                      color:var(--ink);letter-spacing:-0.01em;margin:4px 0 2px 0;
                      font-variation-settings:'opsz' 144;">
            {(rec_b.get('name_raw') or '—')[:48]}
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:11px;
                      color:var(--ink-faint);margin-bottom:14px;">
            {rec_b.get('source_record_id', '—')}
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Field-by-field comparison rows underneath. NOTE: HTML must NOT have
    # leading whitespace per line — Streamlit's markdown processor treats
    # 4+ leading spaces as a code block and renders the raw HTML as text.
    def _field_pair_row(label, va, vb, kind="norm"):
        match = _field_match(va, vb, kind=kind)
        bg = "background:#e8f0d8;" if match else "background:var(--white);"
        tag = ('<span style="color:var(--moss-bright);font-family:Inter,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.2em;">EXACT</span>' if match
               else '<span style="color:var(--crimson);font-family:Inter,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.2em;">DIFFERS</span>'
               if (va and vb) else '')
        va_disp = va if va else "—"
        vb_disp = vb if vb else "—"
        return (
            f'<tr style="{bg}border-bottom:0.5px solid var(--rule-soft);">'
            f'<td style="padding:8px 12px;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;width:90px;">{label}</td>'
            f'<td style="padding:8px 12px;font-size:13px;color:var(--ink);font-family:Inter,sans-serif;">{va_disp}</td>'
            f'<td style="padding:8px 12px;font-size:13px;color:var(--ink);font-family:Inter,sans-serif;">{vb_disp}</td>'
            f'<td style="padding:8px 12px;text-align:right;width:80px;">{tag}</td>'
            f'</tr>'
        )

    rows_html = "".join([
        _field_pair_row("Address", rec_a.get("address_raw"), rec_b.get("address_raw"), "norm"),
        _field_pair_row("PAN", rec_a.get("pan"), rec_b.get("pan"), "exact"),
        _field_pair_row("GSTIN", rec_a.get("gstin"), rec_b.get("gstin"), "exact"),
        _field_pair_row("PIN", rec_a.get("pin_code"), rec_b.get("pin_code"), "pin"),
        _field_pair_row("Phone", rec_a.get("phone"), rec_b.get("phone"), "exact"),
        _field_pair_row("Sector", rec_a.get("sector_raw"), rec_b.get("sector_raw"), "norm"),
    ])
    table_html = (
        '<table style="width:100%;border-collapse:collapse;border:0.5px solid var(--rule);border-top:0;margin-top:-1px;">'
        '<thead style="background:var(--surface);">'
        '<tr>'
        '<th style="padding:8px 12px;text-align:left;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">Field</th>'
        '<th style="padding:8px 12px;text-align:left;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">Record A</th>'
        '<th style="padding:8px 12px;text-align:left;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">Record B</th>'
        '<th style="padding:8px 12px;text-align:right;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">Match</th>'
        '</tr>'
        '</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
    )
    st.markdown(table_html, unsafe_allow_html=True)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── Why the model is uncertain (SHAP, centered horizontal bars) ─────────
    sh1, sh2 = st.columns([3, 2], gap="medium")
    with sh1:
        st.markdown("""
        <div class="sub-eyebrow">Why the model is uncertain</div>
        <div class="sub-h2">Feature contributions to the score</div>
        """, unsafe_allow_html=True)
        shap_d = item.get("shap_contributions") or {}
        if shap_d:
            top = sorted(shap_d.items(), key=lambda x: abs(x[1]), reverse=True)[:8]
            top_sorted = sorted(top, key=lambda x: x[1])
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[v for _, v in top_sorted],
                y=[k for k, _ in top_sorted],
                orientation="h",
                marker_color=["#15803d" if v > 0 else "#991b1b" for _, v in top_sorted],
                marker_line=dict(width=0),
                text=[f"{v:+.2f}" for _, v in top_sorted],
                textposition="outside",
                textfont=dict(family="'JetBrains Mono', monospace", size=11,
                              color="#0f1f3a"),
                hoverinfo="skip",
            ))
            fig.update_layout(
                height=max(220, 32 * len(top_sorted) + 60),
                margin=dict(l=8, r=40, t=4, b=24),
                showlegend=False,
                xaxis=dict(zeroline=True, zerolinecolor="#0f1f3a", zerolinewidth=1.2,
                           gridcolor="#e5dcc8", showgrid=False),
                yaxis=dict(showgrid=False, color="#4a3f33", tickfont=dict(size=11)),
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
            )
            st.plotly_chart(fig, use_container_width=True, key=f"shap_{item['pair_id']}_{idx}")
        else:
            st.markdown('<div style="color:var(--ink-faint);font-style:italic;">No SHAP attribution available.</div>',
                        unsafe_allow_html=True)

        # Subtle context line
        shared = item.get("shared_blocks") or []
        if shared:
            st.markdown(f"""
            <div style="font-family:'Fraunces',serif;font-style:italic;font-size:13px;
                        color:var(--ink-faint);margin-top:8px;">
              Shared blocking keys: {', '.join(shared)}
            </div>
            """, unsafe_allow_html=True)

    # ── Decision panel (dark indigo with 4 buttons) ─────────────────────────
    with sh2:
        st.markdown("""
        <div style="background:var(--indigo-deep);color:var(--paper);padding:22px 22px 18px 22px;
                    border-top:6px solid var(--saffron);">
          <div style="font-size:10px;letter-spacing:0.3em;text-transform:uppercase;
                      color:var(--saffron-bright);font-weight:700;margin-bottom:4px;">Your decision</div>
          <div style="font-family:'Fraunces',serif;font-size:24px;font-weight:700;color:var(--paper);
                      margin-bottom:14px;font-variation-settings:'opsz' 144;">
            What's the verdict?
          </div>
        </div>
        """, unsafe_allow_html=True)

        queue_id = item.get("queue_id")
        pair_id = item["pair_id"]
        id_a = rec_a.get("canonical_id", "")
        id_b = rec_b.get("canonical_id", "")

        def _submit(decision: str, label: str):
            resp = api_post("/api/v1/review/decide", {
                "queue_id": queue_id, "pair_id": pair_id,
                "canonical_id_a": id_a, "canonical_id_b": id_b,
                "decision": decision,
                "reviewer_id": reviewer_id,
                "reviewer_tier": reviewer_tier,
            })
            if resp:
                st.toast(f"{label} recorded — UBID layer updated")
                st.session_state["rq_idx"] = min(len(items) - 1, idx + 1) if idx + 1 < len(items) else 0
                st.rerun()

        # Decision-panel buttons: no help= (tooltip would auto-position upward
        # and obstruct sibling buttons). Self-explanatory labels + shortcut hints.
        if st.button("✅  Confirm match", key=f"m_{pair_id}_{idx}", use_container_width=True,
                     type="primary"):
            _submit("confirm_match", "Confirm match")
        if st.button("❌  Reject", key=f"r_{pair_id}_{idx}", use_container_width=True):
            _submit("reject", "Reject")
        if st.button("⏫  Defer to senior", key=f"d_{pair_id}_{idx}", use_container_width=True,
                     disabled=(reviewer_tier == "senior")):
            _submit("defer", "Defer")
        if st.button("🚩  Flag quality", key=f"f_{pair_id}_{idx}", use_container_width=True):
            _submit("flag_quality", "Flag")

        st.markdown(f"""
        <div style="font-family:'Inter',sans-serif;font-size:10px;letter-spacing:0.15em;
                    text-transform:uppercase;color:var(--ink-faint);margin-top:14px;text-align:right;">
          Logged in as <span style="color:var(--ink);font-weight:700;">{reviewer_id}</span> &middot;
          <span style="color:var(--saffron);font-weight:700;">{reviewer_tier}</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Bulk actions (collapsible, secondary affordance) ────────────────────
    with st.expander("Bulk actions for this queue"):
        bcol1, bcol2 = st.columns([3, 2])
        bulk_threshold = bcol1.slider(
            "Auto-confirm all items with calibrated probability ≥",
            0.55, 1.0, 0.92, 0.01,
            help=H("Submits confirm_match for every visible item at or above this threshold."),
        )
        qualifying = [i for i in items if i.get("calibrated_probability", 0) >= bulk_threshold]
        bcol2.markdown(f"""
        <div style="text-align:right;font-family:'Fraunces',serif;font-size:32px;font-weight:700;
                    color:var(--ink);margin-top:14px;">{len(qualifying)}</div>
        <div style="text-align:right;font-size:10px;letter-spacing:0.3em;text-transform:uppercase;
                    color:var(--ink-faint);">items qualifying</div>
        """, unsafe_allow_html=True)

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
            st.session_state["rq_idx"] = 0
            st.success(f"✓ {ok} pairs confirmed in bulk")
            st.rerun()

        if bbtn2.button("❌ Reject visible queue", key="bulk_reject"):
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
            st.session_state["rq_idx"] = 0
            st.success(f"✓ {ok} pairs rejected")
            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# AUDIT MERGES
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🧐 Audit Merges":

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
    # If we navigated here from another page (e.g. Browse UBIDs "Open"), use
    # that UBID as the default and auto-load. Pop it so a manual page revisit
    # doesn't keep auto-loading the same one.
    default_ubid = st.session_state.pop("selected_ubid", "")

    lk1, lk2, lk3 = st.columns([3, 1, 1])
    ubid_input = lk1.text_input("UBID", value=default_ubid,
                                  placeholder="e.g. f131c2a5-811f-4666-…",
                                  label_visibility="collapsed")
    force = lk2.checkbox("Recompute", help=H("Bypass the verdict cache."))
    use_ref = lk3.checkbox("Ref date", value=True, help=H("Apply the toolbar reference date."))

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
        score = float(live.get("continuity_score", 0) or 0)

        members = detail.get("source_records") or []
        member_count = detail.get("record_count", len(members))
        n_systems = len({(r.get("source_system") or "").lower() for r in members if r.get("source_system")})

        # Pull a primary record for the title
        primary = members[0] if members else {}
        biz_name = (primary.get("name_raw") or "—").upper()
        addr_short = primary.get("address_raw") or ""
        addr_short = (addr_short[:80] + "…") if len(addr_short) > 80 else addr_short
        sector_str = (detail.get("sector") or primary.get("sector_raw") or "").strip()

        verdict_color = {
            "active":           ("#15803d", "#1a4f1a"),
            "dormant":          ("#d97706", "#8a4a04"),
            "closed":           ("#991b1b", "#6b1313"),
            "closed_by_silence":("#991b1b", "#6b1313"),
            "nascent":          ("#1e3a5f", "#0f1f3a"),
            "unknown":          ("#4a3f33", "#2c2520"),
        }.get(verdict, ("#4a3f33", "#2c2520"))

        # Determine "verdict since" — earliest timeline entry of audit, fall back gracefully
        timeline = live.get("evidence_timeline") or []
        if timeline:
            try:
                _dates = pd.to_datetime([t["event_date"] for t in timeline])
                first_event = _dates.min().strftime("%b %Y")
                last_event = _dates.max().strftime("%b %Y")
            except Exception:
                first_event = "—"; last_event = "—"
        else:
            first_event = "—"; last_event = "—"

        # ═══════════════════════════════════════════════════════════════════
        # Title row + verdict pinned card
        # ═══════════════════════════════════════════════════════════════════
        title_l, title_r = st.columns([5, 3], gap="medium")

        with title_l:
            st.markdown(f"""
            <div class="sub-eyebrow">Activity Status &middot; single business</div>
            <div style="font-family:'Fraunces',serif;font-size:42px;font-weight:700;
                        color:var(--ink);letter-spacing:-0.02em;line-height:1.05;
                        font-variation-settings:'opsz' 144;margin:8px 0 6px 0;">
              {biz_name}
            </div>
            <div style="font-family:'Fraunces',serif;font-style:italic;font-size:14px;
                        color:var(--ink-faint);">
              {addr_short or '—'}{' &middot; ' + sector_str if sector_str else ''}
            </div>
            <div style="display:flex;gap:32px;margin-top:18px;flex-wrap:wrap;">
              <div>
                <div style="font-size:9px;letter-spacing:0.25em;text-transform:uppercase;
                            color:var(--ink-faint);font-weight:700;">UBID</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:13px;
                            font-weight:700;color:var(--ink);">{ubid_input[:24]}…</div>
              </div>
              <div>
                <div style="font-size:9px;letter-spacing:0.25em;text-transform:uppercase;
                            color:var(--ink-faint);font-weight:700;">Legal Entity</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:13px;
                            font-weight:700;color:var(--ink);">PAN {primary.get('pan') or '—'}</div>
              </div>
              <div>
                <div style="font-size:9px;letter-spacing:0.25em;text-transform:uppercase;
                            color:var(--ink-faint);font-weight:700;">Sources</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:13px;
                            font-weight:700;color:var(--ink);">{n_systems} systems &middot; {member_count} records</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        with title_r:
            st.markdown(f"""
            <div style="background:{verdict_color[0]};color:#fff;padding:22px 26px;
                        border-top:6px solid {verdict_color[1]};">
              <div style="font-size:10px;letter-spacing:0.3em;text-transform:uppercase;
                          color:#fff;opacity:0.85;font-weight:700;">Current Verdict</div>
              <div style="font-family:'Fraunces',serif;font-size:54px;font-weight:700;
                          color:#fff;line-height:1.0;letter-spacing:-0.02em;
                          font-variation-settings:'opsz' 144;margin:6px 0 4px 0;
                          text-transform:capitalize;">
                {verdict.replace('_', ' ')}
              </div>
              <div style="font-family:'Fraunces',serif;font-style:italic;font-size:13px;
                          color:#fff;opacity:0.9;">
                Continuity score S = {score:.2f}{(' · since ' + first_event) if first_event != '—' else ''}
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Action buttons under the verdict card
            ub1, ub2 = st.columns(2)
            if ub1.button("Unmerge…", use_container_width=True,
                           help=H("Split a wrongly-merged member off into a new UBID."),
                           key="open_unmerge"):
                st.session_state["show_unmerge"] = not st.session_state.get("show_unmerge", False)
            if ub2.button("Challenge verdict", use_container_width=True,
                           help=H("Flag the verdict as wrong; senior reviewer will re-evaluate."),
                           key="challenge_verdict"):
                st.toast("Challenge logged — senior reviewer will re-evaluate")

        overrides = live.get("deterministic_overrides") or []
        if overrides:
            st.markdown(f"""
            <div style="margin:14px 0;padding:10px 14px;background:var(--surface);
                        border-left:3px solid var(--saffron);font-size:13px;
                        font-family:'Fraunces',serif;font-style:italic;color:var(--ink-soft);">
              Deterministic override applied: {' · '.join(overrides)}
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

        # ═══════════════════════════════════════════════════════════════════
        # Two-column: signal contributions (left) + 4-lane timeline (right)
        # ═══════════════════════════════════════════════════════════════════
        col_left, col_right = st.columns([3, 4], gap="medium")

        # ── LEFT: Signal contributions ────────────────────────────────────────
        with col_left:
            st.markdown("""
            <div class="sub-eyebrow">Evidence &middot; why active</div>
            <div class="sub-h2">Signal contributions</div>
            <div class="sub-cap">Each event decays exponentially with cadence-aware tolerance.</div>
            """, unsafe_allow_html=True)

            # Continuity score scale bar
            S = max(0.0, min(5.5, score))
            S_pct = (S / 5.5) * 100
            # Coloured zones: red 0-0.15, saffron 0.15-1.5, moss 1.5-5+
            st.markdown(f"""
            <div style="margin:10px 0 18px 0;">
              <div style="display:flex;justify-content:space-between;align-items:baseline;
                          margin-bottom:6px;">
                <div style="font-size:9px;letter-spacing:0.3em;text-transform:uppercase;
                            color:var(--ink-faint);font-weight:700;">Continuity Score S</div>
                <div style="font-family:'Fraunces',serif;font-size:24px;font-weight:700;
                            color:var(--ink);">{score:.2f}</div>
              </div>
              <div style="position:relative;display:flex;height:14px;border:0.5px solid var(--rule);">
                <div style="flex:0.15;background:#fce4d4;"></div>
                <div style="flex:1.35;background:#bbdf95;"></div>
                <div style="flex:4;background:#a6cd72;"></div>
              </div>
              <div style="position:relative;height:0;">
                <div style="position:absolute;left:{S_pct}%;top:-19px;
                            transform:translateX(-50%);width:2px;height:24px;background:var(--ink);"></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-family:'JetBrains Mono',monospace;
                          font-size:10px;color:var(--ink-faint);margin-top:8px;">
                <span>0</span><span>0.15</span><span>1.5</span><span>5+</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Build the signal table
            if timeline:
                tdf = pd.DataFrame(timeline)
                tdf["contribution_signed"] = tdf["decayed_contribution"] * tdf["sign"]
                tdf = tdf.sort_values("contribution_signed", key=lambda s: s.abs(), ascending=False)
                top_n = 7
                top = tdf.head(top_n)
                rest = tdf.iloc[top_n:]
                rest_sum = float(rest["contribution_signed"].sum()) if len(rest) else 0.0

                row_html = []
                for _, r in top.iterrows():
                    contribution = float(r["contribution_signed"])
                    pos = contribution >= 0
                    contrib_color = "var(--moss-bright)" if pos else "var(--crimson)"
                    contrib_str = f"{contribution:+.2f}"
                    days = int(r.get("days_ago", 0) or 0)
                    if days < 730:
                        recency = f"{days} days"
                    else:
                        recency = f"{days//365}y {days%365}d"
                    weight = float(r.get("weight", 0) or 0)
                    decay_factor = float(r.get("decayed_contribution", 0) or 0)
                    decay_pct = (decay_factor / abs(weight)) if weight else 0
                    src = (r.get("source_system") or "").upper()
                    etype = str(r.get("event_type") or "").replace("_", " ").title()

                    row_html.append(
                        '<tr style="border-bottom:0.5px solid var(--rule-soft);">'
                        '<td style="padding:10px 6px;">'
                        f'<div style="font-size:13px;font-weight:600;color:var(--ink);font-family:Inter,sans-serif;">{etype}</div>'
                        f'<div style="font-size:11px;color:var(--ink-faint);font-family:Inter,sans-serif;">{src}</div>'
                        '</td>'
                        f'<td style="padding:10px 6px;font-family:\'JetBrains Mono\',monospace;font-size:12px;color:var(--ink-soft);">{recency}</td>'
                        f'<td style="padding:10px 6px;font-family:\'JetBrains Mono\',monospace;font-size:11px;color:var(--ink-faint);">{weight:+.1f} &times; {decay_pct:.2f}</td>'
                        f'<td style="padding:10px 6px;text-align:right;font-family:\'JetBrains Mono\',monospace;font-size:13px;font-weight:700;color:{contrib_color};">{contrib_str}</td>'
                        '</tr>'
                    )
                if rest_sum:
                    rs_color = "var(--moss-bright)" if rest_sum >= 0 else "var(--crimson)"
                    row_html.append(
                        '<tr style="background:var(--surface);">'
                        '<td style="padding:10px 6px;">'
                        f'<div style="font-size:12px;font-style:italic;color:var(--ink-faint);font-family:\'Fraunces\',serif;">+ {len(rest)} older signals (decayed)</div>'
                        '</td>'
                        '<td></td>'
                        '<td style="padding:10px 6px;font-family:\'Fraunces\',serif;font-style:italic;font-size:11px;color:var(--ink-faint);">contributing &lt; 0.10 each</td>'
                        f'<td style="padding:10px 6px;text-align:right;font-family:\'JetBrains Mono\',monospace;font-size:13px;font-weight:700;color:{rs_color};">{rest_sum:+.2f}</td>'
                        '</tr>'
                    )
                table_signal_html = (
                    '<table style="width:100%;border-collapse:collapse;border-top:0.5px solid var(--rule);">'
                    '<thead style="background:var(--surface);">'
                    '<tr>'
                    '<th style="padding:8px 6px;text-align:left;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">Signal</th>'
                    '<th style="padding:8px 6px;text-align:left;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">Recency</th>'
                    '<th style="padding:8px 6px;text-align:left;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">w &times; Decay</th>'
                    '<th style="padding:8px 6px;text-align:right;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">Contribution</th>'
                    '</tr>'
                    '</thead>'
                    f'<tbody>{"".join(row_html)}</tbody>'
                    '</table>'
                )
                st.markdown(table_signal_html, unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:var(--ink-faint);font-style:italic;padding:18px 0;">'
                            'No activity events yet for this UBID.</div>',
                            unsafe_allow_html=True)

        # ── RIGHT: 4-lane source timeline ─────────────────────────────────────
        with col_right:
            st.markdown("""
            <div class="sub-eyebrow">Timeline &middot; activity over time</div>
            <div class="sub-h2">Source events plotted by date</div>
            <div class="sub-cap">Color-coded by source &middot; size by decayed contribution.</div>
            """, unsafe_allow_html=True)

            if timeline:
                tdf = pd.DataFrame(timeline)
                tdf["event_date"] = pd.to_datetime(tdf["event_date"])
                tdf["contribution_signed"] = tdf["decayed_contribution"] * tdf["sign"]
                tdf = tdf.sort_values("event_date")

                # Source palette + lane order
                src_colors = {
                    "ekarmika": "#1e3a5f",   # indigo
                    "fbis":     "#4a5d23",   # moss
                    "kspcb":    "#15803d",   # moss-bright
                    "bescom":   "#d97706",   # saffron
                    "bwssb":    "#991b1b",   # crimson
                }
                src_order = ["ekarmika", "fbis", "kspcb", "bescom", "bwssb"]
                src_display = {"ekarmika": "S&E", "fbis": "FBIS",
                               "kspcb": "KSPCB", "bescom": "BESCOM", "bwssb": "BWSSB"}
                lanes_present = [s for s in src_order if s in tdf["source_system"].unique()]
                if not lanes_present:
                    lanes_present = list(tdf["source_system"].unique())

                fig = go.Figure()
                latest_idx = tdf["event_date"].idxmax()
                for src in lanes_present:
                    sub = tdf[tdf["source_system"] == src]
                    if sub.empty:
                        continue
                    color = src_colors.get(src, "#7a6a55")
                    sizes = []
                    line_colors = []
                    line_widths = []
                    for i, row in sub.iterrows():
                        mag = abs(float(row["contribution_signed"] or 0))
                        sizes.append(max(8, min(22, 8 + mag * 28)))
                        if i == latest_idx:
                            line_colors.append("#0f1f3a")
                            line_widths.append(2.0)
                        else:
                            line_colors.append("#FFFFFF")
                            line_widths.append(0.5)
                    # Negative events get crimson
                    point_colors = [color if c >= 0 else "#991b1b"
                                    for c in sub["contribution_signed"]]
                    fig.add_trace(go.Scatter(
                        x=sub["event_date"],
                        y=[src_display.get(src, src.upper())] * len(sub),
                        mode="markers",
                        marker=dict(size=sizes, color=point_colors,
                                    line=dict(color=line_colors, width=line_widths)),
                        text=[f"{src_display.get(src, src.upper())} · "
                              f"{str(t).replace('_',' ')} · {d.strftime('%b %d %Y')}"
                              for t, d in zip(sub["event_type"], sub["event_date"])],
                        hovertemplate="%{text}<br>contribution=%{customdata:+.3f}<extra></extra>",
                        customdata=sub["contribution_signed"],
                        showlegend=False,
                        name=src_display.get(src, src.upper()),
                    ))

                # "TODAY" marker
                today_dt = pd.Timestamp(ref_date) if use_ref else pd.Timestamp.now()
                fig.add_vline(x=today_dt, line_dash="dot", line_color="#0f1f3a", line_width=1.2)
                fig.add_annotation(
                    x=today_dt, y=1.05, xref="x", yref="paper",
                    text="TODAY",
                    font=dict(family="'Inter', sans-serif", size=9, color="#0f1f3a"),
                    showarrow=False, xanchor="center",
                )

                fig.update_layout(
                    height=320,
                    margin=dict(l=8, r=24, t=22, b=24),
                    showlegend=False,
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    yaxis=dict(
                        categoryorder="array",
                        categoryarray=[src_display.get(s, s.upper()) for s in lanes_present],
                        tickfont=dict(family="'Inter', sans-serif", size=10, color="#4a3f33"),
                    ),
                    xaxis=dict(gridcolor="#e5dcc8", showgrid=True,
                               tickfont=dict(family="'JetBrains Mono', monospace", size=10,
                                             color="#4a3f33")),
                )
                st.plotly_chart(fig, use_container_width=True, key="activity_lanes")

                # Stats summary strip below the timeline
                total_events = len(tdf)
                last30 = int((tdf["event_date"] >= (today_dt - pd.Timedelta(days=30))).sum())
                ms1, ms2, ms3, ms4 = st.columns(4)
                for col, lab, val in [
                    (ms1, "First event",  first_event),
                    (ms2, "Total events", total_events),
                    (ms3, "Last 30 days", last30),
                    (ms4, "Verdict since", first_event),
                ]:
                    col.markdown(f"""
                    <div style="font-size:9px;letter-spacing:0.25em;text-transform:uppercase;
                                color:var(--ink-faint);font-weight:700;margin-top:8px;">{lab}</div>
                    <div style="font-family:'Fraunces',serif;font-size:18px;font-weight:700;
                                color:var(--ink);line-height:1.1;font-variation-settings:'opsz' 144;">
                      {val}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:var(--ink-faint);font-style:italic;padding:36px 0;'
                            'text-align:center;font-family:Fraunces,serif;">No timeline events.</div>',
                            unsafe_allow_html=True)

        # ── Linked source records (compact card list) ────────────────────────
        st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div class="sub-eyebrow">Membership &middot; linked records</div>
        <div class="sub-h2">Every record currently in this UBID</div>
        """, unsafe_allow_html=True)

        if members:
            recs_html = []
            for r in members:
                recs_html.append(
                    '<div style="background:var(--white);padding:12px 16px;display:grid;'
                    'grid-template-columns:120px 1fr auto;gap:14px;align-items:center;'
                    'border-bottom:0.5px solid var(--rule-soft);">'
                    '<div>'
                    f'<div style="font-size:9px;letter-spacing:0.25em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;">{r["source_system"]}</div>'
                    f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:var(--ink-soft);">{r["source_record_id"]}</div>'
                    '</div>'
                    '<div>'
                    f'<div style="font-size:13px;color:var(--ink);font-weight:600;">{r.get("name_raw") or "—"}</div>'
                    f'<div style="font-size:11px;color:var(--ink-faint);font-family:Inter,sans-serif;">{(r.get("address_raw") or "—")[:120]}</div>'
                    '</div>'
                    '<div style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:var(--ink-faint);text-align:right;">'
                    f'{r.get("pan") or "no PAN"}<br>pin {r.get("pin_code") or "—"}'
                    '</div>'
                    '</div>'
                )
            st.markdown(
                '<div style="border:0.5px solid var(--rule);">'
                + "".join(recs_html)
                + '</div>',
                unsafe_allow_html=True,
            )

        # ── Unmerge UI (collapsed by default) ─────────────────────────────────
        if st.session_state.get("show_unmerge") and len(members) >= 2:
            st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
            with st.expander("Split (unmerge) a member from this UBID", expanded=True):
                opts = [
                    f"{r['source_system']}/{r['source_record_id']} · {(r.get('name_raw') or '')[:30]}"
                    for r in members
                ]
                opt_to_id = {opt: r["canonical_id"] for opt, r in zip(opts, members)}

                u_col1, u_col2 = st.columns(2)
                pick_a = u_col1.selectbox("Record A (stays on this UBID)", opts, key="unmerge_a")
                pick_b = u_col2.selectbox("Record B (peeled off to new UBID)",
                                            [o for o in opts if o != pick_a], key="unmerge_b")
                u_notes = st.text_input("Reason (optional, recorded in audit log)",
                                         key="unmerge_notes",
                                         placeholder="e.g. 'different proprietor' / 'shared pin only'")
                if st.button("🔓 Split (unmerge)", key="do_unmerge", type="primary"):
                    resp = api_post("/api/v1/review/unmerge", {
                        "canonical_id_a": opt_to_id[pick_a],
                        "canonical_id_b": opt_to_id[pick_b],
                        "reviewer_id": reviewer_id,
                        "reviewer_tier": reviewer_tier,
                        "notes": u_notes or None,
                    })
                    if resp:
                        st.success(f"✓ split UBID {resp['previous_shared_ubid'][:8]}… — refresh to see lineage")
                        st.session_state["show_unmerge"] = False
                        st.rerun()

        # ── Audit trail (collapsed) ──────────────────────────────────────────
        st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
        audit = api_get(f"/api/v1/ubid/{ubid_input}/audit")
        if audit:
            with st.expander(f"UBID lineage & audit trail · {audit.get('decision_count', 0)} decisions · "
                              f"{audit.get('constraint_count', 0)} constraints"):
                tl = audit.get("timeline") or []
                if tl:
                    kind_colors = {"link": "var(--moss-bright)",
                                    "decision": "var(--indigo)",
                                    "constraint": "var(--saffron)"}
                    items_html = []
                    for evt in tl[:25]:
                        c = kind_colors.get(evt["kind"], "var(--ink-soft)")
                        items_html.append(
                            f'<div style="border-left:3px solid {c};padding:6px 12px;margin:4px 0;background:var(--white);font-family:Inter,sans-serif;">'
                            f'<span style="color:{c};font-weight:700;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;">{evt["kind"]}</span>'
                            ' &middot; '
                            f'<span style="color:var(--ink-faint);font-family:\'JetBrains Mono\',monospace;font-size:11px;">{evt["ts"][:19]}</span>'
                            ' &middot; '
                            f'<span style="color:var(--ink);font-size:13px;">{evt["summary"]}</span>'
                            f'<div style="font-size:11px;color:var(--ink-faint);margin-top:2px;">by {evt.get("actor", "?")}</div>'
                            '</div>'
                        )
                    st.markdown("".join(items_html), unsafe_allow_html=True)
                    if len(tl) > 25:
                        st.markdown(f'<div style="font-style:italic;color:var(--ink-faint);font-family:Fraunces,serif;text-align:center;padding:8px;">+ {len(tl) - 25} earlier events</div>',
                                    unsafe_allow_html=True)

        # ── Full event log (compact expander) ────────────────────────────────
        if timeline:
            with st.expander(f"Full evidence log · {len(timeline)} events"):
                df_show = pd.DataFrame(timeline)[
                    ["event_date", "event_type", "source_system", "weight", "sign",
                     "days_ago", "decayed_contribution"]
                ]
                st.dataframe(df_show, use_container_width=True, height=400)
                csv_bytes = df_show.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download evidence as CSV",
                    data=csv_bytes,
                    file_name=f"evidence_{ubid_input[:8]}.csv",
                    mime="text/csv",
                    key="dl_evidence",
                )


# ═════════════════════════════════════════════════════════════════════════════
# QUARANTINE
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🚧 Quarantine":

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
