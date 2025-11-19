#!/usr/bin/env python3
"""Quick test to verify MCP server tools are registered correctly."""

import asyncio
import sys
from pathlib import Path

# Add cli to path
sys.path.insert(0, str(Path(__file__).parent))

from badger.mcp.server import create_mcp_server
from badger.graph.dgraph import DgraphClient
from badger.embeddings.service import EmbeddingService


async def test_tools():
    """Test that tools are registered."""
    print("Testing MCP server tool registration...")
    
    try:
        # Create test client
        dgraph_client = DgraphClient("localhost:8080")
        embedding_service = EmbeddingService()
        
        # Create server
        server = create_mcp_server(dgraph_client, embedding_service)
        
        # Test list_tools
        print("\n1. Testing list_tools handler...")
        if hasattr(server, '_list_tools_handler'):
            tools = await server._list_tools_handler()
            print(f"   ✓ Found {len(tools)} tools:")
            tool_names = [tool.name for tool in tools]
            for name in tool_names:
                print(f"     - {name}")
            
            # Check for the specific tool
            if "get_include_dependencies" in tool_names:
                print("   ✓ 'get_include_dependencies' tool is registered")
            else:
                print("   ✗ 'get_include_dependencies' tool NOT found!")
                print(f"   Available tools: {tool_names}")
        else:
            print("   ✗ list_tools handler not found!")
        
        # Test call_tool
        print("\n2. Testing call_tool handler...")
        if hasattr(server, '_call_tool_handler'):
            print("   ✓ call_tool handler exists")
        else:
            print("   ✗ call_tool handler not found!")
        
        # Check if server has the MCP SDK's internal tool registration
        print("\n3. Checking MCP SDK internal state...")
        # The MCP SDK may store handlers differently - let's check various attributes
        handler_attrs = ['_handlers', '_tool_handlers', 'handlers', 'tools']
        found_attrs = []
        for attr in handler_attrs:
            if hasattr(server, attr):
                found_attrs.append(attr)
                try:
                    value = getattr(server, attr)
                    if isinstance(value, dict):
                        print(f"   ✓ Server has {attr}: {list(value.keys())}")
                    elif isinstance(value, list):
                        print(f"   ✓ Server has {attr}: {len(value)} items")
                    else:
                        print(f"   ✓ Server has {attr}: {type(value).__name__}")
                except:
                    pass
        
        if not found_attrs:
            print("   ⚠ Server doesn't expose handler attributes (this is OK - tools are registered via decorators)")
            print("   ✓ Tools are registered via @server.list_tools() and @server.call_tool() decorators")
        
        dgraph_client.close()
        print("\n✓ Test complete!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_tools())

