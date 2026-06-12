import os


def extract_text(file_path: str) -> str:
    """
    Extract text from TXT files.
    Designed for RAG pipelines before chunking and embedding.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Text file not found: {file_path}")

    try:

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Basic cleaning
        text = text.replace("\r", "\n")
        text = text.strip()

        if not text:
            raise ValueError("TXT file is empty")

        return text

    except UnicodeDecodeError:
        # fallback for non-utf8 files
        with open(file_path, "r", encoding="latin-1") as f:
            text = f.read()

        return text.strip()

    except Exception as e:
        raise RuntimeError(f"TXT extraction failed: {e}")