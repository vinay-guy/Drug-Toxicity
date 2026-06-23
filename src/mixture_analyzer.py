"""
mixture_analyzer.py — Multi-compound chemical mixture toxicity analysis.

Supports 2–10 compounds, predicts individual and combined toxicity,
detects interaction types, and aggregates health risks.
"""

from __future__ import annotations

import os
import sys
import pickle
import warnings
import numpy as np
from dataclasses import dataclass, field

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

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import (
    canonicalize_smiles,
    probability_to_label,
    compute_confidence,
    TOXICITY_LABELS,
    TOXICITY_COLORS,
    MODEL_DIR,
    logger,
)
from alerts import detect_alerts, compute_alert_boosted_probability, AlertReport
from disease_mapper import generate_health_report, HealthReport
from features import compute_features_for_smiles, get_feature_names


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class CompoundResult:
    """Prediction result for a single compound."""
    smiles: str
    canonical_smiles: str
    probability: float
    raw_probability: float
    predicted_class: int
    label: str
    confidence: float
    alert_report: AlertReport | None = None
    health_report: HealthReport | None = None
    pIC50_estimate: float = 0.0
    mol_weight: float = 0.0
    shap_explanation: dict | None = None


@dataclass
class MixtureResult:
    """Combined prediction result for a chemical mixture."""
    components: list[CompoundResult] = field(default_factory=list)
    combined_probability: float = 0.0
    combined_label: str = "UNKNOWN"
    combined_confidence: float = 0.0
    interaction_type: str = "INDEPENDENT"
    interaction_explanation: str = ""
    most_dangerous: CompoundResult | None = None
    combined_health_report: HealthReport | None = None
    danger_level: int = 0  # 1–10


# ---------------------------------------------------------------------------
# Interaction detection rules
# ---------------------------------------------------------------------------
SYNERGY_RULES: list[dict] = [
    {
        "name": "Aromatic + Nitro → Carcinogenic amplification",
        "alert_a": "Benzene Ring",
        "alert_b": "Nitro Group",
        "modifier": 1.35,
        "explanation": "Aromatic compounds combined with nitro groups amplify carcinogenic risk through enhanced metabolic activation of nitroaromatics.",
    },
    {
        "name": "Halogenated solvent + Aldehyde → Liver/CNS synergy",
        "alert_a": "Halogenated Alkyl",
        "alert_b": "Aldehyde",
        "modifier": 1.30,
        "explanation": "Halogenated solvents impair hepatic detoxification, increasing aldehyde-mediated liver damage and CNS depression.",
    },
    {
        "name": "Multiple Aromatic Amines → Blood cancer risk",
        "alert_a": "Aromatic Amine (Primary)",
        "alert_b": "Aromatic Amine (Secondary)",
        "modifier": 1.40,
        "explanation": "Multiple aromatic amines overwhelm N-acetylation detoxification, dramatically increasing bladder and blood cancer risk.",
    },
    {
        "name": "Epoxide + Quinone → Extreme reactivity",
        "alert_a": "Epoxide",
        "alert_b": "Quinone",
        "modifier": 1.50,
        "explanation": "Epoxide alkylation combined with quinone-mediated oxidative stress creates extreme genotoxic and cytotoxic synergy.",
    },
    {
        "name": "Aromatic Amine + Nitro → Enhanced mutagenesis",
        "alert_a": "Aromatic Amine (Primary)",
        "alert_b": "Nitro Group",
        "modifier": 1.35,
        "explanation": "Both share nitroreduction activation pathways, competing for detoxification enzymes and amplifying DNA damage.",
    },
    {
        "name": "Hydrazine + Aldehyde → Hepatotoxic synergy",
        "alert_a": "Hydrazine",
        "alert_b": "Aldehyde",
        "modifier": 1.30,
        "explanation": "Hydrazine-induced glutathione depletion removes the primary defense against aldehyde reactivity in hepatocytes.",
    },
    {
        "name": "PAH + Benzene → Hematotoxic amplification",
        "alert_a": "Polyaromatic Hydrocarbon (3+ fused rings)",
        "alert_b": "Benzene Ring",
        "modifier": 1.25,
        "explanation": "Combined PAH and benzene exposure overwhelms CYP-mediated detoxification, amplifying bone marrow toxicity.",
    },
]


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------
_cached_model = None
_cached_scaler = None
_cached_features = None


def _get_model():
    global _cached_model
    if _cached_model is None:
        path = os.path.join(MODEL_DIR, "best_model.pkl")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    _cached_model = pickle.load(f)
            except (ModuleNotFoundError, ImportError) as e:
                # Fallback for numpy._core.numeric compatibility
                import importlib
                class CompatibilityUnpickler(pickle.Unpickler):
                    def find_class(self, module, name):
                        if module == "numpy._core.numeric":
                            module = "numpy.core.numeric"
                        return super().find_class(module, name)
                
                with open(path, "rb") as f:
                    _cached_model = CompatibilityUnpickler(f).load()
    return _cached_model


