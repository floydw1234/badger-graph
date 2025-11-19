"""Integration tests for MCP tools."""

import pytest
import asyncio
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


@pytest.mark.integration
class TestMCPTools:
    """Test all MCP tool implementations."""
    
    @pytest.mark.asyncio
    async def test_find_symbol_usages_function(self, dgraph_client, clean_dgraph, indexed_c_codebase):
        """Test find_symbol_usages for functions."""
        # Find a function that exists in the test codebase
        # We'll search for 'main' which should exist in main.c
        result = await find_symbol_usages(
            dgraph_client,
            "main",
            "function"
        )
        
        assert isinstance(result, dict)
        assert "usages" in result
        assert "count" in result
        assert "symbol" in result
        assert result["symbol"] == "main"
        assert result["symbol_type"] == "function"
        assert isinstance(result["usages"], list)
    
    @pytest.mark.asyncio
    async def test_find_symbol_usages_macro(self, dgraph_client, clean_dgraph, indexed_c_codebase):
        """Test find_symbol_usages for macros."""
        result = await find_symbol_usages(
            dgraph_client,
            "MAX_SIZE",  # Common macro name, may or may not exist
            "macro"
        )
        
        assert isinstance(result, dict)
        assert "usages" in result
        assert "count" in result
        assert "symbol" in result
        assert result["symbol_type"] == "macro"
    
    @pytest.mark.asyncio
    async def test_find_symbol_usages_invalid_type(self, dgraph_client):
        """Test find_symbol_usages with invalid symbol type."""
        result = await find_symbol_usages(
            dgraph_client,
            "test",
            "invalid_type"
        )
        
        assert isinstance(result, dict)
        assert "error" in result
        assert result["type"] == "invalid_parameter"
    
    @pytest.mark.asyncio
    async def test_get_include_dependencies(self, dgraph_client, clean_dgraph, indexed_c_codebase):
        """Test get_include_dependencies."""
        # Get a header file from the indexed codebase
        header_files = [f for f in indexed_c_codebase["files"] if f.endswith(".h")]
        if not header_files:
            pytest.skip("No header files in test codebase")
        
        result = await get_include_dependencies(
            dgraph_client,
            header_files[0]
        )
        
        assert isinstance(result, dict)
        assert "file" in result
        assert "dependencies" in result
        assert isinstance(result["dependencies"], list)
    
    @pytest.mark.asyncio
    async def test_find_struct_field_access(self, dgraph_client, clean_dgraph, indexed_c_codebase):
        """Test find_struct_field_access."""
        # Try to find a struct field access (may not exist in test codebase)
        result = await find_struct_field_access(
            dgraph_client,
            "User",
            "name"
        )
        
        assert isinstance(result, dict)
        assert "accesses" in result
        assert "count" in result
        assert "struct_name" in result
        assert "field_name" in result
        assert isinstance(result["accesses"], list)
    
    @pytest.mark.asyncio
    async def test_get_function_callers(self, dgraph_client, clean_dgraph, indexed_c_codebase):
        """Test get_function_callers."""
        result = await get_function_callers(
            dgraph_client,
            "main",
            include_indirect=True
        )
        
        assert isinstance(result, dict)
        assert "callers" in result
        assert "count" in result
        assert "function_name" in result
        assert isinstance(result["callers"], list)
        assert isinstance(result.get("indirect", []), list)
    
    @pytest.mark.asyncio
    async def test_get_function_callers_no_indirect(self, dgraph_client, clean_dgraph, indexed_c_codebase):
        """Test get_function_callers without indirect calls."""
        result = await get_function_callers(
            dgraph_client,
            "main",
            include_indirect=False
        )
        
        assert isinstance(result, dict)
        assert "callers" in result
        assert "indirect" in result
        assert len(result["indirect"]) == 0
    
    @pytest.mark.asyncio
    async def test_semantic_code_search(self, dgraph_client, embedding_service, clean_dgraph, indexed_c_codebase):
        """Test semantic_code_search."""
        result = await semantic_code_search(
            dgraph_client,
            embedding_service,
            "function that processes data",
            file_pattern="*",
            limit=5
        )
        
        assert isinstance(result, dict)
        assert "functions" in result
        assert "classes" in result
        assert "count" in result
        assert "query" in result
        assert isinstance(result["functions"], list)
        assert isinstance(result["classes"], list)
    
    @pytest.mark.asyncio
    async def test_semantic_code_search_empty_query(self, dgraph_client, embedding_service):
        """Test semantic_code_search with empty query."""
        result = await semantic_code_search(
            dgraph_client,
            embedding_service,
            "",
            limit=5
        )
        
        assert isinstance(result, dict)
        assert "error" in result
        assert result["type"] == "invalid_parameter"
    
    @pytest.mark.asyncio
    async def test_check_affected_files(self, dgraph_client, clean_dgraph, indexed_c_codebase):
        """Test check_affected_files."""
        # Use a file from the indexed codebase
        test_file = indexed_c_codebase["files"][0]
        
        result = await check_affected_files(
            dgraph_client,
            [test_file]
        )
        
        assert isinstance(result, dict)
        assert "affected_files" in result
        assert "by_type" in result
        assert "count" in result
        assert "changed_files" in result
        assert isinstance(result["affected_files"], list)
        assert isinstance(result["by_type"], dict)
        assert "direct_include" in result["by_type"]
        assert "transitive_include" in result["by_type"]
        assert "function_call" in result["by_type"]
    
    @pytest.mark.asyncio
    async def test_check_affected_files_multiple(self, dgraph_client, clean_dgraph, indexed_c_codebase):
        """Test check_affected_files with multiple files."""
        if len(indexed_c_codebase["files"]) < 2:
            pytest.skip("Need at least 2 files for this test")
        
        result = await check_affected_files(
            dgraph_client,
            indexed_c_codebase["files"][:2]
        )
        
        assert isinstance(result, dict)
        assert "affected_files" in result
        assert len(result["changed_files"]) == 2

