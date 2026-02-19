"""Test Module 6: LLM Explanation Generator — verify template and structure."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.llm_generator import (
    ExplanationInput, LLMGenerator, TemplateGenerator
)


def test_llm_generator():
    print("=== Module 6: LLM Explanation Generator Tests ===\n")

    # Test with template mode (no API key)
    gen = LLMGenerator()
    mode = gen.initialize()  # No API key = template mode
    print(f"Active mode: {mode}")
    assert mode == "template"

    # Test 1: CYP2D6 IM + Codeine
    inp1 = ExplanationInput(
        gene="CYP2D6",
        diplotype="*1/*4",
        phenotype="IM",
        phenotype_label="Intermediate Metabolizer",
        drug="CODEINE",
        risk_label="Adjust",
        severity="moderate",
        recommendation="Use codeine with caution at reduced dose.",
        rag_contexts=["CYP2D6 metabolizes codeine to morphine via O-demethylation."],
        detected_variants=[
            {"rsid": "rs3892097", "genotype": "0/1"},
            {"rsid": "rs1065852", "genotype": "0/1"},
        ],
    )

    out1 = gen.generate(inp1)
    print(f"\n[Test 1] CYP2D6 *1/*4 + CODEINE:")
    print(f"  Mode: {out1.mode}")
    print(f"  Summary: {out1.summary[:120]}...")
    print(f"  Mechanism: {out1.mechanism[:120]}...")
    assert out1.mode == "template"
    assert "CYP2D6" in out1.summary
    assert "*1/*4" in out1.summary
    assert len(out1.mechanism) > 50

    # Test 2: DPYD PM + Fluorouracil (critical)
    inp2 = ExplanationInput(
        gene="DPYD",
        diplotype="*1/*2A",
        phenotype="IM",
        phenotype_label="Intermediate Metabolizer",
        drug="FLUOROURACIL",
        risk_label="Adjust",
        severity="critical",
        recommendation="Reduce fluorouracil dose by 50%.",
        rag_contexts=[],
        detected_variants=[{"rsid": "rs3918290", "genotype": "0/1"}],
    )

    out2 = gen.generate(inp2)
    print(f"\n[Test 2] DPYD *1/*2A + FLUOROURACIL:")
    print(f"  Summary: {out2.summary[:120]}...")
    assert "DPYD" in out2.summary

    # Test 3: SLCO1B1 + Simvastatin
    inp3 = ExplanationInput(
        gene="SLCO1B1",
        diplotype="*1A/*5",
        phenotype="DF",
        phenotype_label="Decreased Function",
        drug="SIMVASTATIN",
        risk_label="Adjust",
        severity="high",
        recommendation="Use lower dose simvastatin or switch to pravastatin.",
        rag_contexts=[],
        detected_variants=[{"rsid": "rs4149056", "genotype": "0/1"}],
    )

    out3 = gen.generate(inp3)
    print(f"\n[Test 3] SLCO1B1 *1A/*5 + SIMVASTATIN:")
    print(f"  Summary: {out3.summary[:120]}...")
    assert "SLCO1B1" in out3.summary

    # Test 4: Toxic risk
    inp4 = ExplanationInput(
        gene="CYP2D6",
        diplotype="*1xN/*1",
        phenotype="UM",
        phenotype_label="Ultrarapid Metabolizer",
        drug="CODEINE",
        risk_label="Toxic",
        severity="critical",
        recommendation="AVOID codeine.",
        rag_contexts=[],
        detected_variants=[],
    )

    out4 = gen.generate(inp4)
    print(f"\n[Test 4] CYP2D6 UM + CODEINE (Toxic):")
    print(f"  Summary: {out4.summary[:120]}...")
    assert "Toxic" in out4.summary or "toxicity" in out4.mechanism.lower()

    print(f"\n=== ALL MODULE 6 TESTS PASSED ===")


if __name__ == "__main__":
    test_llm_generator()
