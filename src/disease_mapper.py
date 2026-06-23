"""
disease_mapper.py — Maps structural alerts and molecular features to
predicted diseases, organ toxicity risks, and health outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class DiseaseRisk:
    """A predicted disease risk."""
    disease: str
    probability: float  # 0–1
    severity: str       # LOW / MODERATE / HIGH / CRITICAL
    related_alerts: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class OrganRisk:
    """Risk assessment for a specific organ."""
    organ: str
    risk_score: float   # 0–100
    risk_level: str     # LOW / MODERATE / HIGH / CRITICAL
    contributing_alerts: list[str] = field(default_factory=list)


@dataclass
class HealthReport:
    """Full health risk report."""
    diseases: list[DiseaseRisk] = field(default_factory=list)
    organ_risks: list[OrganRisk] = field(default_factory=list)
    summary: str = ""

    @property
    def top_diseases(self) -> list[DiseaseRisk]:
        return sorted(self.diseases, key=lambda d: d.probability, reverse=True)[:5]

    @property
    def organ_risk_dict(self) -> dict[str, float]:
        return {o.organ: o.risk_score for o in self.organ_risks}


# ---------------------------------------------------------------------------
# Alert → Disease mapping
# ---------------------------------------------------------------------------
ALERT_DISEASE_MAP: dict[str, list[dict]] = {
    "Benzene Ring": [
        {"disease": "Leukemia (AML)", "base_prob": 0.45, "severity": "HIGH",
         "description": "Chronic benzene exposure is an established cause of acute myeloid leukemia"},
        {"disease": "Aplastic Anemia", "base_prob": 0.35, "severity": "HIGH",
         "description": "Benzene metabolites suppress bone marrow function"},
        {"disease": "Myelodysplastic Syndrome", "base_prob": 0.30, "severity": "MODERATE",
         "description": "Benzene-induced clonal hematopoietic disorder"},
    ],
    "Nitro Group": [
        {"disease": "Methemoglobinemia", "base_prob": 0.55, "severity": "HIGH",
         "description": "Nitro reduction products oxidize hemoglobin iron to Fe³⁺"},
        {"disease": "Liver Cancer (HCC)", "base_prob": 0.40, "severity": "HIGH",
         "description": "Nitroreduction generates DNA-reactive hydroxylamine metabolites"},
        {"disease": "Contact Dermatitis", "base_prob": 0.25, "severity": "MODERATE",
         "description": "Nitroaromatic compounds are common skin sensitizers"},
    ],
    "Aromatic Amine (Primary)": [
        {"disease": "Bladder Cancer", "base_prob": 0.55, "severity": "CRITICAL",
         "description": "Aromatic amines are classic bladder carcinogens (established since 1954)"},
        {"disease": "Hemolytic Anemia", "base_prob": 0.30, "severity": "HIGH",
         "description": "N-hydroxylamine metabolites damage red blood cell membranes"},
        {"disease": "Liver Cancer", "base_prob": 0.35, "severity": "HIGH",
         "description": "Hepatic N-oxidation generates DNA-reactive electrophiles"},
    ],
    "Aromatic Amine (Secondary)": [
        {"disease": "Bladder Cancer", "base_prob": 0.45, "severity": "HIGH",
         "description": "Secondary aromatic amines share carcinogenic activation pathways"},
        {"disease": "Hemolytic Anemia", "base_prob": 0.25, "severity": "MODERATE",
         "description": "Oxidative metabolites damage erythrocyte hemoglobin"},
    ],
    "Aldehyde": [
        {"disease": "Respiratory Irritation", "base_prob": 0.50, "severity": "MODERATE",
         "description": "Aldehydes react with airway epithelial proteins"},
        {"disease": "Skin Sensitization", "base_prob": 0.40, "severity": "MODERATE",
         "description": "Protein-aldehyde hapten formation triggers immune response"},
        {"disease": "Asthma (occupational)", "base_prob": 0.30, "severity": "MODERATE",
         "description": "Airway inflammation from aldehyde-protein conjugates"},
    ],
    "Formaldehyde-like": [
        {"disease": "Nasopharyngeal Cancer", "base_prob": 0.50, "severity": "CRITICAL",
         "description": "IARC Group 1 carcinogen — causes nasal squamous cell carcinoma"},
        {"disease": "Respiratory Toxicity", "base_prob": 0.60, "severity": "HIGH",
         "description": "Severe irritation and DNA-protein cross-links in respiratory tract"},
        {"disease": "Leukemia", "base_prob": 0.30, "severity": "HIGH",
         "description": "Epidemiological evidence links formaldehyde to myeloid leukemia"},
    ],
    "Halogenated Alkyl": [
        {"disease": "CNS Depression", "base_prob": 0.50, "severity": "HIGH",
         "description": "Halogenated solvents are potent central nervous system depressants"},
        {"disease": "Liver Necrosis", "base_prob": 0.45, "severity": "HIGH",
         "description": "CYP2E1 metabolism generates hepatotoxic trichloromethyl radicals"},
        {"disease": "Kidney Toxicity", "base_prob": 0.35, "severity": "MODERATE",
         "description": "Renal proximal tubule damage from glutathione conjugate metabolites"},
        {"disease": "Cardiac Arrhythmia", "base_prob": 0.25, "severity": "HIGH",
         "description": "Myocardial sensitization to catecholamines"},
    ],
    "Polyaromatic Hydrocarbon (3+ fused rings)": [
        {"disease": "Lung Cancer", "base_prob": 0.55, "severity": "CRITICAL",
         "description": "PAH diol-epoxides form bulky DNA adducts in lung epithelium"},
        {"disease": "Skin Cancer", "base_prob": 0.45, "severity": "HIGH",
         "description": "Topical PAH exposure induces squamous cell carcinoma"},
        {"disease": "Bladder Cancer", "base_prob": 0.30, "severity": "HIGH",
         "description": "Urinary excretion of PAH metabolites damages urothelium"},
    ],
    "Reactive α,β-Unsaturated Carbonyl": [
        {"disease": "Allergic Contact Dermatitis", "base_prob": 0.45, "severity": "MODERATE",
         "description": "Michael acceptors haptenize skin proteins triggering T-cell response"},
        {"disease": "Hepatotoxicity", "base_prob": 0.35, "severity": "MODERATE",
         "description": "GSH depletion and mitochondrial dysfunction in hepatocytes"},
    ],
    "Epoxide": [
        {"disease": "Mutagenicity", "base_prob": 0.65, "severity": "CRITICAL",
         "description": "Epoxide ring opens to alkylate DNA bases, especially guanine N7"},
        {"disease": "Carcinogenicity", "base_prob": 0.55, "severity": "CRITICAL",
         "description": "Covalent DNA adducts cause point mutations and chromosomal aberrations"},
        {"disease": "Skin Sensitization", "base_prob": 0.40, "severity": "MODERATE",
         "description": "Protein hapten formation via epoxide ring-opening"},
    ],
    "Quinone": [
        {"disease": "Oxidative Hemolysis", "base_prob": 0.45, "severity": "HIGH",
         "description": "Redox cycling depletes erythrocyte GSH and damages membranes"},
        {"disease": "Hepatotoxicity", "base_prob": 0.40, "severity": "HIGH",
         "description": "Oxidative stress and protein arylation in hepatocytes"},
        {"disease": "Nephrotoxicity", "base_prob": 0.30, "severity": "MODERATE",
         "description": "Renal tubular damage from quinone-thioether conjugates"},
    ],
    "Hydrazine": [
        {"disease": "Hepatotoxicity", "base_prob": 0.55, "severity": "HIGH",
         "description": "Acyl radical generation causes centrilobular hepatic necrosis"},
        {"disease": "Lupus-like Syndrome", "base_prob": 0.35, "severity": "MODERATE",
         "description": "Drug-induced lupus via hydrazine metabolites (e.g., isoniazid)"},
        {"disease": "Liver Cancer", "base_prob": 0.35, "severity": "HIGH",
         "description": "Methylation of DNA by diazomethane metabolites"},
    ],
    "Acyl Halide": [
        {"disease": "Severe Chemical Burns", "base_prob": 0.70, "severity": "CRITICAL",
         "description": "Immediate acylation of tissue proteins causes necrosis"},
        {"disease": "Respiratory Failure", "base_prob": 0.55, "severity": "CRITICAL",
         "description": "Inhalation causes pulmonary edema and chemical pneumonitis"},
    ],
    "Nitroso Group": [
        {"disease": "Liver Cancer", "base_prob": 0.50, "severity": "HIGH",
         "description": "N-nitroso compounds are potent hepatocarcinogens"},
        {"disease": "Esophageal Cancer", "base_prob": 0.35, "severity": "HIGH",
         "description": "GI tract exposure to nitrosamines linked to esophageal SCC"},
    ],
    "Azide": [
        {"disease": "Metabolic Acidosis", "base_prob": 0.50, "severity": "HIGH",
         "description": "Cytochrome oxidase inhibition shifts metabolism to anaerobic glycolysis"},
        {"disease": "Cardiovascular Collapse", "base_prob": 0.40, "severity": "CRITICAL",
         "description": "Profound hypotension from mitochondrial ATP depletion"},
    ],
    "Isocyanate": [
        {"disease": "Occupational Asthma", "base_prob": 0.60, "severity": "HIGH",
         "description": "Isocyanates are the leading cause of occupational asthma worldwide"},
        {"disease": "Hypersensitivity Pneumonitis", "base_prob": 0.40, "severity": "HIGH",
         "description": "IgG-mediated lung inflammation from inhaled isocyanate-protein conjugates"},
    ],
}

# ---------------------------------------------------------------------------
# Alert → Organ mapping
# ---------------------------------------------------------------------------
ALERT_ORGAN_MAP: dict[str, dict[str, float]] = {
    "Benzene Ring":          {"Blood": 70, "Bone Marrow": 75, "Liver": 30, "Immune System": 40},
    "Nitro Group":           {"Blood": 60, "Liver": 65, "Skin": 35, "Kidneys": 30},
    "Aromatic Amine (Primary)":   {"Bladder": 75, "Blood": 55, "Liver": 60},
    "Aromatic Amine (Secondary)": {"Bladder": 60, "Blood": 45, "Liver": 50},
    "Aldehyde":              {"Lungs": 55, "Skin": 50, "Eyes": 45},
    "Formaldehyde-like":     {"Lungs": 75, "Nasal Cavity": 70, "Blood": 40},
    "Halogenated Alkyl":     {"Liver": 70, "Brain": 65, "Kidneys": 50, "Heart": 40},
    "Polyaromatic Hydrocarbon (3+ fused rings)": {"Lungs": 70, "Skin": 60, "Bladder": 45},
    "Reactive α,β-Unsaturated Carbonyl": {"Skin": 55, "Liver": 45, "GI Tract": 35},
    "Epoxide":               {"DNA/Genome": 80, "Liver": 50, "Skin": 45, "Lungs": 40},
    "Quinone":               {"Blood": 60, "Liver": 55, "Kidneys": 45},
    "Hydrazine":             {"Liver": 75, "Immune System": 45, "Blood": 35},
    "Acyl Halide":           {"Skin": 80, "Lungs": 75, "Eyes": 70, "GI Tract": 60},
    "Nitroso Group":         {"Liver": 70, "GI Tract": 55},
    "Azide":                 {"Heart": 65, "Brain": 60, "Mitochondria": 70},
    "Isocyanate":            {"Lungs": 75, "Skin": 50, "Immune System": 55},
}

# Full list of tracked organs
ALL_ORGANS = [
    "Liver", "Kidneys", "Heart", "Brain", "Lungs", "Blood",
    "Skin", "GI Tract", "Bladder", "Bone Marrow", "Eyes",
    "Immune System", "Nasal Cavity", "DNA/Genome", "Mitochondria",
]


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------
def predict_diseases(alert_matches: list) -> list[DiseaseRisk]:
    """
    Given a list of AlertMatch objects, return predicted diseases.
    """
    disease_dict: dict[str, DiseaseRisk] = {}

    for match in alert_matches:
        entries = ALERT_DISEASE_MAP.get(match.name, [])
        for entry in entries:
            name = entry["disease"]
            # Scale probability by match count (diminishing)
            scaled_prob = min(entry["base_prob"] * (1 + 0.15 * (match.count - 1)), 0.95)

            if name in disease_dict:
                # Combine probabilities: P = 1 - (1-Pa)(1-Pb)
                existing = disease_dict[name]
                combined = 1 - (1 - existing.probability) * (1 - scaled_prob)
                existing.probability = round(min(combined, 0.95), 3)
                if match.name not in existing.related_alerts:
                    existing.related_alerts.append(match.name)
                # Upgrade severity
                if _severity_rank(entry["severity"]) > _severity_rank(existing.severity):
                    existing.severity = entry["severity"]
            else:
                disease_dict[name] = DiseaseRisk(
                    disease=name,
                    probability=round(scaled_prob, 3),
                    severity=entry["severity"],
                    related_alerts=[match.name],
                    description=entry["description"],
                )

    return sorted(disease_dict.values(), key=lambda d: d.probability, reverse=True)


def predict_organ_risks(alert_matches: list) -> list[OrganRisk]:
    """
    Compute risk scores for each organ based on alert matches.
    """
    organ_scores: dict[str, float] = {organ: 0.0 for organ in ALL_ORGANS}
    organ_alerts: dict[str, list[str]] = {organ: [] for organ in ALL_ORGANS}

    for match in alert_matches:
        organ_map = ALERT_ORGAN_MAP.get(match.name, {})
        for organ, score in organ_map.items():
            if organ in organ_scores:
                # Combine with diminishing returns
                scaled = score * (1 + 0.1 * (match.count - 1))
                organ_scores[organ] = min(
                    100, organ_scores[organ] + scaled * (1 - organ_scores[organ] / 100)
                )
                if match.name not in organ_alerts[organ]:
                    organ_alerts[organ].append(match.name)

    results = []
    for organ in ALL_ORGANS:
        score = round(organ_scores[organ], 1)
        if score > 0:
            results.append(OrganRisk(
                organ=organ,
                risk_score=score,
                risk_level=_score_to_level(score),
                contributing_alerts=organ_alerts[organ],
            ))

    return sorted(results, key=lambda o: o.risk_score, reverse=True)


def generate_health_report(alert_matches: list) -> HealthReport:
    """
    Generate a comprehensive health risk report from structural alerts.
    """
    diseases = predict_diseases(alert_matches)
    organ_risks = predict_organ_risks(alert_matches)

    if not diseases:
        summary = "No significant disease risks were identified based on structural analysis."
    else:
        top3 = diseases[:3]
        disease_strs = [f"{d.disease} ({d.probability:.0%})" for d in top3]
        summary = f"Top predicted health risks: {', '.join(disease_strs)}."
        if organ_risks:
            top_organs = [o.organ for o in organ_risks[:3]]
            summary += f" Primary organs at risk: {', '.join(top_organs)}."

    return HealthReport(
        diseases=diseases,
        organ_risks=organ_risks,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _severity_rank(s: str) -> int:
    return {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}.get(s, 0)


def _score_to_level(score: float) -> str:
    if score >= 70:
        return "CRITICAL"
    elif score >= 50:
        return "HIGH"
    elif score >= 25:
        return "MODERATE"
    else:
        return "LOW"
