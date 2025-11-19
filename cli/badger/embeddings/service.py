"""Embedding service for generating vector embeddings using sentence-transformers."""

import logging
from typing import List, Optional

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings for code elements."""
    
    # Default model: all-MiniLM-L6-v2 outputs 384-dimensional embeddings
    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384
    
    def __init__(self, model_name: Optional[str] = None):
        """Initialize the embedding service.
        
        Args:
            model_name: Name of the sentence-transformers model to use.
                       Defaults to all-MiniLM-L6-v2 (384 dimensions).
        """
        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install it with: pip install sentence-transformers"
            )
        
        self.model_name = model_name or self.DEFAULT_MODEL
        self._model: Optional[SentenceTransformer] = None
        logger.info(f"Initializing embedding service with model: {self.model_name}")
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully")
        return self._model
    
    def generate_function_embedding(
        self,
        name: str,
        signature: Optional[str] = None,
        docstring: Optional[str] = None
    ) -> List[float]:
        """Generate embedding for a function.
        
        Args:
            name: Function name
            signature: Function signature (optional)
            docstring: Function docstring (optional)
        
        Returns:
            List of float values representing the embedding vector
        """
        # Build text representation
        parts = [name]
        if signature:
            parts.append(signature)
        if docstring:
            parts.append(docstring)
        
        text = "\n".join(parts)
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            # Return as numpy array for float32vector compatibility
            return embedding
        except Exception as e:
            logger.warning(f"Failed to generate function embedding for '{name}': {e}")
            # Return zero vector as fallback (numpy array)
            import numpy as np
            return np.zeros(self.EMBEDDING_DIMENSION, dtype=np.float32)
    
    def generate_class_embedding(
        self,
        name: str,
        methods: Optional[List[str]] = None
    ) -> List[float]:
        """Generate embedding for a class.
        
        Args:
            name: Class name
            methods: List of method names (optional)
        
        Returns:
            List of float values representing the embedding vector
        """
        # Build text representation
        parts = [name]
        if methods:
            methods_text = ", ".join(methods)
            parts.append(f"Methods: {methods_text}")
        
        text = "\n".join(parts)
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            # Return as numpy array for float32vector compatibility
            return embedding
        except Exception as e:
            logger.warning(f"Failed to generate class embedding for '{name}': {e}")
            # Return zero vector as fallback (numpy array)
            import numpy as np
            return np.zeros(self.EMBEDDING_DIMENSION, dtype=np.float32)
    
    def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a user query.
        
        Args:
            query: Natural language query string from user
        
        Returns:
            List of float values representing the embedding vector (384 dimensions)
        
        Raises:
            ValueError: If query is empty or invalid
        """
        if not query or not query.strip():
            logger.warning("Empty query provided, returning zero vector")
            import numpy as np
            return np.zeros(self.EMBEDDING_DIMENSION, dtype=np.float32)
        
        try:
            embedding = self.model.encode(query.strip(), convert_to_numpy=True)
            # Return as numpy array for consistency with other methods
            return embedding
        except Exception as e:
            logger.warning(f"Failed to generate query embedding: {e}")
            # Return zero vector as fallback (numpy array)
            import numpy as np
            return np.zeros(self.EMBEDDING_DIMENSION, dtype=np.float32)
    
    @property
    def embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this service."""
        return self.EMBEDDING_DIMENSION

