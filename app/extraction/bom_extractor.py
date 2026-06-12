def extract_bom(text):
    """
    Extracts BOM (Bill of Materials) data from text.

    Expected text format example:
    Part Name | Material | Quantity

    Example line:
    Pipe | Steel | 10

    Returns:
    [
        {"part": "Pipe", "material": "Steel", "qty": 10}
    ]
    """

    # List to store extracted BOM parts
    parts = []

    # -------------------------------------------------
    # Step 1: Loop through each line of the input text
    # -------------------------------------------------
    # The text may come from a PDF, CSV, or extracted table.
    for line in text.splitlines():

        # -------------------------------------------------
        # Step 2: Check if the line looks like a table row
        # -------------------------------------------------
        # Many extracted tables use "|" as column separators.
        if "|" in line:

            # Split the line into cells and remove extra spaces
            cells = [c.strip() for c in line.split("|")]

            # -------------------------------------------------
            # Step 3: Validate structure
            # -------------------------------------------------
            # Ensure at least 3 columns exist:
            # Part | Material | Quantity
            # Also verify that the last column is a number
            if len(cells) >= 3 and cells[-1].isdigit():

                # -------------------------------------------------
                # Step 4: Store extracted BOM information
                # -------------------------------------------------
                parts.append({
                    "part": cells[0],       # First column → part name
                    "material": cells[1],   # Second column → material type
                    "qty": int(cells[2])    # Third column → quantity
                })

    # -------------------------------------------------
    # Step 5: Return the extracted BOM list
    # -------------------------------------------------
    return parts