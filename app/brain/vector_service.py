import os
import re
import faiss
import pickle
import hashlib
import numpy as np
import logging
from rank_bm25 import BM25Okapi

# Set up simple logging so you can see what the code is doing in your terminal
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class VectorService:
    """
    A unified Vector Store that handles both FAISS (Vector Search) 
    and BM25 (Keyword Search) to give you Hybrid Search capabilities.
    """
    def __init__(self, save_dir="./vectorstore", dimension=3072):
        # 1. Configuration
        self.save_dir = save_dir
        self.dimension = dimension
        self.index_file = os.path.join(save_dir, "index.faiss")
        self.docs_file = os.path.join(save_dir, "docs.pkl")
        
        # 2. State Variables
        self.index = None
        self.documents = []           # Stores the actual text chunks and metadata
        self.document_hashes = set()  # Tracks duplicates
        self.bm25 = None              # Keyword search engine
        
        # Ensure the save directory exists
        os.makedirs(self.save_dir, exist_ok=True)
        
        # Load existing data when the service starts
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

    # ==========================================
    # ADDING DATA (BATCH PROCESSING)
    # ==========================================

    def add_documents(self, chunks: list, embeddings, source_filename: str):
        """
        Takes a list of text chunks and their embeddings, and adds them to the store.
        Batch processing is much faster and safer than adding them one by one.
        """
        # 🔥 FIX: Safe NumPy Array Check (Using "is None or len() == 0")
        if not chunks or embeddings is None or len(embeddings) == 0:
            logger.warning("No chunks or embeddings provided.")
            return

        # Prepare lists for new, non-duplicate data
        new_embeddings = []
        new_docs = []

        # Filter out duplicates
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

        # Convert embeddings to the format FAISS needs (numpy float32 array)
        embeddings_array = np.array(new_embeddings).astype("float32")
        
        # L2 Normalization (Required for Cosine Similarity / Inner Product)
        faiss.normalize_L2(embeddings_array)
        
        # Add to FAISS index
        assert self.index is not None, "FAISS index is not initialized!"
        self.index.add(embeddings_array) # pyright: ignore[reportCallIssue]
        
        # Add to our text database
        self.documents.extend(new_docs)
        
        # Save everything to disk immediately so they stay perfectly in sync
        self.save_index()
        logger.info(f"✅ Successfully added {len(new_docs)} new chunks from {source_filename}.")

    # ==========================================
    # SEARCHING DATA
    # ==========================================

    def hybrid_search(self, query: str, query_embedding: list, top_k: int = 5):
        """
        Combines Vector Search (meaning) and Keyword Search (exact words) 
        for the best possible RAG retrieval.
        """
        if self.index.ntotal == 0: # pyright: ignore[reportOptionalMemberAccess]
            logger.warning("Database is empty. Returning nothing.")
            return []

        # --- 1. Vector Search (FAISS) ---
        q_emb_array = np.array([query_embedding]).astype("float32")
        faiss.normalize_L2(q_emb_array)
        
        # Get distances and indexes from FAISS
        distances, indices = self.index.search(q_emb_array, top_k * 2) # type: ignore
        
        vector_results = []
        for idx in indices[0]:
            if 0 <= idx < len(self.documents):
                vector_results.append(self.documents[idx])

        # --- 2. Keyword Search (BM25) ---
        keyword_results = []
        if self.bm25 is not None:
            scores = self.bm25.get_scores(self._tokenize(query))
            # Get top indices based on score
            ranked_indices = np.argsort(scores)[::-1][:top_k * 2]
            keyword_results = [self.documents[i] for i in ranked_indices if scores[i] > 0]

        # --- 3. Combine Results & Remove Duplicates ---
        combined_dict = {}
        for doc in vector_results + keyword_results:
            # Using the hash as a key ensures we don't return the same chunk twice
            combined_dict[doc["hash"]] = doc 
            
        # Convert back to a list and return only the top_k requested
        final_results = list(combined_dict.values())[:top_k]
        return final_results

    # ==========================================
    # SAVING & LOADING (PERSISTENCE)
    # ==========================================

    def save_index(self):
        """Saves the FAISS index and the text chunks to your hard drive."""
        try:
            faiss.write_index(self.index, self.index_file)
            with open(self.docs_file, "wb") as f:
                pickle.dump(self.documents, f)
            
            # Rebuild keyword search whenever we save new data
            self._rebuild_bm25() 
            logger.info("💾 Index and Documents saved to disk successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to save index: {e}")

    def load_index(self):
        """Loads data from the hard drive into memory."""
        # Check if BOTH files exist. If one is missing, they are out of sync.
        if os.path.exists(self.index_file) and os.path.exists(self.docs_file):
            try:
                self.index = faiss.read_index(self.index_file)
                with open(self.docs_file, "rb") as f:
                    self.documents = pickle.load(f)
                
                # Re-populate the hash set to prevent future duplicates
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
        # IndexFlatIP calculates Cosine Similarity (best for text embeddings)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.documents = []
        self.document_hashes = set()
        self.bm25 = None

# ==========================================
# HOW TO USE THIS IN FASTAPI
# ==========================================
# Instantiate this ONCE at the top of your main FastAPI file.
# Do NOT create a new one inside your routes.

vector_store = VectorService(save_dir="./vectorstore", dimension=3072)