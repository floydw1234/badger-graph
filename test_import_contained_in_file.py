#!/usr/bin/env python3
"""Test if Import.containedInFile relationship exists."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

async def test_contained_in_file():
    client = DgraphClient()
    
    # Query an import with encryption module
    query = '''
    {
        imports(func: eq(Import.module, "packages/encryption/encryption.h"), first: 5) {
            uid
            Import.module
            Import.text
            Import.containedInFile {
                uid
                File.path
            }
        }
    }
    '''
    
    txn = client.client.txn(read_only=True)
    try:
        result = txn.query(query)
        data = json.loads(result.json)
    finally:
        txn.discard()
    
    imports = data.get("imports", [])
    print(f"Found {len(imports)} imports")
    
    for imp in imports:
        print(f"\nImport: {imp.get('Import.module')}")
        print(f"  Text: {imp.get('Import.text', '')[:60]}")
        file_ref = imp.get("Import.containedInFile")
        print(f"  containedInFile type: {type(file_ref)}")
        print(f"  containedInFile value: {file_ref}")
        
        if file_ref:
            if not isinstance(file_ref, list):
                file_ref = [file_ref]
            for f in file_ref:
                if isinstance(f, dict):
                    print(f"    File: {f.get('File.path')}")

if __name__ == "__main__":
    asyncio.run(test_contained_in_file())

