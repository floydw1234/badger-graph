#!/usr/bin/env python3
"""Diagnostic script to understand what's in the database vs what get_include_dependencies finds."""

import asyncio
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient
from badger.mcp.tools import get_include_dependencies, extract_relative_path

async def diagnose():
    client = DgraphClient()
    
    # Test file
    test_file = "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/comm/gossipApi.c"
    
    print("=" * 80)
    print("DIAGNOSTIC: get_include_dependencies for gossipApi.c")
    print("=" * 80)
    
    # Step 1: Determine what we're searching for
    print("\n1. TARGET MODULES BEING SEARCHED:")
    print("-" * 80)
    
    h_path = test_file[:-2] + ".h"
    rel_path = extract_relative_path(h_path)
    target_modules = {
        rel_path,
        h_path.split("/")[-1],
        extract_relative_path(test_file)
    }
    
    print(f"Test file: {test_file}")
    print(f"Header file: {h_path}")
    print(f"Target modules to search:")
    for tm in sorted(target_modules):
        print(f"  - {tm}")
    
    # Step 2: Query Dgraph directly for all imports matching these modules
    print("\n2. WHAT'S ACTUALLY IN THE DATABASE:")
    print("-" * 80)
    
    all_imports_by_module = defaultdict(list)
    all_imports_by_filename = defaultdict(list)
    
    # Query all imports
    all_imports_query = """
    {
        imports(func: has(Import.module)) {
            uid
            Import.module
            Import.text
            Import.file
        }
    }
    """
    
    txn = client.client.txn(read_only=True)
    try:
        result = txn.query(all_imports_query)
        data = json.loads(result.json)
    finally:
        txn.discard()
    
    imports = data.get("imports", [])
    print(f"Total imports in database: {len(imports)}")
    
    # Categorize imports
    for imp in imports:
        if not isinstance(imp, dict):
            continue
        module = imp.get("Import.module", "")
        if not module:
            continue
        
        file_path = imp.get("Import.file", "")
        all_imports_by_module[module].append(file_path)
        
        # Also index by filename
        filename = module.split("/")[-1]
        all_imports_by_filename[filename].append((module, file_path))
    
    # Find matches for our target modules
    print(f"\nFiles that match target modules:")
    matching_files = set()
    
    for target_module in target_modules:
        print(f"\n  Searching for module: '{target_module}'")
        
        # Exact match
        if target_module in all_imports_by_module:
            files = all_imports_by_module[target_module]
            print(f"    Exact match: Found {len(files)} file(s)")
            for f in files:
                print(f"      - {f}")
                matching_files.add(f)
        
        # Filename match
        target_filename = target_module.split("/")[-1]
        if target_filename in all_imports_by_filename:
            matches = all_imports_by_filename[target_filename]
            print(f"    Filename match ('{target_filename}'): Found {len(matches)} import(s)")
            for module, file_path in matches:
                if module not in target_modules:  # Only show if not already matched
                    print(f"      - {file_path} (includes '{module}')")
                    matching_files.add(file_path)
    
    print(f"\n  Total unique files found: {len(matching_files)}")
    
    # Step 3: Test current implementation
    print("\n3. WHAT get_include_dependencies FINDS:")
    print("-" * 80)
    
    result = await get_include_dependencies(client, test_file)
    found_files = {dep.get("file") for dep in result.get("dependencies", [])}
    
    print(f"Found {len(found_files)} file(s):")
    for f in sorted(found_files):
        print(f"  - {f}")
    
    # Step 4: Compare
    print("\n4. COMPARISON:")
    print("-" * 80)
    
    missing = matching_files - found_files
    extra = found_files - matching_files
    
    if not missing and not extra:
        print("✓ Perfect match! All files found.")
    else:
        if missing:
            print(f"✗ Missing {len(missing)} file(s) that exist in database:")
            for f in sorted(missing):
                print(f"  - {f}")
        
        if extra:
            print(f"⚠ Found {len(extra)} file(s) not in direct matches (might be transitive):")
            for f in sorted(extra):
                print(f"  - {f}")
    
    # Step 5: Show transitive dependencies
    print("\n5. TRANSITIVE DEPENDENCIES ANALYSIS:")
    print("-" * 80)
    
    # For each file that includes gossipApi.h, check what includes it
    transitive = set()
    for file_path in matching_files:
        deps_result = await get_include_dependencies(client, file_path)
        transitive_files = {dep.get("file") for dep in deps_result.get("dependencies", [])}
        transitive.update(transitive_files)
    
    print(f"Files that include files that include gossipApi.h: {len(transitive)}")
    for f in sorted(transitive)[:10]:
        print(f"  - {f}")
    
    # Step 6: Show all unique module paths for gossipApi
    print("\n6. ALL MODULE PATH VARIATIONS FOR 'gossipApi':")
    print("-" * 80)
    
    gossip_modules = {m for m in all_imports_by_module.keys() if "gossipApi" in m.lower() or "gossip" in m.lower()}
    print(f"Found {len(gossip_modules)} unique module path(s) containing 'gossip':")
    for m in sorted(gossip_modules):
        files = all_imports_by_module[m]
        print(f"  - '{m}' ({len(files)} file(s))")
        for f in files[:5]:
            print(f"      {f}")
    
    # Step 7: Check what files include the files that include gossipApi.h
    print("\n7. TRANSITIVE DEPENDENCIES (files that include files that include gossipApi.h):")
    print("-" * 80)
    
    direct_includers = matching_files
    transitive_includers = set()
    
    for direct_file in direct_includers:
        print(f"\n  Checking what includes: {direct_file}")
        deps_result = await get_include_dependencies(client, direct_file)
        transitive = {dep.get("file") for dep in deps_result.get("dependencies", [])}
        transitive_includers.update(transitive)
        print(f"    Found {len(transitive)} file(s) that include this file:")
        for t in sorted(transitive)[:5]:
            print(f"      - {t}")
    
    print(f"\n  Total transitive dependencies: {len(transitive_includers)}")
    
    # Step 8: Check if there are files that include gossipApi.c directly
    print("\n8. FILES THAT INCLUDE gossipApi.c DIRECTLY:")
    print("-" * 80)
    
    gossip_c_modules = {m for m in all_imports_by_module.keys() if m.endswith("gossipApi.c")}
    print(f"Found {len(gossip_c_modules)} module path(s) ending with 'gossipApi.c':")
    for m in sorted(gossip_c_modules):
        files = all_imports_by_module[m]
        print(f"  - '{m}' ({len(files)} file(s))")
        for f in files:
            print(f"      {f}")

if __name__ == "__main__":
    asyncio.run(diagnose())

