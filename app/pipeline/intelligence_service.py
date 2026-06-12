import json
import logging
import re
from typing import Dict
from app.brain.llm_service import ask_llm

logger = logging.getLogger(__name__)

class DocumentIntelligence:

    async def extract_structured_data(self, raw_text: str) -> Dict:

        prompt = f"""
You are an AI that extracts structured data.

Return ONLY valid JSON. No explanation. No markdown.

STRICT FORMAT:
{{
  "project": "string",
  "items": [
    {{
      "name": "string",
      "qty": number,
      "specification": "string"
    }}
  ]
}}

RULES:
- qty must be a number
- if missing, use 1
- DO NOT return text outside JSON

TEXT:
{raw_text[:6000]}
"""

        raw_json_str = ""

        try:
            # 1️⃣ Call LLM
            raw_json_str = await ask_llm(prompt, context="")

            if not raw_json_str or not raw_json_str.strip():
                raise ValueError("Empty LLM response")

            clean_text = raw_json_str.strip()

            # --------------------------------------------------
            # 2️⃣ Remove markdown blocks
            # --------------------------------------------------
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_text, re.DOTALL)
            if match:
                clean_text = match.group(1)

            # --------------------------------------------------
            # 3️⃣ Extract JSON if extra text exists
            # --------------------------------------------------
            json_match = re.search(r"\{.*\}", clean_text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(0)

            # --------------------------------------------------
            # 4️⃣ Fix common JSON issues (🔥 important)
            # --------------------------------------------------
            clean_text = clean_text.replace("\n", " ")
            clean_text = re.sub(r",\s*}", "}", clean_text)  # trailing commas
            clean_text = re.sub(r",\s*]", "]", clean_text)

            # --------------------------------------------------
            # 5️⃣ Parse JSON
            # --------------------------------------------------
            structured_data = json.loads(clean_text)

            # --------------------------------------------------
            # 6️⃣ Validate structure (🔥 MUST)
            # --------------------------------------------------
            if "items" not in structured_data:
                structured_data["items"] = []

            for item in structured_data["items"]:
                item["name"] = item.get("name", "Unknown Item")
                item["qty"] = item.get("qty", 1)
                item["specification"] = item.get("specification", "")

            return structured_data

        except Exception as e:
            logger.error(f"❌ JSON parsing failed: {e}")
            logger.error(f"🔴 Raw LLM output: {raw_json_str}")

            # --------------------------------------------------
            # 🔥 FALLBACK (Never crash pipeline)
            # --------------------------------------------------
            return {
                "project": "Unknown Project",
                "items": []
            }