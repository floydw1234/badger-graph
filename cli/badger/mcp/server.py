"""MCP server implementation for Badger code graph database."""

import asyncio
import json
import logging
import sys
from typing import Any, Optional, Sequence

from ..graph.dgraph import DgraphClient
from ..graph.indexer import index_workspace
from ..embeddings.service import EmbeddingService
from .config import MCPServerConfig
from . import tools

logger = logging.getLogger(__name__)

# Import MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    logger.error("MCP SDK not found. Please install with: pip install mcp>=1.0.0")
    raise


def create_mcp_server(
    dgraph_client: DgraphClient,
    embedding_service: EmbeddingService
) -> Server:
    """Create and configure MCP server with all tools.
    
    Args:
        dgraph_client: Dgraph client instance
        embedding_service: Embedding service instance
    
    Returns:
        Configured MCP server instance
    """
    # Create server instance
    server = Server(name="badger-mcp-server", version="0.1.0")
    
    # Store client and service in server for use in handlers
    server._dgraph_client = dgraph_client
    server._embedding_service = embedding_service
    
    # Register list_tools handler
    @server.list_tools()
    async def list_tools_handler() -> list[Tool]:
        """List all available tools."""
        return [
            Tool(
                name="find_symbol_usages",
                description="Find all usages of a symbol. Works for both C and Python codebases. Symbol types: function (both languages), macro (C only), variable (both), struct (C only, stored as Class), typedef (C only). Use this when refactoring to find all places that need updates.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Symbol name (function, macro, variable, struct, typedef)"
                        },
                        "symbol_type": {
                            "type": "string",
                            "enum": ["function", "macro", "variable", "struct", "typedef"],
                            "description": "Type of symbol. Note: macro, struct, and typedef are C-specific."
                        }
                    },
                    "required": ["symbol", "symbol_type"]
                }
            ),
            Tool(
                name="get_include_dependencies",
                description="Get all files that transitively import (Python) or include (C/C++) this file. Automatically detects language from file extension (.py for Python, .c/.h for C). Use this before modifying a file to see impact. Returns the full dependency tree.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to file (Python .py or C/C++ .c/.h)"
                        }
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="find_struct_field_access",
                description="Find all places where a struct field is accessed (C/C++ only). Use this when renaming or removing struct fields. Includes direct access (struct.field), pointer access (struct->field), and casts. Structs are stored as Class nodes in the graph.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "struct_name": {
                            "type": "string",
                            "description": "Name of the struct (C/C++ only)"
                        },
                        "field_name": {
                            "type": "string",
                            "description": "Name of the field"
                        }
                    },
                    "required": ["struct_name", "field_name"]
                }
            ),
            Tool(
                name="get_function_callers",
                description="Find all callers of a function (works for both C and Python). Use this when changing function signatures. include_indirect finds function pointer assignments (C) or callback patterns. Returns direct callers via inverse relationship.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function"
                        },
                        "include_indirect": {
                            "type": "boolean",
                            "description": "Include function pointer assignments (C) or indirect calls",
                            "default": True
                        }
                    },
                    "required": ["function_name"]
                }
            ),
            Tool(
                name="semantic_code_search",
                description="Search for code by semantic meaning using embeddings (works for both C and Python). Use this to find similar code patterns or related functionality. Searches both functions and classes/structs. Example: 'buffer allocation' finds all buffer-related code. Use file_pattern to filter by language (e.g., '*.c' for C, '*.py' for Python).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query"
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "Glob pattern to filter files (e.g., '*.c', '*.py', '*')",
                            "default": "*"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="check_affected_files",
                description="Given a list of changed files, find all files that might be affected (works for both C and Python). Use this before committing to see full impact of changes. Includes transitive dependencies (imports/includes) and call graph relationships (functions called from changed files). Automatically handles language-specific dependency resolution.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "changed_files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of file paths that were changed (can mix C and Python files)"
                        }
                    },
                    "required": ["changed_files"]
                }
            )
        ]
    
    # Store handler function for testing (direct reference to the decorated function)
    # Note: The decorator registers the handler with the server, we also store it for testing
    server._list_tools_handler = list_tools_handler
    
    # Register call_tool handler
    @server.call_tool()
    async def call_tool_handler(
        name: str,
        arguments: dict[str, Any] | None
    ) -> Sequence[TextContent]:
        """Handle tool calls."""
        logger.info(f"Tool called: {name} with arguments: {arguments}")
        
        if arguments is None:
            arguments = {}
        
        try:
            if name == "find_symbol_usages":
                result = await tools.find_symbol_usages(
                    server._dgraph_client,
                    arguments.get("symbol", ""),
                    arguments.get("symbol_type", "")
                )
            elif name == "get_include_dependencies":
                result = await tools.get_include_dependencies(
                    server._dgraph_client,
                    arguments.get("file_path", "")
                )
            elif name == "find_struct_field_access":
                result = await tools.find_struct_field_access(
                    server._dgraph_client,
                    arguments.get("struct_name", ""),
                    arguments.get("field_name", "")
                )
            elif name == "get_function_callers":
                result = await tools.get_function_callers(
                    server._dgraph_client,
                    arguments.get("function_name", ""),
                    arguments.get("include_indirect", True)
                )
            elif name == "semantic_code_search":
                result = await tools.semantic_code_search(
                    server._dgraph_client,
                    server._embedding_service,
                    arguments.get("query", ""),
                    arguments.get("file_pattern", "*"),
                    arguments.get("limit", 10)
                )
            elif name == "check_affected_files":
                result = await tools.check_affected_files(
                    server._dgraph_client,
                    arguments.get("changed_files", [])
                )
            else:
                result = {
                    "error": f"Unknown tool: {name}",
                    "type": "unknown_tool"
                }
            
            # Format result as JSON string
            result_json = json.dumps(result, indent=2)
            return [TextContent(type="text", text=result_json)]
        
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}", exc_info=True)
            error_result = {
                "error": str(e),
                "type": "tool_error"
            }
            return [TextContent(type="text", text=json.dumps(error_result, indent=2))]
    
    # Store call_tool handler for testing (direct reference)
    server._call_tool_handler = call_tool_handler
    
    return server


