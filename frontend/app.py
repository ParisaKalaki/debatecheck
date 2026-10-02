"""
DebateCheck - Streamlit Frontend.

Start the FastAPI backend first (from backend/):
    uvicorn app.api.main:app --reload

Then start this frontend (from the repository root):
    streamlit run frontend/app.py
"""

import html
import os
import re
import time as time_module

import requests
import streamlit as st


API_URL = os.getenv("DEBATECHECK_API_URL", "http://127.0.0.1:8002")
VERIFY_URL = f"{API_URL.rstrip('/')}/verify"

st.set_page_config(
    page_title="DebateCheck | Health Claim Intelligence",
    page_icon="⚖️",
    layout="wide",
)

# CSS will be injected later via inject_chat_styles()

# ---------- Clean SVG Vector Icons (No generic emojis) ----------

SVG_ICONS = {
    "scale": """<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>""",
    "gavel": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="m14.5 12.5-8 8a2.119 2.119 0 1 1-3-3l8-8"/><path d="m16 16 6-6"/><path d="m8 8 6-6"/><path d="m9 7 8 8"/><path d="m21 11-8-8"/></svg>""",
    "shield_check": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>""",
    "shield_cross": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>""",
    "check_circle": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>""",
    "x_circle": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>""",
    "minus_circle": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/></svg>""",
    "alert_triangle": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>""",
    "chat_bubble": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>""",
    "brain": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04Z"/></svg>""",
    "file_text": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></svg>""",
}


# ---------- Polished CSS Design System (Unindented to prevent markdown code parsing) ----------

CHAT_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

/* Main typography & spacing */
html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Header Banner */
.brand-hero {
    background: linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(99, 102, 241, 0.06) 50%, rgba(168, 85, 247, 0.05) 100%);
    border: 1px solid rgba(99, 102, 241, 0.2);
    border-radius: 18px;
    padding: 22px 28px;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 18px;
}

.brand-icon-box {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    background: linear-gradient(135deg, #2563eb, #6366f1);
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
    flex-shrink: 0;
}

.brand-title {
    font-size: 1.65rem;
    font-weight: 700;
    line-height: 1.2;
    background: linear-gradient(90deg, #1e40af, #4f46e5);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}

[data-theme="dark"] .brand-title {
    background: linear-gradient(90deg, #60a5fa, #a5b4fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.brand-tagline {
    font-size: 0.92rem;
    opacity: 0.78;
    margin-top: 3px;
}

/* Section Header Bar */
.arena-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    margin: 1.5rem 0 1rem 0;
    background: rgba(0, 0, 0, 0.02);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 14px;
}

[data-theme="dark"] .arena-header {
    background: rgba(255, 255, 255, 0.03);
    border-color: rgba(255, 255, 255, 0.08);
}

.arena-title {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 1.15rem;
    font-weight: 700;
}

.arena-badge {
    font-size: 0.75rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 20px;
    background: rgba(99, 102, 241, 0.1);
    color: #4f46e5;
}

[data-theme="dark"] .arena-badge {
    background: rgba(99, 102, 241, 0.2);
    color: #a5b4fc;
}

/* Chat Conversation Canvas */
.chat-conversation-container {
    max-width: 900px;
    margin: 0.5rem auto 1.75rem auto;
    display: flex;
    flex-direction: column;
    gap: 1.1rem;
}

/* Chat Row: Left for PRO, Right for CON */
.chat-row {
    display: flex;
    width: 100%;
    margin-bottom: 0.25rem;
}

.chat-row-left {
    justify-content: flex-start;
}

.chat-row-right {
    justify-content: flex-end;
}

/* Base Chat Bubble */
.chat-bubble {
    max-width: 82%;
    min-width: 290px;
    padding: 18px 22px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.05);
    position: relative;
    box-sizing: border-box;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.chat-bubble:hover {
    box-shadow: 0 6px 22px rgba(15, 23, 42, 0.08);
    transform: translateY(-1px);
}

/* PRO Bubble (Left - Fresh Medical Blue) */
.chat-bubble-pro {
    background: linear-gradient(145deg, #f8faff 0%, #edf5ff 100%);
    border: 1.5px solid #bfdbfe;
    border-radius: 22px 22px 22px 5px;
    color: #0f172a;
}

/* CON Bubble (Right - Warm Coral/Rose) */
.chat-bubble-con {
    background: linear-gradient(145deg, #fffafa 0%, #ffedf0 100%);
    border: 1.5px solid #fecdd3;
    border-radius: 22px 22px 5px 22px;
    color: #0f172a;
}

/* Dark Mode Theme Support */
@media (prefers-color-scheme: dark) {
    .chat-bubble-pro {
        background: linear-gradient(145deg, #0b1a2e 0%, #112642 100%);
        border: 1.5px solid #1e3a8a;
        color: #f8fafc;
    }
    .chat-bubble-con {
        background: linear-gradient(145deg, #2b1119 0%, #3a1622 100%);
        border: 1.5px solid #881337;
        color: #f8fafc;
    }
}

[data-theme="dark"] .chat-bubble-pro {
    background: linear-gradient(145deg, #0b1a2e 0%, #112642 100%);
    border: 1.5px solid #1e3a8a;
    color: #f8fafc;
}

[data-theme="dark"] .chat-bubble-con {
    background: linear-gradient(145deg, #2b1119 0%, #3a1622 100%);
    border: 1.5px solid #881337;
    color: #f8fafc;
}

/* Bubble Header */
.chat-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.chat-header-con {
    justify-content: flex-end;
}

[data-theme="dark"] .chat-header {
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.agent-avatar-chip {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
    flex-shrink: 0;
}

.avatar-pro {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
}

.avatar-con {
    background: linear-gradient(135deg, #e11d48, #be123c);
}

.agent-name {
    font-size: 0.88rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}

.agent-round {
    font-size: 0.78rem;
    font-weight: 500;
    opacity: 0.72;
}

/* Argument Content: Human-friendly & scannable */
.chat-body {
    font-size: 0.96rem;
    line-height: 1.62;
}

.chat-points {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.point-item {
    position: relative;
    padding-left: 18px;
}

.point-item::before {
    content: "•";
    position: absolute;
    left: 4px;
    top: -1px;
    font-size: 1.25rem;
    color: #3b82f6;
    line-height: 1.5;
}

.chat-bubble-con .point-item::before {
    color: #f43f5e;
}

/* Inline Citation Pill Tag */
.chat-inline-source {
    font-size: 0.76rem;
    font-weight: 600;
    text-decoration: none !important;
    padding: 2px 7px;
    border-radius: 6px;
    background: rgba(37, 99, 235, 0.12);
    border: 1px solid rgba(37, 99, 235, 0.22);
    color: #1d4ed8 !important;
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    gap: 3px;
    margin-left: 4px;
    transition: all 0.15s ease;
}

.chat-bubble-con .chat-inline-source {
    background: rgba(225, 29, 72, 0.1);
    border-color: rgba(225, 29, 72, 0.2);
    color: #be123c !important;
}

[data-theme="dark"] .chat-inline-source {
    background: rgba(59, 130, 246, 0.2);
    border-color: rgba(59, 130, 246, 0.4);
    color: #93c5fd !important;
}

[data-theme="dark"] .chat-bubble-con .chat-inline-source {
    background: rgba(244, 63, 94, 0.2);
    border-color: rgba(244, 63, 94, 0.4);
    color: #fca5a5 !important;
}

.chat-inline-source:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}

/* Moderator Verdict Card */
.moderator-card {
    margin: 2rem 0 1.5rem 0;
    border-radius: 18px;
    border: 2px solid #6366f1;
    background: linear-gradient(145deg, rgba(99, 102, 241, 0.06) 0%, rgba(147, 51, 234, 0.03) 100%);
    padding: 26px;
    box-shadow: 0 8px 30px rgba(99, 102, 241, 0.09);
    position: relative;
    overflow: hidden;
}

.moderator-banner {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: linear-gradient(135deg, #6366f1, #4f46e5);
    color: #ffffff !important;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
    margin-bottom: 14px;
}

.moderator-title {
    font-size: 1.38rem;
    font-weight: 700;
    line-height: 1.45;
    margin: 8px 0 18px 0;
    color: inherit;
}

.moderator-metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 14px;
    margin-top: 14px;
}

.moderator-metric-box {
    padding: 12px 16px;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(99, 102, 241, 0.16);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
}

[data-theme="dark"] .moderator-metric-box {
    background: rgba(15, 23, 42, 0.6);
    border-color: rgba(99, 102, 241, 0.3);
}

.moderator-metric-label {
    font-size: 0.74rem;
    font-weight: 600;
    opacity: 0.72;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-bottom: 4px;
}

.moderator-metric-value {
    font-size: 1.15rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 6px;
}
</style>"""


def inject_chat_styles():
    """Inject modern, responsive CSS for the live debate chat conversation."""
    st.markdown(CHAT_CSS, unsafe_allow_html=True)

# Immediately inject styles so the header is styled from the start
inject_chat_styles()


# ---------- Helpers: Plain-Language Humanizer & Citations ----------

def confidence_percent(value) -> int:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, round(value * 100)))


