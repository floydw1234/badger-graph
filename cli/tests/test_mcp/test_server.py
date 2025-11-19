"""Integration tests for MCP server."""

import pytest
import asyncio
from badger.mcp.server import create_mcp_server
from badger.graph.dgraph import DgraphClient
from badger.embeddings.service import EmbeddingService


@pytest.mark.integration
class TestMCPServer:
    """Test MCP server initialization and tool registration."""
    
    def test_server_creation(self, dgraph_client, embedding_service):
        """Test that MCP server can be created."""
        server = create_mcp_server(dgraph_client, embedding_service)
        assert server is not None
        assert hasattr(server, '_dgraph_client')
        assert hasattr(server, '_embedding_service')
    
    @pytest.mark.asyncio
    async def test_list_tools(self, mcp_server):
        """Test that server can list all tools."""
        # Get tools via the server's internal handler (for testing)
        if hasattr(mcp_server, '_list_tools_handler'):
            tools_list = await mcp_server._list_tools_handler()
            
            assert isinstance(tools_list, list)
            assert len(tools_list) == 6  # Should have 6 tools
            
            tool_names = [tool.name for tool in tools_list]
            expected_tools = [
                "find_symbol_usages",
                "get_include_dependencies",
                "find_struct_field_access",
                "get_function_callers",
                "semantic_code_search",
                "check_affected_files"
            ]
            
            for expected_tool in expected_tools:
                assert expected_tool in tool_names, f"Tool {expected_tool} not found"
        else:
            pytest.skip("list_tools handler not accessible for testing")
    
    @pytest.mark.asyncio
    async def test_call_tool_find_symbol_usages(self, mcp_server, clean_dgraph, indexed_c_codebase):
        """Test calling find_symbol_usages tool via server."""
        if hasattr(mcp_server, '_call_tool_handler'):
            result = await mcp_server._call_tool_handler(
                "find_symbol_usages",
                {"symbol": "main", "symbol_type": "function"}
            )
            
            assert result is not None
            assert len(result) > 0
            # Result should be a list of TextContent objects
            assert hasattr(result[0], 'text')
            
            # Parse JSON response
            import json
            parsed = json.loads(result[0].text)
            assert "usages" in parsed
            assert "symbol" in parsed
        else:
            pytest.skip("call_tool handler not accessible for testing")
    
    @pytest.mark.asyncio
    async def test_call_tool_invalid_tool(self, mcp_server):
        """Test calling non-existent tool."""
        if hasattr(mcp_server, '_call_tool_handler'):
            result = await mcp_server._call_tool_handler(
                "nonexistent_tool",
                {}
            )
            
            assert result is not None
            assert len(result) > 0
            
            import json
            parsed = json.loads(result[0].text)
            assert "error" in parsed
        else:
            pytest.skip("call_tool handler not accessible for testing")
    
    @pytest.mark.asyncio
    async def test_call_tool_error_handling(self, mcp_server):
        """Test error handling in tool calls."""
        if hasattr(mcp_server, '_call_tool_handler'):
            # Call with invalid parameters
            result = await mcp_server._call_tool_handler(
                "find_symbol_usages",
                {"symbol": "test"}  # Missing symbol_type
            )
            
            assert result is not None
            # Should still return a result (may be error or empty)
            assert len(result) > 0
        else:
            pytest.skip("call_tool handler not accessible for testing")

