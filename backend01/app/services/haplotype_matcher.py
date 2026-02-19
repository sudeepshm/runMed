"""
PharmaGuard — Haplotype Matcher & Star Allele Lookup (Module 3).

Takes parsed VCF variants and determines:
  1. Which star alleles are present on each haplotype
  2. The diplotype (e.g. *1/*4)
  3. The phenotype (e.g. Intermediate Metabolizer) via activity scores

Algorithm:
  - For each gene, gather the patient's variants at that gene's loci.
  - Score each defined star allele by how many of its defining variants
    are present (heterozygous or homozygous).
  - Assign the two best-matching alleles as the diplotype.
  - Sum activity scores → map to phenotype via thresholds.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Load star allele definitions from JSON ────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STAR_ALLELE_JSON = DATA_DIR / "star_allele_definitions.json"

_DEFINITIONS: Dict = {}


def _load_definitions() -> Dict:
    """Load and cache star allele definitions."""
    global _DEFINITIONS
    if _DEFINITIONS:
        return _DEFINITIONS
    if STAR_ALLELE_JSON.exists():
        with open(STAR_ALLELE_JSON, "r") as f:
            _DEFINITIONS = json.load(f)
    else:
        logger.warning("Star allele definitions not found: %s", STAR_ALLELE_JSON)
    return _DEFINITIONS


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class AlleleCall:
    """A single star allele assignment for one haplotype."""
    allele_name: str        # e.g. "*4"
    activity_score: float   # e.g. 0.0
    function: str           # e.g. "No function"
    matched_variants: int   # how many defining variants matched
    total_defining: int     # total defining variants for this allele


@dataclass
class DiplotypeResult:
    """Full diplotype + phenotype result for a gene."""
    gene: str
    allele1: AlleleCall
    allele2: AlleleCall
    diplotype: str              # e.g. "*1/*4"
    activity_score_total: float # sum of both allele scores
    phenotype: str              # e.g. "IM"
    phenotype_label: str        # e.g. "Intermediate Metabolizer"
    matched_rsids: List[str] = field(default_factory=list)


@dataclass
class HaplotypeResult:
    """Results for all genes analysed."""
    gene_results: Dict[str, DiplotypeResult] = field(default_factory=dict)
    genes_analysed: int = 0
    errors: List[str] = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────

def match_haplotypes(
    variants: List[dict],
    target_genes: Optional[Set[str]] = None,
) -> HaplotypeResult:
    """
    Assign star allele diplotypes and phenotypes for each pharmacogene.

    Args:
        variants: List of dicts with keys {rsid, genotype, gene, alt, ref, ...}
                  (typically from vcf_parser.ParsedVariant converted to dict).
        target_genes: Optional filter — only analyse these genes.

    Returns:
        HaplotypeResult with per-gene DiplotypeResults.
    """
    defs = _load_definitions()
    result = HaplotypeResult()

    # Group variants by gene
    gene_variants: Dict[str, List[dict]] = {}
    for v in variants:
        gene = v.get("gene", "")
        if gene and (target_genes is None or gene in target_genes):
            gene_variants.setdefault(gene, []).append(v)

    # Analyse each gene
    for gene, gene_def in defs.items():
        if target_genes and gene not in target_genes:
            continue

        gv = gene_variants.get(gene, [])

        try:
            diplotype_result = _assign_diplotype(gene, gene_def, gv)
            result.gene_results[gene] = diplotype_result
            result.genes_analysed += 1
        except Exception as exc:
            logger.exception("Error assigning diplotype for %s", gene)
            result.errors.append(f"{gene}: {exc}")

    return result


def match_single_gene(gene: str, variants: List[dict]) -> Optional[DiplotypeResult]:
    """Convenience: match haplotypes for a single gene."""
    hr = match_haplotypes(variants, target_genes={gene})
    return hr.gene_results.get(gene)


# ── Core algorithm ────────────────────────────────────────────────────

def _assign_diplotype(
    gene: str,
    gene_def: dict,
    variants: List[dict],
) -> DiplotypeResult:
    """
    Assign diplotype for a single gene.

    Strategy:
      1. Build a set of the patient's variant alleles at this gene's loci.
      2. For each star allele definition, count how many defining variants
         the patient carries (at least heterozygous).
      3. Rank alleles by match fraction.
      4. Handle het/hom to determine two allele calls.
      5. Sum activity scores → phenotype.
    """
    alleles_def = gene_def.get("alleles", {})
    pheno_map = gene_def.get("phenotype_map", {})

    # Build patient variant index: rsid → {genotype, alt, ref}
    patient_variants: Dict[str, dict] = {}
    matched_rsids: List[str] = []
    for v in variants:
        rsid = v.get("rsid", "")
        if rsid:
            patient_variants[rsid] = v

    # Score each star allele
    allele_scores: List[Tuple[str, AlleleCall]] = []

    for allele_name, allele_info in alleles_def.items():
        defining = allele_info.get("defining_variants", [])

        if not defining:
            # Wild-type (*1 or equivalent) — scored last as default
            allele_scores.append((
                allele_name,
                AlleleCall(
                    allele_name=allele_name,
                    activity_score=allele_info.get("activity_score", 1.0),
                    function=allele_info.get("name", ""),
                    matched_variants=0,
                    total_defining=0,
                ),
            ))
            continue

        # Count matches
        matched = 0
        for dv in defining:
            rsid = dv.get("rsid", "")
            expected_alt = dv.get("alt", "")
            pv = patient_variants.get(rsid)

            if pv:
                gt = pv.get("genotype", "")
                pv_alt = pv.get("alt", "")

                # Check if patient carries the alt allele
                has_alt = _genotype_has_alt(gt, pv_alt, expected_alt)
                if has_alt:
                    matched += 1
                    if rsid not in matched_rsids:
                        matched_rsids.append(rsid)

        if matched > 0:
            allele_scores.append((
                allele_name,
                AlleleCall(
                    allele_name=allele_name,
                    activity_score=allele_info.get("activity_score", 0.0),
                    function=allele_info.get("name", ""),
                    matched_variants=matched,
                    total_defining=len(defining),
                ),
            ))

    # Sort by: full matches first (matched == total), then by match count desc
    allele_scores.sort(
        key=lambda x: (
            -(x[1].matched_variants / max(x[1].total_defining, 1)),  # match fraction desc
            -x[1].matched_variants,  # absolute matches desc
        )
    )

    # ── Assign diplotype ──────────────────────────────────────
    # Separate wild-type from variant alleles
    wildtype = None
    variant_alleles: List[AlleleCall] = []

    for name, call in allele_scores:
        if call.total_defining == 0:
            if wildtype is None:
                wildtype = call
        else:
            variant_alleles.append(call)

    # Default wild-type
    if wildtype is None:
        wt_name = "*1" if "*1" in alleles_def else list(alleles_def.keys())[0]
        wt_info = alleles_def.get(wt_name, {})
        wildtype = AlleleCall(
            allele_name=wt_name,
            activity_score=wt_info.get("activity_score", 1.0),
            function=wt_info.get("name", "Normal function"),
            matched_variants=0,
            total_defining=0,
        )

    # Determine allele pair
    if not variant_alleles:
        # Homozygous wild-type
        allele1 = wildtype
        allele2 = AlleleCall(**{**wildtype.__dict__})
    elif len(variant_alleles) == 1:
        va = variant_alleles[0]
        # Check if homozygous for this variant allele
        is_hom = _is_homozygous_for_allele(va, variants, alleles_def)
        if is_hom:
            allele1 = va
            allele2 = AlleleCall(**{**va.__dict__})
        else:
            allele1 = wildtype
            allele2 = va
    else:
        # Multiple variant alleles — take top two
        allele1 = variant_alleles[0]
        allele2 = variant_alleles[1]

    # Build diplotype string (sorted alphabetically for consistency)
    names = sorted([allele1.allele_name, allele2.allele_name], key=_allele_sort_key)
    diplotype_str = f"{names[0]}/{names[1]}"

    # Calculate total activity score
    total_score = allele1.activity_score + allele2.activity_score

    # Map to phenotype
    phenotype, phenotype_label = _score_to_phenotype(total_score, pheno_map)

    return DiplotypeResult(
        gene=gene,
        allele1=allele1,
        allele2=allele2,
        diplotype=diplotype_str,
        activity_score_total=total_score,
        phenotype=phenotype,
        phenotype_label=phenotype_label,
        matched_rsids=matched_rsids,
    )


# ── Helpers ───────────────────────────────────────────────────────────

def _genotype_has_alt(genotype: str, vcf_alt: str, expected_alt: str) -> bool:
    """
    Check if a genotype string indicates the patient carries the alt allele.
    Genotype formats: "0/1", "1/1", "0|1", etc.
    """
    if not genotype or genotype == ".":
        return False

    sep = "|" if "|" in genotype else "/"
    alleles = genotype.split(sep)

    # If any allele is non-ref (not "0"), patient has alt
    return any(a != "0" and a != "." for a in alleles)


def _is_homozygous_for_allele(
    allele_call: AlleleCall,
    variants: List[dict],
    alleles_def: dict,
) -> bool:
    """Check if the patient is homozygous for a variant allele's defining variants."""
    allele_info = alleles_def.get(allele_call.allele_name, {})
    defining = allele_info.get("defining_variants", [])

    if not defining:
        return False

    patient_index = {v.get("rsid", ""): v for v in variants}

    for dv in defining:
        rsid = dv.get("rsid", "")
        pv = patient_index.get(rsid)
        if not pv:
            return False
        gt = pv.get("genotype", "")
        if not _is_homozygous_gt(gt):
            return False

    return True


def _is_homozygous_gt(genotype: str) -> bool:
    """Check if a genotype is homozygous alt (1/1, 2/2, etc.)."""
    if not genotype or genotype == ".":
        return False
    sep = "|" if "|" in genotype else "/"
    alleles = genotype.split(sep)
    return len(alleles) == 2 and alleles[0] == alleles[1] and alleles[0] != "0"


def _score_to_phenotype(score: float, pheno_map: dict) -> Tuple[str, str]:
    """Map an activity score to a phenotype using the gene's thresholds."""
    for pheno, thresholds in pheno_map.items():
        if thresholds["min_score"] <= score <= thresholds["max_score"]:
            return pheno, thresholds.get("label", pheno)

    # Fallback
    return "Unknown", f"Activity score {score} — no matching phenotype"


def _allele_sort_key(name: str) -> Tuple[int, str]:
    """Sort allele names: *1 < *2 < *3A < *10 etc."""
    clean = name.lstrip("*")
    # Separate numeric prefix from suffix
    num = ""
    suffix = ""
    for i, ch in enumerate(clean):
        if ch.isdigit():
            num += ch
        else:
            suffix = clean[i:]
            break
    return (int(num) if num else 999, suffix)
