"""
shap_analysis.py — SHAP explainability engine for toxicity predictions.

Generates SHAP summary plots, dependence plots, force plots,
and human-readable explanations combining SHAP values with structural alerts.

Usage:
    python src/shap_analysis.py
"""

from __future__ import annotations

import os
import sys
import pickle
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import shap
from utils import MODEL_DIR, OUTPUT_DIR, TOXICITY_LABELS, logger


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def _load_model(name: str = None):
    """Load a trained model. If name is None, load the best model."""
    if name is None:
        path = os.path.join(MODEL_DIR, "best_model.pkl")
    else:
        path = os.path.join(MODEL_DIR, f"{name}_model.pkl")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def _load_feature_names() -> list[str]:
    path = os.path.join(MODEL_DIR, "feature_names.pkl")
    with open(path, "rb") as f:
        return pickle.load(f)


def _load_scaler():
    path = os.path.join(MODEL_DIR, "scaler.pkl")
    with open(path, "rb") as f:
        return pickle.load(f)


def _load_test_data():
    data = np.load(os.path.join(MODEL_DIR, "test_data.npz"))
    return data["X_test"], data["y_test"]


# ---------------------------------------------------------------------------
# SHAP explainer creation
# ---------------------------------------------------------------------------
def create_explainer(model=None, X_background=None):
    """Create a SHAP TreeExplainer (or KernelExplainer fallback)."""
    if model is None:
        model = _load_model()

    try:
        explainer = shap.TreeExplainer(model)
        logger.info("Created SHAP TreeExplainer")
    except Exception:
        if X_background is None:
            X_test, _ = _load_test_data()
            X_background = shap.sample(X_test, min(100, len(X_test)))
        explainer = shap.KernelExplainer(model.predict_proba, X_background)
        logger.info("Created SHAP KernelExplainer (fallback)")

    return explainer


# ---------------------------------------------------------------------------
# Single-instance explanation
# ---------------------------------------------------------------------------
def explain_single(
    feature_vector: np.ndarray,
    model=None,
    explainer=None,
    feature_names: list[str] | None = None,
    predicted_class: int | None = None,
) -> dict:
    """
    Generate SHAP explanation for a single molecule.

    Returns dict with:
      - shap_values: raw array
      - top_toxic: features pushing toward toxicity
      - top_protective: features pushing toward non-toxic
      - explanation_text: human-readable narrative
      - force_plot_html: HTML string for force plot (if possible)
    """
    if model is None:
        model = _load_model()
    if explainer is None:
        explainer = create_explainer(model)
    if feature_names is None:
        feature_names = _load_feature_names()

    # Reshape to 2D if needed
    x = feature_vector.reshape(1, -1) if feature_vector.ndim == 1 else feature_vector

    # Get SHAP values
    shap_vals = explainer.shap_values(x)

    # For multi-class, shap_vals is a list of arrays [n_classes][n_samples, n_features]
    # or for newer SHAP, it might be an Explanation object
    if isinstance(shap_vals, list):
        # Use the predicted class (or class with max sum if not provided)
        if predicted_class is None:
            predicted_class = int(model.predict(x)[0])
        sv = shap_vals[predicted_class][0]
    elif isinstance(shap_vals, np.ndarray) and shap_vals.ndim == 3:
        if predicted_class is None:
            predicted_class = int(model.predict(x)[0])
        sv = shap_vals[0, :, predicted_class]
    elif isinstance(shap_vals, np.ndarray) and shap_vals.ndim == 2:
        sv = shap_vals[0]
    else:
        # Explanation object
        try:
            if predicted_class is None:
                predicted_class = int(model.predict(x)[0])
            sv = shap_vals.values[0, :, predicted_class] if shap_vals.values.ndim == 3 else shap_vals.values[0]
        except Exception:
            sv = np.zeros(len(feature_names))

    # Sort features by SHAP magnitude
    indices = np.argsort(np.abs(sv))[::-1]

    # Top toxic (positive SHAP = pushing toward predicted class)
    top_toxic = []
    top_protective = []
    for i in indices[:20]:
        entry = {
            "feature": feature_names[i] if i < len(feature_names) else f"Feature_{i}",
            "shap_value": round(float(sv[i]), 4),
            "raw_value": round(float(x[0, i]), 4),
        }
        if sv[i] > 0:
            top_toxic.append(entry)
        else:
            top_protective.append(entry)

    # Human-readable narrative
    explanation = _build_narrative(top_toxic[:5], top_protective[:3], predicted_class)

    # Force plot HTML
    force_html = None
    try:
        base_val = explainer.expected_value
        if isinstance(base_val, (list, np.ndarray)):
            base_val = base_val[predicted_class] if predicted_class < len(base_val) else base_val[0]
        force_plot = shap.force_plot(base_val, sv, x[0], feature_names=feature_names)
        force_html = shap.getjs() + force_plot.html()
    except Exception:
        pass

    return {
        "shap_values": sv,
        "top_toxic": top_toxic[:10],
        "top_protective": top_protective[:10],
        "explanation_text": explanation,
        "force_plot_html": force_html,
        "predicted_class": predicted_class,
    }