def risk_badge_html(risk: str) -> str:
    """Return a clean vector status pill for risk levels."""
    risk_title = (risk or "Unknown").title()
    if risk_title == "Low":
        return f'{SVG_ICONS["check_circle"]} <span style="color: #10b981; font-weight: 700;">Low Risk</span>'
    elif risk_title == "High":
        return f'{SVG_ICONS["x_circle"]} <span style="color: #ef4444; font-weight: 700;">High Risk</span>'
    else:
        return f'{SVG_ICONS["alert_triangle"]} <span style="color: #f59e0b; font-weight: 700;">Medium Risk</span>'


def stance_badge_html(stance: str) -> str:
    """Return a clean vector icon for stance."""
    stance_lower = (stance or "neutral").lower()
    if stance_lower == "support":
        return SVG_ICONS["check_circle"]
    elif stance_lower == "contradict":
        return SVG_ICONS["x_circle"]
    return SVG_ICONS["minus_circle"]


def get_citation_url(cid: str, evidence_by_id: dict) -> str:
    """Retrieve the real PubMed URL for an evidence snippet ID.
    Falls back to PMID extraction or the PubMed homepage if not found."""
    norm_id = re.sub(r"[\u2010-\u2015]", "-", str(cid)).strip()
    clean_id = re.sub(r"[^\w\-]", "", norm_id)
    item = evidence_by_id.get(clean_id) or evidence_by_id.get(norm_id) or evidence_by_id.get(cid)
    if item and item.get("source_url"):
        return item["source_url"]

    # Extract PMID if formatted as E-<pmid>-<chunk>
    pmid_match = re.match(r"^E-(\d+)", clean_id, re.IGNORECASE)
    if pmid_match:
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmid_match.group(1)}/"

    return "https://pubmed.ncbi.nlm.nih.gov/"


