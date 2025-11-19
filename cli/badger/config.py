"""Configuration management for Badger CLI."""

import yaml
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class BadgerConfig(BaseSettings):
    """Badger configuration settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="BADGER_",
        case_sensitive=False,
        env_file=".badgerrc",
        env_file_encoding="utf-8",
    )
    
    graphdb_endpoint: Optional[str] = Field(
        default="http://localhost:8080",
        description="Graph database endpoint URL (default: local Dgraph started by 'badger init_graph')"
    )
    
    language: Optional[str] = Field(
        default=None,
        description="Default language to use (auto-detect if not specified)"
    )
    
    verbose: bool = Field(
        default=False,
        description="Enable verbose output"
    )
    
    config_file: Optional[Path] = Field(
        default=None,
        description="Path to configuration file"
    )
    
    # LLM configuration
    llm_provider: str = Field(
        default="ollama",
        description="LLM provider: 'ollama' or 'vllm'"
    )
    
    qwen_endpoint: Optional[str] = Field(
        default=None,
        description="URL for qwen-3-coder-30b model endpoint"
    )
    
    gpt_oss_endpoint: Optional[str] = Field(
        default=None,
        description="URL for gpt-oss-120b model endpoint"
    )
    
    qwen_model: Optional[str] = Field(
        default=None,
        description="Model name for qwen (default: 'qwen3-coder-30b' for Ollama)"
    )
    
    gpt_oss_model: Optional[str] = Field(
        default=None,
        description="Model name for gpt-oss (default: 'gpt-oss-120b' for Ollama)"
    )
    
    api_key: Optional[str] = Field(
        default=None,
        description="Optional API key (not needed for local Ollama/vLLM)"
    )
    
    max_retries: int = Field(
        default=3,
        description="Number of retry attempts for LLM requests"
    )
    
    timeout: int = Field(
        default=300,
        description="Request timeout in seconds for LLM requests"
    )


def get_config_file_path(directory: Path) -> Path:
    """Get the path to the config file in the given directory."""
    return directory / ".badgerrc"


def load_config(config_path: Optional[Path] = None, directory: Optional[Path] = None) -> BadgerConfig:
    """Load configuration from file or environment variables."""
    # Try to find config file
    config_file = None
    if config_path:
        config_file = Path(config_path)
    elif directory:
        config_file = get_config_file_path(directory)
    
    if config_file and config_file.exists():
        return BadgerConfig(_env_file=str(config_file))
    
    # Try default location
    default_config = Path.home() / ".badgerrc"
    if default_config.exists():
        return BadgerConfig(_env_file=str(default_config))
    
    return BadgerConfig()


def save_config(config: BadgerConfig, directory: Path) -> None:
    """Save configuration to file in the given directory."""
    config_file = get_config_file_path(directory)
    
    config_dict = {
        "graphdb_endpoint": config.graphdb_endpoint,
        "language": config.language,
        "verbose": config.verbose,
        "llm_provider": config.llm_provider,
        "qwen_endpoint": config.qwen_endpoint,
        "gpt_oss_endpoint": config.gpt_oss_endpoint,
        "qwen_model": config.qwen_model,
        "gpt_oss_model": config.gpt_oss_model,
        "api_key": config.api_key,
        "max_retries": config.max_retries,
        "timeout": config.timeout,
    }
    
    # Remove None values
    config_dict = {k: v for k, v in config_dict.items() if v is not None}
    
    with open(config_file, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False)

