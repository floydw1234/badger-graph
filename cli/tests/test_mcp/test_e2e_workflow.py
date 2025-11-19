"""End-to-end workflow test for MCP server.

This test simulates a complete refactoring workflow:
1. Index a C codebase
2. Use MCP tools to find symbol usages
3. Check include dependencies
4. Find struct field accesses
5. Get function callers
6. Perform semantic code search
7. Check affected files
"""

import pytest
import time
from badger.mcp.tools import (
    find_symbol_usages,
    get_include_dependencies,
    find_struct_field_access,
    get_function_callers,
    semantic_code_search,
    check_affected_files
)
from badger.graph.dgraph import DgraphClient
from badger.embeddings.service import EmbeddingService
from badger.mcp.server import create_mcp_server


@pytest.mark.integration
class TestE2EWorkflow:
    """End-to-end workflow tests."""
    
    @pytest.mark.asyncio
    async def test_complete_refactoring_workflow(self, dgraph_client, clean_dgraph, indexed_c_codebase):
        """Test complete refactoring workflow using all MCP tools."""
        embedding_service = EmbeddingService()
        
        # Step 1: Find symbol usages (e.g., before renaming a function)
        usage_result = await find_symbol_usages(
            dgraph_client,
            "main",
            "function"
        )
        assert usage_result["count"] >= 0
        print(f"Found {usage_result['count']} usages of 'main'")
        
        # Step 2: Check include dependencies (e.g., before modifying a header)
        header_files = [f for f in indexed_c_codebase["files"] if f.endswith(".h")]
        if header_files:
            dep_result = await get_include_dependencies(
                dgraph_client,
                header_files[0]
            )
            assert "dependencies" in dep_result
            print(f"Found {len(dep_result['dependencies'])} files depending on {header_files[0]}")
        
        # Step 3: Find struct field accesses (e.g., before renaming a field)
        field_result = await find_struct_field_access(
            dgraph_client,
            "User",
            "name"
        )
        assert "accesses" in field_result
        print(f"Found {field_result['count']} accesses to User.name")
        
        # Step 4: Get function callers (e.g., before changing function signature)
        caller_result = await get_function_callers(
            dgraph_client,
            "main",
            include_indirect=True
        )
        assert "callers" in caller_result
        print(f"Found {caller_result['count']} callers of 'main'")
        
        # Step 5: Semantic code search (e.g., find related functionality)
        search_result = await semantic_code_search(
            dgraph_client,
            embedding_service,
            "main function entry point",
            limit=5
        )
        assert "functions" in search_result
        print(f"Found {search_result['count']} semantically similar results")
        
        # Step 6: Check affected files (e.g., before committing changes)
        if indexed_c_codebase["files"]:
            affected_result = await check_affected_files(
                dgraph_client,
                [indexed_c_codebase["files"][0]]
            )
            assert "affected_files" in affected_result
            print(f"Found {affected_result['count']} affected files")
    
    @pytest.mark.asyncio
    async def test_mcp_server_e2e(self, dgraph_client, clean_dgraph, indexed_c_codebase):
        """Test MCP server end-to-end with tool calls."""
        embedding_service = EmbeddingService()
        server = create_mcp_server(dgraph_client, embedding_service)
        
        # List tools (using internal handler for testing)
        if hasattr(server, '_list_tools_handler'):
            tools_list = await server._list_tools_handler()
            assert len(tools_list) == 6
        
        # Call find_symbol_usages (using internal handler for testing)
        if hasattr(server, '_call_tool_handler'):
            result1 = await server._call_tool_handler(
                "find_symbol_usages",
                {"symbol": "main", "symbol_type": "function"}
            )
            assert result1 is not None
            
            # Call semantic_code_search
            result2 = await server._call_tool_handler(
                "semantic_code_search",
                {"query": "function entry point", "limit": 3}
            )
            assert result2 is not None
            
            # Call check_affected_files
            if indexed_c_codebase["files"]:
                result3 = await server._call_tool_handler(
                    "check_affected_files",
                    {"changed_files": [indexed_c_codebase["files"][0]]}
                )
                assert result3 is not None

