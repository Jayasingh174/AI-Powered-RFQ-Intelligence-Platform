import json
import logging
import re
from typing import Dict

from app.brain.llm_service import ask_llm
from app.brain.chunk_service import chunk_text

logger = logging.getLogger(__name__)


class DocumentIntelligence:
    """
    Converts unstructured raw text from multiple document sources
    into structured, machine-readable JSON requirements.
    """

    EXTRACTION_INSTRUCTION = (
        "Extract the following attributes into a strict JSON format:\n"
        "- project (The name of the RFQ/Project)\n"
        "- items (A list containing: name, qty, specification)\n\n"
        "Return ONLY valid JSON. Do not include conversational text or markdown blocks."
    )

    MAX_EXTRACTION_CHARS = 8000

    def _build_extraction_context(self, raw_text: str) -> str:
        """
        Builds the text window sent to the LLM for structured extraction.

        Uses the same paragraph/sentence-aware splitter as the RAG pipeline
        (chunk_service.chunk_text) instead of a blind raw_text[:N] slice, so
        the 8000-char cutoff lands on a clean chunk boundary rather than
        mid-table-row or mid-sentence — important here specifically because
        a truncated BOM/spec line right at the cutoff can silently drop or
        corrupt an item the LLM is being asked to extract.
        """
        chunks = chunk_text(raw_text)

        if not chunks:
            # Fallback: chunk_text() may return nothing for very short text
            # (its own filtering drops fragments under 30 chars). In that
            # case there's nothing worth chunk-aligning anyway.
            return raw_text[: self.MAX_EXTRACTION_CHARS]

        context = ""
        for chunk in chunks:
            if len(context) + len(chunk) > self.MAX_EXTRACTION_CHARS:
                break
            context += chunk + "\n\n"

        return context.strip() or raw_text[: self.MAX_EXTRACTION_CHARS]

    async def extract_structured_data(self, raw_text: str) -> Dict:
        """
        Sends raw text to the LLM and parses the result into a clean
        Project/Items JSON structure.
        """
        raw_json_str = ""
        try:
            # 1. Call the LLM.
            # ask_llm() is grounded QA: it answers `question` strictly from
            # `context`, and short-circuits with a fallback message if
            # context is empty/too short. So the document text goes in
            # `context` (what to extract FROM) and the extraction ask goes
            # in `question` (what to DO with it).
            extraction_context = self._build_extraction_context(raw_text)

            raw_json_str = await ask_llm(
                question=self.EXTRACTION_INSTRUCTION,
                context=extraction_context,
            )

            if not raw_json_str or not raw_json_str.strip():
                raise ValueError("LLM returned an empty response")

            # 2. Clean LLM Output (Remove markdown if present)
            clean_json = raw_json_str.strip()

            # Extract JSON inside ```json ... ``` OR ``` ... ```
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_json, re.DOTALL)
            if match:
                clean_json = match.group(1)

            # 3. Parse JSON
            structured_data = json.loads(clean_json)
            return structured_data

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Raw LLM output: {raw_json_str}")
            raise ValueError("Invalid JSON returned from LLM")

        except Exception as e:
            logger.error(f"Error in extract_structured_data: {e}")
            raise
