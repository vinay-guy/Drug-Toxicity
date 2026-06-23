"""
alerts.py — SMARTS‑based structural alert detection for toxic substructures.

Defines 10+ toxic substructure patterns, severity scoring, probability
override logic, and human‑readable explanation generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
try:
    from rdkit import Chem
    RDKit_AVAILABLE = True
except Exception:
    Chem = None
    RDKit_AVAILABLE = False

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class AlertMatch:
    """A single structural alert match."""
    name: str
    smarts: str
    severity: int          # 1–5  (1 = low, 5 = critical)
    severity_label: str    # human string
    probability_boost: float
    description: str
    mechanism: str
    count: int = 1         # number of matches in molecule


@dataclass
class AlertReport:
    """Aggregated alert report for a molecule."""
    matches: list[AlertMatch] = field(default_factory=list)
    total_severity: int = 0
    override_probability: float | None = None
    explanation: str = ""

    @property
    def n_alerts(self) -> int:
        return len(self.matches)

    @property
    def has_critical(self) -> bool:
        return any(m.severity >= 4 for m in self.matches)

    @property
    def max_severity(self) -> int:
        return max((m.severity for m in self.matches), default=0)


# ---------------------------------------------------------------------------
# Structural alerts definitions
# ---------------------------------------------------------------------------
STRUCTURAL_ALERTS: list[dict] = [
    {
        "name": "Benzene Ring",
        "smarts": "c1ccccc1",
        "severity": 2,
        "severity_label": "MODERATE",
        "probability_boost": 0.15,
        "description": "Aromatic benzene ring — associated with hematotoxicity",
        "mechanism": "Metabolized to benzene oxide and muconaldehyde, causing bone marrow suppression",
    },
    {
        "name": "Nitro Group",
        "smarts": "[N+](=O)[O-]",
        "severity": 4,
        "severity_label": "HIGH",
        "probability_boost": 0.25,
        "description": "Nitro functional group — strong genotoxic and mutagenic alert",
        "mechanism": "Reduced to nitroso and hydroxylamine intermediates that form DNA adducts",
    },
    {
        "name": "Aromatic Amine (Primary)",
        "smarts": "[c]-[NH2]",
        "severity": 4,
        "severity_label": "HIGH",
        "probability_boost": 0.25,
        "description": "Primary aromatic amine — carcinogenic structural alert",
        "mechanism": "N-hydroxylation followed by esterification generates reactive nitrenium ions",
    },
    {
        "name": "Aromatic Amine (Secondary)",
        "smarts": "[c]-[NH]-[c]",
        "severity": 4,
        "severity_label": "HIGH",
        "probability_boost": 0.22,
        "description": "Secondary aromatic amine — potential carcinogen",
        "mechanism": "Oxidative activation forms electrophilic metabolites that bind to DNA",
    },
    {
        "name": "Aldehyde",
        "smarts": "[CX3H1](=O)[#6]",
        "severity": 3,
        "severity_label": "MODERATE",
        "probability_boost": 0.15,
        "description": "Aldehyde group — reactive electrophile",
        "mechanism": "Forms Schiff bases with proteins and DNA, causing cross-linking",
    },
    {
        "name": "Formaldehyde-like",
        "smarts": "[CH2]=O",
        "severity": 4,
        "severity_label": "HIGH",
        "probability_boost": 0.25,
        "description": "Formaldehyde-like structure — known carcinogen (IARC Group 1)",
        "mechanism": "Highly reactive, forms DNA-protein cross-links in nasal epithelium",
    },
    {
        "name": "Halogenated Alkyl",
        "smarts": "[CX4][F,Cl,Br,I]",
        "severity": 3,
        "severity_label": "HIGH",
        "probability_boost": 0.20,
        "description": "Halogenated alkyl group — associated with liver and CNS toxicity",
        "mechanism": "Metabolic dehalogenation generates reactive free radicals and phosgene",
    },
    {
        "name": "Polyaromatic Hydrocarbon (3+ fused rings)",
        "smarts": "c1ccc2cc3ccccc3cc2c1",
        "severity": 4,
        "severity_label": "HIGH",
        "probability_boost": 0.25,
        "description": "Polyaromatic hydrocarbon (PAH) — strong carcinogenic alert",
        "mechanism": "Metabolic activation by CYP enzymes forms diol-epoxides that intercalate DNA",
    },
    {
        "name": "Reactive α,β-Unsaturated Carbonyl",
        "smarts": "[#6]=[#6]-[#6]=O",
        "severity": 3,
        "severity_label": "MODERATE",
        "probability_boost": 0.18,
        "description": "Michael acceptor — reactive electrophile causing protein alkylation",
        "mechanism": "Undergoes 1,4-conjugate addition with cellular nucleophiles (GSH, proteins)",
    },
    {
        "name": "Epoxide",
        "smarts": "C1OC1",
        "severity": 5,
        "severity_label": "CRITICAL",
        "probability_boost": 0.30,
        "description": "Epoxide ring — highly reactive mutagen",
        "mechanism": "Ring-opening by DNA nucleophiles creates covalent adducts; potent mutagen",
    },
    {
        "name": "Quinone",
        "smarts": "O=C1C=CC(=O)C=C1",
        "severity": 4,
        "severity_label": "HIGH",
        "probability_boost": 0.25,
        "description": "Quinone — causes oxidative stress and redox cycling",
        "mechanism": "One-electron reduction generates semiquinone radicals producing superoxide",
    },
    {
        "name": "Hydrazine",
        "smarts": "[NX3]-[NX3]",
        "severity": 4,
        "severity_label": "HIGH",
        "probability_boost": 0.25,
        "description": "Hydrazine moiety — hepatotoxic and carcinogenic",
        "mechanism": "Oxidized to diazene intermediates; generates reactive acyl radicals in liver",
    },
    {
        "name": "Acyl Halide",
        "smarts": "[CX3](=O)[F,Cl,Br,I]",
        "severity": 5,
        "severity_label": "CRITICAL",
        "probability_boost": 0.30,
        "description": "Acyl halide — extremely reactive, corrosive",
        "mechanism": "Immediate acylation of proteins and nucleic acids; severe tissue damage",
    },
    {
        "name": "Nitroso Group",
        "smarts": "[NX2]=O",
        "severity": 4,
        "severity_label": "HIGH",
        "probability_boost": 0.25,
        "description": "Nitroso group — potent alkylating agent",
        "mechanism": "Tautomerizes to diazo compounds that alkylate DNA bases",
    },
    {
        "name": "Azide",
        "smarts": "[N-]=[N+]=N",
        "severity": 4,
        "severity_label": "HIGH",
        "probability_boost": 0.22,
        "description": "Organic azide — cytochrome oxidase inhibitor",
        "mechanism": "Binds to Fe³⁺ in cytochrome c oxidase, blocking mitochondrial respiration",
    },
    {
        "name": "Isocyanate",
        "smarts": "[NX2]=C=O",
        "severity": 4,
        "severity_label": "HIGH",
        "probability_boost": 0.25,
        "description": "Isocyanate — potent respiratory sensitizer",
        "mechanism": "Reacts with NH/OH groups in proteins causing hapten formation and allergy",
    },
]


# Pre-compile SMARTS patterns
_COMPILED_ALERTS: list[tuple[dict, object | None]] = []
if RDKit_AVAILABLE and Chem is not None:
    for _alert in STRUCTURAL_ALERTS:
        _pat = Chem.MolFromSmarts(_alert["smarts"])
        _COMPILED_ALERTS.append((_alert, _pat))
else:
    # RDKit not available: leave patterns empty so detection is a no-op
    for _alert in STRUCTURAL_ALERTS:
        _COMPILED_ALERTS.append((_alert, None))


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------
def detect_alerts(mol) -> AlertReport:
    """
    Scan a molecule for all structural alerts.

    Parameters
    ----------
    mol : rdkit.Chem.Mol or str (SMILES)

    Returns
    -------
    AlertReport with all matches, total severity, override probability,
    and human-readable explanation.
    """
    if not RDKit_AVAILABLE or Chem is None:
        return AlertReport(explanation="RDKit not installed; structural alert detection unavailable.")

    if isinstance(mol, str):
        mol = Chem.MolFromSmiles(mol)
    if mol is None:
        return AlertReport(explanation="Invalid molecule — cannot analyze.")

    matches: list[AlertMatch] = []
    total_severity = 0

    for alert_def, pattern in _COMPILED_ALERTS:
        if pattern is None:
            continue
        hits = mol.GetSubstructMatches(pattern)
        if hits:
            match = AlertMatch(
                name=alert_def["name"],
                smarts=alert_def["smarts"],
                severity=alert_def["severity"],
                severity_label=alert_def["severity_label"],
                probability_boost=alert_def["probability_boost"],
                description=alert_def["description"],
                mechanism=alert_def["mechanism"],
                count=len(hits),
            )
            matches.append(match)
            total_severity += match.severity * match.count

    # Build report
    report = AlertReport(matches=matches, total_severity=total_severity)

    # Override probability when extremely dangerous groups exist
    report.override_probability = _compute_override(matches, total_severity)

    # Generate explanation
    report.explanation = _generate_explanation(matches)

    return report


def _compute_override(matches: list[AlertMatch], total_severity: int) -> float | None:
    """
    Return an override probability if structural alerts alone warrant
    a minimum toxicity floor.
    """
    if not matches:
        return None

    n_critical = sum(1 for m in matches if m.severity >= 5)
    n_high = sum(1 for m in matches if m.severity >= 4)

    # Multiple critical alerts → floor at 0.90 (CRITICAL)
    if n_critical >= 2:
        return 0.95

    # One critical alert → floor at 0.80
    if n_critical >= 1:
        return 0.80

    # Multiple high-severity alerts → floor at 0.70
    if n_high >= 3:
        return 0.85

    if n_high >= 2:
        return 0.70

    # High total severity → floor at 0.60
    if total_severity >= 12:
        return 0.65

    return None


def _generate_explanation(matches: list[AlertMatch]) -> str:
    """Build a human-readable explanation from matched alerts."""
    if not matches:
        return "No known toxic structural alerts were detected in this molecule."

    # Sort by severity descending
    sorted_matches = sorted(matches, key=lambda m: m.severity, reverse=True)

    alert_names = [m.name for m in sorted_matches[:5]]
    mechanisms = [m.mechanism for m in sorted_matches[:3]]

    if len(alert_names) == 1:
        intro = f"This molecule contains **{alert_names[0]}**"
    elif len(alert_names) == 2:
        intro = f"This molecule contains **{alert_names[0]}** and **{alert_names[1]}**"
    else:
        listed = ", ".join(f"**{n}**" for n in alert_names[:-1])
        intro = f"This molecule contains {listed}, and **{alert_names[-1]}**"

    severity_word = "moderately" if sorted_matches[0].severity <= 3 else "highly"
    explanation = (
        f"{intro}, which are {severity_word} associated with toxicity. "
    )

    if mechanisms:
        explanation += "Key mechanisms: " + "; ".join(mechanisms[:2]) + "."

    return explanation


def get_alert_summary_table(report: AlertReport) -> list[dict]:
    """Return a list of dicts suitable for DataFrame display."""
    rows = []
    for m in report.matches:
        rows.append({
            "Alert": m.name,
            "Severity": f"{'🔴' * min(m.severity, 5)} ({m.severity}/5)",
            "Count": m.count,
            "Description": m.description,
            "Probability Boost": f"+{m.probability_boost:.0%}",
        })
    return rows


def compute_alert_boosted_probability(
    base_probability: float,
    report: AlertReport,
) -> float:
    """
    Adjust model probability upward based on structural alerts.
    Uses the override floor when applicable, otherwise adds
    a diminishing boost.
    """
    if report.override_probability is not None:
        return max(base_probability, report.override_probability)

    if not report.matches:
        return base_probability

    # Diminishing additive boost
    boost = 0.0
    for i, m in enumerate(sorted(report.matches, key=lambda x: x.probability_boost, reverse=True)):
        discount = 1.0 / (1 + i * 0.5)          # 1st full, 2nd 67%, 3rd 50% …
        boost += m.probability_boost * discount

    boosted = base_probability + boost * (1 - base_probability)  # asymptotic cap
    return min(round(boosted, 4), 0.999)
