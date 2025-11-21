#!/usr/bin/env python3
"""Extract problematic node UIDs from GraphQL error paths and query them directly."""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from badger.graph.dgraph import DgraphClient
import requests

def find_from_graphql_errors():
    """Run GraphQL query, extract error paths, then query those specific nodes."""
    client = DgraphClient()
    
    # Run the exact GraphQL query that fails
    query = """
    query {
        files: queryFile(first: 10000) {
            id
            path
            containsImport {
                id
                module
                text
            }
        }
    }
    """
    
    print("Running GraphQL query to get error details...")
    graphql_url = f"{client.http_endpoint}/graphql"
    payload = {"query": query}
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(graphql_url, json=payload, headers=headers)
    response.raise_for_status()
    result = response.json()
    
    errors = result.get("errors", [])
    data = result.get("data", {})
    files = data.get("files", [])
    
    print(f"GraphQL returned {len(errors)} errors and {len(files)} files")
    
    # Extract file IDs and import IDs from errors
    file_ids = set()
    import_ids = set()
    
    for error in errors:
        path = error.get("path", [])
        if len(path) >= 2 and path[0] == "files":
            file_idx = path[1]
            if file_idx < len(files):
                file_node = files[file_idx]
                file_id = file_node.get("id")
                if file_id:
                    file_ids.add(file_id)
                
                # Get import ID if available
                if len(path) >= 4 and path[2] == "containsImport":
                    import_idx = path[3] if isinstance(path[3], int) else None
                    if import_idx is not None:
                        imports = file_node.get("containsImport", [])
                        if isinstance(imports, list) and import_idx < len(imports):
                            imp = imports[import_idx]
                            if imp and isinstance(imp, dict):
                                imp_id = imp.get("id")
                                if imp_id:
                                    import_ids.add(imp_id)
    
    print(f"Found {len(file_ids)} file IDs and {len(import_ids)} import IDs from errors")
    
    # Query these specific Import nodes directly
    bad_nodes = []
    
    if import_ids:
        print(f"\nQuerying {len(import_ids)} problematic Import nodes directly...")
        # Query in batches
        import_id_list = list(import_ids)
        batch_size = 10
        
        for batch_start in range(0, min(len(import_id_list), 50), batch_size):  # Limit to first 50
            batch = import_id_list[batch_start:batch_start + batch_size]
            
            uid_query = "{\n"
            for i, imp_id in enumerate(batch):
                # Convert GraphQL ID to Dgraph UID format if needed
                # GraphQL IDs are usually hex strings like "0x1234"
                uid = imp_id
                if isinstance(imp_id, str) and imp_id.startswith("0x"):
                    uid = imp_id
                elif isinstance(imp_id, str) and imp_id.isdigit():
                    uid = f"0x{imp_id}"
                
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
                
                for i, imp_id in enumerate(batch):
                    node_key = f"node{i}"
                    nodes = node_data.get(node_key, [])
                    if nodes:
                        node = nodes[0] if isinstance(nodes, list) else nodes
                        module = node.get("Import.module")
                        
                        # Check if module is missing/invalid
                        is_bad = False
                        reason = ""
                        if "Import.module" not in node:
                            is_bad = True
                            reason = "KEY_MISSING"
                        elif module is None:
                            is_bad = True
                            reason = "VALUE_NONE"
                        elif isinstance(module, str) and not module.strip():
                            is_bad = True
                            reason = "EMPTY_STRING"
                        
                        if is_bad:
                            bad_nodes.append({
                                "import_id": imp_id,
                                "uid": node.get("uid"),
                                "reason": reason,
                                "dgraph_type": node.get("dgraph.type", []),
                                "module": module,
                                "text": node.get("Import.text", "MISSING"),
                                "file": node.get("Import.file", "MISSING"),
                                "line": node.get("Import.line", "MISSING")
                            })
                        else:
                            # Node has module, but GraphQL still errored - interesting!
                            bad_nodes.append({
                                "import_id": imp_id,
                                "uid": node.get("uid"),
                                "reason": "GRAPHQL_ERROR_BUT_HAS_MODULE",
                                "dgraph_type": node.get("dgraph.type", []),
                                "module": module,
                                "text": node.get("Import.text", "MISSING"),
                                "file": node.get("Import.file", "MISSING"),
                                "line": node.get("Import.line", "MISSING")
                            })
                    else:
                        # Node not found - orphaned edge?
                        bad_nodes.append({
                            "import_id": imp_id,
                            "uid": "NOT_FOUND",
                            "reason": "ORPHANED_EDGE",
                            "dgraph_type": [],
                            "module": None,
                            "text": "N/A",
                            "file": "N/A",
                            "line": "N/A"
                        })
            finally:
                txn.discard()
    
    # Also try to get import IDs from the files that were returned
    print(f"\nExtracting import IDs from GraphQL response...")
    for file_node in files:
        imports = file_node.get("containsImport", [])
        if not isinstance(imports, list):
            imports = [imports] if imports else []
        
        for imp in imports:
            if imp and isinstance(imp, dict):
                imp_id = imp.get("id")
                if imp_id and imp_id not in import_ids:
                    import_ids.add(imp_id)
    
    print(f"Total unique import IDs found: {len(import_ids)}")
    print(f"Problematic nodes identified: {len(bad_nodes)}")
    
    # Write to problem_nodes.txt
    output_file = Path(__file__).parent.parent.parent.parent / "problem_nodes.txt"
    
    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("PROBLEMATIC IMPORT NODES - Extracted from GraphQL Errors\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Summary:\n")
        f.write(f"  GraphQL errors: {len(errors)}\n")
        f.write(f"  Files in response: {len(files)}\n")
        f.write(f"  Import IDs extracted: {len(import_ids)}\n")
        f.write(f"  Problematic nodes found: {len(bad_nodes)}\n")
        f.write("\n")
        
        if len(bad_nodes) == 0:
            f.write("Could not extract specific node information from GraphQL errors.\n")
            f.write("GraphQL may be rejecting nodes before returning their IDs.\n")
        else:
            # Group by reason
            by_reason = {}
            for node in bad_nodes:
                reason = node["reason"]
                if reason not in by_reason:
                    by_reason[reason] = []
                by_reason[reason].append(node)
            
            f.write(f"Breakdown by issue type:\n")
            for reason, nodes in sorted(by_reason.items()):
                f.write(f"  {reason}: {len(nodes)} node(s)\n")
            f.write("\n" + "=" * 80 + "\n\n")
            
            # Write detailed information
            for i, node in enumerate(bad_nodes, 1):
                f.write(f"Bad Node #{i}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Issue: {node['reason']}\n")
                f.write(f"GraphQL ID: {node['import_id']}\n")
                f.write(f"Dgraph UID: {node['uid']}\n")
                f.write(f"Dgraph Type: {node['dgraph_type']}\n")
                f.write(f"Module: {repr(node['module'])}\n")
                f.write(f"Text: {repr(node['text'])}\n")
                f.write(f"File: {node['file']}\n")
                f.write(f"Line: {node['line']}\n")
                f.write("\n")
    
    print(f"\nDetailed information written to: {output_file}")
    
    return bad_nodes

if __name__ == "__main__":
    find_from_graphql_errors()

