"""
app.py — Streamlit Web Application for AI Drug Toxicity Prediction System.

Professional dark-themed UI with 4 modes:
  1. Single Compound Analysis
  2. Mixture Analysis
  3. Batch CSV Upload
  4. Research Dashboard

Usage:
    streamlit run src/app.py
"""

from __future__ import annotations

import sys
import numpy as np

# NumPy 1.x / 2.x compatibility layer for pickle loading
try:
    import numpy._core
except ImportError:
    try:
        import numpy.core as core
        sys.modules['numpy._core'] = core
    except Exception:
        pass
    try:
        import numpy.core.numeric as numeric
        sys.modules['numpy._core.numeric'] = numeric
    except Exception:
        pass

import os
import io
import json
import pickle
import warnings
import pandas as pd
import hashlib
import secrets

warnings.filterwarnings("ignore")

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
# RDKit is used indirectly via `src/utils.py`; imports are optional so the
# app can start without RDKit installed. See `utils.RDKit_AVAILABLE` for runtime checks.

from utils import (
    parse_input, canonicalize_smiles, smiles_to_mol, mol_to_image,
    probability_to_label, class_to_label, resolve_compound_name,
    TOXICITY_LABELS, TOXICITY_COLORS, TOXICITY_EMOJIS,
    MODEL_DIR, OUTPUT_DIR, DATA_DIR, logger,
)
from alerts import detect_alerts, compute_alert_boosted_probability, get_alert_summary_table
from disease_mapper import generate_health_report
from features import compute_features_for_smiles, get_feature_names
from mixture_analyzer import predict_single, analyze_mixture, CompoundResult
from shap_analysis import create_explainer, explain_single

