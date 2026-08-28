from openai import AsyncOpenAI
import asyncio
import logging

from app.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def ask_llm(question: str, context: str = "", mode: str = "qa"):
    """
    Standardizes the LLM call. Adding 'mode' prevents the 
    unexpected keyword argument error and allows flexible context handling.
    """
    # 1. Validation & Logging
    logger.info(f"Processing query. Context length: {len(context) if context else 0} | Mode: {mode}")
    
    # FIX: Only enforce strict context if mode is "qa" (Strict RAG). 
    # Agents might call this without context for general reasoning.
    if mode == "qa" and (not context or len(context.strip()) < 10):
        logger.warning("Empty context provided to LLM for a QA task.")
        return "No relevant data found in uploaded documents. Please ensure your files contain readable text."

    try:
        # 2. Token Safety (Optimized for modern 128k context models)
        # 100,000 characters is roughly 25,000 tokens. 
        safe_context = context[:100000] if context else ""

        # 3. System Instructions (Optimized for your BOQ/RAG format & UI requirements)
        system_prompt = (
            "You are an intelligent Document Analysis Assistant.\n"
            "If answering based on provided context, strictly use the context. "
            "If the exact information is missing from the context for a document-specific query, state exactly: 'Information not available in the documents.' Do not guess.\n\n"
            "*** CRITICAL FORMATTING RULES ***\n"
            "1. FOR TABLES: If summarizing data, comparing documents, or listing items, use standard Markdown tables. DO NOT wrap Markdown tables inside code blocks or triple backticks.\n"
            "2. FOR CSV/CODE: If the user explicitly asks for a CSV file, raw code, or raw data, you MUST wrap the dataset inside a markdown code block using triple backticks (e.g., ```csv )."
        )

        # Build the user message dynamically
        if safe_context:
            user_content = f"Context:\n{safe_context}\n\nQuestion: {question}"
        else:
            user_content = f"Question: {question}"

        # 4. LLM Call
        #
        # 🔧 LOGIC FIX: this call previously had no retry logic at all — a
        # single transient failure (rate limit, brief network error) fell
        # straight through to the except-block below and returned
        # "LLM processing failed" immediately. config.py declares
        # MAX_RETRIES specifically for this ("Added your retry limit
        # here"), and embedding_service.py already establishes the same
        # exponential-backoff retry pattern for OpenAI calls elsewhere in
        # this codebase — this brings ask_llm() in line with that, so a
        # single rate-limit blip no longer surfaces as a hard failure to
        # the user.
        response = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=OPENAI_TEMPERATURE,
                    max_tokens=OPENAI_MAX_TOKENS,
                )
                break
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                wait = 1 * (2 ** attempt)
                logger.warning(f"⚠️ LLM call attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)

        # 5. Robust Extraction
        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            return "Information not available."

        return answer.strip()

    except Exception as e:
        logger.error(f"LLM Integration Error: {str(e)}", exc_info=True)
        return "LLM processing failed. Please check API connectivity or model availability."
