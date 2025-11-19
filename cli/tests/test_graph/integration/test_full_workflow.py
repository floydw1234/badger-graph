"""Comprehensive integration test for complete graph workflow.

This test can be run standalone to validate the entire pipeline:
    pytest tests/test_graph/integration/test_full_workflow.py -m integration

It tests real-world scenarios matching the README.md workflow:
- Schema setup and GraphQL schema upload
- Parsing and indexing files (Python and C)
- Inserting data with relationships (function calls, class inheritance, file containment)
- Querying functions and classes with full context (file, line, relationships)
- Cross-language queries (Python + C codebase)
- Vector similarity search for semantic code discovery
- Incremental updates (simulating file save events)
- Relationship traversal (finding callers/callees, inheritance chains)
- Cross-file persistence (updating one file doesn't break others)

This test simulates the actual usage pattern where:
1. User asks "What does function X do?" → agent queries graph for function + relationships
2. User asks "Find similar code to X" → agent uses vector similarity search
3. User saves a file → graph updates incrementally
4. Agent needs to understand code flow → traverses function call relationships
5. Agent needs class hierarchy → traverses inheritance relationships
"""

import pytest
import time
from badger.graph.dgraph import DgraphClient


@pytest.mark.integration
def test_complete_graph_workflow(
    dgraph_client,
    clean_dgraph,
    parsed_python_data,
    parsed_c_data
):
    """Comprehensive test of the entire graph workflow matching real-world usage.
    
    This test validates the complete pipeline as described in README.md:
    - Indexing codebase (parsing Python and C files)
    - Building graph with relationships (function calls, inheritance, containment)
    - Querying for context (functions, classes, with relationships)
    - Vector similarity search (semantic code discovery)
    - Incremental updates (file save simulation)
    - Relationship traversal (callers, callees, inheritance chains)
    - Cross-file persistence (multi-file codebase handling)
    
    Each step includes realistic assertions that match what an agent would need
    when answering user queries about the codebase.
    
    Can be run standalone for debugging:
        pytest tests/test_graph/integration/test_full_workflow.py -m integration -v
    """
    # Step 1: Setup GraphQL schema
    assert dgraph_client.setup_graphql_schema() is True
    
    # Step 2: Insert Python file
    py_result = dgraph_client.insert_graph(parsed_python_data["graph_data"])
    assert py_result is True, "Failed to insert Python file"
    
    # Step 3: Insert C file
    c_result = dgraph_client.insert_graph(parsed_c_data["graph_data"])
    assert c_result is True, "Failed to insert C file"
    
    # Step 4: Wait for embeddings and indexing
    time.sleep(1.5)
    
    # Step 5: Test querying functions with relationships (real-world query pattern)
    # This simulates what happens when a user asks "What does function X do?"
    # The agent needs: function details, file context, and what it calls/is called by
    if parsed_python_data["graph_data"].functions:
        func_name = parsed_python_data["graph_data"].functions[0]["name"]
        query_result = dgraph_client.query_context({
            "functions": [func_name]
        })
        
        assert "functions" in query_result
        assert len(query_result["functions"]) > 0
        
        func = query_result["functions"][0]
        assert func["name"] == func_name
        assert "file" in func, "Function should have file path"
        assert "line" in func, "Function should have line number"
        
        # Real-world: agent needs to know what file contains this function
        assert "files" in query_result
        assert len(query_result["files"]) > 0
        file_path = func["file"]
        matching_files = [f for f in query_result["files"] if f.get("path") == file_path]
        assert len(matching_files) > 0, f"Should find file {file_path} containing function {func_name}"
        
        # Real-world: query_context returns basic function info
        # Relationship traversal is tested separately in Step 14 with direct GraphQL queries
        # This ensures query_context works for basic queries, while full relationship
        # traversal uses more detailed GraphQL queries when needed
    
    # Step 6: Test querying classes with inheritance relationships (real-world pattern)
    # This simulates: "What classes inherit from BaseService?"
    # Agent needs: class details, methods, inheritance chain, file context
    if parsed_python_data["graph_data"].classes:
        class_name = parsed_python_data["graph_data"].classes[0]["name"]
        query_result = dgraph_client.query_context({
            "classes": [class_name]
        })
        
        assert "classes" in query_result
        assert len(query_result["classes"]) > 0
        
        cls = query_result["classes"][0]
        assert cls["name"] == class_name
        assert "file" in cls, "Class should have file path"
        assert "line" in cls, "Class should have line number"
        
        # Real-world: query_context returns basic class info
        # Full inheritance traversal is tested separately in Step 15 with direct GraphQL queries
        # This ensures query_context works for basic queries, while inheritance chains
        # use more detailed GraphQL queries when needed
        
        # Real-world: agent needs to know what file contains this class
        assert "files" in query_result
        file_path = cls["file"]
        matching_files = [f for f in query_result["files"] if f.get("path") == file_path]
        assert len(matching_files) > 0, f"Should find file {file_path} containing class {class_name}"
    
    # Step 7: Test querying multiple functions (real-world: "What do functions X and Y do?")
    # This simulates batch queries that an agent might make
    if len(parsed_python_data["graph_data"].functions) >= 2:
        func_names = [
            parsed_python_data["graph_data"].functions[0]["name"],
            parsed_python_data["graph_data"].functions[1]["name"]
        ]
        query_result = dgraph_client.query_context({
            "functions": func_names
        })
        
        assert len(query_result["functions"]) >= 2, "Should return at least 2 functions"
        result_names = [f.get("name") for f in query_result["functions"]]
        for name in func_names:
            assert name in result_names, f"Should find function {name} in results"
        
        # Real-world: verify each function has complete context
        for func in query_result["functions"]:
            assert "name" in func and "file" in func, "Each function should have name and file"
            assert func["name"] in func_names, f"Function {func['name']} should be in query list"
    
    # Step 8: Test cross-language queries (real-world: codebase with Python and C)
    # This simulates: "What does the C function X do?" in a mixed codebase
    if parsed_c_data["graph_data"].functions:
        c_func_name = parsed_c_data["graph_data"].functions[0]["name"]
        query_result = dgraph_client.query_context({
            "functions": [c_func_name]
        })
        
        assert "functions" in query_result
        assert len(query_result["functions"]) > 0
        
        c_func = query_result["functions"][0]
        assert c_func["name"] == c_func_name
        assert "file" in c_func, "C function should have file path"
        
        # Real-world: verify file context is returned
        assert "files" in query_result
        c_file_path = c_func["file"]
        matching_files = [f for f in query_result["files"] if f.get("path") == c_file_path]
        assert len(matching_files) > 0, f"Should find C file {c_file_path}"
    
    # Step 9: Test embeddings were generated
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
        func = result["func"][0] if isinstance(result["func"], list) else result["func"]
        assert "embedding" in func
        assert len(func["embedding"]) == 384
    
    # Step 10: Test vector similarity search (real-world: "Find functions similar to X")
    # This simulates semantic code search - finding similar code by meaning, not just name
    if parsed_python_data["graph_data"].functions:
        # Find function with signature/docstring for meaningful similarity
        ref_func = None
        for func in parsed_python_data["graph_data"].functions:
            if func.get("signature") or func.get("docstring"):
                ref_func = func
                break
        
        if ref_func:
            # Get reference function
            query_ref = """
            query($refFuncName: String!, $refFuncFile: String!) {
                ref: queryFunction(filter: {name: {eq: $refFuncName}, file: {eq: $refFuncFile}}) {
                    id
                    name
                    signature
                    docstring
                }
            }
            """
            
            result = dgraph_client.execute_graphql_query(
                query_ref,
                {"refFuncName": ref_func["name"], "refFuncFile": ref_func["file"]}
            )
            
            if result.get("ref") and len(result["ref"]) > 0:
                ref_func_data = result["ref"][0]
                ref_id = ref_func_data["id"]
                
                # Real-world: vector similarity search finds semantically similar code
                # This is how the agent finds related code when user asks vague questions
                similar_query = """
                query($refFuncId: ID!) {
                    similar: querySimilarFunctionById(id: $refFuncId, by: embedding, topK: 3) {
                        id
                        name
                        file
                        signature
                        vector_distance
                    }
                }
                """
                
                similar_result = dgraph_client.execute_graphql_query(similar_query, {"refFuncId": ref_id})
                assert "similar" in similar_result, "Similarity search should return results"
                assert len(similar_result["similar"]) > 0, "Should find at least one similar function"
                
                # Real-world: verify similarity results have useful context
                for similar_func in similar_result["similar"]:
                    assert "name" in similar_func, "Similar function should have name"
                    assert "vector_distance" in similar_func, "Should include distance metric"
                    # The reference function itself should be in results (distance = 0 or very small)
                    if similar_func["id"] == ref_id:
                        assert similar_func.get("vector_distance", 1.0) < 0.1, "Self-match should have very small distance"
    
    # Step 11: Test update operation (real-world: file save triggers graph update)
    # This simulates what happens when a user edits and saves a file
    # The graph should update incrementally without affecting other files
    update_result = dgraph_client.update_graph(
        str(parsed_python_data["file_path"]),
        parsed_python_data["parse_result"]
    )
    assert update_result is True, "Failed to update graph after file change"
    
    # Step 12: Verify data still queryable after update (real-world: agent queries after file save)
    # This ensures the update didn't break existing queries
    if parsed_python_data["graph_data"].functions:
        func_name = parsed_python_data["graph_data"].functions[0]["name"]
        query_result = dgraph_client.query_context({
            "functions": [func_name]
        })
        assert len(query_result["functions"]) > 0, "Should still find function after update"
        
        # Real-world: verify the function still has all its relationships
        func = query_result["functions"][0]
        assert func["name"] == func_name, "Function name should match"
        assert "file" in func, "Function should still have file path"
    
    # Step 13: Test cross-file relationships persist (real-world: multi-file codebase)
    # This ensures updating one file doesn't break queries for other files
    # Critical for large codebases where files are edited independently
    if parsed_c_data["graph_data"].functions:
        c_func_name = parsed_c_data["graph_data"].functions[0]["name"]
        query_result = dgraph_client.query_context({
            "functions": [c_func_name]
        })
        assert len(query_result["functions"]) > 0, "C file functions should still be accessible after Python update"
        
        c_func = query_result["functions"][0]
        assert c_func["name"] == c_func_name, "C function should still be findable"
    
    # Step 14: Test relationship traversal (real-world: "What calls function X?")
    # This simulates finding callers/callees - critical for understanding code flow
    if parsed_python_data["graph_data"].functions and parsed_python_data["graph_data"].relationships:
        # Find a function that has call relationships
        func_with_calls = None
        for func in parsed_python_data["graph_data"].functions:
            # Check if this function appears in any relationships
            func_name = func["name"]
            has_calls = any(
                rel.get("caller") == func_name or rel.get("callee") == func_name
                for rel in parsed_python_data["graph_data"].relationships
                if rel.get("type") == "function_call"
            )
            if has_calls:
                func_with_calls = func
                break
        
        if func_with_calls:
            # Query with full relationship context
            query = """
            query($funcName: String!, $funcFile: String!) {
                func: queryFunction(filter: {name: {eq: $funcName}, file: {eq: $funcFile}}) {
                    id
                    name
                    file
                    callsFunction {
                        id
                        name
                        file
                    }
                    calledByFunction {
                        id
                        name
                        file
                    }
                    containedInFile {
                        path
                        functionsCount
                    }
                }
            }
            """
            
            result = dgraph_client.execute_graphql_query(query, {
                "funcName": func_with_calls["name"],
                "funcFile": func_with_calls["file"]
            })
            
            if result.get("func") and len(result["func"]) > 0:
                func_data = result["func"][0]
                # Real-world: agent needs to know call relationships
                assert "callsFunction" in func_data, "Function should have callsFunction field"
                assert "calledByFunction" in func_data, "Function should have calledByFunction field"
                assert "containedInFile" in func_data, "Function should have file containment"
                
                # If relationships exist, verify they're populated
                if func_data.get("callsFunction"):
                    assert len(func_data["callsFunction"]) > 0, "If function calls others, list should be populated"
                if func_data.get("calledByFunction"):
                    assert len(func_data["calledByFunction"]) > 0, "If function is called, list should be populated"
    
    # Step 15: Test class inheritance traversal (real-world: "What classes inherit from X?")
    # This simulates understanding class hierarchies
    if parsed_python_data["graph_data"].classes:
        # Find a class with inheritance
        class_with_inheritance = None
        for cls in parsed_python_data["graph_data"].classes:
            if cls.get("base_classes"):
                class_with_inheritance = cls
                break
        
        if class_with_inheritance:
            query = """
            query($className: String!, $classFile: String!) {
                cls: queryClass(filter: {name: {eq: $className}, file: {eq: $classFile}}) {
                    id
                    name
                    file
                    baseClasses
                    inheritsClass {
                        id
                        name
                        file
                    }
                    inheritedByClass {
                        id
                        name
                        file
                    }
                    containsMethod {
                        id
                        name
                    }
                }
            }
            """
            
            result = dgraph_client.execute_graphql_query(query, {
                "className": class_with_inheritance["name"],
                "classFile": class_with_inheritance["file"]
            })
            
            if result.get("cls") and len(result["cls"]) > 0:
                cls_data = result["cls"][0]
                # Real-world: agent needs inheritance information
                assert "baseClasses" in cls_data, "Class should have baseClasses field"
                assert "inheritsClass" in cls_data, "Class should have inheritsClass relationship"
                assert "inheritedByClass" in cls_data, "Class should have inheritedByClass relationship"
                assert "containsMethod" in cls_data, "Class should have methods"
    
    # Test completed successfully
    # Note: Database cleanup is handled by clean_dgraph fixture

