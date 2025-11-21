"""MCP server implementation for Badger code graph database."""

import asyncio
import json
import logging
import sys
from typing import Any, Optional, Sequence

from toon_py import encode
from pathlib import Path
from ..graph.dgraph import DgraphClient
from ..graph.indexer import index_and_build_graph
from ..graph.workspace_metadata import load_workspace_path
from ..graph.hash_cache import HashCache
from ..embeddings.service import EmbeddingService
from .config import MCPServerConfig
from .file_watcher import FileWatcher
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
                description="Find all files that DEPEND ON the target file (reverse dependencies). Returns files that import (Python) or include (C/C++) the target file, NOT files that the target imports/includes. Automatically detects language from file extension (.py for Python, .c/.h for C). Use this before modifying a file to see which files will be affected. Returns transitive dependencies (files that include files that include the target). Example: For 'gossipApi.h', returns files like 'main.c' that include it, not files that 'gossipApi.h' itself includes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to file (Python .py or C/C++ .c/.h) to find reverse dependencies for"
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
    auto_index: bool = False,
    watch: bool = False
) -> None:
    """Run MCP server with stdio transport.
    
    Args:
        dgraph_endpoint: Dgraph endpoint URL (optional, uses config if not provided)
        workspace_path: Path to workspace/codebase root (optional, uses cwd or env var)
        config: MCP server configuration (optional)
        auto_index: If True, automatically index the workspace on startup (default: False)
        watch: If True, watch for file changes and auto-update graph (default: False)
    """
    # Initialize file_watcher to None at function scope to avoid UnboundLocalError
    file_watcher: Optional[FileWatcher] = None
    
    try:
        # Initialize configuration
        if config is None:
            config = MCPServerConfig(
                dgraph_endpoint=dgraph_endpoint,
                workspace_path=workspace_path
            )
        
        # Initialize Dgraph client first (needed for validation checks)
        logger.info(f"Connecting to Dgraph at {config.dgraph_endpoint}")
        dgraph_client = DgraphClient(config.dgraph_endpoint)
        
        # Load workspace path from metadata if watching
        actual_workspace_path = Path(config.workspace_path)
        if watch:
            stored_workspace = load_workspace_path(actual_workspace_path)
            if stored_workspace:
                actual_workspace_path = stored_workspace
                logger.info(f"Using stored workspace path: {actual_workspace_path}")
            else:
                logger.error(f"No indexed workspace found. Cannot start file watcher.")
                logger.error(f"Please run 'badger index' first to index a workspace.")
                logger.error(f"File watching requires an indexed workspace.")
                raise ValueError(
                    "File watching requires an indexed workspace. "
                    "Run 'badger index' first to index your workspace."
                )
            
            # Check if graph has any data
            try:
                # Quick check: query for any files
                check_query = "query { files: queryFile(first: 1) { id } }"
                result = dgraph_client.execute_graphql_query(check_query)
                file_count = len(result.get("files", []))
                
                if file_count == 0:
                    logger.error("Graph database is empty. Cannot start file watcher.")
                    logger.error("Please run 'badger index' first to index your workspace.")
                    raise ValueError(
                        "Graph database is empty. "
                        "Run 'badger index' first to index your workspace before starting file watcher."
                    )
                else:
                    logger.info(f"Graph database contains data ({file_count}+ files found)")
            except Exception as e:
                logger.error(f"Failed to verify graph has data: {e}")
                logger.error("File watcher requires an indexed workspace with data in the graph.")
                raise ValueError(
                    "Cannot verify graph has data. "
                    "Run 'badger index' first to index your workspace."
                ) from e
        
        logger.info(f"Using workspace: {actual_workspace_path}")
        
        # Validate connection
        try:
            # Try a simple query to validate connection
            test_query = "query { __schema { types { name } } }"
            dgraph_client.execute_graphql_query(test_query)
            logger.info("Dgraph connection validated")
        except Exception as e:
            logger.warning(f"Dgraph connection validation failed: {e}")
            logger.warning("Continuing anyway - connection may work at runtime")
        
        # Initialize embedding service
        logger.info("Initializing embedding service")
        embedding_service = EmbeddingService()
        
        # Setup file watcher if requested (will be started after we enter async context)
        if watch:
            async def handle_file_changes(changed_files: set[Path]):
                """Handle file changes by re-indexing workspace."""
                logger.info(f"File changes detected: {len(changed_files)} files")
                
                # Separate deleted files from modified/new files
                deleted_files = [f for f in changed_files if not f.exists()]
                modified_or_new_files = [f for f in changed_files if f.exists()]
                
                # Handle deleted files first
                if deleted_files:
                    logger.info(f"Handling {len(deleted_files)} deleted files")
                    await handle_file_deletions(dgraph_client, deleted_files)
                
                # Re-index entire workspace (fast with tree-sitter)
                # This handles:
                # - New files: will be found and indexed
                # - Modified files: will be re-parsed, hash cache will skip unchanged nodes
                # - Deleted files: won't be found (they don't exist), so won't be in parse results
                try:
                    logger.info("Re-indexing workspace after file changes...")
                    parse_results, graph_data = index_and_build_graph(
                        actual_workspace_path,
                        language=None,  # Auto-detect
                        verbose=False
                    )
                    
                    if parse_results:
                        # Initialize hash cache from user-level location
                        from ..graph.hash_cache import get_user_hash_cache_path
                        cache_file = get_user_hash_cache_path()
                        hash_cache = HashCache(cache_file)
                        
                        # Insert graph (hash cache will filter out unchanged nodes)
                        # For new files: nodes will be inserted (not in cache)
                        # For modified files: only changed nodes will be inserted (hash cache filters unchanged)
                        # For deleted files: already removed from graph, won't be in parse_results
                        if dgraph_client.insert_graph(graph_data, strict_validation=True, hash_cache=hash_cache):
                            logger.info(f"Successfully updated graph: {len(parse_results)} files indexed")
                            if deleted_files:
                                logger.info(f"Deleted files removed from graph: {len(deleted_files)} files")
                            if modified_or_new_files:
                                logger.info(f"Modified/new files processed: {len(modified_or_new_files)} files")
                        else:
                            logger.error("Failed to update graph database")
                    else:
                        # No files found - could mean all files were deleted
                        if deleted_files and not modified_or_new_files:
                            logger.info(f"All changed files were deletions. Graph updated.")
                        else:
                            logger.warning("No files found to index")
                except Exception as e:
                    logger.error(f"Error re-indexing workspace: {e}", exc_info=True)
            
            async def handle_file_deletions(client: DgraphClient, deleted_files: list[Path]):
                """Remove nodes from deleted files from the graph."""
                import pydgraph
                
                for deleted_file in deleted_files:
                    try:
                        # Query for file node and all related nodes
                        file_path_str = str(deleted_file.resolve())
                        escaped_path = file_path_str.replace('"', '\\"')
                        
                        # Use DQL to find file and all nodes it contains
                        dql_query = f"""
                        {{
                            files(func: eq(File.path, "{escaped_path}")) {{
                                uid
                                File.path
                                File.containsFunction {{
                                    uid
                                }}
                                File.containsClass {{
                                    uid
                                }}
                                File.containsStruct {{
                                    uid
                                }}
                                File.containsImport {{
                                    uid
                                }}
                                File.containsMacro {{
                                    uid
                                }}
                                File.containsVariable {{
                                    uid
                                }}
                                File.containsTypedef {{
                                    uid
                                }}
                                File.containsStructFieldAccess {{
                                    uid
                                }}
                            }}
                        }}
                        """
                        
                        txn = client.client.txn()
                        try:
                            result = txn.query(dql_query)
                            data = json.loads(result.json)
                            files = data.get("files", [])
                            
                            if files:
                                file_node = files[0]
                                file_uid = file_node.get("uid")
                                
                                # Collect all UIDs to delete
                                uids_to_delete = [file_uid]
                                
                                # Add all contained nodes
                                for rel_type in ["File.containsFunction", "File.containsClass", "File.containsStruct",
                                                "File.containsImport", "File.containsMacro", "File.containsVariable",
                                                "File.containsTypedef", "File.containsStructFieldAccess"]:
                                    contained = file_node.get(rel_type, [])
                                    for node in contained:
                                        if "uid" in node:
                                            uids_to_delete.append(node["uid"])
                                
                                # Delete all nodes
                                if uids_to_delete:
                                    delete_data = [{"uid": uid} for uid in uids_to_delete]
                                    delete_mutation = txn.create_mutation(del_obj=delete_data)
                                    txn.mutate(delete_mutation)
                                    txn.commit()
                                    logger.info(f"Deleted {len(uids_to_delete)} nodes for file: {file_path_str}")
                            else:
                                logger.debug(f"File not found in graph: {file_path_str}")
                        except Exception as e:
                            logger.warning(f"Failed to delete nodes for {file_path_str}: {e}")
                            txn.discard()
                    except Exception as e:
                        logger.warning(f"Error handling deletion of {deleted_file}: {e}")
            
            # Store callback and workspace for later (will start watcher in async context)
            file_watcher_callback = handle_file_changes
            file_watcher_workspace = actual_workspace_path
        
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
        try:
            async with stdio_server() as (read_stream, write_stream):
                # Start file watcher now that we're in async context
                if watch:
                    event_loop = asyncio.get_running_loop()
                    file_watcher = FileWatcher(
                        file_watcher_workspace,
                        file_watcher_callback,
                        debounce_seconds=10.0,
                        event_loop=event_loop
                    )
                    file_watcher.start()
                    logger.info(f"File watcher started for workspace: {file_watcher_workspace}")
                
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options()
                )
        finally:
            # Stop file watcher on shutdown
            if file_watcher:
                file_watcher.stop()
    
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        if file_watcher:
            file_watcher.stop()
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        if file_watcher:
            file_watcher.stop()
        sys.exit(1)



