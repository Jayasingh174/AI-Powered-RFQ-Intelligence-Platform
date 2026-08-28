from pydantic import BaseModel, Field
from typing import List, Optional

class QueryRequest(BaseModel):
    """
    Standard user query structure.
    """
    question: str = Field(..., json_schema_extra={"example": "What is the fire pump capacity?"})
    top_k: int = Field(default=8, ge=1, le=20)

class QueryResponse(BaseModel):
    """
    Standardized response for the Document Intelligence pipeline.
    Matches the output of ask_rag() exactly — field names are kept
    identical to the keys in query_pipeline.py's _build_response()
    dict, since FastAPI's response_model validates a plain dict by
    field name and silently drops anything that doesn't match.
    """
    question: str
    answer: str
    sources: List[str] = []
    chunks_used: int = 0
    context_preview: Optional[str] = None

    # Added: ask_rag() always computes this (from the cross-encoder
    # reranker) and passes it into _build_response(), but there was no
    # field here to receive it, so it was silently dropped on every call.
    confidence: float = 0.0

    error: Optional[str] = None

    # Removed: 'project_name'. ask_rag() has no concept of a project —
    # it's a corpus-wide Q&A pipeline, not a per-project one — so this
    # field could never be populated by anything except its own
    # "Unknown Project" default. It was dead weight, not a bug fix target.

    # Pydantic V2 configuration style
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "question": "What is the fire pump capacity?",
                "answer": "The fire pump capacity is 500 GPM as per the RAG specifications.",
                "sources": ["RAG_Mall_Project.pdf"],
                "chunks_used": 3,
                "confidence": 0.87
            }
        }
    }
