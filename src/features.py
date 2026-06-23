"""
features.py — Molecular feature engineering using RDKit.

Generates:
  1. Physicochemical descriptors (~25 features)
  2. Morgan fingerprints  (1024 bits)
  3. MACCS keys           (167 bits)

Total: ~1216 features per molecule.

Usage:
    python src/features.py
"""

from __future__ import annotations

import os
import sys
import warnings
import pickle
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog('rdApp.*')
    from rdkit.Chem import (
        Descriptors,
        rdMolDescriptors,
        MACCSkeys,
        AllChem,
        QED,
    )
    from rdkit.Chem import GraphDescriptors
    RDKit_AVAILABLE = True
except Exception:
    Chem = None
    Descriptors = None
    rdMolDescriptors = None
    MACCSkeys = None
    AllChem = None
    QED = None
    GraphDescriptors = None
    RDKit_AVAILABLE = False

from sklearn.preprocessing import StandardScaler

from utils import canonicalize_smiles, DATA_DIR, MODEL_DIR, logger

# ---------------------------------------------------------------------------
# Descriptor computation
# ---------------------------------------------------------------------------
DESCRIPTOR_NAMES = [
    "MolWt", "HeavyAtomMolWt", "ExactMolWt",
    "MolLogP", "TPSA",
    "NumHAcceptors", "NumHDonors",
    "NumRotatableBonds", "NumHeavyAtoms", "NumAtoms",
    "NumValenceElectrons", "NumRadicalElectrons",
    "RingCount", "NumAromaticRings", "NumAliphaticRings",
    "NumSaturatedRings", "NumAromaticHeterocycles",
    "FractionCSP3",
    "BertzCT",
    "Kappa1", "Kappa2", "Kappa3",
    "Chi0v", "Chi1v",
    "HallKierAlpha",
    "QED_score", "SAS_estimate",
]


def _compute_descriptors(mol) -> dict:
    """Compute physicochemical descriptors for a single molecule."""
    if mol is None:
        return {name: np.nan for name in DESCRIPTOR_NAMES}

    try:
        desc = {
            "MolWt": Descriptors.MolWt(mol),
            "HeavyAtomMolWt": Descriptors.HeavyAtomMolWt(mol),
            "ExactMolWt": Descriptors.ExactMolWt(mol),
            "MolLogP": Descriptors.MolLogP(mol),
            "TPSA": Descriptors.TPSA(mol),
            "NumHAcceptors": Descriptors.NumHAcceptors(mol),
            "NumHDonors": Descriptors.NumHDonors(mol),
            "NumRotatableBonds": Descriptors.NumRotatableBonds(mol),
            "NumHeavyAtoms": mol.GetNumHeavyAtoms(),
            "NumAtoms": mol.GetNumAtoms(),
            "NumValenceElectrons": Descriptors.NumValenceElectrons(mol),
            "NumRadicalElectrons": Descriptors.NumRadicalElectrons(mol),
            "RingCount": Descriptors.RingCount(mol),
            "NumAromaticRings": Descriptors.NumAromaticRings(mol),
            "NumAliphaticRings": Descriptors.NumAliphaticRings(mol),
            "NumSaturatedRings": Descriptors.NumSaturatedRings(mol),
            "NumAromaticHeterocycles": Descriptors.NumAromaticHeterocycles(mol),
            "FractionCSP3": Descriptors.FractionCSP3(mol),
            "BertzCT": GraphDescriptors.BertzCT(mol),
            "Kappa1": GraphDescriptors.Kappa1(mol),
            "Kappa2": GraphDescriptors.Kappa2(mol),
            "Kappa3": GraphDescriptors.Kappa3(mol),
            "Chi0v": GraphDescriptors.Chi0v(mol),
            "Chi1v": GraphDescriptors.Chi1v(mol),
            "HallKierAlpha": GraphDescriptors.HallKierAlpha(mol),
            "QED_score": QED.qed(mol),
        }
        # Synthetic accessibility (use SA_Score from rdkit contrib if available,
        # else use a simple estimate based on complexity)
        try:
            from rdkit.Chem import RDConfig
            sa_path = os.path.join(RDConfig.RDContribDir, "SA_Score")
            if sa_path not in sys.path:
                sys.path.insert(0, sa_path)
            import sascorer
            desc["SAS_estimate"] = sascorer.calculateScore(mol)
        except Exception:
            # Fallback: use BertzCT-based approximation
            desc["SAS_estimate"] = min(10.0, desc["BertzCT"] / 100.0)

    except Exception:
        desc = {name: np.nan for name in DESCRIPTOR_NAMES}

    return desc


