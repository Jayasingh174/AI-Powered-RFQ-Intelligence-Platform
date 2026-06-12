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
    Matches the output of ask_rfq() exactly.
    """
    question: str
    answer: str
    sources: List[str] = []
    chunks_used: int = 0
    context_preview: Optional[str] = None
    project_name: Optional[str] = "Unknown Project"
    error: Optional[str] = None

    # Pydantic V2 configuration style
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "question": "What is the fire pump capacity?",
                "answer": "The fire pump capacity is 500 GPM as per the RFQ specifications.",
                "sources": ["RFQ_Mall_Project.pdf"],
                "chunks_used": 3,
                "project_name": "Mall Fire Safety System"
            }
        }
    }