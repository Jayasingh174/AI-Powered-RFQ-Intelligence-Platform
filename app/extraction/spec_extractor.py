import re

def extract_specs(text):

    specs = {}

    patterns = {
        "material": r"material\s*:\s*([^\n]+)",
        "tolerance": r"tolerance\s*:\s*([^\n]+)",
        "surface_finish": r"surface\s*finish\s*:\s*([^\n]+)",
        "coating": r"coating\s*:\s*([^\n]+)",
        "heat_treatment": r"heat\s*treatment\s*:\s*([^\n]+)"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            specs[key] = match.group(1).strip()

    return specs