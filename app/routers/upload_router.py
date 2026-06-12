
"""
RFQ AI System - Upload Router
Handles single file processing and multi-file bundle uploads.
"""

import os
import logging
import aiofiles
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.pipeline.rfq_pipeline import process_rfq, process_rfq_bundle

# --- Models ---
from app.models.rfq_model import RFQRequest, RFQResponse

# --- Setup ---
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------
# 1️⃣ SINGLE FILE PROCESSING
# ---------------------------------------------------------
@router.post("/process", response_model=RFQResponse)
async def process_single_rfq(request: RFQRequest):
    """
    Processes a single document already present on the server.
    Ideal for re-running analysis on a specific file.
    """
    try:
        file_path = request.file_path
        logger.info(f"Processing single file: {file_path}")

        # Await the main extraction pipeline
        result = await process_rfq(file_path)

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        return result

    except Exception as e:
        logger.error(f"❌ Single-file processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# 2️⃣ MULTI-FILE BUNDLE UPLOAD (Document Intelligence Task)
# ---------------------------------------------------------
@router.post("/bundle")
async def upload_rfq_bundle(
    project_name: str = Form("New RFQ Project"),
    files: List[UploadFile] = File(...)
):
    """
    The 'Intelligence' Endpoint:
    1. Saves multiple files (PDF, XLSX, DOCX) asynchronously in chunks.
    2. Runs the cross-file engineering conflict detection.
    3. Returns structured JSON including the project requirements.
    """
    saved_filepaths = []
    
    try:
        # Step 1: Securely save all uploaded files to disk
        for file in files:
            # Security: Sanitize the filename to prevent path traversal and handle None/empty filenames
            original_name = file.filename or ""
            if not original_name:
                # fallback to a generated name to avoid None or empty filename
                from uuid import uuid4
                original_name = f"uploaded_{uuid4().hex}"
            safe_filename = Path(original_name).name
            filepath = os.path.join(UPLOAD_DIR, safe_filename)
            
            # Performance: Async file writing in 1MB chunks to save RAM
            async with aiofiles.open(filepath, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):  # Read 1MB at a time
                    await buffer.write(chunk)
                
            saved_filepaths.append(filepath)
            logger.info(f"📁 Uploaded: {safe_filename}")

        # Step 2: Trigger the Multi-Source Extraction Orchestrator
        logger.info(f"🚀 Analyzing bundle for project: {project_name}")
        
        pipeline_result = await process_rfq_bundle(
            project_name=project_name, 
            file_paths=saved_filepaths
        )

        # Step 3: Return the machine-readable JSON results
        return pipeline_result

    except Exception as e:
        logger.error(f"❌ Bundle processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bundle analysis failed: {str(e)}")