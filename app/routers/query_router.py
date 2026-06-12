"""
RFQ AI System - Query & Search Router
Handles direct AI questions (Chatbot) and raw document search/retrieval operations.
"""

import logging
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# --- Core Pipelines & Logic ---
from app.pipeline.query_pipeline import ask_rfq

# 🔥 THE FIX: Pointing to the correct optimized_rag file
from app.pipeline.optimization_service import retrieve_and_rerank

# --- Models ---
from app.models.query_model import QueryRequest, QueryResponse

# Configure logger for this module
logger = logging.getLogger(__name__)

# Define the router
router = APIRouter(prefix="/query", tags=["Query & Search"])

# ==========================================
# 📝 INLINE MODELS (For Search Endpoint)
# ==========================================
class SearchRequest(BaseModel):
    query: str
    initial_k: Optional[int] = 20
    final_k: Optional[int] = 5

class SearchResponse(BaseModel):
    status: str
    query: str
    results: List[Dict]
    confidence_score: float

# ==========================================
# 🤖 CHATBOT QUERY ENDPOINT (/ask)
# ==========================================
@router.post("/ask", response_model=QueryResponse)
async def query_rfq(request: QueryRequest):
    """
    Primary API Endpoint for Chatbot:
    1. Receives a user question via POST.
    2. Awaits the RAG pipeline to generate an answer based on document context.
    3. Returns a structured JSON response with the answer and sources.
    """
    try:
        logger.info(f"🤖 Processing user query: '{request.question}'")

        # Execute the end-to-end RAG pipeline
        result = await ask_rfq(question=request.question)

        return result

    except Exception as e:
        logger.error(f"❌ API Query Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"The AI query failed to process: {str(e)}"
        )

# ==========================================
# 🔍 RAW SEARCH & RERANK ENDPOINT (/search)
# ==========================================
@router.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """
    Direct Search Endpoint:
    Executes a hybrid search query and reranks the results without generating an AI response.
    Useful for debugging, UI document lists, or advanced data retrieval.
    """
    logger.info(f"🔍 Executing raw search for query: '{request.query}'")
    
    try:
        # Await the async function from optimized_rag.py
        # Ensure initial_k/final_k are ints (fallback to defaults if None)
        initial_k = request.initial_k if request.initial_k is not None else 20
        final_k = request.final_k if request.final_k is not None else 5

        results, score = await retrieve_and_rerank(
            query=request.query,
            initial_k=initial_k,
            final_k=final_k
        )

        return SearchResponse(
            status="success",
            query=request.query,
            results=results,
            confidence_score=score
        )

    except Exception as e:
        logger.error(f"❌ Search routing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search execution failed: {str(e)}")