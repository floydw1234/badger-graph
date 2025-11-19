"""Tests for LLM model clients."""

import pytest
from unittest.mock import Mock, patch
from badger.llm.models import QwenClient
from badger.config import BadgerConfig


class TestQwenClient:
    """Test QwenClient functionality."""
    
    @pytest.fixture
    def config(self):
        """Create a test config."""
        return BadgerConfig(
            llm_provider="ollama",
            qwen_endpoint="http://localhost:11434",
            qwen_model="qwen3-coder:30b"
        )
    
    @pytest.fixture
    def qwen_client(self, config):
        """Create a QwenClient instance for testing."""
        return QwenClient(config)
    
    def test_construct_graphql_query_with_functions(self, qwen_client):
        """Test GraphQL query construction with function matches."""
        matched_elements = {
            "functions": [
                {"name": "process_user_data", "file": "src/user.py", "signature": "def process_user_data(user_id: int)", "vector_distance": 0.2},
                {"name": "get_user", "file": "src/user.py", "signature": "def get_user(user_id: int)", "vector_distance": 0.3}
            ],
            "classes": []
        }
        user_query = "find functions that handle user data"
        
        # Mock the LLM response
        mock_response = {
            "content": """query($funcName0: String!, $funcName1: String!) {
    func_0: queryFunction(filter: {name: {eq: $funcName0}}) {
        id
        name
        file
        line
        signature
        callsFunction {
            name
            file
        }
    }
    func_1: queryFunction(filter: {name: {eq: $funcName1}}) {
        id
        name
        file
        line
        signature
    }
}""",
            "model": "qwen3-coder:30b",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        }
        
        with patch.object(qwen_client, 'chat_completion', return_value=mock_response):
            query = qwen_client.construct_graphql_query(matched_elements, user_query)
        
        # Verify query structure
        assert "query" in query.lower()
        assert "queryFunction" in query
        assert "$funcName0" in query or "process_user_data" in query
        assert "$funcName1" in query or "get_user" in query
    
    def test_construct_graphql_query_with_classes(self, qwen_client):
        """Test GraphQL query construction with class matches."""
        matched_elements = {
            "functions": [],
            "classes": [
                {"name": "UserManager", "file": "src/user.py", "methods": ["create_user", "delete_user"], "vector_distance": 0.2}
            ]
        }
        user_query = "find classes that manage users"
        
        # Mock the LLM response
        mock_response = {
            "content": """query($className0: String!) {
    cls_0: queryClass(filter: {name: {eq: $className0}}) {
        id
        name
        file
        line
        methods
        containsMethod {
            name
            file
        }
    }
}""",
            "model": "qwen3-coder:30b",
            "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}
        }
        
        with patch.object(qwen_client, 'chat_completion', return_value=mock_response):
            query = qwen_client.construct_graphql_query(matched_elements, user_query)
        
        # Verify query structure
        assert "query" in query.lower()
        assert "queryClass" in query
        assert "$className0" in query or "UserManager" in query
    
    def test_construct_graphql_query_with_markdown_wrapping(self, qwen_client):
        """Test that markdown code blocks are removed from LLM response."""
        matched_elements = {
            "functions": [
                {"name": "test_func", "file": "test.py", "signature": "def test_func()", "vector_distance": 0.1}
            ],
            "classes": []
        }
        user_query = "test query"
        
        # Mock response with markdown code blocks
        mock_response = {
            "content": """```graphql
query($funcName0: String!) {
    func_0: queryFunction(filter: {name: {eq: $funcName0}}) {
        id
        name
    }
}
```""",
            "model": "qwen3-coder:30b",
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}
        }
        
        with patch.object(qwen_client, 'chat_completion', return_value=mock_response):
            query = qwen_client.construct_graphql_query(matched_elements, user_query)
        
        # Verify markdown was removed
        assert not query.startswith("```")
        assert not query.endswith("```")
        assert "query" in query.lower()
        assert "queryFunction" in query
    
    def test_construct_graphql_query_empty_matches(self, qwen_client):
        """Test query construction with no matches."""
        matched_elements = {
            "functions": [],
            "classes": []
        }
        user_query = "find something that doesn't exist"
        
        # Mock response for empty case
        mock_response = {
            "content": "query { }",
            "model": "qwen3-coder:30b",
            "usage": {"prompt_tokens": 50, "completion_tokens": 5, "total_tokens": 55}
        }
        
        with patch.object(qwen_client, 'chat_completion', return_value=mock_response):
            query = qwen_client.construct_graphql_query(matched_elements, user_query)
        
        # Should still return a query (even if empty)
        assert isinstance(query, str)
    
    def test_construct_graphql_query_both_types(self, qwen_client):
        """Test query construction with both functions and classes."""
        matched_elements = {
            "functions": [
                {"name": "process_data", "file": "src/data.py", "signature": "def process_data()", "vector_distance": 0.2}
            ],
            "classes": [
                {"name": "DataHandler", "file": "src/data.py", "methods": ["handle"], "vector_distance": 0.3}
            ]
        }
        user_query = "find data processing code"
        
        # Mock response
        mock_response = {
            "content": """query($funcName0: String!, $className0: String!) {
    func_0: queryFunction(filter: {name: {eq: $funcName0}}) {
        id
        name
        file
    }
    cls_0: queryClass(filter: {name: {eq: $className0}}) {
        id
        name
        file
    }
}""",
            "model": "qwen3-coder:30b",
            "usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160}
        }
        
        with patch.object(qwen_client, 'chat_completion', return_value=mock_response):
            query = qwen_client.construct_graphql_query(matched_elements, user_query)
        
        # Verify both types are in query
        assert "queryFunction" in query
        assert "queryClass" in query

