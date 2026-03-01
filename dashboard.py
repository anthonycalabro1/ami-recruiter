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
    get_dashboard_stats, update_candidate_status, get_status_history,
    save_rubric_feedback, get_pending_feedback, get_candidates_by_tier,
    get_recent_activity, get_processing_timeline, get_area_distribution
)
from notifications import generate_handoff_email

st.set_page_config(
    page_title="AMI Recruiting Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1B3A5C, #2E75B6);
        color: white;
        padding: 20px 30px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .metric-card {
        background: white;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        text-align: center;
    }
    .tier-high { background-color: #1B7A2F; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; }
    .tier-medium { background-color: #CC7A00; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; }
    .tier-low { background-color: #CC4400; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; }
    .tier-eliminated { background-color: #CC0000; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 4px 4px 0 0;
    }
    /* Fix selectbox dropdown visibility */
    [data-baseweb="popover"] {
        background-color: #1e2a3a !important;
        border: 1px solid #4a90d9 !important;
        border-radius: 8px !important;
    }
    [data-baseweb="menu"] {
        background-color: #1e2a3a !important;
    }
    [data-baseweb="menu"] [role="option"] {
        color: #e0e8f0 !important;
        background-color: #1e2a3a !important;
    }
    [data-baseweb="menu"] [role="option"]:hover {
        background-color: #2e75b6 !important;
        color: #ffffff !important;
    }
    [data-baseweb="menu"] [aria-selected="true"] {
        background-color: #34526e !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)


def tier_badge(tier):
    """Create an HTML tier badge."""
    tier_class = f"tier-{tier.lower()}" if tier else "tier-eliminated"
    return f'<span class="{tier_class}">{tier}</span>'


def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0; font-size: 28px;">🎯 AMI Recruiting Dashboard</h1>
        <p style="margin:5px 0 0 0; opacity: 0.9;">Candidate Pipeline Management</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", [
        "📊 Pipeline Overview",
        "👤 Candidate Details",
        "📈 Analytics",
        "🔍 Eliminated Review",
        "📝 Rubric Feedback",
        "📧 Handoff Email Generator",
        "⚙️ System"
    ])

    # Auto-refresh control
    st.sidebar.divider()
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=False)
    if auto_refresh:
        refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 15, 120, 30)
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=refresh_interval * 1000, key="auto_refresh")
        except ImportError:
            # Fallback if streamlit-autorefresh not installed
            import time
            time.sleep(refresh_interval)
            st.rerun()

    # Recent Activity feed
    st.sidebar.divider()
    st.sidebar.subheader("Recent Activity")
    activity = get_recent_activity(5)
    if activity:
        for a in activity:
            st.sidebar.caption(
                f"**{a['candidate_name']}**: {_format_status(a['new_status'])} "
                f"({a['changed_by']}, {a['created_at'][:16]})"
            )
    else:
        st.sidebar.caption("No activity yet.")

    # Page routing
    if page == "📊 Pipeline Overview":
        show_pipeline_overview()
    elif page == "👤 Candidate Details":
        show_candidate_details()
    elif page == "📈 Analytics":
        show_analytics()
    elif page == "🔍 Eliminated Review":
        show_eliminated_review()
    elif page == "📝 Rubric Feedback":
        show_rubric_feedback()
    elif page == "📧 Handoff Email Generator":
        show_handoff_generator()
    elif page == "⚙️ System":
        show_system_status()


