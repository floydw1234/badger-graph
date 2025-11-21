"""Workspace metadata management for tracking indexed workspace."""

import json
import logging
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def get_user_badger_dir() -> Path:
    """Get the path to user-level Badger data directory.
    
    Returns:
        Path to ~/.badger/ (or ~/.config/badger/ if XDG_CONFIG_HOME is set)
    """
    # Check for XDG_CONFIG_HOME first (follows XDG Base Directory spec)
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        config_dir = Path(xdg_config) / "badger"
    else:
        # Fall back to ~/.badger
        config_dir = Path.home() / ".badger"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_user_workspace_registry_path() -> Path:
    """Get the path to user-level workspace registry.
    
    Returns:
        Path to ~/.badger/workspace.json (or ~/.config/badger/workspace.json if XDG_CONFIG_HOME is set)
    """
    return get_user_badger_dir() / "workspace.json"


def save_workspace_path(workspace_path: Path) -> None:
    """Save workspace path to user-level registry.
    
    Since only one workspace is active at a time, we store it in a single
    user-level location (~/.badger/workspace.json) that's always accessible
    regardless of where commands are run from.
    
    Args:
        workspace_path: Path to workspace root to save
    """
    resolved_path = workspace_path.resolve()
    metadata = {
        "workspace_path": str(resolved_path),
        "indexed_at": datetime.now().isoformat()
    }
    
    # Save to user-level registry (single source of truth)
    registry_path = get_user_workspace_registry_path()
    try:
        with open(registry_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.debug(f"Saved workspace path to user registry: {registry_path}")
    except Exception as e:
        logger.warning(f"Failed to save workspace metadata to user registry: {e}")


def load_workspace_path(workspace_path: Optional[Path] = None) -> Optional[Path]:
    """Load workspace path from user-level registry.
    
    Since only one workspace is active at a time, we load from a single
    user-level location (~/.badger/workspace.json) that's always accessible
    regardless of where commands are run from.
    
    Args:
        workspace_path: Optional workspace path (for backwards compatibility, not used)
        
    Returns:
        Workspace path if found, None otherwise
    """
    # Load from user-level registry (single source of truth)
    registry_path = get_user_workspace_registry_path()
    if registry_path.exists():
        try:
            with open(registry_path, "r") as f:
                metadata = json.load(f)
                stored_path = Path(metadata.get("workspace_path", ""))
                if stored_path.exists():
                    logger.debug(f"Found workspace in user registry: {stored_path}")
                    return stored_path.resolve()
                else:
                    logger.warning(f"Workspace path in registry does not exist: {stored_path}")
        except Exception as e:
            logger.warning(f"Failed to load workspace metadata from user registry: {e}")
    
    return None


def clear_workspace_metadata(workspace_path: Optional[Path] = None) -> None:
    """Clear workspace metadata from user-level registry.
    
    Since only one workspace is active at a time, we clear the single
    user-level registry file.
    
    Args:
        workspace_path: Optional workspace path (for backwards compatibility, not used)
    """
    # Clear user-level registry (single source of truth)
    registry_path = get_user_workspace_registry_path()
    if registry_path.exists():
        try:
            registry_path.unlink()
            logger.debug(f"Cleared workspace from user registry: {registry_path}")
        except Exception as e:
            logger.warning(f"Failed to clear workspace from user registry: {e}")

