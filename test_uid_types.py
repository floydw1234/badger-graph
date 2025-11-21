#!/usr/bin/env python3
"""Test UID types and query behavior."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

async def test_uid_types():
    client = DgraphClient()
    
    # Get files with imports
    files_query = """
    {
        files(func: type(File), first: 3) {
            uid
            File.path
            File.containsImport {
                uid
            }
        }
    }
    """
    
    txn = client.client.txn(read_only=True)
    try:
        result = txn.query(files_query)
        data = json.loads(result.json)
    finally:
        txn.discard()
    
    files = data.get("files", [])
    import_uids = set()
    
    for file_node in files:
        imports_list = file_node.get("File.containsImport", [])
        if not isinstance(imports_list, list):
            imports_list = [imports_list] if imports_list else []
        
        for imp in imports_list:
            if isinstance(imp, dict):
                imp_uid = imp.get("uid")
                if imp_uid:
                    import_uids.add(imp_uid)
                    print(f"UID type: {type(imp_uid)}, value: {imp_uid}, repr: {repr(imp_uid)}")
    
    print(f"\nCollected {len(import_uids)} UIDs")
    print(f"UID set type: {type(import_uids)}")
    
    # Try querying
    if import_uids:
        # Method 1: Join as strings
        uid_list1 = ", ".join(str(uid) for uid in import_uids)
        query1 = f"""
        {{
            imports(func: uid({uid_list1})) {{
                uid
                expand(_all_)
            }}
        }}
        """
        
        print(f"\nMethod 1: Join as strings")
        print(f"Query snippet: ...uid({uid_list1[:100]}...)")
        
        txn1 = client.client.txn(read_only=True)
        try:
            result1 = txn1.query(query1)
            data1 = json.loads(result1.json)
        except Exception as e:
            print(f"ERROR: {e}")
            txn1.discard()
        else:
            txn1.discard()
            imports1 = data1.get("imports", [])
            print(f"Result: {len(imports1)} imports")
            if imports1:
                first = imports1[0]
                print(f"  First import keys: {list(first.keys())}")
        
        # Method 2: Use UIDs directly (if they're already strings)
        uid_list2 = ", ".join(import_uids)
        query2 = f"""
        {{
            imports(func: uid({uid_list2})) {{
                uid
                expand(_all_)
            }}
        }}
        """
        
        print(f"\nMethod 2: Use UIDs directly")
        print(f"Query snippet: ...uid({uid_list2[:100]}...)")
        
        txn2 = client.client.txn(read_only=True)
        try:
            result2 = txn2.query(query2)
            data2 = json.loads(result2.json)
        except Exception as e:
            print(f"ERROR: {e}")
            txn2.discard()
        else:
            txn2.discard()
            imports2 = data2.get("imports", [])
            print(f"Result: {len(imports2)} imports")
            if imports2:
                first = imports2[0]
                print(f"  First import keys: {list(first.keys())}")

if __name__ == "__main__":
    asyncio.run(test_uid_types())

