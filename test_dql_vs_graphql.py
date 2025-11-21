#!/usr/bin/env python3
"""Test DQL versions vs GraphQL versions of MCP tools."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient
from badger.mcp.tools import get_include_dependencies, check_affected_files
from badger.mcp.tools_dql import get_include_dependencies_dql, check_affected_files_dql

async def test_comparison():
    client = DgraphClient()
    
    # Test file
    test_file = "/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/encryption/encryption.h"
    
    print("=" * 80)
    print("COMPARING GraphQL vs DQL IMPLEMENTATIONS")
    print("=" * 80)
    
    print(f"\nTest file: {test_file}\n")
    
    # Test 1: get_include_dependencies
    print("1. Testing get_include_dependencies:")
    print("-" * 80)
    
    print("\n  GraphQL version:")
    result_graphql = await get_include_dependencies(client, test_file)
    print(f"    Count: {result_graphql.get('count', 0)}")
    print(f"    Dependencies: {len(result_graphql.get('dependencies', []))}")
    if result_graphql.get('error'):
        print(f"    ERROR: {result_graphql.get('error')}")
    for dep in result_graphql.get("dependencies", [])[:5]:
        print(f"      - {dep.get('file')}")
    
    print("\n  DQL version:")
    result_dql = await get_include_dependencies_dql(client, test_file)
    print(f"    Count: {result_dql.get('count', 0)}")
    print(f"    Dependencies: {len(result_dql.get('dependencies', []))}")
    if result_dql.get('error'):
        print(f"    ERROR: {result_dql.get('error')}")
    for dep in result_dql.get("dependencies", [])[:5]:
        print(f"      - {dep.get('file')}")
    
    print("\n  Comparison:")
    graphql_count = result_graphql.get('count', 0)
    dql_count = result_dql.get('count', 0)
    if graphql_count == dql_count:
        print(f"    ✓ Both found {graphql_count} dependencies")
    else:
        print(f"    ✗ MISMATCH: GraphQL={graphql_count}, DQL={dql_count}")
        print(f"    DQL version found {dql_count - graphql_count} more dependencies")
    
    # Test 2: check_affected_files
    print("\n" + "=" * 80)
    print("2. Testing check_affected_files:")
    print("-" * 80)
    
    print("\n  GraphQL version:")
    result_graphql2 = await check_affected_files(client, [test_file])
    print(f"    Count: {result_graphql2.get('count', 0)}")
    print(f"    Affected files: {len(result_graphql2.get('affected_files', []))}")
    if result_graphql2.get('error'):
        print(f"    ERROR: {result_graphql2.get('error')}")
    by_type = result_graphql2.get('by_type', {})
    print(f"    By type:")
    for type_name, items in by_type.items():
        print(f"      - {type_name}: {len(items)}")
    
    print("\n  DQL version:")
    result_dql2 = await check_affected_files_dql(client, [test_file])
    print(f"    Count: {result_dql2.get('count', 0)}")
    print(f"    Affected files: {len(result_dql2.get('affected_files', []))}")
    if result_dql2.get('error'):
        print(f"    ERROR: {result_dql2.get('error')}")
    by_type2 = result_dql2.get('by_type', {})
    print(f"    By type:")
    for type_name, items in by_type2.items():
        print(f"      - {type_name}: {len(items)}")
    
    print("\n  Comparison:")
    graphql_count2 = result_graphql2.get('count', 0)
    dql_count2 = result_dql2.get('count', 0)
    if graphql_count2 == dql_count2:
        print(f"    ✓ Both found {graphql_count2} affected files")
    else:
        print(f"    ✗ MISMATCH: GraphQL={graphql_count2}, DQL={dql_count2}")
        print(f"    DQL version found {dql_count2 - graphql_count2} more affected files")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    if dql_count > graphql_count or dql_count2 > graphql_count2:
        print("✓ DQL versions work better - found more results")
        print("  This confirms the issue is with GraphQL, not the data")
    elif graphql_count == 0 and dql_count > 0:
        print("✓ DQL versions work - GraphQL is failing")
    elif graphql_count == dql_count == 0:
        print("? Both return 0 - need to investigate why")
    else:
        print("Both versions return similar results")

if __name__ == "__main__":
    asyncio.run(test_comparison())

