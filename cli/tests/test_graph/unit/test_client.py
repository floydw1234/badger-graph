"""Unit tests for DgraphClient - no database access required."""

import pytest
from badger.graph.dgraph import DgraphClient


class TestDgraphClientInitialization:
    """Test DgraphClient initialization and configuration."""
    
    def test_client_initialization_with_endpoint(self):
        """Test that DgraphClient initializes correctly with endpoint."""
        client = DgraphClient("localhost:8080")
        try:
            assert client is not None
            assert hasattr(client, 'client')
            assert hasattr(client, 'client_stub')
            assert client.endpoint == "localhost:9080"  # Should convert to gRPC
            assert client.http_endpoint == "http://localhost:8080"  # HTTP endpoint
        finally:
            client.close()
    
    def test_client_initialization_default(self):
        """Test that DgraphClient uses default endpoint."""
        client = DgraphClient()
        try:
            assert client.endpoint == "localhost:9080"
            assert client.http_endpoint == "http://localhost:8080"
        finally:
            client.close()
    
    def test_client_initialization_custom_port(self):
        """Test that DgraphClient handles custom ports correctly."""
        client = DgraphClient("localhost:9090")
        try:
            assert client.endpoint == "localhost:9090"
            assert client.http_endpoint == "http://localhost:9090"
        finally:
            client.close()
    
    def test_client_initialization_hostname_only(self):
        """Test that DgraphClient handles hostname without port."""
        client = DgraphClient("example.com")
        try:
            assert client.endpoint == "example.com:9080"
            assert client.http_endpoint == "http://example.com:8080"
        finally:
            client.close()
    


class TestUIDGeneration:
    """Test deterministic UID generation."""
    
    @pytest.fixture
    def client(self):
        """Create a DgraphClient instance for testing."""
        client = DgraphClient()
        yield client
        client.close()
    
    def test_uid_generation_deterministic(self, client):
        """Test that same input produces same UID."""
        uid1 = client._generate_uid("test_path")
        uid2 = client._generate_uid("test_path")
        
        # Same input should produce same UID
        assert uid1 == uid2
    
    def test_uid_generation_different_inputs(self, client):
        """Test that different inputs produce different UIDs."""
        uid1 = client._generate_uid("test_path")
        uid2 = client._generate_uid("different_path")
        
        # Different input should produce different UID
        assert uid1 != uid2
    
    def test_uid_generation_format(self, client):
        """Test that UID is in correct format."""
        uid = client._generate_uid("test_path")
        
        # Should be hex string of length 16
        assert len(uid) == 16
        assert all(c in '0123456789abcdef' for c in uid)
    
    def test_uid_generation_various_inputs(self, client):
        """Test UID generation with various input types."""
        uid1 = client._generate_uid("file.py")
        uid2 = client._generate_uid("file.py@function_name")
        uid3 = client._generate_uid("/path/to/file.py")
        
        # All should be valid and different
        assert len(uid1) == 16
        assert len(uid2) == 16
        assert len(uid3) == 16
        assert uid1 != uid2 != uid3


class TestQueryContextEmpty:
    """Test query_context with empty inputs - no database access."""
    
    @pytest.fixture
    def client(self):
        """Create a DgraphClient instance for testing."""
        client = DgraphClient()
        yield client
        client.close()
    
    def test_query_context_empty_dict(self, client):
        """Test querying with empty query elements."""
        result = client.query_context({})
        assert result == {}
    
    def test_query_context_none_functions(self, client):
        """Test querying with None functions list."""
        result = client.query_context({"functions": None})
        # Should handle gracefully
        assert isinstance(result, dict)
    
    def test_query_context_empty_lists(self, client):
        """Test querying with empty lists."""
        result = client.query_context({
            "functions": [],
            "classes": [],
            "variables": []
        })
        assert result == {}

