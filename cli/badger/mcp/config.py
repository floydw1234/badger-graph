"""Configuration for MCP server."""

import os
from pathlib import Path
from typing import Optional
from ..config import load_config, BadgerConfig


class MCPServerConfig:
    """Configuration for MCP server."""
    
    def __init__(
        self,
        dgraph_endpoint: Optional[str] = None,
        workspace_path: Optional[str] = None
    ):
        """Initialize MCP server configuration.
        
        Args:
            dgraph_endpoint: Dgraph endpoint URL. If None, loads from BadgerConfig.
            workspace_path: Path to workspace/codebase root. If None, uses current working directory.
        """
        if dgraph_endpoint:
            self.dgraph_endpoint = dgraph_endpoint
        else:
            # Load from BadgerConfig
            config = load_config()
            # Use config endpoint or default to local
            self.dgraph_endpoint = (config.graphdb_endpoint if config else None) or "http://localhost:8080"
        
        # Determine workspace path
        if workspace_path:
            self.workspace_path = Path(workspace_path).resolve()
        else:
            # Try environment variable first (Cursor may set this)
            workspace_env = os.environ.get("BADGER_WORKSPACE_PATH") or os.environ.get("WORKSPACE_PATH")
            if workspace_env:
                self.workspace_path = Path(workspace_env).resolve()
            else:
                # Fall back to current working directory
                self.workspace_path = Path.cwd()
        

