#!/usr/bin/env python3
"""Debug script to test check_affected_files for encryption.h"""

import asyncio
import sys
from pathlib import Path

# Add the cli directory to path
sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient
from badger.mcp.tools import check_affected_files

async def test_check_affected():
    print("=" * 80)
    print("Testing check_affected_files for encryption.h")
    print("=" * 80)
    
    client = DgraphClient()
    
    # First, let's see what files exist in the graph
    print("\n1. Checking what files exist in the graph (searching for 'encryption'):")
    query = """
    query {
        files: queryFile(first: 100) {
            path
        }
    }
    """
    result = client.execute_graphql_query(query, {})
    encryption_files = [f.get("path") for f in result.get("files", []) if "encryption" in f.get("path", "").lower()]
    print(f"Found {len(encryption_files)} files with 'encryption' in path:")
    for f in encryption_files:
        print(f"  - {f}")
    
    # Try to find the exact path
    print("\n2. Searching for encryption.h in graph:")
    # Use the actual path from the graph
    actual_path = None
    all_files_result = client.execute_graphql_query(query, {})
    for f in all_files_result.get("files", []):
        path = f.get("path", "")
        if "encryption" in path.lower() and path.endswith("encryption.h") and "packages" in path:
            actual_path = path
            print(f"  ✓ Found: {actual_path}")
            
            # Get details about this file
            detail_query = """
            query($filePath: String!) {
                file: queryFile(filter: {path: {eq: $filePath}}, first: 1) {
                    path
                    containsImport {
                        module
                        text
                    }
                    containsFunction {
                        name
                    }
                }
            }
            """
            detail_result = client.execute_graphql_query(detail_query, {"filePath": actual_path})
            if detail_result.get("file"):
                file_node = detail_result["file"][0] if isinstance(detail_result["file"], list) else detail_result["file"]
                imports = file_node.get("containsImport", [])
                functions = file_node.get("containsFunction", [])
                print(f"    - Imports: {len(imports) if isinstance(imports, list) else (1 if imports else 0)}")
                print(f"    - Functions: {len(functions) if isinstance(functions, list) else (1 if functions else 0)}")
                if functions:
                    func_list = functions if isinstance(functions, list) else [functions]
                    print(f"    - Function names: {[f.get('name') for f in func_list]}")
            break
    
    if not actual_path:
        print("\n❌ Could not find encryption.h in graph!")
        print("Available files with 'encryption':")
        for f in encryption_files[:10]:
            print(f"  - {f}")
        return
    
    print(f"\n4. Testing check_affected_files with: {actual_path}")
    result = await check_affected_files(client, [actual_path])
    
    print(f"\nResult:")
    print(f"  - Total affected files: {result.get('count', 0)}")
    print(f"  - Affected files list: {result.get('affected_files', [])}")
    
    print(f"\n  By type:")
    by_type = result.get("by_type", {})
    for type_name, items in by_type.items():
        print(f"    - {type_name}: {len(items)} files")
        for item in items[:5]:  # Show first 5
            print(f"        * {item.get('file')} - {item.get('reason', '')}")
        if len(items) > 5:
            print(f"        ... and {len(items) - 5} more")
    
    print("\n" + "=" * 80)
    print("5. Directly checking what files include encryption.h:")
    query2 = """
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
    result2 = client.execute_graphql_query(query2, {})
    
    # Find files that include encryption.h
    # The module might be stored as "packages/encryption/encryption.h" or similar
    includers = []
    for file in result2.get("files", []):
        imports = file.get("containsImport", [])
        if not isinstance(imports, list):
            imports = [imports] if imports else []
        
        for imp in imports:
            module = imp.get("module", "")
            if "encryption.h" in module or module.endswith("encryption/encryption.h"):
                includers.append({
                    "file": file.get("path"),
                    "module": module,
                    "text": imp.get("text", "")
                })
    
    print(f"Found {len(includers)} files that include encryption.h:")
    for item in includers:
        print(f"  - {item['file']}")
        print(f"    (imports: {item['module']})")
    
    print("\n" + "=" * 80)
    print("6. Checking for encrypt_envelope_payload function:")
    query3 = """
    query($funcName: String!) {
        func: queryFunction(filter: {name: {eq: $funcName}}, first: 10) {
            name
            file
            calledByFunction {
                name
                file
            }
        }
    }
    """
    result3 = client.execute_graphql_query(query3, {"funcName": "encrypt_envelope_payload"})
    if result3.get("func"):
        funcs = result3["func"] if isinstance(result3["func"], list) else [result3["func"]]
        for func in funcs:
            print(f"  Function: {func.get('name')} in {func.get('file')}")
            callers = func.get("calledByFunction", [])
            if callers:
                callers_list = callers if isinstance(callers, list) else [callers]
                print(f"    Called by {len(callers_list)} functions:")
                for caller in callers_list:
                    print(f"      - {caller.get('name')} in {caller.get('file')}")
    else:
        print("  Function not found in graph")

if __name__ == "__main__":
    asyncio.run(test_check_affected())

