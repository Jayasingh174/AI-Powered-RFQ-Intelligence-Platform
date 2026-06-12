"""
RFQ AI System - Unified Pipeline
Handles both single-file processing and multi-file 'Bundle' orchestrations.
Merges data from PDFs, CAD, and Excel, checks for consistency, and saves deliverables.
"""

import os
import re
import json
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

# ----- Internal Configuration & Services -----
from app.config import UPLOAD_DIR
from app.brain.document_service import process_document
from app.brain.vector_service import vector_store
from app.brain.conflict_engine import detect_conflicts
from app.services.cad_service import extract_dwg
from app.services.excel_service import extract_boq_data
from app.pipeline.intelligence_service import DocumentIntelligence

logger = logging.getLogger(__name__)

# ==========================================================
# 🧹 DATA CLEANING HELPERS
# ==========================================================

def safe_int(val, default=1):
    """Converts mixed strings (e.g., '25 Nos') into clean integers."""
    try:
        num_str = re.sub(r"[^\d.]", "", str(val))
        return int(float(num_str)) if num_str else default
    except Exception:
        return default

def clean_item(text: str) -> str:
    """Normalizes item names for better matching across different files."""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def normalize_entity(item, quantity, source, etype, path):
    """Creates a standardized dictionary for every item found in any file."""
    return {
        "item": clean_item(item),
        "quantity": safe_int(quantity),
        "source": source,
        "type": etype,
        "file_path": path,
    }

