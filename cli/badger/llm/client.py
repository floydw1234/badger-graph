"""LLM client wrapper for OpenAI-compatible APIs."""

import logging
import time
from typing import List, Dict, Any, Optional, Iterator, Generator
from collections import defaultdict
from datetime import datetime, timedelta

import openai
import tiktoken

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter for LLM requests."""
    
    def __init__(self, requests_per_minute: int = 60):
        """Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum number of requests per minute
        """
        self.requests_per_minute = requests_per_minute
        self.requests: defaultdict = defaultdict(list)
    
    def wait_if_needed(self, key: str) -> None:
        """Wait if rate limit would be exceeded.
        
        Args:
            key: Key to track requests (e.g., model name)
        """
        now = datetime.now()
        # Remove requests older than 1 minute
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if now - req_time < timedelta(minutes=1)
        ]
        
        # If at limit, wait until oldest request is 1 minute old
        if len(self.requests[key]) >= self.requests_per_minute:
            oldest = min(self.requests[key])
            wait_until = oldest + timedelta(minutes=1)
            wait_seconds = (wait_until - now).total_seconds()
            if wait_seconds > 0:
                logger.debug(f"Rate limit reached, waiting {wait_seconds:.2f} seconds")
                time.sleep(wait_seconds)
        
        # Record this request
        self.requests[key].append(now)


class LLMClient:
    """Client for interacting with OpenAI-compatible LLM APIs."""
    
    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 300,
        requests_per_minute: int = 60
    ):
        """Initialize LLM client.
        
        Args:
            endpoint: Base URL for the API (e.g., http://localhost:11434)
            model: Model name to use
            api_key: Optional API key (not needed for local Ollama/vLLM)
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            requests_per_minute: Rate limit (requests per minute)
        """
        self.endpoint = endpoint.rstrip('/')
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limiter = RateLimiter(requests_per_minute)
        
        # Initialize OpenAI client
        self.client = openai.OpenAI(
            base_url=f"{self.endpoint}/v1",
            api_key=api_key or "not-needed",
        )
        
        # Tokenizer cache
        self._tokenizer_cache: Dict[str, Any] = {}
    
    def _get_tokenizer(self, model_name: Optional[str] = None) -> Any:
        """Get or create tokenizer for the model.
        
        Args:
            model_name: Model name (defaults to self.model)
        
        Returns:
            Tiktoken tokenizer instance
        """
        model_name = model_name or self.model
        
        if model_name not in self._tokenizer_cache:
            try:
                # Try to get appropriate tokenizer
                # Most models use cl100k_base, but we can try to detect
                if "gpt" in model_name.lower() or "qwen" in model_name.lower():
                    encoding_name = "cl100k_base"
                else:
                    encoding_name = "cl100k_base"  # Default fallback
                
                self._tokenizer_cache[model_name] = tiktoken.get_encoding(encoding_name)
            except Exception as e:
                logger.warning(f"Failed to load tokenizer for {model_name}: {e}")
                # Fallback to cl100k_base
                self._tokenizer_cache[model_name] = tiktoken.get_encoding("cl100k_base")
        
        return self._tokenizer_cache[model_name]
    
    def count_tokens(self, text: str, model_name: Optional[str] = None) -> int:
        """Count tokens in text.
        
        Args:
            text: Text to count tokens for
            model_name: Optional model name (defaults to self.model)
        
        Returns:
            Number of tokens
        """
        try:
            tokenizer = self._get_tokenizer(model_name)
            return len(tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed: {e}, using approximation")
            # Fallback approximation: ~4 characters per token
            return len(text) // 4
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
        
        Returns:
            Function result
        
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {self.max_retries} attempts: {e}")
                    raise
            except openai.RateLimitError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    # Wait longer for rate limits
                    wait_time = 60  # Wait 1 minute
                    logger.warning(
                        f"Rate limit exceeded (attempt {attempt + 1}/{self.max_retries}). "
                        f"Waiting {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Rate limit error after {self.max_retries} attempts: {e}")
                    raise
            except Exception as e:
                # For other errors, don't retry
                logger.error(f"Request failed with error: {e}")
                raise
        
        if last_exception:
            raise last_exception
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send chat completion request (non-streaming).
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for OpenAI API
        
        Returns:
            Response dict with 'content' and other metadata
        """
        # Rate limit
        self.rate_limiter.wait_if_needed(self.model)
        
        def _make_request():
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=self.timeout,
                **kwargs
            )
        
        response = self._retry_with_backoff(_make_request)
        
        # Extract content
        content = response.choices[0].message.content
        usage = response.usage
        
        return {
            "content": content,
            "model": response.model,
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage else None,
                "completion_tokens": usage.completion_tokens if usage else None,
                "total_tokens": usage.total_tokens if usage else None,
            },
            "finish_reason": response.choices[0].finish_reason,
        }
    
    def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """Send streaming chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for OpenAI API
        
        Yields:
            Content chunks as they arrive
        """
        # Rate limit
        self.rate_limiter.wait_if_needed(self.model)
        
        def _make_request():
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                timeout=self.timeout,
                **kwargs
            )
        
        try:
            stream = self._retry_with_backoff(_make_request)
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise

