#!/usr/bin/env python3
"""Test current get_include_dependencies implementation with detailed logging."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient
from badger.mcp.tools import get_include_dependencies, extract_relative_path

async def test_with_logging():
    client = DgraphClient()
    
    test_file = "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/comm/gossipApi.c"
    
    print("=" * 80)
    print("TESTING CURRENT IMPLEMENTATION")
    print("=" * 80)
    
    print(f"\nTest file: {test_file}")
    
    # Determine target modules (same logic as in get_include_dependencies)
    h_path = test_file[:-2] + ".h"
    rel_path = extract_relative_path(h_path)
    target_modules = {
        rel_path,
        h_path.split("/")[-1],
        extract_relative_path(test_file)
    }
    
    print(f"\nTarget modules being searched:")
    for tm in sorted(target_modules):
        print(f"  - {tm}")
    
    # Count queries (we'll need to add logging to the actual function for this)
    print(f"\nCalling get_include_dependencies...")
    result = await get_include_dependencies(client, test_file)
    
    print(f"\nResults:")
    print(f"  Count: {result.get('count', 0)}")
    print(f"  Depth: {result.get('depth', 0)}")
    print(f"  Dependencies found: {len(result.get('dependencies', []))}")
    
    if result.get('error'):
        print(f"  ERROR: {result.get('error')}")
    
    print(f"\nDependencies by depth:")
    by_depth = {}
    for dep in result.get('dependencies', []):
        depth = dep.get('depth', 0)
        if depth not in by_depth:
            by_depth[depth] = []
        by_depth[depth].append(dep)
    
    for depth in sorted(by_depth.keys()):
        print(f"  Depth {depth}: {len(by_depth[depth])} file(s)")
        for dep in by_depth[depth]:
            print(f"    - {dep.get('file')} (includes {dep.get('module')})")
    
    # Check if we're missing transitive dependencies
    print(f"\nChecking for transitive dependencies...")
    
    # Files that directly include gossipApi.h
    direct_files = {dep.get('file') for dep in result.get('dependencies', [])}
    
    # For each direct file, check what includes it
    transitive = set()
    for direct_file in direct_files:
        print(f"\n  Checking what includes: {direct_file}")
        deps_result = await get_include_dependencies(client, direct_file)
        transitive_files = {dep.get('file') for dep in deps_result.get('dependencies', [])}
        transitive.update(transitive_files)
        print(f"    Found {len(transitive_files)} file(s):")
        for tf in sorted(transitive_files)[:5]:
            print(f"      - {tf}")
    
    print(f"\nTotal transitive dependencies: {len(transitive)}")
    print(f"All files that should be affected (direct + transitive): {len(direct_files | transitive)}")

if __name__ == "__main__":
    asyncio.run(test_with_logging())

