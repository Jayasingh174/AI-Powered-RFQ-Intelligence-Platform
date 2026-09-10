import asyncio
import logging
import pandas as pd
from openai import AsyncOpenAI, APIStatusError, APITimeoutError, RateLimitError

from app.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIStatusError)


async def _call_with_retry(**kwargs):
    """Retries the chat completion call on transient errors only."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return await client.chat.completions.create(**kwargs)
        except RETRYABLE_ERRORS as e:
            last_error = e
            if attempt == MAX_RETRIES - 1:
                logger.error(f"LLM call failed after {MAX_RETRIES} attempts: {e}")
                raise
            delay = 2 ** attempt
            logger.warning(f"LLM attempt {attempt + 1} failed ({e}); retrying in {delay}s")
            await asyncio.sleep(delay)
        except Exception as e:
            # Non-retryable (bad key, invalid request, etc.) — fail fast
            logger.error(f"Non-retryable LLM error: {e}", exc_info=True)
            raise
    raise last_error


async def ask_llm(question: str, context: str = "") -> str:
    logger.info(f"Processing query. Context length: {len(context) if context else 0}")

    if not context or len(context.strip()) < 10:
        logger.warning("Empty context provided to LLM.")
        return "No relevant data found in uploaded documents. Please ensure your files contain readable text."

    try:
        safe_context = context[:100000]
        system_prompt = ("...")  # unchanged

        response = await _call_with_retry(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{safe_context}\n\nQuestion: {question}"}
            ],
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
        )

        answer = response.choices[0].message.content
        return answer.strip() if answer and answer.strip() else "Information not available in the documents."

    except Exception as e:
        logger.error(f"LLM Integration Error: {str(e)}", exc_info=True)
        return "LLM processing failed. Please check API connectivity or model availability."
