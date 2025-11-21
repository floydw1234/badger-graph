#!/usr/bin/env python3
"""Debug DQL queries to see what data exists."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

async def debug_dql():
    client = DgraphClient()
    
    test_file = "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/encryption/encryption.h"
    
    print("=" * 80)
    print("DEBUGGING DQL QUERIES")
    print("=" * 80)
    
    # First, check if the file exists
    print(f"\n1. Checking if file exists: {test_file}")
    file_query = f'''
    {{
        files(func: eq(File.path, "{test_file}")) {{
            uid
            File.path
        }}
    }}
    '''
    
    txn = client.client.txn(read_only=True)
    try:
        result = txn.query(file_query)
        data = json.loads(result.json)
        files = data.get("files", [])
        print(f"   Found {len(files)} file(s)")
        for f in files:
            print(f"   - {f.get('File.path')} (uid: {f.get('uid')})")
    finally:
        txn.discard()
    
    # Check all files with "encryption" in path
    print(f"\n2. Checking all files with 'encryption' in path:")
    file_query2 = '''
    {
        files(func: has(File.path)) @filter(regexp(File.path, /encryption/)) {
            uid
            File.path
        }
    }
    '''
    
    txn2 = client.client.txn(read_only=True)
    try:
        result2 = txn2.query(file_query2)
        data2 = json.loads(result2.json)
        files2 = data2.get("files", [])
        print(f"   Found {len(files2)} file(s)")
        for f in files2[:10]:
            print(f"   - {f.get('File.path')}")
    finally:
        txn2.discard()
    
    # Check imports with "encryption" in module
    print(f"\n3. Checking imports with 'encryption' in module:")
    import_query = '''
    {
        imports(func: has(Import.module)) @filter(regexp(Import.module, /encryption/)) {
            uid
            Import.module
            Import.text
        }
    }
    '''
    
    txn3 = client.client.txn(read_only=True)
    try:
        result3 = txn3.query(import_query)
        data3 = json.loads(result3.json)
        imports = data3.get("imports", [])
        print(f"   Found {len(imports)} import(s)")
        for imp in imports[:10]:
            print(f"   - module: {imp.get('Import.module')}")
            print(f"     text: {imp.get('Import.text', '')[:60]}")
    finally:
        txn3.discard()
    
    # Check files that contain imports
    print(f"\n4. Checking files and their imports (sample):")
    files_imports_query = '''
    {
        files(func: type(File), first: 20) {
            uid
            File.path
            containsImport {
                uid
                Import.module
                Import.text
            }
        }
    }
    '''
    
    txn4 = client.client.txn(read_only=True)
    try:
        result4 = txn4.query(files_imports_query)
        data4 = json.loads(result4.json)
        files4 = data4.get("files", [])
        print(f"   Found {len(files4)} file(s)")
        for f in files4:
            path = f.get("File.path", "")
            if "encryption" in path.lower():
                imports_list = f.get("containsImport", [])
                if not isinstance(imports_list, list):
                    imports_list = [imports_list] if imports_list else []
                print(f"   - {path}")
                print(f"     Has {len(imports_list)} import(s)")
                for imp in imports_list[:3]:
                    if isinstance(imp, dict):
                        print(f"       * {imp.get('Import.module', 'N/A')}")
    finally:
        txn4.discard()
    
    # Try to find files that include encryption.h
    print(f"\n5. Looking for files that include encryption.h:")
    # Try different module formats
    target_modules = [
        "packages/encryption/encryption.h",
        "encryption.h",
        "encryption/encryption.h"
    ]
    
    for target in target_modules:
        print(f"\n   Searching for module: {target}")
        # Method 1: Query imports and use reverse edge
        search_query = f'''
        {{
            imports(func: eq(Import.module, "{target}")) {{
                uid
                Import.module
                Import.text
                ~File.containsImport {{
                    uid
                    File.path
                }}
            }}
        }}
        '''
        
        txn5 = client.client.txn(read_only=True)
        try:
            result5 = txn5.query(search_query)
            data5 = json.loads(result5.json)
            imports5 = data5.get("imports", [])
            print(f"      Found {len(imports5)} import(s) with this module")
            for imp in imports5:
                print(f"      - Import: {imp.get('Import.module')}")
                files_with_import = imp.get("~File.containsImport", [])
                if not isinstance(files_with_import, list):
                    files_with_import = [files_with_import] if files_with_import else []
                for f in files_with_import:
                    if isinstance(f, dict):
                        print(f"        In file: {f.get('File.path')}")
        finally:
            txn5.discard()
    
    # Method 2: Query all files and filter by imports
    print(f"\n6. Querying all files and checking their imports:")
    all_files_query = '''
    {
        files(func: type(File)) {
            uid
            File.path
            File.containsImport {
                uid
                Import.module
                Import.text
            }
        }
    }
    '''
    
    txn6 = client.client.txn(read_only=True)
    try:
        result6 = txn6.query(all_files_query)
        data6 = json.loads(result6.json)
        files6 = data6.get("files", [])
        print(f"   Checking {len(files6)} files...")
        matching_files = []
        for f in files6:
            imports_list = f.get("File.containsImport", [])
            if not isinstance(imports_list, list):
                imports_list = [imports_list] if imports_list else []
            for imp in imports_list:
                if isinstance(imp, dict):
                    module = imp.get("Import.module", "")
                    if "encryption.h" in module:
                        matching_files.append({
                            "file": f.get("File.path"),
                            "module": module
                        })
                        break
        print(f"   Found {len(matching_files)} files that include encryption.h:")
        for mf in matching_files:
            print(f"      - {mf['file']} (includes {mf['module']})")
    finally:
        txn6.discard()

if __name__ == "__main__":
    asyncio.run(debug_dql())

