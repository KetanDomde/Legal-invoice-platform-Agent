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
                background: rgba(255,255,255,.1);
                border-radius: 12px;
                padding: 14px 16px;
                margin-bottom: 10px;
                color: #EAF0FF;
            }}
            .kv-sidebar-card small {{ color: rgba(234,240,255,.72) !important; }}

            /* Workbench sidebar — navy gradient, matches the rest of this
               engagement's brand deliverables (docHelpers.js / decks). */
            section[data-testid="stSidebar"] {{
                background: linear-gradient(180deg, {NAVY} 0%, #0a0640 100%);
            }}
            section[data-testid="stSidebar"] * {{ color: #EAF0FF !important; }}
            section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.18) !important; }}
            /* Ten workbench pages overflow Streamlit's default sidebar-nav
               height and collapse behind a "View more" toggle — expand it
               so the full flow is visible at a glance. */
            div[data-testid="stSidebarNav"] {{ max-height: none !important; }}
            div[data-testid="stSidebarNav"] > ul {{ max-height: none !important; }}
            div[data-testid="stSidebarNavSeparator"] {{ display: none !important; }}
            section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] textarea {{
                color: {NAVY} !important;
            }}
            section[data-testid="stSidebar"] .stButton>button {{
                border-color: rgba(255,255,255,.35);
                background: rgba(255,255,255,.08);
            }}

            /* Workbench building blocks (cards/badges/timeline/notices),
               layered on top of the existing kv-* system above. */
            .wb-badge {{
                display:inline-flex; align-items:center; gap:6px; border-radius:999px;
                padding:5px 11px; font-size:12px; font-weight:700; white-space:nowrap;
            }}
            .wb-notice {{
                border-radius:14px; padding:13px 15px; border:1px solid #fed7aa;
                background:#fff7ed; color:#9a3412; font-size:13px; font-weight:600; margin: 8px 0;
            }}
            .wb-notice.success {{ border-color:#bbf7d0; background:#f0fdf4; color:#166534; }}
            .wb-chip {{
                background:{LIGHT}; border:1px solid #dfe4ee; padding:6px 10px; border-radius:999px;
                font-size:12px; font-weight:700; color:#4a5365; display:inline-block; margin:3px 3px 3px 0;
            }}
            .wb-kv {{ font-size: 14px; margin: 3px 0; }}
            .wb-kv .k {{ color: {GREY}; display: inline-block; min-width: 160px; }}
            .wb-kv .v {{ font-weight: 700; }}
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


# ---------------------------------------------------------------------------
# Workbench building blocks — cards/badges/timeline/notices in the same
# visual language as render_banner()/status_badge() above, used across the
# 10-screen intake -> workspace -> review -> admin flow.
# ---------------------------------------------------------------------------

WB_BADGE_STYLES = {
    "green": ("#e8f8f1", "#087443"),
    "blue": ("#e8efff", "#1746bb"),
    "orange": ("#fff3e5", "#b45a00"),
    "red": ("#fdecec", RED),
    "purple": ("#f1e8ff", "#673ab7"),
    "gray": ("#eef0f4", "#4c5568"),
}


def badge(text: str, color: str = "gray") -> str:
    bg, fg = WB_BADGE_STYLES.get(color, WB_BADGE_STYLES["gray"])
    return f'<span class="wb-badge" style="background:{bg};color:{fg}">{text}</span>'


def notice(text: str, success: bool = False) -> None:
    cls = "wb-notice success" if success else "wb-notice"
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def chip(text: str) -> str:
    return f'<span class="wb-chip">{text}</span>'


def chips(items: list) -> None:
    st.markdown("".join(chip(i) for i in items), unsafe_allow_html=True)


def kv_row(label: str, value) -> None:
    st.markdown(f'<div class="wb-kv"><span class="k">{label}</span><span class="v">{value}</span></div>', unsafe_allow_html=True)


def page_header(number: int, title: str, subtitle: str, extra_badge: str | None = None) -> None:
    left, right = st.columns([5, 2])
    with left:
        st.markdown(f"## {number}. {title}")
        st.caption(subtitle)
    with right:
        if extra_badge:
            st.markdown(f'<div style="text-align:right;padding-top:14px">{extra_badge}</div>', unsafe_allow_html=True)


def metric_row(items: list) -> None:
    """items: [(label, value), ...] — thin wrapper around kpi_tile in columns."""
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            kpi_tile(label, value)


def timeline(steps: list) -> None:
    """steps: [(label, state)] where state is "done" | "active" | "pending" | "rejected"."""
    state_colors = {"done": BLUE, "active": BLUE, "pending": "#dfe4ee", "rejected": RED}
    cols = st.columns(len(steps))
    for i, (label, state) in enumerate(steps):
        color = state_colors.get(state, "#dfe4ee")
        text_color = "#fff" if state in ("done", "active", "rejected") else "#6a7280"
        label_color = BLUE if state == "active" else (RED if state == "rejected" else GREY)
        weight = 800 if state in ("active", "rejected") else 500
        with cols[i]:
            st.markdown(
                f"""
                <div style="text-align:center">
                  <div style="width:32px;height:32px;border-radius:50%;background:{color};color:{text_color};
                              display:inline-grid;place-items:center;font-size:12px;font-weight:900;margin:0 auto">{i + 1}</div>
                  <div style="font-size:11px;color:{label_color};margin-top:6px;font-weight:{weight};line-height:1.2">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def artifact_row(label: str, right_html: str) -> None:
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'border:1px solid #ECEDF6;border-radius:12px;padding:10px 12px;margin-bottom:8px;'
        f'background:#fbfcff;font-size:13px"><span>{label}</span><span>{right_html}</span></div>',
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
          <div style="width:42px;height:42px;border-radius:12px;background:#fff;color:#020067;
                      display:grid;place-items:center;font-weight:900">K</div>
          <div>
            <div style="font-weight:800;font-size:16px;line-height:1.15">Legal Invoice Platform</div>
            <div style="opacity:.75;font-size:11px;margin-top:2px">Konverge AI &middot; Agent Workbench</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.divider()
