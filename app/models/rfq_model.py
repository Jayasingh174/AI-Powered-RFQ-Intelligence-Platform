from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class RFQRequest(BaseModel):
    """
    Request model for processing a single document.
    """
    file_path: str = Field(default="uploads/RFQ_Mall_Project.pdf", description="Path to the RFQ document file")

class RFQResponse(BaseModel):
    """
    Structured response for the Document Intelligence task.
    Matches the 'result' dictionary in rfq_pipeline.py.
    """
    status: str = "success"
    message: str
    project_name: Optional[str] = "Unknown Project"
    
    # Machine-readable structured items (The core of your task)
    structured_items: List[Dict[str, Any]] = []
    
    # Granular extraction details
    bom: List[Dict[str, Any]] = []
    specifications: List[Dict[str, Any]] = []
    tables: List[List[Any]] = []
    
    # CAD specific data if applicable
    cad_summary: Optional[str] = None
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "status": "success",
                "project_name": "Mall Fire Safety System",
                "structured_items": [
                    {"name": "Fire Pump", "qty": 2, "specification": "500 GPM"}
                ],
                "message": "Full extraction & intelligence pipeline complete."
            }
        }
    }