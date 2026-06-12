import fitz  # This is PyMuPDF
import logging
import os

logger = logging.getLogger(__name__)

def extract_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file using PyMuPDF.
    Provides superior handling of multi-column layouts and tables found in RFQs.
    """
    if not os.path.exists(file_path):
        logger.error(f"❌ PDF not found at path: {file_path}")
        return ""

    try:
        # Open the PDF document
        doc = fitz.open(file_path)
        text_chunks = []

        # Iterate through all pages
        for page_num, page in enumerate(doc.pages() if doc.page_count > 0 else []):
            # Extract text preserving visual layout as much as possible
            page_text = page.get_text("text")
            
            if page_text.strip():
                # Add a page marker so the LLM knows where it is in the document
                text_chunks.append(f"--- PAGE {page_num + 1} ---\n{page_text}")

        # Close the document to free up system memory
        doc.close()

        logger.info(f"✅ Successfully extracted {len(text_chunks)} pages from PDF.")
        return "\n\n".join(text_chunks).strip()

    except Exception as e:
        logger.error(f"❌ Critical failure extracting PDF {file_path}. Error: {e}")
        raise ValueError(f"Failed to read PDF file: {e}")