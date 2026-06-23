"""
data_prep.py — Data loading, cleaning, merging, and label derivation.

Processes Tox21, ChEMBL, and ZINC datasets into a single training-ready
master file with 5-class toxicity labels.

Usage:
    python src/data_prep.py
"""

from __future__ import annotations

import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import (
    canonicalize_smiles,
    compute_pIC50,
    estimate_pIC50_from_assays,
    DATA_DIR,
    logger,
)

# Tox21 assay columns
TOX21_ASSAYS = [
    "NR-AR", "NR-AR-LBD", "NR-AhR", "NR-Aromatase",
    "NR-ER", "NR-ER-LBD", "NR-PPAR-gamma",
    "SR-ARE", "SR-ATAD5", "SR-HSE", "SR-MMP", "SR-p53",
]


# ===================================================================
# Step 1 — Load and clean Tox21
# ===================================================================
def load_tox21(path: str | None = None) -> pd.DataFrame:
    """Load and preprocess Tox21 dataset."""
    if path is None:
        path = os.path.join(DATA_DIR, "tox21.csv")
    logger.info(f"Loading Tox21 from {path}")
    df = pd.read_csv(path)
    logger.info(f"  Raw shape: {df.shape}")

    # Canonicalize SMILES
    df["canonical_smiles"] = df["smiles"].apply(canonicalize_smiles)
    df = df.dropna(subset=["canonical_smiles"]).copy()

    # Remove duplicates (keep first)
    df = df.drop_duplicates(subset=["canonical_smiles"], keep="first")

    # Compute assay hit count (number of positive assays)
    df["assay_hits"] = df[TOX21_ASSAYS].sum(axis=1).fillna(0).astype(int)
    df["assay_tested"] = df[TOX21_ASSAYS].notna().sum(axis=1).astype(int)

    # Binary toxicity: any positive assay
    df["tox_binary"] = (df["assay_hits"] > 0).astype(int)

    logger.info(f"  Cleaned shape: {df.shape}")
    logger.info(f"  Toxic: {df['tox_binary'].sum()}, Non-toxic: {(df['tox_binary']==0).sum()}")
    return df


# ===================================================================
# Step 2 — Load and clean ChEMBL
# ===================================================================
def load_chembl(path: str | None = None) -> pd.DataFrame:
    """Load ChEMBL data, filter IC50, compute pIC50."""
    if path is None:
        path = os.path.join(DATA_DIR, "chembl.csv")
    logger.info(f"Loading ChEMBL from {path}")
    df = pd.read_csv(path, sep=";")
    logger.info(f"  Raw shape: {df.shape}")

    # Filter to IC50 entries with valid values
    ic50 = df[df["Standard Type"] == "IC50"].copy()
    ic50 = ic50.dropna(subset=["Standard Value"])
    ic50["Standard Value"] = pd.to_numeric(ic50["Standard Value"], errors="coerce")
    ic50 = ic50.dropna(subset=["Standard Value"])
    ic50 = ic50[ic50["Standard Value"] > 0]

    # Canonicalize SMILES
    ic50["canonical_smiles"] = ic50["Smiles"].apply(canonicalize_smiles)
    ic50 = ic50.dropna(subset=["canonical_smiles"])

    # Compute pIC50
    ic50["pIC50"] = ic50["Standard Value"].apply(compute_pIC50)

    # Average pIC50 per compound
    grouped = (
        ic50.groupby("canonical_smiles")
        .agg(
            pIC50=("pIC50", "mean"),
            IC50_nM=("Standard Value", "median"),
            n_measurements=("pIC50", "count"),
        )
        .reset_index()
    )

    logger.info(f"  Unique compounds with IC50: {len(grouped)}")
    logger.info(f"  pIC50 range: {grouped['pIC50'].min():.2f} – {grouped['pIC50'].max():.2f}")
    return grouped


# ===================================================================
# Step 3 — Load and clean ZINC
# ===================================================================
def load_zinc(path: str | None = None, sample_n: int = 5000) -> pd.DataFrame:
    """Load ZINC drug-like compounds and sample non-toxic examples."""
    if path is None:
        path = os.path.join(DATA_DIR, "zinc250k.csv")
    logger.info(f"Loading ZINC from {path}")
    df = pd.read_csv(path)
    logger.info(f"  Raw shape: {df.shape}")

    # Clean SMILES (strip newlines)
    df["smiles"] = df["smiles"].str.strip()

    # Sample first to save time on canonicalization
    if sample_n and len(df) > sample_n:
        # Sample double the amount to account for duplicates/invalids
        df = df.sample(n=min(sample_n * 2, len(df)), random_state=42)

    df["canonical_smiles"] = df["smiles"].apply(canonicalize_smiles)
    df = df.dropna(subset=["canonical_smiles"])
    df = df.drop_duplicates(subset=["canonical_smiles"], keep="first")

    # Sample down to exactly sample_n if we have more
    if sample_n and len(df) > sample_n:
        df = df.sample(n=sample_n, random_state=42)
        logger.info(f"  Sampled {sample_n} compounds")

    logger.info(f"  Cleaned shape: {df.shape}")
    return df