# ===================================================================
# Page configuration
# ===================================================================
st.set_page_config(
    page_title="AI Drug Toxicity Prediction System",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===================================================================
# Custom CSS
# ===================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    :root {
        --bg-primary: #0a0a1a;
        --bg-secondary: #111128;
        --bg-card: rgba(26, 26, 62, 0.7);
        --accent-green: #22c55e;
        --accent-yellow: #eab308;
        --accent-orange: #f97316;
        --accent-red: #ef4444;
        --accent-crimson: #dc2626;
        --accent-blue: #6366f1;
        --accent-purple: #a855f7;
        --text-primary: #f0f0ff;
        --text-secondary: #a0a0cc;
        --border: rgba(99, 102, 241, 0.2);
    }

    .stApp {
        background: linear-gradient(135deg, #0a0a1a 0%, #111128 40%, #1a1a3e 100%);
        font-family: 'Inter', sans-serif;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d0d24 0%, #141432 100%);
        border-right: 1px solid var(--border);
    }

    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: var(--accent-blue) !important;
    }

    /* Cards */
    .glass-card {
        background: var(--bg-card);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 24px;
        marg        streamlit run pharmacy2/src/app.pyin: 10px 0;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .glass-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px rgba(99, 102, 241, 0.15);
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, rgba(26, 26, 62, 0.8), rgba(40, 40, 80, 0.6));
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin: 5px 0;
    }

    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .metric-label {
        font-size: 0.85rem;
        color: var(--text-secondary);
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Alert badges */
    .badge-critical { background: linear-gradient(135deg, #dc2626, #b91c1c); color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 0.8rem; display: inline-block; }
    .badge-high { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 0.8rem; display: inline-block; }
    .badge-moderate { background: linear-gradient(135deg, #f97316, #ea580c); color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 0.8rem; display: inline-block; }
    .badge-low { background: linear-gradient(135deg, #22c55e, #16a34a); color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 0.8rem; display: inline-block; }
    .badge-synergistic { background: linear-gradient(135deg, #dc2626, #9333ea); color: white; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 0.9rem; display: inline-block; }
    .badge-additive { background: linear-gradient(135deg, #f97316, #eab308); color: white; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 0.9rem; display: inline-block; }
    .badge-independent { background: linear-gradient(135deg, #6366f1, #3b82f6); color: white; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 0.9rem; display: inline-block; }

    /* Header */
    .main-header {
        text-align: center;
        padding: 10px 0 30px 0;
    }

    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 8px;
    }

    .main-header p {
        color: var(--text-secondary);
        font-size: 1.1rem;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background: var(--bg-card);
        border-radius: 10px;
        border: 1px solid var(--border);
        padding: 10px 20px;
        color: var(--text-secondary);
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.3), rgba(168, 85, 247, 0.3));
        border-color: var(--accent-blue);
        color: white !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 28px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4);
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 10px;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Dataframes */
    .stDataFrame {
        border: 1px solid var(--border);
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ===================================================================
# Helper functions
# ===================================================================
@st.cache_resource
def load_model():
    """Load the best trained model."""
    path = os.path.join(MODEL_DIR, "best_model.pkl")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


@st.cache_resource
def load_scaler():
    path = os.path.join(MODEL_DIR, "scaler.pkl")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


@st.cache_resource
def load_feature_names():
    path = os.path.join(MODEL_DIR, "feature_names.pkl")
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        return pickle.load(f)


@st.cache_resource
def load_training_meta():
    path = os.path.join(MODEL_DIR, "training_meta.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def make_toxicity_gauge(probability: float, label: str) -> go.Figure:
    """Create an animated toxicity gauge chart."""
    color = TOXICITY_COLORS.get(label, "#6366f1")

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=probability * 100,
        number={"suffix": "%", "font": {"size": 48, "color": "white", "family": "Inter"}},
        title={"text": f"Toxicity: {label}", "font": {"size": 18, "color": color, "family": "Inter"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#555", "tickfont": {"color": "#aaa"}},
            "bar": {"color": color, "thickness": 0.75},
            "bgcolor": "#9ad5f8",
            "borderwidth": 2,
            "bordercolor": "#777782",
            "steps": [
                {"range": [0, 20], "color": "rgba(34, 197, 94, 0.15)"},
                {"range": [20, 40], "color": "rgba(234, 179, 8, 0.15)"},
                {"range": [40, 60], "color": "rgba(249, 115, 22, 0.15)"},
                {"range": [60, 80], "color": "rgba(239, 68, 68, 0.15)"},
                {"range": [80, 100], "color": "rgba(220, 38, 38, 0.2)"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.8,
                "value": probability * 100,
            },
        },
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=280,
        margin=dict(l=30, r=30, t=60, b=20),
        font=dict(family="Inter"),
    )
    return fig


def make_organ_heatmap(organ_risks: list) -> go.Figure:
    """Create an organ risk heatmap."""
    if not organ_risks:
        return go.Figure()

    organs = [o.organ for o in organ_risks[:10]]
    scores = [o.risk_score for o in organ_risks[:10]]

    colors = []
    for s in scores:
        if s >= 70: colors.append("#dc2626")
        elif s >= 50: colors.append("#ef4444")
        elif s >= 25: colors.append("#f97316")
        else: colors.append("#22c55e")

    fig = go.Figure(go.Bar(
        x=scores, y=organs,
        orientation="h",
        marker=dict(
            color=scores,
            colorscale=[[0, "#22c55e"], [0.3, "#eab308"], [0.6, "#f97316"], [0.8, "#ef4444"], [1, "#dc2626"]],
            cmin=0, cmax=100,
        ),
        text=[f"{s:.0f}%" for s in scores],
        textposition="inside",
        textfont=dict(color="white", size=12, family="Inter"),
    ))

    fig.update_layout(
        title=dict(text="Organ Toxicity Risk", font=dict(color="white", size=16, family="Inter")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Risk Score (%)", color="#aaa", gridcolor="#333355", range=[0, 100]),
        yaxis=dict(color="#ddd", autorange="reversed"),
        height=max(300, len(organs) * 40),
        margin=dict(l=10, r=20, t=50, b=30),
        font=dict(family="Inter"),
    )
    return fig


def make_disease_chart(diseases: list) -> go.Figure:
    """Create a disease risk chart."""
    if not diseases:
        return go.Figure()

    top = diseases[:8]
    names = [d.disease for d in top]
    probs = [d.probability * 100 for d in top]
    severities = [d.severity for d in top]

    color_map = {"CRITICAL": "#dc2626", "HIGH": "#ef4444", "MODERATE": "#f97316", "LOW": "#22c55e"}
    colors = [color_map.get(s, "#6366f1") for s in severities]

    fig = go.Figure(go.Bar(
        x=probs, y=names,
        orientation="h",
        marker=dict(color=colors),
        text=[f"{p:.0f}%" for p in probs],
        textposition="inside",
        textfont=dict(color="white", size=11, family="Inter"),
    ))

    fig.update_layout(
        title=dict(text="Predicted Disease Risks", font=dict(color="white", size=16, family="Inter")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Probability (%)", color="#aaa", gridcolor="#B5B5DB", range=[0, 100]),
        yaxis=dict(color="#ddd", autorange="reversed"),
        height=max(300, len(names) * 45),
        margin=dict(l=10, r=20, t=50, b=30),
        font=dict(family="Inter"),
    )
    return fig


def render_molecule_image(smiles: str):
    """Render 2D structure of a molecule."""
    mol = smiles_to_mol(smiles)
    if mol is None:
        return None
    img = mol_to_image(mol, size=(350, 350))
    return img


def render_compound_card(result: CompoundResult, key_prefix: str = ""):
    """Render a full compound analysis card."""
    color = TOXICITY_COLORS.get(result.label, "#6366f1")
    emoji = TOXICITY_EMOJIS.get(result.label, "❓")

    # Header
    st.markdown(f"""
    <div class="glass-card">
        <h3 style="color: {color}; margin-bottom: 10px;">
            {emoji} {result.label}
            <span style="font-size: 0.8rem; color: #a0a0cc; font-weight: 400;">
                — {result.canonical_smiles[:50]}{'…' if len(result.canonical_smiles) > 50 else ''}
            </span>
        </h3>
    </div>
    """, unsafe_allow_html=True)

    # Metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{result.probability:.1%}</div>
            <div class="metric-label">Toxicity Prob.</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{result.confidence:.1%}</div>
            <div class="metric-label">Confidence</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{result.pIC50_estimate}</div>
            <div class="metric-label">pIC50 Est.</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{result.mol_weight:.0f}</div>
            <div class="metric-label">Mol. Weight</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        n_alerts = result.alert_report.n_alerts if result.alert_report else 0
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{n_alerts}</div>
            <div class="metric-label">Alerts</div>
        </div>""", unsafe_allow_html=True)

    # Layout: Gauge + Structure + Details
    col_gauge, col_struct, col_detail = st.columns([1.2, 1, 1.2])

    with col_gauge:
        fig = make_toxicity_gauge(result.probability, result.label)
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_gauge")

    with col_struct:
        img = render_molecule_image(result.canonical_smiles)
        if img is not None:
            st.image(img, caption="2D Molecular Structure", use_container_width=True)
        else:
            st.warning("Could not render molecule")

    with col_detail:
        # Structural alerts
        if result.alert_report and result.alert_report.matches:
            st.markdown("##### ⚠️ Structural Alerts")
            for m in result.alert_report.matches[:5]:
                badge_class = "badge-critical" if m.severity >= 5 else "badge-high" if m.severity >= 4 else "badge-moderate"
                st.markdown(f"""
                <span class="{badge_class}">{m.name} ({m.severity}/5)</span>
                <span style="color: #a0a0cc; font-size: 0.85rem;"> — {m.description[:60]}</span>
                """, unsafe_allow_html=True)
            st.markdown("")
        else:
            st.markdown("##### ✅ No Structural Alerts Detected")

    # Explanation
    if result.alert_report and result.alert_report.explanation:
        st.markdown(f"""
        <div class="glass-card" style="border-left: 4px solid {color};">
            <strong>🧠 AI Explanation:</strong> {result.alert_report.explanation}
        </div>
        """, unsafe_allow_html=True)

    # Disease and Organ charts
    if result.health_report:
        col_disease, col_organ = st.columns(2)
        with col_disease:
            if result.health_report.diseases:
                fig = make_disease_chart(result.health_report.diseases)
                st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_disease")
        with col_organ:
            if result.health_report.organ_risks:
                fig = make_organ_heatmap(result.health_report.organ_risks)
                st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_organ")


# ===================================================================
# SIDEBAR
# ===================================================================

# -------------------------
# Simple env-based auth
# -------------------------
def _make_password_hash(password: str, salt: bytes | None = None) -> str:
    """Create a salted PBKDF2-SHA256 hash string for storing in env vars.

    Returns: "{salt_hex}:{hash_hex}" where both parts are hex-encoded.
    """
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return salt.hex() + ":" + dk.hex()


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        return secrets.compare_digest(dk, expected)
    except Exception:
        return False


def _maybe_rerun():
    """Attempt to rerun the Streamlit script in a way compatible with multiple versions.

    If `st.experimental_rerun` is available it will be used. Otherwise the function
    sets a short-lived session flag and stops execution so the user can refresh.
    """
    try:
        rerun = getattr(st, "experimental_rerun", None)
        if callable(rerun):
            rerun()
            return
    except Exception:
        pass

    # Fallback: set a session flag and stop (user can reload the browser)
    try:
        st.session_state._needs_rerun = True
    except Exception:
        pass
    st.stop()


def _require_login():
    """If `LOGIN_USERNAME` and `LOGIN_PASSWORD_HASH` env vars are set, require login.

    - `LOGIN_USERNAME`: plaintext username
    - `LOGIN_PASSWORD_HASH`: salt:hash produced by `_make_password_hash`

    If the env vars are not set the app remains open (developer convenience).
    """
    # Prefer explicit env vars for automation; otherwise use file-backed auth
    username_env = os.getenv("LOGIN_USERNAME")
    pw_hash_env = os.getenv("LOGIN_PASSWORD_HASH")
    auth_env = bool(username_env and pw_hash_env)

    auth_file = os.path.join(MODEL_DIR, ".auth.json")

    def _load_file_creds():
        try:
            if not os.path.exists(auth_file):
                return None
            with open(auth_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data.get("username"), data.get("password_hash")
        except Exception:
            return None

    def _save_file_creds(username: str, pw_hash: str):
        data = {"username": username, "password_hash": pw_hash}
        with open(auth_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    # Determine active credential source
    if auth_env:
        stored_user, stored_hash = username_env, pw_hash_env
    else:
        file_creds = _load_file_creds()
        if file_creds:
            stored_user, stored_hash = file_creds
        else:
            stored_user, stored_hash = None, None

    # If no credentials at all, offer a signup/register flow
    if not stored_user or not stored_hash:
        st.markdown("""
        <div class="glass-card">
            <h3 style="color: #a855f7;">Create Admin Account</h3>
            <p style="color: #a0a0cc;">No credentials found. Create an admin account to secure the app.</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            new_user = st.text_input("New username", key="signup_user")
        with col2:
            new_pass = st.text_input("New password", type="password", key="signup_pass")
        new_pass_confirm = st.text_input("Confirm password", type="password", key="signup_pass_confirm")

        if st.button("Create account", key="signup_submit"):
            if not new_user or not new_pass:
                st.error("Username and password are required")
            elif new_pass != new_pass_confirm:
                st.error("Passwords do not match")
            else:
                ph = _make_password_hash(new_pass)
                try:
                    _save_file_creds(new_user, ph)
                    st.success("Account created — restarting app to apply login")
                    _maybe_rerun()
                except Exception as e:
                    st.error(f"Failed to save credentials: {e}")

        st.stop()

    # At this point we have stored_user and stored_hash (either env or file)
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        # Provide sign-out control in sidebar
        if st.sidebar.button("Sign out"):
            st.session_state.authenticated = False
            _maybe_rerun()
        return

    # Present login form
    st.markdown("""
    <div class="glass-card">
        <h3 style="color: #a855f7;">🔒 Login Required</h3>
        <p style="color: #a0a0cc;">Enter your credentials to access the application.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        user = st.text_input("Username", key="login_user")
    with col2:
        pwd = st.text_input("Password", type="password", key="login_pass")

    if st.button("Sign in", key="login_submit"):
        if user == stored_user and _verify_password(pwd, stored_hash):
            st.session_state.authenticated = True
            _maybe_rerun()
        else:
            st.error("Invalid credentials")

    st.stop()


# Enforce login (env or file-backed)
_require_login()
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h1 style="font-size: 1.8rem; background: linear-gradient(135deg, #6366f1, #a855f7);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🧬 ToxPredict AI
        </h1>
        <p style="color: #a0a0cc; font-size: 0.9rem;">
            Advanced Drug Toxicity Screening
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    mode = st.radio(
        "Analysis Mode",
        ["🔬 Single Compound", "🧪 Mixture Analysis", "📊 Batch CSV Upload", "🔍 Research Dashboard"],
        index=0,
    )

    st.divider()

    # Model info
    meta = load_training_meta()
    if meta:
        st.markdown("##### 📈 Model Info")
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #a855f7; font-weight: 600;">{meta.get('best_model', 'N/A')}</div>
            <div class="metric-label">Best Model</div>
        </div>
        """, unsafe_allow_html=True)
        best_results = meta.get("results", {}).get(meta.get("best_model", ""), {})
        if best_results:
            st.metric("F1 Score", f"{best_results.get('f1_score', 0):.4f}")
            st.metric("Accuracy", f"{best_results.get('accuracy', 0):.4f}")
            st.metric("ROC-AUC", f"{best_results.get('roc_auc', 'N/A')}")
    else:
        st.warning("⚠️ No trained model found. Run `python src/train_model.py` first.")

    st.divider()
    st.markdown("""
    <p style="color: #666; font-size: 0.75rem; text-align: center;">
        Built with RDKit • XGBoost • SHAP • Streamlit<br>
        Drug Toxicity Prediction System v1.0
    </p>
    """, unsafe_allow_html=True)


# ===================================================================
# HEADER
# ===================================================================
st.markdown("""
<div class="main-header">
    <h1>🧬 AI Drug Toxicity Prediction System</h1>
    <p>Predict compound toxicity, detect structural alerts, and assess health risks using machine learning</p>
</div>
""", unsafe_allow_html=True)


# ===================================================================
# MODE 1: Single Compound
# ===================================================================
if mode == "🔬 Single Compound":
    st.markdown("### 🔬 Single Compound Toxicity Analysis")

    col_input, col_examples = st.columns([2, 1])

    with col_input:
        input_text = st.text_input(
            "Enter SMILES string or compound name",
            placeholder="e.g., c1ccccc1  or  benzene  or  CC(=O)Nc1ccc(O)cc1",
            help="Supports SMILES notation, common compound names, or PubChem lookup",
        )

    with col_examples:
        st.markdown("##### Quick Examples")
        example_cols = st.columns(3)
        examples = [
            ("Benzene", "c1ccccc1"),
            ("Aspirin", "aspirin"),
            ("TNT", "tnt"),
            ("Caffeine", "caffeine"),
            ("Aniline", "Nc1ccccc1"),
            ("Ethanol", "CCO"),
        ]
        for i, (name, smi) in enumerate(examples):
            with example_cols[i % 3]:
                if st.button(name, key=f"ex_{i}"):
                    st.session_state["single_input"] = smi

    # Use session state for example buttons
    if "single_input" in st.session_state:
        input_text = st.session_state.pop("single_input")

    if input_text:
        with st.spinner("🔄 Analyzing compound …"):
            parsed = parse_input(input_text)
            if not parsed:
                st.error("❌ Could not parse input. Please enter a valid SMILES string or compound name.")
            else:
                smiles = parsed[0]
                result = predict_single(smiles)
                if result is None:
                    st.error("❌ Failed to analyze compound. Invalid molecular structure.")
                else:
                    render_compound_card(result, key_prefix="single")

                    # SHAP explanation (expandable)
                    with st.expander("🔍 SHAP Feature Explanation", expanded=False):
                        try:
                            model = load_model()
                            scaler = load_scaler()
                            fnames = load_feature_names()
                            if model and scaler and fnames:
                                fv = compute_features_for_smiles(result.canonical_smiles)
                                if fv is not None:
                                    fv = np.nan_to_num(fv, nan=0.0, posinf=0.0, neginf=0.0)
                                    fv_scaled = scaler.transform(fv.reshape(1, -1))
                                    shap_result = explain_single(fv_scaled, model=model, feature_names=fnames)

                                    st.markdown(f"**{shap_result['explanation_text']}**")

                                    col_toxic, col_protect = st.columns(2)
                                    with col_toxic:
                                        st.markdown("##### 🔴 Top Risk-Increasing Features")
                                        for f in shap_result["top_toxic"][:7]:
                                            st.markdown(f"- **{f['feature']}**: SHAP = {f['shap_value']:+.4f}")
                                    with col_protect:
                                        st.markdown("##### 🟢 Top Protective Features")
                                        for f in shap_result["top_protective"][:7]:
                                            st.markdown(f"- **{f['feature']}**: SHAP = {f['shap_value']:+.4f}")
                            else:
                                st.info("Train the model first to enable SHAP explanations.")
                        except Exception as e:
                            st.warning(f"SHAP analysis unavailable: {e}")

                    # Downloadable report
                    report_data = {
                        "SMILES": result.canonical_smiles,
                        "Toxicity Label": result.label,
                        "Toxicity Probability": result.probability,
                        "Confidence": result.confidence,
                        "pIC50 Estimate": result.pIC50_estimate,
                        "Molecular Weight": result.mol_weight,
                        "Structural Alerts": result.alert_report.n_alerts if result.alert_report else 0,
                        "Explanation": result.alert_report.explanation if result.alert_report else "",
                        "Diseases": ", ".join(d.disease for d in result.health_report.top_diseases) if result.health_report else "",
                    }
                    report_df = pd.DataFrame([report_data])
                    csv = report_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Report (CSV)",
                        csv, "toxicity_report.csv",
                        "text/csv", key="dl_single",
                    )


# ===================================================================
# MODE 2: Mixture Analysis
# ===================================================================
elif mode == "🧪 Mixture Analysis":
    st.markdown("### 🧪 Chemical Mixture Toxicity Analysis")

    st.markdown("""
    <div class="glass-card">
        <p style="color: var(--text-secondary);">
            Enter mixture components (2-10 compounds). Supports multiple input formats:
        </p>
        <ul style="color: var(--text-secondary);">
            <li>Comma-separated: benzene, aniline, formaldehyde</li>
            <li>Dot-separated SMILES (one line per mixture): c1ccccc1.CCO</li>
            <li>Multiple mixtures (one per line): each line is a separate mixture</li>
            <li>Mixed format: combine any format on each line</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    mixture_input = st.text_area(
        "Enter mixture components",
        placeholder="e.g., benzene, aniline, formaldehyde\nor: c1ccccc1, Nc1ccccc1, C=O\nor: c1ccccc1.CCO (benzene + ethanol)\nor paste multiple mixtures (one per line)",
        height=120,
    )

    col_btn, col_example = st.columns([1, 2])
    with col_btn:
        analyze_btn = st.button("🔬 Analyze Mixture", type="primary")
    with col_example:
        st.markdown("**Quick examples:**")
        example_mixtures = {
            "Benzene + Ethanol": "c1ccccc1.CCO",
            "Toluene + Ethanol": "Cc1ccccc1.CCO",
            "Aniline + Acetone": "Nc1ccccc1.CC(C)=O",
            "Benzene + Paracetamol": "c1ccccc1.CC(=O)Nc1ccc(O)cc1",
        }
        for name, val in example_mixtures.items():
            if st.button(name, key=f"mix_{name}"):
                st.session_state["mixture_input"] = val
                analyze_btn = True

    if "mixture_input" in st.session_state:
        mixture_input = st.session_state.pop("mixture_input")
        analyze_btn = True

    if analyze_btn and mixture_input:
        with st.spinner("🔄 Analyzing mixture …"):
            # Parse all components
            all_smiles = []
            
            # Handle both line-by-line and comma-separated input
            # First split by newlines to handle multi-line input
            lines = [line.strip() for line in mixture_input.split("\n") if line.strip()]
            
            for line in lines:
                # Each line can be comma-separated or dot-separated
                # Try comma separation first
                if "," in line and "." not in line:
                    # Comma-separated on this line
                    for part in line.split(","):
                        parsed = parse_input(part.strip())
                        all_smiles.extend(parsed)
                else:
                    # Try parsing as a single entry (may contain dots for mixtures)
                    parsed = parse_input(line)
                    all_smiles.extend(parsed)

            if len(all_smiles) < 2:
                st.error("❌ Need at least 2 valid compounds. Check your input.")
            else:
                result = analyze_mixture(all_smiles)
                if result is None:
                    st.error("❌ Mixture analysis failed.")
                else:
                    # Combined result header
                    color = TOXICITY_COLORS.get(result.combined_label, "#6366f1")
                    emoji = TOXICITY_EMOJIS.get(result.combined_label, "❓")

                    st.markdown(f"""
                    <div class="glass-card" style="border: 2px solid {color};">
                        <h2 style="color: {color}; text-align: center;">
                            {emoji} Combined Toxicity: {result.combined_label}
                            ({result.combined_probability:.1%})
                        </h2>
                    </div>
                    """, unsafe_allow_html=True)

                    # Top metrics
                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        badge_cls = f"badge-{'synergistic' if result.interaction_type == 'SYNERGISTIC' else 'additive' if result.interaction_type == 'ADDITIVE' else 'independent'}"
                        st.markdown(f"""<div class="metric-card">
                            <span class="{badge_cls}">{result.interaction_type}</span>
                            <div class="metric-label" style="margin-top: 8px;">Interaction Type</div>
                        </div>""", unsafe_allow_html=True)
                    with m2:
                        st.markdown(f"""<div class="metric-card">
                            <div class="metric-value">{result.combined_confidence:.1%}</div>
                            <div class="metric-label">Confidence</div>
                        </div>""", unsafe_allow_html=True)
                    with m3:
                        st.markdown(f"""<div class="metric-card">
                            <div class="metric-value">{result.danger_level}/10</div>
                            <div class="metric-label">Danger Level</div>
                        </div>""", unsafe_allow_html=True)
                    with m4:
                        if result.most_dangerous:
                            st.markdown(f"""<div class="metric-card">
                                <div style="color: #ef4444; font-weight: 700; font-size: 0.9rem;">
                                    {result.most_dangerous.canonical_smiles[:25]}…
                                </div>
                                <div class="metric-label">Most Dangerous</div>
                            </div>""", unsafe_allow_html=True)

                    # Interaction explanation
                    st.markdown(f"""
                    <div class="glass-card" style="border-left: 4px solid {color};">
                        <strong>⚗️ Interaction Analysis:</strong> {result.interaction_explanation}
                    </div>
                    """, unsafe_allow_html=True)

                    # Combined gauge
                    fig = make_toxicity_gauge(result.combined_probability, result.combined_label)
                    st.plotly_chart(fig, use_container_width=True, key="mixture_gauge")

                    # Combined health report
                    if result.combined_health_report:
                        cd, co = st.columns(2)
                        with cd:
                            fig = make_disease_chart(result.combined_health_report.diseases)
                            st.plotly_chart(fig, use_container_width=True, key="mix_disease")
                        with co:
                            fig = make_organ_heatmap(result.combined_health_report.organ_risks)
                            st.plotly_chart(fig, use_container_width=True, key="mix_organ")

                    # Individual components
                    st.markdown("---")
                    st.markdown("### 📋 Individual Component Analysis")
                    for i, comp in enumerate(result.components):
                        with st.expander(f"Component {i+1}: {comp.canonical_smiles[:40]}… — {comp.label} ({comp.probability:.1%})", expanded=(i == 0)):
                            render_compound_card(comp, key_prefix=f"mix_comp_{i}")

                    # Download mixture report
                    rows = []
                    for comp in result.components:
                        rows.append({
                            "SMILES": comp.canonical_smiles,
                            "Label": comp.label,
                            "Probability": comp.probability,
                            "Confidence": comp.confidence,
                            "Alerts": comp.alert_report.n_alerts if comp.alert_report else 0,
                        })
                    rows.append({
                        "SMILES": "=== COMBINED ===",
                        "Label": result.combined_label,
                        "Probability": result.combined_probability,
                        "Confidence": result.combined_confidence,
                        "Alerts": result.interaction_type,
                    })
                    mix_df = pd.DataFrame(rows)
                    csv = mix_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Mixture Report (CSV)",
                        csv, "mixture_report.csv",
                        "text/csv", key="dl_mixture",
                    )


# ===================================================================
# MODE 3: Batch CSV Upload
# ===================================================================
elif mode == "📊 Batch CSV Upload":
    st.markdown("### 📊 Batch Toxicity Analysis")

    st.markdown("""
    <div class="glass-card">
        <p style="color: var(--text-secondary);">
            Upload a CSV file with a <code>smiles</code> column for single compounds,
            or a <code>mixture</code> column for dot/comma-separated mixtures.
            Each row will be analyzed independently.
        </p>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload CSV", type=["csv"], key="batch_upload")

    if uploaded is not None:
        df = pd.read_csv(uploaded)
        st.markdown(f"**Loaded {len(df)} rows × {len(df.columns)} columns**")
        st.dataframe(df.head(5), use_container_width=True)

        # Detect mode
        has_smiles = "smiles" in df.columns or "SMILES" in df.columns
        has_mixture = "mixture" in df.columns or "Mixture" in df.columns
        smi_col = "smiles" if "smiles" in df.columns else "SMILES" if "SMILES" in df.columns else None
        mix_col = "mixture" if "mixture" in df.columns else "Mixture" if "Mixture" in df.columns else None

        if not has_smiles and not has_mixture:
            st.error("❌ CSV must have a `smiles` or `mixture` column.")
        else:
            if st.button("🚀 Run Batch Analysis", type="primary"):
                results = []
                progress = st.progress(0)
                status = st.empty()

                total = len(df)
                for idx, row in df.iterrows():
                    i = int(idx)
                    progress.progress((i + 1) / total)
                    status.text(f"Processing {i + 1}/{total} …")

                    if mix_col and pd.notna(row.get(mix_col, None)):
                        # Mixture mode
                        parts = parse_input(str(row[mix_col]))
                        if len(parts) >= 2:
                            mix_result = analyze_mixture(parts)
                            if mix_result:
                                results.append({
                                    "Input": row[mix_col],
                                    "Mode": "Mixture",
                                    "Label": mix_result.combined_label,
                                    "Probability": mix_result.combined_probability,
                                    "Confidence": mix_result.combined_confidence,
                                    "Interaction": mix_result.interaction_type,
                                    "N_Components": len(mix_result.components),
                                    "Danger_Level": mix_result.danger_level,
                                    "Diseases": ", ".join(d.disease for d in mix_result.combined_health_report.top_diseases) if mix_result.combined_health_report else "",
                                    "Most_Dangerous": mix_result.most_dangerous.canonical_smiles[:30] if mix_result.most_dangerous else "",
                                })
                                continue

                    if smi_col and pd.notna(row.get(smi_col, None)):
                        parsed = parse_input(str(row[smi_col]))
                        if parsed:
                            comp = predict_single(parsed[0])
                            if comp:
                                results.append({
                                    "Input": row[smi_col],
                                    "Mode": "Single",
                                    "Label": comp.label,
                                    "Probability": comp.probability,
                                    "Confidence": comp.confidence,
                                    "Interaction": "N/A",
                                    "N_Components": 1,
                                    "Danger_Level": min(10, int(comp.probability * 10) + (comp.alert_report.n_alerts if comp.alert_report else 0)),
                                    "Diseases": ", ".join(d.disease for d in comp.health_report.top_diseases) if comp.health_report else "",
                                    "Most_Dangerous": "",
                                })
                                continue

                    results.append({
                        "Input": row.get(smi_col or mix_col, ""),
                        "Mode": "Error",
                        "Label": "UNKNOWN",
                        "Probability": 0,
                        "Confidence": 0,
                        "Interaction": "N/A",
                        "N_Components": 0,
                        "Danger_Level": 0,
                        "Diseases": "",
                        "Most_Dangerous": "",
                    })

                progress.progress(1.0)
                status.text("✅ Analysis complete!")

                result_df = pd.DataFrame(results)
                st.markdown("### 📊 Results")
                st.dataframe(result_df, use_container_width=True)

                # Summary statistics
                st.markdown("### 📈 Summary Statistics")
                s1, s2, s3, s4 = st.columns(4)
                with s1:
                    st.metric("Total Analyzed", len(result_df))
                with s2:
                    toxic_count = len(result_df[result_df["Label"].isin(["TOXIC", "HIGH RISK", "CRITICAL"])])
                    st.metric("Toxic+", toxic_count)
                with s3:
                    avg_prob = result_df["Probability"].mean()
                    st.metric("Avg Probability", f"{avg_prob:.1%}")
                with s4:
                    max_danger = result_df["Danger_Level"].max()
                    st.metric("Max Danger Level", f"{max_danger}/10")

                # Toxicity distribution
                col_dist, col_disease = st.columns(2)
                with col_dist:
                    label_counts = result_df["Label"].value_counts()
                    fig = px.pie(
                        values=label_counts.values,
                        names=label_counts.index,
                        title="Toxicity Distribution",
                        color=label_counts.index,
                        color_discrete_map=TOXICITY_COLORS,
                    )
                    fig.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="white", family="Inter"),
                    )
                    st.plotly_chart(fig, use_container_width=True, key="batch_pie")

                with col_disease:
                    # Most common diseases
                    all_diseases = []
                    for d in result_df["Diseases"]:
                        if isinstance(d, str) and d:
                            all_diseases.extend([x.strip() for x in d.split(",")])
                    if all_diseases:
                        disease_series = pd.Series(all_diseases).value_counts().head(10)
                        fig = px.bar(
                            x=disease_series.values,
                            y=disease_series.index,
                            orientation="h",
                            title="Most Common Disease Risks",
                            labels={"x": "Frequency", "y": "Disease"},
                        )
                        fig.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="white", family="Inter"),
                            xaxis=dict(gridcolor="#333355"),
                            yaxis=dict(autorange="reversed"),
                        )
                        fig.update_traces(marker_color="#a855f7")
                        st.plotly_chart(fig, use_container_width=True, key="batch_diseases")

                # Download
                csv = result_df.to_csv(index=False)
                st.download_button(
                    "📥 Download Full Results (CSV)",
                    csv, "batch_results.csv",
                    "text/csv", key="dl_batch",
                )


# ===================================================================
# MODE 4: Research Dashboard
# ===================================================================
elif mode == "🔍 Research Dashboard":
    st.markdown("### 🔍 Research Dashboard")

    meta = load_training_meta()

    # Dataset overview
    st.markdown("#### 📂 Dataset Overview")
    d1, d2, d3 = st.columns(3)

    tox21_path = os.path.join(DATA_DIR, "tox21.csv")
    zinc_path = os.path.join(DATA_DIR, "zinc250k.csv")
    master_path = os.path.join(DATA_DIR, "master_processed.csv")

    with d1:
        if os.path.exists(tox21_path):
            tdf = pd.read_csv(tox21_path)
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value">{len(tdf):,}</div>
                <div class="metric-label">Tox21 Molecules</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.info("Tox21 not found")
    with d2:
        if os.path.exists(zinc_path):
            zdf = pd.read_csv(zinc_path)
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value">{len(zdf):,}</div>
                <div class="metric-label">ZINC Compounds</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.info("ZINC not found")
    with d3:
        if os.path.exists(master_path):
            mdf = pd.read_csv(master_path)
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value">{len(mdf):,}</div>
                <div class="metric-label">Training Samples</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.info("Run data_prep.py first")

    st.divider()

    # Model performance
    if meta and "results" in meta:
        st.markdown("#### 📈 Model Performance Comparison")

        perf_data = []
        for name, metrics in meta["results"].items():
            perf_data.append({
                "Model": name,
                "Accuracy": metrics["accuracy"],
                "Precision": metrics["precision"],
                "Recall": metrics["recall"],
                "F1 Score": metrics["f1_score"],
                "ROC-AUC": metrics.get("roc_auc", 0),
            })
        perf_df = pd.DataFrame(perf_data)

        # Bar chart comparison
        fig = go.Figure()
        colors = ["#6366f1", "#a855f7", "#ec4899"]
        metrics_to_plot = ["Accuracy", "Precision", "Recall", "F1 Score", "ROC-AUC"]
        for i, (_, row) in enumerate(perf_df.iterrows()):
            fig.add_trace(go.Bar(
                name=row["Model"],
                x=metrics_to_plot,
                y=[row[m] for m in metrics_to_plot],
                marker_color=colors[i % len(colors)],
                text=[f"{row[m]:.3f}" for m in metrics_to_plot],
                textposition="outside",
                textfont=dict(color="white", size=11),
            ))

        fig.update_layout(
            barmode="group",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white", family="Inter"),
            xaxis=dict(gridcolor="#333355"),
            yaxis=dict(gridcolor="#333355", range=[0, 1.1], title="Score"),
            legend=dict(bgcolor="rgba(26,26,62,0.8)", bordercolor="#333355"),
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True, key="perf_chart")

        st.dataframe(perf_df.style.highlight_max(axis=0, subset=metrics_to_plot, color="#6366f1"),
                     use_container_width=True)

        st.divider()

    # Training data distribution
    if os.path.exists(master_path):
        st.markdown("#### 📊 Toxicity Class Distribution")
        mdf = pd.read_csv(master_path)

        if "toxicity_class" in mdf.columns:
            class_counts = mdf["toxicity_class"].value_counts().sort_index()
            labels = [TOXICITY_LABELS.get(i, f"Class {i}") for i in class_counts.index]
            colors = [list(TOXICITY_COLORS.values())[i] for i in class_counts.index]

            fig = go.Figure(go.Bar(
                x=labels, y=class_counts.values,
                marker=dict(color=colors),
                text=class_counts.values,
                textposition="outside",
                textfont=dict(color="white", size=12),
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white", family="Inter"),
                xaxis=dict(title="Toxicity Class", gridcolor="#333355"),
                yaxis=dict(title="Count", gridcolor="#333355"),
                height=350,
            )
            st.plotly_chart(fig, use_container_width=True, key="class_dist")

        st.divider()

    # Saved evaluation plots
    st.markdown("#### 🖼️ Evaluation Plots")
    eval_plots = ["confusion_matrices.png", "roc_curves.png", "pr_curves.png", "shap_summary.png"]
    for plot_name in eval_plots:
        plot_path = os.path.join(OUTPUT_DIR, plot_name)
        if os.path.exists(plot_path):
            st.image(plot_path, caption=plot_name.replace("_", " ").replace(".png", "").title(),
                    use_container_width=True)

    if not any(os.path.exists(os.path.join(OUTPUT_DIR, p)) for p in eval_plots):
        st.info("Run `python src/evaluate.py` and `python src/shap_analysis.py` to generate evaluation plots.")
