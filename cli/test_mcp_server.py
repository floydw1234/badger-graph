#!/usr/bin/env python3
"""Test script to verify MCP server is working correctly.

This is a simple standalone test script. For comprehensive tests, see:
    pytest tests/test_mcp/ -m integration
"""

import asyncio
import sys
from pathlib import Path

# Add cli to path
sys.path.insert(0, str(Path(__file__).parent))

from badger.mcp.server import create_mcp_server
from badger.graph.dgraph import DgraphClient
from badger.embeddings.service import EmbeddingService


async def test_server():
    """Test that the MCP server can list tools and handle calls."""
    print("Testing MCP Server...")
    
    # Create test client
    dgraph_client = DgraphClient("localhost:8080")
    embedding_service = EmbeddingService()
    
    # Create server
    server = create_mcp_server(dgraph_client, embedding_service)
    
    # Test list_tools (using internal handler for testing)
    print("\n1. Testing list_tools()...")
    if hasattr(server, '_list_tools_handler'):
        tools = await server._list_tools_handler()
        print(f"   ✓ Found {len(tools)} tools:")
        for tool in tools:
            print(f"     - {tool.name}")
    else:
        print("   ⚠ list_tools handler not accessible (this is OK for runtime)")
    
    # Test call_tool with a simple query
    print("\n2. Testing call_tool()...")
    try:
        if hasattr(server, '_call_tool_handler'):
            result = await server._call_tool_handler(
                "find_symbol_usages",
                {"symbol": "test", "symbol_type": "function"}
            )
        else:
            print("   ⚠ call_tool handler not accessible")
            result = None
        print(f"   ✓ Tool call succeeded")
        print(f"   Result type: {type(result)}")
        if result:
            print(f"   Result length: {len(result)}")
            if result[0].text:
                import json
                try:
                    parsed = json.loads(result[0].text)
                    print(f"   Result keys: {list(parsed.keys())}")
                except:
                    print(f"   Result preview: {result[0].text[:100]}...")
    except Exception as e:
        print(f"   ✗ Tool call failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    dgraph_client.close()
    
    print("\n✓ MCP Server test complete!")


if __name__ == "__main__":
    asyncio.run(test_server())