def show_pipeline_overview():
    """Show the main pipeline overview with metrics and candidate list."""
    stats = get_dashboard_stats()

    # Metrics row
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    with col1:
        st.metric("Total", stats['total_candidates'])
    with col2:
        st.metric("Processing", stats['processing'])
    with col3:
        st.metric("🟢 High", stats['high'])
    with col4:
        st.metric("🟡 Medium", stats['medium'])
    with col5:
        st.metric("🟠 Low", stats['low'])
    with col6:
        st.metric("🔴 Eliminated", stats['eliminated'])
    with col7:
        st.metric("✅ Handed Off", stats['handed_off'])

    st.divider()

    # Search box
    search_term = st.text_input("🔍 Search by candidate name", "", key="search")

    # Filter controls
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Filter by Status", [
            "All", "scored_high", "scored_medium", "scored_low",
            "eliminated_pending_review", "phone_screen_scheduled",
            "phone_screen_pass_senior", "phone_screen_pass_manager",
            "phone_screen_reject", "handed_off", "processing", "error"
        ])
    with col2:
        fa_filter = st.selectbox("Filter by Functional Area", [
            "All", "Strategy & Business Case", "Business Integration",
            "System Integration", "Field Deployment Management", "AMI Operations"
        ])
    with col3:
        sort_by = st.selectbox("Sort by", ["Most Recent", "Highest Score", "Name"])

    # Get candidates
    if status_filter == "All":
        candidates = get_all_candidates()
    else:
        candidates = get_all_candidates(status_filter)

    if not candidates:
        st.info("No candidates found. Drop resumes into the AMI_Candidates_Inbox folder to get started.")
        return

    # Build display data
    display_data = []
    for c in candidates:
        scores = get_candidate_scores(c['id'])

        # Filter by functional area if specified
        if fa_filter != "All":
            scores = [s for s in scores if s['functional_area'] == fa_filter]
            if not scores:
                continue

        highest_score = max(scores, key=lambda s: s['weighted_score'] or 0) if scores else None

        display_data.append({
            'ID': c['id'],
            'Name': c['name'],
            'AMI Years': c['total_ami_years'] or 0,
            'Role Routing': _format_routing(c['role_routing']),
            'Primary Area': highest_score['functional_area'] if highest_score else 'N/A',
            'Score': f"{highest_score['weighted_score']:.2f}" if highest_score and highest_score['weighted_score'] else 'N/A',
            'Tier': highest_score['tier'] if highest_score else 'N/A',
            'Status': _format_status(c['status']),
            'Areas Scored': len(scores),
            'Date': c['created_at'][:10] if c['created_at'] else ''
        })

    # Apply search filter
    if search_term:
        search_lower = search_term.lower()
        display_data = [d for d in display_data if search_lower in d['Name'].lower()]

    if not display_data:
        st.info("No candidates match the current filters.")
        return

    # Sort
    if sort_by == "Highest Score":
        display_data.sort(key=lambda x: float(x['Score']) if x['Score'] != 'N/A' else 0, reverse=True)
    elif sort_by == "Name":
        display_data.sort(key=lambda x: x['Name'])

    # Display as table
    df = pd.DataFrame(display_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # CSV Export + count
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Showing {len(display_data)} candidates")
    with col2:
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=f"ami_pipeline_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )


def show_candidate_details():
    """Show detailed view of a specific candidate."""
    candidates = get_all_candidates()

    if not candidates:
        st.info("No candidates in the system yet.")
        return

    # Candidate selector
    candidate_options = {f"{c['name']} (ID: {c['id']})": c['id'] for c in candidates}
    selected = st.selectbox("Select Candidate", list(candidate_options.keys()))
    candidate_id = candidate_options[selected]

    candidate = get_candidate(candidate_id)
    scores = get_candidate_scores(candidate_id)
    history = get_status_history(candidate_id)

    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.subheader(candidate['name'])
        if candidate['email']:
            st.write(f"📧 {candidate['email']}")
        if candidate['phone']:
            st.write(f"📱 {candidate['phone']}")
    with col2:
        st.metric("AMI Years", candidate['total_ami_years'] or 'N/A')
    with col3:
        st.metric("Role Routing", _format_routing(candidate['role_routing']))

    # Status management
    st.divider()
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write(f"**Current Status:** {_format_status(candidate['status'])}")
    with col2:
        new_status = st.selectbox("Update Status", [
            candidate['status'],
            "phone_screen_scheduled",
            "phone_screen_pass_senior",
            "phone_screen_pass_manager",
            "phone_screen_reject",
            "handed_off",
            "eliminated_confirmed"
        ], key="status_update")
        if new_status != candidate['status']:
            notes = st.text_input("Notes (optional)", key="status_notes")
            if st.button("Update Status"):
                update_candidate_status(candidate_id, new_status, 'user', notes)
                st.success(f"Status updated to: {_format_status(new_status)}")
                st.rerun()

    # Functional area scores
    st.divider()
    st.subheader("Functional Area Scores")

    if not scores:
        st.warning("No scores available yet.")
    else:
        for score in scores:
            tier = score['tier'] or 'N/A'
            with st.expander(
                f"{'🟢' if tier == 'HIGH' else '🟡' if tier == 'MEDIUM' else '🟠' if tier == 'LOW' else '🔴'} "
                f"{score['functional_area']} — {tier} ({score['weighted_score']:.2f})"
                + (" ⭐ Manager Stretch" if score['manager_stretch_flag'] else ""),
                expanded=(tier == 'HIGH')
            ):
                # Gate results
                st.write("**Gate Results:**")
                gate_col1, gate_col2, gate_col3 = st.columns(3)
                with gate_col1:
                    g1 = "✅" if score['gate1_pass'] else "❌"
                    st.write(f"{g1} Gate 1 (AMI Experience): {score['gate1_reason'] or ''}")
                with gate_col2:
                    g2 = "✅" if score['gate2_pass'] else "❌"
                    st.write(f"{g2} Gate 2 (AMI Years): {score['gate2_reason'] or ''}")
                with gate_col3:
                    g3 = "✅" if score.get('gate3_pass') else "❌"
                    st.write(f"{g3} Gate 3: {score.get('gate3_reason', '')}")

                # Dimension scores
                if score['dimension_scores']:
                    st.write("**Dimension Scores:**")
                    dim_scores = json.loads(score['dimension_scores']) if isinstance(score['dimension_scores'], str) else score['dimension_scores']
                    for dim_name, dim_data in dim_scores.items():
                        if isinstance(dim_data, dict):
                            s = dim_data.get('score', 'N/A')
                            r = dim_data.get('reasoning', '')
                            st.write(f"- **{dim_name}**: {s}/5 — {r}")

                # Narrative
                st.write("**Assessment:**")
                st.write(score['scoring_narrative'] or 'No narrative available.')

                # Manager stretch
                if score['manager_stretch_flag']:
                    st.info(f"⭐ **Manager Stretch Flag:** {score['manager_stretch_narrative']}")

                # Phone screen questions
                if score['phone_screen_questions']:
                    st.write("**Phone Screen Questions:**")
                    questions = json.loads(score['phone_screen_questions']) if isinstance(score['phone_screen_questions'], str) else score['phone_screen_questions']
                    for i, q in enumerate(questions, 1):
                        if isinstance(q, dict):
                            st.write(f"**Q{i}:** {q.get('question', '')}")
                            st.write(f"   *Dimension:* {q.get('dimension_tested', '')}")
                            st.write(f"   *Listen for:* {q.get('what_to_listen_for', '')}")
                            st.write(f"   *Red flags:* {q.get('red_flag_answers', '')}")
                            st.write("")
                        else:
                            st.write(f"**Q{i}:** {q}")

    # Parsed profile
    st.divider()
    with st.expander("📄 Parsed Resume Profile"):
        if candidate['parsed_profile']:
            profile = json.loads(candidate['parsed_profile']) if isinstance(candidate['parsed_profile'], str) else candidate['parsed_profile']
            st.json(profile)
        else:
            st.write("No parsed profile available.")

    # Status history
    with st.expander("📋 Status History"):
        if history:
            for h in history:
                st.write(f"**{h['created_at']}** — {_format_status(h['new_status'])} "
                         f"(by {h['changed_by']}) {': ' + h['notes'] if h['notes'] else ''}")
        else:
            st.write("No history available.")

    # Notes
    st.divider()
    st.subheader("Notes")
    current_notes = candidate.get('notes', '') or ''
    new_notes = st.text_area("Add/edit notes", value=current_notes, height=100, key="candidate_notes")
    if st.button("Save Notes") and new_notes != current_notes:
        from database import get_connection
        conn = get_connection()
        conn.execute("UPDATE candidates SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                     (new_notes, candidate_id))
        conn.commit()
        conn.close()
        st.success("Notes saved.")


def show_analytics():
    """Show pipeline analytics and funnel visualization."""
    st.subheader("📈 Pipeline Analytics")

    stats = get_dashboard_stats()

    # Pipeline Funnel
    st.write("**Pipeline Funnel**")
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

    for label, count in funnel_data:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.write(f"**{label}**")
        with col2:
            pct = (count / total) * 100
            st.progress(min(pct / 100, 1.0))
            st.caption(f"{count} ({pct:.0f}%)")

    st.divider()

    # Tier Distribution and Functional Area Distribution side by side
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Tier Distribution**")
        tier_data = {
            'Tier': ['HIGH', 'MEDIUM', 'LOW', 'ELIMINATED'],
            'Count': [stats['high'], stats['medium'], stats['low'], stats['eliminated']]
        }
        tier_df = pd.DataFrame(tier_data)
        st.bar_chart(tier_df.set_index('Tier'))

    with col2:
        st.write("**Functional Area Breakdown**")
        area_dist = get_area_distribution()
        if area_dist:
            area_df = pd.DataFrame(area_dist)
            # Pivot to show areas as rows, tiers as columns
            try:
                pivot = area_df.pivot_table(index='functional_area', columns='tier', values='count', fill_value=0)
                st.dataframe(pivot, use_container_width=True)
            except Exception:
                st.dataframe(area_df, use_container_width=True, hide_index=True)
        else:
            st.info("No scoring data yet.")

    st.divider()

    # Processing Timeline
    st.write("**Processing Timeline**")
    timeline = get_processing_timeline()
    if timeline:
        timeline_df = pd.DataFrame(timeline)
        timeline_df['date'] = pd.to_datetime(timeline_df['date'])
        timeline_df = timeline_df.set_index('date')
        st.bar_chart(timeline_df['count'])
    else:
        st.info("No processing data yet.")

    # Summary metrics
    st.divider()
    st.write("**Summary**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        pass_rate = (scored / total * 100) if total > 0 else 0
        st.metric("Pass Rate (scored/total)", f"{pass_rate:.0f}%")
    with col2:
        high_rate = (stats['high'] / total * 100) if total > 0 else 0
        st.metric("High Tier Rate", f"{high_rate:.0f}%")
    with col3:
        elim_rate = (stats['eliminated'] / total * 100) if total > 0 else 0
        st.metric("Elimination Rate", f"{elim_rate:.0f}%")
    with col4:
        st.metric("Avg Areas/Candidate", f"{_avg_areas_scored():.1f}")


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


def show_eliminated_review():
    """Show eliminated candidates for review and feedback."""
    st.subheader("🔍 Eliminated Candidates — Pending Review")
    st.write("Review eliminated candidates to verify the rubric's assessment. "
             "Override or provide feedback to improve the rubric.")

    candidates = get_all_candidates('eliminated_pending_review')

    if not candidates:
        st.success("No eliminated candidates pending review.")
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


def show_rubric_feedback():
    """Show accumulated rubric feedback."""
    st.subheader("📝 Rubric Feedback Queue")
    st.write("Accumulated feedback from eliminated candidate reviews. "
             "Use this to identify patterns and update rubrics.")

    feedback = get_pending_feedback()

    if not feedback:
        st.success("No pending rubric feedback.")
        return

    for fb in feedback:
        with st.expander(f"📋 {fb['candidate_name']} — {fb['functional_area']} — {fb['created_at'][:10]}"):
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


def show_handoff_generator():
    """Generate handoff emails for candidates who passed phone screen."""
    st.subheader("📧 Handoff Email Generator")
    st.write("Generate pre-written emails for candidates who passed the phone screen.")

    # Get candidates with passing status
    candidates = (get_all_candidates('phone_screen_pass_senior') +
                  get_all_candidates('phone_screen_pass_manager'))

    if not candidates:
        st.info("No candidates have passed the phone screen yet. "
                "Update a candidate's status to 'Phone Screen Pass' from the Candidate Details page.")
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


def show_system_status():
    """Show system status and failed resume management."""
    st.subheader("⚙️ System Status")

    # Failed files
    failed_folder = os.path.join(PROJECT_DIR, "AMI_Candidates_Failed")
    inbox_folder = os.path.join(PROJECT_DIR, "AMI_Candidates_Inbox")
    processed_folder = os.path.join(PROJECT_DIR, "AMI_Candidates_Processed")

    col1, col2, col3 = st.columns(3)
    with col1:
        inbox_count = len([f for f in os.listdir(inbox_folder) if os.path.isfile(os.path.join(inbox_folder, f))]) if os.path.exists(inbox_folder) else 0
        st.metric("Inbox", inbox_count)
    with col2:
        processed_count = len([f for f in os.listdir(processed_folder) if os.path.isfile(os.path.join(processed_folder, f))]) if os.path.exists(processed_folder) else 0
        st.metric("Processed", processed_count)
    with col3:
        failed_files = [f for f in os.listdir(failed_folder)
                        if not f.endswith('.reason.txt') and os.path.isfile(os.path.join(failed_folder, f))] if os.path.exists(failed_folder) else []
        st.metric("Failed", len(failed_files))

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


def _format_status(status):
    """Format status for display."""
    status_labels = {
        'processing': '⏳ Processing',
        'scored_high': '🟢 Scored — High',
        'scored_medium': '🟡 Scored — Medium',
        'scored_low': '🟠 Scored — Low',
        'eliminated_pending_review': '🔴 Eliminated — Pending Review',
        'eliminated_confirmed': '❌ Eliminated — Confirmed',
        'phone_screen_scheduled': '📅 Phone Screen Scheduled',
        'phone_screen_pass_senior': '✅ Passed — Senior',
        'phone_screen_pass_manager': '✅ Passed — Manager',
        'phone_screen_reject': '❌ Phone Screen — Rejected',
        'handed_off': '🏁 Handed Off',
        'error': '⚠️ Error'
    }
    return status_labels.get(status, status)


def _format_routing(routing):
    """Format role routing for display."""
    routing_labels = {
        'senior_only': 'Senior',
        'senior_plus_manager_flag': 'Senior + Mgr Flag',
        'manager_only': 'Manager',
        'eliminated': 'Eliminated'
    }
    return routing_labels.get(routing, routing or 'N/A')


if __name__ == "__main__":
    main()
