#!/usr/bin/env python3
"""Test expand(_all_) with Import nodes."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

async def test_expand():
    client = DgraphClient()
    
    # Get a few Import UIDs first
    query1 = '''
    {
        imports(func: has(Import.module), first: 3) {
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
    
    print(f"Got {len(uids)} UIDs: {uids}")
    
    if not uids:
        return
    
    # Try querying by UID with expand(_all_)
    uid_list = ", ".join(uids)
    query2 = f'''
    {{
        imports(func: uid({uid_list})) {{
            uid
            expand(_all_)
        }}
    }}
    '''
    
    print(f"\nQuery with expand(_all_):")
    print(query2)
    
    txn2 = client.client.txn(read_only=True)
    try:
        result2 = txn2.query(query2)
        data2 = json.loads(result2.json)
    except Exception as e:
        print(f"ERROR: {e}")
        txn2.discard()
        return
    finally:
        txn2.discard()
    
    imports2 = data2.get("imports", [])
    print(f"\nResult: {len(imports2)} imports")
    for imp in imports2:
        print(f"  UID: {imp.get('uid')}")
        print(f"  Keys: {list(imp.keys())}")
        for key, value in imp.items():
            if key != 'uid':
                print(f"    {key}: {value}")
    
    # Try with explicit predicates
    query3 = f'''
    {{
        imports(func: uid({uid_list})) {{
            uid
            Import.module
            Import.text
            Import.file
            Import.line
            dgraph.type
        }}
    }}
    '''
    
    print(f"\n\nQuery with explicit predicates:")
    print(query3)
    
    txn3 = client.client.txn(read_only=True)
    try:
        result3 = txn3.query(query3)
        data3 = json.loads(result3.json)
    except Exception as e:
        print(f"ERROR: {e}")
        txn3.discard()
        return
    finally:
        txn3.discard()
    
    imports3 = data3.get("imports", [])
    print(f"\nResult: {len(imports3)} imports")
    for imp in imports3:
        print(f"  UID: {imp.get('uid')}")
        print(f"  Keys: {list(imp.keys())}")
        for key, value in imp.items():
            if key != 'uid':
                print(f"    {key}: {value}")

if __name__ == "__main__":
    asyncio.run(test_expand())

