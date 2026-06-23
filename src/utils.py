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
import re
import logging


try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Draw
    RDKit_AVAILABLE = True
except Exception:
    Chem = None
    Descriptors = None
    Draw = None
    RDKit_AVAILABLE = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("ToxPredict")

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")

for _d in (DATA_DIR, MODEL_DIR, OUTPUT_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# Toxicity label scheme
# ---------------------------------------------------------------------------
TOXICITY_LABELS = {
    0: "NON-TOXIC",
    1: "MODERATE",
    2: "TOXIC",
    3: "HIGH RISK",
    4: "CRITICAL",
}

TOXICITY_COLORS = {
    "NON-TOXIC": "#22c55e",
    "MODERATE":  "#eab308",
    "TOXIC":     "#f97316",
    "HIGH RISK": "#ef4444",
    "CRITICAL":  "#dc2626",
}

TOXICITY_EMOJIS = {
    "NON-TOXIC": "✅",
    "MODERATE":  "⚠️",
    "TOXIC":     "🔶",
    "HIGH RISK": "🔴",
    "CRITICAL":  "☠️",
}

# ---------------------------------------------------------------------------
# Common compound name → SMILES dictionary
# ---------------------------------------------------------------------------
COMMON_COMPOUNDS: dict[str, str] = {
    # --- Solvents & common chemicals ---
    "benzene":           "c1ccccc1",
    "toluene":           "Cc1ccccc1",
    "ethanol":           "CCO",
    "methanol":          "CO",
    "acetone":           "CC(C)=O",
    "formaldehyde":      "C=O",
    "acetaldehyde":      "CC=O",
    "chloroform":        "ClC(Cl)Cl",
    "acetic acid":       "CC(O)=O",
    "phenol":            "Oc1ccccc1",
    "aniline":           "Nc1ccccc1",
    "naphthalene":       "c1ccc2ccccc2c1",
    "anthracene":        "c1ccc2cc3ccccc3cc2c1",
    "pyrene":            "c1cc2ccc3cccc4ccc(c1)c2c34",
    "nitrobenzene":      "[O-][N+](=O)c1ccccc1",
    "tnt":               "Cc1c([N+]([O-])=O)cc([N+]([O-])=O)cc1[N+]([O-])=O",
    "aspirin":           "CC(=O)Oc1ccccc1C(O)=O",
    "caffeine":          "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
    "paracetamol":       "CC(=O)Nc1ccc(O)cc1",
    "acetaminophen":     "CC(=O)Nc1ccc(O)cc1",
    "ibuprofen":         "CC(C)Cc1ccc(C(C)C(O)=O)cc1",
    "nicotine":          "CN1CCC[C@H]1c1cccnc1",
    "morphine":          "CN1CC[C@]23c4c5ccc(O)c4O[C@H]2[C@@H](O)C=C[C@H]3[C@@H]1C5",
    "glucose":           "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
    "water":             "O",
    "ethylene oxide":    "C1CO1",
    "vinyl chloride":    "C=CCl",
    "carbon tetrachloride": "ClC(Cl)(Cl)Cl",
    "dichloromethane":   "ClCCl",
    "dimethylformamide": "CN(C)C=O",
    "dmso":              "CS(C)=O",
    "hydrogen peroxide": "OO",
    "ammonia":           "N",
    "hydrazine":         "NN",
    "cyclohexane":       "C1CCCCC1",
    "diethyl ether":     "CCOCC",
    "thf":               "C1CCOC1",
    "pyridine":          "c1ccncc1",
    "acrolein":          "C=CC=O",
    "styrene":           "C=Cc1ccccc1",
    "bisphenol a":       "CC(C)(c1ccc(O)cc1)c1ccc(O)cc1",
    "ddt":               "ClC(Cl)=C(c1ccc(Cl)cc1)c1ccc(Cl)cc1",
    # --- Drugs ---
    "metformin":         "CN(C)C(=N)NC(=N)N",
    "amoxicillin":       "CC1(C)S[C@@H]2[C@H](NC(=O)[C@@H](N)c3ccc(O)cc3)C(=O)N2[C@@H]1C(O)=O",
    "ciprofloxacin":     "O=C(O)c1cn(C2CC2)c2cc(N3CCNCC3)c(F)cc2c1=O",
    "doxorubicin":       "COc1cccc2c1C(=O)c1c(O)c3c(c(O)c1C2=O)C[C@@](O)(C(=O)CO)C[C@@H]3O[C@H]1C[C@H](N)[C@H](O)[C@H](C)O1",
    "warfarin":          "CC(=O)C[C@@H](c1ccccc1)c1c(O)c2ccccc2oc1=O",
    "diazepam":          "CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21",
    "penicillin":        "CC1(C)S[C@@H]2[C@H](NC(=O)Cc3ccccc3)C(=O)N2[C@@H]1C(O)=O",
    "erythromycin":      "CC[C@@H]1OC(=O)[C@H](C)[C@@H](O[C@H]2C[C@@](C)(OC)[C@@H](O)[C@H](C)O2)[C@H](C)[C@@H](O[C@@H]2O[C@H](C)C[C@@H](N(C)C)[C@@H]2O)[C@](C)(O)C[C@@H](C)C(=O)[C@H](C)[C@@H](O)[C@]1(C)O",
    "methotrexate":      "CN(Cc1cnc2nc(N)nc(N)c2n1)c1ccc(C(=O)N[C@@H](CCC(O)=O)C(O)=O)cc1",
    "tamoxifen":         "CCC(/=C(\\c1ccccc1)c1ccc(OCCN(C)C)cc1)c1ccccc1",
    "omeprazole":        "COc1ccc2[nH]c(S(=O)Cc3ncc(C)c(OC)c3C)nc2c1",
    "losartan":          "CCCCc1nc(Cl)c(CO)n1Cc1ccc(-c2ccccc2-c2nn[nH]n2)cc1",
}


# ---------------------------------------------------------------------------
# SMILES utilities
# ---------------------------------------------------------------------------
def canonicalize_smiles(smi: str) -> str | None:
    """Return canonical SMILES or None if invalid."""
    if not smi or not isinstance(smi, str):
        return None
    smi = smi.strip().replace("\n", "").replace("\r", "")
    if RDKit_AVAILABLE and Chem is not None:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            return None
        return Chem.MolToSmiles(mol)
    # RDKit unavailable: return the trimmed input as best-effort fallback
    return smi


def is_valid_smiles(smi: str) -> bool:
    """Check whether a SMILES string is valid."""
    if RDKit_AVAILABLE and Chem is not None:
        return canonicalize_smiles(smi) is not None
    # Without RDKit we cannot robustly validate; assume non-empty string is OK
    return bool(smi and isinstance(smi, str))


def smiles_to_mol(smi: str):
    """Convert SMILES to RDKit Mol object."""
    if not smi:
        return None
    smi = smi.strip().replace("\n", "").replace("\r", "")
    if RDKit_AVAILABLE and Chem is not None:
        return Chem.MolFromSmiles(smi)
    return None


def mol_to_image(mol, size=(350, 350)):
    """Generate a 2‑D image of a molecule."""
    if mol is None:
        return None
    if RDKit_AVAILABLE and Draw is not None:
        return Draw.MolToImage(mol, size=size)
    return None


# ---------------------------------------------------------------------------
# Compound name resolution
# ---------------------------------------------------------------------------
def resolve_compound_name(name: str) -> str | None:
    """
    Resolve a compound name to a SMILES string.
    1.  Check local dictionary (case‑insensitive).
    2.  (Optional) Query PubChem PUG REST.
    Returns canonical SMILES or None.
    """
    if not name or not isinstance(name, str):
        return None

    key = name.strip().lower()

    # Local lookup
    if key in COMMON_COMPOUNDS:
        return canonicalize_smiles(COMMON_COMPOUNDS[key])

    # Try PubChem REST (best-effort, no hard dependency on network)
    try:
        import urllib.request, json
        url = (
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
            f"name/{key}/property/CanonicalSMILES/JSON"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "ToxPredict/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            smi = data["PropertyTable"]["Properties"][0]["CanonicalSMILES"]
            return canonicalize_smiles(smi)
    except Exception:
        pass

    return None


def parse_input(text: str) -> list[str]:
    """
    Parse user input into a list of SMILES strings.

    Supports:
      - Single SMILES
      - Compound name
      - Dot‑separated mixture  (SMILES1.SMILES2)
      - Comma‑separated list
    """
    if not text or not isinstance(text, str):
        return []

    text = text.strip()
    results: list[str] = []

    # Check if it's a dot-separated mixture of SMILES
    if "." in text:
        # Try parsing entire string as one SMILES first
        canon = canonicalize_smiles(text)
        if canon and "." in canon:
            # It's a real mixture SMILES (salts / mixtures)
            parts = canon.split(".")
            for p in parts:
                c = canonicalize_smiles(p)
                if c:
                    results.append(c)
            if results:
                return results

    # Comma-separated
    if "," in text:
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            c = canonicalize_smiles(part)
            if c:
                results.append(c)
            else:
                c = resolve_compound_name(part)
                if c:
                    results.append(c)
        return results

    # Single entry — try SMILES first, then name
    canon = canonicalize_smiles(text)
    if canon:
        return [canon]

    resolved = resolve_compound_name(text)
    if resolved:
        return [resolved]

    return []


# ---------------------------------------------------------------------------
# Toxicity helpers
# ---------------------------------------------------------------------------
def probability_to_label(prob: float) -> str:
    """Map a toxicity probability [0, 1] to a label string."""
    if prob < 0.2:
        return "NON-TOXIC"
    elif prob < 0.4:
        return "MODERATE"
    elif prob < 0.6:
        return "TOXIC"
    elif prob < 0.8:
        return "HIGH RISK"
    else:
        return "CRITICAL"


def class_to_label(cls: int) -> str:
    """Map a predicted class index to a label string."""
    return TOXICITY_LABELS.get(int(cls), "UNKNOWN")


def compute_confidence(
    model_prob: float,
    n_alerts: int,
    n_features_available: int,
    total_features: int,
) -> float:
    """
    Compute a confidence score in [0, 1].

    Components:
      - Model certainty: max(proba) distance from random baseline
      - Feature coverage: fraction of valid features
      - Alert agreement: whether alerts support model direction
    """
    certainty = min(abs(model_prob - 0.5) * 2, 1.0)
    coverage = min(n_features_available / max(total_features, 1), 1.0)
    alert_boost = min(n_alerts * 0.05, 0.2) if model_prob > 0.5 else 0.0
    confidence = 0.5 * certainty + 0.3 * coverage + 0.2 * alert_boost
    return round(min(max(confidence, 0.0), 1.0), 3)


def compute_pIC50(ic50_nM: float) -> float | None:
    """Compute pIC50 from IC50 in nanomolar: pIC50 = −log10(IC50 × 1e‑9)."""
    if ic50_nM is None or ic50_nM <= 0:
        return None
    return -np.log10(ic50_nM * 1e-9)


def estimate_pIC50_from_assays(assay_hits: int, total_assays: int = 12) -> float:
    """
    Surrogate pIC50 estimate from Tox21 assay hit ratio.
    Maps [0, 1] hit ratio → [4.0, 9.0] pIC50 range.
    """
    ratio = assay_hits / max(total_assays, 1)
    return round(4.0 + ratio * 5.0, 3)
