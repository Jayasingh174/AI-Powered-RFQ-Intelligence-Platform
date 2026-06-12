from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import CHUNK_SIZE, CHUNK_OVERLAP

# Initialize the splitter with a descending hierarchy of separators.
# It tries to keep paragraphs together first (\n\n), and if the chunk is still 
# too big, it falls back to splitting by lines, then sentences, and finally words.
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=[
        "\n\n",
        "\n",
        ". ",
        "; ",
        ", ",
        " "
    ],
)

def chunk_text(text: str) -> list[str]:
    """
    Split text into chunks suitable for embeddings.
    Works well for documents, tables, and CAD outputs.
    """
    
    # Guard clause: Return an empty list early if there's no meaningful text to process
    if not text or not text.strip():
        return []

    # Generate the initial raw chunks based on our size and overlap config
    chunks = splitter.split_text(text)

    cleaned_chunks = []

    for chunk in chunks:
        # Remove leading and trailing whitespace from the chunk
        chunk = chunk.strip()

        # Skip any fully empty chunks that might have resulted from extra newlines
        if not chunk:
            continue

        # Context-aware filtering: 
        # Ignore tiny fragments (like stray page numbers or raw OCR artifacts) 
        # UNLESS they contain a colon (':'), which usually indicates highly important 
        # structured key-value data from a BOM or CAD file (e.g., "Qty: 5" or "Material: Steel").
        if len(chunk) < 30 and ":" not in chunk:
            continue

        # If the chunk passed all the filters, add it to our final list
        cleaned_chunks.append(chunk)

    return cleaned_chunks