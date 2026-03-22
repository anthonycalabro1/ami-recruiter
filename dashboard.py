"""
AMI Recruiting Dashboard - Streamlit-based interface for managing candidates.
"""

import streamlit as st
import json
import os
import sys
import shutil
import pandas as pd
from datetime import datetime
from pathlib import Path

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from database import (
    get_all_candidates, get_candidate, get_candidate_scores,
    get_dashboard_stats, update_candidate_status, update_candidate, get_status_history,
    save_rubric_feedback, get_pending_feedback, get_candidates_by_tier,
    get_recent_activity, get_processing_timeline, get_area_distribution,
    DB_INIT_ERROR, USE_POSTGRES, DATABASE_URL
)
from notifications import generate_handoff_email


# ─── UI Constants ─────────────────────────────────────────────────────────────

STATUS_FILTER_OPTIONS = {
    "All":                             None,
    "🟢 Scored — High":               "scored_high",
    "🟡 Scored — Medium":             "scored_medium",
    "🟠 Scored — Low":                "scored_low",
    "🔴 Eliminated — Pending Review": "eliminated_pending_review",
    "❌ Eliminated — Confirmed":      "eliminated_confirmed",
    "📅 Phone Screen Scheduled":      "phone_screen_scheduled",
    "✅ Passed — Senior":             "phone_screen_pass_senior",
    "✅ Passed — Manager":            "phone_screen_pass_manager",
    "❌ Phone Screen Rejected":       "phone_screen_reject",
    "🏁 Handed Off":                  "handed_off",
    "⏳ Processing":                  "processing",
    "⚠️ Error":                       "error",
}

_TIER_CELL_STYLE = {
    'HIGH':       'background-color: #2D8A4E; color: white; font-weight: bold;',
    'MEDIUM':     'background-color: #C4841D; color: white; font-weight: bold;',
    'LOW':        'background-color: #B85C3A; color: white; font-weight: bold;',
    'ELIMINATED': 'background-color: #A63D40; color: white; font-weight: bold;',
    'N/A':        'background-color: #2a2a2e; color: #7A756E; font-weight: bold;',
}

NAV_PAGES = [
    "01  Pipeline Overview",
    "02  Candidate Details",
    "03  Analytics",
    "04  Eliminated Review",
    "05  Rubric Feedback",
    "06  Handoff Emails",
    "07  System",
]


# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AMI Recruiting Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": None,
        "Report a bug": None,
        "About": "AMI Recruiting Dashboard — Candidate Pipeline Management",
    },
)

# ── Database connection guard ─────────────────────────────────────────────────
if DB_INIT_ERROR:
    st.error("⚠️ Database Connection Failed")
    st.markdown("The dashboard could not connect to the database. Full diagnostics:")
    st.code(DB_INIT_ERROR, language="text")
    st.info(
        "**To fix this on Streamlit Cloud:**\n\n"
        "1. Go to your app → **Manage app** → **Secrets**\n"
        "2. Make sure `DATABASE_URL` uses the **Session Pooler** URL from Supabase\n"
        "   - Supabase → Settings → Database → scroll to top → Connection string → Type: **Session pooler**\n"
        "3. The URL should look like:\n"
        "   `postgresql://postgres.YOURPROJECT:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres`\n"
        "4. Save secrets and wait for the app to redeploy"
    )
    st.stop()
# ─────────────────────────────────────────────────────────────────────────────


# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=IBM+Plex+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
/* ── Design tokens ──────────────────────────────────────────────────────────── */
:root {
    --primary:      #C4841D;
    --primary-dk:   #1A1A1E;
    --bg:           #121215;
    --bg-card:      #1E1E23;
    --success:      #2D8A4E;
    --warning:      #C4841D;
    --danger-lt:    #B85C3A;
    --danger:       #A63D40;
    --border:       rgba(255,255,255,0.06);
    --text:         #E8E4DE;
    --text-muted:   #7A756E;
    --font-display: 'DM Serif Display', Georgia, serif;
    --font-body:    'IBM Plex Sans', -apple-system, sans-serif;
    --font-mono:    'JetBrains Mono', 'Fira Code', monospace;
}

/* ── Global overrides ──────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"], .main .block-container {
    font-family: var(--font-body) !important;
    color: var(--text);
}
h1, h2, h3 { font-family: var(--font-display) !important; font-weight: 400 !important; letter-spacing: -0.5px; }
code, .stCode, [data-testid="stMetricValue"] { font-family: var(--font-mono) !important; }

/* ── Stagger fade-in animation ─────────────────────────────────────────────── */
@keyframes fadeSlideUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes subtlePulse {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.7; }
}

/* ── Header ─────────────────────────────────────────────────────────────────── */
.main-header {
    background: var(--primary-dk);
    color: var(--text);
    padding: 28px 0 20px 0;
    margin-bottom: 8px;
    border: none;
    border-radius: 0;
    box-shadow: none;
    animation: fadeSlideUp 0.6s ease-out;
}
.main-header h1 {
    margin: 0;
    font-family: var(--font-display) !important;
    font-size: 38px;
    font-weight: 400;
    letter-spacing: -1px;
    color: var(--text);
}
.main-header .header-subtitle {
    margin: 6px 0 0 0;
    font-family: var(--font-mono) !important;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    color: var(--text-muted);
}
.header-accent {
    width: 64px;
    height: 2px;
    background: var(--primary);
    margin-top: 16px;
    border-radius: 1px;
}

