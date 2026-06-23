"""
evaluate.py — Model evaluation, visualization, and comparison.

Generates confusion matrices, ROC curves, PR curves, and comparison tables.

Usage:
    python src/evaluate.py
"""

from __future__ import annotations

import os
import sys
import json
import pickle
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sklearn.metrics import (
    confusion_matrix, ConfusionMatrixDisplay,
    roc_curve, auc, precision_recall_curve, average_precision_score,
    classification_report,
)
from sklearn.preprocessing import label_binarize

from utils import MODEL_DIR, OUTPUT_DIR, TOXICITY_LABELS, logger

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "figure.facecolor": "#0e1117",
    "axes.facecolor": "#1a1a2e",
    "text.color": "#ffffff",
    "axes.labelcolor": "#ffffff",
    "xtick.color": "#cccccc",
    "ytick.color": "#cccccc",
    "axes.edgecolor": "#333355",
    "grid.color": "#333355",
    "font.family": "sans-serif",
})

COLORS = ["#22c55e", "#eab308", "#f97316", "#ef4444", "#dc2626"]
MODEL_NAMES = ["XGBoost", "RandomForest", "LightGBM"]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def _load_test_data():
    data = np.load(os.path.join(MODEL_DIR, "test_data.npz"))
    return data["X_test"], data["y_test"]


def _load_model(name: str):
    path = os.path.join(MODEL_DIR, f"{name}_model.pkl")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def _load_meta():
    path = os.path.join(MODEL_DIR, "training_meta.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------
def plot_confusion_matrices():
    """Plot confusion matrix for each model."""
    X_test, y_test = _load_test_data()
    n_classes = len(np.unique(y_test))
    labels = [TOXICITY_LABELS[i] for i in range(n_classes)]

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle("Confusion Matrices", fontsize=16, color="white", y=1.02)

    for idx, name in enumerate(MODEL_NAMES):
        model = _load_model(name)
        if model is None:
            continue

        y_pred = model.predict(X_test)
        cm = confusion_matrix(y_test, y_pred)

        ax = axes[idx]
        sns.heatmap(
            cm, annot=True, fmt="d", cmap="YlOrRd",
            xticklabels=labels, yticklabels=labels,
            ax=ax, cbar_kws={"shrink": 0.8},
        )
        ax.set_title(name, fontsize=14, color="white")
        ax.set_ylabel("True Label" if idx == 0 else "")
        ax.set_xlabel("Predicted Label")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "confusion_matrices.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#0e1117")
    plt.close(fig)
    logger.info(f"Saved confusion matrices to {path}")
    return path


# ---------------------------------------------------------------------------
# ROC curves
# ---------------------------------------------------------------------------
def plot_roc_curves():
    """Plot one-vs-rest ROC curves for each model."""
    X_test, y_test = _load_test_data()
    n_classes = len(np.unique(y_test))
    y_bin = label_binarize(y_test, classes=list(range(n_classes)))

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle("ROC Curves (One-vs-Rest)", fontsize=16, color="white", y=1.02)

    for idx, name in enumerate(MODEL_NAMES):
        model = _load_model(name)
        if model is None:
            continue

        y_proba = model.predict_proba(X_test)
        ax = axes[idx]

        for i in range(n_classes):
            if y_bin[:, i].sum() == 0:
                continue
            fpr, tpr, _ = roc_curve(y_bin[:, i], y_proba[:, i])
            roc_auc = auc(fpr, tpr)
            ax.plot(fpr, tpr, color=COLORS[i], linewidth=2,
                    label=f"{TOXICITY_LABELS[i]} (AUC={roc_auc:.2f})")

        ax.plot([0, 1], [0, 1], "w--", alpha=0.3)
        ax.set_title(name, fontsize=14, color="white")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate" if idx == 0 else "")
        ax.legend(fontsize=8, loc="lower right",
                  facecolor="#1a1a2e", edgecolor="#333355", labelcolor="white")
        ax.set_xlim([0, 1])
        ax.set_ylim([0, 1.05])

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "roc_curves.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#0e1117")
    plt.close(fig)
    logger.info(f"Saved ROC curves to {path}")
    return path


# ---------------------------------------------------------------------------
# PR curves
# ---------------------------------------------------------------------------
def plot_pr_curves():
    """Plot precision-recall curves for each model."""
    X_test, y_test = _load_test_data()
    n_classes = len(np.unique(y_test))
    y_bin = label_binarize(y_test, classes=list(range(n_classes)))

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle("Precision-Recall Curves", fontsize=16, color="white", y=1.02)

    for idx, name in enumerate(MODEL_NAMES):
        model = _load_model(name)
        if model is None:
            continue

        y_proba = model.predict_proba(X_test)
        ax = axes[idx]

        for i in range(n_classes):
            if y_bin[:, i].sum() == 0:
                continue
            prec, rec, _ = precision_recall_curve(y_bin[:, i], y_proba[:, i])
            ap = average_precision_score(y_bin[:, i], y_proba[:, i])
            ax.plot(rec, prec, color=COLORS[i], linewidth=2,
                    label=f"{TOXICITY_LABELS[i]} (AP={ap:.2f})")

        ax.set_title(name, fontsize=14, color="white")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision" if idx == 0 else "")
        ax.legend(fontsize=8, loc="lower left",
                  facecolor="#1a1a2e", edgecolor="#333355", labelcolor="white")
        ax.set_xlim([0, 1])
        ax.set_ylim([0, 1.05])

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "pr_curves.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#0e1117")
    plt.close(fig)
    logger.info(f"Saved PR curves to {path}")
    return path


# ---------------------------------------------------------------------------
# Model comparison table
# ---------------------------------------------------------------------------
def generate_comparison_table() -> pd.DataFrame:
    """Create a model comparison table from saved metadata."""
    meta = _load_meta()
    if not meta or "results" not in meta:
        logger.warning("No training metadata found.")
        return pd.DataFrame()

    rows = []
    for name, metrics in meta["results"].items():
        rows.append({
            "Model": name,
            "Accuracy": metrics["accuracy"],
            "Precision": metrics["precision"],
            "Recall": metrics["recall"],
            "F1 Score": metrics["f1_score"],
            "ROC-AUC": metrics.get("roc_auc", "N/A"),
        })

    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, "model_comparison.csv")
    df.to_csv(path, index=False)
    logger.info(f"Saved model comparison to {path}")
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_evaluation():
    """Run all evaluation steps."""
    logger.info("=" * 60)
    logger.info("RUNNING MODEL EVALUATION")
    logger.info("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    plot_confusion_matrices()
    plot_roc_curves()
    plot_pr_curves()
    comparison = generate_comparison_table()

    logger.info("\n" + comparison.to_string(index=False))
    logger.info("\nEvaluation complete!")
    return comparison


if __name__ == "__main__":
    run_evaluation()
