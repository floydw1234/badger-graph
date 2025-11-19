"""End-to-end integration tests for complete query processing pipeline."""

import pytest
import time
from unittest.mock import Mock, patch
from badger.graph.dgraph import DgraphClient
from badger.llm.models import QwenClient
from badger.config import BadgerConfig


@pytest.mark.integration
class TestQueryPipeline:
    """Test complete query processing pipeline."""
    
    @pytest.fixture
    def config(self):
        """Create a test config."""
        return BadgerConfig(
            llm_provider="ollama",
            qwen_endpoint="http://localhost:11434",
            qwen_model="qwen3-coder:30b"
        )
    
    def test_query_with_vector_search_no_llm(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test query_with_vector_search() without LLM (fallback to simple query)."""
        # Insert data
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Wait for indexing
        time.sleep(1.0)
        
        # Test query
        user_query = "find functions that process data"
        results = dgraph_client.query_with_vector_search(
            user_query=user_query,
            top_k=3,
            qwen_client=None,  # No LLM client
            use_llm_query=False
        )
        
        # Verify results structure
        assert isinstance(results, dict)
        assert "functions" in results
        assert "classes" in results
        assert "files" in results
        
        # Should have some results if data exists
        if parsed_python_data["graph_data"].functions:
            # May or may not have results depending on similarity
            assert isinstance(results["functions"], list)
            assert isinstance(results["classes"], list)
            assert isinstance(results["files"], list)
    
    def test_query_with_vector_search_empty_query(self, dgraph_client, clean_dgraph):
        """Test query_with_vector_search() with empty query."""
        results = dgraph_client.query_with_vector_search(
            user_query="",
            top_k=5
        )
        
        assert results == {"functions": [], "classes": [], "files": []}
    
    def test_query_with_vector_search_with_mocked_llm(self, dgraph_client, clean_dgraph, parsed_python_data, config):
        """Test query_with_vector_search() with mocked LLM."""
        # Insert data
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Wait for indexing
        time.sleep(1.0)
        
        # Create QwenClient
        qwen_client = QwenClient(config)
        
        # Mock the LLM response
        mock_response = {
            "content": """query($funcName0: String!) {
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
}""",
            "model": "qwen3-coder:30b",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        }
        
        # Test query
        user_query = "find functions that handle user data"
        
        with patch.object(qwen_client, 'chat_completion', return_value=mock_response):
            results = dgraph_client.query_with_vector_search(
                user_query=user_query,
                top_k=3,
                qwen_client=qwen_client,
                use_llm_query=True
            )
        
        # Verify results structure
        assert isinstance(results, dict)
        assert "functions" in results
        assert "classes" in results
        assert "files" in results
    
    def test_query_pipeline_steps(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test individual steps of the query pipeline."""
        # Insert data
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Wait for indexing
        time.sleep(1.0)
        
        # Step 1: Generate query embedding
        from badger.embeddings.service import EmbeddingService
        embedding_service = EmbeddingService()
        user_query = "functions that process user information"
        query_embedding = embedding_service.generate_query_embedding(user_query)
        
        assert query_embedding is not None
        if hasattr(query_embedding, 'shape'):
            assert query_embedding.shape == (384,)
        else:
            assert len(query_embedding) == 384
        
        # Step 2: Vector similarity search
        vector_results = dgraph_client.vector_search_similar(
            query_embedding=query_embedding.tolist() if hasattr(query_embedding, 'tolist') else query_embedding,
            top_k=3,
            search_type="both"
        )
        
        assert isinstance(vector_results, dict)
        assert "functions" in vector_results
        assert "classes" in vector_results
        
        # Step 3: If we have matches, test query construction
        if vector_results.get("functions") or vector_results.get("classes"):
            # Test that we can construct a simple query from results
            query_elements = {
                "functions": [f["name"] for f in vector_results.get("functions", [])],
                "classes": [c["name"] for c in vector_results.get("classes", [])]
            }
            
            context_results = dgraph_client.query_context(query_elements)
            
            assert isinstance(context_results, dict)
            assert "functions" in context_results
            assert "classes" in context_results
            assert "files" in context_results

