"""
RFQ AI System - Query & Search Router
Handles direct AI questions (Chatbot) and raw document search/retrieval operations.
"""

import copy
import logging
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.pipeline.query_pipeline import ask_rfq
from app.pipeline.optimization_service import retrieve_and_rerank
from app.models.query_model import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query & Search"])


class SearchRequest(BaseModel):
    query: str
    initial_k: Optional[int] = 20
    final_k: Optional[int] = 5


class SearchResponse(BaseModel):
    status: str
    query: str
    results: List[Dict]
    confidence_score: float


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

        # 🔧 FIX: forward top_k instead of silently discarding it
        result = await ask_rfq(question=request.question, top_k=request.top_k)

        return result

    except Exception as e:
        logger.error(f"❌ API Query Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"The AI query failed to process: {str(e)}"
        )


@router.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """
    Direct Search Endpoint:
    Executes a hybrid search query and reranks the results without generating an AI response.
    Useful for debugging, UI document lists, or advanced data retrieval.
    """
    logger.info(f"🔍 Executing raw search for query: '{request.query}'")

    try:
        initial_k = request.initial_k if request.initial_k is not None else 20
        final_k = request.final_k if request.final_k is not None else 5

        results, score = await retrieve_and_rerank(
            query=request.query,
            initial_k=initial_k,
            final_k=final_k
        )

        # 🔧 FIX: deep-copy before this leaves retrieve_and_rerank's
        # ownership. retrieve_and_rerank() attaches 'rerank_score'
        # directly onto the dicts returned by vector_store.hybrid_search(),
        # which are live references into vector_store.documents — the
        # actual persisted index, not a snapshot. Without copying, every
        # search request permanently contaminates the index with the last
        # query's relevance score, which then gets written to disk on the
        # next save_index() and can race with concurrent requests.
        safe_results = [copy.deepcopy(r) for r in results]

        return SearchResponse(
            status="success",
            query=request.query,
            results=safe_results,
            confidence_score=score
        )

    except Exception as e:
        logger.error(f"❌ Search routing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search execution failed: {str(e)}")
