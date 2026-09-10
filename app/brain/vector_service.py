import os
import re
import faiss
import pickle
import hashlib
import numpy as np
import logging
from rank_bm25 import BM25Okapi

from app.config import SAVE_DIR, EMBEDDING_DIMENSION

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class VectorService:
    """
    A unified Vector Store that handles both FAISS (Vector Search)
    and BM25 (Keyword Search) to give you Hybrid Search capabilities,
    with proper score fusion and support for deleting a document's
    chunks out of the index.
    """
    def __init__(self, save_dir="./vectorstore", dimension=3072):
        # 1. Configuration
        self.save_dir = save_dir
        self.dimension = dimension
        self.index_file = os.path.join(save_dir, "index.faiss")
        self.docs_file = os.path.join(save_dir, "docs.pkl")
        self.embeddings_file = os.path.join(save_dir, "embeddings.pkl")

        # 2. State Variables
        self.index = None
        self.documents = []           # Text chunks + metadata
        self.embeddings = []          # Raw vectors, same order/index as self.documents
        self.document_hashes = set()  # Tracks duplicates
        self.bm25 = None              # Keyword search engine

        os.makedirs(self.save_dir, exist_ok=True)
        self.load_index()

    # ==========================================
    # CORE LOGIC & HELPERS
    # ==========================================

    def _get_hash(self, text):
        """Creates a unique ID for a chunk of text to prevent duplicate uploads."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _tokenize(self, text):
        """Splits text into words for the BM25 keyword search."""
        return re.findall(r'\w+', text.lower())

    def _rebuild_bm25(self):
        """Rebuilds the keyword search engine based on current documents."""
        if not self.documents:
            self.bm25 = None
            return

        tokenized_docs = [self._tokenize(doc["text"]) for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized_docs)
        logger.info("BM25 Keyword index rebuilt.")

    def _reciprocal_rank_fusion(self, vector_results: list, keyword_results: list, k: int = 60) -> list:
        """
        Fuses vector and keyword result rankings instead of just
        concatenating them, so a strong keyword match (e.g. an exact
        part number) can outrank a weak semantic-only match.
        """
        scores = {}
        for rank, doc in enumerate(vector_results):
            scores[doc["hash"]] = scores.get(doc["hash"], 0) + 1 / (k + rank)
        for rank, doc in enumerate(keyword_results):
            scores[doc["hash"]] = scores.get(doc["hash"], 0) + 1 / (k + rank)

        all_docs = {d["hash"]: d for d in vector_results + keyword_results}
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [all_docs[h] for h, _ in ranked]

    # ==========================================
    # ADDING DATA (BATCH PROCESSING)
    # ==========================================

    def add_documents(self, chunks: list, embeddings, source_filename: str):
        """
        Takes a list of text chunks and their embeddings, and adds them to the store.
        Batch processing is much faster and safer than adding them one by one.
        """
        if not chunks or embeddings is None or len(embeddings) == 0:
            logger.warning("No chunks or embeddings provided.")
            return

        new_embeddings = []
        new_docs = []

        for chunk, emb in zip(chunks, embeddings):
            text_hash = self._get_hash(chunk)

            if text_hash not in self.document_hashes:
                new_embeddings.append(emb)
                new_docs.append({
                    "text": chunk,
                    "hash": text_hash,
                    "metadata": {"source": source_filename}
                })
                self.document_hashes.add(text_hash)

        if not new_embeddings:
            logger.info("All chunks were duplicates. Nothing new added.")
            return

        embeddings_array = np.array(new_embeddings).astype("float32")
        faiss.normalize_L2(embeddings_array)
        self.index.add(embeddings_array)
        self.documents.extend(new_docs)
        self.embeddings.extend(new_embeddings)
        self.save_index()
        logger.info(f"✅ Successfully added {len(new_docs)} new chunks from {source_filename}.")

    # ==========================================
    # REMOVING DATA
    # ==========================================

    def delete_by_source(self, source_filename: str) -> int:
        """
        Removes every chunk belonging to a given source file and rebuilds
        the FAISS + BM25 indexes to exclude them. Returns the number of
        chunks removed. IndexFlatIP has no cheap removal-by-id, so we
        rebuild from the surviving embeddings.
        """
        keep_docs, keep_embeddings = [], []
        removed = 0

        for doc, emb in zip(self.documents, self.embeddings):
            if doc["metadata"].get("source") == source_filename:
                self.document_hashes.discard(doc["hash"])
                removed += 1
            else:
                keep_docs.append(doc)
                keep_embeddings.append(emb)

        self.documents = keep_docs
        self.embeddings = keep_embeddings

        self.index = faiss.IndexFlatIP(self.dimension)
        if keep_embeddings:
            arr = np.array(keep_embeddings).astype("float32")
            faiss.normalize_L2(arr)
            self.index.add(arr)

        self._rebuild_bm25()
        self.save_index()
        logger.info(f"🗑️ Removed {removed} chunks for source '{source_filename}'.")
        return removed

    # ==========================================
    # SEARCHING DATA
    # ==========================================

    def hybrid_search(self, query: str, query_embedding: list, top_k: int = 5):
        """
        Combines Vector Search (meaning) and Keyword Search (exact words)
        using Reciprocal Rank Fusion for the best possible RAG retrieval.
        """
        if self.index.ntotal == 0:
            logger.warning("Database is empty. Returning nothing.")
            return []

        q_emb_array = np.array([query_embedding]).astype("float32")
        faiss.normalize_L2(q_emb_array)

        distances, indices = self.index.search(q_emb_array, top_k * 2)

        vector_results = []
        for idx in indices[0]:
            if 0 <= idx < len(self.documents):
                vector_results.append(self.documents[idx])

        keyword_results = []
        if self.bm25 is not None:
            scores = self.bm25.get_scores(self._tokenize(query))
            ranked_indices = np.argsort(scores)[::-1][:top_k * 2]
            keyword_results = [self.documents[i] for i in ranked_indices if scores[i] > 0]

        fused_results = self._reciprocal_rank_fusion(vector_results, keyword_results)
        return fused_results[:top_k]

    # ==========================================
    # SAVING & LOADING (PERSISTENCE)
    # ==========================================

    def save_index(self):
        """Saves the FAISS index, text chunks, and their embeddings to disk."""
        try:
            faiss.write_index(self.index, self.index_file)
            with open(self.docs_file, "wb") as f:
                pickle.dump(self.documents, f)
            with open(self.embeddings_file, "wb") as f:
                pickle.dump(self.embeddings, f)

            self._rebuild_bm25()
            logger.info("💾 Index, documents, and embeddings saved to disk successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to save index: {e}")

    def load_index(self):
        """Loads data from the hard drive into memory."""
        if os.path.exists(self.index_file) and os.path.exists(self.docs_file):
            try:
                self.index = faiss.read_index(self.index_file)
                with open(self.docs_file, "rb") as f:
                    self.documents = pickle.load(f)

                # Older saves won't have an embeddings file — fall back to
                # empty so delete_by_source() has something to work with
                # going forward, instead of crashing on load.
                if os.path.exists(self.embeddings_file):
                    with open(self.embeddings_file, "rb") as f:
                        self.embeddings = pickle.load(f)
                else:
                    logger.warning(
                        "⚠ No embeddings file found (pre-upgrade index). "
                        "delete_by_source() won't work correctly until documents are re-uploaded."
                    )
                    self.embeddings = []

                self.document_hashes = {doc["hash"] for doc in self.documents}
                self._rebuild_bm25()

                logger.info(f"✅ Loaded existing database: {len(self.documents)} chunks.")
            except Exception as e:
                logger.error(f"⚠ Corrupted save files: {e}. Starting fresh.")
                self._initialize_empty_state()
        else:
            logger.info("🆕 No existing database found. Creating a new one.")
            self._initialize_empty_state()

    def _initialize_empty_state(self):
        """Creates a fresh, empty database."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.documents = []
        self.embeddings = []
        self.document_hashes = set()
        self.bm25 = None


# ==========================================
# HOW TO USE THIS IN FASTAPI
# ==========================================
# Instantiate this ONCE at the top of your main FastAPI file.
# Do NOT create a new one inside your routes.

vector_store = VectorService(save_dir=SAVE_DIR, dimension=EMBEDDING_DIMENSION)
