#!/usr/bin/env python3
"""Test matching directly"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

client = DgraphClient()

# Test the matching logic
file_path = "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/encryption/encryption.h"

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

target_modules = set()
rel_path = extract_relative_path(file_path)
target_modules.add(rel_path)
target_modules.add(file_path.split("/")[-1])

print(f"Target modules to search for: {target_modules}")
print()

# Query files and check imports
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

matches_found = []
if "files" in result:
    for file in result.get("files", []):
        file_path_check = file.get("path", "")
        imports = file.get("containsImport", [])
        if not isinstance(imports, list):
            imports = [imports] if imports else []
        
        for imp in imports:
            if not imp:
                continue
            module = imp.get("module")
            if not module:
                continue
            
            # Check matching logic
            matches = False
            if module in target_modules:
                matches = True
            else:
                for target in target_modules:
                    if module == target:
                        matches = True
                        break
                    module_filename = module.split("/")[-1]
                    target_filename = target.split("/")[-1]
                    if module_filename == target_filename:
                        if "/" not in target:
                            matches = True
                            break
                        if module.endswith(target) or target.endswith(module):
                            matches = True
                            break
            
            if matches:
                matches_found.append({
                    "file": file_path_check,
                    "module": module,
                    "text": imp.get("text", "")
                })

print(f"Found {len(matches_found)} matches:")
for m in matches_found:
    print(f"  - {m['file']}")
    print(f"    Module: {m['module']}")
    print(f"    Text: {m['text']}")

