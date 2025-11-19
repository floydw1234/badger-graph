#!/usr/bin/env python3
"""Test script to verify MCP tool fixes."""

import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from badger.graph.dgraph import DgraphClient
from badger.mcp import tools

async def main():
    """Test all MCP tools with known examples."""
    client = DgraphClient("http://localhost:8080")
    
    print("=" * 80)
    print("TESTING MCP TOOLS AFTER FIXES")
    print("=" * 80)
    
    # Test 1: get_function_callers
    print("\n1. Testing get_function_callers('create_mcp_server'):")
    result1 = await tools.get_function_callers(client, "create_mcp_server", include_indirect=True)
    print(f"   Found {result1.get('count', 0)} callers")
    if result1.get("callers"):
        for caller in result1["callers"]:
            # The return structure uses "caller" key, not "name"
            caller_name = caller.get('caller') or caller.get('name', 'Unknown')
            print(f"   - {caller_name} in {caller.get('file')}:{caller.get('line')}")
    else:
        print("   ❌ No callers found (should find caller in run_mcp_server)")
    
    # Test 2: get_function_callers for insert_graph
    print("\n2. Testing get_function_callers('insert_graph'):")
    result2 = await tools.get_function_callers(client, "insert_graph", include_indirect=True)
    print(f"   Found {result2.get('count', 0)} callers")
    if result2.get("callers"):
        for caller in result2["callers"]:
            caller_name = caller.get('caller') or caller.get('name', 'Unknown')
            print(f"   - {caller_name} in {caller.get('file')}:{caller.get('line')}")
    else:
        print("   ❌ No callers found (should find callers in main.py and indexer.py)")
    
    # Test 3: get_include_dependencies
    print("\n3. Testing get_include_dependencies('cli/badger/mcp/server.py'):")
    result3 = await tools.get_include_dependencies(client, "cli/badger/mcp/server.py")
    print(f"   Found {result3.get('count', 0)} dependent files")
    if result3.get("dependencies"):
        for dep in result3["dependencies"][:5]:  # Show first 5
            print(f"   - {dep.get('file')} (depth: {dep.get('depth')}) - {dep.get('reason')}")
    else:
        print("   ❌ No dependencies found (should find files that import badger.mcp.server)")
    
    # Test 4: find_symbol_usages (should now show call sites)
    print("\n4. Testing find_symbol_usages('create_mcp_server', 'function'):")
    result4 = await tools.find_symbol_usages(client, "create_mcp_server", "function")
    print(f"   Found {result4.get('count', 0)} usages")
    call_sites = [u for u in result4.get("usages", []) if u.get("type") == "call"]
    definitions = [u for u in result4.get("usages", []) if u.get("type") == "definition"]
    print(f"   - {len(definitions)} definition(s)")
    print(f"   - {len(call_sites)} call site(s)")
    if call_sites:
        for call in call_sites[:3]:  # Show first 3
            print(f"     -> {call.get('file')}:{call.get('line')} - {call.get('context')}")
    else:
        print("   ⚠️  No call sites found (should show callers)")
    
    # Test 5: check_affected_files
    print("\n5. Testing check_affected_files(['cli/badger/mcp/server.py']):")
    result5 = await tools.check_affected_files(client, ["cli/badger/mcp/server.py"])
    print(f"   Found {result5.get('count', 0)} affected files")
    if result5.get("affected_files"):
        for file in result5["affected_files"][:5]:  # Show first 5
            print(f"   - {file}")
    else:
        print("   ❌ No affected files found (should find files that import or call functions from server.py)")
    
    print("\n" + "=" * 80)
    print("Testing complete")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())

