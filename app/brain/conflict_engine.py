import difflib
import re
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

def extract_numbers(text: str) -> set:
    """
    Extracts all numbers (including decimals) from a string.
    Returns a set of strings to allow for easy comparison.
    """
    return set(re.findall(r'\d*\.?\d+', text))

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
        
        source_totals = defaultdict(float) # Default to float for safe math
        
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