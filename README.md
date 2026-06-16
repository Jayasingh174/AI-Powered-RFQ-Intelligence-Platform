
# 🚀 AI-Powered RFQ Intelligence Platform

An intelligent AI-powered system that automates the analysis of complex *Request for Quotation (RFQ)* documents using a *Retrieval-Augmented Generation (RAG)*      pipeline.

It eliminates manual effort by extracting insights, detecting inconsistencies, and answering queries across multiple document formats—all in seconds.

---

# ✨ Key Features

- **📄 Multi-Format Support**  
  Processes PDFs, Excel BOQs (Bill of Quantities), and AutoCAD files (.DWG/.DXF).

- **🔍 Hybrid Smart Search (RAG)**  
  Combines semantic + keyword search to answer natural language queries accurately.

- **⚠️ Conflict Detection**  
  Identifies mismatches between BOQs, specifications, and engineering drawings.

- **📊 Risk Analysis**  
  Flags missing requirements, ambiguities, and potential cost risks.

- **📌 Source Citations & Confidence Score**  
  Every response includes traceable references and reliability indicators.

---

## 🛠️ Setup Guide

### 1. Clone Repository
```bash
git clone <repo-link>
cd RFQ-AI-Optimizer
````

---

### 2. Create Virtual Environment (venv)

#### 🔹 For Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### 🔹 For Mac/Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Configure Environment Variables

Create a `.env` file in the root folder:

```env
OPENAI_API_KEY=your_openai_key
HF_TOKEN=your_huggingface_token
```

---

### 5. CAD File Support (Optional)

Install **ODA File Converter** and update its path in:

```
app/services/cad_service.py
```

---

## 🚀 Running the Application

```bash
uvicorn app.main:app --reload
```

* 🌐 **Web App:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* 📘 **API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 💡 Example Queries

### 📌 Information Extraction

* "Summarize all uploaded RFQ documents"
* "List all equipment with quantities"
* "Extract fire safety requirements"

### ⚠️ Conflict Detection

* "Are there inconsistencies between BOQ and drawings?"
* "Compare M-F1 vs M-F2 drawings"


## 🧠 Architecture Overview

```
User Query
   ↓
Hybrid Retrieval (FAISS + Keyword Search)
   ↓
Relevant Document Chunks
   ↓
LLM Processing (OpenAI)
   ↓
Structured Answer + Citations + Confidence Score
```

---

## 📁 Project Structure

```
RFQ-AI-Optimizer/
│
├── app/
│   ├── brain/        # Core AI logic & conflict detection
│   ├── extraction/   # Data extraction (tables, specs, BOM)
│   ├── pipeline/     # RAG pipeline orchestration
│   ├── routers/      # API endpoints (FastAPI)
│   ├── services/     # File processing (PDF, Excel, CAD)
│   └── web/          # Frontend (HTML/CSS/JS)
│
├── .env              # Environment variables (ignored)
├── venv/             # Virtual environment (ignored)
└── requirements.txt
```

---

## ⚙️ Tech Stack

* **Backend:** FastAPI
* **AI/LLM:** OpenAI, HuggingFace
* **Vector DB:** FAISS
* **Frontend:** HTML, CSS, JavaScript
* **Document Parsing:** Custom pipelines for PDF, Excel, CAD

---

## 🎯 Use Cases

* EPC & Construction RFQ Analysis
* Procurement Automation
* Engineering Document Validation
* Tender Risk Assessment

---

## 📈 Future Improvements

* Add fine-tuned domain-specific LLM
* Implement real-time collaboration
* Improve CAD parsing with 3D model understanding
* Deploy using Docker + AWS

---

## 👩‍💻 Author

**Jaya Singh**
Full Stack Developer | AI/ML Enthusiast


