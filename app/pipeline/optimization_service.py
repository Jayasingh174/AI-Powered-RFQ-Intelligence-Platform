import asyncio
import json
import logging
import numpy as np
from sentence_transformers import CrossEncoder
from typing import List, Dict, Tuple

# Import your existing services
from app.brain.vector_service import vector_store
from app.brain.embedding_service import embed_query  

logger = logging.getLogger(__name__)

# ==========================================
# PART 1: CORE RAG LOGIC (Retrieval & Reranking)
# ==========================================

# Load the Reranker model
logger.info("Loading Cross-Encoder Reranker model...")
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

async def retrieve_and_rerank(query: str, initial_k: int = 20, final_k: int = 5) -> Tuple[List[Dict], float]:
    """
    1. Performs Hybrid Search (Vector + Keyword) using your VectorService
    2. Reranks the results
    3. Calculates a Confidence Score
    """
    logger.info(f"Starting optimized retrieval for query: '{query}'")

    # 1. HYBRID SEARCH (Cast a wide net using your unified method)
    try:
        # First, convert the text query into numbers (embedding)
        query_embedding = await embed_query(query)
        
        # Now pass both the text and the embedding to your vector store
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

    # 2. RERANKING (The Judge)
    # Prepare pairs: [[query, chunk_text_1], [query, chunk_text_2], ...]
    pairs = [[query, chunk['text']] for chunk in all_chunks]
    
    # Get scores from the ML model
    scores = reranker.predict(pairs)
    
    # Attach scores to the chunks
    for i, chunk in enumerate(all_chunks):
        chunk['rerank_score'] = float(scores[i])
    
    # Sort by the new score (highest first) and keep only the top `final_k`
    reranked_chunks = sorted(all_chunks, key=lambda x: x['rerank_score'], reverse=True)[:final_k]

    # 3. CONFIDENCE SCORE (0.0 to 1.0)
    avg_score = np.mean([c['rerank_score'] for c in reranked_chunks])
    confidence = float(1 / (1 + np.exp(-avg_score)))

    logger.info(f"Reranking complete. Confidence: {confidence:.2f}")
    return reranked_chunks, round(confidence, 2)

def compress_context(chunks: list, max_tokens: int = 3000) -> str:
    """
    Context Compression: Takes the top reranked chunks and joins them.
    If the combined text is too large, it smartly trims the least important 
    chunks from the bottom up.
    """
    compressed_text = ""
    
    for chunk in chunks:
        if len(compressed_text) + len(chunk['text']) > max_tokens:
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
    # Imported here to avoid circular imports at the top of the file
    from app.pipeline.query_pipeline import ask_rfq

    print("🚀 Initializing Optimized RAG Pipeline Test...\n")
    
    # A specific question that requires good retrieval
    test_question = "What are the specific payment terms and fire pump capacities required for this project?"
    
    # Run the pipeline
    result = await ask_rfq(question=test_question, top_k=5)
    
    # Format the output exactly how Knowforth Tech wants it
    final_output = {
        "Answer": result.get("answer"),
        "Sources": result.get("sources", []),
        "Confidence": result.get("confidence", 0.0),
        "Metrics": {
            "Optimization_Used": result.get("optimization_used", []),
            "Chunks_Compressed": result.get("chunks_used", 0)
        }
    }
    
    # Print it beautifully to the terminal so you can screenshot it
    print(json.dumps(final_output, indent=4))
    
    print("\n✅ Test Complete. Take a screenshot of the JSON above for your submission!")

if __name__ == "__main__":
    asyncio.run(run_optimization_test())