# ===================================================================
# Step 4 — Merge datasets
# ===================================================================
def merge_datasets(
    tox21: pd.DataFrame,
    chembl: pd.DataFrame,
    zinc: pd.DataFrame,
) -> pd.DataFrame:
    """Merge all three datasets on canonical SMILES."""
    logger.info("Merging datasets …")

    # --- Tox21 base ---
    master = tox21[["canonical_smiles", "tox_binary", "assay_hits", "assay_tested"]
                    + TOX21_ASSAYS].copy()

    # --- Merge ChEMBL pIC50 ---
    master = master.merge(
        chembl[["canonical_smiles", "pIC50", "IC50_nM"]],
        on="canonical_smiles",
        how="left",
    )

    # --- Fill missing pIC50 from assay hits ---
    mask = master["pIC50"].isna()
    master.loc[mask, "pIC50"] = master.loc[mask, "assay_hits"].apply(
        lambda h: estimate_pIC50_from_assays(h)
    )

    # --- Add ZINC as non-toxic ---
    zinc_clean = zinc[["canonical_smiles", "logP", "qed", "SAS"]].copy()
    # Exclude ZINC molecules already in Tox21
    zinc_clean = zinc_clean[~zinc_clean["canonical_smiles"].isin(master["canonical_smiles"])]
    zinc_clean["tox_binary"] = 0
    zinc_clean["assay_hits"] = 0
    zinc_clean["assay_tested"] = 0
    zinc_clean["pIC50"] = 4.0  # baseline non-toxic
    for col in TOX21_ASSAYS:
        zinc_clean[col] = 0.0

    master = pd.concat([master, zinc_clean], ignore_index=True)

    # --- Merge ZINC properties back for Tox21 molecules too ---
    zinc_props = zinc[["canonical_smiles", "logP", "qed", "SAS"]].drop_duplicates(
        subset=["canonical_smiles"]
    )
    for col in ["logP", "qed", "SAS"]:
        if col not in master.columns:
            master[col] = np.nan
        # Fill from ZINC where available
        zinc_lookup = zinc_props.set_index("canonical_smiles")[col]
        missing = master[col].isna()
        master.loc[missing, col] = master.loc[missing, "canonical_smiles"].map(zinc_lookup)

    logger.info(f"  Merged shape: {master.shape}")
    return master


# ===================================================================
# Step 5 — Derive 5-class toxicity labels
# ===================================================================
def derive_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive multi-class toxicity labels.

    Classes:
      0 = NON-TOXIC   : 0 assay hits AND pIC50 < 5.0
      1 = MODERATE     : 1-2 assay hits  OR 5.0 ≤ pIC50 < 5.5
      2 = TOXIC        : 3-4 assay hits  OR 5.5 ≤ pIC50 < 6.0
      3 = HIGH RISK    : 5-6 assay hits  OR 6.0 ≤ pIC50 < 7.0
      4 = CRITICAL     : 7+  assay hits  OR pIC50 ≥ 7.0
    """
    logger.info("Deriving 5-class toxicity labels …")

    conditions = [
        (df["assay_hits"] >= 7) | (df["pIC50"] >= 7.0),          # CRITICAL
        (df["assay_hits"] >= 5) | (df["pIC50"] >= 6.0),          # HIGH RISK
        (df["assay_hits"] >= 3) | (df["pIC50"] >= 5.5),          # TOXIC
        (df["assay_hits"] >= 1) | (df["pIC50"] >= 5.0),          # MODERATE
    ]
    choices = [4, 3, 2, 1]
    df["toxicity_class"] = np.select(conditions, choices, default=0)

    counts = df["toxicity_class"].value_counts().sort_index()
    labels = {0: "NON-TOXIC", 1: "MODERATE", 2: "TOXIC", 3: "HIGH RISK", 4: "CRITICAL"}
    for cls, cnt in counts.items():
        logger.info(f"  Class {cls} ({labels[cls]}): {cnt}")

    return df


# ===================================================================
# Step 6 — Handle remaining missing values
# ===================================================================
def handle_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing values with sensible defaults."""
    logger.info("Handling missing values …")

    # Fill assay NaNs with 0 (not tested = assumed negative)
    for col in TOX21_ASSAYS:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(float)

    # Fill ZINC properties with medians
    for col in ["logP", "qed", "SAS"]:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    # Fill IC50_nM NaN with a neutral value
    if "IC50_nM" in df.columns:
        df["IC50_nM"] = df["IC50_nM"].fillna(0)

    return df


# ===================================================================
# Main pipeline
# ===================================================================
def run_pipeline() -> pd.DataFrame:
    """Execute the full preprocessing pipeline."""
    logger.info("=" * 60)
    logger.info("STARTING DATA PREPROCESSING PIPELINE")
    logger.info("=" * 60)

    tox21 = load_tox21()
    chembl = load_chembl()
    zinc = load_zinc(sample_n=5000)

    master = merge_datasets(tox21, chembl, zinc)
    master = derive_labels(master)
    master = handle_missing(master)

    # Save
    out_path = os.path.join(DATA_DIR, "master_processed.csv")
    master.to_csv(out_path, index=False)
    logger.info(f"Saved processed data to {out_path}")
    logger.info(f"Final shape: {master.shape}")
    logger.info("=" * 60)
    logger.info("PREPROCESSING COMPLETE")
    logger.info("=" * 60)

    return master


if __name__ == "__main__":
    run_pipeline()
