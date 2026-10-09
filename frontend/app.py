"""
DebateCheck - Streamlit Frontend.

Start the FastAPI backend first (from backend/):
     uvicorn app.api.main:app --reload --port 8002

Then start this frontend (from the repository root):
    streamlit run frontend/app.py
"""

import html
import json
import os
import re
import time as time_module

import requests
import streamlit as st


API_URL = os.getenv("DEBATECHECK_API_URL", "http://127.0.0.1:8002").rstrip("/")
VERIFY_URL = f"{API_URL}/verify"
STREAM_URL = f"{API_URL}/verify/stream"
STATUS_URL = f"{API_URL}/config/status"
KEYS_URL = f"{API_URL}/config/keys"

# key name -> (label, help text, where to get it, hide input?)
KEY_HELP = {
    "NCBI_EMAIL": ("Your email address (for PubMed)",
                   "Not a secret - PubMed just asks who is searching.", None, False),
    "GOOGLE_API_KEY": ("Google Gemini API key",
                       "Free. Sign in, click 'Create API key', and copy it.",
                       "https://aistudio.google.com/apikey", True),
    "GROQ_API_KEY": ("Groq API key",
                     "Free. Sign in, click 'Create API Key', and copy it.",
                     "https://console.groq.com/keys", True),
    "NCBI_API_KEY": ("NCBI API key (optional)",
                     "Optional - only raises PubMed's rate limit. Account settings > API Key Management.",
                     "https://www.ncbi.nlm.nih.gov/account/settings/", True),
}
KEY_PAYLOAD_FIELD = {
    "NCBI_EMAIL": "ncbi_email",
    "GOOGLE_API_KEY": "google_api_key",
    "GROQ_API_KEY": "groq_api_key",
    "NCBI_API_KEY": "ncbi_api_key",
}

