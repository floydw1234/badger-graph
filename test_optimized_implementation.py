#!/usr/bin/env python3
"""Test optimized get_include_dependencies with multiple files."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient
from badger.mcp.tools import get_include_dependencies, check_affected_files

async def test_multiple():
    client = DgraphClient()
    
    test_files = [
        '/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/encryption/encryption.h',
        '/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/comm/gossip/gossip.h',
        '/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/main.c'
    ]
    
    for test_file in test_files:
        print(f'\n{"="*80}')
        print(f'Testing: {test_file.split("/")[-1]}')
        print(f'{"="*80}')
        result = await get_include_dependencies(client, test_file)
        print(f'  Count: {result.get("count", 0)}')
        print(f'  Depth: {result.get("depth", 0)}')
        if result.get('error'):
            print(f'  ERROR: {result.get("error")}')
        else:
            deps = result.get('dependencies', [])
            print(f'  Dependencies: {len(deps)}')
            for dep in deps[:5]:
                print(f'    - {dep.get("file").split("/")[-1]} (depth {dep.get("depth", 0)})')
            if len(deps) > 5:
                print(f'    ... and {len(deps) - 5} more')
    
    # Test check_affected_files
    print(f'\n{"="*80}')
    print('Testing check_affected_files for gossipApi.c')
    print(f'{"="*80}')
    result2 = await check_affected_files(client, ['/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/comm/gossipApi.c'])
    print(f'  Count: {result2.get("count", 0)}')
    by_type = result2.get('by_type', {})
    for type_name, items in by_type.items():
        print(f'  {type_name}: {len(items)}')
        for item in items[:3]:
            print(f'    - {item.get("file").split("/")[-1]}')

if __name__ == "__main__":
    asyncio.run(test_multiple())

