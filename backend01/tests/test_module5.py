"""Test Module 5: RAG Context Engine — verify local knowledge retrieval."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Reset the singleton so we test fresh
import app.services.rag_engine as rag_mod
rag_mod._engine = None

from app.services.rag_engine import RAGEngine


def test_rag_engine():
    print("=== Module 5: RAG Context Engine Tests ===\n")

    engine = RAGEngine()
    backend = engine.initialize()  # No API keys = local backend
    print(f"Active backend: {backend}")
    assert backend == "local", f"Expected local, got {backend}"

    # Test 1: CYP2D6 + Codeine query
    result = engine.retrieve(gene="CYP2D6", diplotype="*1/*4", drug="CODEINE", phenotype="IM")
    print(f"\n[Test 1] CYP2D6 *1/*4 + CODEINE:")
    print(f"  Backend: {result.backend}")
    print(f"  Contexts retrieved: {len(result.contexts)}")
    for ctx in result.contexts:
        print(f"    - {ctx.title} (score={ctx.relevance_score:.3f}, gene={ctx.gene})")
    assert len(result.contexts) > 0, "No contexts retrieved for CYP2D6 + CODEINE"

    # Verify top result is CYP2D6-related
    top = result.contexts[0]
    assert "CYP2D6" in top.gene or "CYP2D6" in top.content, "Top result not CYP2D6-related"

    # Test 2: CYP2C9 + Warfarin query
    result2 = engine.retrieve(gene="CYP2C9", diplotype="*1/*2", drug="WARFARIN", phenotype="IM")
    print(f"\n[Test 2] CYP2C9 *1/*2 + WARFARIN:")
    print(f"  Contexts retrieved: {len(result2.contexts)}")
    for ctx in result2.contexts:
        print(f"    - {ctx.title} (score={ctx.relevance_score:.3f})")
    assert len(result2.contexts) > 0

    # Test 3: DPYD + Fluorouracil query
    result3 = engine.retrieve(gene="DPYD", diplotype="*1/*2A", drug="FLUOROURACIL")
    print(f"\n[Test 3] DPYD *1/*2A + FLUOROURACIL:")
    print(f"  Contexts retrieved: {len(result3.contexts)}")
    for ctx in result3.contexts:
        print(f"    - {ctx.title} (score={ctx.relevance_score:.3f})")
    assert len(result3.contexts) > 0

    # Test 4: Verify context content is non-empty
    for ctx in result.contexts:
        assert len(ctx.content) > 50, f"Context too short: {ctx.doc_id}"

    print(f"\n=== ALL MODULE 5 TESTS PASSED ===")


if __name__ == "__main__":
    test_rag_engine()