st.set_page_config(
    page_title="DebateCheck | Health Claim Intelligence",
    page_icon="⚖️",
    layout="wide",
    # Collapsed after keys are successfully set up (see render_key_form)
    initial_sidebar_state=st.session_state.get("sidebar_state", "auto"),
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

/* ===== Theme-agnostic overrides (readable in BOTH light and dark Streamlit themes) =====
   Streamlit does not set data-theme on the page, so the [data-theme="dark"] rules above
   never apply. These rules use semi-transparent tints and inherit the theme's text colour. */

.brand-title {
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.arena-header {
    background: rgba(99, 102, 241, 0.06);
    border: 1px solid rgba(99, 102, 241, 0.25);
}

.arena-badge {
    background: rgba(99, 102, 241, 0.18);
    color: #818cf8;
    border: 1px solid rgba(99, 102, 241, 0.4);
}

.chat-bubble-pro {
    background: rgba(59, 130, 246, 0.10);
    border: 1.5px solid rgba(59, 130, 246, 0.45);
    color: inherit;
}

.chat-bubble-con {
    background: rgba(244, 63, 94, 0.10);
    border: 1.5px solid rgba(244, 63, 94, 0.45);
    color: inherit;
}

.chat-header {
    border-bottom: 1px solid rgba(128, 128, 128, 0.25);
}

.chat-inline-source,
.chat-bubble-pro .chat-inline-source {
    background: #2563eb;
    border: 1px solid #2563eb;
    color: #ffffff !important;
}

.chat-bubble-con .chat-inline-source {
    background: #e11d48;
    border: 1px solid #e11d48;
    color: #ffffff !important;
}

.moderator-card {
    background: rgba(99, 102, 241, 0.07);
}

.moderator-metric-box {
    background: rgba(99, 102, 241, 0.10);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: inherit;
}

.moderator-metric-label {
    opacity: 0.85;
}

/* Debate conclusion card */
.conclusion-card {
    margin: 0 0 1.75rem 0;
    border-radius: 18px;
    border: 2px solid rgba(34, 197, 94, 0.6);
    background: rgba(34, 197, 94, 0.07);
    padding: 22px 26px;
}

.conclusion-label {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: #16a34a;
    color: #ffffff !important;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.conclusion-answer {
    font-size: 1.25rem;
    font-weight: 700;
    line-height: 1.45;
    margin: 14px 0 8px 0;
}

.conclusion-summary {
    font-size: 1rem;
    line-height: 1.65;
    margin-bottom: 10px;
}

.conclusion-caveat {
    font-size: 0.92rem;
    padding: 9px 13px;
    border-radius: 10px;
    background: rgba(34, 197, 94, 0.12);
}

/* Quick-answer (background knowledge) card */
.bg-card {
    margin: 0.5rem 0 1.5rem 0;
    border-radius: 18px;
    border: 2px solid #f59e0b;
    background: linear-gradient(145deg, rgba(245, 158, 11, 0.07) 0%, rgba(251, 191, 36, 0.03) 100%);
    padding: 22px 26px;
    box-shadow: 0 8px 30px rgba(245, 158, 11, 0.08);
}

.bg-label {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: linear-gradient(135deg, #f59e0b, #d97706);
    color: #ffffff !important;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.bg-headline {
    font-size: 1.28rem;
    font-weight: 700;
    line-height: 1.45;
    margin: 14px 0 8px 0;
}

.bg-takeaway {
    font-size: 1rem;
    line-height: 1.6;
    margin-bottom: 10px;
}

.bg-points {
    margin: 0 0 12px 1.1rem;
    padding: 0;
    line-height: 1.65;
}

.bg-note {
    font-size: 0.92rem;
    padding: 9px 13px;
    border-radius: 10px;
    background: rgba(245, 158, 11, 0.12);
    margin-bottom: 8px;
}

.bg-fineprint {
    font-size: 0.85rem;
    font-weight: 600;
    color: #ef4444;
    margin: -1.1rem 0 1.5rem 6px;
}

.bg-disclaimer {
    font-size: 0.8rem;
    opacity: 0.75;
    margin-top: 6px;
}
</style>"""


DC_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@600;700&display=swap');

:root {
    --dc-navy: #1f1b5e;
    --dc-navy-2: #2b2580;
    --dc-gold: #c99a2e;
    --dc-gold-soft: #f6ecd2;
    --dc-cream: #fbf8f1;
    --dc-line: #ebe4d3;
    --dc-ink: #1e1b3a;
    --dc-muted: #6b6782;
    --dc-pro: #2f3f9e;
    --dc-pro-soft: #e3e7fb;
    --dc-con: #b3263a;
    --dc-con-soft: #fbe3e7;
}

/* ---------- Premium outer frame around the whole page content ---------- */
[data-testid="stMainBlockContainer"] {
    position: relative;
    width: calc(100% - 3rem);
    max-width: 1240px;
    margin: 4.5rem auto 2.5rem auto;   /* clears Streamlit's top toolbar so the top edge is visible */
    padding: 2.4rem 2.6rem 2.6rem 2.6rem !important;
    border-radius: 28px;
    /* thin gold line + soft navy halo + depth shadow; works on light and dark backgrounds */
    box-shadow:
        inset 0 6px 0 #c99a2e,                    /* gold accent along the top edge (follows the curve) */
        0 0 0 1.5px rgba(201, 154, 46, 0.55),     /* thin gold outline */
        0 0 0 7px rgba(43, 37, 128, 0.07),        /* soft navy halo */
        0 24px 60px rgba(31, 27, 94, 0.16);       /* depth */
    overflow: visible !important;
}
@media (max-width: 640px) {
    [data-testid="stMainBlockContainer"] {
        width: calc(100% - 1rem);
        margin: 4rem auto 1.2rem auto;
        padding: 1.6rem 1rem 1.6rem 1rem !important;
        border-radius: 20px;
    }
}

/* ---------- Header bar ---------- */
.dc-header {
    display: flex; align-items: center; gap: 14px;
    background: linear-gradient(90deg, var(--dc-navy) 0%, var(--dc-navy-2) 100%);
    border-radius: 18px; padding: 18px 26px; margin-bottom: 14px;
}
.dc-header-logo { color: var(--dc-gold); display: flex; }
.dc-header-logo svg { width: 30px; height: 30px; }
.dc-header-title { color: #ffffff; font-size: 1.6rem; font-weight: 800; letter-spacing: -0.01em; line-height: 1.1; }
.dc-header-tagline { color: #c7c4ef; font-size: 0.85rem; margin-top: 2px; }

/* Claim form styled as the header search bar */
.st-key-claim_box [data-testid="stForm"] {
    background: linear-gradient(90deg, var(--dc-navy) 0%, var(--dc-navy-2) 100%);
    border: none; border-radius: 18px; padding: 18px 22px;
}
.st-key-claim_box [data-testid="stForm"] label p { color: #e4e2fb !important; font-weight: 600; }
.st-key-claim_box [data-baseweb="textarea"],
.st-key-claim_box [data-baseweb="base-input"] {
    background: #ffffff !important; border-radius: 14px !important; border: none !important;
}
.st-key-claim_box textarea {
    border-radius: 14px !important; background: #ffffff !important;
    color: #1e1b3a !important; -webkit-text-fill-color: #1e1b3a !important;
    caret-color: #1e1b3a !important;
}
.st-key-claim_box textarea::placeholder { color: #8a87a3 !important; -webkit-text-fill-color: #8a87a3 !important; }
.st-key-claim_box [data-testid="stFormSubmitButton"] button {
    background: linear-gradient(90deg, #d8ab3c, #c4922a) !important; color: var(--dc-navy) !important;
    border: none !important; border-radius: 999px !important; font-weight: 800 !important;
}

/* ---------- Generic cards ---------- */
.dc-grid { display: grid; gap: 16px; margin: 6px 0 18px 0;
           grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); }
.dc-card {
    background: var(--dc-cream); color: var(--dc-ink);
    border: 1px solid var(--dc-line); border-radius: 18px;
    padding: 20px 22px; box-shadow: 0 6px 20px rgba(31, 27, 94, 0.06);
}
.dc-card a { color: inherit; }
.dc-card-title { color: var(--dc-muted); font-size: 0.92rem; margin-bottom: 6px; }
.dc-serif { font-family: 'Roboto Slab', Georgia, serif; font-weight: 700; letter-spacing: -0.01em; }

/* Verdict card */
.dc-verdict { border-left: 5px solid var(--dc-gold); }
.dc-verdict-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dc-verdict-label { font-size: 2.6rem; line-height: 1.05; color: var(--dc-navy); }
.dc-verdict-text { font-size: 0.98rem; line-height: 1.5; margin: 10px 0 10px 0; }
.dc-pill { display: inline-block; background: #ebe7fb; color: var(--dc-navy-2);
           border-radius: 999px; padding: 3px 11px; font-size: 0.78rem; font-weight: 600; }
.dc-ring { text-align: center; flex-shrink: 0; }
.dc-ring-caption { color: var(--dc-gold); font-weight: 700; font-size: 0.9rem; margin-top: 2px; }

/* Risk card */
.dc-risk-label { font-size: 2.3rem; line-height: 1.1; }
.dc-risk-scale { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin: 12px 0 4px 0; }
.dc-risk-seg { height: 8px; border-radius: 99px; background: #e9e5f5; position: relative; }
.dc-risk-seg.active::before { content: "\\25BC"; position: absolute; top: -15px; left: 50%;
                              transform: translateX(-50%); font-size: 10px; color: var(--dc-navy); }
.dc-risk-names { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; text-align: center;
                 font-size: 0.8rem; color: var(--dc-muted); }
.dc-risk-names .active { color: var(--dc-ink); font-weight: 700; }
.dc-risk-reason { font-size: 0.92rem; line-height: 1.5; margin-top: 12px; }

/* Evidence quality card */
.dc-q-row { margin: 9px 0; }
.dc-q-head { display: flex; justify-content: space-between; font-size: 0.86rem; }
.dc-q-head span:last-child { color: var(--dc-muted); font-size: 0.78rem; }
.dc-q-bar { height: 6px; background: #ece8f6; border-radius: 99px; margin-top: 4px; overflow: hidden; }
.dc-q-fill { height: 100%; border-radius: 99px; }
.dc-split { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--dc-line); }
.dc-split-bar { display: flex; height: 8px; border-radius: 99px; overflow: hidden; background: #ece8f6; margin: 6px 0; }
.dc-split-legend { display: flex; justify-content: space-between; font-size: 0.8rem; font-weight: 700; }
.dc-note { color: var(--dc-muted); font-size: 0.76rem; margin-top: 8px; }

/* Debate */
.dc-section-title { display: flex; justify-content: space-between; align-items: baseline;
                    margin: 18px 2px 4px 2px; }
.dc-section-title h3 { margin: 0; font-size: 1.25rem; }
.dc-section-title span { font-size: 0.82rem; opacity: 0.75; }
.dc-agent-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.dc-agent-chip { display: inline-flex; align-items: center; gap: 7px; padding: 6px 14px;
                 border-radius: 999px; font-weight: 700; font-size: 0.95rem; }
.dc-agent-chip.pro { background: var(--dc-pro-soft); color: var(--dc-pro); }
.dc-agent-chip.con { background: var(--dc-con-soft); color: var(--dc-con); }
.dc-agent-sub { color: var(--dc-muted); font-size: 0.75rem; }
.dc-round { font-size: 0.74rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
            color: var(--dc-muted); margin: 14px 0 4px 0; }
.dc-point { display: flex; gap: 10px; margin: 10px 0 12px 0; }
.dc-num { flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%; color: #fff; font-size: 0.75rem;
          font-weight: 700; display: flex; align-items: center; justify-content: center; margin-top: 1px; }
.dc-num.pro { background: var(--dc-pro); }
.dc-num.con { background: var(--dc-con); }
.dc-point-text { font-size: 0.95rem; line-height: 1.5; }
.dc-tags { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 6px; }
.dc-tag { display: inline-block; text-decoration: none !important; border-radius: 999px;
          padding: 2px 10px; font-size: 0.74rem; border: 1px solid var(--dc-line); background: #f1ede2; }
.dc-tag.pro { color: var(--dc-pro) !important; }
.dc-tag.con { color: var(--dc-con) !important; }
.dc-tag:hover { filter: brightness(0.95); }

/* Traceable sources */
.dc-src { display: flex; align-items: center; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--dc-line);
          text-decoration: none !important; }
.dc-src:last-of-type { border-bottom: none; }
.dc-src-badge { width: 34px; height: 34px; border-radius: 9px; color: #fff; font-weight: 700; font-size: 0.8rem;
                display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.dc-src-main { flex: 1; min-width: 0; }
.dc-src-title { font-weight: 700; font-size: 0.9rem; color: var(--dc-ink); }
.dc-src-meta { font-size: 0.75rem; color: var(--dc-muted); }
.dc-dots { letter-spacing: 2px; font-size: 0.8rem; white-space: nowrap; }

/* Strongest counter-evidence */
.dc-counter { background: var(--dc-gold-soft); border: 1px solid #e8d49b; color: var(--dc-ink);
              border-radius: 18px; padding: 18px 22px; margin: 4px 0 18px 0; }
.dc-counter-label { display: inline-block; background: var(--dc-gold); color: #fff; border-radius: 999px;
                    padding: 3px 12px; font-size: 0.74rem; font-weight: 700; margin-bottom: 8px; }
.dc-counter a { color: var(--dc-navy-2); }

/* Quick answer + conclusion restyled as cream cards */
.bg-card { background: var(--dc-cream) !important; color: var(--dc-ink) !important;
           border: 1px solid var(--dc-line) !important; border-left: 5px solid var(--dc-gold) !important;
           box-shadow: 0 6px 20px rgba(31, 27, 94, 0.06) !important; }
.bg-label { background: var(--dc-gold) !important; }
.bg-note { background: var(--dc-gold-soft) !important; }
.conclusion-card { background: var(--dc-cream) !important; color: var(--dc-ink) !important;
                   border: 1px solid var(--dc-line) !important; border-left: 5px solid #16a34a !important; }
</style>"""



def inject_chat_styles():
    """Inject modern, responsive CSS (base styles + mockup-style dashboard)."""
    st.markdown(CHAT_CSS, unsafe_allow_html=True)
    st.markdown(DC_CSS, unsafe_allow_html=True)

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
        status_color = "#22c55e"
        status_icon = SVG_ICONS["check_circle"]
    elif any(w in v_lower for w in ["refute", "false", "debunk", "unsupported", "contradict"]):
        status_color = "#f43f5e"
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
        f'<div class="moderator-metric-label">Verdict</div>'
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


def render_claim_check_note(analysis: dict | None):
    """Show how the claim was interpreted and searched, for transparency."""
    if not analysis:
        return
    checkable = analysis.get("checkable_claim") or ""
    query = analysis.get("search_query_used") or analysis.get("pubmed_query") or ""
    if analysis.get("analysis_fallback"):
        st.caption("Claim analysis was unavailable, so the claim was searched as written.")
    st.caption(f"Checked against the evidence as: \u201c{checkable}\u201d")
    if query:
        st.caption(f"PubMed search used: {query}")


def render_background_card(background: dict | None, debate_available: bool):
    """One-line quick answer from general medical knowledge, pointing users to the
    evidence-based debate conclusion for a more informed answer."""
    if not background:
        return

    # Guidance inside the card (only when a debate exists)
    pointer_html = (
        '<div class="bg-takeaway">\U0001F4A1 <strong>For a more informed answer, read the '
        'Debate Conclusion below.</strong> It is based on real PubMed studies you can check, '
        'not just general AI knowledge.</div>'
        if debate_available else ""
    )

    # Fine print shown OUTSIDE the card, in muted text (not part of the answer)
    fineprint = "AI-generated from general knowledge, not from the retrieved studies."
    if not debate_available:
        fineprint = (
            "No research-based debate was possible for this claim, so treat this as general "
            "information only. " + fineprint
        )

    differs_html = ""
    if debate_available and background.get("differs_from_evidence_verdict"):
        note = html.escape(background.get("verdict_note") or "")
        differs_html = (
            f'<div class="bg-note">\u26A0\uFE0F <strong>This quick answer differs from the debate '
            f'result.</strong> {note} The debate conclusion is based on real, traceable studies, '
            f'so check it and its sources before deciding.</div>'
        )

    card_html = (
        f'<div class="bg-card">'
        f'<div class="bg-label">{SVG_ICONS["brain"]} Quick Answer \u2022 General Knowledge</div>'
        f'<div class="bg-headline">{html.escape(background.get("headline", ""))}</div>'
        f'{pointer_html}'
        f'{differs_html}'
        f'</div>'
        f'<div class="bg-fineprint">\u26A0\uFE0F ! {fineprint}</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


def render_no_debate_notice(evidence: list[dict]):
    """Plain-language notice when there was nothing to debate."""
    if evidence:
        st.warning(
            "**Not enough research to debate this claim.** We found some PubMed studies, but none "
            "of them directly support or contradict this claim, so our AI agents had nothing "
            "reliable to debate.\n\n"
            "This doesn't mean the claim is true or false, only that we couldn't check it against "
            "research. Try rephrasing it more specifically: say what is taken or done, and what "
            "health effect it has."
        )
        with st.expander(f"Studies we found ({len(evidence)} snippets) - none directly address the claim", expanded=False):
            for item in evidence:
                render_evidence_card(item)
    else:
        st.warning(
            "**No research found for this claim.** We searched PubMed but couldn't find any studies "
            "on it, so there was nothing for our AI agents to debate.\n\n"
            "This doesn't mean the claim is true or false, only that we couldn't check it against "
            "research. Try rephrasing it more specifically: say what is taken or done, and what "
            "health effect it has."
        )


def render_conclusion_card(conclusion: dict | None):
    """Plain-language conclusion of the debate (built only from the debate and verdict)."""
    if not conclusion:
        return
    caveat = conclusion.get("caveat")
    caveat_html = (
        f'<div class="conclusion-caveat"><strong>Keep in mind:</strong> {html.escape(caveat)}</div>'
        if caveat else ""
    )
    card_html = (
        f'<div class="conclusion-card">'
        f'<div class="conclusion-label">{SVG_ICONS["scale"]} Debate Conclusion \u2022 In Plain Language</div>'
        f'<div class="conclusion-answer">{html.escape(conclusion.get("answer", ""))}</div>'
        f'<div class="conclusion-summary">{html.escape(conclusion.get("summary", ""))}</div>'
        f'{caveat_html}'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


# ---------- Dashboard helpers (mockup-style layout) ----------

DESIGN_LABELS = {
    "systematic_review": "Systematic review",
    "meta_analysis": "Meta-analysis",
    "RCT": "Randomised trial",
    "clinical_trial": "Clinical trial",
    "cohort_study": "Cohort study",
    "pilot_trial": "Pilot trial",
    "observational": "Observational study",
    "narrative_review": "Narrative review",
    "case_report": "Case report",
}
# Strongest -> weakest, mirrors the judge's quality tiers
DESIGN_ORDER = ["systematic_review", "meta_analysis", "RCT", "clinical_trial", "cohort_study",
                "pilot_trial", "observational", "narrative_review", "case_report", None]
DESIGN_COLORS = {
    "systematic_review": "#2b2580", "meta_analysis": "#2b2580", "RCT": "#2f3f9e",
    "clinical_trial": "#4f5fbf", "cohort_study": "#6b7bd6", "pilot_trial": "#8f9be0",
    "observational": "#8f9be0", "narrative_review": "#b8b3d6", "case_report": "#b8b3d6", None: "#c9c5dc",
}
SOURCE_BADGE_COLORS = ["#2f3f9e", "#5b3a9e", "#b3263a", "#1f7a6d", "#8a5a12", "#3f6fb5"]
CREDIBILITY_DOTS = {"high": 4, "medium": 3, "low": 2}
MIDDOT = " \u00b7 "
ARROW = "\u2197"
DOT = "\u25cf"
CITE_TAIL = re.compile(r"\[\s*(E-\d+-\d+(?:\s*,\s*E-\d+-\d+)*)\s*\]\s*$")


NO_DESIGN_HTML = '<div class="dc-note">No study design information.</div>'
NO_SOURCES_HTML = '<div class="dc-note">No sources cited yet.</div>'


def design_label(design) -> str:
    return DESIGN_LABELS.get(design, "Design not stated")


def paper_key(item: dict | None, cid: str) -> str:
    """Group snippets by paper (PMID), so one paper = one numbered source."""
    match = re.match(r"^E-(\d+)", cid or "")
    return match.group(1) if match else (item or {}).get("source_url") or cid


def build_source_index(turns: list[dict], evidence_by_id: dict) -> dict:
    """Number cited papers S1, S2, ... in the order they are first cited."""
    index = {}
    for turn in turns:
        for cid in turn.get("cited_ids", []):
            key = paper_key(evidence_by_id.get(cid), cid)
            if key not in index:
                index[key] = {"n": len(index) + 1, "item": evidence_by_id.get(cid), "cid": cid}
    return index


def parse_points(argument: str) -> list[tuple[str, list[str]]]:
    """Split an agent argument ('- text [E-.., E-..]' per line) into (text, cited_ids) points."""
    points = []
    for line in (argument or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*\u2022]\s*", "", line)
        match = CITE_TAIL.search(line)
        ids = [i.strip() for i in match.group(1).split(",")] if match else []
        text = CITE_TAIL.sub("", line).strip()
        points.append((text, ids))
    return points


def source_tag_html(cid: str, evidence_by_id: dict, source_index: dict, side: str) -> str:
    item = evidence_by_id.get(cid) or {}
    src = source_index.get(paper_key(item, cid), {})
    parts = [f"S{src['n']}" if src else "Source", design_label(item.get("study_design"))]
    if item.get("sample_size"):
        parts.append(f"n={item['sample_size']}")
    elif item.get("pub_date"):
        parts.append(str(item["pub_date"]))
    url = get_citation_url(cid, evidence_by_id)
    label = html.escape(MIDDOT.join(parts))
    return (f'<a class="dc-tag {side}" href="{url}" target="_blank" rel="noopener noreferrer">'
            f'{label} {ARROW}</a>')


def ring_svg(percent: int) -> str:
    circumference = 2 * 3.1416 * 42
    filled = circumference * percent / 100
    return (
        f'<svg width="118" height="118" viewBox="0 0 110 110">'
        f'<circle cx="55" cy="55" r="42" fill="none" stroke="#f1e7cc" stroke-width="10"/>'
        f'<circle cx="55" cy="55" r="42" fill="none" stroke="#c99a2e" stroke-width="10" stroke-linecap="round" '
        f'stroke-dasharray="{filled:.1f} {circumference:.1f}" transform="rotate(-90 55 55)"/>'
        f'<text x="55" y="57" text-anchor="middle" font-size="22" font-weight="700" fill="#1f1b5e">{percent}%</text>'
        f'<text x="55" y="74" text-anchor="middle" font-size="9" fill="#6b6782">agreement</text>'
        f'</svg>'
    )


def render_verdict_row(verdict: dict, conclusion: dict | None, evidence: list[dict], n_sources: int):
    """Three summary cards: judge's verdict, misinformation risk, evidence by quality."""
    percent = confidence_percent(verdict.get("confidence"))
    agreement = "High" if percent >= 75 else "Moderate" if percent >= 50 else "Low"
    label = verdict.get("verdict", "Unknown")
    summary = (conclusion or {}).get("answer") or verdict.get("final_answer", "")

    verdict_card = (
        f'<div class="dc-card dc-verdict">'
        f'<div class="dc-card-title">Judge\u2019s verdict</div>'
        f'<div class="dc-verdict-row">'
        f'<div><div class="dc-serif dc-verdict-label">{html.escape(label)}</div></div>'
        f'<div class="dc-ring">{ring_svg(percent)}<div class="dc-ring-caption">{agreement} agreement</div></div>'
        f'</div>'
        f'<div class="dc-verdict-text">{html.escape(summary)}</div>'
        f'<span class="dc-pill">Based on {n_sources} cited source{"s" if n_sources != 1 else ""}</span>'
        f'</div>'
    )

    risk = (verdict.get("misinformation_risk") or "Medium").title()
    risk_color = {"Low": "#16a34a", "Medium": "#c99a2e", "High": "#b3263a"}.get(risk, "#c99a2e")
    segs, names = "", ""
    for level, color in (("Low", "#16a34a"), ("Medium", "#c99a2e"), ("High", "#b3263a")):
        active = level == risk
        segs += f'<div class="dc-risk-seg{" active" if active else ""}" style="{f"background:{color};" if active else ""}"></div>'
        names += f'<div class="{"active" if active else ""}">{level}</div>'
    risk_card = (
        f'<div class="dc-card">'
        f'<div class="dc-card-title">Misinformation risk</div>'
        f'<div class="dc-serif dc-risk-label" style="color:{risk_color};">{risk}</div>'
        f'<div class="dc-risk-scale">{segs}</div><div class="dc-risk-names">{names}</div>'
        f'<div class="dc-risk-reason">{html.escape(verdict.get("risk_reason") or "")}</div>'
        f'</div>'
    )

    counts = {}
    for item in evidence:
        design = item.get("study_design") if item.get("study_design") in DESIGN_LABELS else None
        counts[design] = counts.get(design, 0) + 1
    top = max(counts.values(), default=1)
    rows = ""
    for design in DESIGN_ORDER:
        if design not in counts:
            continue
        n = counts[design]
        rows += (
            f'<div class="dc-q-row"><div class="dc-q-head"><span>{design_label(design)}</span>'
            f'<span>{n} snippet{"s" if n != 1 else ""}</span></div>'
            f'<div class="dc-q-bar"><div class="dc-q-fill" style="width:{100 * n / top:.0f}%;'
            f'background:{DESIGN_COLORS[design]};"></div></div></div>'
        )
    support = sum(1 for e in evidence if e.get("stance") == "support")
    contradict = sum(1 for e in evidence if e.get("stance") == "contradict")
    total = max(support + contradict, 1)
    split = (
        f'<div class="dc-split"><div class="dc-card-title" style="margin:0;">Evidence split (excluding neutral)</div>'
        f'<div class="dc-split-bar"><div style="width:{100 * support / total:.0f}%;background:#2f3f9e;"></div>'
        f'<div style="width:{100 * contradict / total:.0f}%;background:#b3263a;"></div></div>'
        f'<div class="dc-split-legend"><span style="color:#2f3f9e;">Supports {support}</span>'
        f'<span style="color:#b3263a;">Contradicts {contradict}</span></div></div>'
    )
    quality_card = (
        f'<div class="dc-card">'
        f'<div class="dc-card-title">Evidence by study quality</div>'
        f'{rows or NO_DESIGN_HTML}'
        f'{split}'
        f'<div class="dc-note">Strongest study types first. Counts of retrieved snippets; the judge weighs quality, not counts.</div>'
        f'</div>'
    )
    st.markdown(f'<div class="dc-grid">{verdict_card}{risk_card}{quality_card}</div>', unsafe_allow_html=True)


def agent_card_html(side: str, turns: list[dict], evidence_by_id: dict, source_index: dict) -> str:
    is_pro = side == "pro"
    icon = SVG_ICONS["shield_check"] if is_pro else SVG_ICONS["shield_cross"]
    name = "PRO agent" if is_pro else "CON agent"
    body = ""
    number = 0
    for turn in turns:
        round_name = "Opening" if int(turn.get("round", 1)) == 1 else "Rebuttal"
        body += f'<div class="dc-round">Round {turn.get("round", 1)} \u00b7 {round_name}</div>'
        for text, ids in parse_points(turn.get("argument", "")):
            number += 1
            first_per_paper = {}
            for cid in ids:
                first_per_paper.setdefault(paper_key(evidence_by_id.get(cid), cid), cid)
            tags = "".join(source_tag_html(cid, evidence_by_id, source_index, side)
                           for cid in first_per_paper.values())
            tags_html = f'<div class="dc-tags">{tags}</div>' if tags else ""
            body += (
                f'<div class="dc-point"><div class="dc-num {side}">{number}</div><div>'
                f'<div class="dc-point-text">{html.escape(humanize_text(text))}</div>'
                f'{tags_html}</div></div>'
            )
    if not turns:
        body = '<div class="dc-note">Waiting for this agent\u2026</div>'
    return (
        f'<div class="dc-card">'
        f'<div class="dc-agent-head"><span class="dc-agent-chip {side}">{icon} {name}</span>'
        f'<span class="dc-agent-sub">cited evidence only</span></div>'
        f'{body}</div>'
    )


def sources_card_html(source_index: dict, evidence_count: int) -> str:
    rows = ""
    for key, src in source_index.items():
        item = src["item"] or {}
        dots = CREDIBILITY_DOTS.get((item.get("source_credibility") or "").lower(), 1)
        url = get_citation_url(src["cid"], {src["cid"]: item} if item else {})
        color = SOURCE_BADGE_COLORS[(src["n"] - 1) % len(SOURCE_BADGE_COLORS)]
        rows += (
            f'<a class="dc-src" href="{url}" target="_blank" rel="noopener noreferrer">'
            f'<div class="dc-src-badge" style="background:{color};">S{src["n"]}</div>'
            f'<div class="dc-src-main"><div class="dc-src-title">{design_label(item.get("study_design"))}</div>'
            f'<div class="dc-src-meta">PubMed \u00b7 {html.escape(str(item.get("pub_date") or "year unknown"))}</div></div>'
            f'<div class="dc-dots"><span style="color:#c99a2e;">{DOT * dots}</span>'
            f'<span style="color:#ddd6c3;">{DOT * (4 - dots)}</span></div>'
            f'</a>'
        )
    return (
        f'<div class="dc-card">'
        f'<div class="dc-agent-head"><span class="dc-src-title" style="font-size:1rem;">Traceable sources</span></div>'
        f'{rows or NO_SOURCES_HTML}'
        f'<div class="dc-note">Papers cited in the debate. Dots show source credibility (study design). {evidence_count} snippets retrieved '
        f'in total \u2014 see \u201cRetrieved PubMed Literature\u201d below.</div>'
        f'</div>'
    )


def debate_grid_html(turns: list[dict], evidence_by_id: dict, evidence_count: int) -> str:
    source_index = build_source_index(turns, evidence_by_id)
    pro = [t for t in turns if str(t.get("agent", "")).upper() == "PRO"]
    con = [t for t in turns if str(t.get("agent", "")).upper() == "CON"]
    return (
        f'<div class="dc-grid">'
        f'{agent_card_html("pro", pro, evidence_by_id, source_index)}'
        f'{agent_card_html("con", con, evidence_by_id, source_index)}'
        f'{sources_card_html(source_index, evidence_count)}'
        f'</div>'
    )


def counter_evidence_html(verdict: dict, evidence_by_id: dict) -> str:
    text = verdict.get("top_counter_evidence")
    if not text:
        return ""
    body = clean_argument_html(text, evidence_by_id)   # turns citation IDs into Source links
    return (
        f'<div class="dc-counter" style="margin:0;"><span class="dc-counter-label">Strongest evidence against this verdict</span>'
        f'<div style="font-size:0.8rem;color:#6b6782;margin-bottom:6px;">The opposing side\u2019s best point, '
        f'shown so you can judge whether the verdict could be wrong.</div>'
        f'<div style="font-size:1rem;line-height:1.55;">{body}</div></div>'
    )


def chat_debate_html(turns: list[dict], evidence_by_id: dict) -> str:
    bubbles = "".join(render_turn_bubble_html(t, evidence_by_id) for t in turns)
    return f'<div class="chat-conversation-container">{bubbles}</div>'


def render_result(data: dict, live: bool = True):
    """Debate conversation -> verdict/risk/quality cards -> conclusion ->
    sources + strongest counter-evidence -> detailed dossier.
    The quick answer is shown only when there was nothing to debate."""
    inject_chat_styles()

    verdict = data.get("verdict", {})
    evidence = data.get("evidence", [])
    transcript = data.get("transcript", [])
    evidence_by_id = {item.get("id"): item for item in evidence if item.get("id")}
    ordered_transcript = sort_transcript_turns(transcript)

    # No debate possible -> quick answer + plain-language notice only
    if not transcript:
        render_background_card(data.get("background"), debate_available=False)
        render_no_debate_notice(evidence)
        return

    # 1. Debate as a chat conversation (revealed turn by turn on a new result)
    st.markdown(
        f'<div class="arena-header"><div class="arena-title">{SVG_ICONS["chat_bubble"]} Live Evidence Debate</div>'
        f'<div class="arena-badge">2 Rounds \u2022 AI Agents Grounded in PubMed</div></div>',
        unsafe_allow_html=True,
    )
    chat = st.empty()
    if live:
        for i in range(1, len(ordered_transcript) + 1):
            chat.markdown(chat_debate_html(ordered_transcript[:i], evidence_by_id), unsafe_allow_html=True)
            time_module.sleep(0.85)
    else:
        chat.markdown(chat_debate_html(ordered_transcript, evidence_by_id), unsafe_allow_html=True)

    # 2. Traceable sources + strongest counter-evidence (right after the debate)
    source_index = build_source_index(ordered_transcript, evidence_by_id)
    st.markdown(
        f'<div class="dc-grid">{sources_card_html(source_index, len(evidence))}'
        f'{counter_evidence_html(verdict, evidence_by_id)}</div>',
        unsafe_allow_html=True,
    )

    # 3. Summary cards
    render_verdict_row(verdict, data.get("conclusion"), evidence, len(source_index))

    # 4. Plain-language conclusion
    render_conclusion_card(data.get("conclusion"))

    # 5. Detailed dossier (collapsed)
    confidence = confidence_percent(verdict.get("confidence"))
    st.markdown(f"### {SVG_ICONS['file_text']} Detailed Clinical Dossier", unsafe_allow_html=True)

    with st.expander("Judge Reasoning & Study Limitations", expanded=False):
        st.markdown(replace_citation_ids_markdown(verdict.get("reasoning") or "No reasoning returned.", evidence_by_id))
        st.caption(
            f"Agreement ({confidence}%) is how many independent judge runs chose this verdict; "
            "it is not a probability that the medical claim is true."
        )
        gap = verdict.get("evidence_gap_note")
        if gap:
            st.warning(f"Uncertainty / evidence limitations: {gap}")
        else:
            st.info(
                "Uncertainty / evidence limitations: This result is based on the PubMed "
                "evidence retrieved for this query and may not represent all available "
                "medical research."
            )

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


# ---------- API key setup ----------

def fetch_config_status() -> dict | None:
    try:
        response = requests.get(STATUS_URL, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None


def render_key_form(status: dict, form_key: str, only_missing: bool):
    """Form to enter API keys. Keys are validated and applied by the backend."""
    keys = status.get("keys", {})
    inputs = {}
    with st.form(form_key):
        for name, (label, help_text, url, secret) in KEY_HELP.items():
            if only_missing and keys.get(name):
                continue
            state = "set" if keys.get(name) else "missing"
            inputs[name] = st.text_input(
                f"{label} - currently {state}",
                type="password" if secret else "default",
                key=f"{form_key}_{name}",
                placeholder="Leave blank to keep the current value" if keys.get(name) else "",
            )
            st.caption(f"{help_text} [Get it here]({url})" if url else help_text)
        save = st.checkbox(
            "Remember these keys on this computer (saves them to the .env file)",
            value=True, key=f"{form_key}_save",
        )
        submitted = st.form_submit_button("Save keys", type="primary")

    if not submitted:
        return

    payload = {KEY_PAYLOAD_FIELD[n]: v.strip() for n, v in inputs.items() if v and v.strip()}
    if not payload:
        st.warning("Please enter at least one value.")
        return
    payload["save_to_env"] = save

    with st.spinner("Checking your keys..."):
        try:
            response = requests.post(KEYS_URL, json=payload, timeout=60)
        except requests.exceptions.RequestException:
            st.error("Could not reach the backend to save the keys.")
            return

    if response.ok:
        st.session_state["sidebar_state"] = "collapsed"   # keys verified -> tuck the sidebar away
        st.success("Keys saved and working.")
        time_module.sleep(0.8)
        st.rerun()

    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = response.text
    if isinstance(detail, dict):
        for name, message in detail.items():
            st.error(f"**{KEY_HELP.get(name, (name,))[0]}:** {message}")
    else:
        st.error(str(detail))


# ---------- Streaming verification with live progress ----------

def run_verification_stream(claim_text: str) -> dict | None:
    """Calls /verify/stream and shows each real pipeline step as it happens."""
    progress_bar = st.progress(0.0, text="Starting...")
    start = time_module.time()
    message, fraction, result = "Starting...", 0.0, None

    with st.status("Verifying your claim - this usually takes 1-3 minutes...", expanded=False) as status_box:
        try:
            with requests.post(
                STREAM_URL, json={"claim": claim_text}, stream=True, timeout=(10, 120),
            ) as response:
                if not response.ok:
                    status_box.update(label="Something went wrong", state="error")
                    st.error(f"Backend returned {response.status_code}: {response.text[:300]}")
                    return None

                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    event = json.loads(line)
                    elapsed = int(time_module.time() - start)

                    if event["type"] == "progress":
                        message, fraction = event["message"], event["progress"]
                        if message != "Done!":
                            st.write(f"\u2022 {message}")
                    elif event["type"] == "result":
                        result = event["data"]
                    elif event["type"] == "error":
                        status_box.update(label="Something went wrong", state="error")
                        st.error(event["detail"])
                        if "API key" in event["detail"]:
                            st.info("Open **API keys** in the sidebar to add or fix your keys.")
                        progress_bar.empty()
                        return None

                    progress_bar.progress(min(fraction, 1.0), text=f"{message}  \u00b7  {elapsed}s elapsed")

        except requests.exceptions.ConnectionError:
            status_box.update(label="Lost connection to the backend", state="error")
            st.error("Could not connect to the backend. Is it still running?")
            return None
        except requests.exceptions.ReadTimeout:
            status_box.update(label="The backend stopped responding", state="error")
            st.error("The backend stopped responding. Check its terminal for errors.")
            return None

        if result is None:
            status_box.update(label="No result received", state="error")
            return None

        status_box.update(label=f"Done in {int(time_module.time() - start)}s", state="complete", expanded=False)

    progress_bar.empty()
    return result


# ---------- Page Layout & State Management ----------

# Header bar
st.markdown(
    f'<div class="dc-header"><div class="dc-header-logo">{SVG_ICONS["scale"]}</div>'
    f'<div><div class="dc-header-title">DebateCheck</div>'
    f'<div class="dc-header-tagline">AI agents debate health claims using real PubMed evidence</div></div></div>',
    unsafe_allow_html=True,
)

st.info(
    "DebateCheck is an educational evidence-verification tool, not medical advice. "
    "Its output depends on retrieved literature and AI interpretation. For personal "
    "medical decisions, consult a qualified health professional."
)

config = fetch_config_status()
if config is None:
    st.error(
        "**Can't reach the DebateCheck backend.** Start it in a second terminal "
        "(with the virtual environment activated), then refresh this page:"
    )
    st.code("cd backend\nuvicorn app.api.main:app --reload --port 8002", language="bash")
    st.stop()

with st.sidebar:
    st.markdown("### \u2699\ufe0f API keys")
    if config.get("use_fixture"):
        st.caption("Demo mode is on - no keys are needed.")
    for key_name, (key_label, *_rest) in KEY_HELP.items():
        st.write(("\u2705 " if config["keys"].get(key_name) else "\u274c ") + key_label)
    if config.get("ready"):   # during first-time setup the form is on the main page instead
        with st.expander("Add or update keys"):
            render_key_form(config, "sidebar_keys_form", only_missing=False)

if not config.get("ready"):
    st.warning(
        "### \U0001F511 One-time setup needed\n"
        "DebateCheck needs a few **free** API keys to search PubMed and run its AI agents. "
        "Enter the missing ones below - it takes about two minutes, and you only need to do it once."
    )
    render_key_form(config, "setup_keys_form", only_missing=True)
    st.stop()

with st.container(key="claim_box"):
    with st.form("claim_form"):
        claim = st.text_area(
            "Enter a health claim to verify:",
            placeholder="e.g. Intermittent fasting increases longevity",
            height=90,
        )
        submitted = st.form_submit_button(
            "Check claim",
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
        result_data = run_verification_stream(claim.strip())
        if result_data:
            # Persist response in session state
            st.session_state["analysis_data"] = result_data
            st.session_state["run_live_animation"] = True

# Display results if available in session state (preserves view across filter clicks!)
if st.session_state.get("analysis_data"):
    # Only animate live on brand new submissions, not on filter reruns!
    should_animate = st.session_state.pop("run_live_animation", False)
    render_result(st.session_state["analysis_data"], live=should_animate)