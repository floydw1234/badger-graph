#!/usr/bin/env python3
"""Debug DQL implementation step by step."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient
from badger.mcp.tools_dql import extract_relative_path

async def debug_step_by_step():
    client = DgraphClient()
    
    test_file = "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/encryption/encryption.h"
    
    # Determine target modules
    target_modules = set()
    rel_path = extract_relative_path(test_file)
    target_modules.add(rel_path)
    target_modules.add(test_file.split("/")[-1])
    
    print(f"Target modules: {target_modules}")
    
    # Step 1: Get all files with Import UIDs
    files_query = """
    {
        files(func: type(File)) {
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
    print(f"\nStep 1: Found {len(files)} files")
    
    # Collect Import UIDs
    import_uids = set()
    file_to_import_uids = {}
    
    for file_node in files:
        file_path = file_node.get("File.path", "")
        imports_list = file_node.get("File.containsImport", [])
        if not isinstance(imports_list, list):
            imports_list = [imports_list] if imports_list else []
        
        file_import_uids = []
        for imp in imports_list:
            if isinstance(imp, dict):
                imp_uid = imp.get("uid")
                if imp_uid:
                    import_uids.add(imp_uid)
                    file_import_uids.append(imp_uid)
        
        if file_import_uids:
            file_to_import_uids[file_path] = file_import_uids
    
    print(f"Step 2: Found {len(import_uids)} unique Import UIDs")
    print(f"Step 2: {len(file_to_import_uids)} files have imports")
    
    # Step 3: Query Import nodes
    if import_uids:
        # UIDs should be used directly, not as strings
        uid_list = ", ".join(import_uids)
        imports_query = f"""
        {{
            imports(func: uid({uid_list})) {{
                uid
                expand(_all_)
            }}
        }}
        """
        
        print(f"\nGenerated query:")
        print(imports_query[:200] + "..." if len(imports_query) > 200 else imports_query)
        
        txn2 = client.client.txn(read_only=True)
        try:
            result2 = txn2.query(imports_query)
            data2 = json.loads(result2.json)
        finally:
            txn2.discard()
        
        imports = data2.get("imports", [])
        print(f"Step 3: Retrieved {len(imports)} Import nodes")
        
        # Debug: check first import
        if imports:
            first_imp = imports[0]
            print(f"\nFirst Import node structure:")
            print(f"  Type: {type(first_imp)}")
            if isinstance(first_imp, dict):
                print(f"  Keys: {list(first_imp.keys())}")
                for key, value in first_imp.items():
                    print(f"    {key}: {value}")
        
        uid_to_import = {imp.get("uid"): imp for imp in imports if isinstance(imp, dict)}
        
        # Step 4: Check matches
        print(f"\nStep 4: Checking for matches...")
        matches_found = []
        
        for file_path, import_uids_list in file_to_import_uids.items():
            for imp_uid in import_uids_list:
                imp = uid_to_import.get(imp_uid)
                if not imp:
                    continue
                
                module = imp.get("Import.module", "")
                if not module:
                    # Try alternative key names
                    module = imp.get("module", "")
                if not module:
                    continue
                
                # Check if matches
                if module in target_modules:
                    matches_found.append({
                        "file": file_path,
                        "module": module,
                        "target": "exact match"
                    })
                elif module.split("/")[-1] in [t.split("/")[-1] for t in target_modules]:
                    matches_found.append({
                        "file": file_path,
                        "module": module,
                        "target": "filename match"
                    })
        
        print(f"Found {len(matches_found)} matches:")
        for match in matches_found[:10]:
            print(f"  - {match['file']}: includes {match['module']} ({match['target']})")
        
        # Show some sample modules
        print(f"\nSample Import modules (first 10):")
        for i, (uid, imp) in enumerate(list(uid_to_import.items())[:10]):
            print(f"  {i+1}. {imp.get('Import.module', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(debug_step_by_step())

