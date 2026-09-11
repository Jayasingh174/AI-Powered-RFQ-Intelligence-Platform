# AI-Powered RFQ Intelligence Platform

An AI-driven document intelligence system for engineering RFQs (Requests for Quotation). Upload PDFs, Word docs, Excel BOQs, and CAD drawings (DWG/DXF), then ask natural-language questions about quantities, specifications, and cross-document conflicts — all grounded in the uploaded documents via Retrieval-Augmented Generation (RAG).

---

## What it does

- **Multi-format ingestion** — PDF, DOCX (including embedded tables), CSV, XLSX/XLS (BOQ-aware), TXT, DWG, and DXF
- **Hybrid retrieval** — combines FAISS vector search (semantic) with BM25 keyword search (exact terms — part numbers, spec codes) via Reciprocal Rank Fusion
- **Cross-encoder reranking** — a second-pass relevance model re-scores retrieved chunks before they reach the LLM, improving answer grounding
- **Grounded chat** — ask questions about uploaded documents; answers are strictly sourced from document content, with cited filenames
- **Cross-document conflict detection** — flags when the same item/quantity is reported differently across multiple documents (e.g. a BOQ says 10 units, a spec sheet says 15)
- **CAD-aware extraction** — parses DWG/DXF entities and named blocks so CAD quantities participate in conflict detection alongside text-based documents
- **Structured extraction** — an LLM extraction pass produces machine-readable JSON (project name, items, quantities, specs) per document, saved to `deliverables/`

---

## Architecture

```
app/
├── main.py                 # FastAPI app, lifespan, router registration
├── config.py                # Environment-driven configuration
├── routers/                 # API endpoints
│   ├── upload_router.py     # Single-file & multi-file bundle upload
│   ├── query_router.py      # Chat (/ask) and raw search (/search)
│   └── document_router.py   # Document listing, deletion, CSV export
├── pipeline/
│   ├── rag_pipeline.py      # Single-file & bundle processing orchestration
│   ├── query_pipeline.py    # Retrieval → rerank → context → LLM answer
│   └── optimization_service.py  # Hybrid retrieval, cross-encoder reranking, context compression
├── brain/
│   ├── vector_service.py    # FAISS + BM25 hybrid vector store
│   ├── embedding_service.py # OpenAI embeddings (with retry)
│   ├── llm_service.py       # OpenAI chat completion (with retry)
│   ├── chunk_service.py     # Text chunking for embeddings
│   ├── conflict_engine.py   # Cross-document quantity conflict detection
│   └── document_upload.py   # Filesystem-backed document state
├── extraction/
│   ├── bom_extractor.py     # Pattern-based Bill of Materials extraction
│   ├── spec_extractor.py    # Regex-based spec field extraction
│   └── table_extractor.py   # Table block detection
├── services/
│   ├── pdf_service.py       # PyMuPDF text extraction
│   ├── docx_service.py      # Paragraph + table extraction
│   ├── csv_service.py       # CSV → structured text
│   ├── excel_service.py     # Excel BOQ parsing
│   ├── cad_service.py       # DWG→DXF conversion, entity parsing
│   └── intelligence_service.py  # LLM-based structured JSON extraction
├── models/                  # Pydantic request/response schemas
└── web/                     # Static frontend (HTML/CSS/JS)
```

**Data flow (single file):** Upload → text extraction (format-specific service) → chunking → embedding → FAISS/BM25 index → parallel: (a) pattern-based BOM/spec/table extraction, (b) LLM structured extraction → conflict detection → result saved to `deliverables/`.

**Data flow (chat):** Question → embed → hybrid search (FAISS + BM25, fused via RRF) → cross-encoder rerank → context compression → grounded LLM answer with cited sources.

---

## Setup

### Prerequisites
- Python 3.10+
- An OpenAI API key
- (Optional, for `.dwg` support) [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) installed locally

### Installation

```bash
git clone https://github.com/Jayasingh174/AI-Powered-RFQ-Intelligence-Platform.git
cd AI-Powered-RFQ-Intelligence-Platform
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the project root:

```bash
# Required
OPENAI_API_KEY=your-openai-api-key-here

# Optional — sensible defaults apply if omitted
APP_NAME=RFQ AI System
DEBUG=True

UPLOAD_DIR=uploads
SAVE_DIR=vectorstore
DWG_TEMP_DIR=temp_dxf

EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSION=3072

OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.0
OPENAI_MAX_TOKENS=2000
MAX_RETRIES=3

TOP_K=8
MAX_CONTEXT_CHARS=12000

ALLOWED_FILE_TYPES=docx,pdf,dwg,dxf,txt,csv,xlsx,xls
MAX_UPLOAD_SIZE_MB=50

# Required only for .dwg uploads — leave unset if you only need .dxf
ODA_PATH=
```

### Run

```bash
uvicorn app.main:app --reload
```

Then open **http://localhost:8000**.

---

## API reference

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/upload/bundle` | Upload and process multiple files, run cross-document conflict detection |
| `POST` | `/upload/process` | Reprocess a single file already on disk |
| `POST` | `/query/ask` | Ask a grounded question; returns an answer, sources, and confidence |
| `POST` | `/query/search` | Raw hybrid search + rerank, no LLM generation (debugging / advanced use) |
| `GET` | `/documents` | List currently indexed documents |
| `DELETE` | `/delete/{filename}` | Remove a document from disk and the search index |
| `POST` | `/export/conflicts` | Export a conflict report as CSV |

Interactive API docs are available at `/docs` once the server is running.

---

## Project status

This project is under active development. Known limitations at the time of writing:

- CAD table-merge handling in `.docx` extraction is a documented limitation (merged cells can duplicate in extracted rows)
- SRI hash for the CDN-loaded markdown renderer needs to be generated for your pinned library version before production deployment
- `.env.example` should be added alongside this README to document required variables without risking real keys being committed

See commit history and inline code comments (marked `🔧 FIX`) for a record of issues found and resolved during development.

---

## Author

Jaya Singh — B.Tech CSE, AI Engineer focused on RAG pipelines, multi-agent systems, and LLM application development.
