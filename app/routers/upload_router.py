"""
RFQ AI System - Upload Router
Handles single file processing and multi-file bundle uploads.
"""

import os
import logging
import aiofiles
from pathlib import Path
from typing import List
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

# 🔧 FIX: point at the pipeline module that actually exists.
# If the real file is app/pipeline/rag_pipeline.py with
# process_rag()/process_rag_bundle(), alias on import so the rest
# of this file (and any RFQ-named consumers) doesn't need renaming.
from app.pipeline.rag_pipeline import process_rag, process_rag_bundle

# 🔧 FIX: same — point at the models file that actually exists.
from app.models.rag_model import RFQRequest, RFQResponse

from app.config import UPLOAD_DIR, validate_upload  # 🔧 FIX: use config's UPLOAD_DIR, not a local hardcode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/process", response_model=RFQResponse)
async def process_single_rfq(request: RFQRequest):
    """
    Processes a single document already present on the server.
    Ideal for re-running analysis on a specific file.
    """
    try:
        file_path = request.file_path
        logger.info(f"Processing single file: {file_path}")

        result = await process_rag(file_path)

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Single-file processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bundle")
async def upload_rfq_bundle(
    project_name: str = Form("New RFQ Project"),
    files: List[UploadFile] = File(...)
):
    """
    The 'Intelligence' Endpoint:
    1. Validates and saves multiple files asynchronously in chunks.
    2. Runs the cross-file engineering conflict detection.
    3. Returns structured JSON including the project requirements.
    """
    saved_filepaths = []

    try:
        for file in files:
            original_name = file.filename or ""
            if not original_name:
                original_name = f"uploaded_{uuid4().hex}"
            safe_filename = Path(original_name).name
            filepath = os.path.join(UPLOAD_DIR, safe_filename)

            async with aiofiles.open(filepath, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):
                    await buffer.write(chunk)

            # 🔧 FIX: validate after write (need the file on disk for
            # size check) but before it's handed to the pipeline — a
            # bad file type/size now fails fast with a clean message
            # instead of surfacing as a confusing pipeline error later.
            try:
                validate_upload(filepath)
            except ValueError as ve:
                os.remove(filepath)
                raise HTTPException(status_code=400, detail=str(ve))

            saved_filepaths.append(filepath)
            logger.info(f"📁 Uploaded: {safe_filename}")

        logger.info(f"🚀 Analyzing bundle for project: {project_name}")

        pipeline_result = await process_rag_bundle(
            project_name=project_name,
            file_paths=saved_filepaths
        )

        return pipeline_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Bundle processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bundle analysis failed: {str(e)}")
