"""
RAG AI System - Document State Manager
Handles reading the actual file system to ensure the UI is always
in sync with the hard drive.
"""
import os

# 🔧 LOGIC FIX: was hardcoded to "uploads" here, duplicating (and
# potentially conflicting with) app.config.UPLOAD_DIR, which is
# env-var-overridable. If UPLOAD_DIR were ever set via .env to point
# somewhere else, upload_router.py would save files there while this
# module kept listing/deleting from a literal "uploads" folder — the
# "Documents" UI would silently go out of sync with where files
# actually live. Sourcing it from config makes the two agree.
from app.config import UPLOAD_DIR

def get_documents():
    """
    Reads the actual files from the hard drive so the list
    survives server restarts.
    """
    if not os.path.exists(UPLOAD_DIR):
        return []
    
    # Check the actual folder on your computer and return the filenames
    files = os.listdir(UPLOAD_DIR)
    
    # Filter out any hidden system files or folders
    clean_files = [f for f in files if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    
    return clean_files
def add_document(name):
    """
    Note: Since we are reading directly from the hard drive now, 
    we don't strictly need to manually append to a list anymore! 
    The file being saved to the 'uploads' folder automatically adds it.
    """
    pass
def delete_document(name):
    """
    Safely deletes the file from the hard drive.

    🔧 LOGIC FIX: 'name' is never sanitized before being joined onto
    UPLOAD_DIR. Since this is called directly from the DELETE
    /delete/{filename} route with the URL path parameter, a filename
    like "../../../some/other/file" would resolve OUTSIDE UPLOAD_DIR
    and os.remove() would delete whatever it points to — a path
    traversal vulnerability. os.path.basename() strips any directory
    components so 'name' can only ever refer to a file directly inside
    UPLOAD_DIR, regardless of what's in the URL.
    """
    safe_name = os.path.basename(name)
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False
