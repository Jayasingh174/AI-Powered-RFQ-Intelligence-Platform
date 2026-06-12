"""
RFQ AI System - Document & Export Router
Handles document listing, file deletion, and CSV conflict report generation.
"""

import logging
import csv
import io
import os
from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

# Internal logic imports
from app.brain.document_upload import get_documents, delete_document

logger = logging.getLogger(__name__)

# Initialize the router
router = APIRouter(tags=["Document Management"])

# ==========================================
# 📂 DOCUMENT LISTING
# ==========================================
@router.get("/documents")
def list_documents():
    """
    Retrieves a list of all currently uploaded and processed documents
    from the server to display in the 'Indexed Documents' UI.
    """
    try:
        logger.info("Fetching list of available documents...")
        docs = get_documents()
        
        return {
            "status": "success", 
            "documents": docs
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to retrieve documents: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Could not retrieve documents: {str(e)}"
        )

# ==========================================
# 🗑️ DOCUMENT DELETION
# ==========================================
@router.delete("/delete/{filename}")
def remove_document(filename: str):
    """
    Deletes a specific file from the 'uploads' folder and 
    removes it from the UI list.
    """
    try:
        logger.info(f"🗑️ Attempting to delete document: {filename}")
        
        # Trigger the physical deletion from the hard drive
        success = delete_document(filename)
        
        if success:
            logger.info(f"✅ Successfully deleted: {filename}")
            return {"status": "success", "message": f"Deleted {filename}"}
        else:
            logger.warning(f"⚠️ File not found for deletion: {filename}")
            raise HTTPException(status_code=404, detail="File not found on disk.")
            
    except HTTPException:
        raise 
    except Exception as e:
        logger.error(f"❌ Failed to delete document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 📥 EXPORT CONFLICTS TO CSV
# ==========================================
@router.post("/export/conflicts")
async def export_conflicts_csv(data: dict):
    """
    Receives the JSON conflict report from the frontend and 
    converts it into a downloadable CSV file.
    """
    try:
        logger.info("📊 Generating CSV Conflict Report for export...")
        
        # Use an in-memory string buffer for the CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 1. Write the CSV Headers
        writer.writerow(["Entity Name", "Source Document", "Detected Quantity"])
        
        # 2. Extract conflict details from the payload
        # Note: Frontend passes responseData.engineering_analysis as the body
        conflict_details = data.get("conflict_details", [])
        
        if not conflict_details:
            writer.writerow(["No major conflicts detected between documents", "N/A", "N/A"])
        else:
            # 3. Format JSON entries into CSV rows
            for item in conflict_details:
                entity_name = item.get("entity", "Unknown Item")
                quantities = item.get("quantities", {})
                
                for source, qty in quantities.items():
                    writer.writerow([entity_name, source, qty])
                    
        # 4. Return as a streamable response
        return PlainTextResponse(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=RFQ_Conflict_Report.csv"
            }
        )

    except Exception as e:
        logger.error(f"❌ CSV Export failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate CSV report.")