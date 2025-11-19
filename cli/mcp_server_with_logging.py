#!/usr/bin/env python3
"""MCP server with logging - Main entry point for Badger MCP Server."""

import sys
import logging
import asyncio
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Add cli to path
cli_dir = Path(__file__).parent
sys.path.insert(0, str(cli_dir))

# Set up file logging first (before importing anything that might log)
log_file = cli_dir / "mcp_server.log"
try:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Get root logger and add file handler
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)
except Exception as e:
    print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)

# Now import and run the server
from badger.mcp.server import run_mcp_server

def main():
    """Main entry point for MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Badger MCP Server")
    parser.add_argument(
        "--graphdb-endpoint",
        type=str,
        default=None,
        help="Graph database endpoint URL (default: from BADGER_GRAPHDB_ENDPOINT env or config)"
    )
    parser.add_argument(
        "--workspace", "-w",
        type=str,
        default=None,
        help="Path to workspace/codebase root (default: current directory or BADGER_WORKSPACE_PATH env var)"
    )
    parser.add_argument(
        "--auto-index",
        action="store_true",
        help="Enable automatic indexing on startup"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set up console logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add console handler to root logger (file handler already added above)
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(log_level)
    
    print(f"MCP server logs also written to: {log_file}", file=sys.stderr)
    
    # Run server
    try:
        asyncio.run(run_mcp_server(
            dgraph_endpoint=args.graphdb_endpoint,
            workspace_path=args.workspace,
            auto_index=args.auto_index
        ))
    except KeyboardInterrupt:
        logging.info("Server shutdown requested")
    except Exception as e:
        logging.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

