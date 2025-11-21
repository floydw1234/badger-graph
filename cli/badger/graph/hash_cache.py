"""Hash cache for incremental indexing.

Stores hashes of indexed nodes to skip unchanged nodes on subsequent indexing runs.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Set, Any, Optional

logger = logging.getLogger(__name__)


class HashCache:
    """Manages hash cache for incremental indexing."""
    
    def __init__(self, cache_file: Path):
        """Initialize hash cache.
        
        Args:
            cache_file: Path to the cache file (JSON format)
        """
        self.cache_file = cache_file
        self.cache: Set[str] = set()
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load hash cache from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.cache = set(data.get("hashes", []))
                logger.debug(f"Loaded {len(self.cache)} hashes from cache")
            except Exception as e:
                logger.warning(f"Failed to load hash cache: {e}, starting with empty cache")
                self.cache = set()
        else:
            self.cache = set()
    
    def save_cache(self) -> None:
        """Save hash cache to file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump({"hashes": list(self.cache)}, f, indent=2)
            logger.debug(f"Saved {len(self.cache)} hashes to cache")
        except Exception as e:
            logger.warning(f"Failed to save hash cache: {e}")
    
    def clear_cache(self) -> None:
        """Clear the hash cache."""
        self.cache = set()
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
                logger.info("Cleared hash cache")
            except Exception as e:
                logger.warning(f"Failed to delete cache file: {e}")
    
    def has_hash(self, node_hash: str) -> bool:
        """Check if a hash exists in the cache.
        
        Args:
            node_hash: Hash to check
        
        Returns:
            True if hash exists, False otherwise
        """
        return node_hash in self.cache
    
    def add_hash(self, node_hash: str) -> None:
        """Add a hash to the cache.
        
        Args:
            node_hash: Hash to add
        """
        self.cache.add(node_hash)
    
    def get_cache_size(self) -> int:
        """Get the number of hashes in the cache.
        
        Returns:
            Number of cached hashes
        """
        return len(self.cache)


def calculate_node_hash(node_type: str, node_data: Dict[str, Any]) -> str:
    """Calculate a hash for a node based on its content.
    
    The hash is based on the node's identifying and content fields,
    so it will change if the node's content changes.
    
    Args:
        node_type: Type of node (File, Function, Class, etc.)
        node_data: Node data dictionary
    
    Returns:
        SHA256 hash as hex string
    """
    # Create a canonical representation of the node for hashing
    # Include all fields that affect the node's identity and content
    hash_data = {"type": node_type}
    
    if node_type == "File":
        hash_data.update({
            "path": node_data.get("path", ""),
            "functions_count": node_data.get("functions_count", 0),
            "classes_count": node_data.get("classes_count", 0),
            "structs_count": node_data.get("structs_count", 0),
            "imports_count": node_data.get("imports_count", 0),
            "macros_count": node_data.get("macros_count", 0),
            "variables_count": node_data.get("variables_count", 0),
            "typedefs_count": node_data.get("typedefs_count", 0),
            "struct_field_accesses_count": node_data.get("struct_field_accesses_count", 0),
            "ast_nodes": node_data.get("ast_nodes", 0),
        })
    elif node_type == "Function":
        hash_data.update({
            "name": node_data.get("name", ""),
            "file": node_data.get("file", ""),
            "line": node_data.get("line", 0),
            "column": node_data.get("column", 0),
            "signature": node_data.get("signature", ""),
            "parameters": node_data.get("parameters", ""),
            "return_type": node_data.get("return_type", ""),
            "docstring": node_data.get("docstring", ""),
        })
    elif node_type == "Class":
        # Class node hash
        name = node.get("Class.name", "")
        file = node.get("Class.file", "")
        methods = tuple(sorted(node.get("Class.methods", [])))
        base_classes = tuple(sorted(node.get("Class.baseClasses", [])))
        return f"{name}@{file}@{methods}@{base_classes}"
    elif node_type == "Struct":
        # Struct node hash
        name = node.get("Struct.name", "")
        file = node.get("Struct.file", "")
        fields = tuple(sorted(node.get("Struct.fields", [])))
        return f"{name}@{file}@{fields}"
        hash_data.update({
            "name": node_data.get("name", ""),
            "file": node_data.get("file", ""),
            "line": node_data.get("line", 0),
            "column": node_data.get("column", 0),
            "methods": sorted(node_data.get("methods", [])) if node_data.get("methods") else [],
            "base_classes": sorted(node_data.get("base_classes", [])) if node_data.get("base_classes") else [],
        })
    elif node_type == "Import":
        hash_data.update({
            "module": node_data.get("module", ""),
            "file": node_data.get("file", ""),
            "line": node_data.get("line", 0),
            "text": node_data.get("text", ""),
            "imported_items": sorted(node_data.get("imported_items", [])) if node_data.get("imported_items") else [],
            "alias": node_data.get("alias", ""),
        })
    elif node_type == "Macro":
        hash_data.update({
            "name": node_data.get("name", ""),
            "file": node_data.get("file", ""),
            "line": node_data.get("line", 0),
            "column": node_data.get("column", 0),
            "value": node_data.get("value", ""),
            "parameters": sorted(node_data.get("parameters", [])) if node_data.get("parameters") else [],
        })
    elif node_type == "Variable":
        hash_data.update({
            "name": node_data.get("name", ""),
            "file": node_data.get("file", ""),
            "line": node_data.get("line", 0),
            "column": node_data.get("column", 0),
            "type": node_data.get("type", ""),
            "storage_class": node_data.get("storage_class", ""),
            "is_global": node_data.get("is_global", False),
        })
    elif node_type == "Typedef":
        hash_data.update({
            "name": node_data.get("name", ""),
            "file": node_data.get("file", ""),
            "line": node_data.get("line", 0),
            "column": node_data.get("column", 0),
            "underlying_type": node_data.get("underlying_type", ""),
        })
    elif node_type == "StructFieldAccess":
        hash_data.update({
            "struct_name": node_data.get("struct_name", ""),
            "field_name": node_data.get("field_name", ""),
            "file": node_data.get("file", ""),
            "line": node_data.get("line", 0),
            "column": node_data.get("column", 0),
            "access_type": node_data.get("access_type", ""),
        })
    
    # Create a deterministic JSON string (sorted keys, no whitespace)
    json_str = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
    
    # Calculate SHA256 hash
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

