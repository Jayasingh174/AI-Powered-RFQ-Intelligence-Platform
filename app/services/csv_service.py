import pandas as pd
import os

def extract_csv(file_path: str) -> str:
    """
    Extracts text from a CSV file and converts rows into structured sentences.
    Optimized for RAG (Retrieval-Augmented Generation) context windows.
    """
    # 1. Safety Check: Does the file exist?
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: The file {file_path} could not be located.")

    try:
        # 2. Encoding Fallback: Users often upload Excel-generated CSVs 
        # that use Windows encoding instead of standard UTF-8.
        df = pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding='cp1252')
        
    # 3. Handle empty uploads
    if df.empty:
        return "The uploaded CSV document contains no data."

    # 4. Context Window Optimization: Drop columns that are entirely empty 
    # to save AI token costs and reduce noise.
    df.dropna(how='all', axis=1, inplace=True)

    rows = []
    
    for index, row in df.iterrows():
        # Clean the data: strip whitespace and ignore empty string values
        row_elements = [
            f"{col}: {str(row[col]).strip()}" 
            for col in df.columns 
            if pd.notna(row[col]) and str(row[col]).strip() != ""
        ]
        
        # 5. Citation Anchor: Add the row number so the LLM can explicitly 
        # tell the user "Found on Row 12" in the chat interface.
        if row_elements:
            row_text = f"Row {index + 1}: " + " | ".join(row_elements)
            rows.append(row_text)

    # Use double newlines so your chunk_service.py can easily split the text by paragraph
    return "\n\n".join(rows)