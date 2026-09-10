import numpy as np
import logging
import asyncio
from typing import List
from openai import AsyncOpenAI
from app.config import OPENAI_API_KEY, EMBEDDING_MODEL, MAX_RETRIES  # 🔧 FIX: import MAX_RETRIES

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
logger = logging.getLogger(__name__)

# ------------------------------
# Utility: Retry Wrapper
# ------------------------------
async def with_retry(func, *args, retries=MAX_RETRIES, delay=1, **kwargs):  # 🔧 FIX: default from config
    """
    Safely retries an async function by creating a fresh coroutine
    on every attempt.
    """
    for attempt in range(retries):
        try:
            # Generate and await a fresh coroutine every loop
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == retries - 1:
                logger.error(f"❌ API call failed after {retries} attempts: {e}")
                raise
            logger.warning(f"⚠️ API attempt {attempt + 1} failed. Retrying in {delay * (2 ** attempt)}s...")
            await asyncio.sleep(delay * (2 ** attempt))

# ------------------------------
# Batch Embeddings
# ------------------------------
async def embed_texts(
    texts: List[str],
    batch_size: int = 32
) -> np.ndarray:
    if not texts:
        return np.array([], dtype="float32")

    embeddings_list = []

    for i in range(0, len(texts), batch_size):
        original_batch = texts[i:i + batch_size]
        cleaned_batch = [t.strip() if isinstance(t, str) else "" for t in original_batch]

        try:
            response = await asyncio.wait_for(
                with_retry(
                    client.embeddings.create,
                    model=EMBEDDING_MODEL,
                    input=cleaned_batch
                ),
                timeout=30
            )

            for idx, data in enumerate(response.data):
                if cleaned_batch[idx]:
                    embeddings_list.append(np.array(data.embedding, dtype="float32"))
                else:
                    dim = len(response.data[0].embedding)
                    embeddings_list.append(np.zeros(dim, dtype="float32"))

        except Exception as e:
            logger.exception(f"Embedding batch failed at index {i}: {e}")
            dim = len(embeddings_list[0]) if embeddings_list else 3072
            for _ in original_batch:
                embeddings_list.append(np.zeros(dim, dtype="float32"))

    if not embeddings_list:
        return np.array([], dtype="float32")

    return np.vstack(embeddings_list)

# ------------------------------
# Single Query Embedding
# ------------------------------
async def embed_query(text: str) -> np.ndarray:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Query text cannot be empty.")

    try:
        response = await asyncio.wait_for(
            with_retry(
                client.embeddings.create,
                model=EMBEDDING_MODEL,
                input=text.strip()
            ),
            timeout=30
        )

        embedding = np.array(response.data[0].embedding, dtype="float32")

        if embedding.ndim != 1:
            raise ValueError("Invalid embedding shape")

        logger.info(f"Query embedding generated. Shape: {embedding.shape}")
        return embedding

    except Exception as e:
        logger.exception(f"Failed to embed query: {e}")
        raise
