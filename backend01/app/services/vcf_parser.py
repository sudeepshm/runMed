"""
PharmaGuard — VCF Parser & Bioinformatics Preprocessor (Module 2).

Parses VCF files, validates format, extracts pharmacogenomic variants,
and normalises them for downstream haplotype matching.

Uses PyVCF3 (pure-Python, Windows-compatible fallback for cyvcf2).
"""

from __future__ import annotations

import io
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import vcf  # PyVCF3

logger = logging.getLogger(__name__)

# ── Pharmacogene coordinate map ───────────────────────────────────────
# Maps (chromosome, start, end) → gene symbol.
# Coordinates are GRCh38 approximate loci covering the full gene region.

PHARMACOGENE_REGIONS: Dict[str, List[Tuple[int, int, str]]] = {
    # chromosome → [(start, end, gene), ...]
    "chr10": [
        (94_727_000, 94_833_000, "CYP2C9"),   # CYP2C9
        (96_445_000, 96_615_000, "CYP2C19"),   # CYP2C19
    ],
    "chr13": [
        (48_004_000, 48_101_000, "DPYD"),      # DPYD
    ],
    "chr16": [
        (31_090_000, 31_120_000, "VKORC1"),    # VKORC1
    ],
    "chr22": [
        (42_120_000, 42_140_000, "CYP2D6"),    # CYP2D6
    ],
    "chr7": [
        (99_648_000, 99_700_000, "CYP3A5"),    # CYP3A5
    ],
    "chr6": [
        (18_128_000, 18_155_000, "TPMT"),      # TPMT
    ],
    "chr12": [
        (21_130_000, 21_240_000, "SLCO1B1"),   # SLCO1B1
    ],
}

# Also support bare chromosome names (without "chr" prefix)
_extra: Dict[str, List[Tuple[int, int, str]]] = {}
for _chr, _regions in PHARMACOGENE_REGIONS.items():
    bare = _chr.replace("chr", "")
    _extra[bare] = _regions
PHARMACOGENE_REGIONS.update(_extra)


# ── Known pharmacogenomic rsIDs (quick filter) ─────────────────────
KNOWN_PGX_RSIDS: Set[str] = {
    # CYP2D6
    "rs3892097", "rs1065852", "rs1135840", "rs16947", "rs28371725",
    "rs5030655", "rs5030656", "rs28371706", "rs59421388",
    # CYP2C19
    "rs12248560", "rs4244285", "rs4986893", "rs28399504", "rs56337013",
    # CYP2C9
    "rs1799853", "rs1057910", "rs28371686", "rs7900194", "rs9332131",
    # CYP3A5
    "rs776746",
    # DPYD
    "rs3918290", "rs55886062", "rs67376798", "rs75017182",
    # TPMT
    "rs1142345", "rs1800460", "rs1800462",
    # SLCO1B1
    "rs4149056", "rs2306283",
    # VKORC1
    "rs9923231", "rs116855232",
}


@dataclass
class ParsedVariant:
    """A single variant extracted from the VCF."""
    chrom: str
    pos: int
    rsid: str
    ref: str
    alt: str
    genotype: str           # e.g. "0/1"
    allelic_depth: str      # e.g. "25,20"
    read_depth: int
    quality: float
    gene: str               # mapped pharmacogene, e.g. "CYP2D6"
    is_pharmacogene: bool   # True if within a known PGx region


@dataclass
class VCFParseResult:
    """Result of parsing a VCF file."""
    success: bool
    vcf_version: str = ""
    sample_id: str = ""
    total_variants: int = 0
    pharmacogene_variants: List[ParsedVariant] = field(default_factory=list)
    genes_found: Set[str] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────

def validate_vcf_content(content: bytes) -> Tuple[bool, str]:
    """
    Validate that the VCF content is well-formed and version 4.2.
    Returns (is_valid, error_message).
    """
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        return False, "File could not be decoded as UTF-8."

    lines = text.split("\n")

    if not lines:
        return False, "VCF file is empty."

    # Check fileformat header
    first_line = lines[0].strip()
    if not first_line.startswith("##fileformat="):
        return False, f"Missing ##fileformat header. Got: {first_line[:60]}"

    version = first_line.split("=", 1)[1]
    if version != "VCFv4.2":
        return False, f"Unsupported VCF version: {version}. Expected VCFv4.2."

    # Check for #CHROM header
    has_chrom = any(l.strip().startswith("#CHROM") for l in lines)
    if not has_chrom:
        return False, "Missing #CHROM header line."

    return True, ""


