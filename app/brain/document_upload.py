"""
RAG AI System - Document State Manager
Handles reading the actual file system to ensure the UI is always
in sync with the hard drive.
"""

import os

UPLOAD_DIR = "uploads"

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
    """
    file_path = os.path.join(UPLOAD_DIR, name)
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False