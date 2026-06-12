import os
from dotenv import load_dotenv

# -------------------------------------------------
# Load environment variables
# -------------------------------------------------
load_dotenv()

# -------------------------------------------------
# Chunking settings
# -------------------------------------------------
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 200))

# -------------------------------------------------
# Application settings
# -------------------------------------------------
APP_NAME = os.getenv("APP_NAME", "RFQ AI System")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# -------------------------------------------------
# Directory settings
# -------------------------------------------------
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
SAVE_DIR = os.getenv("SAVE_DIR", "vectorstore")
DWG_TEMP_DIR = os.getenv("DWG_TEMP_DIR", "temp_dxf")

# Create directories on startup
for folder in [UPLOAD_DIR, SAVE_DIR, DWG_TEMP_DIR]:
    os.makedirs(folder, exist_ok=True)

# -------------------------------------------------
# Embedding model settings
# -------------------------------------------------
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", 3072))

# -------------------------------------------------
# OpenAI API settings
# -------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    # Fail fast if the API key is missing
    raise ValueError("CRITICAL ERROR: OPENAI_API_KEY is not set in the environment.")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", 0.0))
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", 2000))

# -------------------------------------------------
# Retrieval & RAG settings
# -------------------------------------------------
TOP_K = int(os.getenv("TOP_K", 8))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", 12000))

# -------------------------------------------------
# Default financial settings
# -------------------------------------------------
DEFAULT_LABOR_RATE = float(os.getenv("DEFAULT_LABOR_RATE", 75.0))
DEFAULT_OVERHEAD = float(os.getenv("DEFAULT_OVERHEAD", 0.2))

# -------------------------------------------------
# Upload settings
# -------------------------------------------------
# Convert to a set of lowercase extensions WITH dots for easy checking (e.g., {'.pdf', '.docx'})
ALLOWED_FILE_TYPES = set(
    f".{ext.strip().lower()}" for ext in 
    os.getenv("ALLOWED_FILE_TYPES", "docx,pdf,dwg,dxf,txt,csv,xlsx,xls").replace(".", "").split(",")
)

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", 50))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# -------------------------------------------------
# FAISS Storage Paths (Synced with vector_service.py)
# -------------------------------------------------
INDEX_FILE = os.path.join(SAVE_DIR, "index.faiss")
DOCS_FILE = os.path.join(SAVE_DIR, "docs.npy")

# -------------------------------------------------
# Validation Helpers
# -------------------------------------------------
def validate_upload(file_path: str) -> bool:
    """
    Validates uploaded file type and size against global configuration limits.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext not in ALLOWED_FILE_TYPES:
        raise ValueError(
            f"File type '{ext}' not allowed. Allowed types: {', '.join(ALLOWED_FILE_TYPES)}"
        )

    size_bytes = os.path.getsize(file_path)

    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        raise ValueError(
            f"File size {size_mb:.2f} MB exceeds limit of {MAX_UPLOAD_SIZE_MB} MB"
        )

    return True