def _get_scaler():
    global _cached_scaler
    if _cached_scaler is None:
        path = os.path.join(MODEL_DIR, "scaler.pkl")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    _cached_scaler = pickle.load(f)
            except (ModuleNotFoundError, ImportError):
                class CompatibilityUnpickler(pickle.Unpickler):
                    def find_class(self, module, name):
                        if module == "numpy._core.numeric":
                            module = "numpy.core.numeric"
                        return super().find_class(module, name)
                
                with open(path, "rb") as f:
                    _cached_scaler = CompatibilityUnpickler(f).load()
    return _cached_scaler


def _get_feature_names():
    global _cached_features
    if _cached_features is None:
        path = os.path.join(MODEL_DIR, "feature_names.pkl")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    _cached_features = pickle.load(f)
            except (ModuleNotFoundError, ImportError):
                class CompatibilityUnpickler(pickle.Unpickler):
                    def find_class(self, module, name):
                        if module == "numpy._core.numeric":
                            module = "numpy.core.numeric"
                        return super().find_class(module, name)
                
                with open(path, "rb") as f:
                    _cached_features = CompatibilityUnpickler(f).load()
    return _cached_features


# ---------------------------------------------------------------------------
# Single compound prediction
# ---------------------------------------------------------------------------
def predict_single(smiles: str) -> CompoundResult | None:
    """
    Predict toxicity for a single compound.

    Returns CompoundResult with probability, label, alerts, diseases, etc.
    """
    canonical = canonicalize_smiles(smiles)
    if canonical is None:
        logger.warning(f"Invalid SMILES: {smiles}")
        return None

    model = _get_model()
    scaler = _get_scaler()
    feature_names = _get_feature_names()

    # Compute features
    fv = compute_features_for_smiles(canonical)
    if fv is None:
        logger.warning(f"Cannot compute features for: {canonical}")
        return None

    # Handle NaN/inf
    fv = np.nan_to_num(fv, nan=0.0, posinf=0.0, neginf=0.0)

    # Scale
    if scaler is not None:
        fv_scaled = scaler.transform(fv.reshape(1, -1))
    else:
        fv_scaled = fv.reshape(1, -1)

    # Predict
    if model is not None:
        proba = model.predict_proba(fv_scaled)[0]
        predicted_class = int(model.predict(fv_scaled)[0])
        # Use max probability as toxicity score
        raw_probability = float(proba[predicted_class])
        # Convert to single toxicity probability [0, 1]
        # Weight higher classes more heavily
        weights = np.array([0.0, 0.25, 0.5, 0.75, 1.0])[:len(proba)]
        toxicity_prob = float(np.sum(proba * weights))
    else:
        # Fallback: use alerts-only mode
        raw_probability = 0.5
        toxicity_prob = 0.5
        predicted_class = 2

    # Structural alerts
    alert_report = detect_alerts(canonical)

    # Boost probability with alerts
    final_probability = compute_alert_boosted_probability(toxicity_prob, alert_report)
    final_label = probability_to_label(final_probability)

    # Health report
    health_report = generate_health_report(alert_report.matches)

    # Molecular weight from features
    mol_wt = float(fv[0]) if len(fv) > 0 else 0.0

    # Confidence
    n_features_valid = int(np.sum(~np.isnan(fv) & (fv != 0)))
    confidence = compute_confidence(
        final_probability, alert_report.n_alerts,
        n_features_valid, len(fv),
    )

    # pIC50 estimate (from feature index or basic prediction)
    pIC50_est = round(4.0 + final_probability * 5.0, 2)

    result = CompoundResult(
        smiles=smiles,
        canonical_smiles=canonical,
        probability=round(final_probability, 4),
        raw_probability=round(raw_probability, 4),
        predicted_class=predicted_class,
        label=final_label,
        confidence=confidence,
        alert_report=alert_report,
        health_report=health_report,
        pIC50_estimate=pIC50_est,
        mol_weight=round(mol_wt, 2),
    )

    return result


