"""Shared fixtures for MCP tests."""

import pytest
from pathlib import Path
from badger.graph.dgraph import DgraphClient
from badger.embeddings.service import EmbeddingService
from badger.mcp.server import create_mcp_server
from badger.graph.builder import build_graph
from badger.parsers.c import CParser
from badger.parsers.python import PythonParser

@pytest.fixture(scope="session")
def dgraph_client():
    """Session-scoped Dgraph client for MCP tests."""
    client = DgraphClient("localhost:8080")
    yield client
    client.close()


@pytest.fixture(scope="session")
def embedding_service():
    """Session-scoped EmbeddingService for MCP tests."""
    return EmbeddingService()


@pytest.fixture(scope="function")
def clean_dgraph(dgraph_client):
    """Clean database before each MCP test."""
    # Query all nodes and delete them
    try:
        query = """
        {
            files: queryFile {
                id
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
            allMacros: queryMacro {
                id
            }
            allVariables: queryVariable {
                id
            }
            allTypedefs: queryTypedef {
                id
            }
            allStructFieldAccesses: queryStructFieldAccess {
                id
            }
        }
        """
        
        result = dgraph_client.execute_graphql_query(query)
        
        # Collect all UIDs to delete
        uids_to_delete = []
        
        # Collect all node UIDs
        for node_type in ["files", "allFunctions", "allClasses", "allImports", 
                          "allMacros", "allVariables", "allTypedefs", "allStructFieldAccesses"]:
            if node_type in result:
                for node in result[node_type]:
                    if node and node.get("id"):
                        uids_to_delete.append(node["id"])
        
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
        import logging
        logging.getLogger(__name__).warning(f"Failed to clean Dgraph: {e}")
    
    yield


@pytest.fixture
def mcp_server(dgraph_client, embedding_service):
    """Create an MCP server instance for testing."""
    return create_mcp_server(dgraph_client, embedding_service)


@pytest.fixture
def test_code_dir():
    """Path to test_code directory."""
    return Path(__file__).parent.parent / "test_code"


@pytest.fixture
def indexed_c_codebase(dgraph_client, clean_dgraph, test_code_dir):
    """Index C test codebase and return graph data."""
    c_dir = test_code_dir / "C"
    if not c_dir.exists():
        pytest.skip(f"Test C codebase not found: {c_dir}")
    
    parser = CParser()
    parse_results = []
    
    # Parse all C files in test_code/C
    for c_file in c_dir.glob("*.c"):
        try:
            parse_result = parser.parse_file(c_file)
            parse_results.append(parse_result)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to parse {c_file}: {e}")
    
    # Also parse header files
    for h_file in c_dir.glob("*.h"):
        try:
            parse_result = parser.parse_file(h_file)
            parse_results.append(parse_result)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to parse {h_file}: {e}")
    
    if not parse_results:
        pytest.skip("No C files parsed successfully")
    
    # Build graph
    graph_data = build_graph(parse_results)
    
    # Insert into Dgraph
    result = dgraph_client.insert_graph(graph_data)
    assert result is True, "Failed to insert graph data"
    
    # Wait for indexing
    import time
    time.sleep(1.5)  # Give Dgraph time to index
    
    return {
        "parse_results": parse_results,
        "graph_data": graph_data,
        "files": [r.file_path for r in parse_results]
    }

