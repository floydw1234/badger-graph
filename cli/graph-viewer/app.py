"""Flask app for visualizing Dgraph code graph with Cytoscape.js."""

import json
import logging
from pathlib import Path
from flask import Flask, render_template, jsonify, request
import sys

# Add parent directory to path to import badger modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from badger.graph.dgraph import DgraphClient
from badger.config import load_config

app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

logger = logging.getLogger(__name__)

# Global Dgraph client
dgraph_client = None


def get_dgraph_client():
    """Get or create Dgraph client."""
    global dgraph_client
    if dgraph_client is None:
        # Try to load config from current directory or parent
        config = load_config(directory=Path.cwd())
        endpoint = config.graphdb_endpoint or "http://localhost:8080"
        dgraph_client = DgraphClient(endpoint=endpoint)
    return dgraph_client


@app.route('/')
def index():
    """Render the main graph visualization page."""
    return render_template('index.html')


@app.route('/voyager')
def voyager():
    """Render the GraphQL Voyager visualization page."""
    client = get_dgraph_client()
    graphql_endpoint = f"{client.http_endpoint}/graphql"
    return render_template('voyager.html', graphql_endpoint=graphql_endpoint)


@app.route('/explorer')
def explorer():
    """Render the GraphiQL explorer page for querying live data."""
    client = get_dgraph_client()
    graphql_endpoint = f"{client.http_endpoint}/graphql"
    return render_template('graphiql.html', graphql_endpoint=graphql_endpoint)


