"""Integration tests for vector similarity search."""

import pytest
import time
from badger.graph.dgraph import DgraphClient
from badger.embeddings.service import EmbeddingService


@pytest.mark.integration
class TestVectorSimilaritySearch:
    """Test vector similarity search functionality."""
    
    def test_function_similarity_search(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test finding similar functions using vector search."""
        # Insert data
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Wait for indexing
        time.sleep(1.0)
        
        # Find a function with signature/docstring for better similarity matching
        ref_func_data = None
        for func in parsed_python_data["graph_data"].functions:
            if func.get("signature") or func.get("docstring"):
                ref_func_data = func
                break
        
        if ref_func_data:
            ref_func_name = ref_func_data["name"]
            ref_func_file = ref_func_data["file"]
            
            # Query for the reference function with embedding
            query_ref = """
            query($refFuncName: String!, $refFuncFile: String!) {
                ref: queryFunction(filter: {name: {eq: $refFuncName}, file: {eq: $refFuncFile}}) {
                    id
                    name
                    embedding
                }
            }
            """
            
            result = dgraph_client.execute_graphql_query(query_ref, {"refFuncName": ref_func_name, "refFuncFile": ref_func_file})
            
            assert "ref" in result
            ref_list = result["ref"] if isinstance(result["ref"], list) else [result["ref"]]
            assert len(ref_list) > 0
            
            ref_func = ref_list[0]
            assert "embedding" in ref_func, "Reference function should have embedding"
            
            # Vector similarity search using Dgraph's auto-generated querySimilarFunctionById
            # Requires 'by' parameter specifying the embedding field
            similar_query = """
            query($refFuncId: ID!) {
                similar: querySimilarFunctionById(id: $refFuncId, by: embedding, topK: 3) {
                    id
                    name
                    file
                    signature
                    docstring
                    vector_distance
                }
            }
            """
            
            similar_result = dgraph_client.execute_graphql_query(similar_query, {"refFuncId": ref_func["id"]})
            
            assert "similar" in similar_result
            similar_funcs = similar_result["similar"] if isinstance(similar_result["similar"], list) else [similar_result["similar"]]
            
            # Should find at least the reference function itself
            assert len(similar_funcs) > 0, "Should find at least one similar function"
            
            # Verify we found the reference function itself
            func_names = [f.get("name", "") for f in similar_funcs]
            assert ref_func_name in func_names, f"Should find reference function {ref_func_name}, got: {func_names}"
    
    def test_class_similarity_search(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test finding similar classes using vector search."""
        # Insert data
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Wait for indexing
        time.sleep(1.0)
        
        # Find a class with methods for better similarity matching
        ref_class_data = None
        for cls in parsed_python_data["graph_data"].classes:
            if cls.get("methods"):
                ref_class_data = cls
                break
        
        if ref_class_data:
            ref_class_name = ref_class_data["name"]
            ref_class_file = ref_class_data["file"]
            
            # Query for the reference class with embedding
            query_ref = """
            query($refClassName: String!, $refClassFile: String!) {
                ref: queryClass(filter: {name: {eq: $refClassName}, file: {eq: $refClassFile}}) {
                    id
                    name
                    embedding
                }
            }
            """
            
            result = dgraph_client.execute_graphql_query(query_ref, {"refClassName": ref_class_name, "refClassFile": ref_class_file})
            
            assert "ref" in result
            ref_list = result["ref"] if isinstance(result["ref"], list) else [result["ref"]]
            assert len(ref_list) > 0
            
            ref_class = ref_list[0]
            assert "embedding" in ref_class, "Reference class should have embedding"
            
            # Vector similarity search using Dgraph's auto-generated querySimilarClassById
            # Requires 'by' parameter specifying the embedding field
            similar_query = """
            query($refClassId: ID!) {
                similar: querySimilarClassById(id: $refClassId, by: embedding, topK: 2) {
                    id
                    name
                    file
                    methods
                    vector_distance
                }
            }
            """
            
            similar_result = dgraph_client.execute_graphql_query(similar_query, {"refClassId": ref_class["id"]})
            
            assert "similar" in similar_result
            similar_classes = similar_result["similar"] if isinstance(similar_result["similar"], list) else [similar_result["similar"]]
            
            # Should find at least the reference class itself
            assert len(similar_classes) > 0, "Should find at least one similar class"
            
            # Verify we found the reference class itself
            class_names = [c.get("name", "") for c in similar_classes]
            assert ref_class_name in class_names, f"Should find reference class {ref_class_name}, got: {class_names}"
    
    def test_vector_search_similar_api_functions(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test high-level vector_search_similar() API for functions."""
        # Insert data
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Wait for indexing
        time.sleep(1.0)
        
        # Generate query embedding
        embedding_service = EmbeddingService()
        query = "function that processes user data"
        query_embedding = embedding_service.generate_query_embedding(query)
        
        # Use high-level API
        results = dgraph_client.vector_search_similar(
            query_embedding=query_embedding,
            top_k=3,
            search_type="functions"
        )
        
        # Verify results structure
        assert "functions" in results
        assert isinstance(results["functions"], list)
        
        # Should find at least some functions if data exists
        if parsed_python_data["graph_data"].functions:
            assert len(results["functions"]) > 0, "Should find at least one similar function"
            
            # Verify result structure
            for func in results["functions"]:
                assert "name" in func
                assert "file" in func
                assert "vector_distance" in func
                assert isinstance(func["vector_distance"], (int, float))
                assert func["vector_distance"] >= 0.0  # Distance should be non-negative
    
    def test_vector_search_similar_api_classes(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test high-level vector_search_similar() API for classes."""
        # Insert data
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Wait for indexing
        time.sleep(1.0)
        
        # Generate query embedding
        embedding_service = EmbeddingService()
        query = "class that handles user management"
        query_embedding = embedding_service.generate_query_embedding(query)
        
        # Use high-level API
        results = dgraph_client.vector_search_similar(
            query_embedding=query_embedding,
            top_k=2,
            search_type="classes"
        )
        
        # Verify results structure
        assert "classes" in results
        assert isinstance(results["classes"], list)
        
        # Should find at least some classes if data exists
        if parsed_python_data["graph_data"].classes:
            assert len(results["classes"]) > 0, "Should find at least one similar class"
            
            # Verify result structure
            for cls in results["classes"]:
                assert "name" in cls
                assert "file" in cls
                assert "vector_distance" in cls
                assert isinstance(cls["vector_distance"], (int, float))
                assert cls["vector_distance"] >= 0.0
    
    def test_vector_search_similar_api_both(self, dgraph_client, clean_dgraph, parsed_python_data):
        """Test high-level vector_search_similar() API for both functions and classes."""
        # Insert data
        result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
        assert result is True
        
        # Wait for indexing
        time.sleep(1.0)
        
        # Generate query embedding
        embedding_service = EmbeddingService()
        query = "code that processes data"
        query_embedding = embedding_service.generate_query_embedding(query)
        
        # Use high-level API with both types
        results = dgraph_client.vector_search_similar(
            query_embedding=query_embedding,
            top_k=3,
            search_type="both"
        )
        
        # Verify results structure
        assert "functions" in results
        assert "classes" in results
        assert isinstance(results["functions"], list)
        assert isinstance(results["classes"], list)
        
        # Results should be limited to top_k
        assert len(results["functions"]) <= 3
        assert len(results["classes"]) <= 3
    
    def test_vector_search_similar_api_invalid_embedding(self, dgraph_client, clean_dgraph):
        """Test vector_search_similar() with invalid embedding."""
        # Test with empty embedding
        results = dgraph_client.vector_search_similar(
            query_embedding=[],
            top_k=5
        )
        assert results == {"functions": [], "classes": []}
        
        # Test with wrong dimension
        results = dgraph_client.vector_search_similar(
            query_embedding=[1.0, 2.0, 3.0],  # Wrong dimension
            top_k=5
        )
        assert results == {"functions": [], "classes": []}

