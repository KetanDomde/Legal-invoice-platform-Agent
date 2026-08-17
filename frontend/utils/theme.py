"""
Konverge AI brand theme for the Streamlit frontend.

Colors match the palette already used across this project's Word/PowerPoint
deliverables (docHelpers.js): navy, orange, blue, grey, light background.
Keep this file as the single source of truth for brand constants so every
page stays visually consistent.
"""
import streamlit as st

NAVY = "#020067"
ORANGE = "#FF8100"
BLUE = "#0072D2"
GREY = "#807F85"
LIGHT = "#F4F5FA"
WHITE = "#FFFFFF"
GREEN = "#1E9E64"
RED = "#D64545"

STATUS_COLORS = {
    "submitted": GREY,
    "pending_review": BLUE,
    "under_review": BLUE,
    "clarification_requested": "#B98900",
    "approved": GREEN,
    "rejected": RED,
}

ROLE_COLORS = {
    "admin": NAVY,
    "editor": BLUE,
    "viewer": GREY,
}


def inject_base_css():
    st.markdown(
        f"""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <style>
            html, body, [class*="css"] {{
                font-family: 'Inter', sans-serif;
            }}
            h1, h2, h3, .kv-display {{
                font-family: 'Poppins', sans-serif !important;
                color: {NAVY};
                font-weight: 700;
            }}
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}

            .kv-banner {{
                background: linear-gradient(100deg, {NAVY} 0%, #0d0a8f 100%);
                padding: 28px 36px 40px 36px;
                border-radius: 0 0 18px 18px;
                margin: -1rem -1rem 1.6rem -1rem;
                position: relative;
                overflow: hidden;
            }}
            .kv-banner h1 {{
                color: {WHITE} !important;
                font-size: 1.65rem;
                margin: 0;
                letter-spacing: 0.2px;
            }}
            .kv-banner .kv-kicker {{
                color: {ORANGE};
                font-weight: 700;
                letter-spacing: 1.6px;
                font-size: 0.72rem;
                text-transform: uppercase;
                margin-bottom: 4px;
                display: block;
            }}
            .kv-banner .kv-sub {{
                color: #cfd0f4;
                font-size: 0.92rem;
                margin-top: 6px;
            }}
            .kv-wave {{
                position: absolute;
                bottom: -2px; left: 0; width: 100%;
                line-height: 0;
            }}

            .kv-card {{
                background: {WHITE};
                border: 1px solid #ECEDF6;
                border-radius: 14px;
                padding: 20px 22px;
                box-shadow: 0 2px 10px rgba(2,0,103,0.05);
                margin-bottom: 14px;
            }}

            .kv-kpi {{
                background: {WHITE};
                border-left: 5px solid {ORANGE};
                border-radius: 10px;
                padding: 14px 18px;
                box-shadow: 0 2px 8px rgba(2,0,103,0.06);
            }}
            .kv-kpi .kv-kpi-label {{
                color: {GREY};
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.6px;
                font-weight: 600;
            }}
            .kv-kpi .kv-kpi-value {{
                font-family: 'Poppins', sans-serif;
                color: {NAVY};
                font-size: 1.7rem;
                font-weight: 800;
                margin-top: 2px;
            }}

            .kv-pill {{
                display: inline-block;
                padding: 3px 12px;
                border-radius: 999px;
                font-size: 0.74rem;
                font-weight: 600;
                color: white;
                letter-spacing: 0.2px;
            }}

            .kv-sidebar-card {{
                background: {LIGHT};
                border-radius: 12px;
                padding: 14px 16px;
                margin-bottom: 10px;
            }}
            [data-testid="stSidebar"] {{
                background-color: #FBFBFE;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_banner(title: str, kicker: str = "KONVERGE AI · LEGAL INVOICE PLATFORM", subtitle: str | None = None):
    sub_html = f'<div class="kv-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="kv-banner">
            <span class="kv-kicker">{kicker}</span>
            <h1>{title}</h1>
            {sub_html}
            <div class="kv-wave">
                <svg viewBox="0 0 500 40" preserveAspectRatio="none" style="width:100%;height:26px;">
                    <path d="M0 20 Q125 40 250 20 T500 20 V40 H0 Z" fill="{ORANGE}" opacity="0.9"/>
                </svg>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, GREY)
    label = (status or "unknown").replace("_", " ").title()
    return f'<span class="kv-pill" style="background:{color}">{label}</span>'


def role_badge(role: str) -> str:
    color = ROLE_COLORS.get(role, GREY)
    return f'<span class="kv-pill" style="background:{color}">{(role or "").title()}</span>'


def kpi_tile(label: str, value: str):
    st.markdown(
        f"""
        <div class="kv-kpi">
            <div class="kv-kpi-label">{label}</div>
            <div class="kv-kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def money(amount) -> str:
    if amount is None:
        return "—"
    return f"${amount:,.2f}"