@app.route('/api/graph')
def get_graph():
    """Get full graph data from Dgraph."""
    try:
        client = get_dgraph_client()
        
        # Query all nodes and relationships using GraphQL
        # Note: We filter out nodes with missing required fields in Python
        # because Dgraph may have created empty placeholder nodes from relationship references
        query = """
        {
            files: queryFile {
                id
                path
                functionsCount
                classesCount
                importsCount
                containsFunction {
                    id
                    name
                    file
                    line
                    column
                    signature
                    callsFunction {
                        id
                        name
                        file
                    }
                }
                containsClass {
                    id
                    name
                    file
                    line
                    column
                    methods
                    containsMethod {
                        id
                        name
                        file
                        line
                        signature
                    }
                    inheritsClass {
                        id
                        name
                        file
                    }
                }
                containsStruct {
                    id
                    name
                    file
                    line
                    column
                    fields
                }
                containsImport {
                    id
                    module
                    file
                    line
                    text
                }
            }
        }
        """
        
        try:
            result = client.execute_graphql_query(query)
        except Exception as query_ex:
            logger.error(f"GraphQL query exception: {query_ex}")
            # If query fails due to missing required fields, try to handle gracefully
            # by catching the specific error and returning a helpful message
            error_msg = str(query_ex)
            if "Non-nullable field" in error_msg or "was not present" in error_msg:
                logger.warning("Query failed due to nodes with missing required fields. "
                             "These are likely empty placeholder nodes created by relationship references. "
                             "Try running 'badger clear' and re-indexing.")
                return jsonify({
                    "elements": [], 
                    "error": "Query failed due to nodes with missing required fields. "
                            "This can happen if empty placeholder nodes exist in the database. "
                            "Try: 'badger clear' then 'badger index' to clean up and re-index."
                }), 200
            return jsonify({"elements": [], "error": "Query failed. Some File nodes may be missing required fields. Try re-indexing."}), 200
        
        # If query failed or returned empty, return empty graph with helpful message
        if not result or "files" not in result:
            logger.warning("GraphQL query returned no files or failed.")
            logger.warning("This may indicate some File nodes are missing the 'path' field.")
            logger.warning("Try: badger clear (to remove old data), then badger index (to re-index)")
            return jsonify({"elements": [], "error": "No files found. Try clearing and re-indexing: 'badger clear' then 'badger index'"})
        
        # Convert to Cytoscape.js format
        elements = []
        node_ids = set()
        
        # Process files
        if "files" in result:
            for file_node in result["files"]:
                file_uid = file_node.get("id")
                file_path = file_node.get("path", "")
                
                # Skip files without path (shouldn't happen with filter, but be safe)
                if not file_path:
                    logger.warning(f"Skipping file node {file_uid} without path field")
                    continue
                
                if file_uid and file_uid not in node_ids:
                    elements.append({
                        "data": {
                            "id": file_uid,
                            "label": Path(file_path).name if file_path else "File",
                            "type": "file",
                            "path": file_path,
                            "functions_count": file_node.get("functionsCount", 0),
                            "classes_count": file_node.get("classesCount", 0),
                            "structs_count": file_node.get("structsCount", 0),
                        }
                    })
                    node_ids.add(file_uid)
                
                # Process functions in file
                if "containsFunction" in file_node:
                    for func in file_node["containsFunction"]:
                        if not func:
                            continue
                        func_uid = func.get("id")
                        func_name = func.get("name", "")
                        
                        # Skip functions with missing required fields (empty placeholder nodes)
                        if not func_name or not func_name.strip():
                            logger.debug(f"Skipping function {func_uid} with empty name")
                            continue
                        
                        if func_uid and func_uid not in node_ids:
                            elements.append({
                                "data": {
                                    "id": func_uid,
                                    "label": func_name or "Function",
                                    "type": "function",
                                    "name": func_name,
                                    "file": func.get("file", ""),
                                    "line": func.get("line", 0),
                                    "signature": func.get("signature", ""),
                                }
                            })
                            node_ids.add(func_uid)
                        
                        # Add edge from file to function
                        if file_uid and func_uid:
                            edge_id = f"{file_uid}-{func_uid}"
                            if edge_id not in node_ids:
                                elements.append({
                                    "data": {
                                        "id": edge_id,
                                        "source": file_uid,
                                        "target": func_uid,
                                        "type": "contains"
                                    }
                                })
                                node_ids.add(edge_id)
                        
                        # Process function calls
                        if "callsFunction" in func:
                            for callee in func["callsFunction"]:
                                if not callee:
                                    continue
                                callee_uid = callee.get("id")
                                callee_name = callee.get("name", "")
                                
                                # Skip callees with missing required fields
                                if not callee_name or not callee_name.strip():
                                    logger.debug(f"Skipping callee {callee_uid} with empty name")
                                    continue
                                
                                if callee_uid and callee_uid not in node_ids:
                                    # Add callee node if not already added
                                    elements.append({
                                        "data": {
                                            "id": callee_uid,
                                            "label": callee.get("name", "Function"),
                                            "type": "function",
                                            "name": callee.get("name", ""),
                                            "file": callee.get("file", ""),
                                            "line": callee.get("line", 0),
                                        }
                                    })
                                    node_ids.add(callee_uid)
                                
                                # Add call edge
                                if func_uid and callee_uid:
                                    edge_id = f"{func_uid}-calls-{callee_uid}"
                                    if edge_id not in node_ids:
                                        elements.append({
                                            "data": {
                                                "id": edge_id,
                                                "source": func_uid,
                                                "target": callee_uid,
                                                "type": "calls"
                                            }
                                        })
                                        node_ids.add(edge_id)
                
                # Process structs in file
                if "containsStruct" in file_node:
                    for struct in file_node["containsStruct"]:
                        if not struct:
                            continue
                        struct_uid = struct.get("id")
                        struct_name = struct.get("name", "")
                        
                        # Skip structs with missing required fields
                        if not struct_name or not struct_name.strip():
                            logger.debug(f"Skipping struct {struct_uid} with empty name")
                            continue
                        
                        if struct_uid and struct_uid not in node_ids:
                            elements.append({
                                "data": {
                                    "id": struct_uid,
                                    "label": struct_name or "Struct",
                                    "type": "struct",
                                    "name": struct_name,
                                    "file": struct.get("file", ""),
                                    "line": struct.get("line", 0),
                                    "fields": struct.get("fields", []),
                                }
                            })
                            node_ids.add(struct_uid)
                        
                        # Add edge from file to struct
                        if file_uid and struct_uid:
                            edge_id = f"{file_uid}-{struct_uid}"
                            if edge_id not in node_ids:
                                elements.append({
                                    "data": {
                                        "id": edge_id,
                                        "source": file_uid,
                                        "target": struct_uid,
                                        "type": "contains"
                                    }
                                })
                                node_ids.add(edge_id)
                
                # Process classes in file
                if "containsClass" in file_node:
                    for cls in file_node["containsClass"]:
                        if not cls:
                            continue
                        cls_uid = cls.get("id")
                        cls_name = cls.get("name", "")
                        
                        # Skip classes with missing required fields
                        if not cls_name or not cls_name.strip():
                            logger.debug(f"Skipping class {cls_uid} with empty name")
                            continue
                        
                        if cls_uid and cls_uid not in node_ids:
                            elements.append({
                                "data": {
                                    "id": cls_uid,
                                    "label": cls_name or "Class",
                                    "type": "class",
                                    "name": cls_name,
                                    "file": cls.get("file", ""),
                                    "line": cls.get("line", 0),
                                    "methods": cls.get("methods", []),
                                }
                            })
                            node_ids.add(cls_uid)
                        
                        # Add edge from file to class
                        if file_uid and cls_uid:
                            edge_id = f"{file_uid}-{cls_uid}"
                            if edge_id not in node_ids:
                                elements.append({
                                    "data": {
                                        "id": edge_id,
                                        "source": file_uid,
                                        "target": cls_uid,
                                        "type": "contains"
                                    }
                                })
                                node_ids.add(edge_id)
                        
                        # Process methods
                        if "containsMethod" in cls:
                            for method in cls["containsMethod"]:
                                if not method:
                                    continue
                                method_uid = method.get("id")
                                method_name = method.get("name", "")
                                
                                # Skip methods with missing required fields
                                if not method_name or not method_name.strip():
                                    logger.debug(f"Skipping method {method_uid} with empty name")
                                    continue
                                
                                if method_uid and method_uid not in node_ids:
                                    # Add method node
                                    elements.append({
                                        "data": {
                                            "id": method_uid,
                                            "label": method.get("name", "Method"),
                                            "type": "function",
                                            "name": method.get("name", ""),
                                            "file": method.get("file", ""),
                                            "line": method.get("line", 0),
                                            "signature": method.get("signature", ""),
                                        }
                                    })
                                    node_ids.add(method_uid)
                                
                                # Add method edge from class to method
                                if cls_uid and method_uid:
                                        edge_id = f"{cls_uid}-method-{method_uid}"
                                        if edge_id not in node_ids:
                                            elements.append({
                                                "data": {
                                                    "id": edge_id,
                                                    "source": cls_uid,
                                                    "target": method_uid,
                                                    "type": "contains"
                                                }
                                            })
                                            node_ids.add(edge_id)
                        
                        # Process inheritance
                        if "inheritsClass" in cls:
                            for base in cls["inheritsClass"]:
                                if not base:
                                    continue
                                base_uid = base.get("id")
                                base_name = base.get("name", "")
                                
                                # Skip base classes with missing required fields
                                if not base_name or not base_name.strip():
                                    logger.debug(f"Skipping base class {base_uid} with empty name")
                                    continue
                                
                                if base_uid and base_uid not in node_ids:
                                    # Add base class node
                                    elements.append({
                                        "data": {
                                            "id": base_uid,
                                            "label": base.get("name", "Class"),
                                            "type": "class",
                                            "name": base.get("name", ""),
                                            "file": base.get("file", ""),
                                        }
                                    })
                                    node_ids.add(base_uid)
                                
                                # Add inheritance edge
                                if cls_uid and base_uid:
                                        edge_id = f"{cls_uid}-inherits-{base_uid}"
                                        if edge_id not in node_ids:
                                            elements.append({
                                                "data": {
                                                    "id": edge_id,
                                                    "source": cls_uid,
                                                    "target": base_uid,
                                                    "type": "inherits"
                                                }
                                            })
                                            node_ids.add(edge_id)
            
            return jsonify({"elements": elements})
            
    except Exception as e:
        logger.error(f"Error fetching graph: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/search')
def search_nodes():
    """Search for nodes by text query."""
    query_text = request.args.get('q', '').strip()
    if not query_text:
        return jsonify({"elements": []})
    
    try:
        client = get_dgraph_client()
        
        # Search in function names and class names using GraphQL text search
        search_query = """
        query($queryText: String!) {
            functions: queryFunction(filter: {name: {alloftext: $queryText}}) {
                id
                name
                file
                line
                signature
                callsFunction {
                    id
                    name
                    file
                }
                containedInFile {
                    id
                    path
                }
            }
            classes: queryClass(filter: {name: {alloftext: $queryText}}) {
                id
                name
                file
                line
                inheritsClass {
                    id
                    name
                    file
                }
                containedInFile {
                    id
                    path
                }
            }
            structs: queryStruct(filter: {name: {alloftext: $queryText}}) {
                id
                name
                file
                line
                fields
                containedInFile {
                    id
                    path
                }
            }
        }
        """
        
        result = client.execute_graphql_query(search_query, {"queryText": query_text})
        
        elements = []
        node_ids = set()
        
        # Add matching functions
        if "functions" in result:
            for func in result["functions"]:
                    func_uid = func.get("id")
                    if func_uid and func_uid not in node_ids:
                        elements.append({
                            "data": {
                                "id": func_uid,
                                "label": func.get("name", ""),
                                "type": "function",
                                "name": func.get("name", ""),
                                "file": func.get("file", ""),
                                "line": func.get("line", 0),
                                "signature": func.get("signature", ""),
                            }
                        })
                        node_ids.add(func_uid)
                    
                    # Add relationships for this function
                    # Add file relationship
                    if "containedInFile" in func and func["containedInFile"]:
                        file_rel = func["containedInFile"][0] if isinstance(func["containedInFile"], list) else func["containedInFile"]
                        file_uid = file_rel.get("id")
                        file_path = file_rel.get("path", "")
                        
                        if file_uid:
                            # Add file node if not exists
                            if file_uid not in node_ids:
                                elements.append({
                                    "data": {
                                        "id": file_uid,
                                        "label": Path(file_path).name if file_path else "File",
                                        "type": "file",
                                        "path": file_path,
                                    }
                                })
                                node_ids.add(file_uid)
                            
                            # Add edge
                            edge_id = f"{file_uid}-{func_uid}"
                            if edge_id not in node_ids:
                                elements.append({
                                    "data": {
                                        "id": edge_id,
                                        "source": file_uid,
                                        "target": func_uid,
                                        "type": "contains"
                                    }
                                })
                                node_ids.add(edge_id)
                    
                    # Add function call relationships
                    if "callsFunction" in func:
                        for callee in func["callsFunction"]:
                            if not callee:
                                continue
                            callee_uid = callee.get("id")
                            
                            if callee_uid:
                                # Add callee node if not exists
                                if callee_uid not in node_ids:
                                    elements.append({
                                        "data": {
                                            "id": callee_uid,
                                            "label": callee.get("name", "Function"),
                                            "type": "function",
                                            "name": callee.get("name", ""),
                                            "file": callee.get("file", ""),
                                            "line": callee.get("line", 0),
                                        }
                                    })
                                    node_ids.add(callee_uid)
                                
                                # Add call edge
                                edge_id = f"{func_uid}-calls-{callee_uid}"
                                if edge_id not in node_ids:
                                    elements.append({
                                        "data": {
                                            "id": edge_id,
                                            "source": func_uid,
                                            "target": callee_uid,
                                            "type": "calls"
                                        }
                                    })
                                    node_ids.add(edge_id)
        
        # Add matching structs
        if "structs" in result:
            for struct in result["structs"]:
                struct_uid = struct.get("id")
                if struct_uid and struct_uid not in node_ids:
                    elements.append({
                        "data": {
                            "id": struct_uid,
                            "label": struct.get("name", ""),
                            "type": "struct",
                            "name": struct.get("name", ""),
                            "file": struct.get("file", ""),
                            "line": struct.get("line", 0),
                            "fields": struct.get("fields", []),
                        }
                    })
                    node_ids.add(struct_uid)
                
                # Add relationships for this struct
                # Add file relationship
                if "containedInFile" in struct and struct["containedInFile"]:
                    file_rel = struct["containedInFile"][0] if isinstance(struct["containedInFile"], list) else struct["containedInFile"]
                    file_uid = file_rel.get("id")
                    file_path = file_rel.get("path", "")
                    
                    if file_uid:
                        # Add file node if not exists
                        if file_uid not in node_ids:
                            elements.append({
                                "data": {
                                    "id": file_uid,
                                    "label": Path(file_path).name if file_path else "File",
                                    "type": "file",
                                    "path": file_path,
                                }
                            })
                            node_ids.add(file_uid)
                        
                        # Add edge
                        edge_id = f"{file_uid}-{struct_uid}"
                        if edge_id not in node_ids:
                            elements.append({
                                "data": {
                                    "id": edge_id,
                                    "source": file_uid,
                                    "target": struct_uid,
                                    "type": "contains"
                                }
                            })
                            node_ids.add(edge_id)
        
        # Add matching classes
        if "classes" in result:
            for cls in result["classes"]:
                    cls_uid = cls.get("id")
                    if cls_uid and cls_uid not in node_ids:
                        elements.append({
                            "data": {
                                "id": cls_uid,
                                "label": cls.get("name", ""),
                                "type": "class",
                                "name": cls.get("name", ""),
                                "file": cls.get("file", ""),
                                "line": cls.get("line", 0),
                            }
                        })
                        node_ids.add(cls_uid)
                    
                    # Add file relationship
                    if "containedInFile" in cls and cls["containedInFile"]:
                        file_rel = cls["containedInFile"][0] if isinstance(cls["containedInFile"], list) else cls["containedInFile"]
                        file_uid = file_rel.get("id")
                        file_path = file_rel.get("path", "")
                        
                        if file_uid:
                            # Add file node if not exists
                            if file_uid not in node_ids:
                                elements.append({
                                    "data": {
                                        "id": file_uid,
                                        "label": Path(file_path).name if file_path else "File",
                                        "type": "file",
                                        "path": file_path,
                                    }
                                })
                                node_ids.add(file_uid)
                            
                            # Add edge
                            edge_id = f"{file_uid}-{cls_uid}"
                            if edge_id not in node_ids:
                                elements.append({
                                    "data": {
                                        "id": edge_id,
                                        "source": file_uid,
                                        "target": cls_uid,
                                        "type": "contains"
                                    }
                                })
                                node_ids.add(edge_id)
                    
                    # Add inheritance relationships
                    if "inheritsClass" in cls:
                        for base in cls["inheritsClass"]:
                            if not base:
                                continue
                            base_uid = base.get("id")
                            
                            if base_uid:
                                # Add base class node if not exists
                                if base_uid not in node_ids:
                                    elements.append({
                                        "data": {
                                            "id": base_uid,
                                            "label": base.get("name", "Class"),
                                            "type": "class",
                                            "name": base.get("name", ""),
                                            "file": base.get("file", ""),
                                        }
                                    })
                                    node_ids.add(base_uid)
                                
                                # Add inheritance edge
                                edge_id = f"{cls_uid}-inherits-{base_uid}"
                                if edge_id not in node_ids:
                                    elements.append({
                                        "data": {
                                            "id": edge_id,
                                            "source": cls_uid,
                                            "target": base_uid,
                                            "type": "inherits"
                                        }
                                    })
                                    node_ids.add(edge_id)
        
        return jsonify({"elements": elements})
            
    except Exception as e:
        logger.error(f"Error searching nodes: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/debug/classes')
def debug_classes():
    """Debug endpoint to check if classes have methods."""
    try:
        client = get_dgraph_client()
        
        query = """
        {
            classes: queryClass(first: 5) {
                id
                name
                file
                methods
                containsMethod {
                    id
                    name
                    file
                    line
                }
            }
        }
        """
        
        result = client.execute_graphql_query(query)
        return jsonify(result)
            
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/node/<node_id>')
def get_node_details(node_id):
    """Get detailed information about a specific node."""
    try:
        client = get_dgraph_client()
        
        # Try to get node by ID - need to query all types since we don't know which type it is
        query = """
        query($nodeId: ID!) {
            file: getFile(id: $nodeId) {
                id
                path
                functionsCount
                classesCount
                importsCount
            }
            function: getFunction(id: $nodeId) {
                id
                name
                file
                line
                column
                signature
                parameters
                returnType
                docstring
                belongsToClass {
                    id
                    name
                }
            }
            class: getClass(id: $nodeId) {
                id
                name
                file
                line
                column
                methods
                baseClasses
                containsMethod {
                    id
                    name
                    line
                }
            }
            import: getImport(id: $nodeId) {
                id
                module
                file
                line
                text
            }
        }
        """
        
        result = client.execute_graphql_query(query, {"nodeId": node_id})
        
        # Return the first non-null result
        if result.get("file"):
            return jsonify(result["file"])
        elif result.get("function"):
            return jsonify(result["function"])
        elif result.get("class"):
            return jsonify(result["class"])
        elif result.get("import"):
            return jsonify(result["import"])
        else:
            return jsonify({"error": "Node not found"}), 404
            
    except Exception as e:
        logger.error(f"Error fetching node details: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    import os
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