/* ── Metric tiles ──────────────────────────────────────────────────────────── */
.metric-strip {
    display: flex;
    gap: 0;
    margin: 8px 0 20px 0;
    animation: fadeSlideUp 0.6s ease-out 0.1s both;
}
.metric-tile {
    flex: 1;
    padding: 18px 16px;
    border-right: 1px solid var(--border);
    position: relative;
    transition: background 0.2s ease;
}
.metric-tile:hover { background: rgba(255,255,255,0.02); }
.metric-tile:last-child { border-right: none; }
.metric-tile .metric-value {
    font-family: var(--font-mono) !important;
    font-size: 36px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 6px;
    color: var(--text);
}
.metric-tile .metric-label {
    font-family: var(--font-body) !important;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-muted);
    font-weight: 500;
}
.metric-tile.accent-success { border-left: 2px solid var(--success); }
.metric-tile.accent-warning { border-left: 2px solid var(--warning); }
.metric-tile.accent-danger-lt { border-left: 2px solid var(--danger-lt); }
.metric-tile.accent-danger { border-left: 2px solid var(--danger); }
.metric-tile.accent-primary { border-left: 2px solid var(--primary); }

/* ── Tier badges ───────────────────────────────────────────────────────────── */
.tier-high       { background: var(--success); color: white; padding: 2px 10px; border-radius: 3px; font-family: var(--font-mono); font-weight: 500; font-size: 11px; letter-spacing: 0.5px; white-space: nowrap; display: inline-block; }
.tier-medium     { background: var(--warning); color: white; padding: 2px 10px; border-radius: 3px; font-family: var(--font-mono); font-weight: 500; font-size: 11px; letter-spacing: 0.5px; white-space: nowrap; display: inline-block; }
.tier-low        { background: var(--danger-lt); color: white; padding: 2px 10px; border-radius: 3px; font-family: var(--font-mono); font-weight: 500; font-size: 11px; letter-spacing: 0.5px; white-space: nowrap; display: inline-block; }
.tier-eliminated { background: var(--danger); color: white; padding: 2px 10px; border-radius: 3px; font-family: var(--font-mono); font-weight: 500; font-size: 11px; letter-spacing: 0.5px; white-space: nowrap; display: inline-block; }

/* ── Selected-row callout ──────────────────────────────────────────────────── */
.selected-callout {
    background: linear-gradient(90deg, rgba(196,132,29,0.08), transparent);
    border-left: 2px solid var(--primary);
    padding: 12px 18px;
    border-radius: 0 4px 4px 0;
    margin: 4px 0 10px 0;
    font-size: 14px;
    font-family: var(--font-body);
    animation: fadeSlideUp 0.3s ease-out;
}

/* ── Sidebar styling ───────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #16161A !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stRadio > label {
    font-family: var(--font-mono) !important;
    font-size: 10px !important;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--text-muted) !important;
    margin-bottom: 8px;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label {
    padding: 8px 12px !important;
    border-radius: 4px;
    margin: 1px 0;
    transition: all 0.2s ease;
    border-left: 2px solid transparent;
    font-family: var(--font-body) !important;
    font-size: 13px !important;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover {
    background: rgba(196,132,29,0.06) !important;
    border-left-color: rgba(196,132,29,0.3);
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label[data-checked="true"],
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:has(input:checked) {
    background: rgba(196,132,29,0.10) !important;
    border-left-color: var(--primary) !important;
    color: var(--text) !important;
}
[data-testid="stSidebar"] [data-testid="stCaption"] {
    font-family: var(--font-body) !important;
    font-size: 12px !important;
    border-left: 1px solid rgba(196,132,29,0.2);
    padding-left: 10px;
    margin: 4px 0;
}

/* ── Profile card ──────────────────────────────────────────────────────────── */
.profile-card {
    display: flex;
    align-items: flex-start;
    gap: 20px;
    padding: 24px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-bottom: 20px;
    animation: fadeSlideUp 0.5s ease-out;
}
.profile-initials {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: var(--primary);
    color: var(--primary-dk);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-display) !important;
    font-size: 24px;
    font-weight: 400;
    flex-shrink: 0;
}
.profile-info { flex: 1; }
.profile-info h2 {
    font-family: var(--font-display) !important;
    font-size: 28px;
    margin: 0 0 6px 0;
    font-weight: 400;
    color: var(--text);
}
.profile-contact {
    font-family: var(--font-mono) !important;
    font-size: 12px;
    color: var(--text-muted);
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}
.profile-contact span { white-space: nowrap; }
.profile-stats {
    display: flex;
    gap: 32px;
    flex-shrink: 0;
    align-self: center;
}
.profile-stat {
    text-align: right;
}
.profile-stat .stat-value {
    font-family: var(--font-mono) !important;
    font-size: 32px;
    font-weight: 700;
    color: var(--text);
    line-height: 1;
}
.profile-stat .stat-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-muted);
    margin-top: 4px;
}

/* ── Score gauge blocks ────────────────────────────────────────────────────── */
.score-gauge {
    display: inline-flex;
    gap: 3px;
    margin-left: 8px;
    vertical-align: middle;
}
.score-gauge .gauge-block {
    width: 14px;
    height: 10px;
    border-radius: 2px;
    background: rgba(255,255,255,0.08);
    transition: transform 0.15s ease;
}
.score-gauge .gauge-block.filled { background: var(--primary); }
.score-gauge .gauge-block.filled.s5 { background: var(--success); }
.score-gauge .gauge-block.filled.s4 { background: #5BA86C; }
.score-gauge .gauge-block.filled.s3 { background: var(--warning); }
.score-gauge .gauge-block.filled.s2 { background: var(--danger-lt); }
.score-gauge .gauge-block.filled.s1 { background: var(--danger); }
.score-gauge:hover .gauge-block { transform: scaleY(1.3); }

/* ── Gate chips ────────────────────────────────────────────────────────────── */
.gate-row {
    display: flex;
    gap: 8px;
    margin: 8px 0 16px 0;
}
.gate-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 12px;
    border-radius: 3px;
    font-family: var(--font-mono) !important;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.3px;
}
.gate-chip.pass {
    background: rgba(45,138,78,0.15);
    color: var(--success);
    border: 1px solid rgba(45,138,78,0.25);
}
.gate-chip.fail {
    background: rgba(166,61,64,0.15);
    color: var(--danger);
    border: 1px solid rgba(166,61,64,0.25);
}

