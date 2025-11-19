"""Shared fixtures for test_graph tests."""

import pytest
from pathlib import Path
from badger.graph.dgraph import DgraphClient
from badger.graph.builder import build_graph
from badger.parsers.python import PythonParser
from badger.parsers.c import CParser

@pytest.fixture(scope="session")
def dgraph_client():
    """Session-scoped Dgraph client for all tests.
    
    This fixture creates a DgraphClient instance that is shared across
    all tests in the session. It's closed after all tests complete.
    """
    client = DgraphClient("localhost:8080")
    yield client
    client.close()


@pytest.fixture(scope="function")
def clean_dgraph(dgraph_client):
    """Clean database before each integration test.
    
    This fixture deletes all nodes from Dgraph before each test,
    ensuring tests start with a clean state. It runs before each
    test function that uses it.
    """
    # Query all nodes and delete them
    try:
        # Get all nodes of each type (including orphaned nodes)
        query = """
        {
            files: queryFile {
                id
                containsFunction {
                    id
                }
                containsClass {
                    id
                }
                containsImport {
                    id
                }
            }
            allFunctions: queryFunction {
                id
            }
            allClasses: queryClass {
                id
            }
            allImports: queryImport {
                id
            }
        }
        """
        
        result = dgraph_client.execute_graphql_query(query)
        
        # Collect all UIDs to delete
        uids_to_delete = []
        
        # Collect file UIDs and their children
        if "files" in result:
            for file_node in result["files"]:
                file_id = file_node.get("id")
                if file_id:
                    uids_to_delete.append(file_id)
                
                # Collect function UIDs
                if "containsFunction" in file_node:
                    for func in file_node["containsFunction"]:
                        if func and func.get("id"):
                            uids_to_delete.append(func["id"])
                
                # Collect class UIDs
                if "containsClass" in file_node:
                    for cls in file_node["containsClass"]:
                        if cls and cls.get("id"):
                            uids_to_delete.append(cls["id"])
                
                # Collect import UIDs
                if "containsImport" in file_node:
                    for imp in file_node["containsImport"]:
                        if imp and imp.get("id"):
                            uids_to_delete.append(imp["id"])
        
        # Also collect any orphaned nodes (not connected to files)
        if "allFunctions" in result:
            for func in result["allFunctions"]:
                if func and func.get("id") and func["id"] not in uids_to_delete:
                    uids_to_delete.append(func["id"])
        
        if "allClasses" in result:
            for cls in result["allClasses"]:
                if cls and cls.get("id") and cls["id"] not in uids_to_delete:
                    uids_to_delete.append(cls["id"])
        
        if "allImports" in result:
            for imp in result["allImports"]:
                if imp and imp.get("id") and imp["id"] not in uids_to_delete:
                    uids_to_delete.append(imp["id"])
        
        # Delete all nodes
        if uids_to_delete:
            txn = dgraph_client.client.txn()
            try:
                delete_data = [{"uid": uid} for uid in uids_to_delete]
                delete_mutation = txn.create_mutation(del_obj=delete_data)
                txn.mutate(delete_mutation)
                txn.commit()
            finally:
                txn.discard()
    except Exception as e:
        # If cleanup fails, log but don't fail the test
        # (database might be empty or not accessible)
        import logging
        logging.getLogger(__name__).warning(f"Failed to clean Dgraph: {e}")
    
    yield
    
    # Optional: cleanup after test (currently disabled to allow debugging)
    # Uncomment if you want tests to clean up after themselves
    # try:
    #     # Same cleanup logic as above
    #     pass
    # except Exception:
    #     pass


@pytest.fixture
def test_code_dir():
    """Path to test_code directory."""
    return Path(__file__).parent.parent / "test_code"


@pytest.fixture
def sample_python_file(test_code_dir):
    """Path to sample Python test file."""
    file_path = test_code_dir / "python" / "sample_app.py"
    if not file_path.exists():
        pytest.skip(f"Test file not found: {file_path}")
    return file_path


@pytest.fixture
def sample_c_file(test_code_dir):
    """Path to sample C test file."""
    file_path = test_code_dir / "C" / "service.c"
    if not file_path.exists():
        pytest.skip(f"Test file not found: {file_path}")
    return file_path


@pytest.fixture
def python_parser():
    """Python parser instance."""
    return PythonParser()


@pytest.fixture
def c_parser():
    """C parser instance."""
    return CParser()


@pytest.fixture
def parsed_python_data(sample_python_file, python_parser):
    """Pre-parsed Python file data."""
    parse_result = python_parser.parse_file(sample_python_file)
    graph_data = build_graph([parse_result])
    return {
        "file_path": sample_python_file,
        "parse_result": parse_result,
        "graph_data": graph_data
    }


@pytest.fixture
def parsed_c_data(sample_c_file, c_parser):
    """Pre-parsed C file data."""
    parse_result = c_parser.parse_file(sample_c_file)
    graph_data = build_graph([parse_result])
    return {
        "file_path": sample_c_file,
        "parse_result": parse_result,
        "graph_data": graph_data
    }

