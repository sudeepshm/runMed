"""
PharmaGuard — RAG Context Engine (Module 5).

Retrieves semantically relevant clinical guidelines and biological
mechanisms for detected pharmacogenomic findings.

Two backends:
  1. LOCAL (default): TF-IDF keyword matching against the built-in
     PGx knowledge base — works offline, no API keys needed.
  2. PINECONE (optional): Semantic vector search against Pinecone
     index with Gemini embeddings — richer retrieval when configured.

The engine auto-selects the best available backend on startup.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KNOWLEDGE_JSON = DATA_DIR / "pgx_knowledge_base.json"


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class RetrievedContext:
    """A single chunk of retrieved context."""
    doc_id: str
    title: str
    content: str
    relevance_score: float  # 0.0–1.0
    gene: str = ""
    drug: str = ""
    source: str = "local"   # "local" or "pinecone"


@dataclass
class RAGResult:
    """Result from the RAG context engine."""
    contexts: List[RetrievedContext] = field(default_factory=list)
    query: str = ""
    backend: str = "local"  # "local" or "pinecone"
    total_docs_searched: int = 0


# ── Local knowledge base (TF-IDF) ────────────────────────────────────

class LocalKnowledgeBase:
    """
    Simple TF-IDF-based local knowledge retrieval engine.
    No external dependencies — works entirely offline.
    """

    def __init__(self):
        self.documents: List[dict] = []
        self.doc_vectors: List[Dict[str, float]] = []
        self.idf: Dict[str, float] = {}
        self._loaded = False

    def load(self) -> None:
        """Load and index the PGx knowledge base."""
        if self._loaded:
            return

        if not KNOWLEDGE_JSON.exists():
            logger.warning("Knowledge base not found: %s", KNOWLEDGE_JSON)
            return

        with open(KNOWLEDGE_JSON, "r", encoding="utf-8") as f:
            self.documents = json.load(f)

        # Build TF-IDF index
        self._build_index()
        self._loaded = True
        logger.info(
            "Local knowledge base loaded: %d documents", len(self.documents)
        )

    def search(
        self, query: str, top_k: int = 3, gene: str = "", drug: str = ""
    ) -> List[RetrievedContext]:
        """
        Search the knowledge base using TF-IDF + gene/drug boosting.

        Args:
            query: Search query text.
            top_k: Number of results to return.
            gene: Optional gene filter/boost.
            drug: Optional drug filter/boost.

        Returns:
            List of RetrievedContext sorted by relevance.
        """
        self.load()

        if not self.documents:
            return []

        query_vector = self._text_to_tfidf(query)
        scored: List[Tuple[float, int]] = []

        for idx, doc_vec in enumerate(self.doc_vectors):
            # Cosine similarity
            score = self._cosine_similarity(query_vector, doc_vec)

            # Boost if gene/drug matches
            doc = self.documents[idx]
            if gene and doc.get("gene", "").upper() == gene.upper():
                score *= 1.5
            if drug and doc.get("drug", "").upper() == drug.upper():
                score *= 1.8

            scored.append((score, idx))

        # Sort by score descending
        scored.sort(key=lambda x: -x[0])

        results: List[RetrievedContext] = []
        for score, idx in scored[:top_k]:
            if score < 0.01:
                continue
            doc = self.documents[idx]
            results.append(
                RetrievedContext(
                    doc_id=doc.get("id", f"doc_{idx}"),
                    title=doc.get("title", ""),
                    content=doc.get("content", ""),
                    relevance_score=min(score, 1.0),
                    gene=doc.get("gene", ""),
                    drug=doc.get("drug", ""),
                    source="local",
                )
            )

        return results

    # ── TF-IDF internals ──────────────────────────────────────

    def _tokenize(self, text: str) -> List[str]:
        """Simple lowercase tokenization with stop word removal."""
        tokens = re.findall(r"[a-z0-9*]+", text.lower())
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "of", "in", "to", "for", "with", "on", "at", "by", "from",
            "as", "into", "through", "during", "and", "or", "but", "not",
            "if", "then", "than", "that", "this", "it", "its", "which",
        }
        return [t for t in tokens if t not in stop_words and len(t) > 1]

    def _build_index(self) -> None:
        """Build TF-IDF vectors for all documents."""
        # Document frequency
        df: Counter = Counter()
        doc_tokens: List[List[str]] = []

        for doc in self.documents:
            text = f"{doc.get('title', '')} {doc.get('content', '')}"
            tokens = self._tokenize(text)
            doc_tokens.append(tokens)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                df[token] += 1

        n_docs = len(self.documents)

        # IDF
        self.idf = {
            token: math.log((n_docs + 1) / (count + 1)) + 1
            for token, count in df.items()
        }

        # TF-IDF vectors
        self.doc_vectors = []
        for tokens in doc_tokens:
            tf = Counter(tokens)
            max_tf = max(tf.values()) if tf else 1
            vector: Dict[str, float] = {}
            for token, count in tf.items():
                normalized_tf = 0.5 + 0.5 * (count / max_tf)
                vector[token] = normalized_tf * self.idf.get(token, 1.0)
            self.doc_vectors.append(vector)

    def _text_to_tfidf(self, text: str) -> Dict[str, float]:
        """Convert query text to a TF-IDF vector."""
        tokens = self._tokenize(text)
        tf = Counter(tokens)
        max_tf = max(tf.values()) if tf else 1
        vector: Dict[str, float] = {}
        for token, count in tf.items():
            normalized_tf = 0.5 + 0.5 * (count / max_tf)
            vector[token] = normalized_tf * self.idf.get(token, 1.0)
        return vector

    @staticmethod
    def _cosine_similarity(
        vec_a: Dict[str, float], vec_b: Dict[str, float]
    ) -> float:
        """Compute cosine similarity between two sparse vectors."""
        # Dot product
        common_keys = set(vec_a.keys()) & set(vec_b.keys())
        if not common_keys:
            return 0.0

        dot = sum(vec_a[k] * vec_b[k] for k in common_keys)

        # Magnitudes
        mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
        mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (mag_a * mag_b)


# ── Pinecone backend (optional) ──────────────────────────────────────

class PineconeKnowledgeBase:
    """
    Semantic vector search using Pinecone + Gemini embeddings.
    Only activated when GEMINI_API_KEY and PINECONE_API_KEY are set.
    """

    def __init__(self, gemini_api_key: str, pinecone_api_key: str, index_name: str):
        self.gemini_api_key = gemini_api_key
        self.pinecone_api_key = pinecone_api_key
        self.index_name = index_name
        self._index = None
        self._model = None
        self._available = False

    def initialize(self) -> bool:
        """Try to connect to Pinecone. Returns True if successful."""
        try:
            from pinecone import Pinecone
            import google.generativeai as genai

            genai.configure(api_key=self.gemini_api_key)
            self._model = genai

            pc = Pinecone(api_key=self.pinecone_api_key)

            # Check if index exists
            existing = [idx.name for idx in pc.list_indexes()]
            if self.index_name in existing:
                self._index = pc.Index(self.index_name)
                self._available = True
                logger.info("Pinecone connected: index=%s", self.index_name)
            else:
                logger.warning(
                    "Pinecone index '%s' not found. Available: %s",
                    self.index_name,
                    existing,
                )
                self._available = False

            return self._available

        except Exception as exc:
            logger.warning("Pinecone initialization failed: %s", exc)
            self._available = False
            return False

    def search(
        self, query: str, top_k: int = 3, gene: str = "", drug: str = ""
    ) -> List[RetrievedContext]:
        """Semantic search using Gemini embeddings + Pinecone."""
        if not self._available or not self._index:
            return []

        try:
            # Generate query embedding with Gemini
            result = self._model.embed_content(
                model="models/embedding-001",
                content=query,
                task_type="retrieval_query",
            )
            query_embedding = result["embedding"]

            # Build metadata filter
            metadata_filter = {}
            if gene:
                metadata_filter["gene"] = gene.upper()
            if drug:
                metadata_filter["drug"] = drug.upper()

            # Query Pinecone
            query_kwargs = {
                "vector": query_embedding,
                "top_k": top_k,
                "include_metadata": True,
            }
            if metadata_filter:
                query_kwargs["filter"] = metadata_filter

            results = self._index.query(**query_kwargs)

            contexts: List[RetrievedContext] = []
            for match in results.get("matches", []):
                meta = match.get("metadata", {})
                contexts.append(
                    RetrievedContext(
                        doc_id=match.get("id", ""),
                        title=meta.get("title", ""),
                        content=meta.get("content", ""),
                        relevance_score=float(match.get("score", 0)),
                        gene=meta.get("gene", ""),
                        drug=meta.get("drug", ""),
                        source="pinecone",
                    )
                )

            return contexts

        except Exception as exc:
            logger.warning("Pinecone search failed: %s", exc)
            return []


# ── Unified RAG Engine ────────────────────────────────────────────────

class RAGEngine:
    """
    Unified RAG context engine that auto-selects the best backend.

    Priority:
      1. Pinecone (if configured and connected)
      2. Local TF-IDF knowledge base (always available)
    """

    def __init__(self):
        self.local_kb = LocalKnowledgeBase()
        self.pinecone_kb: Optional[PineconeKnowledgeBase] = None
        self.active_backend = "local"

    def initialize(
        self,
        gemini_api_key: str = "",
        pinecone_api_key: str = "",
        pinecone_index: str = "pharmaguard-pgx",
    ) -> str:
        """
        Initialize the RAG engine. Returns the name of the active backend.
        """
        # Always load local KB
        self.local_kb.load()

        # Try Pinecone if keys are provided
        if gemini_api_key and pinecone_api_key:
            self.pinecone_kb = PineconeKnowledgeBase(
                gemini_api_key, pinecone_api_key, pinecone_index
            )
            if self.pinecone_kb.initialize():
                self.active_backend = "pinecone"
                logger.info("RAG backend: Pinecone (semantic search)")
            else:
                self.active_backend = "local"
                logger.info("RAG backend: Local (Pinecone unavailable)")
        else:
            self.active_backend = "local"
            logger.info("RAG backend: Local (no API keys)")

        return self.active_backend

    def retrieve(
        self,
        gene: str,
        diplotype: str,
        drug: str,
        phenotype: str = "",
        top_k: int = 3,
    ) -> RAGResult:
        """
        Retrieve relevant clinical context for a gene–drug finding.

        Args:
            gene: Gene symbol (e.g. "CYP2D6")
            diplotype: Diplotype string (e.g. "*1/*4")
            drug: Drug name (e.g. "CODEINE")
            phenotype: Phenotype (e.g. "IM")
            top_k: Number of context chunks to retrieve.

        Returns:
            RAGResult with retrieved context chunks.
        """
        # Build a rich query
        query = (
            f"{gene} {diplotype} {phenotype} {drug} "
            f"pharmacogenomics metabolism clinical recommendation "
            f"mechanism dosing guideline"
        )

        result = RAGResult(query=query, backend=self.active_backend)

        # Try Pinecone first
        if self.active_backend == "pinecone" and self.pinecone_kb:
            contexts = self.pinecone_kb.search(query, top_k, gene=gene, drug=drug)
            if contexts:
                result.contexts = contexts
                result.total_docs_searched = top_k * 5  # approximate
                return result

        # Fallback to local KB
        result.backend = "local"
        result.contexts = self.local_kb.search(query, top_k, gene=gene, drug=drug)
        result.total_docs_searched = len(self.local_kb.documents)

        return result


# ── Module-level singleton ────────────────────────────────────────────

_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    """Get or create the RAG engine singleton."""
    global _engine
    if _engine is None:
        _engine = RAGEngine()

        # Try to auto-configure from environment
        from app.config import get_settings
        settings = get_settings()
        _engine.initialize(
            gemini_api_key=settings.GEMINI_API_KEY,
            pinecone_api_key=settings.PINECONE_API_KEY,
            pinecone_index=settings.PINECONE_INDEX,
        )

    return _engine


def retrieve_context(
    gene: str, diplotype: str, drug: str, phenotype: str = "", top_k: int = 3
) -> RAGResult:
    """Convenience function: retrieve context using the global engine."""
    engine = get_rag_engine()
    return engine.retrieve(gene, diplotype, drug, phenotype, top_k)
