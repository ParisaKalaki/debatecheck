"""
DebateCheck - Person 4 Streamlit frontend.

Start the FastAPI backend first (from backend/):
    uvicorn app.api.main:app --reload

Then start this frontend (from the repository root):
    streamlit run frontend/app.py
"""

import os
import re

import requests
import streamlit as st


API_URL = os.getenv("DEBATECHECK_API_URL", "http://127.0.0.1:8000")
VERIFY_URL = f"{API_URL.rstrip('/')}/verify"

st.set_page_config(
    page_title="DebateCheck",
    page_icon="⚖️",
    layout="wide",
)

# ---------- Small UI helpers ----------

def confidence_percent(value) -> int:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, round(value * 100)))


def risk_icon(risk: str) -> str:
    return {
        "Low": "🟢",
        "Medium": "🟠",
        "High": "🔴",
    }.get(risk, "⚪")


def stance_icon(stance: str) -> str:
    return {
        "support": "✅",
        "contradict": "❌",
        "neutral": "➖",
    }.get(stance, "•")


def clean_argument(argument: str) -> str:
    """Make the agent's bullet-style text easy to read in Streamlit."""
    if not argument:
        return "No argument returned."
    return argument.strip()


def evidence_ids_in_turn(turn: dict) -> list[str]:
    ids = turn.get("cited_ids") or []
    return list(dict.fromkeys(ids))


def render_evidence_card(item: dict):
    stance = item.get("stance", "neutral")
    snippet_id = item.get("id", "Unknown ID")

    with st.container(border=True):
        st.markdown(f"**{stance_icon(stance)} {snippet_id} — {stance.title()}**")
        st.write(item.get("text") or "No snippet text available.")

        c1, c2, c3, c4 = st.columns(4)
        c1.caption(f"Study design: {item.get('study_design') or 'Unknown'}")
        sample = item.get("sample_size")
        c2.caption(f"Sample size: {sample if sample is not None else 'Not stated'}")
        c3.caption(f"Publication date: {item.get('pub_date') or 'Unknown'}")
        c4.caption(f"Credibility: {item.get('source_credibility') or 'Unknown'}")

        source_url = item.get("source_url")
        if source_url:
            st.link_button("Open PubMed paper ↗", source_url)


def render_result(data: dict):
    verdict = data["verdict"]
    confidence = confidence_percent(verdict.get("confidence"))
    risk = verdict.get("misinformation_risk", "Unknown")

    # ----- Main result -----
    st.subheader("Verification result")

    with st.container(border=True):
        st.markdown(f"### {verdict.get('final_answer', verdict.get('verdict', 'Result'))}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Verdict", verdict.get("verdict", "Unknown"))
        c2.metric("Confidence", f"{confidence}%")
        c3.metric("Misinformation risk", f"{risk_icon(risk)} {risk}")

        st.progress(confidence / 100)
        st.caption(
            "Confidence is the judge's self-consistency agreement rate across "
            "independent judge runs; it is not a probability that the medical claim is true."
        )

        st.markdown("**Why this risk level?**")
        st.write(verdict.get("risk_reason") or "No risk explanation was returned.")

        gap = verdict.get("evidence_gap_note")
        if gap:
            st.warning(f"Uncertainty / evidence limitations: {gap}")
        else:
            st.info(
                "Uncertainty / evidence limitations: This result is based on the PubMed "
                "evidence retrieved for this query and may not represent all available "
                "medical research."
            )

    with st.expander("Judge reasoning"):
        st.write(verdict.get("reasoning") or "No reasoning returned.")

    with st.expander("Strongest counter-evidence"):
        st.write(verdict.get("top_counter_evidence") or "No counter-evidence returned.")

    # ----- Debate -----
    st.subheader("PRO vs CON debate")
    st.caption(
        "Each point is constrained to evidence IDs returned by the retrieval pipeline."
    )

    evidence_by_id = {
        item.get("id"): item for item in data.get("evidence", []) if item.get("id")
    }

    transcript = data.get("transcript", [])
    for turn in transcript:
        agent = turn.get("agent", "Agent")
        rnd = turn.get("round", "?")
        title = f"{'🟦' if agent == 'PRO' else '🟥'} {agent} — Round {rnd}"

        with st.container(border=True):
            st.markdown(f"#### {title}")
            st.markdown(clean_argument(turn.get("argument", "")))

            cited_ids = evidence_ids_in_turn(turn)
            if cited_ids:
                cited_text = ", ".join(f"`{x}`" for x in cited_ids)
                st.caption(f"Cited evidence: {cited_text}")

                with st.expander("View evidence cited in this turn"):
                    for evidence_id in cited_ids:
                        item = evidence_by_id.get(evidence_id)
                        if item:
                            render_evidence_card(item)

    # ----- All evidence -----
    st.subheader("Retrieved PubMed evidence")
    evidence = data.get("evidence", [])
    st.caption(f"{len(evidence)} evidence snippets were retrieved and assessed.")

    stance_filter = st.multiselect(
        "Filter evidence by stance",
        options=["support", "contradict", "neutral"],
        default=["support", "contradict", "neutral"],
    )

    filtered = [e for e in evidence if e.get("stance") in stance_filter]
    for item in filtered:
        render_evidence_card(item)



# ---------- Page ----------

st.title("⚖️ DebateCheck")
st.markdown(
    "**Multi-agent health claim verification grounded in PubMed evidence.** "
    "Enter a checkable health claim to see the evidence, the PRO/CON debate, "
    "and a quality-weighted judge verdict."
)

st.info(
    "DebateCheck is an educational evidence-verification tool, not medical advice. "
    "Its output depends on retrieved literature and AI interpretation. For personal "
    "medical decisions, consult a qualified health professional."
)

with st.form("claim_form"):
    claim = st.text_area(
        "Health claim",
        placeholder="e.g. Vitamin D supplements prevent respiratory infections",
        height=110,
    )

    submitted = st.form_submit_button(
        "Check claim",
        type="primary",
        use_container_width=True,
    )

if submitted:
    if len(claim.strip()) < 5:
        st.warning("Please enter a specific health claim.")
    else:
        status = st.status("Running DebateCheck...", expanded=True)
        status.write("1/3 Retrieving and classifying PubMed evidence...")
        status.write("2/3 Preparing the evidence-grounded PRO/CON debate...")
        status.write("3/3 Asking the quality-weighted judge for a verdict...")

        try:
            response = requests.post(
                VERIFY_URL,
                json={
                    "claim": claim.strip(),
                },
                timeout=600,
            )

            if response.ok:
                data = response.json()
                status.update(
                    label="DebateCheck analysis complete",
                    state="complete",
                    expanded=False,
                )
                render_result(data)
            else:
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                status.update(label="Analysis failed", state="error")
                st.error(f"Backend returned {response.status_code}: {detail}")

        except requests.exceptions.ConnectionError:
            status.update(label="Backend unavailable", state="error")
            st.error(
                "Could not connect to the DebateCheck API. Start the FastAPI backend "
                "with: uvicorn app.api.main:app --reload"
            )
        except requests.exceptions.Timeout:
            status.update(label="Request timed out", state="error")
            st.error(
                "The analysis took too long. This can happen when an external model "
                "provider is rate-limited. Please try again shortly."
            )
        except requests.RequestException as exc:
            status.update(label="Request failed", state="error")
            st.error(f"Request failed: {exc}")