/* ── Phone screen question cards ───────────────────────────────────────────── */
.q-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
    margin: 10px 0;
}
.q-card .q-number {
    font-family: var(--font-mono) !important;
    font-size: 10px;
    color: var(--primary);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 6px;
}
.q-card .q-text {
    font-family: var(--font-body) !important;
    font-size: 15px;
    color: var(--text);
    margin-bottom: 10px;
    line-height: 1.5;
}
.q-card .q-meta {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.6;
}
.q-card .q-meta .q-tag {
    display: inline-block;
    background: rgba(196,132,29,0.12);
    color: var(--primary);
    padding: 1px 8px;
    border-radius: 3px;
    font-family: var(--font-mono) !important;
    font-size: 10px;
    letter-spacing: 0.5px;
    margin-right: 6px;
}
.q-card .q-redflag {
    font-size: 12px;
    color: var(--danger);
    margin-top: 6px;
    padding-left: 10px;
    border-left: 2px solid rgba(166,61,64,0.3);
}

/* ── Funnel visualization ──────────────────────────────────────────────────── */
.funnel-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    margin: 20px 0;
    animation: fadeSlideUp 0.6s ease-out 0.15s both;
}
.funnel-row {
    display: flex;
    align-items: center;
    width: 100%;
    gap: 16px;
}
.funnel-label {
    width: 180px;
    text-align: right;
    font-family: var(--font-body);
    font-size: 13px;
    color: var(--text-muted);
    flex-shrink: 0;
}
.funnel-bar-wrap {
    flex: 1;
    height: 36px;
    display: flex;
    align-items: center;
}
.funnel-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), rgba(196,132,29,0.6));
    border-radius: 3px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 12px;
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
    min-width: 48px;
    transition: width 0.8s ease-out;
}

