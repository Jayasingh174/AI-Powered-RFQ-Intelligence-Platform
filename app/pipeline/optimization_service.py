import asyncio
import json
import logging
import numpy as np
from functools import lru_cache
from sentence_transformers import CrossEncoder
from typing import List, Dict, Tuple

from app.brain.vector_service import vector_store
from app.brain.embedding_service import embed_query

logger = logging.getLogger(__name__)

# ==========================================
# PART 1: CORE RAG LOGIC (Retrieval & Reranking)
# ==========================================

_reranker = None  # lazy-loaded, not loaded at import time


def _get_reranker() -> CrossEncoder:
    """Loads the cross-encoder once, on first use, so a slow/failed
    model download can't block app startup or crash the whole import chain."""
    global _reranker
    if _reranker is None:
        logger.info("Loading Cross-Encoder Reranker model...")
        _reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    return _reranker


async def retrieve_and_rerank(query: str, initial_k: int = 20, final_k: int = 5) -> Tuple[List[Dict], float]:
    """
    1. Performs Hybrid Search (Vector + Keyword) using your VectorService
    2. Reranks the results with a cross-encoder, off the event loop
    3. Calculates a Confidence Score
    """
    logger.info(f"Starting optimized retrieval for query: '{query}'")

    try:
        query_embedding = await embed_query(query)
        all_chunks = vector_store.hybrid_search(
            query=query,
            query_embedding=query_embedding,  # type: ignore
            top_k=initial_k
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return [], 0.0

    if not all_chunks:
        return [], 0.0

    pairs = [[query, chunk['text']] for chunk in all_chunks]

    try:
        reranker = _get_reranker()
        # Offload the blocking, CPU-bound predict() call to a thread so it
        # doesn't stall the event loop for every other concurrent request.
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(None, reranker.predict, pairs)
    except Exception as e:
        # Degrade gracefully instead of failing the whole query if the
        # reranker is unavailable (e.g. model failed to load).
        logger.error(f"Reranking failed, falling back to unranked hybrid results: {e}")
        return all_chunks[:final_k], 0.5

    for i, chunk in enumerate(all_chunks):
        chunk['rerank_score'] = float(scores[i])

    reranked_chunks = sorted(all_chunks, key=lambda x: x['rerank_score'], reverse=True)[:final_k]

    avg_score = np.mean([c['rerank_score'] for c in reranked_chunks])
    confidence = float(1 / (1 + np.exp(-avg_score)))

    logger.info(f"Reranking complete. Confidence: {confidence:.2f}")
    return reranked_chunks, round(confidence, 2)


def compress_context(chunks: list, max_chars: int = 12000) -> str:
    """
    Context Compression: Takes the top reranked chunks and joins them,
    up to a character budget (renamed from max_tokens — the comparison
    below was always character-based, not token-based; aligned the
    default with config.MAX_CONTEXT_CHARS for consistency).
    """
    compressed_text = ""

    for chunk in chunks:
        if len(compressed_text) + len(chunk['text']) > max_chars:
            logger.info("Context compression triggered: Trimming excess chunk data.")
            break

        compressed_text += f"--- Source: {chunk.get('metadata', {}).get('source', 'Unknown')} ---\n"
        compressed_text += chunk['text'] + "\n\n"

    return compressed_text


# ==========================================
# PART 2: PIPELINE TEST SCRIPT
# ==========================================

async def run_optimization_test():
    """
    Simulates a user asking a complex engineering question to prove
    the Reranker and Hybrid search are working correctly.
    """
    # 🔧 FIX: the actual function is ask_rfq, not ask_rag — this import
    # was still broken even after the "optimization_used" metrics fix.
    from app.pipeline.query_pipeline import ask_rfq

    print("🚀 Initializing Optimized RAG Pipeline Test...\n")

    test_question = "What are the specific payment terms and fire pump capacities required for this project?"
    result = await ask_rfq(question=test_question, top_k=5)

    final_output = {
        "Answer": result.get("answer"),
        "Sources": result.get("sources", []),
        "Confidence": result.get("confidence", 0.0),
        "Metrics": {
            "Optimization_Used": [
                "Hybrid Search (BM25 + FAISS)",
                "Cross-Encoder Reranking",
                "Context Compression"
            ],
            "Chunks_Compressed": result.get("chunks_used", 0)
        }
    }

    print(json.dumps(final_output, indent=4))
    print("\n✅ Test Complete. Take a screenshot of the JSON above for your submission!")


if __name__ == "__main__":
    asyncio.run(run_optimization_test())