def _build_narrative(
    top_toxic: list[dict],
    top_protective: list[dict],
    predicted_class: int,
) -> str:
    """Build a human-readable explanation from SHAP features."""
    label = TOXICITY_LABELS.get(predicted_class, "UNKNOWN")

    if not top_toxic and not top_protective:
        return f"Predicted **{label}** — insufficient feature information for explanation."

    parts = [f"This molecule is predicted **{label}**."]

    if top_toxic:
        toxic_names = [f"**{t['feature']}**" for t in top_toxic[:3]]
        parts.append(
            f"Key risk-increasing features: {', '.join(toxic_names)}."
        )

    if top_protective:
        safe_names = [f"**{p['feature']}**" for p in top_protective[:3]]
        parts.append(
            f"Protective features: {', '.join(safe_names)}."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Global SHAP analysis (on test set)
# ---------------------------------------------------------------------------
def run_global_analysis():
    """
    Run SHAP analysis on the test set and save summary plots.
    """
    logger.info("Running global SHAP analysis …")

    model = _load_model()
    if model is None:
        logger.error("No trained model found.")
        return

    X_test, y_test = _load_test_data()
    feature_names = _load_feature_names()
    explainer = create_explainer(model)

    # Use a subsample for speed
    n_sample = min(500, len(X_test))
    indices = np.random.RandomState(42).choice(len(X_test), n_sample, replace=False)
    X_sample = X_test[indices]

    logger.info(f"Computing SHAP values for {n_sample} samples …")
    shap_vals = explainer.shap_values(X_sample)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # --- Summary bar plot ---
    try:
        fig, ax = plt.subplots(figsize=(12, 8))
        if isinstance(shap_vals, list):
            # Average absolute SHAP across classes
            avg_shap = np.mean([np.abs(sv).mean(axis=0) for sv in shap_vals], axis=0)
        elif isinstance(shap_vals, np.ndarray) and shap_vals.ndim == 3:
            avg_shap = np.abs(shap_vals).mean(axis=(0, 2))
        else:
            avg_shap = np.abs(shap_vals).mean(axis=0)

        top_idx = np.argsort(avg_shap)[-20:]
        top_names = [feature_names[i] if i < len(feature_names) else f"F_{i}" for i in top_idx]
        top_vals = avg_shap[top_idx]

        colors = plt.cm.YlOrRd(np.linspace(0.3, 0.9, len(top_idx)))
        ax.barh(range(len(top_idx)), top_vals, color=colors)
        ax.set_yticks(range(len(top_idx)))
        ax.set_yticklabels(top_names, fontsize=9)
        ax.set_xlabel("Mean |SHAP Value|", fontsize=12)
        ax.set_title("Top 20 Most Important Features (SHAP)", fontsize=14, color="white")
        fig.patch.set_facecolor("#0e1117")
        ax.set_facecolor("#1a1a2e")
        plt.tight_layout()
        path = os.path.join(OUTPUT_DIR, "shap_summary.png")
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#0e1117")
        plt.close(fig)
        logger.info(f"Saved SHAP summary to {path}")
    except Exception as e:
        logger.warning(f"Could not generate SHAP summary plot: {e}")

    # --- Dependence plots for top 5 features ---
    try:
        top5 = np.argsort(avg_shap)[-5:][::-1]
        fig, axes = plt.subplots(1, 5, figsize=(25, 5))
        fig.suptitle("SHAP Dependence Plots — Top 5 Features", fontsize=14, color="white")

        for i, feat_idx in enumerate(top5):
            ax = axes[i]
            if isinstance(shap_vals, list):
                sv = shap_vals[0][:, feat_idx]
            elif isinstance(shap_vals, np.ndarray) and shap_vals.ndim == 3:
                sv = shap_vals[:, feat_idx, 0]
            else:
                sv = shap_vals[:, feat_idx]

            ax.scatter(
                X_sample[:, feat_idx], sv,
                c=sv, cmap="coolwarm", alpha=0.5, s=10,
            )
            fname = feature_names[feat_idx] if feat_idx < len(feature_names) else f"F_{feat_idx}"
            ax.set_xlabel(fname, fontsize=10)
            ax.set_ylabel("SHAP Value" if i == 0 else "", fontsize=10)
            ax.set_title(fname, fontsize=11, color="white")
            ax.set_facecolor("#1a1a2e")

        fig.patch.set_facecolor("#0e1117")
        plt.tight_layout()
        path = os.path.join(OUTPUT_DIR, "shap_dependence.png")
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#0e1117")
        plt.close(fig)
        logger.info(f"Saved SHAP dependence plots to {path}")
    except Exception as e:
        logger.warning(f"Could not generate dependence plots: {e}")

    logger.info("✅ Global SHAP analysis complete")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_global_analysis()
