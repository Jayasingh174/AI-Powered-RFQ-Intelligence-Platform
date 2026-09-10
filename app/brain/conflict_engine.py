import difflib
import re
import logging
from collections import defaultdict
from typing import Any, List, Dict

logger = logging.getLogger(__name__)


def extract_numbers(text: str) -> set:
    """
    Extracts all numbers (including decimals) from a string.
    Returns a set of strings to allow for easy comparison.
    """
    return set(re.findall(r'\d*\.?\d+', text))


def normalize_entity(item_name: str, qty: Any, source: str, category: str = "", file_path: str = "") -> Dict[str, Any]:
    """
    Standardizes raw extracted data into a uniform dictionary format
    expected by the conflict engine.
    """
    # Clean the item name
    clean_name = str(item_name).strip() if item_name else "Unknown Item"

    # Safely parse the quantity (fallback to 1.0 if it's text or missing)
    try:
        # Handle cases where quantity might be a string with units like "15 pcs"
        if isinstance(qty, str):
            match = re.search(r"(\d+(\.\d+)?)", qty)
            qty_val = float(match.group(1)) if match else 1.0
        else:
            qty_val = float(qty) if qty is not None else 1.0
    except (ValueError, TypeError):
        qty_val = 1.0

    return {
        "item": clean_name,
        "quantity": qty_val,
        "source": source,
        "category": category,
        "file_path": file_path
    }


def deduplicate_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merges identical items found within the SAME source document.
    (e.g., if "10mm Pipe" appears on page 1 and page 3 of the BOQ,
    this sums their quantities before cross-referencing against CAD).
    """
    deduped_map = {}

    for ent in entities:
        # Create a unique key based on the lowercase item name and its specific source.
        # We also extract numbers to ensure "Pipe 10mm" doesn't merge with "Pipe 20mm"
        numbers_in_name = tuple(extract_numbers(ent["item"]))
        key = (ent["item"].lower(), numbers_in_name, ent["source"])

        if key in deduped_map:
            # If it already exists in this source, add the quantities together
            deduped_map[key]["quantity"] += ent["quantity"]
        else:
            # Otherwise, add it to our tracking map
            deduped_map[key] = ent.copy()

    return list(deduped_map.values())


def detect_conflicts(all_extracted_items: list[dict]) -> dict:
    """
    Cross-references items from multiple files to find quantity mismatches.
    """
    grouped_entities = defaultdict(list)
    canonical_names = []

    # ==========================================
    # PHASE 1: SMART GROUPING & FUZZY MATCHING
    # ==========================================
    for entry in all_extracted_items:
        raw_name = str(entry["item"]).strip().lower()
        entry_numbers = extract_numbers(raw_name)

        potential_matches = difflib.get_close_matches(raw_name, canonical_names, n=3, cutoff=0.75)
        canonical_name = raw_name

        # Safety Check: Only accept a fuzzy match if the extracted numbers match perfectly!
        for match in potential_matches:
            match_numbers = extract_numbers(match)
            if entry_numbers == match_numbers:
                canonical_name = match
                break

        if canonical_name == raw_name and raw_name not in canonical_names:
            canonical_names.append(raw_name)

        grouped_entities[canonical_name].append({
            "quantity": entry.get("quantity", 1),
            "source": entry.get("source", "Unknown")
        })

    conflict_report = []
    full_matrix = []

    # ==========================================
    # PHASE 2: AGGREGATION & CONFLICT DETECTION
    # ==========================================
    for entity, mentions in grouped_entities.items():

        source_totals = defaultdict(float)  # Default to float for safe math

        for m in mentions:
            try:
                # Always treat as float for the addition phase
                qty = float(m["quantity"])
            except ValueError:
                qty = 1.0

            source_totals[m["source"]] += qty

        # 🔥 SAFETY TWEAK: Round to 3 decimal places to prevent floating-point errors,
        # then convert back to an integer if it's a whole number for clean UI presentation.
        clean_source_breakdown = {}
        for source, total in source_totals.items():
            rounded_total = round(total, 3)
            # If it's a perfect whole number (e.g. 5.0), make it an int (5)
            clean_source_breakdown[source] = int(rounded_total) if rounded_total.is_integer() else rounded_total

        # Check for conflicts using our clean numbers
        unique_quantities = set(clean_source_breakdown.values())

        has_conflict = len(clean_source_breakdown) > 1 and len(unique_quantities) > 1

        record = {
            "entity": entity.title(),
            "sources_found": list(clean_source_breakdown.keys()),
            "quantities": clean_source_breakdown,
            "conflict_detected": has_conflict
        }

        if has_conflict:
            conflict_report.append(record)

        full_matrix.append(record)

    # Sort reports alphabetically so they look nice on the frontend
    conflict_report = sorted(conflict_report, key=lambda x: x["entity"])
    full_matrix = sorted(full_matrix, key=lambda x: x["entity"])

    return {
        "total_entities_checked": len(full_matrix),
        "conflicts_found": len(conflict_report),
        "conflict_details": conflict_report,
        "full_matrix": full_matrix
    }