def parse_vcf(content: bytes, sample_id: str = "") -> VCFParseResult:
    """
    Parse VCF file content and extract pharmacogenomic variants.

    Args:
        content: Raw bytes of the VCF file.
        sample_id: Optional sample ID override.

    Returns:
        VCFParseResult with extracted pharmacogene variants.
    """
    result = VCFParseResult(success=False)

    # ── Validate ──────────────────────────────────────────────
    is_valid, error = validate_vcf_content(content)
    if not is_valid:
        result.errors.append(error)
        return result

    # Extract version
    text = content.decode("utf-8", errors="replace")
    first_line = text.split("\n")[0].strip()
    result.vcf_version = first_line.split("=", 1)[1]

    # ── Parse with PyVCF3 ─────────────────────────────────────
    try:
        # PyVCF3 wants a file-like object
        vcf_reader = vcf.Reader(io.StringIO(text))

        # Get sample name
        if vcf_reader.samples:
            result.sample_id = sample_id or vcf_reader.samples[0]

        for record in vcf_reader:
            result.total_variants += 1

            chrom = str(record.CHROM)
            pos = int(record.POS)
            rsid = record.ID or f"{chrom}:{pos}"
            ref = str(record.REF)
            alt = ",".join(str(a) for a in record.ALT) if record.ALT else "."
            quality = float(record.QUAL) if record.QUAL else 0.0

            # ── Extract per-sample fields ─────────────────────
            gt = "."
            ad = "."
            dp = 0

            if record.samples:
                sample = record.samples[0]
                # Genotype
                gt_data = sample.data
                if hasattr(gt_data, "GT") and gt_data.GT is not None:
                    gt = gt_data.GT
                # Allelic depth
                if hasattr(gt_data, "AD") and gt_data.AD is not None:
                    if isinstance(gt_data.AD, (list, tuple)):
                        ad = ",".join(str(x) for x in gt_data.AD)
                    else:
                        ad = str(gt_data.AD)
                # Read depth
                if hasattr(gt_data, "DP") and gt_data.DP is not None:
                    dp = int(gt_data.DP)

            # ── Map to pharmacogene ───────────────────────────
            gene = _map_to_pharmacogene(chrom, pos, rsid)
            is_pgx = gene != ""

            if is_pgx:
                variant = ParsedVariant(
                    chrom=chrom,
                    pos=pos,
                    rsid=rsid,
                    ref=ref,
                    alt=alt,
                    genotype=gt,
                    allelic_depth=ad,
                    read_depth=dp,
                    quality=quality,
                    gene=gene,
                    is_pharmacogene=True,
                )
                result.pharmacogene_variants.append(variant)
                result.genes_found.add(gene)

        result.success = True

    except Exception as exc:
        logger.exception("Error parsing VCF")
        result.errors.append(f"VCF parsing error: {exc}")

    return result


# ── Internal helpers ──────────────────────────────────────────────────

def _map_to_pharmacogene(chrom: str, pos: int, rsid: str) -> str:
    """
    Map a variant to a pharmacogene by:
      1. Known rsID lookup (fast path)
      2. Coordinate-based region lookup (fallback)
    """
    # Fast path: known rsID
    if rsid in KNOWN_PGX_RSIDS:
        # Still need to find the gene name
        regions = PHARMACOGENE_REGIONS.get(chrom, [])
        for start, end, gene in regions:
            if start <= pos <= end:
                return gene
        # rsID is known but coordinates don't match a region —
        # return a best-effort gene from the rsID-to-gene map
        return _rsid_to_gene(rsid)

    # Coordinate-based lookup
    regions = PHARMACOGENE_REGIONS.get(chrom, [])
    for start, end, gene in regions:
        if start <= pos <= end:
            return gene

    return ""


def _rsid_to_gene(rsid: str) -> str:
    """Fallback rsID → gene mapping for known PGx variants."""
    _MAP = {
        # CYP2D6
        "rs3892097": "CYP2D6", "rs1065852": "CYP2D6", "rs1135840": "CYP2D6",
        "rs16947": "CYP2D6", "rs28371725": "CYP2D6", "rs5030655": "CYP2D6",
        "rs5030656": "CYP2D6", "rs28371706": "CYP2D6", "rs59421388": "CYP2D6",
        # CYP2C19
        "rs12248560": "CYP2C19", "rs4244285": "CYP2C19",
        "rs4986893": "CYP2C19", "rs28399504": "CYP2C19", "rs56337013": "CYP2C19",
        # CYP2C9
        "rs1799853": "CYP2C9", "rs1057910": "CYP2C9", "rs28371686": "CYP2C9",
        "rs7900194": "CYP2C9", "rs9332131": "CYP2C9",
        # CYP3A5
        "rs776746": "CYP3A5",
        # DPYD
        "rs3918290": "DPYD", "rs55886062": "DPYD",
        "rs67376798": "DPYD", "rs75017182": "DPYD",
        # TPMT
        "rs1142345": "TPMT", "rs1800460": "TPMT", "rs1800462": "TPMT",
        # SLCO1B1
        "rs4149056": "SLCO1B1", "rs2306283": "SLCO1B1",
        # VKORC1
        "rs9923231": "VKORC1", "rs116855232": "VKORC1",
    }
    return _MAP.get(rsid, "")
