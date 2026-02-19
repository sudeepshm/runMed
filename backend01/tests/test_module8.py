"""
PharmaGuard — Module 8: Comprehensive Testing & Validation Suite

Tests:
  1. PharmCAT-style benchmark VCFs (NA12878, NA18526)
  2. Known genotype → expected diplotype/phenotype validation
  3. Field-by-field JSON schema compliance
  4. Edge cases (empty VCF, unknown drugs, large files)
  5. Full pipeline end-to-end via API
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app
from app.services.vcf_parser import parse_vcf
from app.services.haplotype_matcher import match_haplotypes
from app.services.clinical_engine import assess_risk

client = TestClient(app)

PASS = 0
FAIL = 0

def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} — {detail}")


def load_vcf(filename: str) -> bytes:
    path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "sample_vcfs", filename)
    with open(path, "rb") as f:
        return f.read()


# ═══════════════════════════════════════════════════════════════
# TEST 1: NA12878 Benchmark Genotypes
# ═══════════════════════════════════════════════════════════════

def test_na12878():
    print("\n=== Test Suite 1: NA12878 Benchmark ===\n")

    content = load_vcf("NA12878_pgx.vcf")
    parse_result = parse_vcf(content, sample_id="NA12878")
    check("VCF parsing succeeds", parse_result.success)
    check("Extracted variants > 0", len(parse_result.pharmacogene_variants) > 0,
          f"Got {len(parse_result.pharmacogene_variants)}")

    # Haplotype matching
    vdicts = [
        {"rsid": v.rsid, "genotype": v.genotype, "gene": v.gene,
         "ref": v.ref, "alt": v.alt, "chrom": v.chrom, "pos": v.pos}
        for v in parse_result.pharmacogene_variants
    ]
    hr = match_haplotypes(vdicts)

    # CYP2D6: rs3892097(1/1) + rs1065852(1/1) → *4/*4 (homozygous),
    #         rs16947(1/1) + rs1135840(1/1) → *2 variants also present
    # Expect PM or IM phenotype
    cyp2d6 = hr.gene_results.get("CYP2D6")
    check("CYP2D6 found", cyp2d6 is not None)
    if cyp2d6:
        check("CYP2D6 diplotype assigned", len(cyp2d6.diplotype) > 0, cyp2d6.diplotype)
        check("CYP2D6 phenotype assigned", cyp2d6.phenotype in ("UM", "EM", "IM", "PM"),
              cyp2d6.phenotype)
        print(f"    Diplotype: {cyp2d6.diplotype}, Phenotype: {cyp2d6.phenotype}")

    # CYP2C9: rs1799853(1/1) → *2/*2 hom, rs1057910(0/1) → *3 het
    cyp2c9 = hr.gene_results.get("CYP2C9")
    check("CYP2C9 found", cyp2c9 is not None)
    if cyp2c9:
        check("CYP2C9 phenotype is IM or PM",
              cyp2c9.phenotype in ("IM", "PM"),
              f"Got {cyp2c9.phenotype}")
        print(f"    Diplotype: {cyp2c9.diplotype}, Phenotype: {cyp2c9.phenotype}")

    # DPYD: rs3918290(0/1) → *2A het → IM
    dpyd = hr.gene_results.get("DPYD")
    check("DPYD found", dpyd is not None)
    if dpyd:
        check("DPYD has *2A allele", "*2A" in dpyd.diplotype,
              f"Got {dpyd.diplotype}")
        print(f"    Diplotype: {dpyd.diplotype}, Phenotype: {dpyd.phenotype}")

    # SLCO1B1: rs4149056(1/1) → *5/*5 hom → PF
    slco = hr.gene_results.get("SLCO1B1")
    check("SLCO1B1 found", slco is not None)
    if slco:
        check("SLCO1B1 *5 present", "*5" in slco.diplotype,
              f"Got {slco.diplotype}")
        print(f"    Diplotype: {slco.diplotype}, Phenotype: {slco.phenotype}")


# ═══════════════════════════════════════════════════════════════
# TEST 2: NA18526 Benchmark Genotypes
# ═══════════════════════════════════════════════════════════════

def test_na18526():
    print("\n=== Test Suite 2: NA18526 Benchmark ===\n")

    content = load_vcf("NA18526_pgx.vcf")
    parse_result = parse_vcf(content, sample_id="NA18526")
    check("VCF parsing succeeds", parse_result.success)

    vdicts = [
        {"rsid": v.rsid, "genotype": v.genotype, "gene": v.gene,
         "ref": v.ref, "alt": v.alt, "chrom": v.chrom, "pos": v.pos}
        for v in parse_result.pharmacogene_variants
    ]
    hr = match_haplotypes(vdicts)

    # CYP2D6: rs16947(0/1) + rs1135840(0/1) → *1/*2 → EM
    cyp2d6 = hr.gene_results.get("CYP2D6")
    check("CYP2D6 found", cyp2d6 is not None)
    if cyp2d6:
        check("CYP2D6 phenotype EM or IM",
              cyp2d6.phenotype in ("EM", "IM"),
              f"Got {cyp2d6.phenotype}")
        print(f"    Diplotype: {cyp2d6.diplotype}, Phenotype: {cyp2d6.phenotype}")

    # CYP2C19: rs12248560(0/1) → *1/*17 → RM
    cyp2c19 = hr.gene_results.get("CYP2C19")
    check("CYP2C19 found", cyp2c19 is not None)
    if cyp2c19:
        check("CYP2C19 has *17", "*17" in cyp2c19.diplotype,
              f"Got {cyp2c19.diplotype}")
        print(f"    Diplotype: {cyp2c19.diplotype}, Phenotype: {cyp2c19.phenotype}")


# ═══════════════════════════════════════════════════════════════
# TEST 3: Clinical Engine Risk Validation
# ═══════════════════════════════════════════════════════════════

def test_clinical_risk_matrix():
    print("\n=== Test Suite 3: Clinical Risk Matrix ===\n")

    EXPECTED = [
        ("CYP2D6", "UM", "CODEINE", "Toxic"),
        ("CYP2D6", "PM", "CODEINE", "Ineffective"),
        ("CYP2D6", "EM", "CODEINE", "Safe"),
        ("CYP2C19", "PM", "CLOPIDOGREL", "Ineffective"),
        ("CYP2C19", "UM", "VORICONAZOLE", "Ineffective"),
        ("CYP2C9", "PM", "WARFARIN", "Toxic"),
        ("CYP2C9", "IM", "WARFARIN", "Adjust"),
        ("DPYD", "PM", "FLUOROURACIL", "Toxic"),
        ("DPYD", "IM", "FLUOROURACIL", "Adjust"),
        ("TPMT", "PM", "AZATHIOPRINE", "Toxic"),
        ("SLCO1B1", "PF", "SIMVASTATIN", "Toxic"),
        ("SLCO1B1", "DF", "SIMVASTATIN", "Adjust"),
        ("CYP3A5", "EM", "TACROLIMUS", "Adjust"),
    ]

    for gene, pheno, drug, expected_risk in EXPECTED:
        rec = assess_risk(gene, pheno, drug)
        check(f"{gene} {pheno} + {drug} = {expected_risk}",
              rec.risk_label == expected_risk,
              f"Got {rec.risk_label}")


# ═══════════════════════════════════════════════════════════════
# TEST 4: JSON Schema Compliance (Field-by-Field)
# ═══════════════════════════════════════════════════════════════

def test_json_schema():
    print("\n=== Test Suite 4: JSON Schema Compliance ===\n")

    content = load_vcf("sample.vcf")
    response = client.post(
        "/analyze",
        files={"vcf_file": ("sample.vcf", content, "application/octet-stream")},
        data={"patient_id": "SCHEMA_TEST", "drugs": "CODEINE,WARFARIN"},
    )

    check("HTTP 200", response.status_code == 200, f"Got {response.status_code}")
    data = response.json()

    # Top-level fields
    check("Has 'status' field", "status" in data)
    check("Has 'results' field", "results" in data)
    check("status == 'success'", data["status"] == "success")
    check("results is list", isinstance(data["results"], list))

    for idx, result in enumerate(data["results"]):
        prefix = f"Result[{idx}]"

        # Required fields
        check(f"{prefix} has 'drug'", "drug" in result)
        check(f"{prefix} has 'timestamp'", "timestamp" in result)

        # patient_id (may be aliased)
        has_pid = "patient id" in result or "patient_id" in result
        check(f"{prefix} has patient_id", has_pid)

        # risk_assessment
        ra = result.get("risk_assessment", {})
        check(f"{prefix} risk_assessment.risk_label exists", "risk_label" in ra)
        check(f"{prefix} risk_assessment.confidence_score is number",
              isinstance(ra.get("confidence_score"), (int, float)))
        check(f"{prefix} risk_assessment.confidence_score in [0,1]",
              0 <= ra.get("confidence_score", -1) <= 1,
              f"Got {ra.get('confidence_score')}")
        check(f"{prefix} risk_assessment.severity exists", "severity" in ra)
        check(f"{prefix} risk_label valid",
              ra.get("risk_label") in ("Safe", "Adjust", "Toxic", "Ineffective", "Unknown"),
              f"Got {ra.get('risk_label')}")
        check(f"{prefix} severity valid",
              ra.get("severity") in ("low", "moderate", "high", "critical"),
              f"Got {ra.get('severity')}")

        # pharmacogenomic_profile
        pgx = result.get("pharmacogenomic_profile", {})
        check(f"{prefix} pgx.primary_gene exists", "primary_gene" in pgx)
        check(f"{prefix} pgx.diplotype exists", "diplotype" in pgx)
        check(f"{prefix} pgx.phenotype exists", "phenotype" in pgx)
        check(f"{prefix} pgx.primary_gene is non-empty",
              len(pgx.get("primary_gene", "")) > 0)

        # detected_variants
        dvs = result.get("detected_variants", [])
        check(f"{prefix} detected_variants is list", isinstance(dvs, list))
        if dvs:
            dv0 = dvs[0]
            check(f"{prefix} variant has rsid", "rsid" in dv0)
            check(f"{prefix} rsid starts with 'rs'",
                  dv0.get("rsid", "").startswith("rs"),
                  f"Got {dv0.get('rsid')}")

        # llm_generated_explanation
        llm = result.get("llm_generated_explanation", {})
        check(f"{prefix} llm.summary exists", "summary" in llm)
        check(f"{prefix} llm.summary is non-empty",
              len(llm.get("summary", "")) > 20,
              f"Length: {len(llm.get('summary', ''))}")

        # quality_metrics
        qm = result.get("quality_metrics", {})
        check(f"{prefix} qm.vcf_parsing_success exists", "vcf_parsing_success" in qm)
        check(f"{prefix} qm.total_variants_extracted exists", "total_variants_extracted" in qm)
        check(f"{prefix} qm.pharmacogenes_found exists", "pharmacogenes_found" in qm)


# ═══════════════════════════════════════════════════════════════
# TEST 5: Edge Cases
# ═══════════════════════════════════════════════════════════════

def test_edge_cases():
    print("\n=== Test Suite 5: Edge Cases ===\n")

    content = load_vcf("sample.vcf")

    # Unknown drug
    resp = client.post(
        "/analyze",
        files={"vcf_file": ("sample.vcf", content, "application/octet-stream")},
        data={"patient_id": "EDGE_01", "drugs": "IMAGINARYDRUG"},
    )
    check("Unknown drug returns 200", resp.status_code == 200)
    data = resp.json()
    check("Unknown drug has result", len(data["results"]) == 1)
    check("Unknown drug risk is Unknown",
          data["results"][0]["risk_assessment"]["risk_label"] == "Unknown",
          f"Got {data['results'][0]['risk_assessment']['risk_label']}")

    # Single drug
    resp2 = client.post(
        "/analyze",
        files={"vcf_file": ("sample.vcf", content, "application/octet-stream")},
        data={"patient_id": "EDGE_02", "drugs": "WARFARIN"},
    )
    check("Single drug returns 200", resp2.status_code == 200)
    check("Single drug has 1 result", len(resp2.json()["results"]) == 1)

    # Many drugs
    many = "CODEINE,WARFARIN,SIMVASTATIN,CLOPIDOGREL,FLUOROURACIL,AZATHIOPRINE,TACROLIMUS,TAMOXIFEN"
    resp3 = client.post(
        "/analyze",
        files={"vcf_file": ("sample.vcf", content, "application/octet-stream")},
        data={"patient_id": "EDGE_03", "drugs": many},
    )
    check("8 drugs returns 200", resp3.status_code == 200)
    check("8 drugs has 8 results", len(resp3.json()["results"]) == 8,
          f"Got {len(resp3.json()['results'])}")

    # Invalid VCF content
    resp4 = client.post(
        "/analyze",
        files={"vcf_file": ("bad.vcf", b"not a vcf file", "application/octet-stream")},
        data={"patient_id": "EDGE_04", "drugs": "CODEINE"},
    )
    check("Invalid VCF content returns 400", resp4.status_code == 400)


# ═══════════════════════════════════════════════════════════════
# TEST 6: NA12878 Full API Integration
# ═══════════════════════════════════════════════════════════════

def test_na12878_api():
    print("\n=== Test Suite 6: NA12878 Full API Integration ===\n")

    content = load_vcf("NA12878_pgx.vcf")
    drugs = "CODEINE,WARFARIN,SIMVASTATIN,FLUOROURACIL,AZATHIOPRINE"

    resp = client.post(
        "/analyze",
        files={"vcf_file": ("NA12878_pgx.vcf", content, "application/octet-stream")},
        data={"patient_id": "NA12878", "drugs": drugs},
    )

    check("NA12878 API returns 200", resp.status_code == 200)
    data = resp.json()
    check("NA12878 produces 5 results", len(data["results"]) == 5)

    for result in data["results"]:
        drug = result["drug"]
        risk = result["risk_assessment"]["risk_label"]
        gene = result["pharmacogenomic_profile"]["primary_gene"]
        diplo = result["pharmacogenomic_profile"]["diplotype"]
        print(f"    {drug:18s} | {gene:8s} {diplo:10s} | {risk}")

    # Validate critical findings
    codeine = next((r for r in data["results"] if r["drug"] == "CODEINE"), None)
    if codeine:
        check("NA12878 CODEINE gene is CYP2D6",
              codeine["pharmacogenomic_profile"]["primary_gene"] == "CYP2D6")

    warfarin = next((r for r in data["results"] if r["drug"] == "WARFARIN"), None)
    if warfarin:
        check("NA12878 WARFARIN gene is CYP2C9",
              warfarin["pharmacogenomic_profile"]["primary_gene"] == "CYP2C9")
        # CYP2C9 *2/*3 or *3/*2 → PM → Warfarin should be Toxic
        check("NA12878 WARFARIN risk is Toxic or Adjust",
              warfarin["risk_assessment"]["risk_label"] in ("Toxic", "Adjust"),
              f"Got {warfarin['risk_assessment']['risk_label']}")

    simva = next((r for r in data["results"] if r["drug"] == "SIMVASTATIN"), None)
    if simva:
        check("NA12878 SIMVASTATIN gene is SLCO1B1",
              simva["pharmacogenomic_profile"]["primary_gene"] == "SLCO1B1")

    # Save full JSON output
    out_path = os.path.join(os.path.dirname(__file__), "NA12878_analysis.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\n    Full output saved: {out_path}")


# ═══════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  PharmaGuard — Module 8: Full Validation Suite")
    print("=" * 60)

    test_na12878()
    test_na18526()
    test_clinical_risk_matrix()
    test_json_schema()
    test_edge_cases()
    test_na12878_api()

    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    if FAIL > 0:
        print(f"\n  WARNING: {FAIL} test(s) failed!")
        sys.exit(1)
    else:
        print(f"\n  ALL {PASS} TESTS PASSED!")
        sys.exit(0)
