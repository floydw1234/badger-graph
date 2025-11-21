#!/usr/bin/env python3
"""Debug DQL implementation to see why it's not finding matches."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient
from badger.mcp.tools_dql import extract_relative_path

async def debug_dql_matching():
    client = DgraphClient()
    
    test_file = "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/encryption/encryption.h"
    
    print("=" * 80)
    print("DEBUGGING DQL MATCHING")
    print("=" * 80)
    
    # Determine target modules
    target_modules = set()
    rel_path = extract_relative_path(test_file)
    target_modules.add(rel_path)
    target_modules.add(test_file.split("/")[-1])
    
    print(f"\nTest file: {test_file}")
    print(f"Target modules to search for: {target_modules}")
    
    # Query all files and their imports
    query = """
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
    """
    
    txn = client.client.txn(read_only=True)
    try:
        result = txn.query(query)
        data = json.loads(result.json)
    finally:
        txn.discard()
    
    files = data.get("files", [])
    print(f"\nTotal files in graph: {len(files)}")
    
    # Check how many files have imports
    files_with_imports = 0
    total_imports = 0
    for file_node in files:
        imports_list = file_node.get("File.containsImport", [])
        if not isinstance(imports_list, list):
            imports_list = [imports_list] if imports_list else []
        if imports_list:
            files_with_imports += 1
            total_imports += len(imports_list)
    
    print(f"Files with imports: {files_with_imports}")
    print(f"Total imports: {total_imports}")
    
    matches_found = []
    
    # Debug: print structure of first file with imports
    print("\nDebug: Structure of first file with imports:")
    for file_node in files[:5]:
        imports_list = file_node.get("File.containsImport", [])
        if imports_list:
            print(f"  File: {file_node.get('File.path', 'N/A')}")
            print(f"  containsImport type: {type(imports_list)}")
            print(f"  containsImport value: {imports_list[:2] if isinstance(imports_list, list) else imports_list}")
            break
    
    for file_node in files:
        file_path_check = file_node.get("File.path", "")
        imports_list = file_node.get("File.containsImport", [])
        if not isinstance(imports_list, list):
            imports_list = [imports_list] if imports_list else []
        
        for imp in imports_list:
            if not isinstance(imp, dict):
                continue
            
            module = imp.get("Import.module")
            if not module:
                continue
            
            # Check if module matches any target
            matches = False
            matched_target = None
            
            # Try exact match first
            if module in target_modules:
                matches = True
                matched_target = module
            else:
                # Try matching by filename or path suffix
                for target in target_modules:
                    # Exact match
                    if module == target:
                        matches = True
                        matched_target = target
                        break
                    # Check if they have the same filename
                    module_filename = module.split("/")[-1]
                    target_filename = target.split("/")[-1]
                    if module_filename == target_filename:
                        # If target is just a filename, match any path with that filename
                        if "/" not in target:
                            matches = True
                            matched_target = target
                            break
                        # If both have paths, check if they end the same way
                        if module.endswith("/" + target) or target.endswith("/" + module):
                            matches = True
                            matched_target = target
                            break
                        # Also try matching the last N path components
                        module_parts = module.split("/")
                        target_parts = target.split("/")
                        if len(module_parts) >= len(target_parts):
                            if module_parts[-len(target_parts):] == target_parts:
                                matches = True
                                matched_target = target
                                break
            
            if matches:
                matches_found.append({
                    "file": file_path_check,
                    "module": module,
                    "matched_target": matched_target,
                    "text": imp.get("Import.text", "")
                })
                print(f"\n✓ MATCH FOUND:")
                print(f"  File: {file_path_check}")
                print(f"  Import module: {module}")
                print(f"  Matched target: {matched_target}")
                print(f"  Import text: {imp.get('Import.text', '')[:60]}")
            elif "encryption" in module.lower():
                # Show near-misses for debugging
                print(f"\n  Near-miss (encryption-related but didn't match):")
                print(f"    File: {file_path_check}")
                print(f"    Module: {module}")
                print(f"    Target modules: {target_modules}")
    
    print(f"\n" + "=" * 80)
    print(f"SUMMARY: Found {len(matches_found)} matches")
    print("=" * 80)
    
    if len(matches_found) == 0:
        print("\nNo matches found. Checking what modules actually exist...")
        # Query all unique import modules
        all_modules_query = """
        {
            imports(func: has(Import.module)) {
                Import.module
            }
        }
        """
        
        txn2 = client.client.txn(read_only=True)
        try:
            result2 = txn2.query(all_modules_query)
            data2 = json.loads(result2.json)
        finally:
            txn2.discard()
        
        imports2 = data2.get("imports", [])
        unique_modules = set()
        for imp in imports2:
            module = imp.get("Import.module")
            if module and "encryption" in module.lower():
                unique_modules.add(module)
        
        print(f"\nUnique encryption-related modules in graph:")
        for mod in sorted(unique_modules):
            print(f"  - {mod}")

if __name__ == "__main__":
    asyncio.run(debug_dql_matching())