# ---------------------------------------------------------------------------
# Advanced toxicological escalation logic for mixtures
# ---------------------------------------------------------------------------
def _compute_alert_severity_score(components: list[CompoundResult]) -> tuple[float, str]:
    """
    Compute a bounded, proportional alert-based escalation score for mixtures.

    Improvements over previous implementation:
    - Anchor escalation to the maximum component probability (don't ignore base risk)
    - Use proportional multipliers instead of fixed probability floors
    - Apply multi-toxic and co-occurrence boosts proportionally and bounded by headroom
    - Avoid hard-coded per-mixture thresholds that create unbounded stacking

    Returns (escalated_probability, escalation_explanation)
    """
    ALERT_SEVERITY_WEIGHTS = {
        "Benzene Ring": 0.20,
        "Nitro Group": 0.25,
        "Aromatic Amine (Primary)": 0.22,
        "Aromatic Amine (Secondary)": 0.20,
        "Aldehyde": 0.18,
        "Formaldehyde-like": 0.25,
        "Halogenated Alkyl": 0.18,
        "Polyaromatic Hydrocarbon (3+ fused rings)": 0.25,
        "Reactive α,β-Unsaturated Carbonyl": 0.15,
        "Epoxide": 0.30,
        "Quinone": 0.25,
        "Hydrazine": 0.24,
        "Acyl Halide": 0.30,
        "Nitroso Group": 0.24,
        "Azide": 0.22,
        "Isocyanate": 0.23,
    }

    # Collect alerts and counts
    all_alerts: dict[str, int] = {}
    total_severity_score = 0.0
    toxic_component_count = 0
    distinct_alerts = set()

    for comp in components:
        if comp.alert_report and comp.alert_report.matches:
            for match in comp.alert_report.matches:
                severity_weight = ALERT_SEVERITY_WEIGHTS.get(match.name, 0.15)
                total_severity_score += severity_weight
                distinct_alerts.add(match.name)
                all_alerts[match.name] = all_alerts.get(match.name, 0) + match.count

            if comp.alert_report.n_alerts >= 2:
                toxic_component_count += 1

        # count components with elevated model probability
        if comp.probability >= 0.35:
            toxic_component_count += 1

    # If no alerts at all, no escalation
    if total_severity_score <= 0:
        return 0.0, ""

    # Anchor to component-level probabilities
    max_comp_prob = max((c.probability for c in components), default=0.0)

    # Normalize total severity score by number of components to avoid unbounded sums
    num_components = max(1, len(components))
    normalized_score = total_severity_score / num_components

    # Proportional severity multiplier (bounded)
    # severity_multiplier in [1.0, 1.25] for typical scores
    severity_multiplier = 1.0 + min(normalized_score * 0.5, 0.25)

    # Base escalated probability anchored to max component
    escalated_prob = max_comp_prob * severity_multiplier

    # Absolute cap: allow at most +15 percentage points above max component
    cap = min(max_comp_prob + 0.15, 0.95)
    escalated_prob = min(escalated_prob, cap)

    reasons = []
    reasons.append(f"total_alert_score={total_severity_score:.2f}, normalized={normalized_score:.3f}")

    # Co-occurrence boost: if multiple distinct alert types present, apply small proportional boost
    co_occur_count = len(distinct_alerts)
    if co_occur_count >= 2:
        # proportional boost of headroom (up to 10% of headroom)
        headroom = cap - escalated_prob
        co_boost_frac = min(0.10, 0.03 * co_occur_count)  # small fractional boost
        co_boost = headroom * co_boost_frac
        if co_boost > 0:
            escalated_prob = min(escalated_prob + co_boost, cap)
            reasons.append(f"co_occurrence_boost={co_boost:.3f}")

    # Multi-toxic component boosting: conditional and proportional to remaining headroom
    if toxic_component_count >= 2:
        headroom = cap - escalated_prob
        # smaller proportional boosts than before
        if toxic_component_count == 2:
            boost_frac = 0.06
        else:
            boost_frac = 0.10
        multi_boost = headroom * boost_frac
        if multi_boost > 0:
            escalated_prob = min(escalated_prob + multi_boost, cap)
            reasons.append(f"multi_toxic_boost={multi_boost:.3f}")

    # Final safety: do not exceed a modest absolute escalation above max component (max +15%)
    escalated_prob = min(escalated_prob, cap)

    explanation = "".join(["; ".join(reasons)]) if reasons else ""
    return round(escalated_prob, 4), explanation


