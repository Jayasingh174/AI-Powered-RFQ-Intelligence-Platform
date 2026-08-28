from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class RAGRequest(BaseModel):
    """
    Request model for processing a single document.
    """
    file_path: str = Field(default="uploads/RAG_Mall_Project.pdf", description="Path to the RAG document file")

class RAGResponse(BaseModel):
    """
    Structured response for the Document Intelligence task.
    Field names are matched EXACTLY to the keys returned by process_rag()
    in rag_pipeline.py, because FastAPI's response_model validates a plain
    dict by field name — any dict key that doesn't match a field name here
    is silently dropped from the API response. (Previously this model used
    'project_name'/'structured_items' while the pipeline returned
    'project'/'items', so real extracted data was being discarded.)
    """
    status: str = "success"
    message: str

    # The uploaded file this response corresponds to — was previously
    # missing here entirely, so it never reached the client.
    source_file: Optional[str] = None

    # Renamed from 'project_name' -> 'project' to match process_rag()'s key.
    project: Optional[str] = "Unknown Project"

    # Renamed from 'structured_items' -> 'items' to match process_rag()'s key.
    items: List[Dict[str, Any]] = []

    # Granular extraction details (from the bom/spec/table extractors)
    bom: List[Dict[str, Any]] = []
    specifications: List[Dict[str, Any]] = []
    tables: List[List[Any]] = []

    # Conflict-engine report — was previously missing here entirely,
    # so conflict detection results never reached the client.
    conflicts: Dict[str, Any] = {}

    # CAD specific data if applicable
    cad_summary: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "status": "success",
                "source_file": "RAG_Mall_Project.pdf",
                "project": "Mall Fire Safety System",
                "items": [
                    {"name": "Fire Pump", "qty": 2, "specification": "500 GPM"}
                ],
                "bom": [],
                "specifications": [],
                "tables": [],
                "conflicts": {},
                "message": "Full extraction & intelligence pipeline complete."
            }
        }
    }