async def run_mcp_server(
    dgraph_endpoint: Optional[str] = None,
    workspace_path: Optional[str] = None,
    config: Optional[MCPServerConfig] = None,
    auto_index: bool = False
) -> None:
    """Run MCP server with stdio transport.
    
    Args:
        dgraph_endpoint: Dgraph endpoint URL (optional, uses config if not provided)
        workspace_path: Path to workspace/codebase root (optional, uses cwd or env var)
        config: MCP server configuration (optional)
        auto_index: If True, automatically index the workspace on startup (default: False)
    """
    try:
        # Initialize configuration
        if config is None:
            config = MCPServerConfig(
                dgraph_endpoint=dgraph_endpoint,
                workspace_path=workspace_path
            )
        
        # Initialize Dgraph client
        logger.info(f"Connecting to Dgraph at {config.dgraph_endpoint}")
        logger.info(f"Using workspace: {config.workspace_path}")
        dgraph_client = DgraphClient(config.dgraph_endpoint)
        
        # Validate connection
        try:
            # Try a simple query to validate connection
            test_query = "query { __schema { types { name } } }"
            dgraph_client.execute_graphql_query(test_query)
            logger.info("Dgraph connection validated")
        except Exception as e:
            logger.warning(f"Dgraph connection validation failed: {e}")
            logger.warning("Continuing anyway - connection may work at runtime")
        
        # Auto-index workspace if requested
        if auto_index:
            logger.info("Auto-indexing workspace...")
            try:
                parse_results, graph_data = index_workspace(
                    config.workspace_path,
                    dgraph_client,
                    language=None,  # Auto-detect
                    auto_index=True,
                    strict_validation=True  # Default to strict for MCP server
                )
                if parse_results:
                    logger.info(f"Workspace indexed successfully: {len(parse_results)} files")
                else:
                    logger.warning("No files found to index")
            except Exception as e:
                logger.error(f"Failed to auto-index workspace: {e}", exc_info=True)
                logger.warning("Continuing with MCP server startup - you may need to index manually")
        
        # Initialize embedding service
        logger.info("Initializing embedding service")
        embedding_service = EmbeddingService()
        
        # Create server
        logger.info("Creating MCP server")
        server = create_mcp_server(dgraph_client, embedding_service)
        
        # Verify tools are registered by calling list_tools handler
        try:
            if hasattr(server, '_list_tools_handler'):
                tools_list = await server._list_tools_handler()
                logger.info(f"MCP server ready with {len(tools_list)} tools:")
                for tool in tools_list:
                    logger.info(f"  - {tool.name}: {tool.description[:60]}...")
            else:
                logger.warning("list_tools handler not found - tools may not be registered")
        except Exception as e:
            logger.warning(f"Could not verify tools: {e}")
            logger.info("MCP server ready (tools should be available after initialization)")
        
        # Run server with stdio transport
        logger.info("Starting MCP server with stdio transport")
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)



