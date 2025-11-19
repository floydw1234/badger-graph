"""Utilities for generating Dgraph namespace IDs from folder paths."""

import hashlib
from pathlib import Path


def get_namespace_from_path(folder_path: Path) -> int:
    """Generate a deterministic namespace ID from a folder path.
    
    Uses SHA256 hash of the absolute path to generate a consistent namespace ID.
    The hash is converted to an integer in a safe range for Dgraph namespaces.
    
    Args:
        folder_path: Path to the folder to index
    
    Returns:
        Namespace ID (integer)
    """
    # Get absolute path and normalize
    abs_path = str(folder_path.resolve())
    
    # Hash the path
    hash_obj = hashlib.sha256(abs_path.encode('utf-8'))
    hash_hex = hash_obj.hexdigest()
    
    # Convert to integer, but keep it in a reasonable range
    # Use first 8 hex digits (32 bits) to ensure it fits in int32
    # Dgraph namespaces are typically small integers, but we use the full range
    namespace_int = int(hash_hex[:8], 16)
    
    # Ensure it's positive (Python int can be negative)
    # Use modulo to keep it in a reasonable range if needed
    # Dgraph supports namespace IDs from 0 to 2^31-1
    namespace_int = abs(namespace_int) % (2**31)
    
    return namespace_int


def get_namespace_name(folder_path: Path) -> str:
    """Get a human-readable namespace name from a folder path.
    
    Args:
        folder_path: Path to the folder
    
    Returns:
        Namespace name (based on folder name)
    """
    return folder_path.resolve().name

