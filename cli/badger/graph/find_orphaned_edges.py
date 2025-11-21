#!/usr/bin/env python3
"""Find File nodes with containsImport edges pointing to invalid Import nodes."""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from badger.graph.dgraph import DgraphClient

def find_orphaned_edges():
    """Find File nodes with containsImport edges to invalid nodes."""
    client = DgraphClient()
    
    # Query File nodes and get ALL containsImport edges (even if they point to invalid nodes)
    query = """
    {
        files(func: type(File)) {
            uid
            File.path
            containsImport {
                uid
                dgraph.type
                Import.module
                Import.text
                Import.file
            }
        }
    }
    """
    
    print("Querying File nodes and containsImport edges...")
    txn = client.client.txn(read_only=True)
    try:
        result = txn.query(query)
        data = json.loads(result.json)
    finally:
        txn.discard()
    
    files = data.get("files", [])
    print(f"Found {len(files)} File nodes")
    
    # Now query each File node individually to see if there are edges we're missing
    # Also check if there are edges that don't resolve to valid Import nodes
    bad_edges = []
    
    for file_node in files:
        file_path = file_node.get("File.path", "UNKNOWN")
        file_uid = file_node.get("uid", "UNKNOWN")
        imports_list = file_node.get("containsImport", [])
        if not isinstance(imports_list, list):
            imports_list = [imports_list] if imports_list else []
        
        # Check each import
        for imp in imports_list:
            if not isinstance(imp, dict):
                continue
            
            uid = imp.get("uid", "UNKNOWN")
            module = imp.get("Import.module")
            dgraph_type = imp.get("dgraph.type", [])
            if not isinstance(dgraph_type, list):
                dgraph_type = [dgraph_type] if dgraph_type else []
            
            # Check if this is a valid Import node
            is_bad = False
            reason = ""
            
            # Check if it's typed as Import
            if "Import" not in dgraph_type:
                is_bad = True
                reason = f"NOT_TYPED_AS_IMPORT (types: {dgraph_type})"
            # Check if module is missing
            elif "Import.module" not in imp:
                is_bad = True
                reason = "MODULE_KEY_MISSING"
            elif module is None:
                is_bad = True
                reason = "MODULE_VALUE_NONE"
            elif isinstance(module, str) and not module.strip():
                is_bad = True
                reason = "MODULE_EMPTY_STRING"
            
            if is_bad:
                bad_edges.append({
                    "file_path": file_path,
                    "file_uid": file_uid,
                    "import_uid": uid,
                    "reason": reason,
                    "dgraph_type": dgraph_type,
                    "module": module,
                    "text": imp.get("Import.text", "MISSING"),
                    "import_file": imp.get("Import.file", "MISSING")
                })
    
    print(f"Found {len(bad_edges)} problematic Import nodes via File relationships")
    
    # Also check if we can query these specific UIDs directly
    if bad_edges:
        print("\nQuerying problematic UIDs directly...")
        uids_to_check = [edge["import_uid"] for edge in bad_edges[:10]]
        
        uid_query = "{\n"
        for i, uid in enumerate(uids_to_check):
            uid_query += f'    node{i}: node(func: uid({uid})) {{\n'
            uid_query += '        uid\n'
            uid_query += '        dgraph.type\n'
            uid_query += '        Import.module\n'
            uid_query += '        Import.text\n'
            uid_query += '        Import.file\n'
            uid_query += '    }\n'
        uid_query += "}\n"
        
        txn2 = client.client.txn(read_only=True)
        try:
            result2 = txn2.query(uid_query)
            data2 = json.loads(result2.json)
            
            print(f"  Queried {len([k for k in data2.keys() if k.startswith('node')])} nodes directly")
            for i, uid in enumerate(uids_to_check):
                node_key = f"node{i}"
                node_data = data2.get(node_key, [])
                if node_data:
                    node = node_data[0] if isinstance(node_data, list) else node_data
                    print(f"    UID {uid}:")
                    print(f"      Type: {node.get('dgraph.type', 'N/A')}")
                    print(f"      Module: {repr(node.get('Import.module', 'MISSING'))}")
                else:
                    print(f"    UID {uid}: NODE NOT FOUND (orphaned edge?)")
        finally:
            txn2.discard()
    
    # Write to problem_nodes.txt
    output_file = Path(__file__).parent.parent.parent.parent / "problem_nodes.txt"
    
    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("PROBLEMATIC IMPORT NODES - Found via File.containsImport Edges\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Summary:\n")
        f.write(f"  Total File nodes: {len(files)}\n")
        f.write(f"  Problematic Import nodes: {len(bad_edges)}\n")
        f.write("\n")
        
        if len(bad_edges) == 0:
            f.write("No problematic nodes found!\n")
            f.write("\nHowever, GraphQL is still reporting errors. This suggests:\n")
            f.write("  - GraphQL schema validation is stricter\n")
            f.write("  - There may be a schema caching issue\n")
            f.write("  - GraphQL might be checking nodes differently than native queries\n")
        else:
            # Group by reason
            by_reason = {}
            for edge in bad_edges:
                reason = edge["reason"]
                if reason not in by_reason:
                    by_reason[reason] = []
                by_reason[reason].append(edge)
            
            f.write(f"Breakdown by issue type:\n")
            for reason, edges in sorted(by_reason.items()):
                f.write(f"  {reason}: {len(edges)} node(s)\n")
            f.write("\n")
            
            # Group by file
            by_file = {}
            for edge in bad_edges:
                file_path = edge["file_path"]
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(edge)
            
            f.write(f"Breakdown by file:\n")
            for file_path, edges in sorted(by_file.items()):
                f.write(f"  {file_path}: {len(edges)} bad node(s)\n")
            f.write("\n" + "=" * 80 + "\n\n")
            
            # Write detailed information
            for i, edge in enumerate(bad_edges, 1):
                f.write(f"Bad Node #{i}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Issue: {edge['reason']}\n")
                f.write(f"File: {edge['file_path']}\n")
                f.write(f"File UID: {edge['file_uid']}\n")
                f.write(f"Import UID: {edge['import_uid']}\n")
                f.write(f"Dgraph Type: {edge['dgraph_type']}\n")
                f.write(f"Module: {repr(edge['module'])}\n")
                f.write(f"Text: {repr(edge['text'])}\n")
                f.write(f"Import File: {edge['import_file']}\n")
                f.write("\n")
    
    print(f"\nDetailed information written to: {output_file}")
    
    if len(bad_edges) > 0:
        print(f"\n" + "=" * 80)
        print(f"FOUND {len(bad_edges)} PROBLEMATIC NODES!")
        print("=" * 80)
    
    return bad_edges

if __name__ == "__main__":
    find_orphaned_edges()

