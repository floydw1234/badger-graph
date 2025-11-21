#!/usr/bin/env python3
"""Comprehensive search for Import nodes - check all possible ways they might be stored."""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from badger.graph.dgraph import DgraphClient

def find_all_imports_comprehensive():
    """Find ALL Import nodes using multiple query methods."""
    client = DgraphClient()
    
    bad_nodes = []
    
    # Method 1: Direct query of Import type
    print("Method 1: Querying Import nodes directly...")
    query1 = """
    {
        imports(func: type(Import)) {
            uid
            dgraph.type
            Import.module
            Import.text
            Import.file
        }
    }
    """
    
    txn1 = client.client.txn(read_only=True)
    try:
        result1 = txn1.query(query1)
        data1 = json.loads(result1.json)
        imports1 = data1.get("imports", [])
        print(f"  Found {len(imports1)} Import nodes")
        
        for imp in imports1:
            module = imp.get("Import.module")
            if not module or (isinstance(module, str) and not module.strip()):
                bad_nodes.append({
                    "method": "direct_query",
                    "uid": imp.get("uid"),
                    "module": module,
                    "text": imp.get("Import.text"),
                    "file": imp.get("Import.file")
                })
    finally:
        txn1.discard()
    
    # Method 2: Query through File relationships
    print("Method 2: Querying through File.containsImport...")
    query2 = """
    {
        files(func: type(File)) {
            File.path
            containsImport {
                uid
                Import.module
                Import.text
                Import.file
            }
        }
    }
    """
    
    txn2 = client.client.txn(read_only=True)
    try:
        result2 = txn2.query(query2)
        data2 = json.loads(result2.json)
        files = data2.get("files", [])
        print(f"  Found {len(files)} File nodes")
        
        for file_node in files:
            imports = file_node.get("containsImport", [])
            if not isinstance(imports, list):
                imports = [imports] if imports else []
            
            for imp in imports:
                if not isinstance(imp, dict):
                    continue
                module = imp.get("Import.module")
                if not module or (isinstance(module, str) and not module.strip()):
                    bad_nodes.append({
                        "method": "file_relationship",
                        "uid": imp.get("uid"),
                        "file_path": file_node.get("File.path"),
                        "module": module,
                        "text": imp.get("Import.text"),
                        "import_file": imp.get("Import.file")
                    })
    finally:
        txn2.discard()
    
    # Method 3: Query by predicate (find all nodes with Import.module predicate)
    print("Method 3: Querying nodes with Import.module predicate...")
    query3 = """
    {
        with_module(func: has(Import.module)) {
            uid
            dgraph.type
            Import.module
        }
    }
    """
    
    txn3 = client.client.txn(read_only=True)
    try:
        result3 = txn3.query(query3)
        data3 = json.loads(result3.json)
        with_module = data3.get("with_module", [])
        print(f"  Found {len(with_module)} nodes with Import.module predicate")
    finally:
        txn3.discard()
    
    # Method 4: Query Import type and check for empty/invalid modules
    print("Method 4: Querying Import type and checking for empty/invalid modules...")
    query4 = """
    {
        all_imports(func: type(Import)) {
            uid
            dgraph.type
            Import.module
            Import.text
            Import.file
            Import.line
        }
    }
    """
    
    txn4 = client.client.txn(read_only=True)
    try:
        result4 = txn4.query(query4)
        data4 = json.loads(result4.json)
        all_imports = data4.get("all_imports", [])
        print(f"  Found {len(all_imports)} Import nodes")
        
        for imp in all_imports:
            module = imp.get("Import.module")
            
            # Check for various invalid states
            if "Import.module" not in imp:
                bad_nodes.append({
                    "method": "predicate_check",
                    "uid": imp.get("uid"),
                    "has_module_predicate": False,
                    "module": None,
                    "text": imp.get("Import.text"),
                    "file": imp.get("Import.file"),
                    "line": imp.get("Import.line")
                })
            elif module is None:
                bad_nodes.append({
                    "method": "predicate_check",
                    "uid": imp.get("uid"),
                    "has_module_predicate": True,
                    "module": None,
                    "text": imp.get("Import.text"),
                    "file": imp.get("Import.file"),
                    "line": imp.get("Import.line")
                })
            elif isinstance(module, str) and not module.strip():
                bad_nodes.append({
                    "method": "predicate_check",
                    "uid": imp.get("uid"),
                    "has_module_predicate": True,
                    "module": module,
                    "text": imp.get("Import.text"),
                    "file": imp.get("Import.file"),
                    "line": imp.get("Import.line")
                })
    finally:
        txn4.discard()
    
    # Remove duplicates
    seen_uids = set()
    unique_bad_nodes = []
    for node in bad_nodes:
        uid = node.get("uid")
        if uid and uid not in seen_uids:
            seen_uids.add(uid)
            unique_bad_nodes.append(node)
    
    print(f"\nTotal unique bad nodes found: {len(unique_bad_nodes)}")
    
    # Write to problem_nodes.txt
    output_file = Path(__file__).parent.parent.parent.parent / "problem_nodes.txt"
    
    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("PROBLEMATIC IMPORT NODES - Comprehensive Search\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Summary:\n")
        f.write(f"  Import nodes (direct): {len(imports1) if 'imports1' in locals() else 0}\n")
        f.write(f"  Nodes with Import.module predicate: {len(with_module) if 'with_module' in locals() else 0}\n")
        f.write(f"  Bad nodes found: {len(unique_bad_nodes)}\n")
        f.write("\n")
        
        if len(unique_bad_nodes) == 0:
            f.write("No problematic nodes found via native Dgraph queries!\n")
            f.write("\nHowever, GraphQL is reporting errors. This suggests:\n")
            f.write("  1. GraphQL schema validation is stricter than native queries\n")
            f.write("  2. There may be a mismatch between stored data and GraphQL schema\n")
            f.write("  3. GraphQL might be checking schema at query time and rejecting valid nodes\n")
            f.write("  4. There could be Import nodes that exist but aren't properly typed\n")
        else:
            f.write("Breakdown by detection method:\n")
            by_method = {}
            for node in unique_bad_nodes:
                method = node.get("method", "unknown")
                if method not in by_method:
                    by_method[method] = []
                by_method[method].append(node)
            
            for method, nodes in sorted(by_method.items()):
                f.write(f"  {method}: {len(nodes)} node(s)\n")
            f.write("\n" + "=" * 80 + "\n\n")
            
            for i, node in enumerate(unique_bad_nodes, 1):
                f.write(f"Bad Node #{i}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Detection Method: {node.get('method', 'unknown')}\n")
                f.write(f"UID: {node.get('uid', 'UNKNOWN')}\n")
                if "file_path" in node:
                    f.write(f"File (containing): {node['file_path']}\n")
                f.write(f"Module: {repr(node.get('module', 'MISSING'))}\n")
                if "has_module_predicate" in node:
                    f.write(f"Has Import.module predicate: {node['has_module_predicate']}\n")
                f.write(f"Text: {repr(node.get('text', 'MISSING'))}\n")
                f.write(f"File: {node.get('file', node.get('import_file', 'MISSING'))}\n")
                f.write("\n")
    
    print(f"\nDetailed information written to: {output_file}")
    
    return unique_bad_nodes

if __name__ == "__main__":
    find_all_imports_comprehensive()

