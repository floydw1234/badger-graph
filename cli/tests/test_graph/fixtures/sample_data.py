"""Test data fixtures for graph tests."""

from pathlib import Path
from badger.graph.builder import GraphData, build_graph
from badger.parsers.python import PythonParser
from badger.parsers.c import CParser


def get_sample_python_file_path() -> Path:
    """Get path to sample Python test file."""
    return Path(__file__).parent.parent.parent / "test_code" / "python" / "sample_app.py"


def get_sample_c_file_path() -> Path:
    """Get path to sample C test file."""
    return Path(__file__).parent.parent.parent / "test_code" / "C" / "service.c"


def parse_python_file(file_path: Path) -> dict:
    """Parse a Python file and return parse result and graph data.
    
    Returns:
        Dictionary with keys: 'parse_result', 'graph_data'
    """
    parser = PythonParser()
    parse_result = parser.parse_file(file_path)
    graph_data = build_graph([parse_result])
    return {
        "parse_result": parse_result,
        "graph_data": graph_data
    }


def parse_c_file(file_path: Path) -> dict:
    """Parse a C file and return parse result and graph data.
    
    Returns:
        Dictionary with keys: 'parse_result', 'graph_data'
    """
    parser = CParser()
    parse_result = parser.parse_file(file_path)
    graph_data = build_graph([parse_result])
    return {
        "parse_result": parse_result,
        "graph_data": graph_data
    }


def create_mock_graph_data() -> GraphData:
    """Create a mock GraphData object for testing.
    
    Returns:
        GraphData instance with sample data
    """
    return GraphData(
        files=[{"path": "test.py", "functions_count": 2, "classes_count": 1}],
        functions=[
            {"name": "test_func", "file": "test.py", "line": 10, "column": 0}
        ],
        classes=[
            {"name": "TestClass", "file": "test.py", "line": 5, "column": 0}
        ],
        imports=[],
        relationships=[]
    )

