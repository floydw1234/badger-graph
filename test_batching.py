#!/usr/bin/env python3
"""Test batching UID queries."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

async def test_batching():
    client = DgraphClient()
    
    # Get some Import UIDs
    query1 = '''
    {
        imports(func: has(Import.module), first: 10) {
            uid
            Import.module
        }
    }
    '''
    
    txn1 = client.client.txn(read_only=True)
    try:
        result1 = txn1.query(query1)
        data1 = json.loads(result1.json)
    finally:
        txn1.discard()
    
    imports1 = data1.get("imports", [])
    uids = [imp.get("uid") for imp in imports1 if imp.get("uid")]
    
    print(f"Got {len(uids)} UIDs")
    
    # Test batching
    batch_size = 5
    all_imports = {}
    
    for i in range(0, len(uids), batch_size):
        batch_uids = uids[i:i + batch_size]
        uid_list = ", ".join(batch_uids)
        query2 = f"""
        {{
            imports(func: uid({uid_list})) {{
                uid
                expand(_all_)
            }}
        }}
        """
        
        print(f"\nBatch {i//batch_size + 1}: Querying {len(batch_uids)} UIDs")
        
        txn2 = client.client.txn(read_only=True)
        try:
            result2 = txn2.query(query2)
            data2 = json.loads(result2.json)
        finally:
            txn2.discard()
        
        imports2 = data2.get("imports", [])
        print(f"  Retrieved {len(imports2)} imports")
        
        for imp in imports2:
            if isinstance(imp, dict):
                uid = imp.get("uid")
                all_imports[uid] = imp
                print(f"    UID {uid}: keys = {list(imp.keys())}")
                if "Import.module" in imp:
                    print(f"      module = {imp['Import.module']}")
    
    print(f"\nTotal imports collected: {len(all_imports)}")
    print(f"Sample import with module: {[k for k, v in all_imports.items() if 'Import.module' in v][:3]}")

if __name__ == "__main__":
    asyncio.run(test_batching())

