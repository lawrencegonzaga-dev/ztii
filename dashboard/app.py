"""ZTII industrial intelligence command center.

The dashboard connects to the FastAPI service when it is available and falls
back to a clearly labelled portfolio demo dataset when it is not. This keeps
the interface useful for hosted demos without pretending simulated telemetry
is live plant data.
"""

from __future__ import annotations

import html
import math
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import altair as alt
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh


st.set_page_config(
    page_title="ZTII | Industrial Intelligence",
    page_icon="ZT",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = ["Command Center", "Fleet Intelligence", "Alerts", "Provisioning", "Edge & PLC"]
REFRESH_INTERVALS = [5, 10, 15, 30, 60]
TEMP_WARNING = 55.0
TEMP_CRITICAL = 65.0
VIB_WARNING = 1.0
VIB_CRITICAL = 1.5


def configured_api_url() -> str:
    """Read the API endpoint from trusted server-side configuration only."""
    try:
        secret_url = st.secrets.get("ZTII_API_URL")
    except Exception:
        secret_url = None
    return str(secret_url or os.getenv("ZTII_API_URL", "http://127.0.0.1:8000")).rstrip("/")


API_URL = configured_api_url()


st.markdown(
    """
    <style>
    :root {
        --ink: #132019;
        --muted: #68736c;
        --line: #dce3de;
        --panel: #ffffff;
        --canvas: #f4f7f4;
        --brand: #176346;
        --brand-deep: #10271f;
        --brand-soft: #deeee6;
        --warning: #ae6517;
        --warning-soft: #fff2dc;
        --critical: #a94336;
        --critical-soft: #fbe8e5;
        --info: #34658b;
    }

    html, body, [class*="css"] {
        font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    h1, h2, h3, h4 {
        font-family: "Arial Narrow", Inter, ui-sans-serif, sans-serif !important;
        letter-spacing: -0.025em;
    }
    [data-testid="stAppViewContainer"] { background: var(--canvas); color: var(--ink); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stMainBlockContainer"] { max-width: 1450px; padding: 2rem 2.35rem 4rem; }
    [data-testid="stSidebar"] { background: var(--brand-deep); border-right: 0; }
    [data-testid="stSidebar"] > div { padding-top: 1.2rem; }
    [data-testid="stSidebar"] * { color: #eaf3ee; }
    [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.12); }
    [data-testid="stSidebar"] [role="radiogroup"] { gap: .28rem; }
    [data-testid="stSidebar"] [role="radiogroup"] label {
        border: 1px solid transparent;
        border-radius: 10px;
        padding: .62rem .72rem;
        transition: background .15s ease, border-color .15s ease;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: rgba(255,255,255,.07);
        border-color: rgba(255,255,255,.08);
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
        background: #d9eee4;
        border-color: #d9eee4;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { color: #123d2d; font-weight: 700; }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color: #a7bdb2; }
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,.07);
        color: white;
        border: 1px solid rgba(255,255,255,.12);
    }

    div[data-testid="stMetric"] {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 1.02rem 1.12rem;
        box-shadow: 0 7px 24px rgba(20, 45, 33, .04);
    }
    div[data-testid="stMetric"] label { color: var(--muted); font-size: .8rem; }
    div[data-testid="stMetricValue"] { color: var(--ink); font-weight: 700; }
    div[data-testid="stMetricDelta"] { font-size: .72rem; }

    .zt-brand { padding: .4rem .15rem 1.15rem; }
    .zt-mark {
        display: inline-grid; place-items: center; width: 38px; height: 38px;
        border-radius: 11px; background: #d5f2e5; color: #104b36;
        font-weight: 800; margin-right: .65rem;
    }
    .zt-brand-name { color: white; font-weight: 800; font-size: 1.08rem; letter-spacing: -.02em; }
    .zt-brand-copy { display: block; margin: .62rem 0 0; color: #91aa9d; font-size: .74rem; line-height: 1.5; }
    .zt-source {
        display: flex; align-items: center; gap: .55rem; padding: .65rem .72rem;
        background: rgba(255,255,255,.055); border: 1px solid rgba(255,255,255,.09);
        border-radius: 10px; margin: .4rem 0 1rem;
    }
    .zt-source-dot { width: 8px; height: 8px; border-radius: 50%; background: #67d4a5; box-shadow: 0 0 0 4px rgba(103,212,165,.12); }
    .zt-source-dot.demo { background: #e7b35a; box-shadow: 0 0 0 4px rgba(231,179,90,.12); }
    .zt-source strong { display:block; color:white; font-size:.76rem; }
    .zt-source span { display:block; color:#94aea1; font-size:.66rem; }
    .zt-side-caption { color: #89a095; font-size: .67rem; line-height: 1.45; }

    .zt-eyebrow { color: var(--brand); font-size: .7rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
    .zt-title { margin: .28rem 0 .35rem; color: var(--ink); font-size: clamp(2rem, 3vw, 2.8rem); line-height: 1.04; }
    .zt-lede { color: var(--muted); max-width: 720px; margin: 0; font-size: .94rem; line-height: 1.62; }
    .zt-live-card {
        background: var(--brand-deep); border-radius: 14px; padding: 1rem 1.1rem;
        color: white; min-height: 96px; border: 1px solid #234437;
    }
    .zt-live-row { display:flex; align-items:center; justify-content:space-between; gap:1rem; }
    .zt-live-dot { width:8px; height:8px; background:#65d6a5; border-radius:50%; display:inline-block; box-shadow:0 0 0 5px rgba(101,214,165,.12); margin-right:.48rem; }
    .zt-live-dot.demo { background:#e7b35a; box-shadow:0 0 0 5px rgba(231,179,90,.12); }
    .zt-live-label { color:#bdd2c7; font-size:.68rem; text-transform:uppercase; letter-spacing:.1em; }
    .zt-live-value { font-size:1.2rem; font-weight:750; margin-top:.5rem; }
    .zt-live-meta { font-size:.74rem; color:#a7c0b3; }

    .zt-banner {
        border-radius: 13px; padding: .9rem 1.05rem; margin: 1.35rem 0 1rem;
        display:flex; align-items:center; justify-content:space-between; gap:1rem; border:1px solid;
    }
    .zt-banner strong { font-size:.86rem; }
    .zt-banner span { font-size:.78rem; }
    .zt-banner.normal { background:#e8f3ed; border-color:#cbe2d6; color:#184a37; }
    .zt-banner.warning { background:var(--warning-soft); border-color:#f0d6aa; color:#77430d; }
    .zt-banner.critical { background:var(--critical-soft); border-color:#edc4be; color:#7f3027; }
    .zt-banner.demo { background:#edf1f4; border-color:#d4dde3; color:#3b5568; }

    .zt-section-head { margin: 1.75rem 0 .85rem; display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; }
    .zt-section-head h2 { margin: 0 0 .22rem; font-size: 1.2rem; color:var(--ink); }
    .zt-section-head p { margin:0; color:var(--muted); font-size:.81rem; }
    .zt-kicker { color:var(--brand); font-size:.68rem; font-weight:800; text-transform:uppercase; letter-spacing:.1em; }
    .zt-panel { background:white; border:1px solid var(--line); border-radius:15px; padding:1.1rem 1.15rem; box-shadow:0 7px 24px rgba(20,45,33,.035); }
    .zt-panel-title { font-weight:750; font-size:.9rem; color:var(--ink); margin-bottom:.15rem; }
    .zt-panel-copy { color:var(--muted); font-size:.75rem; margin-bottom:.8rem; }
    .zt-attention {
        display:flex; align-items:center; justify-content:space-between; gap:1rem;
        padding:.78rem .05rem; border-bottom:1px solid #edf1ee;
    }
    .zt-attention:last-child { border-bottom:0; }
    .zt-device-id { font-weight:750; font-size:.82rem; color:var(--ink); }
    .zt-device-meta { color:var(--muted); font-size:.7rem; margin-top:.14rem; }
    .zt-pill { display:inline-block; border-radius:999px; padding:.22rem .58rem; font-size:.64rem; font-weight:800; letter-spacing:.035em; text-transform:uppercase; }
    .zt-pill.normal, .zt-pill.resolved { background:#e3f1e9; color:#1c6247; }
    .zt-pill.warning, .zt-pill.acknowledged { background:#fff0d7; color:#8b520f; }
    .zt-pill.critical, .zt-pill.active { background:#f8e3df; color:#94372c; }
    .zt-pill.unknown { background:#e8ece9; color:#5d6962; }
    .zt-pill.recovery { background:#e3edf5; color:#315f81; }

    .zt-detail-head {
        background:linear-gradient(112deg,#10271f,#19533d); color:white; border-radius:16px;
        padding:1.25rem 1.35rem; display:flex; align-items:center; justify-content:space-between; gap:1rem; margin:1rem 0;
    }
    .zt-detail-head h2 { color:white; font-size:1.35rem; margin:0 0 .2rem; }
    .zt-detail-head p { color:#aec7ba; font-size:.76rem; margin:0; }
    .zt-recommendation { border-left:4px solid var(--brand); background:#edf5f1; border-radius:0 12px 12px 0; padding:.9rem 1rem; color:#29473a; font-size:.82rem; line-height:1.55; }
    .zt-factor { display:flex; align-items:center; gap:.7rem; margin:.75rem 0; }
    .zt-factor-label { width:88px; color:var(--muted); font-size:.72rem; }
    .zt-factor-track { height:8px; background:#e6ebe8; border-radius:999px; flex:1; overflow:hidden; }
    .zt-factor-fill { height:100%; background:linear-gradient(90deg,#1d6b4d,#65b58f); border-radius:999px; }
    .zt-factor-value { width:42px; text-align:right; font-weight:700; font-size:.7rem; }

    .zt-alert-card { background:white; border:1px solid var(--line); border-radius:13px; padding:.92rem 1rem; min-height:88px; }
    .zt-alert-top { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:.45rem; }
    .zt-alert-message { color:#34453c; font-size:.8rem; line-height:1.45; }
    .zt-alert-meta { color:var(--muted); font-size:.67rem; margin-top:.45rem; }
    .zt-stepper { display:grid; grid-template-columns:repeat(4,1fr); gap:.5rem; margin:.8rem 0 1rem; }
    .zt-step { background:#edf3ef; color:#315142; border-radius:10px; padding:.7rem .65rem; font-size:.7rem; font-weight:700; text-align:center; }
    .zt-provision-result { background:#e6f2eb; border:1px solid #c9e2d4; border-radius:14px; padding:1.05rem 1.15rem; color:#1d4f3b; }
    .zt-provision-result strong { font-size:.95rem; }
    .zt-provision-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:.55rem 1.2rem; margin-top:.8rem; font-size:.75rem; }
    .zt-register { display:flex; justify-content:space-between; gap:1rem; padding:.72rem 0; border-bottom:1px solid #edf1ee; font-size:.77rem; }
    .zt-register:last-child { border-bottom:0; }
    .zt-register code { color:var(--brand); font-weight:800; }
    .zt-footer { margin-top:2.7rem; padding-top:1rem; border-top:1px solid var(--line); display:flex; justify-content:space-between; gap:1rem; color:#7a867f; font-size:.68rem; }

    .stButton > button, .stDownloadButton > button { border-radius:10px; font-weight:700; min-height:39px; }
    .stButton > button[kind="primary"] { background:var(--brand); border-color:var(--brand); }
    [data-testid="stDataFrame"] { background:white; border:1px solid var(--line); border-radius:14px; overflow:hidden; }
    [data-testid="stExpander"] { background:white; border:1px solid var(--line); border-radius:12px; }
    [data-baseweb="select"] > div, [data-baseweb="input"] > div, .stTextInput input { border-radius:10px; }
    hr { border-color: var(--line); }

    @media (max-width: 800px) {
        [data-testid="stMainBlockContainer"] { padding:1.2rem 1rem 3rem; }
        .zt-title { font-size:2rem; }
        .zt-live-card { margin-top:.4rem; }
        .zt-section-head, .zt-banner, .zt-detail-head, .zt-footer { align-items:flex-start; flex-direction:column; }
        .zt-stepper { grid-template-columns:1fr 1fr; }
        .zt-provision-grid { grid-template-columns:1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def repair_text(value: Any) -> str:
    """Repair common UTF-8-as-Latin-1 mojibake stored by early prototypes."""
    text = "" if value is None else str(value)
    try:
        repaired = text.encode("latin-1").decode("utf-8")
        if repaired:
            text = repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text.replace("Â°C", "°C").replace("â", "—").replace("â€“", "–")


def health_key(value: Any) -> str:
    value = repair_text(value).lower()
    if "critical" in value:
        return "critical"
    if "warning" in value:
        return "warning"
    if "normal" in value or "healthy" in value:
        return "normal"
    return "unknown"


def status_key(value: Any) -> str:
    value = repair_text(value).strip().lower()
    return value if value in {"active", "acknowledged", "resolved"} else "unknown"


def numeric_risk(value: Any) -> int:
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return min(100, max(0, round(float(match.group())))) if match else 0


def safe_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def fmt_number(value: Any, digits: int = 1, suffix: str = "") -> str:
    number = safe_number(value)
    return f"{number:.{digits}f}{suffix}" if number is not None else "Awaiting data"


def api_request(method: str, path: str, **kwargs: Any) -> Tuple[Optional[Any], Optional[str]]:
    try:
        response = requests.request(method, f"{API_URL}{path}", timeout=kwargs.pop("timeout", 6), **kwargs)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as exc:
        detail = str(exc)
        if getattr(exc, "response", None) is not None:
            try:
                detail = exc.response.json().get("detail", detail)
            except Exception:
                pass
        return None, detail


def demo_devices() -> Dict[str, Dict[str, Any]]:
    now = datetime.now()
    return {
        "MTR-L01-001": {"temperature": 42.8, "vibration": 0.38, "status": "Online", "health": "Normal", "risk": "12% (Low)", "recommendation": "Continue standard monitoring.", "registered_at": (now - timedelta(days=74)).strftime("%Y-%m-%d %H:%M:%S")},
        "PMP-L02-014": {"temperature": 57.4, "vibration": 1.08, "status": "Online", "health": "Warning", "risk": "54% (Medium)", "recommendation": "Inspect pump alignment during the next maintenance window.", "registered_at": (now - timedelta(days=51)).strftime("%Y-%m-%d %H:%M:%S")},
        "CMP-L01-007": {"temperature": 67.2, "vibration": 1.64, "status": "Online", "health": "Critical", "risk": "88% (High)", "recommendation": "Reduce load and inspect bearings immediately.", "registered_at": (now - timedelta(days=43)).strftime("%Y-%m-%d %H:%M:%S")},
        "FAN-L03-021": {"temperature": 46.1, "vibration": 0.44, "status": "Online", "health": "Normal", "risk": "18% (Low)", "recommendation": "No immediate action required.", "registered_at": (now - timedelta(days=36)).strftime("%Y-%m-%d %H:%M:%S")},
        "CNV-L02-003": {"temperature": 53.8, "vibration": 0.91, "status": "Online", "health": "Normal", "risk": "34% (Low)", "recommendation": "Watch vibration drift over the next operating cycle.", "registered_at": (now - timedelta(days=28)).strftime("%Y-%m-%d %H:%M:%S")},
    }


def demo_alerts() -> List[Dict[str, Any]]:
    if "demo_alerts" not in st.session_state:
        now = datetime.now()
        st.session_state.demo_alerts = [
            {"id": 9003, "device_id": "CMP-L01-007", "level": "Critical", "message": "Bearing vibration and temperature crossed the critical operating envelope.", "status": "ACTIVE", "created_at": (now - timedelta(minutes=4)).strftime("%Y-%m-%d %H:%M:%S")},
            {"id": 9002, "device_id": "PMP-L02-014", "level": "Warning", "message": "Vibration trend is 18% above the seven-day baseline.", "status": "ACKNOWLEDGED", "created_at": (now - timedelta(minutes=27)).strftime("%Y-%m-%d %H:%M:%S")},
            {"id": 9001, "device_id": "CNV-L02-003", "level": "Recovery", "message": "Asset returned to its normal operating envelope.", "status": "RESOLVED", "created_at": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")},
        ]
    return st.session_state.demo_alerts


def demo_history(device_id: str, device: Dict[str, Any]) -> List[Dict[str, Any]]:
    base_temp = safe_number(device.get("temperature")) or 44.0
    base_vib = safe_number(device.get("vibration")) or 0.4
    now = datetime.now().replace(second=0, microsecond=0)
    seed = sum(ord(char) for char in device_id) % 17
    rows: List[Dict[str, Any]] = []
    for index in range(72):
        angle = (index + seed) / 7.2
        drift = (index - 36) / 600
        rows.append(
            {
                "recorded_at": (now - timedelta(minutes=(71 - index) * 10)).isoformat(),
                "temperature": round(base_temp + math.sin(angle) * 2.2 + drift * base_temp, 2),
                "vibration": round(max(0.1, base_vib + math.sin(angle + 0.7) * 0.09 + drift), 2),
            }
        )
    return rows


def normalize_devices(devices: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for device_id, device in devices.items():
        health = health_key(device.get("health"))
        rows.append(
            {
                "Device": device_id,
                "Health": health.title(),
                "Temperature": safe_number(device.get("temperature")),
                "Vibration": safe_number(device.get("vibration")),
                "Risk": numeric_risk(device.get("risk")),
                "Status": repair_text(device.get("status") or "Unknown"),
                "Recommendation": repair_text(device.get("recommendation") or "No recommendation available."),
            }
        )
    return pd.DataFrame(rows)


def load_snapshot() -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], bool, Optional[str]]:
    devices_payload, devices_error = api_request("GET", "/devices")
    if isinstance(devices_payload, dict) and devices_payload:
        alerts_payload, _ = api_request("GET", "/alerts?include_resolved=true")
        alerts = alerts_payload if isinstance(alerts_payload, list) else []
        return devices_payload, alerts, False, None
    reason = devices_error or "The connected service has no telemetry yet."
    return demo_devices(), demo_alerts(), True, reason


def section_header(title: str, copy: str, kicker: str = "") -> None:
    kicker_html = f'<div class="zt-kicker">{html.escape(kicker)}</div>' if kicker else ""
    st.markdown(
        f'<div class="zt-section-head"><div>{kicker_html}<h2>{html.escape(title)}</h2><p>{html.escape(copy)}</p></div></div>',
        unsafe_allow_html=True,
    )


def pill(label: str, style: Optional[str] = None) -> str:
    css = style or label.lower()
    return f'<span class="zt-pill {html.escape(css)}">{html.escape(label)}</span>'


def render_sidebar(active_alerts: int, demo_mode: bool) -> str:
    with st.sidebar:
        st.markdown(
            """
            <div class="zt-brand">
                <span class="zt-mark">ZT</span><span class="zt-brand-name">ZTII</span>
                <span class="zt-brand-copy">Zero-touch industrial intelligence<br>Operations command center</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        source_label = "Portfolio demo" if demo_mode else "Live service"
        source_copy = "Representative telemetry" if demo_mode else "FastAPI connected"
        dot_class = "demo" if demo_mode else ""
        st.markdown(
            f'<div class="zt-source"><i class="zt-source-dot {dot_class}"></i><div><strong>{source_label}</strong><span>{source_copy}</span></div></div>',
            unsafe_allow_html=True,
        )
        selected = st.radio("Navigation", PAGES, label_visibility="collapsed", key="navigation")
        if active_alerts:
            st.caption(f"{active_alerts} active alert{'s' if active_alerts != 1 else ''}")
        st.divider()
        auto_refresh = st.toggle("Live refresh", value=True, key="auto_refresh")
        refresh_interval = st.selectbox("Refresh every", REFRESH_INTERVALS, index=1, format_func=lambda value: f"{value} seconds", disabled=not auto_refresh)
        if auto_refresh:
            st_autorefresh(interval=refresh_interval * 1000, key="global_refresh")
        if st.button("Refresh now", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        st.markdown(
            f'<div class="zt-side-caption">Endpoint: {html.escape(API_URL)}<br>Updated {datetime.now().strftime("%H:%M:%S")}</div>',
            unsafe_allow_html=True,
        )
    return selected


PAGE_COPY = {
    "Command Center": ("Fleet operations", "Industrial intelligence, made actionable.", "Monitor asset health, understand risk signals, and move from detection to maintenance action in one control plane."),
    "Fleet Intelligence": ("Asset intelligence", "Understand every machine.", "Bring live telemetry, operating history, AI factors, and the next best action into one focused asset view."),
    "Alerts": ("Event operations", "Turn signals into action.", "Triage risk events with clear ownership states, useful context, and fast operational controls."),
    "Provisioning": ("Zero-touch onboarding", "From discovery to monitored asset.", "Register a device, map it to an industrial asset, and start monitoring with a guided workflow."),
    "Edge & PLC": ("Industrial edge", "See the control-plane connection.", "Inspect edge synchronization, PLC state, and the Modbus register contract without losing operational context."),
}


def render_header(page: str, devices_df: pd.DataFrame, demo_mode: bool) -> None:
    eyebrow, title, copy = PAGE_COPY[page]
    critical = int((devices_df["Health"] == "Critical").sum()) if not devices_df.empty else 0
    warning = int((devices_df["Health"] == "Warning").sum()) if not devices_df.empty else 0
    if critical:
        state = f"{critical} critical"
    elif warning:
        state = f"{warning} need attention"
    else:
        state = "Fleet stable"
    connected = int((devices_df["Status"] == "Online").sum()) if not devices_df.empty else 0
    col_copy, col_status = st.columns([3.5, 1], gap="large")
    with col_copy:
        st.markdown(
            f'<div class="zt-eyebrow">{html.escape(eyebrow)}</div><h1 class="zt-title">{html.escape(title)}</h1><p class="zt-lede">{html.escape(copy)}</p>',
            unsafe_allow_html=True,
        )
    with col_status:
        live_label = "Demo telemetry" if demo_mode else "Live fleet"
        dot_class = "demo" if demo_mode else ""
        st.markdown(
            f'<div class="zt-live-card"><div class="zt-live-row"><span class="zt-live-label"><i class="zt-live-dot {dot_class}"></i>{live_label}</span><span class="zt-live-meta">{datetime.now().strftime("%H:%M")}</span></div><div class="zt-live-value">{html.escape(state)}</div><div class="zt-live-meta">{connected} of {len(devices_df)} assets connected</div></div>',
            unsafe_allow_html=True,
        )


def render_system_banner(devices_df: pd.DataFrame, demo_mode: bool) -> None:
    if demo_mode:
        st.markdown('<div class="zt-banner demo"><strong>Portfolio demonstration mode</strong><span>Representative data is active so every workflow remains explorable.</span></div>', unsafe_allow_html=True)
        return
    critical = int((devices_df["Health"] == "Critical").sum())
    warning = int((devices_df["Health"] == "Warning").sum())
    if critical:
        st.markdown(f'<div class="zt-banner critical"><strong>Immediate attention required</strong><span>{critical} critical asset{("s" if critical != 1 else "")} should be triaged now.</span></div>', unsafe_allow_html=True)
    elif warning:
        st.markdown(f'<div class="zt-banner warning"><strong>Maintenance attention advised</strong><span>{warning} asset{("s" if warning != 1 else "")} are outside their normal envelope.</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="zt-banner normal"><strong>All monitored assets are stable</strong><span>No critical or warning conditions are currently detected.</span></div>', unsafe_allow_html=True)


def render_command_center(devices: Dict[str, Dict[str, Any]], alerts: List[Dict[str, Any]], demo_mode: bool) -> None:
    df = normalize_devices(devices)
    render_system_banner(df, demo_mode)
    normal = int((df["Health"] == "Normal").sum())
    warning = int((df["Health"] == "Warning").sum())
    critical = int((df["Health"] == "Critical").sum())
    active = sum(1 for alert in alerts if status_key(alert.get("status")) == "active")
    online = int((df["Status"] == "Online").sum())
    availability = round(online / len(df) * 100) if len(df) else 0
    metrics = st.columns(5)
    metrics[0].metric("Connected assets", online, f"{len(df) - online} not communicating")
    metrics[1].metric("Fleet availability", f"{availability}%", f"{online} online of {len(df)}")
    metrics[2].metric("Warning", warning, "Plan intervention")
    metrics[3].metric("Critical", critical, "Act immediately")
    metrics[4].metric("Active alerts", active, "Open events")

    section_header("Operational picture", "Fleet distribution and the assets that deserve attention first.", "Now")
    chart_col, queue_col = st.columns([1.1, 1], gap="large")
    with chart_col:
        health_counts = df.groupby("Health", dropna=False).size().reset_index(name="Assets")
        domain = ["Normal", "Warning", "Critical", "Unknown"]
        range_colors = ["#2f8765", "#d28a30", "#b14d40", "#89958e"]
        donut = (
            alt.Chart(health_counts)
            .mark_arc(innerRadius=72, outerRadius=112, cornerRadius=5, padAngle=0.025)
            .encode(
                theta=alt.Theta("Assets:Q"),
                color=alt.Color("Health:N", scale=alt.Scale(domain=domain, range=range_colors), legend=alt.Legend(orient="bottom", title=None)),
                tooltip=["Health:N", "Assets:Q"],
            )
            .properties(height=285)
        )
        st.markdown('<div class="zt-panel"><div class="zt-panel-title">Fleet health distribution</div><div class="zt-panel-copy">Current condition across all connected assets.</div>', unsafe_allow_html=True)
        st.altair_chart(donut, width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)
    with queue_col:
        st.markdown('<div class="zt-panel"><div class="zt-panel-title">Priority attention queue</div><div class="zt-panel-copy">Sorted by health state and predicted risk.</div>', unsafe_allow_html=True)
        priority = df[df["Health"].isin(["Critical", "Warning"])].copy()
        priority["severity"] = priority["Health"].map({"Critical": 2, "Warning": 1})
        priority = priority.sort_values(["severity", "Risk"], ascending=False).head(4)
        if priority.empty:
            st.markdown('<div class="zt-attention"><div><div class="zt-device-id">No assets require attention</div><div class="zt-device-meta">The monitored fleet is within its expected envelope.</div></div></div>', unsafe_allow_html=True)
        else:
            for _, row in priority.iterrows():
                st.markdown(
                    f'<div class="zt-attention"><div><div class="zt-device-id">{html.escape(str(row["Device"]))}</div><div class="zt-device-meta">{fmt_number(row["Temperature"], 1, " °C")} · {fmt_number(row["Vibration"], 2, " mm/s")} · Risk {row["Risk"]}%</div></div>{pill(row["Health"])}</div>',
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    section_header("Live fleet", "Search and filter the operating state, then export the current view.", "Assets")
    filter_col, search_col, export_col = st.columns([1.4, 2.2, 1])
    with filter_col:
        health_filter = st.multiselect("Health", ["Normal", "Warning", "Critical", "Unknown"], default=["Normal", "Warning", "Critical", "Unknown"], label_visibility="collapsed", placeholder="Filter health")
    with search_col:
        search = st.text_input("Search assets", placeholder="Search device ID or status", label_visibility="collapsed")
    filtered = df[df["Health"].isin(health_filter)] if health_filter else df.iloc[0:0]
    if search:
        mask = filtered.astype(str).apply(lambda column: column.str.contains(search, case=False, na=False)).any(axis=1)
        filtered = filtered[mask]
    with export_col:
        st.download_button("Export view", filtered.to_csv(index=False).encode("utf-8"), "ztii-fleet.csv", "text/csv", width="stretch")
    table_df = filtered[["Device", "Health", "Temperature", "Vibration", "Risk", "Status", "Recommendation"]]
    st.caption(f"Showing {len(table_df)} of {len(df)} assets")
    st.dataframe(
        table_df,
        hide_index=True,
        width="stretch",
        column_config={
            "Temperature": st.column_config.NumberColumn("Temperature", format="%.1f °C"),
            "Vibration": st.column_config.NumberColumn("Vibration", format="%.2f mm/s"),
            "Risk": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%d%%"),
            "Recommendation": st.column_config.TextColumn("Recommended action", width="large"),
        },
    )


@st.cache_data(ttl=20, show_spinner=False)
def fetch_history(device_id: str) -> Optional[List[Dict[str, Any]]]:
    payload, _ = api_request("GET", f"/history/{device_id}?limit=500", timeout=10)
    return payload if isinstance(payload, list) else None


@st.cache_data(ttl=30, show_spinner=False)
def fetch_explanation(device_id: str) -> Optional[Dict[str, Any]]:
    payload, _ = api_request("GET", f"/explain/{device_id}", timeout=12)
    return payload if isinstance(payload, dict) else None


def fallback_explanation(device: Dict[str, Any]) -> Dict[str, Any]:
    temperature = safe_number(device.get("temperature")) or 0
    vibration = safe_number(device.get("vibration")) or 0
    temp = max(0.05, (temperature - 40) / 40)
    vib = max(0.05, (vibration - 0.3) / 1.7)
    total = temp + vib
    temp_pct = round(temp / total * 100, 1)
    vib_pct = round(vib / total * 100, 1)
    primary = "Temperature" if temp_pct >= vib_pct else "Vibration"
    return {"primary_factor": primary, "temperature": temp_pct, "vibration": vib_pct, "explanation": f"{primary} contributes most to the current risk estimate based on deviation from the normal operating baseline."}


def render_fleet_intelligence(devices: Dict[str, Dict[str, Any]], demo_mode: bool) -> None:
    if not devices:
        st.info("No assets are available yet. Provision a device to begin monitoring.")
        return
    selected = st.selectbox("Select an asset", list(devices.keys()), key="fleet_device")
    device = devices[selected]
    health = health_key(device.get("health"))
    risk = numeric_risk(device.get("risk"))
    st.markdown(
        f'<div class="zt-detail-head"><div><h2>{html.escape(selected)}</h2><p>Registered {html.escape(repair_text(device.get("registered_at") or "Date unavailable"))} · {html.escape(repair_text(device.get("status") or "Unknown"))}</p></div>{pill(health.title(), health)}</div>',
        unsafe_allow_html=True,
    )
    metrics = st.columns(4)
    metrics[0].metric("Temperature", fmt_number(device.get("temperature"), 1, " °C"), "Warning at 55 °C")
    metrics[1].metric("Vibration", fmt_number(device.get("vibration"), 2, " mm/s"), "Warning at 1.00")
    metrics[2].metric("Predicted risk", f"{risk}%", repair_text(device.get("risk") or "Awaiting model"))
    metrics[3].metric("Operating state", health.title(), repair_text(device.get("status") or "Unknown"))

    section_header("Recommended action", "Translate the current risk state into an operator-ready next step.")
    st.markdown(f'<div class="zt-recommendation"><strong>{html.escape(repair_text(device.get("recommendation") or "No recommendation available."))}</strong></div>', unsafe_allow_html=True)

    history = demo_history(selected, device) if demo_mode else fetch_history(selected)
    section_header("Operating trend", "Recent telemetry with warning and critical thresholds for context.", "Telemetry")
    if history:
        history_df = pd.DataFrame(history)
        history_df["recorded_at"] = pd.to_datetime(history_df["recorded_at"], errors="coerce")
        history_df["temperature"] = pd.to_numeric(history_df["temperature"], errors="coerce")
        history_df["vibration"] = pd.to_numeric(history_df["vibration"], errors="coerce")
        history_df = history_df.dropna(subset=["recorded_at"]).sort_values("recorded_at").tail(500)
        temp_chart = (
            alt.Chart(history_df)
            .mark_line(color="#1f7553", strokeWidth=2)
            .encode(x=alt.X("recorded_at:T", title=None), y=alt.Y("temperature:Q", title="Temperature (°C)", scale=alt.Scale(zero=False)), tooltip=[alt.Tooltip("recorded_at:T", title="Time"), alt.Tooltip("temperature:Q", title="Temperature", format=".1f")])
            .properties(height=245)
        )
        temp_rules = alt.Chart(pd.DataFrame({"threshold": [TEMP_WARNING, TEMP_CRITICAL], "level": ["Warning", "Critical"]})).mark_rule(strokeDash=[5, 4]).encode(y="threshold:Q", color=alt.Color("level:N", scale=alt.Scale(domain=["Warning", "Critical"], range=["#d28a30", "#b14d40"]), legend=None))
        vib_chart = (
            alt.Chart(history_df)
            .mark_area(line={"color": "#396b8d", "strokeWidth": 2}, color=alt.Gradient(gradient="linear", stops=[alt.GradientStop(color="#dfeaf1", offset=0), alt.GradientStop(color="#6d9ab8", offset=1)], x1=1, x2=1, y1=1, y2=0))
            .encode(x=alt.X("recorded_at:T", title=None), y=alt.Y("vibration:Q", title="Vibration (mm/s)", scale=alt.Scale(zero=False)), tooltip=[alt.Tooltip("recorded_at:T", title="Time"), alt.Tooltip("vibration:Q", title="Vibration", format=".2f")])
            .properties(height=245)
        )
        vib_rules = alt.Chart(pd.DataFrame({"threshold": [VIB_WARNING, VIB_CRITICAL], "level": ["Warning", "Critical"]})).mark_rule(strokeDash=[5, 4]).encode(y="threshold:Q", color=alt.Color("level:N", scale=alt.Scale(domain=["Warning", "Critical"], range=["#d28a30", "#b14d40"]), legend=None))
        left, right = st.columns(2, gap="large")
        with left:
            st.altair_chart(temp_chart + temp_rules, width="stretch")
        with right:
            st.altair_chart(vib_chart + vib_rules, width="stretch")
    else:
        st.info("This asset is registered and waiting for its first historical readings.")

    section_header("Explainable risk", "See which signal contributes most to the current prediction.", "AI insight")
    live_explanation = None if demo_mode or safe_number(device.get("temperature")) is None else fetch_explanation(selected)
    explanation = (live_explanation or {}).get("explanation") or fallback_explanation(device)
    primary = repair_text(explanation.get("primary_factor") or "Unknown")
    temperature_pct = min(100, max(0, float(explanation.get("temperature") or 0)))
    vibration_pct = min(100, max(0, float(explanation.get("vibration") or 0)))
    insight_col, factor_col = st.columns([1.15, 1], gap="large")
    with insight_col:
        st.markdown(f'<div class="zt-panel"><div class="zt-kicker">Primary factor</div><div class="zt-panel-title" style="font-size:1.15rem;margin-top:.25rem">{html.escape(primary)}</div><div class="zt-panel-copy" style="line-height:1.55;margin-top:.55rem">{html.escape(repair_text(explanation.get("explanation") or "No explanation available."))}</div></div>', unsafe_allow_html=True)
    with factor_col:
        bars = [("Temperature", temperature_pct), ("Vibration", vibration_pct)]
        body = "".join(f'<div class="zt-factor"><span class="zt-factor-label">{label}</span><div class="zt-factor-track"><div class="zt-factor-fill" style="width:{value:.1f}%"></div></div><span class="zt-factor-value">{value:.0f}%</span></div>' for label, value in bars)
        st.markdown(f'<div class="zt-panel"><div class="zt-panel-title">Signal contribution</div>{body}</div>', unsafe_allow_html=True)


def mutate_demo_alert(alert_id: int, new_status: str) -> None:
    for alert in demo_alerts():
        if alert.get("id") == alert_id:
            alert["status"] = new_status
            timestamp_field = "acknowledged_at" if new_status == "ACKNOWLEDGED" else "resolved_at"
            alert[timestamp_field] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def render_alerts(alerts: List[Dict[str, Any]], demo_mode: bool) -> None:
    active = sum(1 for item in alerts if status_key(item.get("status")) == "active")
    acknowledged = sum(1 for item in alerts if status_key(item.get("status")) == "acknowledged")
    resolved = sum(1 for item in alerts if status_key(item.get("status")) == "resolved")
    metrics = st.columns(4)
    metrics[0].metric("All events", len(alerts))
    metrics[1].metric("Active", active, "Needs owner")
    metrics[2].metric("Acknowledged", acknowledged, "In progress")
    metrics[3].metric("Resolved", resolved, "Closed")
    section_header("Event queue", "Filter by operating priority, then acknowledge or resolve actionable events.", "Operations")
    filter_status, filter_level, filter_device = st.columns(3)
    with filter_status:
        statuses = st.multiselect("Status", ["ACTIVE", "ACKNOWLEDGED", "RESOLVED"], default=["ACTIVE", "ACKNOWLEDGED", "RESOLVED"])
    with filter_level:
        levels = st.multiselect("Severity", ["Critical", "Warning", "Recovery"], default=["Critical", "Warning", "Recovery"])
    device_options = sorted({str(item.get("device_id", "Unknown")) for item in alerts})
    with filter_device:
        device_filter = st.selectbox("Asset", ["All assets"] + device_options)
    filtered = [item for item in alerts if str(item.get("status", "")).upper() in statuses and repair_text(item.get("level")) in levels and (device_filter == "All assets" or item.get("device_id") == device_filter)]
    if not filtered:
        st.info("No alerts match the current filters.")
        return
    for alert in filtered:
        alert_id = int(alert.get("id") or 0)
        level = repair_text(alert.get("level") or "Unknown")
        status = status_key(alert.get("status"))
        card_col, action_col = st.columns([5, 1.2], gap="medium")
        with card_col:
            st.markdown(
                f'<div class="zt-alert-card"><div class="zt-alert-top"><span class="zt-device-id">{html.escape(str(alert.get("device_id") or "Unknown asset"))}</span>{pill(level, level.lower())} {pill(status.title(), status)}</div><div class="zt-alert-message">{html.escape(repair_text(alert.get("message") or "No message provided."))}</div><div class="zt-alert-meta">Event #{alert_id} · {html.escape(repair_text(alert.get("created_at") or "Time unavailable"))}</div></div>',
                unsafe_allow_html=True,
            )
        with action_col:
            if status == "active":
                if st.button("Acknowledge", key=f"ack-{alert_id}", width="stretch"):
                    if demo_mode:
                        mutate_demo_alert(alert_id, "ACKNOWLEDGED")
                        st.rerun()
                    _, error = api_request("POST", f"/alerts/{alert_id}/acknowledge")
                    if error:
                        st.error(error)
                    else:
                        st.cache_data.clear()
                        st.rerun()
            if status in {"active", "acknowledged"}:
                if st.button("Resolve", key=f"resolve-{alert_id}", type="primary", width="stretch"):
                    if demo_mode:
                        mutate_demo_alert(alert_id, "RESOLVED")
                        st.rerun()
                    _, error = api_request("POST", f"/alerts/{alert_id}/resolve")
                    if error:
                        st.error(error)
                    else:
                        st.cache_data.clear()
                        st.rerun()


def render_provisioning(demo_mode: bool) -> None:
    section_header("Provision a new asset", "Validate device identity and map it to the operational model in one guided flow.", "Workflow")
    st.markdown('<div class="zt-stepper"><div class="zt-step">01 · Discover</div><div class="zt-step">02 · Verify Key</div><div class="zt-step">03 · Register</div><div class="zt-step">04 · Monitor</div></div>', unsafe_allow_html=True)
    form_col, context_col = st.columns([1.15, 1], gap="large")
    with form_col:
        with st.form("provision_form"):
            device_id = st.text_input("Device ID", placeholder="e.g. MTR-L04-028", help="Use the plant's durable device identifier.")
            device_key = st.text_input("Device key", type="password", placeholder="Pre-shared device key", help="Sent only as the X-Device-Key request header. It is never stored or displayed.")
            device_type = st.selectbox("Device type", ["Industrial Sensor", "Motor Controller", "Vibration Sensor", "Energy Meter", "PLC Gateway"])
            location = st.text_input("Asset location", placeholder="e.g. Line 4 / Packaging")
            submitted = st.form_submit_button("Discover and provision", type="primary", width="stretch")
        if submitted:
            clean_id = device_id.strip().upper()
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{2,39}", clean_id):
                st.error("Use 3–40 letters, numbers, dots, hyphens, or underscores for the device ID.")
            elif demo_mode:
                result = {"device_id": clean_id, "identity": f"ZTII-{clean_id}", "asset_id": f"ASSET-{clean_id}", "location": location.strip() or "Unassigned", "source": "Portfolio demo"}
                st.session_state.provision_result = result
                st.success("Device identity validated and provisioned in this demo session.")
            elif not device_key.strip():
                st.error("Enter the device's pre-shared key to provision against the live service.")
            else:
                payload, error = api_request("POST", "/discover", json={"device_id": clean_id, "device_type": device_type, "location": location.strip() or None}, headers={"X-Device-Key": device_key.strip()}, timeout=10)
                if error or not isinstance(payload, dict):
                    st.error(f"Provisioning did not complete. {error or 'The service returned an invalid response.'}")
                else:
                    st.session_state.provision_result = {**payload, "device_id": clean_id, "source": "Live service"}
                    st.success("Device provisioned successfully. It is now available to the monitoring service.")
                    st.cache_data.clear()
    with context_col:
        st.markdown('<div class="zt-panel"><div class="zt-panel-title">What ZTII automates</div><div class="zt-panel-copy">The onboarding contract is designed for consistent, low-touch industrial deployment.</div><div class="zt-attention"><div><div class="zt-device-id">Durable identity</div><div class="zt-device-meta">Creates the device and registry identity.</div></div></div><div class="zt-attention"><div><div class="zt-device-id">Asset mapping</div><div class="zt-device-meta">Links telemetry to an operating asset and location.</div></div></div><div class="zt-attention"><div><div class="zt-device-id">Monitoring readiness</div><div class="zt-device-meta">Prepares the device for telemetry, risk, and alerts.</div></div></div></div>', unsafe_allow_html=True)
    result = st.session_state.get("provision_result")
    if result:
        st.markdown(
            f'<div class="zt-provision-result"><strong>Provisioning complete</strong><div class="zt-provision-grid"><span>Device · <b>{html.escape(str(result.get("device_id") or "—"))}</b></span><span>Identity · <b>{html.escape(str(result.get("identity") or "—"))}</b></span><span>Asset · <b>{html.escape(str(result.get("asset_id") or "—"))}</b></span><span>Location · <b>{html.escape(str(result.get("location") or "—"))}</b></span></div></div>',
            unsafe_allow_html=True,
        )


def render_edge_plc(demo_mode: bool) -> None:
    plc_payload, plc_error = (None, "Demo mode") if demo_mode else api_request("GET", "/plc/status")
    sync_payload, sync_error = (None, "Demo mode") if demo_mode else api_request("GET", "/offline/status")
    plc = plc_payload if isinstance(plc_payload, dict) else {"status": "online", "mode": "simulated", "registers": {"temperature": 46.8, "vibration": 0.62, "health": 0, "risk": 26, "alarm": 0}}
    sync = sync_payload if isinstance(sync_payload, dict) else {"mode": "EDGE", "queue": {"total": 12840, "pending": 3, "synced": 12837}}
    registers = plc.get("registers") or {}
    queue = sync.get("queue") or {}
    simulated = demo_mode or str(plc.get("mode", "")).lower() == "simulated"
    section_header("Edge operating state", "Connection and synchronization health at the industrial control boundary.", "Connectivity")
    metrics = st.columns(4)
    metrics[0].metric("PLC connection", "Simulated" if simulated else str(plc.get("status", "Unknown")).title(), "Modbus TCP")
    metrics[1].metric("Edge mode", str(sync.get("mode", "Unknown")))
    metrics[2].metric("Pending sync", int(queue.get("pending") or 0), "Buffered readings")
    sync_rate = round((int(queue.get("synced") or 0) / max(1, int(queue.get("total") or 0))) * 100, 1)
    metrics[3].metric("Sync completion", f"{sync_rate}%", f"{int(queue.get('synced') or 0):,} readings")
    if simulated:
        st.markdown('<div class="zt-banner demo"><strong>Simulation is active</strong><span>The register state demonstrates the Modbus contract; it is not a claim of a connected physical PLC.</span></div>', unsafe_allow_html=True)
    elif plc_error or sync_error:
        st.warning("One or more edge services are not currently reporting.")
    section_header("Control register snapshot", "Operator-friendly values from the five-register ZTII Modbus contract.", "PLC / Modbus")
    register_col, state_col = st.columns([1.2, 1], gap="large")
    health_map = {0: "Normal", 1: "Warning", 2: "Critical"}
    alarm_map = {0: "Clear", 1: "Warning", 2: "Critical"}
    mapping = [
        ("40001", "Temperature", fmt_number(registers.get("temperature"), 1, " °C")),
        ("40002", "Vibration", fmt_number(registers.get("vibration"), 2, " mm/s")),
        ("40003", "Health", health_map.get(int(registers.get("health") or 0), "Unknown")),
        ("40004", "Risk score", f"{int(registers.get('risk') or 0)}%"),
        ("40005", "Alarm", alarm_map.get(int(registers.get("alarm") or 0), "Unknown")),
    ]
    with register_col:
        rows = "".join(f'<div class="zt-register"><span><code>{address}</code> · {label}</span><strong>{value}</strong></div>' for address, label, value in mapping)
        st.markdown(f'<div class="zt-panel"><div class="zt-panel-title">Holding registers</div><div class="zt-panel-copy">Current decoded values from the register map.</div>{rows}</div>', unsafe_allow_html=True)
    with state_col:
        risk = int(registers.get("risk") or 0)
        st.markdown(f'<div class="zt-panel"><div class="zt-panel-title">Machine state</div><div class="zt-panel-copy">Compact control-plane interpretation.</div><div class="zt-attention"><div><div class="zt-device-id">Health</div><div class="zt-device-meta">Register 40003</div></div>{pill(health_map.get(int(registers.get("health") or 0), "Unknown"))}</div><div class="zt-attention"><div><div class="zt-device-id">Alarm</div><div class="zt-device-meta">Register 40005</div></div>{pill(alarm_map.get(int(registers.get("alarm") or 0), "Unknown"), "critical" if int(registers.get("alarm") or 0) == 2 else "normal")}</div><div class="zt-attention"><div><div class="zt-device-id">Risk score</div><div class="zt-device-meta">Register 40004</div></div><strong>{risk}%</strong></div></div>', unsafe_allow_html=True)
    with st.expander("Engineering details"):
        st.write("Temperature is stored at 10× precision; vibration at 100× precision. Health and alarm registers use 0 = normal, 1 = warning, and 2 = critical.")
        st.dataframe(pd.DataFrame(mapping, columns=["Register", "Parameter", "Decoded value"]), hide_index=True, width="stretch")


def render_footer(demo_mode: bool) -> None:
    source = "Representative portfolio data" if demo_mode else "Live FastAPI service"
    st.markdown(f'<div class="zt-footer"><span>ZTII · Zero-Touch Industrial Intelligence</span><span>{source} · Updated {datetime.now().strftime("%d %b %Y, %H:%M:%S")}</span></div>', unsafe_allow_html=True)


def main() -> None:
    devices, alerts, demo_mode, _ = load_snapshot()
    df = normalize_devices(devices)
    active_alerts = sum(1 for alert in alerts if status_key(alert.get("status")) == "active")
    page = render_sidebar(active_alerts, demo_mode)
    render_header(page, df, demo_mode)
    if page == "Command Center":
        render_command_center(devices, alerts, demo_mode)
    elif page == "Fleet Intelligence":
        render_fleet_intelligence(devices, demo_mode)
    elif page == "Alerts":
        render_alerts(alerts, demo_mode)
    elif page == "Provisioning":
        render_provisioning(demo_mode)
    else:
        render_edge_plc(demo_mode)
    render_footer(demo_mode)


if __name__ == "__main__":
    main()
