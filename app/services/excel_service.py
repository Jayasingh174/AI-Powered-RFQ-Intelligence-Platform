import pandas as pd
import logging
import os

logger = logging.getLogger(__name__)

def extract_boq_data(file_path: str) -> list:
    """
    Reads an Excel BOQ and returns a flat list of row dictionaries.
    """
    if not os.path.exists(file_path):
        logger.error(f"❌ File not found at path: {file_path}")
        return []

    logger.info(f"📂 Attempting to read BOQ from: {file_path}")
    
    # Auto-detect the correct engine based on the file extension
    engine = 'openpyxl' if file_path.endswith('.xlsx') else 'xlrd'

    try:
        # header=None ensures pandas doesn't accidentally use a random logo row as your column keys
        sheets = pd.read_excel(file_path, sheet_name=None, engine=engine)
    except Exception as e:
        logger.error(f"❌ Critical failure reading {file_path}. Error: {str(e)}")
        raise ValueError(f"Failed to read Excel file: {str(e)}")

    all_rows = []

    for sheet_name, df in sheets.items():
        logger.info(f"Processing sheet: {sheet_name} (Rows: {len(df)})")
        
        # Clean up the dataframe by dropping completely empty rows and columns
        df = df.dropna(how='all')
        df = df.dropna(axis=1, how='all')
        
        # Replace NaN values with empty strings so our parsers don't crash
        df = df.fillna("")

        if df.empty:
            logger.warning(f"⚠️ Sheet '{sheet_name}' is empty after cleaning. Skipping.")
            continue

        # Convert the dataframe into a list of dictionaries
        sheet_rows = df.to_dict(orient="records")
        all_rows.extend(sheet_rows)

    logger.info(f"✅ Extracted {len(all_rows)} raw rows from Excel.")
    return all_rows