/* ── Tabs ───────────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { gap: 2px; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] {
    padding: 10px 20px;
    border-radius: 4px 4px 0 0;
    font-family: var(--font-body) !important;
    font-weight: 500;
    font-size: 13px;
    letter-spacing: 0.3px;
    transition: all 0.2s ease;
}
.stTabs [data-baseweb="tab"]:hover { background: rgba(196,132,29,0.06); }

/* ── Section headers ───────────────────────────────────────────────────────── */
.section-label {
    font-family: var(--font-mono) !important;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    color: var(--text-muted);
    margin: 28px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

/* ── Empty state ───────────────────────────────────────────────────────────── */
.empty-state {
    text-align: center;
    padding: 48px 24px;
    color: var(--text-muted);
    animation: fadeSlideUp 0.5s ease-out;
}
.empty-state .empty-icon {
    font-size: 32px;
    margin-bottom: 12px;
    opacity: 0.4;
}
.empty-state .empty-title {
    font-family: var(--font-display) !important;
    font-size: 20px;
    color: var(--text);
    margin-bottom: 6px;
}
.empty-state .empty-desc {
    font-size: 13px;
    max-width: 400px;
    margin: 0 auto;
    line-height: 1.5;
}

/* ── Button refinements ────────────────────────────────────────────────────── */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
    background: var(--primary) !important;
    border: none !important;
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
    letter-spacing: 0.3px;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {
    background: #D4941D !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(196,132,29,0.25) !important;
}
.stButton > button[kind="secondary"],
.stButton > button[data-testid="stBaseButton-secondary"] {
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
    border-color: var(--border) !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="secondary"]:hover,
.stButton > button[data-testid="stBaseButton-secondary"]:hover {
    border-color: rgba(196,132,29,0.4) !important;
    color: var(--primary) !important;
}
/* Danger button style via custom class */
.danger-btn button {
    background: var(--danger) !important;
    border: none !important;
    color: white !important;
}
.danger-btn button:hover {
    background: #BF4548 !important;
}

/* ── DataTable refinements ─────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    animation: fadeSlideUp 0.5s ease-out 0.2s both;
}
[data-testid="stDataFrame"] th {
    font-family: var(--font-mono) !important;
    font-size: 10px !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Expander refinements ──────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)


# ─── Helper: tier badge HTML ───────────────────────────────────────────────────
def tier_badge(tier):
    """Return an HTML tier badge span."""
    safe = (tier or '').lower()
    tier_class = f"tier-{safe}" if safe in ('high', 'medium', 'low', 'eliminated') else "tier-eliminated"
    return f'<span class="{tier_class}">{tier or "N/A"}</span>'


# ─── Helper: color the Tier column in a DataFrame ─────────────────────────────
def _style_tier_col(series):
    return [_TIER_CELL_STYLE.get(str(v), '') for v in series]


# ─── Main app ─────────────────────────────────────────────────────────────────

def main():
    # ── Session-state bootstrap ───────────────────────────────────────────────
    if 'jump_to_candidate' not in st.session_state:
        st.session_state.jump_to_candidate = None

    # Apply any programmatic page switch BEFORE the radio widget renders.
    # We can't set a widget-bound key after its widget has rendered, so we
    # stage the target in _requested_page and apply it here at the top.
    if '_requested_page' in st.session_state:
        st.session_state.nav_page = st.session_state.pop('_requested_page')

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="main-header">
        <h1>AMI Recruiting</h1>
        <div class="header-subtitle">Candidate Pipeline Management</div>
        <div class="header-accent"></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar navigation ────────────────────────────────────────────────────
    st.sidebar.markdown('<div class="section-label">Navigation</div>', unsafe_allow_html=True)
    page = st.sidebar.radio("Go to", NAV_PAGES, key="nav_page", label_visibility="collapsed")

    # Auto-refresh control
    st.sidebar.divider()
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=False)
    if auto_refresh:
        refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 15, 120, 30)
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=refresh_interval * 1000, key="auto_refresh")
        except ImportError:
            import time
            time.sleep(refresh_interval)
            st.rerun()

    # Recent Activity feed
    st.sidebar.divider()
    st.sidebar.markdown('<div class="section-label">Recent Activity</div>', unsafe_allow_html=True)
    activity = get_recent_activity(5)
    if activity:
        for a in activity:
            st.sidebar.caption(
                f"**{a['candidate_name']}**: {_format_status(a['new_status'])} "
                f"({a['changed_by']}, {str(a['created_at'])[:16]})"
            )
    else:
        st.sidebar.caption("No activity yet.")

    # ── Page routing ──────────────────────────────────────────────────────────
    if page == "01  Pipeline Overview":
        show_pipeline_overview()
    elif page == "02  Candidate Details":
        show_candidate_details()
    elif page == "03  Analytics":
        show_analytics()
    elif page == "04  Eliminated Review":
        show_eliminated_review()
    elif page == "05  Rubric Feedback":
        show_rubric_feedback()
    elif page == "06  Handoff Emails":
        show_handoff_generator()
    elif page == "07  System":
        show_system_status()


# ─── Pipeline Overview ────────────────────────────────────────────────────────

def show_pipeline_overview():
    """Show the main pipeline overview with metrics and candidate list."""
    stats = get_dashboard_stats()

    # ── Metrics row ───────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="metric-strip">
        <div class="metric-tile">
            <div class="metric-value">{stats['total_candidates']}</div>
            <div class="metric-label">Total</div>
        </div>
        <div class="metric-tile">
            <div class="metric-value">{stats['processing']}</div>
            <div class="metric-label">Processing</div>
        </div>
        <div class="metric-tile accent-success">
            <div class="metric-value">{stats['high']}</div>
            <div class="metric-label">High Tier</div>
        </div>
        <div class="metric-tile accent-warning">
            <div class="metric-value">{stats['medium']}</div>
            <div class="metric-label">Medium Tier</div>
        </div>
        <div class="metric-tile accent-danger-lt">
            <div class="metric-value">{stats['low']}</div>
            <div class="metric-label">Low Tier</div>
        </div>
        <div class="metric-tile accent-danger">
            <div class="metric-value">{stats['eliminated']}</div>
            <div class="metric-label">Eliminated</div>
        </div>
        <div class="metric-tile accent-primary">
            <div class="metric-value">{stats['handed_off']}</div>
            <div class="metric-label">Handed Off</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Search & Filters ──────────────────────────────────────────────────────
    search_term = st.text_input("🔍 Search by candidate name", "", key="search")

    col1, col2, col3 = st.columns(3)
    with col1:
        status_label = st.selectbox("Filter by Status", list(STATUS_FILTER_OPTIONS.keys()))
        status_filter = STATUS_FILTER_OPTIONS[status_label]
    with col2:
        fa_filter = st.selectbox("Filter by Functional Area", [
            "All", "Strategy & Business Case", "Business Integration",
            "System Integration", "Field Deployment Management", "AMI Operations"
        ])
    with col3:
        sort_by = st.selectbox("Sort by", ["Most Recent", "Highest Score", "Name"])

    # ── Fetch candidates ──────────────────────────────────────────────────────
    candidates = get_all_candidates(status_filter) if status_filter else get_all_candidates()

    if not candidates:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">&#9634;</div>
            <div class="empty-title">No candidates yet</div>
            <div class="empty-desc">Drop resumes into the AMI_Candidates_Inbox folder to start building your pipeline.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Build display data ────────────────────────────────────────────────────
    display_data = []
    for c in candidates:
        scores = get_candidate_scores(c['id'])

        if fa_filter != "All":
            scores = [s for s in scores if s['functional_area'] == fa_filter]
            if not scores:
                continue

        highest_score = max(scores, key=lambda s: s['weighted_score'] or 0) if scores else None

        display_data.append({
            'ID':           c['id'],
            'Name':         c['name'],
            'AMI Years':    c['total_ami_years'] or 0,
            'Role Routing': _format_routing(c['role_routing']),
            'Primary Area': highest_score['functional_area'] if highest_score else 'N/A',
            'Score':        f"{highest_score['weighted_score']:.2f}" if highest_score and highest_score['weighted_score'] else 'N/A',
            'Tier':         highest_score['tier'] if highest_score else 'N/A',
            'Status':       _format_status(c['status']),
            'Areas':        len(scores),
            'Date':         str(c['created_at'])[:10] if c['created_at'] else '',
        })

    # ── Apply search & sort ───────────────────────────────────────────────────
    if search_term:
        display_data = [d for d in display_data if search_term.lower() in d['Name'].lower()]

    if not display_data:
        st.info("No candidates match the current filters.")
        return

    if sort_by == "Highest Score":
        display_data.sort(key=lambda x: float(x['Score']) if x['Score'] != 'N/A' else 0, reverse=True)
    elif sort_by == "Name":
        display_data.sort(key=lambda x: x['Name'])

    # ── Styled DataFrame ──────────────────────────────────────────────────────
    df = pd.DataFrame(display_data)
    df_display = df.drop(columns=['ID'])           # Hide internal ID
    styled = df_display.style.apply(_style_tier_col, subset=['Tier'])

    event = st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    # ── Row selection → navigate ──────────────────────────────────────────────
    if event.selection and event.selection.rows:
        row_idx = event.selection.rows[0]
        sel = display_data[row_idx]
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.markdown(
                f'<div class="selected-callout">'
                f'Selected: <strong>{sel["Name"]}</strong>'
                f' &nbsp;·&nbsp; Tier: <strong>{sel["Tier"]}</strong>'
                f' &nbsp;·&nbsp; Score: <strong>{sel["Score"]}</strong>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("👤 View Details →", type="primary", use_container_width=True):
                st.session_state.jump_to_candidate = sel['ID']
                st.session_state._requested_page = "02  Candidate Details"
                st.rerun()
    else:
        st.caption(f"Click a row to select it · Showing {len(display_data)} candidates")

    # ── CSV Export ────────────────────────────────────────────────────────────
    csv_data = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv_data,
        file_name=f"ami_pipeline_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )


# ─── Candidate Details ────────────────────────────────────────────────────────

def show_candidate_details():
    """Show detailed view of a specific candidate."""
    candidates = get_all_candidates()

    if not candidates:
        st.info("No candidates in the system yet.")
        return

    # ── Back navigation ───────────────────────────────────────────────────────
    if st.button("← Back to Pipeline"):
        st.session_state.jump_to_candidate = None
        st.session_state._requested_page = "01  Pipeline Overview"
        st.rerun()

    # ── Candidate selector ────────────────────────────────────────────────────
    candidate_options = {f"{c['name']} (ID: {c['id']})": c['id'] for c in candidates}
    option_keys = list(candidate_options.keys())

    # Pre-select from click-through navigation
    default_idx = 0
    jump_id = st.session_state.get('jump_to_candidate')
    if jump_id is not None:
        for i, (label, cid) in enumerate(candidate_options.items()):
            if cid == jump_id:
                default_idx = i
                break
        st.session_state.jump_to_candidate = None   # Consume the jump

    selected = st.selectbox("Select Candidate", option_keys, index=default_idx)
    candidate_id = candidate_options[selected]

    candidate = get_candidate(candidate_id)
    scores = get_candidate_scores(candidate_id)
    history = get_status_history(candidate_id)

    # ── Profile header ────────────────────────────────────────────────────────
    _name = candidate['name'] or 'Unknown'
    _initials = ''.join(w[0] for w in _name.split()[:2]).upper() if _name else '?'
    _email = candidate.get('email') or ''
    _phone = candidate.get('phone') or ''
    _contact_parts = []
    if _email:
        _contact_parts.append(f'<span>{_email}</span>')
    if _phone:
        _contact_parts.append(f'<span>{_phone}</span>')
    _contact_html = ' &nbsp;|&nbsp; '.join(_contact_parts) if _contact_parts else '<span>No contact info</span>'
    _ami_yrs = candidate['total_ami_years'] if candidate['total_ami_years'] is not None else 'N/A'
    _routing = _format_routing(candidate['role_routing'])

    st.markdown(f"""
    <div class="profile-card">
        <div class="profile-initials">{_initials}</div>
        <div class="profile-info">
            <h2>{_name}</h2>
            <div class="profile-contact">{_contact_html}</div>
        </div>
        <div class="profile-stats">
            <div class="profile-stat">
                <div class="stat-value">{_ami_yrs}</div>
                <div class="stat-label">AMI Years</div>
            </div>
            <div class="profile-stat">
                <div class="stat-value" style="font-size:20px;">{_routing}</div>
                <div class="stat-label">Role Routing</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Status management ─────────────────────────────────────────────────────
    st.divider()
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write(f"**Current Status:** {_format_status(candidate['status'])}")
    with col2:
        _ALL_STATUSES = [
            "scored_high", "scored_medium", "scored_low",
            "phone_screen_scheduled", "phone_screen_pass_senior",
            "phone_screen_pass_manager", "phone_screen_reject",
            "handed_off",
            "eliminated_pending_review", "eliminated_confirmed",
            "processing",
        ]
        if candidate['status'] not in _ALL_STATUSES:
            _ALL_STATUSES = [candidate['status']] + _ALL_STATUSES
        _cur_idx = _ALL_STATUSES.index(candidate['status'])
        _status_display = [_format_status(s) for s in _ALL_STATUSES]
        _selected = st.selectbox("Update Status", _status_display, index=_cur_idx, key="status_update")
        new_status = _ALL_STATUSES[_status_display.index(_selected)]
        if new_status != candidate['status']:
            notes = st.text_input("Notes (optional)", key="status_notes")
            if st.button("Update Status"):
                update_candidate_status(candidate_id, new_status, 'user', notes)
                st.success(f"Status updated to: {_format_status(new_status)}")
                st.rerun()

    # ── Functional area scores ────────────────────────────────────────────────
    st.divider()
    st.markdown('<div class="section-label">Functional Area Scores</div>', unsafe_allow_html=True)

    if not scores:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">&#9673;</div>
            <div class="empty-title">No scores yet</div>
            <div class="empty-desc">Scores will appear here once the pipeline finishes processing this candidate.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for score in scores:
            tier = score['tier'] or 'N/A'
            ws = score['weighted_score'] or 0
            with st.expander(
                f"{score['functional_area']} — {tier} ({ws:.2f})"
                + (" — Manager Stretch" if score['manager_stretch_flag'] else ""),
                expanded=(tier == 'HIGH')
            ):
                # Gate results as chips
                g1_cls = "pass" if score['gate1_pass'] else "fail"
                g2_cls = "pass" if score['gate2_pass'] else "fail"
                g3_cls = "pass" if score.get('gate3_pass') else "fail"
                g1_icon = "&#10003;" if score['gate1_pass'] else "&#10007;"
                g2_icon = "&#10003;" if score['gate2_pass'] else "&#10007;"
                g3_icon = "&#10003;" if score.get('gate3_pass') else "&#10007;"
                st.markdown(f"""
                <div class="gate-row">
                    <span class="gate-chip {g1_cls}">{g1_icon} G1 AMI Experience</span>
                    <span class="gate-chip {g2_cls}">{g2_icon} G2 AMI Years</span>
                    <span class="gate-chip {g3_cls}">{g3_icon} G3 Area Match</span>
                </div>
                """, unsafe_allow_html=True)

                # Dimension scores with gauge blocks
                if score['dimension_scores']:
                    st.markdown('<div class="section-label">Dimensions</div>', unsafe_allow_html=True)
                    dim_scores = json.loads(score['dimension_scores']) if isinstance(score['dimension_scores'], str) else score['dimension_scores']
                    for dim_name, dim_data in dim_scores.items():
                        if isinstance(dim_data, dict):
                            s = dim_data.get('score', 0)
                            r = dim_data.get('reasoning', '')
                            try:
                                s_int = int(float(s))
                            except (ValueError, TypeError):
                                s_int = 0
                            blocks = ''.join(
                                f'<span class="gauge-block {"filled s" + str(s_int) if i < s_int else ""}"></span>'
                                for i in range(5)
                            )
                            st.markdown(
                                f'**{dim_name}** <span style="font-family:var(--font-mono);color:var(--text-muted);font-size:12px;">{s}/5</span>'
                                f' <span class="score-gauge">{blocks}</span>',
                                unsafe_allow_html=True,
                            )
                            if r:
                                st.caption(r)

                # Narrative
                st.markdown('<div class="section-label">Assessment</div>', unsafe_allow_html=True)
                st.write(score['scoring_narrative'] or 'No narrative available.')

                # Manager stretch
                if score['manager_stretch_flag']:
                    st.info(f"**Manager Stretch Flag:** {score['manager_stretch_narrative']}")

                # Phone screen questions as cards
                if score['phone_screen_questions']:
                    st.markdown('<div class="section-label">Phone Screen Questions</div>', unsafe_allow_html=True)
                    questions = json.loads(score['phone_screen_questions']) if isinstance(score['phone_screen_questions'], str) else score['phone_screen_questions']
                    for i, q in enumerate(questions, 1):
                        if isinstance(q, dict):
                            q_text = q.get('question', '')
                            q_dim = q.get('dimension_tested', '')
                            q_listen = q.get('what_to_listen_for', '')
                            q_red = q.get('red_flag_answers', '')
                            redflag_html = f'<div class="q-redflag">Red flags: {q_red}</div>' if q_red else ''
                            st.markdown(f"""
                            <div class="q-card">
                                <div class="q-number">Question {i}</div>
                                <div class="q-text">{q_text}</div>
                                <div class="q-meta">
                                    <span class="q-tag">{q_dim}</span>
                                    Listen for: {q_listen}
                                </div>
                                {redflag_html}
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.write(f"**Q{i}:** {q}")

    # ── Parsed profile ────────────────────────────────────────────────────────
    st.divider()
    with st.expander("📄 Parsed Resume Profile"):
        if candidate['parsed_profile']:
            profile = json.loads(candidate['parsed_profile']) if isinstance(candidate['parsed_profile'], str) else candidate['parsed_profile']
            st.json(profile)
        else:
            st.write("No parsed profile available.")

    # ── Status history ────────────────────────────────────────────────────────
    with st.expander("📋 Status History"):
        if history:
            for h in history:
                st.write(f"**{str(h['created_at'])[:16]}** — {_format_status(h['new_status'])} "
                         f"(by {h['changed_by']}) {': ' + h['notes'] if h['notes'] else ''}")
        else:
            st.write("No history available.")

    # ── Notes ─────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown('<div class="section-label">Notes</div>', unsafe_allow_html=True)
    current_notes = candidate.get('notes', '') or ''
    new_notes = st.text_area("Add/edit notes", value=current_notes, height=100, key="candidate_notes")
    if st.button("Save Notes") and new_notes != current_notes:
        update_candidate(candidate_id, notes=new_notes)
        st.success("Notes saved.")


# ─── Analytics ────────────────────────────────────────────────────────────────

def show_analytics():
    """Show pipeline analytics and funnel visualization."""
    st.markdown('<div class="section-label">Pipeline Analytics</div>', unsafe_allow_html=True)

    stats = get_dashboard_stats()

    # Pipeline Funnel — CSS tapered visualization
    st.markdown('<div class="section-label">Pipeline Funnel</div>', unsafe_allow_html=True)
    total = max(stats['total_candidates'], 1)
    scored = stats['high'] + stats['medium'] + stats['low']
    phone_screen = stats.get('passed_senior', 0) + stats.get('passed_manager', 0)
    handed_off = stats['handed_off']

    funnel_data = [
        ("Total Candidates", stats['total_candidates']),
        ("Scored (H/M/L)", scored),
        ("Phone Screen Passed", phone_screen),
        ("Handed Off", handed_off),
    ]

    funnel_html = '<div class="funnel-container">'
    for label, count in funnel_data:
        pct = (count / total) * 100
        width_pct = max(pct, 8)  # minimum visible width
        funnel_html += f"""
        <div class="funnel-row">
            <div class="funnel-label">{label}</div>
            <div class="funnel-bar-wrap">
                <div class="funnel-bar" style="width:{width_pct}%;">{count} ({pct:.0f}%)</div>
            </div>
        </div>
        """
    funnel_html += '</div>'
    st.markdown(funnel_html, unsafe_allow_html=True)

    st.divider()

    # Tier Distribution and Functional Area Distribution side by side
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-label">Tier Distribution</div>', unsafe_allow_html=True)
        tier_data = {
            'Tier': ['HIGH', 'MEDIUM', 'LOW', 'ELIMINATED'],
            'Count': [stats['high'], stats['medium'], stats['low'], stats['eliminated']]
        }
        tier_df = pd.DataFrame(tier_data)
        st.bar_chart(tier_df.set_index('Tier'))

    with col2:
        st.markdown('<div class="section-label">Area Breakdown</div>', unsafe_allow_html=True)
        area_dist = get_area_distribution()
        if area_dist:
            area_df = pd.DataFrame(area_dist)
            try:
                pivot = area_df.pivot_table(index='functional_area', columns='tier', values='count', fill_value=0)
                st.dataframe(pivot, use_container_width=True)
            except Exception:
                st.dataframe(area_df, use_container_width=True, hide_index=True)
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">&#9673;</div>
                <div class="empty-title">No scoring data</div>
                <div class="empty-desc">Area breakdown will appear after candidates are scored.</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # Processing Timeline
    st.markdown('<div class="section-label">Processing Timeline</div>', unsafe_allow_html=True)
    timeline = get_processing_timeline()
    if timeline:
        timeline_df = pd.DataFrame(timeline)
        timeline_df['date'] = pd.to_datetime(timeline_df['date'])
        timeline_df = timeline_df.set_index('date')
        st.bar_chart(timeline_df['count'])
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">&#9634;</div>
            <div class="empty-title">No processing data</div>
            <div class="empty-desc">Timeline will populate as resumes are processed.</div>
        </div>
        """, unsafe_allow_html=True)

    # Summary metrics
    st.divider()
    pass_rate = (scored / total * 100) if total > 0 else 0
    high_rate = (stats['high'] / total * 100) if total > 0 else 0
    elim_rate = (stats['eliminated'] / total * 100) if total > 0 else 0
    avg_areas = _avg_areas_scored()

    st.markdown(f"""
    <div class="metric-strip">
        <div class="metric-tile accent-success">
            <div class="metric-value">{pass_rate:.0f}%</div>
            <div class="metric-label">Pass Rate</div>
        </div>
        <div class="metric-tile accent-success">
            <div class="metric-value">{high_rate:.0f}%</div>
            <div class="metric-label">High Tier Rate</div>
        </div>
        <div class="metric-tile accent-danger">
            <div class="metric-value">{elim_rate:.0f}%</div>
            <div class="metric-label">Elimination Rate</div>
        </div>
        <div class="metric-tile">
            <div class="metric-value">{avg_areas:.1f}</div>
            <div class="metric-label">Avg Areas / Candidate</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _avg_areas_scored():
    """Calculate average number of functional areas scored per candidate."""
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT AVG(area_count) FROM (
            SELECT candidate_id, COUNT(*) as area_count
            FROM functional_scores
            GROUP BY candidate_id
        )
    """)
    row = cursor.fetchone()
    conn.close()
    return row[0] if row[0] else 0


# ─── Eliminated Review ────────────────────────────────────────────────────────

def show_eliminated_review():
    """Show eliminated candidates for review and feedback."""
    st.markdown('<div class="section-label">Eliminated Candidates — Pending Review</div>', unsafe_allow_html=True)
    st.caption("Review eliminated candidates to verify the rubric's assessment. "
               "Override or provide feedback to improve the rubric.")

    candidates = get_all_candidates('eliminated_pending_review')

    if not candidates:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">&#10003;</div>
            <div class="empty-title">All clear</div>
            <div class="empty-desc">No eliminated candidates pending review.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for c in candidates:
        scores = get_candidate_scores(c['id'])
        eliminated_scores = [s for s in scores if s['tier'] == 'ELIMINATED']

        with st.expander(f"❌ {c['name']} — {c['total_ami_years'] or 0} AMI years — {c['resume_filename']}"):
            # Show elimination reasons
            for es in eliminated_scores:
                st.write(f"**{es['functional_area']}:**")
                if not es.get('gate1_pass'):
                    st.write(f"  ❌ Gate 1 Failed: {es.get('gate1_reason', 'N/A')}")
                if not es.get('gate2_pass'):
                    st.write(f"  ❌ Gate 2 Failed: {es.get('gate2_reason', 'N/A')}")
                if not es.get('gate3_pass'):
                    st.write(f"  ❌ Gate 3 Failed: {es.get('gate3_reason', 'N/A')}")
                st.write(f"  *{es.get('scoring_narrative', '')}*")

            # Parsed profile summary
            if c['parsed_profile']:
                profile = json.loads(c['parsed_profile']) if isinstance(c['parsed_profile'], str) else c['parsed_profile']
                st.write(f"**Overall Assessment:** {profile.get('overall_assessment', 'N/A')}")
                if profile.get('red_flags'):
                    st.write(f"**Red Flags:** {', '.join(profile['red_flags'])}")

            st.divider()

            # Action buttons
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✅ Confirm Elimination", key=f"confirm_{c['id']}"):
                    update_candidate_status(c['id'], 'eliminated_confirmed', 'user', 'Confirmed elimination after review')
                    st.success("Elimination confirmed.")
                    st.rerun()
            with col2:
                override_tier = st.selectbox("Override to:", ["LOW", "MEDIUM", "HIGH"], key=f"override_{c['id']}")
                if st.button("⬆️ Override", key=f"override_btn_{c['id']}"):
                    update_candidate_status(c['id'], f'scored_{override_tier.lower()}', 'user',
                                            f'Overridden from ELIMINATED to {override_tier}')
                    st.success(f"Overridden to {override_tier}.")
                    st.rerun()
            with col3:
                feedback = st.text_area("Rubric feedback:", key=f"feedback_{c['id']}", height=80,
                                        placeholder="What did the rubric get wrong?")
                if st.button("🏷️ Flag Rubric Issue", key=f"flag_{c['id']}"):
                    if feedback:
                        fa = eliminated_scores[0]['functional_area'] if eliminated_scores else 'General'
                        save_rubric_feedback(c['id'], fa, 'rubric_issue', feedback)
                        st.success("Rubric feedback saved.")
                    else:
                        st.warning("Please enter feedback text.")


# ─── Rubric Feedback ──────────────────────────────────────────────────────────

def show_rubric_feedback():
    """Show accumulated rubric feedback."""
    st.markdown('<div class="section-label">Rubric Feedback Queue</div>', unsafe_allow_html=True)
    st.caption("Accumulated feedback from eliminated candidate reviews. "
               "Use this to identify patterns and update rubrics.")

    feedback = get_pending_feedback()

    if not feedback:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">&#10003;</div>
            <div class="empty-title">No pending feedback</div>
            <div class="empty-desc">Rubric feedback will appear here as you review eliminated candidates.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for fb in feedback:
        with st.expander(f"📋 {fb['candidate_name']} — {fb['functional_area']} — {str(fb['created_at'])[:10]}"):
            st.write(f"**Type:** {fb['feedback_type']}")
            st.write(f"**Feedback:** {fb['feedback_text']}")
            if st.button("Mark Resolved", key=f"resolve_{fb['id']}"):
                from database import get_connection
                conn = get_connection()
                conn.execute("UPDATE rubric_feedback SET resolved = 1 WHERE id = ?", (fb['id'],))
                conn.commit()
                conn.close()
                st.success("Marked as resolved.")
                st.rerun()


# ─── Handoff Email Generator ──────────────────────────────────────────────────

def show_handoff_generator():
    """Generate handoff emails for candidates who passed phone screen."""
    st.markdown('<div class="section-label">Handoff Email Generator</div>', unsafe_allow_html=True)
    st.caption("Generate pre-written emails for candidates who passed the phone screen.")

    # Get candidates with passing status
    candidates = (get_all_candidates('phone_screen_pass_senior') +
                  get_all_candidates('phone_screen_pass_manager'))

    if not candidates:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">&#9993;</div>
            <div class="empty-title">No candidates ready for handoff</div>
            <div class="empty-desc">Update a candidate's status to 'Phone Screen Pass' from the Candidate Details page to generate handoff emails.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for c in candidates:
        role_level = "Senior" if c['status'] == 'phone_screen_pass_senior' else "Manager"
        with st.expander(f"📧 {c['name']} — {role_level}"):
            email_text = generate_handoff_email(c['name'], role_level)
            st.text_area("Email Template (copy and paste into your email):",
                         value=email_text, height=300, key=f"email_{c['id']}")

            if st.button(f"Mark as Handed Off", key=f"handoff_{c['id']}"):
                update_candidate_status(c['id'], 'handed_off', 'user',
                                        f'Handoff email sent for {role_level} role')
                st.success(f"Marked as handed off.")
                st.rerun()


# ─── System Status ────────────────────────────────────────────────────────────

def show_system_status():
    """Show system status and failed resume management."""
    st.markdown('<div class="section-label">System Status</div>', unsafe_allow_html=True)

    # Failed files
    failed_folder = os.path.join(PROJECT_DIR, "AMI_Candidates_Failed")
    inbox_folder = os.path.join(PROJECT_DIR, "AMI_Candidates_Inbox")
    processed_folder = os.path.join(PROJECT_DIR, "AMI_Candidates_Processed")

    inbox_count = len([f for f in os.listdir(inbox_folder) if os.path.isfile(os.path.join(inbox_folder, f))]) if os.path.exists(inbox_folder) else 0
    processed_count = len([f for f in os.listdir(processed_folder) if os.path.isfile(os.path.join(processed_folder, f))]) if os.path.exists(processed_folder) else 0
    failed_files = [f for f in os.listdir(failed_folder)
                    if not f.endswith('.reason.txt') and os.path.isfile(os.path.join(failed_folder, f))] if os.path.exists(failed_folder) else []

    st.markdown(f"""
    <div class="metric-strip">
        <div class="metric-tile">
            <div class="metric-value">{inbox_count}</div>
            <div class="metric-label">Inbox</div>
        </div>
        <div class="metric-tile accent-success">
            <div class="metric-value">{processed_count}</div>
            <div class="metric-label">Processed</div>
        </div>
        <div class="metric-tile accent-danger">
            <div class="metric-value">{len(failed_files)}</div>
            <div class="metric-label">Failed</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Failed resume management
    st.write("**Failed Resumes**")
    if not failed_files:
        st.success("No failed resumes.")
    else:
        for f in failed_files:
            filepath = os.path.join(failed_folder, f)
            reason_file = filepath + ".reason.txt"

            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"📄 **{f}**")
                if os.path.exists(reason_file):
                    with open(reason_file, 'r') as rf:
                        reason_text = rf.read().split('\n')[0]
                    st.caption(f"Reason: {reason_text}")
            with col2:
                if st.button("🔄 Retry", key=f"retry_{f}"):
                    try:
                        dest = os.path.join(inbox_folder, f)
                        if os.path.exists(dest):
                            base, ext = os.path.splitext(f)
                            dest = os.path.join(inbox_folder, f"{base}_retry{ext}")
                        shutil.move(filepath, dest)
                        if os.path.exists(reason_file):
                            os.remove(reason_file)
                        st.success(f"Moved {f} back to inbox for reprocessing.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to retry: {e}")

    st.divider()

    # Log files
    st.write("**Log Files**")
    logs_dir = os.path.join(PROJECT_DIR, "logs")
    if os.path.exists(logs_dir):
        log_files = sorted([f for f in os.listdir(logs_dir) if f.endswith('.log')], reverse=True)
        if log_files:
            for lf in log_files[:5]:
                log_path = os.path.join(logs_dir, lf)
                size_kb = os.path.getsize(log_path) / 1024
                st.caption(f"📋 {lf} ({size_kb:.1f} KB)")
        else:
            st.caption("No log files found.")
    else:
        st.caption("Logs directory not created yet (will be created when pipeline runs).")


# ─── Formatters ───────────────────────────────────────────────────────────────

def _format_status(status):
    """Format status for display."""
    status_labels = {
        'processing':                '⏳ Processing',
        'scored_high':               '🟢 Scored — High',
        'scored_medium':             '🟡 Scored — Medium',
        'scored_low':                '🟠 Scored — Low',
        'eliminated_pending_review': '🔴 Eliminated — Pending Review',
        'eliminated_confirmed':      '❌ Eliminated — Confirmed',
        'phone_screen_scheduled':    '📅 Phone Screen Scheduled',
        'phone_screen_pass_senior':  '✅ Passed — Senior',
        'phone_screen_pass_manager': '✅ Passed — Manager',
        'phone_screen_reject':       '❌ Phone Screen — Rejected',
        'handed_off':                '🏁 Handed Off',
        'error':                     '⚠️ Error',
    }
    return status_labels.get(status, status)


def _format_routing(routing):
    """Format role routing for display."""
    routing_labels = {
        'senior_only':               'Senior',
        'senior_plus_manager_flag':  'Senior + Mgr Flag',
        'manager_only':              'Manager',
        'eliminated':                'Eliminated',
    }
    return routing_labels.get(routing, routing or 'N/A')


if __name__ == "__main__":
    main()
