"""Hash cache for incremental indexing.

Stores hashes of indexed nodes to skip unchanged nodes on subsequent indexing runs.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Dict, Set, Any, Optional

try:
    import orjson
except ImportError:
    orjson = None

logger = logging.getLogger(__name__)


def get_user_hash_cache_path() -> Path:
    """Get the path to user-level hash cache file.
    
    Returns:
        Path to ~/.badger/node_hashes.json (or ~/.config/badger/node_hashes.json if XDG_CONFIG_HOME is set)
    """
    from .workspace_metadata import get_user_badger_dir
    return get_user_badger_dir() / "node_hashes.json"


class HashCache:
    """Manages hash cache for incremental indexing."""
    
    def __init__(self, cache_file: Path):
        """Initialize hash cache.
        
        Args:
            cache_file: Path to the cache file (JSON format)
        """
        self.cache_file = cache_file
        self.cache: Set[str] = set()
        logger.info(f"Initializing hash cache from: {cache_file}")
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load hash cache from file."""
        exists = self.cache_file.exists()
        logger.info(f"Loading hash cache from {self.cache_file} - exists: {exists}")
        if exists:
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.cache = set(data.get("hashes", []))
                logger.info(f"Loaded {len(self.cache)} hashes from cache")
            except Exception as e:
                logger.warning(f"Failed to load hash cache: {e}, starting with empty cache")
                self.cache = set()
        else:
            logger.warning("Cache file not found, starting with empty cache")
            self.cache = set()
    
    def save_cache(self) -> None:
        """Save hash cache to file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump({"hashes": list(self.cache)}, f, indent=2)
            file_size = self.cache_file.stat().st_size if self.cache_file.exists() else 0
            logger.info(f"Saved {len(self.cache)} hashes to cache file: {self.cache_file} (size: {file_size} bytes)")
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
        result = node_hash in self.cache
        if node_hash:
            hash_prefix = node_hash[:12] if len(node_hash) >= 12 else node_hash
            logger.debug(f"Hash check {hash_prefix}...: {'[HIT]' if result else '[MISS]'}")
        return result
    
    def add_hash(self, node_hash: str) -> None:
        """Add a hash to the cache.
        
        Args:
            node_hash: Hash to add
        """
        if node_hash:
            hash_prefix = node_hash[:12] if len(node_hash) >= 12 else node_hash
            logger.debug(f"Adding hash to cache: {hash_prefix}...")
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
        hash_data.update({
            "name": node_data.get("name", ""),
            "file": node_data.get("file", ""),
            "line": node_data.get("line", 0),
            "column": node_data.get("column", 0),
            "methods": sorted(node_data.get("methods", [])) if node_data.get("methods") else [],
            "base_classes": sorted(node_data.get("base_classes", [])) if node_data.get("base_classes") else [],
        })
    elif node_type == "Struct":
        hash_data.update({
            "name": node_data.get("name", ""),
            "file": node_data.get("file", ""),
            "line": node_data.get("line", 0),
            "column": node_data.get("column", 0),
            "fields": sorted(node_data.get("fields", [])) if node_data.get("fields") else [],
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


def calculate_node_hash_from_dgraph_node(node: Dict[str, Any]) -> Optional[str]:
    """Calculate hash directly from a Dgraph node dict.
    
    Excludes only generated fields (uid, embeddings). Includes all relationships
    since they're part of the node's state. Relationship lists are sorted for
    deterministic hashing.
    
    Args:
        node: Dgraph node dictionary (with keys like "Function.name", "Class.file", etc.)
    
    Returns:
        Hash string if node has content, None otherwise
    """
    # Filter out generated fields that should NOT affect the hash:
    # - uid: Database ID (generated, not part of content)
    # - *.embedding: Embeddings (generated from content, expensive to regenerate)
    #   These are excluded so hash only reflects actual code content, not generated vectors
    hashable = {}
    relationship_keys = []
    for k, v in node.items():
        # Skip uid, embeddings, positional metadata (line/column), and temporary fields
        # Line/column are positional and change when comments are added, not content changes
        # _func_data, _class_data, _struct_data are temporary fields used for embedding generation
        if k == "uid" or k.endswith(".embedding") or k.endswith(".line") or k.endswith(".column") or k.startswith("_"):
            continue
        
        # Normalize relationship lists for deterministic hashing
        # Relationship lists contain dicts like [{"uid": "_:abc123..."}, {"uid": "_:def456..."}]
        # UIDs are already hash prefixes (16-char hex from SHA256), so we just extract and sort them
        # This preserves relationship identity while being stable across runs
        is_relationship_list = False
        if isinstance(v, list) and len(v) > 0:
            # Check if it's a relationship list (contains dicts with "uid" keys)
            if isinstance(v[0], dict) and "uid" in v[0]:
                # Extract UIDs: remove "_: " prefix if present, UID is already a stable hash prefix
                normalized_uids = []
                for item in v:
                    uid = item.get("uid", "")
                    if uid:
                        # Remove "_: " prefix if present - UID is already a 16-char hash prefix
                        uid_clean = uid.replace("_:", "").strip()
                        # UID is already a hash prefix (16 chars from SHA256), use as-is
                        normalized_uids.append(uid_clean)
                
                # Sort normalized UIDs for deterministic ordering
                normalized_uids = sorted(normalized_uids)
                v = normalized_uids  # Replace list with sorted list of UID hash prefixes
                is_relationship_list = True
                relationship_keys.append((k, len(v), True))
                logger.debug(f"Relationship {k}: normalized {len(v)} UIDs (using hash prefixes directly)")
        
        hashable[k] = v
    
    if not hashable:
        return None
    
    # Log all keys in hashable dict for first few nodes (DEBUG level)
    # Use a simple counter to limit logging
    if not hasattr(calculate_node_hash_from_dgraph_node, '_log_count'):
        calculate_node_hash_from_dgraph_node._log_count = 0
    
    sorted_keys = sorted(hashable.keys())
    
    # Log at INFO level for Function/Class nodes to see what's being hashed
    node_type = "unknown"
    node_name = "unknown"
    if "Function.name" in hashable:
        node_type = "Function"
        node_name = hashable.get("Function.name", "unknown")
    elif "Class.name" in hashable:
        node_type = "Class"
        node_name = hashable.get("Class.name", "unknown")
    
    if node_type in ["Function", "Class"] and calculate_node_hash_from_dgraph_node._log_count < 5:
        logger.info(f"Hash calculation for {node_type} '{node_name}':")
        logger.info(f"  Keys in hash ({len(sorted_keys)}): {', '.join(sorted_keys)}")
        # Check if line/column are present (they shouldn't be)
        has_line = any(k.endswith(".line") for k in sorted_keys)
        has_column = any(k.endswith(".column") for k in sorted_keys)
        if has_line or has_column:
            logger.warning(f"  WARNING: Found .line or .column in hash! This should be excluded!")
        # Show sample of non-relationship fields
        non_rel_keys = [k for k in sorted_keys if not any(rel in k for rel in [
            "callsFunction", "calledByFunction", "inheritsClass", "containsFunction",
            "containsClass", "containsImport", "usesMacro", "usesVariable", "usesTypedef"
        ])]
        logger.info(f"  Non-relationship fields: {', '.join(non_rel_keys)}")
        if relationship_keys:
            logger.info(f"  Relationship fields: {', '.join([k for k, _, _ in relationship_keys])}")
            # Show sample relationship UIDs
            for k, count, _ in relationship_keys[:2]:
                rel_list = hashable.get(k, [])
                if isinstance(rel_list, list) and len(rel_list) > 0:
                    sample_uids = [str(uid)[:16] for uid in rel_list[:3]]
                    logger.info(f"    {k}: {count} items, sample UID prefixes: {sample_uids}")
        calculate_node_hash_from_dgraph_node._log_count += 1
    elif logger.isEnabledFor(logging.DEBUG) and calculate_node_hash_from_dgraph_node._log_count < 3:
        logger.debug(f"Hashable dict keys ({len(sorted_keys)}): {', '.join(sorted_keys)}")
        if relationship_keys:
            logger.debug(f"Relationship lists: {', '.join([f'{k}({count}, sorted={sorted})' for k, count, sorted in relationship_keys])}")
        calculate_node_hash_from_dgraph_node._log_count += 1
    
    # Use orjson for fast serialization with sorted keys
    if orjson:
        try:
            data = orjson.dumps(hashable, option=orjson.OPT_SORT_KEYS)
            hash_result = hashlib.sha256(data).hexdigest()
            logger.debug(f"Calculated hash: {hash_result[:12]}...")
            return hash_result
        except Exception as e:
            logger.warning(f"Failed to hash node with orjson: {e}, falling back to json")
    
    # Fallback to json if orjson not available or fails
    json_str = json.dumps(hashable, sort_keys=True, separators=(',', ':'))
    hash_result = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    logger.debug(f"Calculated hash (json fallback): {hash_result[:12]}...")
    return hash_result

