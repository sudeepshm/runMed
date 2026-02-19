"""Quick test script for the /analyze endpoint."""

import httpx
import json
import sys

BASE_URL = "http://127.0.0.1:8000"
VCF_PATH = "app/data/sample_vcfs/sample.vcf"


def test_health():
    r = httpx.get(f"{BASE_URL}/health")
    print(f"[HEALTH] {r.status_code}: {r.json()}")
    assert r.status_code == 200


def test_analyze():
    with open(VCF_PATH, "rb") as f:
        r = httpx.post(
            f"{BASE_URL}/analyze",
            files={"vcf_file": ("sample.vcf", f, "text/plain")},
            data={"patient_id": "PATIENT_001", "drugs": "CODEINE,WARFARIN"},
        )

    print(f"\n[ANALYZE] Status: {r.status_code}")

    if r.status_code == 200:
        result = r.json()
        print(f"  Overall status: {result['status']}")
        print(f"  Number of drug results: {len(result['results'])}")

        for dr in result["results"]:
            print(f"\n  Drug: {dr['drug']}")
            print(f"    Variants detected: {len(dr['detected_variants'])}")
            print(f"    Genes found: {dr['pharmacogenomic_profile']['primary_gene']}")
            qm = dr["quality_metrics"]
            print(f"    Total variants: {qm['total_variants_extracted']}")
            print(f"    Pharmacogenes: {qm['pharmacogenes_found']}")

            # Show first 3 variants
            for v in dr["detected_variants"][:3]:
                print(f"      {v['rsid']}  GT={v.get('genotype','?')}  AD={v.get('allelic_depth','?')}")

        # Full JSON for first drug
        print(f"\n[FULL JSON — first drug]:")
        print(json.dumps(result["results"][0], indent=2, default=str))
    else:
        print(f"  Error: {r.text}")


if __name__ == "__main__":
    test_health()
    test_analyze()
    print("\n✅ All tests passed!")
