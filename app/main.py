"""
RFQ AI System - Main Entry Point
Handles application lifecycle (Lifespan), Middleware, Routing, and Static Assets.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# --- Core Logic & Config ---
from app.brain.vector_service import vector_store
from app.config import UPLOAD_DIR, APP_NAME, EMBEDDING_MODEL, OPENAI_API_KEY

# --- API Routers ---
# NOTE: config.py already raises ValueError at import time if
# OPENAI_API_KEY is missing — by the time this import succeeds, the key
# is guaranteed present. If any router import below fails, the traceback
# will name which module failed; it just won't say which router file
# imported it, since this is a single grouped import statement.
from app.routers import (
    upload_router,
    query_router,
    document_router,   # also owns /export/conflicts — not just file listing/delete
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles system initialization and graceful shutdown.
    Ensures FAISS index is loaded and saved correctly.
    """
    print(f"\n{'='*40}")
    print(f"🚀 {APP_NAME} INITIALIZING")
    print(f"{'='*40}")

    # 🔧 FIX: removed the redundant OPENAI_API_KEY check — config.py
    # already fails fast at import time if it's missing, so this branch
    # was unreachable dead code that implied a safety net that doesn't exist.

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs("deliverables", exist_ok=True)

    try:
        vector_store.load_index()
        logger.info("✅ Vector index successfully restored from disk.")
    except Exception as e:
        logger.warning(f"⚠️ No index found or load failed: {e}. Starting fresh.")

    logger.info(f"System active using model: {EMBEDDING_MODEL}")
    print(f"✅ Startup Complete. Listening for requests.\n")

    yield

    logger.info("💾 Persistence: Saving vector index before shutdown...")
    try:
        vector_store.save_index()
        logger.info("✅ Vector index saved successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to save index: {e}")


app = FastAPI(
    title=APP_NAME,
    description="AI-Powered RFQ Intelligence Platform — Document Intelligence & Conflict Analysis",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 🔧 NEW: backstop for anything that slips past each router's own
# try/except — returns clean JSON instead of FastAPI's default HTML
# traceback page. Every router reviewed in this conversation already
# handles its own errors; this only catches what they didn't.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."}
    )


app.include_router(upload_router.router)    # Multi-source ingestion
app.include_router(query_router.router)     # RAG Chatbot
app.include_router(document_router.router)  # File management + conflict export

# NOTE: export_router / quote_router (if present in app/routers/) are not
# registered here. Per this conversation's earlier review, if those files
# exist they're dead code — either wire them in with app.include_router(...)
# or delete them; leaving them un-registered but present invites someone
# to assume they're live.

if os.path.exists("app/web"):
    app.mount("/static", StaticFiles(directory="app/web"), name="static")


@app.get("/", tags=["Frontend"])
async def serve_frontend():
    """Serves the main HTML dashboard."""
    return FileResponse("app/web/index.html")
