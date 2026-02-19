"""
PharmaGuard — Knowledge Ingestion Script for Pinecone.

Reads the local PGx knowledge base, generates Gemini embeddings,
and upserts vectors into a Pinecone index for semantic retrieval.

Usage:
    python scripts/ingest_knowledge.py

Requires:
    GEMINI_API_KEY and PINECONE_API_KEY in .env
"""

import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()


def main():
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    pinecone_key = os.getenv("PINECONE_API_KEY", "")
    index_name = os.getenv("PINECONE_INDEX", "pharmaguard-pgx")

    if not gemini_key or not pinecone_key:
        print("ERROR: GEMINI_API_KEY and PINECONE_API_KEY must be set in .env")
        sys.exit(1)

    # ── Load knowledge base ──────────────────────────────────
    kb_path = Path(__file__).resolve().parent.parent / "app" / "data" / "pgx_knowledge_base.json"
    with open(kb_path, "r", encoding="utf-8") as f:
        documents = json.load(f)

    print(f"Loaded {len(documents)} documents from knowledge base.")

    # ── Setup Gemini ─────────────────────────────────────────
    import google.generativeai as genai

    genai.configure(api_key=gemini_key)
    print("Gemini configured for embedding generation.")

    # ── Setup Pinecone ───────────────────────────────────────
    from pinecone import Pinecone, ServerlessSpec

    pc = Pinecone(api_key=pinecone_key)

    # Create index if it doesn't exist
    existing = [idx.name for idx in pc.list_indexes()]
    if index_name not in existing:
        print(f"Creating Pinecone index: {index_name}")
        pc.create_index(
            name=index_name,
            dimension=768,  # Gemini embedding-001 output dimension
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        # Wait for index to be ready
        time.sleep(10)
    else:
        print(f"Pinecone index '{index_name}' already exists.")

    index = pc.Index(index_name)

    # ── Generate embeddings and upsert ───────────────────────
    vectors = []

    for doc in documents:
        doc_id = doc["id"]
        text = f"{doc.get('title', '')} {doc.get('content', '')}"

        print(f"  Embedding: {doc_id} ({len(text)} chars)...")

        result = genai.embed_content(
            model="models/embedding-001",
            content=text,
            task_type="retrieval_document",
        )
        embedding = result["embedding"]

        metadata = {
            "title": doc.get("title", ""),
            "content": doc.get("content", "")[:1000],
            "gene": doc.get("gene", ""),
            "drug": doc.get("drug", ""),
        }

        vectors.append({
            "id": doc_id,
            "values": embedding,
            "metadata": metadata,
        })

        time.sleep(0.5)  # Rate limiting

    # Upsert in batch
    print(f"\nUpserting {len(vectors)} vectors to Pinecone...")
    index.upsert(vectors=vectors)

    print(f"\nDone! {len(vectors)} documents ingested into '{index_name}'.")
    print(f"Index stats: {index.describe_index_stats()}")


if __name__ == "__main__":
    main()
