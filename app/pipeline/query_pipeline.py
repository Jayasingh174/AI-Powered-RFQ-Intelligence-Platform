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

# 🔥 Import optimization service
from app.pipeline.optimization_service import retrieve_and_rerank, compress_context

logger = logging.getLogger(__name__)

async def ask_rfq(question: str, top_k: int = 8, max_context_chars: int = 4000) -> Dict[str, Any]:
    """
    Orchestrates the full RFQ query pipeline using Reranking and Context Compression.
    """
    try:
        logger.info(f"RFQ Query received: '{question}'")

        # --------------------------------------------------
        # 1️⃣ & 2️⃣ STAGE: Hybrid Retrieval + Cross-Encoder Reranking
        # --------------------------------------------------
        logger.info("Engaging Optimization Service (Hybrid + Rerank)...")
        results, confidence_score = await retrieve_and_rerank(
            query=question, 
            initial_k=20,     # Cast a wide net first (BM25 + Vector)
            final_k=top_k     # Keep only the absolute best for the LLM
        )

        logger.info(f"Retrieved {len(results)} relevant document chunks. Confidence: {confidence_score}")

        # Early exit if database returns nothing
        if not results:
            return _build_response(question, "No relevant information found in the documents.", confidence=0.0)

        # --------------------------------------------------
        # 3️⃣ STAGE: Process results (Metadata Extraction)
        # --------------------------------------------------
        # OPTIMIZATION: Using a 'set' automatically prevents duplicate filenames efficiently
        unique_sources = set()
        
        for r in results:
            # Safely grab metadata, defaulting to empty dict if missing or malformed
            meta = r.get("metadata", {}) if isinstance(r, dict) else {}
            source_path = meta.get("source", "")

            if isinstance(source_path, str) and source_path.strip():
                filename = os.path.basename(source_path.strip())
                if filename.lower() not in ["", "unknown", "none"]:
                    unique_sources.add(filename)

        sources = list(unique_sources)

        # --------------------------------------------------
        # 4️⃣ STAGE: Smart context building (Compression)
        # --------------------------------------------------
        context = compress_context(results, max_tokens=max_context_chars)
        chunks_used = len(results)

        # --------------------------------------------------
        # 5️⃣ STAGE: Context Guard
        # --------------------------------------------------
        # If the compressor trimmed everything because it was junk text
        if len(context.strip()) < 20: 
            logger.warning(f"⚠️ Weak context detected for query: '{question}'")
            return _build_response(
                question, 
                "I found some data, but it's not enough to form a complete, accurate answer.", 
                sources, chunks_used, confidence_score, context
            )

        # --------------------------------------------------
        # 6️⃣ STAGE: Generate Answer via LLM
        # --------------------------------------------------
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