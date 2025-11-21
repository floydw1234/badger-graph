#!/usr/bin/env python3
"""Debug all imports"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

client = DgraphClient()

# Query all imports
query = """
query {
    imports: queryImport(first: 100) {
        module
        file
        text
    }
}
"""

result = client.execute_graphql_query(query, {})

print("All Import nodes (first 100):")
print("=" * 80)

imports = result.get("imports", [])
print(f"Total: {len(imports)}")

# Filter for encryption-related
encryption_imports = []
for imp in imports:
    module = imp.get("module", "")
    text = imp.get("text", "")
    if "encryption" in module.lower() or "encryption" in text.lower():
        encryption_imports.append(imp)

print(f"\nEncryption-related imports: {len(encryption_imports)}")
for imp in encryption_imports:
    print(f"  Module: {imp.get('module', 'MISSING')}")
    print(f"  File: {imp.get('file', 'N/A')}")
    print(f"  Text: {imp.get('text', 'N/A')[:60]}")
    print()

