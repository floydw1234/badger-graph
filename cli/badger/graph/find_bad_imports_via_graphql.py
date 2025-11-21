#!/usr/bin/env python3
"""Find Import nodes by actually running the GraphQL query that fails."""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from badger.graph.dgraph import DgraphClient

def find_bad_imports_via_graphql():
    """Find bad imports by running the actual GraphQL query that fails."""
    client = DgraphClient()
    
    # This is the exact query that's failing in get_include_dependencies
    query = """
    query {
        files: queryFile(first: 10000) {
            path
            containsImport {
                module
                text
            }
        }
    }
    """
    
    print("Running GraphQL query to find problematic nodes...")
    result = client.execute_graphql_query(query, {})
    
    # The query returns {} when there are errors, but we can check the raw response
    # Let's make a direct HTTP request to see the errors
    import requests
    graphql_url = f"{client.http_endpoint}/graphql"
    payload = {"query": query}
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(graphql_url, json=payload, headers=headers)
    response.raise_for_status()
    full_result = response.json()
    
    errors = full_result.get("errors", [])
    data = full_result.get("data", {})
    
    print(f"GraphQL returned {len(errors)} errors")
    
    # Parse error paths to find which nodes are problematic
    bad_node_paths = []
    for error in errors:
        path = error.get("path", [])
        if len(path) >= 4 and path[0] == "files" and path[2] == "containsImport" and path[3] == "module":
            file_index = path[1]
            import_index = path[2] if len(path) > 2 else None
            bad_node_paths.append({
                "file_index": file_index,
                "import_index": import_index,
                "error": error
            })
    
    print(f"Found {len(bad_node_paths)} problematic import references")
    
    # Now try to get the actual data despite errors
    # GraphQL might return partial data
    files = data.get("files", [])
    print(f"Got {len(files)} files in response (despite errors)")
    
    # Find files with problematic imports
    bad_imports = []
    for i, file_node in enumerate(files):
        file_path = file_node.get("path", f"FILE_{i}")
        imports = file_node.get("containsImport", [])
        if not isinstance(imports, list):
            imports = [imports] if imports else []
        
        for j, imp in enumerate(imports):
            if not isinstance(imp, dict):
                continue
            module = imp.get("module")
            if not module or (isinstance(module, str) and not module.strip()):
                bad_imports.append({
                    "file": file_path,
                    "file_index": i,
                    "import_index": j,
                    "import_uid": imp.get("id"),  # GraphQL returns 'id' not 'uid'
                    "module": module,
                    "text": imp.get("text", "MISSING")
                })
    
    # Also try to query the specific UIDs directly using native Dgraph
    print(f"\nQuerying problematic nodes directly via native Dgraph...")
    if bad_imports:
        # Get UIDs from the bad imports
        uids_to_check = [imp["import_uid"] for imp in bad_imports if imp.get("import_uid")]
        
        if uids_to_check:
            # Query these specific nodes
            uid_query = "{\n"
            for i, uid in enumerate(uids_to_check[:10]):  # Limit to first 10 for testing
                uid_query += f'    node{i}: node(func: uid({uid})) {{\n'
                uid_query += '        uid\n'
                uid_query += '        dgraph.type\n'
                uid_query += '        Import.module\n'
                uid_query += '        Import.text\n'
                uid_query += '        Import.file\n'
                uid_query += '        Import.line\n'
                uid_query += '    }\n'
            uid_query += "}\n"
            
            txn = client.client.txn(read_only=True)
            try:
                result = txn.query(uid_query)
                node_data = json.loads(result.json)
                print(f"Queried {len([k for k in node_data.keys() if k.startswith('node')])} nodes directly")
            except Exception as e:
                print(f"Error querying nodes directly: {e}")
            finally:
                txn.discard()
    
    # Write to problem_nodes.txt
    output_file = Path(__file__).parent.parent.parent.parent / "problem_nodes.txt"
    
    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("PROBLEMATIC IMPORT NODES - Found via GraphQL Query\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Summary:\n")
        f.write(f"  GraphQL errors: {len(errors)}\n")
        f.write(f"  Files in response: {len(files)}\n")
        f.write(f"  Bad imports found in response: {len(bad_imports)}\n")
        f.write("\n")
        
        if len(bad_imports) == 0 and len(errors) > 0:
            f.write("NOTE: GraphQL returned errors but no data.\n")
            f.write("This means GraphQL is rejecting the entire query due to missing fields.\n")
            f.write("The problematic nodes exist but GraphQL won't return them.\n\n")
            f.write("Error details:\n")
            for i, error in enumerate(errors[:20], 1):  # Show first 20 errors
                f.write(f"  Error #{i}:\n")
                f.write(f"    Path: {error.get('path', [])}\n")
                f.write(f"    Message: {error.get('message', '')}\n")
                f.write("\n")
        elif len(bad_imports) > 0:
            f.write(f"Breakdown by file:\n")
            by_file = {}
            for imp in bad_imports:
                file_path = imp["file"]
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(imp)
            
            for file_path, nodes in sorted(by_file.items()):
                f.write(f"  {file_path}: {len(nodes)} bad node(s)\n")
            f.write("\n" + "=" * 80 + "\n\n")
            
            for i, imp in enumerate(bad_imports, 1):
                f.write(f"Bad Node #{i}\n")
                f.write("-" * 80 + "\n")
                f.write(f"File: {imp['file']}\n")
                f.write(f"File Index: {imp['file_index']}\n")
                f.write(f"Import Index: {imp['import_index']}\n")
                f.write(f"Import UID: {imp.get('import_uid', 'MISSING')}\n")
                f.write(f"Module: {repr(imp['module'])}\n")
                f.write(f"Text: {repr(imp['text'])}\n")
                f.write("\n")
    
    print(f"\nDetailed information written to: {output_file}")
    
    return bad_imports, errors

if __name__ == "__main__":
    find_bad_imports_via_graphql()

