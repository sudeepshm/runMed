"""
Test Module 7: End-to-End Integration — verify full pipeline via API.

Tests the /analyze endpoint with sample VCF + multiple drugs,
validating the complete JSON output structure.
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_full_pipeline():
    print("=== Module 7: End-to-End Integration Tests ===\n")

    # Load sample VCF
    vcf_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "sample_vcfs", "sample.vcf")
    with open(vcf_path, "rb") as f:
        vcf_content = f.read()

    # Test 1: Full analysis with multiple drugs
    drugs = "CODEINE,WARFARIN,SIMVASTATIN,CLOPIDOGREL,FLUOROURACIL"
    print(f"[Test 1] Full analysis: {drugs}")

    response = client.post(
        "/analyze",
        files={"vcf_file": ("sample.vcf", vcf_content, "application/octet-stream")},
        data={"patient_id": "TEST_001", "drugs": drugs},
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert data["status"] == "success"
    assert len(data["results"]) == 5, f"Expected 5 results, got {len(data['results'])}"

    print(f"  Status: {data['status']}")
    print(f"  Results: {len(data['results'])} drug analyses")
    print(f"  Errors: {len(data.get('errors', []))}")

    # Validate each result
    for result in data["results"]:
        drug = result["drug"]
        risk = result["risk_assessment"]
        pgx = result["pharmacogenomic_profile"]
        explanation = result["llm_generated_explanation"]
        qm = result["quality_metrics"]

        print(f"\n  [{drug}]")
        print(f"    Gene:      {pgx['primary_gene']}")
        print(f"    Diplotype: {pgx['diplotype']}")
        print(f"    Phenotype: {pgx['phenotype']}")
        print(f"    Risk:      {risk['risk_label']} ({risk['severity']}, conf={risk['confidence_score']})")
        print(f"    Variants:  {len(result['detected_variants'])} detected")
        print(f"    Summary:   {explanation['summary'][:80]}...")

        # Schema validation
        assert "patient id" in result or "patient_id" in result, "Missing patient_id"
        assert result["drug"] == drug
        assert risk["risk_label"] in ("Safe", "Adjust", "Toxic", "Ineffective", "Unknown")
        assert risk["severity"] in ("low", "moderate", "high", "critical")
        assert 0 <= risk["confidence_score"] <= 1
        assert len(explanation["summary"]) > 20, f"Summary too short for {drug}"
        assert qm["vcf_parsing_success"] is True
        assert qm["pharmacogenes_found"] >= 5

    # Test 2: Validate specific drug-gene matchups
    codeine = next(r for r in data["results"] if r["drug"] == "CODEINE")
    assert codeine["pharmacogenomic_profile"]["primary_gene"] == "CYP2D6"
    assert "Adjust" in codeine["risk_assessment"]["risk_label"] or \
           "Safe" in codeine["risk_assessment"]["risk_label"] or \
           "Ineffective" in codeine["risk_assessment"]["risk_label"]
    print(f"\n  [Check] CODEINE -> CYP2D6: {codeine['risk_assessment']['risk_label']}")

    warfarin = next(r for r in data["results"] if r["drug"] == "WARFARIN")
    assert warfarin["pharmacogenomic_profile"]["primary_gene"] == "CYP2C9"
    print(f"  [Check] WARFARIN -> CYP2C9: {warfarin['risk_assessment']['risk_label']}")

    simva = next(r for r in data["results"] if r["drug"] == "SIMVASTATIN")
    assert simva["pharmacogenomic_profile"]["primary_gene"] == "SLCO1B1"
    print(f"  [Check] SIMVASTATIN -> SLCO1B1: {simva['risk_assessment']['risk_label']}")

    clopid = next(r for r in data["results"] if r["drug"] == "CLOPIDOGREL")
    assert clopid["pharmacogenomic_profile"]["primary_gene"] == "CYP2C19"
    print(f"  [Check] CLOPIDOGREL -> CYP2C19: {clopid['risk_assessment']['risk_label']}")

    fluoro = next(r for r in data["results"] if r["drug"] == "FLUOROURACIL")
    assert fluoro["pharmacogenomic_profile"]["primary_gene"] == "DPYD"
    print(f"  [Check] FLUOROURACIL -> DPYD: {fluoro['risk_assessment']['risk_label']}")

    # Test 3: Validate JSON is serializable
    json_output = json.dumps(data, indent=2, default=str)
    assert len(json_output) > 500, "JSON output seems too short"
    print(f"\n  [Check] JSON output: {len(json_output)} chars, valid JSON")

    # Test 4: Error handling — invalid file
    print(f"\n[Test 4] Invalid file extension:")
    bad_response = client.post(
        "/analyze",
        files={"vcf_file": ("bad.txt", b"not a vcf", "text/plain")},
        data={"patient_id": "TEST", "drugs": "CODEINE"},
    )
    assert bad_response.status_code == 400
    print(f"  Got 400 as expected: {bad_response.json()['detail']}")

    # Test 5: Error handling — no drugs
    print(f"\n[Test 5] Empty drug list:")
    no_drug_resp = client.post(
        "/analyze",
        files={"vcf_file": ("sample.vcf", vcf_content, "application/octet-stream")},
        data={"patient_id": "TEST", "drugs": ""},
    )
    assert no_drug_resp.status_code in (400, 422)  # 422 from FastAPI form validation
    print(f"  Got 400 as expected: {no_drug_resp.json()['detail']}")

    print(f"\n{'='*60}")
    print(f"  ALL MODULE 7 INTEGRATION TESTS PASSED!")
    print(f"{'='*60}")

    # Save sample output
    output_path = os.path.join(os.path.dirname(__file__), "sample_output.json")
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\n  Sample output saved to: {output_path}")


if __name__ == "__main__":
    test_full_pipeline()
