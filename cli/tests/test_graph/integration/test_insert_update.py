"""Integration tests for insert and update operations."""

import pytest
from badger.graph.dgraph import DgraphClient


@pytest.mark.integration
class TestInsertOperations:
    """Test graph insertion operations."""
    
    def test_insert_python_file(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test inserting a parsed Python file."""
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Verify data was inserted by querying
        if parsed_python_data["graph_data"].functions:
            func_name = parsed_python_data["graph_data"].functions[0]["name"]
            query_result = dgraph_client.query_context({
                "functions": [func_name]
            })
            assert "functions" in query_result
            assert len(query_result["functions"]) > 0
    
    def test_insert_c_file(self, dgraph_client, clean_dgraph, parsed_c_data):
        """Test inserting a parsed C file."""
        result = dgraph_client.insert_graph(parsed_c_data["graph_data"])
        assert result is True
        
        # Verify data was inserted
        if parsed_c_data["graph_data"].functions:
            func_name = parsed_c_data["graph_data"].functions[0]["name"]
            query_result = dgraph_client.query_context({
                "functions": [func_name]
            })
            assert "functions" in query_result
            assert len(query_result["functions"]) > 0
    
    def test_insert_multiple_files(self, dgraph_client, clean_dgraph, parsed_python_data, parsed_c_data):
        """Test inserting multiple files."""
        # Insert Python file
        result1 = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result1 is True
        
        # Insert C file
        result2 = dgraph_client.insert_graph(parsed_c_data["graph_data"])
        assert result2 is True
        
        # Verify both are queryable
        if parsed_python_data["graph_data"].functions and parsed_c_data["graph_data"].functions:
            py_func = parsed_python_data["graph_data"].functions[0]["name"]
            c_func = parsed_c_data["graph_data"].functions[0]["name"]
            
            result = dgraph_client.query_context({
                "functions": [py_func, c_func]
            })
            assert len(result["functions"]) >= 2


@pytest.mark.integration
class TestUpdateOperations:
    """Test graph update operations."""
    
    def test_update_existing_file(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test updating an existing file."""
        # First insert
        result1 = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result1 is True
        
        # Update the same file
        result2 = dgraph_client.update_graph(
            str(parsed_python_data["file_path"]),
            parsed_python_data["parse_result"]
        )
        assert result2 is True
        
        # Update again (should work)
        result3 = dgraph_client.update_graph(
            str(parsed_python_data["file_path"]),
            parsed_python_data["parse_result"]
        )
        assert result3 is True
    
    def test_update_cross_file_relationships(self, dgraph_client, clean_dgraph, parsed_python_data, parsed_c_data):
        """Test that updates preserve cross-file relationships."""
        # Insert both files
        dgraph_client.insert_graph(parsed_python_data["graph_data"])
        dgraph_client.insert_graph(parsed_c_data["graph_data"])
        
        # Update one file
        result = dgraph_client.update_graph(
            str(parsed_python_data["file_path"]),
            parsed_python_data["parse_result"]
        )
        assert result is True
        
        # Verify both files are still queryable
        if parsed_python_data["graph_data"].functions and parsed_c_data["graph_data"].functions:
            py_func = parsed_python_data["graph_data"].functions[0]["name"]
            c_func = parsed_c_data["graph_data"].functions[0]["name"]
            
            result = dgraph_client.query_context({
                "functions": [py_func, c_func]
            })
            assert len(result["functions"]) >= 2

