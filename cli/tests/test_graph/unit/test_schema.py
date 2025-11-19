"""Unit tests for schema setup - minimal database interaction."""

import pytest
from badger.graph.dgraph import DgraphClient


class TestSchemaSetup:
    """Test schema setup functionality."""
    
    @pytest.fixture
    def client(self):
        """Create a DgraphClient instance for testing."""
        client = DgraphClient()
        yield client
        client.close()
    
    def test_schema_setup_idempotent(self, client):
        """Test that GraphQL schema setup is idempotent."""
        # First setup
        result1 = client.setup_graphql_schema()
        assert result1 is True
        
        # Second setup should also succeed
        result2 = client.setup_graphql_schema()
        assert result2 is True
    
    def test_schema_setup_flag(self, client):
        """Test that GraphQL schema setup flag is set after setup."""
        client._graphql_schema_setup = False
        result = client.setup_graphql_schema()
        assert result is True
        assert client._graphql_schema_setup is True
    
    def test_update_schema_resets_flag(self, client):
        """Test that update_schema resets the setup flag."""
        client.setup_graphql_schema()
        assert client._graphql_schema_setup is True
        
        # Update should reset flag
        client.update_schema()
        # Flag should be reset and then set again
        assert client._graphql_schema_setup is True

