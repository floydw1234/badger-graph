"""Indexing utilities for codebases."""

import logging
from pathlib import Path
from typing import Optional, Tuple

from ..parsers import PythonParser, CParser, BaseParser
from ..utils import find_source_files, detect_language
from .builder import build_graph, GraphData
from .dgraph import DgraphClient
from .hash_cache import HashCache
from ..parsers.base import ParseResult

logger = logging.getLogger(__name__)


def get_parser(language: str) -> BaseParser:
    """Get parser for specified language."""
    if language == "python":
        return PythonParser()
    elif language == "c":
        return CParser()
    else:
        raise ValueError(f"Unsupported language: {language}")


def index_workspace(
    workspace_path: Path,
    dgraph_client: DgraphClient,
    language: Optional[str] = None,
    auto_index: bool = True,
    strict_validation: bool = True
) -> Tuple[list[ParseResult], GraphData]:
    """Index a workspace and optionally update the graph database.
    
    This is a simplified version of index_directory that doesn't use Rich console
    output, suitable for use in the MCP server.
    
    Args:
        workspace_path: Path to workspace/codebase root
        dgraph_client: Dgraph client instance (with namespace already set)
        language: Optional language filter (python, c). Auto-detect if not specified.
        auto_index: If True, automatically insert into graph database
    
    Returns:
        Tuple of (parse_results, graph_data)
    """
    logger.info(f"Indexing workspace: {workspace_path}")
    
    # Find source files
    source_files = find_source_files(workspace_path, language=language)
    
    if not source_files:
        logger.warning("No source files found")
        return [], GraphData()
    
    logger.info(f"Found {len(source_files)} source files")
    
    # Parse files
    parse_results = []
    parsers: dict[str, BaseParser] = {}
    
    for file_path in source_files:
        # Detect or use specified language
        file_language = language or detect_language(file_path)
        
        if not file_language:
            continue
        
        # Get or create parser
        if file_language not in parsers:
            try:
                parsers[file_language] = get_parser(file_language)
            except Exception as e:
                logger.warning(f"Failed to initialize {file_language} parser: {e}")
                continue
        
        parser = parsers[file_language]
        
        # Parse file
        try:
            result = parser.parse_file(file_path)
            parse_results.append(result)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
    
    if not parse_results:
        logger.warning("No files successfully parsed")
        return [], GraphData()
    
    # Build graph
    logger.info("Building graph from parse results")
    graph_data = build_graph(parse_results)
    
    # Insert into graph database if requested
    if auto_index and dgraph_client:
        logger.info("Inserting graph into database")
        try:
            # Initialize hash cache for incremental indexing
            cache_file = workspace_path / ".badger-index" / "node_hashes.json"
            hash_cache = HashCache(cache_file)
            
            if hash_cache.get_cache_size() > 0:
                logger.info(f"Hash cache: {hash_cache.get_cache_size()} nodes cached")
            
            if dgraph_client.insert_graph(graph_data, strict_validation=strict_validation, hash_cache=hash_cache):
                logger.info(f"Successfully indexed {len(parse_results)} files")
                logger.info(f"  - {len(graph_data.functions)} functions")
                logger.info(f"  - {len(graph_data.classes)} classes")
                logger.info(f"  - {len(graph_data.imports)} imports")
                if hasattr(graph_data, 'macros') and graph_data.macros:
                    logger.info(f"  - {len(graph_data.macros)} macros")
                if hasattr(graph_data, 'variables') and graph_data.variables:
                    logger.info(f"  - {len(graph_data.variables)} variables")
            else:
                logger.error("Failed to insert graph into database")
        except ValueError as e:
            # Validation error in strict mode
            logger.error(f"Validation error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error inserting graph: {e}", exc_info=True)
            raise
    
    return parse_results, graph_data

