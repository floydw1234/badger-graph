#!/usr/bin/env python3
"""Check what predicates exist on Import nodes."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

async def check_predicates():
    client = DgraphClient()
    
    # Get one Import node and see what predicates it has
    query = '''
    {
        imports(func: has(Import.module), first: 1) {
            uid
            expand(_all_)
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
    print(f"Found {len(imports)} Import nodes")
    
    for imp in imports:
        print(f"\nImport node UID: {imp.get('uid')}")
        print("All predicates:")
        for key, value in imp.items():
            if key != 'uid':
                print(f"  {key}: {value}")

if __name__ == "__main__":
    asyncio.run(check_predicates())

