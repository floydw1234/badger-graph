"""Indexing utilities for codebases."""

import logging
from pathlib import Path
from typing import Optional, Tuple

from ..parsers import PythonParser, CParser, BaseParser
from ..utils import find_source_files, detect_language
from .builder import build_graph, GraphData
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


def index_and_build_graph(
    workspace_path: Path,
    language: Optional[str] = None,
    verbose: bool = False
) -> Tuple[list[ParseResult], GraphData]:
    """Index a workspace and build graph from parse results.
    
    This is a reusable function that extracts the core indexing logic.
    It does not include Rich console output or file saving - those are handled
    by the caller (e.g., main.py's index_directory).
    
    Args:
        workspace_path: Path to workspace/codebase root
        language: Optional language filter (python, c). Auto-detect if not specified.
        verbose: Enable verbose logging
    
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
            if verbose:
                logger.warning(f"Failed to parse {file_path}: {e}")
            else:
                logger.debug(f"Failed to parse {file_path}: {e}")
    
    if not parse_results:
        logger.warning("No files successfully parsed")
        return [], GraphData()
    
    # Build graph
    logger.info("Building graph from parse results")
    graph_data = build_graph(parse_results)
    
    logger.info(f"Graph built: {len(graph_data.functions)} functions, {len(graph_data.classes)} classes")
    if hasattr(graph_data, 'structs') and graph_data.structs:
        logger.info(f"  - {len(graph_data.structs)} structs")
    logger.info(f"  - {len(graph_data.imports)} imports")
    if hasattr(graph_data, 'macros') and graph_data.macros:
        logger.info(f"  - {len(graph_data.macros)} macros")
    if hasattr(graph_data, 'variables') and graph_data.variables:
        logger.info(f"  - {len(graph_data.variables)} variables")
    
    return parse_results, graph_data

