"""UBID Reviewer Console — Streamlit UI.

Run: streamlit run frontend/reviewer_console.py
"""
import os
import httpx
import streamlit as st
import plotly.graph_objects as go

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="UBID Reviewer Console",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("UBID Platform")
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Review Queue", "UBID Lookup", "Activity Status", "Query Explorer"],
)
reviewer_id = st.sidebar.text_input("Reviewer ID", value="reviewer_001")
reviewer_tier = st.sidebar.selectbox("Tier", ["junior", "senior"])

# ── API helpers ────────────────────────────────────────────────────────────────

def api_get(path: str, params: dict = None):
    try:
        r = httpx.get(f"{API_BASE}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, body: dict):
    try:
        r = httpx.post(f"{API_BASE}{path}", json=body, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# ── Dashboard ─────────────────────────────────────────────────────────────────
if page == "Dashboard":
    st.title("Platform Dashboard")

    stats = api_get("/api/v1/query/stats")
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total UBIDs", stats.get("total_ubids", 0))
        col2.metric("Source Records", stats.get("total_source_records", 0))
        col3.metric("Review Queue", stats.get("queue", {}).get("pending", 0))
        col4.metric("Quarantine", stats.get("quarantine", {}).get("unresolved", 0))

        # Verdict distribution pie chart
        vd = stats.get("verdict_distribution", {})
        if vd:
            fig = go.Figure(go.Pie(
                labels=list(vd.keys()),
                values=list(vd.values()),
                hole=0.4,
                marker_colors=["#2ecc71", "#e67e22", "#e74c3c", "#3498db", "#95a5a6"],
            ))
            fig.update_layout(title="Verdict Distribution", height=350)
            st.plotly_chart(fig, use_container_width=True)

        # Records by source
        by_source = stats.get("records_by_source", {})
        if by_source:
            fig2 = go.Figure(go.Bar(
                x=list(by_source.keys()),
                y=list(by_source.values()),
                marker_color="#3498db",
            ))
            fig2.update_layout(title="Records by Source System", height=300)
            st.plotly_chart(fig2, use_container_width=True)


# ── Review Queue ───────────────────────────────────────────────────────────────
elif page == "Review Queue":
    st.title("Review Queue")

    data = api_get("/api/v1/review/queue", params={"limit": 10})
    if not data:
        st.info("No data from API.")
        st.stop()

    qstats = data.get("stats", {})
    col1, col2 = st.columns(2)
    col1.metric("Pending", qstats.get("pending", 0))
    col2.metric("Decided", qstats.get("decided", 0))

    items = data.get("items", [])
    if not items:
        st.success("Queue is empty — all caught up!")
        st.stop()

    st.subheader(f"Top {len(items)} items by priority")

    for item in items:
        prob = item.get("calibrated_probability", 0)
        priority = item.get("priority_score", 0)

        with st.expander(
            f"Priority {priority:.3f} | p={prob:.3f} | "
            f"Pair {item['pair_id'][:8]}…",
            expanded=(priority > 0.6),
        ):
            col_a, col_b = st.columns(2)

            rec_a = item.get("record_a", {})
            rec_b = item.get("record_b", {})

            with col_a:
                st.markdown(f"**Record A** — `{rec_a.get('source_system')}`")
                st.write(f"**Name:** {rec_a.get('name_raw', '')}")
                st.write(f"**Address:** {rec_a.get('address_raw', '')}")
                st.write(f"**PIN:** {rec_a.get('pin_code', '')} | **PAN:** {rec_a.get('pan', 'N/A')}")
                st.write(f"**Sector:** {rec_a.get('sector_raw', 'N/A')}")

            with col_b:
                st.markdown(f"**Record B** — `{rec_b.get('source_system')}`")
                st.write(f"**Name:** {rec_b.get('name_raw', '')}")
                st.write(f"**Address:** {rec_b.get('address_raw', '')}")
                st.write(f"**PIN:** {rec_b.get('pin_code', '')} | **PAN:** {rec_b.get('pan', 'N/A')}")
                st.write(f"**Sector:** {rec_b.get('sector_raw', 'N/A')}")

            # SHAP contributions bar chart
            shap = item.get("shap_contributions", {})
            fv = item.get("feature_vector", {})
            if shap:
                top_feats = sorted(shap.items(), key=lambda x: abs(x[1]), reverse=True)[:8]
                feat_names = [f[0] for f in top_feats]
                feat_vals = [f[1] for f in top_feats]
                colors = ["#2ecc71" if v > 0 else "#e74c3c" for v in feat_vals]
                fig = go.Figure(go.Bar(
                    x=feat_vals, y=feat_names, orientation="h",
                    marker_color=colors,
                ))
                fig.update_layout(title="Feature Contributions (SHAP)", height=250,
                                  margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)

            shared = item.get("shared_blocks", [])
            if shared:
                st.info(f"Shared blocking keys: {', '.join(shared)}")

            # Decision buttons
            cols = st.columns(4)
            queue_id = item.get("queue_id")
            pair_id = item["pair_id"]
            id_a = item["record_a"].get("canonical_id", "")
            id_b = item["record_b"].get("canonical_id", "")

            def make_decision(decision: str):
                result = api_post("/api/v1/review/decide", {
                    "queue_id": queue_id,
                    "pair_id": pair_id,
                    "canonical_id_a": id_a,
                    "canonical_id_b": id_b,
                    "decision": decision,
                    "reviewer_id": reviewer_id,
                    "reviewer_tier": reviewer_tier,
                })
                if result:
                    st.success(f"Decision submitted: {decision}")
                    st.rerun()

            if cols[0].button("✅ Confirm Match", key=f"match_{pair_id}"):
                make_decision("confirm_match")
            if cols[1].button("❌ Reject", key=f"reject_{pair_id}"):
                make_decision("reject")
            if cols[2].button("⏫ Defer to Senior", key=f"defer_{pair_id}"):
                make_decision("defer")
            if cols[3].button("🚩 Flag Quality", key=f"flag_{pair_id}"):
                make_decision("flag_quality")


# ── UBID Lookup ────────────────────────────────────────────────────────────────
elif page == "UBID Lookup":
    st.title("UBID Lookup")

    with st.form("lookup_form"):
        col1, col2 = st.columns(2)
        source = col1.selectbox("Source System", ["", "ekarmika", "fbis", "kspcb", "bescom"])
        record_id = col2.text_input("Source Record ID")
        pan = st.text_input("Or lookup by PAN")
        name = st.text_input("Or lookup by Name")
        pin = st.text_input("Pin Code (required with name)")
        submitted = st.form_submit_button("Lookup")

    if submitted:
        params = {}
        if source and record_id:
            params = {"source": source, "id": record_id}
        elif pan:
            params = {"pan": pan}
        elif name and pin:
            params = {"name": name, "pin": pin}

        if params:
            result = api_get("/api/v1/lookup", params=params)
            if result:
                st.json(result)


# ── Activity Status ────────────────────────────────────────────────────────────
elif page == "Activity Status":
    st.title("Activity Status")

    ubid_input = st.text_input("Enter UBID")
    force = st.checkbox("Force recompute (bypass cache)")

    if ubid_input and st.button("Get Status"):
        result = api_get(f"/api/v1/ubid/{ubid_input}/status", params={"force_recompute": force})
        if result:
            verdict = result.get("verdict", "unknown")
            score = result.get("continuity_score", 0)

            color = {"active": "🟢", "dormant": "🟡", "closed": "🔴",
                     "closed_by_silence": "🔴", "nascent": "🔵"}.get(verdict, "⚪")
            st.subheader(f"{color} Verdict: **{verdict.upper()}** (score: {score:.4f})")

            overrides = result.get("deterministic_overrides", [])
            if overrides:
                st.warning("Deterministic overrides: " + "; ".join(overrides))

            timeline = result.get("evidence_timeline", [])
            if timeline:
                st.subheader("Evidence Timeline")
                for entry in timeline[:20]:
                    sign = "+" if entry.get("sign", 1) > 0 else "-"
                    st.write(
                        f"`{entry.get('event_date')}` "
                        f"**{entry.get('event_type')}** "
                        f"({entry.get('source_system')}) "
                        f"→ {sign}{abs(entry.get('decayed_contribution', 0)):.4f} "
                        f"[{entry.get('days_ago')} days ago]"
                    )


# ── Query Explorer ─────────────────────────────────────────────────────────────
elif page == "Query Explorer":
    st.title("Query Explorer")
    st.markdown("Run the exemplar query: *active factories in pin X with no inspection in N months*")

    with st.form("query_form"):
        col1, col2 = st.columns(2)
        verdict = col1.selectbox("Verdict", ["active", "dormant", "closed", "nascent"])
        source_filter = col1.selectbox("Source System Filter", ["", "ekarmika", "fbis", "kspcb", "bescom"])
        pin_code = col2.text_input("Pin Code")
        district = col2.text_input("District")
        sector_kw = st.text_input("Sector Keyword (e.g. 'factory', 'textile')")
        no_event_type = st.selectbox(
            "No event of type",
            ["", "fac_inspection", "fac_form20_annual", "kspcb_compliance_report",
             "bescom_bill_paid", "se_renewal_pre2019"],
        )
        no_event_days = st.number_input("… in the last N days", min_value=0, value=540)
        limit = st.slider("Result limit", 10, 500, 50)
        run = st.form_submit_button("Run Query")

    if run:
        body = {
            "verdict": verdict,
            "pin_code": pin_code or None,
            "district": district or None,
            "sector_keyword": sector_kw or None,
            "source_system": source_filter or None,
            "no_event_type": no_event_type or None,
            "no_event_since_days": int(no_event_days) if no_event_type and no_event_days else None,
            "limit": limit,
            "offset": 0,
        }
        result = api_post("/api/v1/query/active-businesses", body)
        if result:
            st.success(f"Found {result.get('total', 0)} matching UBIDs")
            rows = result.get("results", [])
            if rows:
                import pandas as pd
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True)
