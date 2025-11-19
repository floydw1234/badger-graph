"""LLM configuration helpers."""

from typing import Optional
from badger.config import BadgerConfig


def get_qwen_endpoint(config: BadgerConfig) -> str:
    """Get qwen endpoint URL from config or use defaults."""
    if config.qwen_endpoint:
        return config.qwen_endpoint
    
    if config.llm_provider == "vllm":
        return "http://localhost:8001"
    else:  # ollama
        return "http://localhost:11434"


def get_gpt_oss_endpoint(config: BadgerConfig) -> str:
    """Get gpt-oss endpoint URL from config or use defaults."""
    if config.gpt_oss_endpoint:
        return config.gpt_oss_endpoint
    
    if config.llm_provider == "vllm":
        return "http://localhost:8000"
    else:  # ollama
        return "http://localhost:11434"


def get_qwen_model(config: BadgerConfig) -> str:
    """Get qwen model name from config or use defaults."""
    if config.qwen_model:
        return config.qwen_model
    
    if config.llm_provider == "vllm":
        # For vLLM, model is specified in the endpoint path or use default
        return "qwen3-coder-30b"
    else:  # ollama - uses colon notation
        return "qwen3-coder:30b"


def get_gpt_oss_model(config: BadgerConfig) -> str:
    """Get gpt-oss model name from config or use defaults."""
    if config.gpt_oss_model:
        return config.gpt_oss_model
    
    if config.llm_provider == "vllm":
        # For vLLM, model is specified in the endpoint path or use default
        return "gpt-oss-120b"
    else:  # ollama - uses colon notation
        return "gpt-oss:120b"

