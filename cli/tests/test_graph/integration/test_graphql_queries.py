"""Integration tests for GraphQL query operations."""

import pytest
from badger.graph.dgraph import DgraphClient


@pytest.mark.integration
class TestGraphQLQueries:
    """Test GraphQL query operations with real database."""
    
    def test_query_single_function(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test querying a single function by name."""
        # Insert data
        dgraph_client.insert_graph(parsed_python_data["graph_data"])
        
        # Query for a function
        if parsed_python_data["graph_data"].functions:
            func_name = parsed_python_data["graph_data"].functions[0]["name"]
            result = dgraph_client.query_context({
                "functions": [func_name]
            })
            
            assert "functions" in result
            assert len(result["functions"]) > 0
            assert result["functions"][0]["name"] == func_name
    
    def test_query_multiple_functions(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test querying multiple functions at once."""
        # Insert data
        dgraph_client.insert_graph(parsed_python_data["graph_data"])
        
        # Query for multiple functions
        if len(parsed_python_data["graph_data"].functions) >= 2:
            func_names = [
                parsed_python_data["graph_data"].functions[0]["name"],
                parsed_python_data["graph_data"].functions[1]["name"]
            ]
            result = dgraph_client.query_context({
                "functions": func_names
            })
            
            assert "functions" in result
            assert len(result["functions"]) >= 2
            
            result_names = [f.get("name") for f in result["functions"]]
            for name in func_names:
                assert name in result_names
    
    def test_query_classes(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test querying classes."""
        # Insert data
        dgraph_client.insert_graph(parsed_python_data["graph_data"])
        
        # Query for classes
        if parsed_python_data["graph_data"].classes:
            class_name = parsed_python_data["graph_data"].classes[0]["name"]
            result = dgraph_client.query_context({
                "classes": [class_name]
            })
            
            assert "classes" in result
            assert len(result["classes"]) > 0
            
            cls = result["classes"][0]
            assert "name" in cls
            assert "file" in cls
            assert "line" in cls
    
    def test_query_with_relationships(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test querying functions and retrieving their relationships."""
        # Insert data
        dgraph_client.insert_graph(parsed_python_data["graph_data"])
        
        # Query for a function
        if parsed_python_data["graph_data"].functions:
            func_name = parsed_python_data["graph_data"].functions[0]["name"]
            result = dgraph_client.query_context({
                "functions": [func_name]
            })
            
            assert "functions" in result
            assert len(result["functions"]) > 0
            # Should return file information
            assert "files" in result
            assert len(result["files"]) > 0
    
    def test_query_c_file_functions(self, dgraph_client, clean_dgraph, parsed_c_data):
        """Test querying functions from C file."""
        # Insert data
        dgraph_client.insert_graph(parsed_c_data["graph_data"])
        
        # Query for functions
        if parsed_c_data["graph_data"].functions:
            func_name = parsed_c_data["graph_data"].functions[0]["name"]
            result = dgraph_client.query_context({
                "functions": [func_name]
            })
            
            assert "functions" in result
            assert len(result["functions"]) > 0
            
            # Verify metadata is present
            func = result["functions"][0]
            assert "name" in func
            assert "file" in func
            assert "line" in func

