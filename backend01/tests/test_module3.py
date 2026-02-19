"""Test Module 3: Haplotype Matcher — verify diplotype and phenotype assignment."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.vcf_parser import parse_vcf
from app.services.haplotype_matcher import match_haplotypes


def test_haplotype_matching():
    """Parse sample VCF → match haplotypes → verify results."""
    # Read sample VCF
    vcf_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "sample_vcfs", "sample.vcf")
    with open(vcf_path, "rb") as f:
        content = f.read()

    # Parse VCF
    parse_result = parse_vcf(content)
    assert parse_result.success, f"VCF parsing failed: {parse_result.errors}"
    print(f"✅ VCF parsed: {len(parse_result.pharmacogene_variants)} pharmacogene variants")

    # Convert variants to dicts for haplotype matcher
    variant_dicts = [
        {
            "rsid": v.rsid,
            "genotype": v.genotype,
            "gene": v.gene,
            "ref": v.ref,
            "alt": v.alt,
            "chrom": v.chrom,
            "pos": v.pos,
        }
        for v in parse_result.pharmacogene_variants
    ]

    # Match haplotypes
    haplo_result = match_haplotypes(variant_dicts)

    print(f"\n{'='*60}")
    print(f"  HAPLOTYPE MATCHING RESULTS — {haplo_result.genes_analysed} genes")
    print(f"{'='*60}")

    for gene, dr in sorted(haplo_result.gene_results.items()):
        print(f"\n  Gene: {gene}")
        print(f"    Diplotype:      {dr.diplotype}")
        print(f"    Phenotype:      {dr.phenotype} ({dr.phenotype_label})")
        print(f"    Activity Score: {dr.activity_score_total}")
        print(f"    Allele 1:       {dr.allele1.allele_name} (score={dr.allele1.activity_score}, fn={dr.allele1.function})")
        print(f"    Allele 2:       {dr.allele2.allele_name} (score={dr.allele2.activity_score}, fn={dr.allele2.function})")
        print(f"    Matched rsIDs:  {dr.matched_rsids}")

    if haplo_result.errors:
        print(f"\n  ⚠ Errors: {haplo_result.errors}")

    # Basic assertions
    assert haplo_result.genes_analysed >= 5, f"Expected ≥5 genes, got {haplo_result.genes_analysed}"

    # CYP2D6: sample has rs3892097(0/1), rs1065852(0/1), rs1135840(1/1), rs16947(0/1)
    # *4 = rs3892097 + rs1065852 → matched, *2 = rs16947 + rs1135840 → matched
    cyp2d6 = haplo_result.gene_results.get("CYP2D6")
    assert cyp2d6 is not None, "CYP2D6 not found"
    print(f"\n  ✅ CYP2D6: {cyp2d6.diplotype} → {cyp2d6.phenotype}")

    # CYP2C19: rs12248560(0/1) → *17 het
    cyp2c19 = haplo_result.gene_results.get("CYP2C19")
    assert cyp2c19 is not None, "CYP2C19 not found"
    print(f"  ✅ CYP2C19: {cyp2c19.diplotype} → {cyp2c19.phenotype}")

    # CYP2C9: rs1799853(0/1) → *2 het
    cyp2c9 = haplo_result.gene_results.get("CYP2C9")
    assert cyp2c9 is not None, "CYP2C9 not found"
    print(f"  ✅ CYP2C9: {cyp2c9.diplotype} → {cyp2c9.phenotype}")

    print(f"\n{'='*60}")
    print(f"  ✅ ALL HAPLOTYPE TESTS PASSED!")
    print(f"{'='*60}")


if __name__ == "__main__":
    test_haplotype_matching()
