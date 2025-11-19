"""Unit tests for embedding service."""

import pytest
import numpy as np
from badger.embeddings.service import EmbeddingService


class TestEmbeddingService:
    """Test embedding service functionality."""
    
    @pytest.fixture
    def embedding_service(self):
        """Create an EmbeddingService instance for testing."""
        return EmbeddingService()
    
    def test_generate_query_embedding(self, embedding_service):
        """Test query embedding generation."""
        query = "find functions that process user data"
        embedding = embedding_service.generate_query_embedding(query)
        
        # Verify embedding format
        assert embedding is not None
        assert isinstance(embedding, np.ndarray) or isinstance(embedding, list)
        
        # Convert to list if numpy array for easier checking
        if isinstance(embedding, np.ndarray):
            embedding_list = embedding.tolist()
        else:
            embedding_list = embedding
        
        # Verify dimension
        assert len(embedding_list) == 384, f"Expected 384 dimensions, got {len(embedding_list)}"
        
        # Verify all values are floats
        assert all(isinstance(x, (int, float)) for x in embedding_list), "All values should be numbers"
        
        # Verify embedding is not all zeros (for non-empty query)
        assert not all(x == 0.0 for x in embedding_list), "Embedding should not be all zeros for valid query"
    
    def test_generate_query_embedding_empty_string(self, embedding_service):
        """Test query embedding generation with empty string."""
        embedding = embedding_service.generate_query_embedding("")
        
        # Should return zero vector
        assert embedding is not None
        if isinstance(embedding, np.ndarray):
            embedding_list = embedding.tolist()
        else:
            embedding_list = embedding
        
        assert len(embedding_list) == 384
        assert all(x == 0.0 for x in embedding_list), "Empty query should return zero vector"
    
    def test_generate_query_embedding_whitespace_only(self, embedding_service):
        """Test query embedding generation with whitespace-only string."""
        embedding = embedding_service.generate_query_embedding("   \n\t  ")
        
        # Should return zero vector
        assert embedding is not None
        if isinstance(embedding, np.ndarray):
            embedding_list = embedding.tolist()
        else:
            embedding_list = embedding
        
        assert len(embedding_list) == 384
        assert all(x == 0.0 for x in embedding_list), "Whitespace-only query should return zero vector"
    
    def test_generate_query_embedding_dimension(self, embedding_service):
        """Test that query embeddings have correct dimension."""
        query = "test query"
        embedding = embedding_service.generate_query_embedding(query)
        
        if isinstance(embedding, np.ndarray):
            assert embedding.shape == (384,), f"Expected shape (384,), got {embedding.shape}"
        else:
            assert len(embedding) == 384, f"Expected 384 dimensions, got {len(embedding)}"
    
    def test_generate_query_embedding_different_queries(self, embedding_service):
        """Test that different queries produce different embeddings."""
        query1 = "find functions that process user data"
        query2 = "get all classes that handle authentication"
        
        embedding1 = embedding_service.generate_query_embedding(query1)
        embedding2 = embedding_service.generate_query_embedding(query2)
        
        # Convert to lists for comparison
        if isinstance(embedding1, np.ndarray):
            emb1_list = embedding1.tolist()
        else:
            emb1_list = embedding1
        
        if isinstance(embedding2, np.ndarray):
            emb2_list = embedding2.tolist()
        else:
            emb2_list = embedding2
        
        # Different queries should produce different embeddings
        assert emb1_list != emb2_list, "Different queries should produce different embeddings"
        
        # Verify both have correct dimension
        assert len(emb1_list) == 384
        assert len(emb2_list) == 384

