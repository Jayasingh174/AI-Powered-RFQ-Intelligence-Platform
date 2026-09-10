"""
RFQ AI System - Query Pipeline
Implements the RAG (Retrieval-Augmented Generation) flow:
1. Embed the user's question.
2. Search and RERANK the vector database for relevant chunks.
3. Build a context window for the LLM.
4. Generate a grounded answer based on the retrieved documents.
"""

import os
import logging
from typing import Dict, Any, List, Optional

from app.brain.embedding_service import embed_query
from app.brain.llm_service import ask_llm
from app.pipeline.optimization_service import retrieve_and_rerank, compress_context
from app.config import MAX_CONTEXT_CHARS  # 🔧 FIX: use config, not a hardcoded default

logger = logging.getLogger(__name__)


async def ask_rfq(question: str, top_k: int = 8, max_context_chars: int = MAX_CONTEXT_CHARS) -> Dict[str, Any]:
    """
    Orchestrates the full RFQ query pipeline using Reranking and Context Compression.
    """
    try:
        logger.info(f"RFQ Query received: '{question}'")

        logger.info("Engaging Optimization Service (Hybrid + Rerank)...")
        results, confidence_score = await retrieve_and_rerank(
            query=question,
            initial_k=20,
            final_k=top_k
        )

        logger.info(f"Retrieved {len(results)} relevant document chunks. Confidence: {confidence_score}")

        if not results:
            return _build_response(question, "No relevant information found in the documents.", confidence=0.0)

        unique_sources = set()
        for r in results:
            meta = r.get("metadata", {}) if isinstance(r, dict) else {}
            source_path = meta.get("source", "")
            if isinstance(source_path, str) and source_path.strip():
                filename = os.path.basename(source_path.strip())
                if filename.lower() not in ["", "unknown", "none"]:
                    unique_sources.add(filename)
        sources = list(unique_sources)

        # 🔧 FIX: build context and count actually-included chunks together,
        # so chunks_used reflects what compression kept, not what was retrieved.
        context, chunks_used = _compress_and_count(results, max_context_chars)

        if len(context.strip()) < 20:
            logger.warning(f"⚠️ Weak context detected for query: '{question}'")
            return _build_response(
                question,
                "I found some data, but it's not enough to form a complete, accurate answer.",
                sources, chunks_used, confidence_score, context
            )

        logger.info("Sending optimized context to LLM...")
        answer = await ask_llm(question, context)
        logger.info("✅ Grounded answer generated successfully.")

        return _build_response(question, answer, sources, chunks_used, confidence_score, context)

    except Exception as e:
        logger.exception(f"❌ Query processing failed: {str(e)}")
        return _build_response(
            question,
            "I encountered an error while analyzing the documents.",
            error=str(e)
        )


def _compress_and_count(chunks: list, max_chars: int) -> tuple[str, int]:
    """
    Wraps compress_context() so chunks_used reflects what actually made
    it into the context, not the raw count of chunks retrieved.
    """
    context = compress_context(chunks, max_tokens=max_chars)

    # Re-derive the included count by matching source markers compress_context
    # writes for each chunk it keeps, rather than duplicating its trimming logic.
    included = context.count("--- Source:")
    return context, included


def _build_response(
    question: str,
    answer: str,
    sources: Optional[List[str]] = None,
    chunks_used: int = 0,
    confidence: float = 0.0,
    context: str = "",
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Helper function to ensure the API always returns a consistent JSON schema,
    even if the pipeline fails early.
    """
    response = {
        "question": question,
        "answer": answer,
        "sources": sources or [],
        "chunks_used": chunks_used,
        "confidence": confidence,
        "context_preview": context[:500] if context else ""
    }
    if error:
        response["error"] = error

    return response
