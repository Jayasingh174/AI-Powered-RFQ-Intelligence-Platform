"""
RAG AI System - Unified Pipeline
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

from app.config import UPLOAD_DIR
from app.brain.document_service import process_document
from app.brain.vector_service import vector_store
from app.brain.conflict_engine import detect_conflicts, normalize_entity, deduplicate_entities  # 🔧 FIX: use the shared implementations, not local duplicates
from app.services.cad_service import extract_dwg
from app.services.excel_service import extract_boq_data
from app.pipeline.intelligence_service import DocumentIntelligence
from app.extraction.bom_extractor import extract_bom
from app.extraction.spec_extractor import extract_specs
from app.extraction.table_extractor import extract_tables

logger = logging.getLogger(__name__)


# ==========================================================
# 📄 SINGLE FILE RAG PROCESSOR
# ==========================================================

async def process_rag(file_path: str) -> Dict[str, Any]:
    """
    Main single RAG processing pipeline:
    1. Reads & cleans text (Ingests into Vector DB)
    2. Uses LLM to extract strict JSON requirements
    3. Runs the Conflict Engine to verify quantities
    4. Handles CAD visuals
    """
    try:
        filename = os.path.basename(file_path)
        logger.info(f"🚀 Starting RAG Pipeline for: {filename}")

        # --------------------------------------------------
        # 1️⃣ Extract text & Store Vectors
        # --------------------------------------------------
        # 🔧 FIX: use process_document()'s own return value instead of
        # re-deriving text from vector_store.documents. Re-deriving by
        # filtering on metadata.source == filename silently breaks
        # whenever this file's content duplicates something already
        # indexed under a different filename — add_documents() correctly
        # skips re-adding duplicate-hash chunks, so nothing ever gets
        # tagged with the new filename, and the old filter finds nothing.
        clean_text = await process_document(file_path)

        if not clean_text or len(clean_text.strip()) < 10:
            raise ValueError(f"No meaningful text extracted for {filename}. Parsing may have failed.")

        # Deterministic pattern-based extraction — fast, no LLM cost,
        # complements (not replaces) the LLM extraction below.
        bom_rows = extract_bom(clean_text)
        spec_fields = extract_specs(clean_text)
        detected_tables = extract_tables(clean_text)

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

        mapped_items = [
            {
                "item": item.get("name", "Unknown Item"),
                "quantity": item.get("qty", 1),
                "source": filename,
            }
            for item in extracted_items
        ]

        conflict_report = detect_conflicts(mapped_items)

        # --------------------------------------------------
        # 4️⃣ Prepare Result
        # --------------------------------------------------
        result = {
            "status": "success",
            "source_file": filename,
            "project": structured_data.get("project", "Unknown Project"),
            "items": extracted_items,
            "bom": bom_rows,
            "specifications": spec_fields,   # 🔧 FIX: no extra list wrapper
            "tables": detected_tables,        # 🔧 FIX: no extra list wrapper — already a list of tables
            "conflicts": conflict_report,
            "message": "Vectors stored, requirements extracted, and conflicts analyzed.",
        }

        # --------------------------------------------------
        # 5️⃣ CAD Processing (Optional)
        # --------------------------------------------------
        if file_path.lower().endswith((".dwg", ".dxf")):
            logger.info("📐 CAD file detected. Running visual extraction...")
            cad_result = extract_dwg(file_path, output_dir=UPLOAD_DIR)
            result["cad_summary"] = cad_result.get("summary")
            result["cad_entities"] = cad_result.get("parsed_entities", {})  # 🔧 FIX: actually set what process_rag_bundle reads

        logger.info(f"✅ RAG Pipeline complete for {filename}")
        return result

    except Exception as e:
        logger.error(f"❌ RAG processing failed for {file_path}: {e}", exc_info=True)
        return {
            "status": "error",
            "project": "Error",
            "items": [],
            "conflicts": {},
            "message": str(e),
        }


# ==========================================================
# 🚀 MULTI-FILE RAG ORCHESTRATOR
# ==========================================================

async def process_rag_bundle(project_name: str, file_paths: List[str]) -> Dict[str, Any]:
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

            # 1️⃣ STAGE: Process Document
            result = await process_rag(str(path))

            if not result or result.get("status") == "error":
                raise ValueError(result.get("message", "Extraction error"))

            with open(f"deliverables/requirements_{filename}.json", "w") as f:
                json.dump(result, f, indent=4)

            # 2️⃣ STAGE: Entity Extraction — now uses conflict_engine's
            # shared normalize_entity/deduplicate_entities (see import
            # above), not a local copy with a different schema and
            # weaker (data-dropping) dedup behavior.
            if ext in EXCEL_EXTS:
                boq_data = extract_boq_data(str(path))
                if isinstance(boq_data, list):
                    for row in boq_data:
                        if not isinstance(row, dict):
                            continue
                        item = row.get("Item") or row.get("Description")
                        qty = row.get("Quantity") or row.get("Qty")
                        if item and qty:
                            entities.append(normalize_entity(item, qty, f"BOQ ({filename})", "BOQ", str(path)))
                status_msg = "processed as BOQ"
            else:
                for entity in result.get("cad_entities", []) or []:
                    entities.append(normalize_entity(
                        entity.get("item", "Unknown"), entity.get("qty"),
                        f"CAD ({filename})", "CAD", str(path)
                    ))
                for item in result.get("bom", []) or []:
                    entities.append(normalize_entity(
                        item.get("item", "Unknown"), item.get("quantity"),
                        f"Spec BOM ({filename})", "Spec BOM", str(path)
                    ))
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
