import os
import logging
from typing import List

# Extraction services
from app.services.pdf_service import extract_pdf
from app.services.docx_service import extract_docx
from app.services.csv_service import extract_csv
from app.services.excel_service import extract_boq_data
from app.services.text_service import extract_text
from app.services.cad_service import extract_dwg, summarize_dxf

# AI pipeline services
from app.brain.chunk_service import chunk_text
from app.brain.embedding_service import embed_texts

# Import the unified VectorService instance
from app.brain.vector_service import vector_store 

from app.config import DWG_TEMP_DIR

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".csv", ".xlsx", ".xls", ".txt", ".dwg", ".dxf"
}

# --- HELPER: FUZZY DICTIONARY MATCHER ---
def get_fuzzy_val(row_dict: dict, possible_keys: list) -> str:
    """Checks a dictionary for multiple possible column names (case-insensitive)"""
    # 🔥 FIX 1: Safely abort if the Excel parser handed us a string instead of a row dictionary
    if not isinstance(row_dict, dict):
        return ""
        
    # Convert all keys in the row to lowercase for safe checking
    lower_row = {str(k).lower().strip(): v for k, v in row_dict.items() if k}
    
    for key in possible_keys:
        if key.lower() in lower_row and lower_row[key.lower()] is not None:
            return str(lower_row[key.lower()]).strip()
    return ""
# ----------------------------------------

async def process_document(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        raise ValueError("File exceeds maximum allowed size (10MB)")

    ext = os.path.splitext(file_path)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    try:
        chunks: List[str] = []
        clean_text = ""

        # ==================================================
        # 1️⃣ EXCEL (BOQ Handling)
        # ==================================================
        if ext in [".xlsx", ".xls"]:
            boq_data = extract_boq_data(file_path)

            if not boq_data:
                raise ValueError("No data extracted from Excel")

            for row in boq_data:
                # 🔥 FIX 1b: Double protection. Skip if the row isn't a dictionary
                if not row or not isinstance(row, dict):
                    continue

                item = get_fuzzy_val(row, ["Item", "Item No", "S.No", "ID", "No."])
                desc = get_fuzzy_val(row, ["Material", "Description", "Item Description", "Name", "Spec"])
                qty = get_fuzzy_val(row, ["Quantity", "Qty", "Qty.", "Amount"])
                unit = get_fuzzy_val(row, ["Unit", "UOM", "Unit of Measure"])

                if not desc and not qty:
                    continue

                text_chunk = f"Item {item}: {desc} | Qty: {qty} {unit}"
                chunks.append(text_chunk)

            clean_text = "\n".join(chunks)
            logger.info(f"📊 Excel processed → {len(chunks)} BOQ chunks")

        # ==================================================
        # 2️⃣ OTHER FILE TYPES
        # ==================================================
        else:
            if ext == ".pdf":
                raw = extract_pdf(file_path)
            elif ext == ".docx":
                raw = extract_docx(file_path)
            elif ext == ".csv":
                raw = extract_csv(file_path)
            elif ext == ".txt":
                raw = extract_text(file_path)
            elif ext == ".dwg":
                raw = extract_dwg(file_path, DWG_TEMP_DIR)
            elif ext == ".dxf":
                # summarize_dxf expects a parsed data dict; pass a dict containing the file path
                raw = summarize_dxf({"file_path": file_path})
            else:
                raw = ""

            if isinstance(raw, dict):
                text_chunks = raw.get("text_chunks", [])
                summary = raw.get("summary", "")
                clean_text = f"{summary}\n\n{' '.join(text_chunks)}"
            else:
                clean_text = str(raw)

            clean_text = clean_text.strip()

            if len(clean_text) < 10:
                raise ValueError("No meaningful text extracted")

            raw_chunks = chunk_text(clean_text)
            chunks = [c.strip() for c in raw_chunks if c and len(c.strip()) > 20]

            logger.info(f"📄 Text processed → {len(chunks)} chunks")

        if not chunks:
            raise ValueError("No valid chunks generated")

        # ==================================================
        # 3️⃣ EMBEDDINGS
        # ==================================================
        embeddings = await embed_texts(chunks)

        # 🔥 FIX 2: Safe NumPy Array Check (Using "is None")
        if embeddings is None or len(embeddings) == 0:
            raise ValueError("Embedding generation failed")

        # ==================================================
        # 4️⃣ STORE VECTORS (THE BATCH FIX)
        # ==================================================
        filename = os.path.basename(file_path)

        vector_store.add_documents(
            chunks=chunks,
            embeddings=embeddings,
            source_filename=filename
        )

        logger.info(f"✅ Document indexed successfully: {filename}")
        return clean_text

    except Exception as e:
        logger.error(f"❌ Document processing failed: {file_path} | {e}", exc_info=True)
        raise RuntimeError(f"Document processing failed: {e}") from e