def deduplicate_entities(entities):
    """Removes identical entries to prevent double-counting."""
    seen = set()
    unique = []
    for e in entities:
        if not isinstance(e, dict) or "item" not in e:
            continue
        key = (e["item"], e["type"], e["file_path"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique

# ==========================================================
# 📄 SINGLE FILE RFQ PROCESSOR
# ==========================================================

async def process_rfq(file_path: str) -> Dict[str, Any]:
    """
    Main single RFQ processing pipeline:
    1. Reads & cleans text (Ingests into Vector DB)
    2. Uses LLM to extract strict JSON requirements
    3. Runs the Conflict Engine to verify quantities
    4. Handles CAD visuals
    """
    try:
        filename = os.path.basename(file_path)
        logger.info(f"🚀 Starting RFQ Pipeline for: {filename}")

        # --------------------------------------------------
        # 1️⃣ Extract text & Store Vectors
        # --------------------------------------------------
        await process_document(file_path)

        # Explicitly grab the text chunks for THIS file from the database
        file_chunks = [
            chunk["text"] for chunk in vector_store.documents 
            if chunk.get("metadata", {}).get("source") == filename
        ]
        
        clean_text = "\n\n".join(file_chunks)

        if not clean_text or len(clean_text.strip()) < 10:
            raise ValueError(f"No meaningful text found in database for {filename}. Parsing may have failed.")

        # --------------------------------------------------
        # 2️⃣ Structured Extraction (LLM Intelligence)
        # --------------------------------------------------
        logger.info(f"🧠 Extracting structured BOM and Specs via LLM (Context length: {len(clean_text)})...")
        
        intelligence = DocumentIntelligence() 
        structured_data = await intelligence.extract_structured_data(clean_text)
        
        extracted_items = structured_data.get("items", [])

        # --------------------------------------------------
        # 3️⃣ Run the Conflict Engine
        # --------------------------------------------------
        logger.info("🔍 Running Conflict Engine on extracted items...")
        
        mapped_items = []
        for item in extracted_items:
            mapped_items.append({
                "item": item.get("name", "Unknown Item"),
                "quantity": item.get("qty", 1),
                "source": filename
            })
            
        conflict_report = detect_conflicts(mapped_items)

        # --------------------------------------------------
        # 4️⃣ Prepare Result 
        # --------------------------------------------------
        result = {
            "status": "success",
            "source_file": filename,
            "project": structured_data.get("project", "Unknown Project"),
            "items": extracted_items,
            "conflicts": conflict_report, 
            "message": "Vectors stored, requirements extracted, and conflicts analyzed."
        }

        # --------------------------------------------------
        # 5️⃣ CAD Processing (Optional)
        # --------------------------------------------------
        if file_path.lower().endswith((".dwg", ".dxf")):
            logger.info("📐 CAD file detected. Running visual extraction...")
            cad_result = extract_dwg(file_path, output_dir=UPLOAD_DIR)
            result["cad_summary"] = cad_result.get("summary")

        logger.info(f"✅ RFQ Pipeline complete for {filename}")
        return result

    except Exception as e:
        logger.error(f"❌ RFQ processing failed for {file_path}: {e}", exc_info=True)
        return {
            "status": "error",
            "project": "Error",
            "items": [],
            "conflicts": {},
            "message": str(e)
        }

# ==========================================================
# 🚀 MULTI-FILE RFQ ORCHESTRATOR
# ==========================================================

async def process_rfq_bundle(project_name: str, file_paths: List[str]) -> Dict[str, Any]:
    """
    Master pipeline for 'Document Intelligence'. 
    Merges data from PDF, Word, and Excel and saves results to the deliverables folder.
    """
    logger.info(f"🚀 Starting Bundle processing for project: {project_name}")

    all_normalized_entities: List[Dict[str, Any]] = []
    processed_results: List[Dict[str, Any]] = []
    success_count = 0
    error_count = 0
    EXCEL_EXTS = {"xlsx", "xls"}

    os.makedirs("deliverables", exist_ok=True)

    for i, raw_path in enumerate(file_paths):
        path = Path(raw_path)
        filename = path.name

        try:
            logger.info(f"Processing {i + 1}/{len(file_paths)}: {filename}")

            if not path.exists() or path.stat().st_size == 0:
                raise ValueError("File not found or empty")

            ext = path.suffix.lower().lstrip(".")
            entities: List[Dict[str, Any]] = []

            # 1️⃣ STAGE: Process Document using the local function
            result = await process_rfq(str(path))
            
            if not result or result.get("status") == "error":
                raise ValueError(result.get("message", "Extraction error"))

            with open(f"deliverables/requirements_{filename}.json", "w") as f:
                json.dump(result, f, indent=4)

            # 2️⃣ STAGE: Entity Extraction
            if ext in EXCEL_EXTS:
                boq_data = extract_boq_data(str(path))
                if isinstance(boq_data, list):
                    for row in boq_data:
                        if not isinstance(row, dict): continue
                        item = row.get("Item") or row.get("Description")
                        qty = row.get("Quantity") or row.get("Qty")
                        if item and qty:
                            entities.append(normalize_entity(item, qty, f"BOQ ({filename})", "BOQ", str(path)))
                status_msg = "processed as BOQ"
            else:
                for entity in result.get("cad_entities", []) or []:
                    entities.append(normalize_entity(entity.get("item", "Unknown"), entity.get("qty"), f"CAD ({filename})", "CAD", str(path)))
                for item in result.get("bom", []) or []:
                    entities.append(normalize_entity(item.get("item", "Unknown"), item.get("quantity"), f"Spec BOM ({filename})", "Spec BOM", str(path)))
                status_msg = "processed as unstructured"

            processed_results.append({"file": filename, "status": status_msg})
            all_normalized_entities.extend(entities)
            success_count += 1

        except Exception as e:
            logger.exception(f"Error processing file {filename}: {e}")
            processed_results.append({"file": filename, "status": "error", "message": str(e)})
            error_count += 1

    # 3️⃣ STAGE: Conflict Detection & Fallback
    all_normalized_entities = deduplicate_entities(all_normalized_entities)
    
    if not all_normalized_entities:
        logger.warning("⚠️ No entities extracted for the report context.")
        conflict_report = {"message": "No machine-readable entities found to analyze."}
    else:
        try:
            conflict_report = detect_conflicts(all_normalized_entities)
        except Exception as e:
            logger.error(f"Conflict detection failed: {e}")
            conflict_report = {"error": str(e)}

    # 4️⃣ STAGE: Final Master Report with Safe Filename
    safe_time = datetime.datetime.now().strftime("%H-%M-%S")
    safe_project = re.sub(r'[\\/*?:"<>|]', "", project_name)
    
    final_output = {
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "summary": {"success": success_count, "errors": error_count},
        "file_details": processed_results,
        "engineering_analysis": conflict_report,
    }

    report_path = f"deliverables/{safe_project}_{safe_time}_Report.json"
    with open(report_path, "w") as f:
        json.dump(final_output, f, indent=4)

    logger.info(f"✅ Full Report saved successfully to {report_path}")
    return final_output