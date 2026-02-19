"""Test Module 4: Clinical Decision Engine — verify CPIC risk assessments."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.clinical_engine import assess_risk, assess_drugs, get_available_drugs


def test_clinical_engine():
    print("=== Module 4: Clinical Decision Engine Tests ===\n")

    # Test 1: Direct lookup — CYP2D6 PM + Codeine should be Ineffective
    rec = assess_risk("CYP2D6", "PM", "CODEINE")
    print(f"[Test 1] CYP2D6 PM + CODEINE:")
    print(f"  Risk: {rec.risk_label} | Severity: {rec.severity} | Conf: {rec.confidence_score}")
    print(f"  Rec: {rec.recommendation[:80]}...")
    assert rec.risk_label == "Ineffective", f"Expected Ineffective, got {rec.risk_label}"
    assert rec.found is True

    # Test 2: CYP2D6 UM + Codeine should be Toxic
    rec2 = assess_risk("CYP2D6", "UM", "CODEINE")
    print(f"\n[Test 2] CYP2D6 UM + CODEINE:")
    print(f"  Risk: {rec2.risk_label} | Severity: {rec2.severity}")
    assert rec2.risk_label == "Toxic"

    # Test 3: CYP2C9 IM + Warfarin should be Adjust
    rec3 = assess_risk("CYP2C9", "IM", "WARFARIN")
    print(f"\n[Test 3] CYP2C9 IM + WARFARIN:")
    print(f"  Risk: {rec3.risk_label} | Severity: {rec3.severity}")
    assert rec3.risk_label == "Adjust"

    # Test 4: Unknown drug should return found=False
    rec4 = assess_risk("CYP2D6", "EM", "UNKNOWNDRUG")
    print(f"\n[Test 4] CYP2D6 EM + UNKNOWNDRUG:")
    print(f"  Risk: {rec4.risk_label} | Found: {rec4.found}")
    assert rec4.found is False

    # Test 5: Multi-drug assessment with sample genotypes
    gene_phenos = {"CYP2D6": "IM", "CYP2C19": "RM", "CYP2C9": "IM", "SLCO1B1": "DF"}
    drugs = ["CODEINE", "WARFARIN", "SIMVASTATIN", "CLOPIDOGREL"]
    result = assess_drugs(gene_phenos, drugs)

    print(f"\n[Test 5] Multi-drug assessment ({len(drugs)} drugs):")
    for r in result.recommendations:
        print(f"  {r.drug:15s} | {r.gene:8s} {r.phenotype:4s} | {r.risk_label:12s} | {r.severity}")
    assert result.drugs_assessed == 4

    # Test 6: Available drugs list
    avail = get_available_drugs()
    print(f"\n[Test 6] Available drugs in CPIC DB: {len(avail)}")
    print(f"  {', '.join(avail[:10])}...")

    print(f"\n=== ALL MODULE 4 TESTS PASSED ===")


if __name__ == "__main__":
    test_clinical_engine()
