#!/usr/bin/env python3
"""Test get_include_dependencies directly"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient
from badger.mcp.tools import get_include_dependencies

async def test():
    client = DgraphClient()
    
    # Test with encryption.h
    file_path = "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/encryption/encryption.h"
    
    print(f"Testing get_include_dependencies for: {file_path}")
    print("=" * 80)
    
    result = await get_include_dependencies(client, file_path)
    
    print(f"Result:")
    print(f"  - Count: {result.get('count', 0)}")
    print(f"  - Dependencies: {len(result.get('dependencies', []))}")
    
    for dep in result.get("dependencies", [])[:10]:
        print(f"    - {dep.get('file')} (includes {dep.get('module')})")
    
    # Also test with encryption.c
    print("\n" + "=" * 80)
    file_path2 = "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/encryption/encryption.c"
    print(f"Testing get_include_dependencies for: {file_path2}")
    print("=" * 80)
    
    result2 = await get_include_dependencies(client, file_path2)
    
    print(f"Result:")
    print(f"  - Count: {result2.get('count', 0)}")
    print(f"  - Dependencies: {len(result2.get('dependencies', []))}")
    
    for dep in result2.get("dependencies", [])[:10]:
        print(f"    - {dep.get('file')} (includes {dep.get('module')})")

if __name__ == "__main__":
    asyncio.run(test())

