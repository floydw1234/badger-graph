"""Unit tests for GraphQL query construction logic."""

import pytest
from unittest.mock import Mock, patch
from badger.graph.dgraph import DgraphClient


class TestGraphQLQueryConstruction:
    """Test GraphQL query construction without executing queries."""
    
    @pytest.fixture
    def client(self):
        """Create a DgraphClient instance for testing."""
        client = DgraphClient()
        yield client
        client.close()
    
    def test_query_context_function_names(self, client):
        """Test query_context constructs correct GraphQL for function names."""
        # Mock the execute_graphql_query to capture the query
        with patch.object(client, 'execute_graphql_query') as mock_execute:
            mock_execute.return_value = {}
            
            client.query_context({
                "functions": ["test_function"]
            })
            
            # Verify query was called
            assert mock_execute.called
            call_args = mock_execute.call_args
            
            # Check query contains function name
            query = call_args[0][0]
            assert "queryFunction" in query
            assert "test_function" in str(call_args[0][1].values())
    
    def test_query_context_class_names(self, client):
        """Test query_context constructs correct GraphQL for class names."""
        with patch.object(client, 'execute_graphql_query') as mock_execute:
            mock_execute.return_value = {}
            
            client.query_context({
                "classes": ["TestClass"]
            })
            
            assert mock_execute.called
            call_args = mock_execute.call_args
            query = call_args[0][0]
            assert "queryClass" in query
            assert "TestClass" in str(call_args[0][1].values())
    
    def test_query_context_multiple_functions(self, client):
        """Test query_context handles multiple function names."""
        with patch.object(client, 'execute_graphql_query') as mock_execute:
            mock_execute.return_value = {}
            
            client.query_context({
                "functions": ["func1", "func2", "func3"]
            })
            
            assert mock_execute.called
            call_args = mock_execute.call_args
            query = call_args[0][0]
            variables = call_args[0][1]
            
            # Should have multiple function queries
            assert query.count("queryFunction") == 3
            assert len(variables) == 3
    
    def test_query_context_mixed_functions_and_classes(self, client):
        """Test query_context handles both functions and classes."""
        with patch.object(client, 'execute_graphql_query') as mock_execute:
            mock_execute.return_value = {}
            
            client.query_context({
                "functions": ["func1"],
                "classes": ["Class1"]
            })
            
            assert mock_execute.called
            call_args = mock_execute.call_args
            query = call_args[0][0]
            
            # Should have both queryFunction and queryClass
            assert "queryFunction" in query
            assert "queryClass" in query