# ---------------------------------------------------------------------------
# Interaction detection
# ---------------------------------------------------------------------------
def _detect_interaction(components: list[CompoundResult]) -> tuple[str, float, str]:
    """
    Detect interaction type between mixture components.

    Returns (interaction_type, modifier, explanation).
    """
    # Collect all alert names across components
    all_alerts: dict[int, set[str]] = {}
    for i, comp in enumerate(components):
        if comp.alert_report:
            all_alerts[i] = {m.name for m in comp.alert_report.matches}
        else:
            all_alerts[i] = set()

    # Check synergy rules across component pairs
    best_modifier = 1.0
    best_type = "INDEPENDENT"
    best_explanation = "Components appear to act independently with no significant pharmacological interaction detected."

    for rule in SYNERGY_RULES:
        for i in range(len(components)):
            for j in range(i + 1, len(components)):
                alerts_i = all_alerts.get(i, set())
                alerts_j = all_alerts.get(j, set())

                # Check if alert_a in one component and alert_b in another
                if (
                    (rule["alert_a"] in alerts_i and rule["alert_b"] in alerts_j) or
                    (rule["alert_b"] in alerts_i and rule["alert_a"] in alerts_j)
                ):
                    if rule["modifier"] > best_modifier:
                        best_modifier = rule["modifier"]
                        best_type = "SYNERGISTIC"
                        best_explanation = rule["explanation"]

    # Check for antagonism (protective features vs toxic ones)
    # Simple heuristic: if one compound is non-toxic and another is highly toxic
    probs = [c.probability for c in components]
    if len(probs) >= 2:
        if min(probs) < 0.2 and max(probs) > 0.6:
            if best_type == "INDEPENDENT":
                best_type = "ADDITIVE"
                best_explanation = "Components have contrasting toxicity profiles, resulting in additive (averaged) risk."
                best_modifier = 1.0

    # Check for purely additive (multiple moderate risks)
    moderate_count = sum(1 for p in probs if 0.3 < p < 0.6)
    if moderate_count >= 2 and best_type == "INDEPENDENT":
        best_type = "ADDITIVE"
        best_modifier = 1.1
        best_explanation = "Multiple compounds with moderate toxicity combine additively, slightly increasing overall risk."

    # Multiple toxic components with many alerts
    total_alerts = sum(comp.alert_report.n_alerts if comp.alert_report else 0 for comp in components)
    if total_alerts >= 5 and best_type == "INDEPENDENT":
        best_type = "SYNERGISTIC"
        best_modifier = 1.2
        best_explanation = "High total structural alert count across components suggests potential synergistic toxicity through enzyme competition."

    return best_type, best_modifier, best_explanation


# ---------------------------------------------------------------------------
# Mixture analysis
# ---------------------------------------------------------------------------
def analyze_mixture(smiles_list: list[str]) -> MixtureResult | None:
    """
    Analyze a chemical mixture of 2–10 compounds.

    Parameters
    ----------
    smiles_list : list of SMILES strings

    Returns
    -------
    MixtureResult with combined toxicity, interaction type, and health risks.
    """
    if not smiles_list or len(smiles_list) < 2:
        logger.warning("Mixture analysis requires at least 2 compounds")
        return None

    if len(smiles_list) > 10:
        smiles_list = smiles_list[:10]
        logger.warning("Truncated mixture to 10 compounds")

    # Predict each component
    components: list[CompoundResult] = []
    for smi in smiles_list:
        result = predict_single(smi)
        if result is not None:
            components.append(result)

    if len(components) < 2:
        logger.warning("Fewer than 2 valid compounds in mixture")
        return None

    # Detect interaction
    interaction_type, modifier, interaction_explanation = _detect_interaction(components)

    # Combine probabilities
    individual_probs = [c.probability for c in components]

    if interaction_type == "SYNERGISTIC":
        # Synergistic: P_combined = 1 - ∏(1 - Pi) * modifier
        combined = 1 - np.prod([1 - p for p in individual_probs])
        combined *= modifier
    elif interaction_type == "ANTAGONISTIC":
        # Antagonistic: average weighted toward lower risk
        combined = np.mean(individual_probs) * 0.8
    elif interaction_type == "ADDITIVE":
        # Additive: weighted average with boost
        combined = np.mean(individual_probs) * modifier
    else:
        # Independent: maximum risk component
        combined = max(individual_probs)

    combined = min(round(combined, 4), 0.999)

    # Apply advanced toxicological escalation logic
    escalated_prob, escalation_explanation = _compute_alert_severity_score(components)
    
    # Use escalated probability if it's higher than the combined probability
    if escalated_prob > combined:
        combined = escalated_prob
        # Enhance interaction explanation with escalation details
        if escalation_explanation:
            interaction_explanation = interaction_explanation + " " + escalation_explanation

    # Most dangerous component
    most_dangerous = max(components, key=lambda c: c.probability)

    # Combined confidence
    individual_confidences = [c.confidence for c in components]
    combined_confidence = round(np.mean(individual_confidences) * 0.9, 3)  # slight penalty

    # Aggregate health report
    all_alert_matches = []
    for comp in components:
        if comp.alert_report:
            all_alert_matches.extend(comp.alert_report.matches)
    combined_health = generate_health_report(all_alert_matches)

    # Danger level (1-10)
    danger_level = min(10, max(1, int(combined * 10) + len(all_alert_matches)))

    result = MixtureResult(
        components=components,
        combined_probability=combined,
        combined_label=probability_to_label(combined),
        combined_confidence=combined_confidence,
        interaction_type=interaction_type,
        interaction_explanation=interaction_explanation,
        most_dangerous=most_dangerous,
        combined_health_report=combined_health,
        danger_level=danger_level,
    )

    return result
