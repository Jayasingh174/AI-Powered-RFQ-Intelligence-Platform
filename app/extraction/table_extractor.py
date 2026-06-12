def extract_tables(text: str):

    if not text:
        return []

    tables = []

    for line in text.splitlines():
        line = line.strip()

        if "|" in line and len(line) > 3:
            tables.append(line)

    return tables