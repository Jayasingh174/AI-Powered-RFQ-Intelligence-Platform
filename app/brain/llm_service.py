from openai import AsyncOpenAI
import logging

from app.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS,
)

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def ask_llm(question: str, context: str = "", mode: str = "qa"):
    """
    Standardizes the LLM call. Adding 'mode' prevents the 
    unexpected keyword argument error.
    """
    # 1. Validation & Logging
    logger.info(f"Processing query. Context length: {len(context) if context else 0}")
    
    if not context or len(context.strip()) < 10:
        logger.warning("Empty context provided to LLM.")
        return "No relevant data found in uploaded documents. Please ensure your files contain readable text."

    try:
        # 2. Token Safety (Optimized for modern 128k context models)
        # 100,000 characters is roughly 25,000 tokens. 
        safe_context = context[:100000] 

        # 3. System Instructions (Optimized for your BOQ/RFQ format & UI requirements)
        system_prompt = (
            "You are an intelligent Document Analysis Assistant powered by RAG.\n"
            "Answer the user's question strictly using the provided context. "
            "If the exact information is missing from the context, state exactly: 'Information not available in the documents.' Do not guess or assume.\n\n"
            "*** CRITICAL FORMATTING RULES ***\n"
            "1. FOR TABLES: If summarizing data, comparing documents, or listing items, use standard Markdown tables. DO NOT wrap Markdown tables inside code blocks or triple backticks.\n"
            "2. FOR CSV/CODE: If the user explicitly asks for a CSV file, raw code, or raw data, you MUST wrap the dataset inside a markdown code block using triple backticks (e.g., ```csv )."
        )

        # 4. LLM Call
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{safe_context}\n\nQuestion: {question}"}
            ],
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
        )

        # 5. Robust Extraction
        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            return "Information not available in the documents."

        return answer.strip()

    except Exception as e:
        logger.error(f"LLM Integration Error: {str(e)}", exc_info=True)
        return "LLM processing failed. Please check API connectivity or model availability."