# ---------------------------------------------------------------------------
# Fingerprint computation
# ---------------------------------------------------------------------------
MORGAN_NBITS = 1024
MORGAN_RADIUS = 2


def _compute_morgan(mol) -> np.ndarray:
    """Morgan fingerprint as bit vector."""
    if mol is None:
        return np.zeros(MORGAN_NBITS, dtype=np.int8)
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, MORGAN_RADIUS, nBits=MORGAN_NBITS)
    return np.array(fp, dtype=np.int8)


def _compute_maccs(mol) -> np.ndarray:
    """MACCS fingerprint (167 bits)."""
    if mol is None:
        return np.zeros(167, dtype=np.int8)
    fp = MACCSkeys.GenMACCSKeys(mol)
    return np.array(fp, dtype=np.int8)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def compute_features_for_smiles(smiles: str) -> np.ndarray | None:
    """
    Compute the full feature vector for a single SMILES string.
    Returns a 1-D numpy array or None if molecule is invalid.
    """
    if not RDKit_AVAILABLE:
        # RDKit not available in this environment (common on CI or minimal installs).
        # Provide a deterministic fallback: a zero-filled feature vector matching
        # the expected length so downstream code can still run (predictions will
        # be based on alerts or fallbacks).
        logger.warning("RDKit not installed; using fallback zero feature vector for '%s'", smiles)
        feature_len = len(get_feature_names())
        return np.zeros(feature_len, dtype=np.float64)

    canonical = canonicalize_smiles(smiles)
    if canonical is None:
        return None
    mol = Chem.MolFromSmiles(canonical)
    if mol is None:
        return None

    desc = _compute_descriptors(mol)
    desc_arr = np.array([desc[n] for n in DESCRIPTOR_NAMES], dtype=np.float64)

    morgan = _compute_morgan(mol)
    maccs = _compute_maccs(mol)

    return np.concatenate([desc_arr, morgan, maccs])


def get_feature_names() -> list[str]:
    """Return ordered list of all feature names."""
    names = list(DESCRIPTOR_NAMES)
    names += [f"Morgan_{i}" for i in range(MORGAN_NBITS)]
    names += [f"MACCS_{i}" for i in range(167)]
    return names


def compute_features_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute features for every molecule in a DataFrame.
    Expects a 'canonical_smiles' column.
    Returns a new DataFrame with feature columns only.
    """
    logger.info(f"Computing molecular features for {len(df)} molecules …")
    feature_names = get_feature_names()
    all_features = []

    for i, smi in enumerate(df["canonical_smiles"]):
        if (i + 1) % 1000 == 0:
            logger.info(f"  Processed {i + 1}/{len(df)}")
        fv = compute_features_for_smiles(smi)
        if fv is None:
            fv = np.full(len(feature_names), np.nan)
        all_features.append(fv)

    feat_df = pd.DataFrame(all_features, columns=feature_names, index=df.index)
    n_invalid = feat_df.isnull().all(axis=1).sum()
    if n_invalid > 0:
        logger.warning(f"  {n_invalid} molecules failed feature computation")

    # Replace NaN/inf in features with column medians
    feat_df = feat_df.replace([np.inf, -np.inf], np.nan)
    feat_df = feat_df.fillna(feat_df.median())
    # If entire column is NaN, fill with 0
    feat_df = feat_df.fillna(0)

    logger.info(f"  Feature matrix shape: {feat_df.shape}")
    return feat_df


def prepare_training_data(
    data_path: str | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str], StandardScaler]:
    """
    Load master_processed.csv, compute features, scale, and return
    (X, y, feature_names, scaler).
    """
    if data_path is None:
        data_path = os.path.join(DATA_DIR, "master_processed.csv")

    logger.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)

    # Compute features
    feat_df = compute_features_dataframe(df)
    feature_names = list(feat_df.columns)

    X = feat_df.values.astype(np.float64)
    y = df["toxicity_class"].values.astype(int)

    # Scale
    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    # Save scaler and feature names
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODEL_DIR, "feature_names.pkl"), "wb") as f:
        pickle.dump(feature_names, f)

    logger.info(f"Saved scaler and feature names to {MODEL_DIR}")
    logger.info(f"X shape: {X.shape}, y shape: {y.shape}")
    logger.info(f"Class distribution: {dict(zip(*np.unique(y, return_counts=True)))}")

    return X, y, feature_names, scaler


# ---------------------------------------------------------------------------
# Standalone entry
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    X, y, names, scaler = prepare_training_data()
    print(f"\nFeature extraction complete!")
    print(f"   Features: {X.shape[1]}")
    print(f"   Samples:  {X.shape[0]}")
    print(f"   Classes:  {np.unique(y)}")
