"""
PharmaGuard — Clinical Decision Engine (Module 4).

Maps (Gene + Phenotype + Drug) triplets to CPIC-based risk assessments:
  - Risk Label: Safe | Adjust | Toxic | Ineffective
  - Severity: low | moderate | high | critical
  - Clinical Recommendation: actionable guidance text

Lookups are performed against the SQLite database (seeded from cpic_recommendations.json)
with an in-memory fallback cache for speed.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CPIC_JSON = DATA_DIR / "cpic_recommendations.json"
DB_PATH = DATA_DIR / "pharmaguard.db"

# ── In-memory cache ──────────────────────────────────────────────────
_CACHE: Dict[Tuple[str, str, str], dict] = {}


def _load_cache() -> None:
    """Load CPIC recommendations into memory for O(1) lookup."""
    global _CACHE
    if _CACHE:
        return

    # Try loading from JSON directly (fastest)
    if CPIC_JSON.exists():
        with open(CPIC_JSON, "r") as f:
            data = json.load(f)
        for rec in data:
            key = (rec["gene"].upper(), rec["phenotype"].upper(), rec["drug"].upper())
            _CACHE[key] = rec
        logger.info("Loaded %d CPIC recommendations into cache", len(_CACHE))
        return

    # Fallback: try SQLite
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM cpic_recommendations").fetchall()
            for r in rows:
                d = dict(r)
                key = (d["gene"].upper(), d["phenotype"].upper(), d["drug"].upper())
                _CACHE[key] = d
            conn.close()
            logger.info("Loaded %d CPIC recommendations from SQLite", len(_CACHE))
        except Exception as exc:
            logger.warning("Could not load CPIC from SQLite: %s", exc)


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class ClinicalRecommendation:
    """A single CPIC-based clinical recommendation for a gene–drug pair."""
    gene: str
    phenotype: str
    drug: str
    risk_label: str         # Safe | Adjust | Toxic | Ineffective
    severity: str           # low | moderate | high | critical
    recommendation: str     # Clinical action text
    confidence_score: float # 0.0–1.0
    source: str = "CPIC"
    found: bool = True      # False if no CPIC guideline exists for this combo


@dataclass
class ClinicalResult:
    """Results from the clinical decision engine for all queried drugs."""
    recommendations: List[ClinicalRecommendation] = field(default_factory=list)
    drugs_assessed: int = 0
    warnings: List[str] = field(default_factory=list)


# ── Confidence scoring ────────────────────────────────────────────────

SEVERITY_CONFIDENCE = {
    "critical": 0.95,
    "high": 0.90,
    "moderate": 0.80,
    "low": 0.70,
}


# ── Public API ────────────────────────────────────────────────────────

def assess_risk(
    gene: str,
    phenotype: str,
    drug: str,
) -> ClinicalRecommendation:
    """
    Look up the CPIC recommendation for a (gene, phenotype, drug) triplet.

    Returns a ClinicalRecommendation. If no guideline exists, returns a
    default "No CPIC guideline" result with found=False.
    """
    _load_cache()

    key = (gene.upper(), phenotype.upper(), drug.upper())
    rec = _CACHE.get(key)

    if rec:
        severity = rec.get("severity", "moderate")
        return ClinicalRecommendation(
            gene=gene,
            phenotype=phenotype,
            drug=drug,
            risk_label=rec["risk_label"],
            severity=severity,
            recommendation=rec["recommendation"],
            confidence_score=SEVERITY_CONFIDENCE.get(severity, 0.75),
            source=rec.get("source", "CPIC"),
            found=True,
        )

    # No guideline found — return a safe default
    return ClinicalRecommendation(
        gene=gene,
        phenotype=phenotype,
        drug=drug,
        risk_label="Unknown",
        severity="low",
        recommendation=(
            f"No CPIC guideline found for {drug} with {gene} {phenotype}. "
            f"Standard dosing may be appropriate — consult clinical pharmacist."
        ),
        confidence_score=0.3,
        source="none",
        found=False,
    )


def assess_drugs(
    gene_phenotypes: Dict[str, str],
    drugs: List[str],
) -> ClinicalResult:
    """
    Assess risks for multiple drugs against detected gene–phenotype profiles.

    Args:
        gene_phenotypes: Dict of {gene: phenotype}, e.g. {"CYP2D6": "IM", "CYP2C19": "RM"}
        drugs: List of drug names, e.g. ["CODEINE", "WARFARIN"]

    Returns:
        ClinicalResult with a recommendation per (drug, relevant gene) pair.
    """
    result = ClinicalResult()

    # Drug → gene affinity map (which genes are relevant for each drug)
    drug_gene_map = _get_drug_gene_map()

    for drug in drugs:
        drug_upper = drug.upper()
        relevant_genes = drug_gene_map.get(drug_upper, [])

        if not relevant_genes:
            # Try all detected genes as a fallback
            relevant_genes = list(gene_phenotypes.keys())

        found_any = False
        for gene in relevant_genes:
            phenotype = gene_phenotypes.get(gene)
            if not phenotype:
                continue

            rec = assess_risk(gene, phenotype, drug_upper)
            if rec.found:
                result.recommendations.append(rec)
                found_any = True

        if not found_any:
            # No specific gene–drug guideline
            result.recommendations.append(
                ClinicalRecommendation(
                    gene="N/A",
                    phenotype="N/A",
                    drug=drug_upper,
                    risk_label="Unknown",
                    severity="low",
                    recommendation=(
                        f"No pharmacogenomic interaction found for {drug_upper} with "
                        f"the patient's detected gene variants. Standard dosing is likely appropriate."
                    ),
                    confidence_score=0.3,
                    source="none",
                    found=False,
                )
            )
            result.warnings.append(
                f"No CPIC guideline for {drug_upper} with detected pharmacogenes."
            )

        result.drugs_assessed += 1

    return result


# ── Drug–Gene affinity map ────────────────────────────────────────────

def _get_drug_gene_map() -> Dict[str, List[str]]:
    """
    Return a mapping of drugs to their pharmacogenomically relevant genes.
    This determines which gene(s) to check for each drug.
    """
    return {
        # CYP2D6 substrates
        "CODEINE": ["CYP2D6"],
        "TRAMADOL": ["CYP2D6"],
        "ONDANSETRON": ["CYP2D6"],
        "TAMOXIFEN": ["CYP2D6"],
        "HYDROCODONE": ["CYP2D6"],
        "OXYCODONE": ["CYP2D6"],
        "ATOMOXETINE": ["CYP2D6"],
        "DEXTROMETHORPHAN": ["CYP2D6"],

        # CYP2C19 substrates
        "CLOPIDOGREL": ["CYP2C19"],
        "OMEPRAZOLE": ["CYP2C19"],
        "PANTOPRAZOLE": ["CYP2C19"],
        "LANSOPRAZOLE": ["CYP2C19"],
        "ESOMEPRAZOLE": ["CYP2C19"],
        "VORICONAZOLE": ["CYP2C19"],
        "CITALOPRAM": ["CYP2C19"],
        "ESCITALOPRAM": ["CYP2C19"],
        "SERTRALINE": ["CYP2C19"],

        # CYP2C9 substrates
        "WARFARIN": ["CYP2C9"],
        "PHENYTOIN": ["CYP2C9"],
        "CELECOXIB": ["CYP2C9"],
        "FLURBIPROFEN": ["CYP2C9"],

        # DPYD substrates
        "FLUOROURACIL": ["DPYD"],
        "5-FLUOROURACIL": ["DPYD"],
        "5-FU": ["DPYD"],
        "CAPECITABINE": ["DPYD"],
        "TEGAFUR": ["DPYD"],

        # TPMT substrates
        "AZATHIOPRINE": ["TPMT"],
        "MERCAPTOPURINE": ["TPMT"],
        "6-MERCAPTOPURINE": ["TPMT"],
        "THIOGUANINE": ["TPMT"],

        # CYP3A5 substrates
        "TACROLIMUS": ["CYP3A5"],

        # SLCO1B1 substrates
        "SIMVASTATIN": ["SLCO1B1"],
        "ATORVASTATIN": ["SLCO1B1"],
        "LOVASTATIN": ["SLCO1B1"],
        "PRAVASTATIN": ["SLCO1B1"],
        "ROSUVASTATIN": ["SLCO1B1"],
        "FLUVASTATIN": ["SLCO1B1"],
    }


def get_available_drugs() -> List[str]:
    """Return list of all drugs with CPIC guidelines in the database."""
    _load_cache()
    drugs = set()
    for _, _, drug in _CACHE.keys():
        drugs.add(drug)
    return sorted(drugs)


def get_available_genes() -> List[str]:
    """Return list of all genes with CPIC guidelines."""
    _load_cache()
    genes = set()
    for gene, _, _ in _CACHE.keys():
        genes.add(gene)
    return sorted(genes)