def humanize_text(text: str) -> str:
    """Make dense academic sentences conversational, human-friendly, and concise."""
    if not text:
        return ""

    replacements = [
        (r"\bdemonstrated the greatest potential effect in preventing\b", "showed the strongest effect at preventing"),
        (r"\bindicated that\b", "found that"),
        (r"\bconcluded that vitamin D supplementation reduces\b", "concluded that vitamin D helps reduce"),
        (r"\bstatistically significant differences?\b", "meaningful difference"),
        (r"\bstatistically significant\b", "meaningful"),
        (r"\brandomized controlled trials\b", "clinical trials"),
        (r"\bacute respiratory infection-related healthcare visits\b", "doctor visits for respiratory infections"),
        (r"\bacute respiratory tract infections\b", "respiratory infections"),
        (r"\bacute respiratory infections\b", "respiratory infections"),
        (r"\bproportion of children under five years of age who make\b", "number of young children needing"),
        (r"\bproportion of children making healthcare visits for\b", "number of children needing clinic visits for"),
        (r"\bchronic cholecalciferol supplementation\b", "regular vitamin D intake"),
        (r"\bindependently associated with a reduced risk of\b", "linked to a lower risk of"),
        (r"\bSARS-CoV-2 breakthrough infection after vaccination\b", "COVID-19 breakthrough infections"),
        (r"\bdoes not reduce the mean number of visits or proportion of children visiting for\b", "does not lower clinic visits for"),
        (r"\bdirect comparison meta-analyses actually revealed\b", "direct trial comparisons showed"),
        (r"\bnetwork meta-analysis demonstrates that\b", "comprehensive trials show that"),
        (r"\boptimal efficacy and a significant trend toward\b", "the highest efficacy with"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Break up long compound run-ons into punchier sentences
    text = re.sub(r",\s*compared to\b", ". In comparison with", text, flags=re.IGNORECASE)
    text = re.sub(r",\s*whereas\b", ". In contrast,", text, flags=re.IGNORECASE)
    text = re.sub(r",\s*while the opponent\b", ". While the opponent", text, flags=re.IGNORECASE)
    text = re.sub(r";\s*", ". ", text)

    return text


def replace_citation_ids_markdown(text: str, evidence_by_id: dict) -> str:
    """Replace any raw citation IDs in Markdown text with clean [Source ↗](url) links."""
    if not text:
        return ""

    text = humanize_text(text)

    def repl_brackets(m):
        inner = m.group(1)
        ids = re.findall(r"E[-\u2010-\u2015]\d+[-\u2010-\u2015]\d+", inner, re.IGNORECASE)
        if not ids:
            return m.group(0)
        links = []
        seen = set()
        for cid in ids:
            url = get_citation_url(cid, evidence_by_id)
            if url not in seen:
                seen.add(url)
                links.append(f"[Source ↗]({url})")
        return "(" + " · ".join(links) + ")"

    def repl_single(m):
        raw_id = m.group(1) if m.lastindex else m.group(0)
        url = get_citation_url(raw_id, evidence_by_id)
        return f"[Source ↗]({url})"

    text = re.sub(r"\[([E0-9\s,\-–—\u2010-\u2015]+)\]", repl_brackets, text)
    text = re.sub(
        r"\(\s*(E[-\u2010-\u2015]\d+[-\u2010-\u2015]\d+)\s*\)",
        lambda m: f"({repl_single(m)})",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"E[-\u2010-\u2015]\d+[-\u2010-\u2015]\d+", repl_single, text, flags=re.IGNORECASE)
    return text


def clean_argument_html(argument: str, evidence_by_id: dict) -> str:
    """Format an agent's argument for human-friendly readability inside a chat bubble:
    - Translates dense medical journal phrasing into concise, conversational language.
    - Converts raw citation IDs into clickable 'Source ↗' inline pill links.
    - Formats bullets into clean points without walls of text.
    """
    if not argument:
        return "<p><em>No argument returned.</em></p>"

    def repl_brackets(m):
        inner = m.group(1)
        ids = re.findall(r"E[-\u2010-\u2015]\d+[-\u2010-\u2015]\d+", inner, re.IGNORECASE)
        if not ids:
            return m.group(0)
        links = []
        seen = set()
        for cid in ids:
            url = get_citation_url(cid, evidence_by_id)
            if url not in seen:
                seen.add(url)
                links.append(f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="chat-inline-source">Source ↗</a>')
        return "(" + " · ".join(links) + ")"

    def repl_single(m):
        raw_id = m.group(1) if m.lastindex else m.group(0)
        url = get_citation_url(raw_id, evidence_by_id)
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="chat-inline-source">Source ↗</a>'

    # Humanize sentence flow and terminology
    text = humanize_text(argument)

    # Replace bracketed citation groups e.g. [E-42143317-3, E-42143317-5]
    text = re.sub(r"\[([E0-9\s,\-–—\u2010-\u2015]+)\]", repl_brackets, text)
    # Replace parenthesized single IDs e.g. (E-42143317-4)
    text = re.sub(r"\(\s*(E[-\u2010-\u2015]\d+[-\u2010-\u2015]\d+)\s*\)", lambda m: f"({repl_single(m)})", text, flags=re.IGNORECASE)
    # Replace any leftover bare IDs
    text = re.sub(r"E[-\u2010-\u2015]\d+[-\u2010-\u2015]\d+", repl_single, text, flags=re.IGNORECASE)

    # Basic markdown formatting
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    bullet_items = []
    html_parts = []

    for line in lines:
        if line.startswith(("- ", "* ", "• ")):
            bullet_items.append(line[2:].strip())
        else:
            if bullet_items:
                html_parts.append('<div class="chat-points">' + "".join(f'<div class="point-item">{b}</div>' for b in bullet_items) + '</div>')
                bullet_items = []
            html_parts.append(f'<p style="margin: 0 0 8px 0;">{line}</p>')

    if bullet_items:
        html_parts.append('<div class="chat-points">' + "".join(f'<div class="point-item">{b}</div>' for b in bullet_items) + '</div>')

    return "".join(html_parts)


def sort_transcript_turns(transcript: list[dict]) -> list[dict]:
    """Ensure messages strictly follow round and side order:
    PRO round 1, CON round 1, PRO round 2, CON round 2."""
    def turn_sort_key(turn: dict):
        try:
            rnd = int(turn.get("round", 1))
        except (ValueError, TypeError):
            rnd = 1
        agent_order = 0 if str(turn.get("agent", "")).upper() == "PRO" else 1
        return (rnd, agent_order)

    return sorted(transcript, key=turn_sort_key)


def render_turn_bubble_html(turn: dict, evidence_by_id: dict) -> str:
    """Render a single turn (PRO or CON) as a clutter-free, modern messaging bubble.
    Notice: The redundant bottom source list is omitted as sources are cited inline."""
    agent = str(turn.get("agent", "Agent")).upper()
    is_pro = (agent == "PRO")
    rnd = turn.get("round", 1)

    row_class = "chat-row-left" if is_pro else "chat-row-right"
    bubble_class = "chat-bubble-pro" if is_pro else "chat-bubble-con"
    avatar_class = "avatar-pro" if is_pro else "avatar-con"
    avatar_icon = SVG_ICONS["shield_check"] if is_pro else SVG_ICONS["shield_cross"]
    agent_label = "PRO Agent" if is_pro else "CON Agent"
    role_desc = "Affirmative Claim" if is_pro else "Counter-Stance"

    if is_pro:
        header_html = (
            f'<div class="chat-header">'
            f'<div class="agent-avatar-chip {avatar_class}">{avatar_icon}</div>'
            f'<div>'
            f'<span class="agent-name">{agent_label}</span> '
            f'<span class="agent-round">• Round {rnd} ({role_desc})</span>'
            f'</div>'
            f'</div>'
        )
    else:
        header_html = (
            f'<div class="chat-header chat-header-con">'
            f'<div>'
            f'<span class="agent-round">Round {rnd} ({role_desc}) • </span>'
            f'<span class="agent-name">{agent_label}</span>'
            f'</div>'
            f'<div class="agent-avatar-chip {avatar_class}">{avatar_icon}</div>'
            f'</div>'
        )

    body_html = clean_argument_html(turn.get("argument", ""), evidence_by_id)

    # Return clean bubble with NO redundant bottom source row
    return (
        f'<div class="chat-row {row_class}">'
        f'<div class="chat-bubble {bubble_class}">'
        f'{header_html}'
        f'<div class="chat-body">{body_html}</div>'
        f'</div>'
        f'</div>'
    )


def render_moderator_card(verdict: dict):
    """Render the judge's verdict as a distinct, clearly separated moderator ruling card."""
    confidence = confidence_percent(verdict.get("confidence"))
    risk = verdict.get("misinformation_risk", "Unknown")
    verdict_label = verdict.get("verdict", "Unknown")
    final_answer = verdict.get("final_answer", verdict_label)

    v_lower = verdict_label.lower()
    if any(w in v_lower for w in ["support", "true", "proven", "affirm"]):
        status_color = "#10b981"
        status_icon = SVG_ICONS["check_circle"]
    elif any(w in v_lower for w in ["refute", "false", "debunk", "unsupported", "contradict"]):
        status_color = "#ef4444"
        status_icon = SVG_ICONS["x_circle"]
    else:
        status_color = "#f59e0b"
        status_icon = SVG_ICONS["alert_triangle"]

    moderator_html = (
        f'<div class="moderator-card">'
        f'<div class="moderator-banner">{SVG_ICONS["gavel"]} MODERATOR RULING • EVIDENCE SYNTHESIS</div>'
        f'<div class="moderator-title">{html.escape(final_answer)}</div>'
        f'<div class="moderator-metrics-grid">'
        f'<div class="moderator-metric-box">'
        f'<div class="moderator-metric-label">Verdict Verdict</div>'
        f'<div class="moderator-metric-value" style="color: {status_color};">{status_icon} {html.escape(verdict_label)}</div>'
        f'</div>'
        f'<div class="moderator-metric-box">'
        f'<div class="moderator-metric-label">Consensus Agreement</div>'
        f'<div class="moderator-metric-value">{confidence}%</div>'
        f'</div>'
        f'<div class="moderator-metric-box">'
        f'<div class="moderator-metric-label">Misinformation Risk</div>'
        f'<div class="moderator-metric-value">{risk_badge_html(risk)}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(moderator_html, unsafe_allow_html=True)


def render_evidence_card(item: dict):
    """Render an individual evidence item without exposing raw internal IDs."""
    stance = item.get("stance", "neutral")
    source_url = item.get("source_url")
    title_suffix = f' — <a href="{source_url}" target="_blank" style="text-decoration: none; font-weight: 600; color: #2563eb;">Open PubMed Paper ↗</a>' if source_url else ""

    with st.container(border=True):
        st.markdown(
            f"{stance_badge_html(stance)} <strong>{stance.title()} Evidence</strong>{title_suffix}",
            unsafe_allow_html=True,
        )
        st.write(item.get("text") or "No snippet text available.")

        c1, c2, c3, c4 = st.columns(4)
        c1.caption(f"Study design: {item.get('study_design') or 'Unknown'}")
        sample = item.get("sample_size")
        c2.caption(f"Sample size: {sample if sample is not None else 'Not stated'}")
        c3.caption(f"Publication date: {item.get('pub_date') or 'Unknown'}")
        c4.caption(f"Credibility: {item.get('source_credibility') or 'Unknown'}")

        if source_url:
            st.link_button("View PubMed Study ↗", source_url)


# ---------- Main Result Rendering Function ----------

def render_result(data: dict, live: bool = True):
    """Render the full verification result with the live chat conversation layout,
    followed by the moderator verdict card and collapsed secondary details."""
    inject_chat_styles()

    verdict = data.get("verdict", {})
    evidence = data.get("evidence", [])
    transcript = data.get("transcript", [])

    evidence_by_id = {
        item.get("id"): item for item in evidence if item.get("id")
    }
    ordered_transcript = sort_transcript_turns(transcript)

    # ==========================================
    # 1. LIVE CHAT CONVERSATION (PRIMARY FOCUS)
    # ==========================================
    arena_header_html = (
        f'<div class="arena-header">'
        f'<div class="arena-title">{SVG_ICONS["chat_bubble"]} Live Evidence Debate</div>'
        f'<div class="arena-badge">2 Rounds • AI Agents Grounded in PubMed</div>'
        f'</div>'
    )
    st.markdown(arena_header_html, unsafe_allow_html=True)

    chat_placeholder = st.empty()

    if live and ordered_transcript:
        accumulated_turns = []
        for turn in ordered_transcript:
            accumulated_turns.append(turn)
            bubbles_html = "".join(
                render_turn_bubble_html(t, evidence_by_id) for t in accumulated_turns
            )
            chat_placeholder.markdown(
                f'<div class="chat-conversation-container">{bubbles_html}</div>',
                unsafe_allow_html=True,
            )
            time_module.sleep(0.85)
    else:
        bubbles_html = "".join(
            render_turn_bubble_html(t, evidence_by_id) for t in ordered_transcript
        )
        chat_placeholder.markdown(
            f'<div class="chat-conversation-container">{bubbles_html}</div>',
            unsafe_allow_html=True,
        )

    # ==========================================
    # 2. MODERATOR VERDICT (BELOW CHAT)
    # ==========================================
    render_moderator_card(verdict)

    # ==========================================
    # 3. SECONDARY / COLLAPSED SECTIONS
    # ==========================================
    confidence = confidence_percent(verdict.get("confidence"))
    risk = verdict.get("misinformation_risk", "Unknown")

    st.markdown(f"### {SVG_ICONS['file_text']} Detailed Clinical Dossier", unsafe_allow_html=True)

    with st.expander("Analysis Breakdown & Study Limitations", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("Verdict", verdict.get("verdict", "Unknown"))
        c2.metric("Consensus Agreement", f"{confidence}%")
        c3.metric("Misinformation Risk", f"{risk}")

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

    col1, col2 = st.columns(2)
    with col1:
        with st.expander("Judge Reasoning & Synthesis", expanded=False):
            raw_reasoning = verdict.get("reasoning") or "No reasoning returned."
            st.markdown(replace_citation_ids_markdown(raw_reasoning, evidence_by_id))
    with col2:
        with st.expander("Key Counter-Evidence", expanded=False):
            raw_counter = verdict.get("top_counter_evidence") or "No counter-evidence returned."
            st.markdown(replace_citation_ids_markdown(raw_counter, evidence_by_id))

    with st.expander(f"Retrieved PubMed Literature ({len(evidence)} Snippets)", expanded=False):
        st.caption(f"{len(evidence)} evidence snippets were retrieved and assessed.")
        stance_filter = st.multiselect(
            "Filter evidence by stance",
            options=["support", "contradict", "neutral"],
            default=["support", "contradict", "neutral"],
            key="stance_filter_multiselect",
        )
        filtered = [e for e in evidence if e.get("stance") in stance_filter]
        if not filtered:
            st.info("No evidence snippets match the selected stance filter.")
        for item in filtered:
            render_evidence_card(item)


# ---------- Page Layout & State Management ----------

# Render Hero Brand Header
hero_html = (
    f'<div class="brand-hero">'
    f'<div class="brand-icon-box">{SVG_ICONS["scale"]}</div>'
    f'<div>'
    f'<h1 class="brand-title">DebateCheck</h1>'
    f'<div class="brand-tagline">Multi-Agent Health Claim Verification Grounded in Peer-Reviewed PubMed Literature</div>'
    f'</div>'
    f'</div>'
)
st.markdown(hero_html, unsafe_allow_html=True)

st.info(
    "DebateCheck is an educational evidence-verification tool, not medical advice. "
    "Its output depends on retrieved literature and AI interpretation. For personal "
    "medical decisions, consult a qualified health professional."
)

with st.form("claim_form"):
    claim = st.text_area(
        "Enter a health claim to verify:",
        placeholder="e.g. Vitamin D supplements prevent respiratory infections in children",
        height=100,
    )

    submitted = st.form_submit_button(
        "Verify Health Claim",
        type="primary",
        use_container_width=True,
    )

# Session State for persisting results across filter interactions
if "analysis_data" not in st.session_state:
    st.session_state["analysis_data"] = None
if "run_live_animation" not in st.session_state:
    st.session_state["run_live_animation"] = False

if submitted:
    if len(claim.strip()) < 5:
        st.warning("Please enter a specific health claim.")
    else:
        with st.spinner("Retrieving PubMed evidence and running the PRO vs CON debate..."):
            try:
                response = requests.post(
                    VERIFY_URL,
                    json={"claim": claim.strip()},
                    timeout=600,
                )
            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the backend.")
                st.stop()

        if not response.ok:
            st.error(f"Backend returned {response.status_code}")
            st.stop()

        # Persist response in session state
        st.session_state["analysis_data"] = response.json()
        st.session_state["run_live_animation"] = True

# Display results if available in session state (preserves view across filter clicks!)
if st.session_state.get("analysis_data"):
    # Only animate live on brand new submissions, not on filter reruns!
    should_animate = st.session_state.pop("run_live_animation", False)
    render_result(st.session_state["analysis_data"], live=should_animate)