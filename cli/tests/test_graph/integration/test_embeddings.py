"""Integration tests for embedding generation and storage."""

import pytest
import time
from badger.graph.dgraph import DgraphClient


@pytest.mark.integration
class TestEmbeddings:
    """Test embedding generation and storage."""
    
    def test_function_embeddings_generated(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test that function embeddings are generated and stored."""
        # Insert data (this will generate embeddings)
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Small delay to ensure data is committed and indexed
        time.sleep(1.0)
        
        # Query for a function with embedding
        if parsed_python_data["graph_data"].functions:
            func_name = parsed_python_data["graph_data"].functions[0]["name"]
            func_file = parsed_python_data["graph_data"].functions[0]["file"]
            
            query = """
            query($funcName: String!, $funcFile: String!) {
                func: queryFunction(filter: {name: {eq: $funcName}, file: {eq: $funcFile}}) {
                    id
                    name
                    embedding
                }
            }
            """
            
            result = dgraph_client.execute_graphql_query(query, {"funcName": func_name, "funcFile": func_file})
            
            assert "func" in result
            func_list = result["func"] if isinstance(result["func"], list) else [result["func"]]
            assert len(func_list) > 0
            
            func = func_list[0]
            assert "embedding" in func, "Embedding should be present"
            embedding = func["embedding"]
            
            # Verify embedding format
            assert isinstance(embedding, list), "Embedding should be a list"
            assert len(embedding) == 384, f"Embedding should be 384 dimensions, got {len(embedding)}"
            assert all(isinstance(x, (int, float)) for x in embedding), "Embedding should contain numbers"
    
    def test_class_embeddings_generated(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test that class embeddings are generated and stored."""
        # Insert data
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Small delay
        time.sleep(1.0)
        
        # Query for a class with embedding
        if parsed_python_data["graph_data"].classes:
            class_name = parsed_python_data["graph_data"].classes[0]["name"]
            class_file = parsed_python_data["graph_data"].classes[0]["file"]
            
            query = """
            query($className: String!, $classFile: String!) {
                cls: queryClass(filter: {name: {eq: $className}, file: {eq: $classFile}}) {
                    id
                    name
                    embedding
                }
            }
            """
            
            result = dgraph_client.execute_graphql_query(query, {"className": class_name, "classFile": class_file})
            
            assert "cls" in result
            cls_list = result["cls"] if isinstance(result["cls"], list) else [result["cls"]]
            assert len(cls_list) > 0
            
            cls = cls_list[0]
            assert "embedding" in cls, "Embedding should be present"
            embedding = cls["embedding"]
            
            # Verify embedding format
            assert isinstance(embedding, list), "Embedding should be a list"
            assert len(embedding) == 384, f"Embedding should be 384 dimensions, got {len(embedding)}"
            assert all(isinstance(x, (int, float)) for x in embedding), "Embedding should contain numbers"
    
    def test_embeddings_on_update(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test that embeddings are regenerated on update."""
        # Insert data
        dgraph_client.insert_graph(parsed_python_data["graph_data"])
        time.sleep(1.0)
        
        # Get initial embedding
        if parsed_python_data["graph_data"].functions:
            func_name = parsed_python_data["graph_data"].functions[0]["name"]
            func_file = parsed_python_data["graph_data"].functions[0]["file"]
            
            query = """
            query($funcName: String!, $funcFile: String!) {
                func: queryFunction(filter: {name: {eq: $funcName}, file: {eq: $funcFile}}) {
                    id
                    embedding
                }
            }
            """
            
            result1 = dgraph_client.execute_graphql_query(query, {"funcName": func_name, "funcFile": func_file})
            initial_embedding = result1["func"][0]["embedding"]
            
            # Update the file
            dgraph_client.update_graph(
                str(parsed_python_data["file_path"]),
                parsed_python_data["parse_result"]
            )
            time.sleep(1.0)
            
            # Get updated embedding
            result2 = dgraph_client.execute_graphql_query(query, {"funcName": func_name, "funcFile": func_file})
            updated_embedding = result2["func"][0]["embedding"]
            
            # Embedding should still exist (may be same or different)
            assert updated_embedding is not None
            assert len(updated_embedding) == 384

