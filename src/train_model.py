"""
train_model.py — Train XGBoost, Random Forest, and LightGBM classifiers
for 5‑class toxicity prediction.

Saves the best model, scaler, feature names, and evaluation metrics.

Usage:
    python src/train_model.py
"""

from __future__ import annotations

import os
import sys
import pickle
import warnings
import json
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix, roc_auc_score,
)
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

from features import prepare_training_data
from utils import MODEL_DIR, OUTPUT_DIR, TOXICITY_LABELS, logger

# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------
def _build_models(n_classes: int) -> dict:
    """Return configured model instances."""
    return {
        "XGBoost": XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.1,
            objective="multi:softprob",
            num_class=n_classes,
            eval_metric="mlogloss",
            use_label_encoder=False,
            tree_method="hist",
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=300,
            max_depth=20,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
        "LightGBM": LGBMClassifier(
            n_estimators=300,
            max_depth=-1,
            learning_rate=0.1,
            num_leaves=31,
            objective="multiclass",
            num_class=n_classes,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        ),
    }


# ---------------------------------------------------------------------------
# Training pipeline
# ---------------------------------------------------------------------------
def train_and_evaluate() -> dict:
    """
    Full training pipeline:
      1.  Prepare data
      2.  Split 80/20 stratified
      3.  Train 3 models
      4.  Evaluate on test set
      5.  Save best model
    """
    # ---- Prepare data ----
    X, y, feature_names, scaler = prepare_training_data()
    n_classes = len(np.unique(y))
    logger.info(f"Training with {n_classes} classes, {X.shape[1]} features, {X.shape[0]} samples")

    # ---- Train/test split ----
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42,
    )
    logger.info(f"Train: {X_train.shape[0]}, Test: {X_test.shape[0]}")

    # Save test set for later evaluation
    np.savez(
        os.path.join(MODEL_DIR, "test_data.npz"),
        X_test=X_test, y_test=y_test,
    )

    # ---- Train models ----
    models = _build_models(n_classes)
    results: dict[str, dict] = {}
    best_model_name = None
    best_f1 = -1

    for name, model in models.items():
        logger.info(f"\n{'='*50}")
        logger.info(f"Training {name} …")
        logger.info(f"{'='*50}")

        model.fit(X_train, y_train)

        # Predictions
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)

        # Metrics
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        rec = recall_score(y_test, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

        try:
            roc = roc_auc_score(y_test, y_proba, multi_class="ovr", average="weighted")
        except Exception:
            roc = None

        cm = confusion_matrix(y_test, y_pred).tolist()
        report = classification_report(
            y_test, y_pred,
            target_names=[TOXICITY_LABELS[i] for i in range(n_classes)],
            output_dict=True,
            zero_division=0,
        )

        results[name] = {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc, 4) if roc else None,
            "confusion_matrix": cm,
            "classification_report": report,
        }

        logger.info(f"  Accuracy:  {acc:.4f}")
        logger.info(f"  Precision: {prec:.4f}")
        logger.info(f"  Recall:    {rec:.4f}")
        logger.info(f"  F1 Score:  {f1:.4f}")
        logger.info(f"  ROC-AUC:   {roc:.4f}" if roc else "  ROC-AUC:   N/A")

        # Save model
        model_path = os.path.join(MODEL_DIR, f"{name}_model.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        logger.info(f"  Saved model to {model_path}")

        if f1 > best_f1:
            best_f1 = f1
            best_model_name = name

    # ---- Save best model reference ----
    logger.info(f"\n{'='*50}")
    logger.info(f"BEST MODEL: {best_model_name}  (F1 = {best_f1:.4f})")
    logger.info(f"{'='*50}")

    meta = {
        "best_model": best_model_name,
        "best_f1": best_f1,
        "n_classes": n_classes,
        "n_features": X.shape[1],
        "n_train": X_train.shape[0],
        "n_test": X_test.shape[0],
        "feature_names_file": "feature_names.pkl",
        "scaler_file": "scaler.pkl",
        "results": results,
    }

    meta_path = os.path.join(MODEL_DIR, "training_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)
    logger.info(f"Saved training metadata to {meta_path}")

    # Copy best model as "best_model.pkl"
    import shutil
    best_src = os.path.join(MODEL_DIR, f"{best_model_name}_model.pkl")
    best_dst = os.path.join(MODEL_DIR, "best_model.pkl")
    shutil.copy2(best_src, best_dst)
    logger.info(f"Copied best model to {best_dst}")

    return results


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    results = train_and_evaluate()
    print("\nTraining complete!")
    for name, metrics in results.items():
        print(f"\n  {name}:")
        print(f"    Accuracy:  {metrics['accuracy']}")
        print(f"    F1 Score:  {metrics['f1_score']}")
        print(f"    ROC-AUC:   {metrics['roc_auc']}")
