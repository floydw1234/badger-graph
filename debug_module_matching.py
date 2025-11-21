#!/usr/bin/env python3
"""Debug module matching"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

client = DgraphClient()

# Test file path
file_path = "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/encryption/encryption.h"

# Extract relative path (same logic as in tools.py)
def extract_relative_path(path: str) -> str:
    """Extract relative path component from absolute path."""
    parts = path.split("/")
    if "packages" in parts:
        idx = parts.index("packages")
        return "/".join(parts[idx:])
    elif "src" in parts:
        idx = parts.index("src")
        return "/".join(parts[idx+1:])
    return parts[-1]

rel_path = extract_relative_path(file_path)
print(f"Target file: {file_path}")
print(f"Extracted relative path: {rel_path}")
print(f"Filename only: {file_path.split('/')[-1]}")
print()

# Now check what modules are actually in the graph
query = """
query {
    files: queryFile(first: 10000) {
        path
        containsImport {
            module
            text
        }
    }
}
"""

result = client.execute_graphql_query(query, {})

# Find files that include encryption.h
print("Files that include encryption.h:")
print("=" * 80)

includers = []
for file in result.get("files", []):
    imports = file.get("containsImport", [])
    if not isinstance(imports, list):
        imports = [imports] if imports else []
    
    for imp in imports:
        module = imp.get("module")
        if module and ("encryption.h" in module or "encryption" in module.lower()):
            includers.append({
                "file": file.get("path"),
                "module": module,
                "text": imp.get("text", "")
            })

for item in includers:
    print(f"File: {item['file']}")
    print(f"  Module: {item['module']}")
    print(f"  Text: {item['text']}")
    print()

print(f"\nTotal: {len(includers)} files")
print()

# Check if our target matches
print("Matching check:")
print(f"  Target relative path: '{rel_path}'")
print(f"  Target filename: '{file_path.split('/')[-1]}'")
print()
for item in includers[:3]:
    module = item['module']
    print(f"  Module '{module}' matches '{rel_path}'? {module == rel_path}")
    print(f"  Module '{module}' ends with '{rel_path}'? {module.endswith(rel_path) if rel_path else False}")
    print(f"  Module '{module}' filename matches? {module.split('/')[-1] == file_path.split('/')[-1]}")

