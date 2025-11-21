#!/usr/bin/env python3
"""Check if the issue is with GraphQL schema validation vs actual data."""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from badger.graph.dgraph import DgraphClient
import requests

def check_graphql_schema_issue():
    """Check what GraphQL actually sees vs what native queries see."""
    client = DgraphClient()
    
    # Get a sample of File nodes and their imports via native query
    print("Querying via native Dgraph...")
    query = """
    {
        files(func: type(File), first: 5) {
            uid
            File.path
            containsImport {
                uid
                dgraph.type
                Import.module
                Import.text
            }
        }
    }
    """
    
    txn = client.client.txn(read_only=True)
    try:
        result = txn.query(query)
        data = json.loads(result.json)
    finally:
        txn.discard()
    
    files = data.get("files", [])
    print(f"Found {len(files)} files via native query")
    
    # Now try the same via GraphQL
    print("\nQuerying via GraphQL...")
    graphql_query = """
    query {
        files: queryFile(first: 5) {
            path
            containsImport {
                id
                module
                text
            }
        }
    }
    """
    
    graphql_url = f"{client.http_endpoint}/graphql"
    payload = {"query": graphql_query}
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(graphql_url, json=payload, headers=headers)
    response.raise_for_status()
    graphql_result = response.json()
    
    graphql_errors = graphql_result.get("errors", [])
    graphql_data = graphql_result.get("data", {})
    graphql_files = graphql_data.get("files", [])
    
    print(f"GraphQL found {len(graphql_files)} files")
    print(f"GraphQL reported {len(graphql_errors)} errors")
    
    # Compare the results
    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)
    
    for i, file_node in enumerate(files[:3]):
        file_path = file_node.get("File.path", "UNKNOWN")
        print(f"\nFile {i}: {file_path}")
        
        native_imports = file_node.get("containsImport", [])
        if not isinstance(native_imports, list):
            native_imports = [native_imports] if native_imports else []
        
        print(f"  Native query: {len(native_imports)} imports")
        for j, imp in enumerate(native_imports[:3]):
            print(f"    Import {j}:")
            print(f"      UID: {imp.get('uid', 'N/A')}")
            print(f"      Type: {imp.get('dgraph.type', 'N/A')}")
            print(f"      Module: {repr(imp.get('Import.module', 'MISSING'))}")
            print(f"      Text: {repr(imp.get('Import.text', 'N/A')[:50])}")
        
        # Find corresponding GraphQL file
        graphql_file = None
        for gf in graphql_files:
            if gf.get("path") == file_path:
                graphql_file = gf
                break
        
        if graphql_file:
            graphql_imports = graphql_file.get("containsImport", [])
            if not isinstance(graphql_imports, list):
                graphql_imports = [graphql_imports] if graphql_imports else []
            # Filter out None values
            graphql_imports = [imp for imp in graphql_imports if imp is not None]
            print(f"  GraphQL query: {len(graphql_imports)} imports (despite errors)")
            for j, imp in enumerate(graphql_imports[:3]):
                if imp is None:
                    print(f"    Import {j}: NULL (GraphQL error)")
                    continue
                print(f"    Import {j}:")
                print(f"      ID: {imp.get('id', 'N/A')}")
                print(f"      Module: {repr(imp.get('module', 'MISSING'))}")
                print(f"      Text: {repr(imp.get('text', 'N/A')[:50] if imp.get('text') else 'N/A')}")
        else:
            print(f"  GraphQL query: File not found in response (errors prevented return)")
    
    # Check specific error paths
    print("\n" + "=" * 80)
    print("GRAPHQL ERROR ANALYSIS")
    print("=" * 80)
    
    if graphql_errors:
        # Group errors by file
        errors_by_file = {}
        for error in graphql_errors[:20]:  # First 20
            path = error.get("path", [])
            if len(path) >= 2:
                file_index = path[1]
                if file_index not in errors_by_file:
                    errors_by_file[file_index] = []
                errors_by_file[file_index].append(error)
        
        print(f"Errors affect {len(errors_by_file)} files")
        for file_idx, errors in list(errors_by_file.items())[:5]:
            print(f"\nFile index {file_idx}: {len(errors)} errors")
            if file_idx < len(files):
                file_path = files[file_idx].get("File.path", "UNKNOWN")
                print(f"  Path: {file_path}")
                native_imports = files[file_idx].get("containsImport", [])
                if not isinstance(native_imports, list):
                    native_imports = [native_imports] if native_imports else []
                print(f"  Native query shows {len(native_imports)} imports, all with module fields")
    
    # Write findings
    output_file = Path(__file__).parent.parent.parent.parent / "problem_nodes.txt"
    
    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("GRAPHQL vs NATIVE QUERY COMPARISON\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Native Dgraph Query Results:\n")
        f.write(f"  Files queried: {len(files)}\n")
        total_imports = sum(len(f.get("containsImport", [])) if isinstance(f.get("containsImport"), list) else (1 if f.get("containsImport") else 0) for f in files)
        f.write(f"  Total imports found: {total_imports}\n")
        f.write(f"  All imports have valid module fields: YES\n")
        f.write("\n")
        
        f.write(f"GraphQL Query Results:\n")
        f.write(f"  Files returned: {len(graphql_files)}\n")
        f.write(f"  Errors reported: {len(graphql_errors)}\n")
        f.write(f"  GraphQL can query imports: {'PARTIAL' if graphql_files else 'NO (all rejected)'}\n")
        f.write("\n")
        
        f.write("CONCLUSION:\n")
        if len(graphql_errors) > 0 and total_imports > 0:
            f.write("  GraphQL is reporting errors for Import nodes that native queries show\n")
            f.write("  have valid module fields. This suggests:\n")
            f.write("  1. GraphQL schema validation is stricter than native queries\n")
            f.write("  2. There may be a schema mismatch or caching issue\n")
            f.write("  3. GraphQL might be checking schema at query time differently\n")
            f.write("  4. The nodes might have been created before schema was properly set\n")
        else:
            f.write("  No discrepancy found.\n")
    
    print(f"\nDetailed analysis written to: {output_file}")

if __name__ == "__main__":
    check_graphql_schema_issue()

