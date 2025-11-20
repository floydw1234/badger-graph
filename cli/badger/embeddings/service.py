"""Embedding service for generating vector embeddings using sentence-transformers."""

import logging
from typing import List, Optional

try:
    from sentence_transformers import SentenceTransformer
    import torch
except ImportError:
    SentenceTransformer = None
    torch = None

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
        
        Raises:
            ImportError: If sentence-transformers is not installed
            RuntimeError: If GPU is not available
        """
        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install it with: pip install sentence-transformers"
            )
        
        if torch is None:
            raise ImportError(
                "PyTorch is not installed. "
                "Install it with: pip install torch"
            )
        
        # Check for GPU availability
        if not torch.cuda.is_available():
            raise RuntimeError(
                "GPU is not available. CUDA is required for embedding generation. "
                "Please ensure you have a CUDA-compatible GPU and PyTorch with CUDA support installed."
            )
        
        # Check GPU compute capability compatibility
        try:
            device_capability = torch.cuda.get_device_capability(0)
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"GPU detected: {device_name} with compute capability {device_capability}")
            
            # Try a simple CUDA operation to verify it works
            test_tensor = torch.zeros(1, device="cuda")
            del test_tensor
            torch.cuda.synchronize()
        except RuntimeError as e:
            if "no kernel image" in str(e).lower() or "not compatible" in str(e).lower():
                raise RuntimeError(
                    f"GPU compute capability mismatch: Your GPU ({device_name} with compute capability {device_capability}) "
                    f"is not supported by the current PyTorch build. "
                    f"PyTorch needs to be built from source or a newer version with support for compute capability {device_capability} "
                    f"needs to be released. See https://pytorch.org/get-started/locally/ for building instructions."
                ) from e
            raise
        
        self.device = "cuda"
        self.model_name = model_name or self.DEFAULT_MODEL
        self._model: Optional[SentenceTransformer] = None
        logger.info(f"Initializing embedding service with model: {self.model_name} on GPU")
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name} on GPU")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"Embedding model loaded successfully on {self.device}")
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
        except RuntimeError as e:
            if "no kernel image" in str(e).lower() or "not compatible" in str(e).lower():
                error_msg = (
                    f"GPU compute capability error when generating embedding for '{name}': {e}. "
                    f"Your GPU may not be supported by the current PyTorch build. "
                    f"Consider building PyTorch from source with support for your GPU's compute capability."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            raise
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
        except RuntimeError as e:
            if "no kernel image" in str(e).lower() or "not compatible" in str(e).lower():
                error_msg = (
                    f"GPU compute capability error when generating embedding for '{name}': {e}. "
                    f"Your GPU may not be supported by the current PyTorch build. "
                    f"Consider building PyTorch from source with support for your GPU's compute capability."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            raise
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

