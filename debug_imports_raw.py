#!/usr/bin/env python3
"""Debug script to see raw import data in graph"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

client = DgraphClient()

# Query all imports to see what's actually stored
query = """
query {
    imports: queryImport(first: 100) {
        id
        module
        file
        text
        importedItems
    }
}
"""

result = client.execute_graphql_query(query, {})

print("=" * 80)
print("All Import nodes in graph (first 100):")
print("=" * 80)

imports = result.get("imports", [])
print(f"Total imports found: {len(imports)}\n")

# Filter for encryption-related imports
encryption_imports = []
for imp in imports:
    module = imp.get("module", "")
    text = imp.get("text", "")
    file_path = imp.get("file", "")
    
    if "encryption" in module.lower() or "encryption" in text.lower():
        encryption_imports.append(imp)

print(f"Encryption-related imports: {len(encryption_imports)}\n")
for imp in encryption_imports:
    print(f"File: {imp.get('file', 'N/A')}")
    print(f"  Module: {imp.get('module', 'MISSING!')}")
    print(f"  Text: {imp.get('text', 'N/A')}")
    print(f"  ImportedItems: {imp.get('importedItems', [])}")
    print()

print("=" * 80)
print("Checking specific files that should include encryption.h:")
print("=" * 80)

test_files = [
    "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/tests/envelope_test.c",
    "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/tests/encryption_test.c",
    "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/transactions/envelope_dispatcher.c",
    "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/transactions/envelope.c",
]

for test_file in test_files:
    query2 = """
    query($filePath: String!) {
        file: queryFile(filter: {path: {eq: $filePath}}, first: 1) {
            path
            containsImport {
                id
                module
                text
                importedItems
            }
        }
    }
    """
    result2 = client.execute_graphql_query(query2, {"filePath": test_file})
    if result2.get("file"):
        file_node = result2["file"][0] if isinstance(result2["file"], list) else result2["file"]
        imports = file_node.get("containsImport", [])
        if not isinstance(imports, list):
            imports = [imports] if imports else []
        
        print(f"\n{test_file}:")
        print(f"  Found {len(imports)} imports")
        for imp in imports:
            module = imp.get("module")
            text = imp.get("text", "")
            print(f"    - Module: {module if module else 'MISSING'}")
            print(f"      Text: {text[:80] if text else 'N/A'}")
    else:
        print(f"\n{test_file}: NOT FOUND in graph")

