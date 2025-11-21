#!/usr/bin/env python3
"""Final comprehensive check - query ALL Import nodes and check EVERYTHING."""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from badger.graph.dgraph import DgraphClient

def find_bad_imports_final():
    """Comprehensive check of ALL Import nodes."""
    client = DgraphClient()
    
    # Query ALL Import nodes with all possible fields
    query = """
    {
        imports(func: type(Import)) {
            uid
            dgraph.type
            Import.module
            Import.text
            Import.file
            Import.line
            Import.importedItems
            Import.alias
        }
    }
    """
    
    print("Querying ALL Import nodes...")
    txn = client.client.txn(read_only=True)
    try:
        result = txn.query(query)
        data = json.loads(result.json)
    finally:
        txn.discard()
    
    imports = data.get("imports", [])
    print(f"Found {len(imports)} total Import nodes")
    
    # Check EVERY node thoroughly
    bad_nodes = []
    
    for i, imp in enumerate(imports):
        uid = imp.get("uid", "UNKNOWN")
        module = imp.get("Import.module")
        dgraph_type = imp.get("dgraph.type", [])
        if not isinstance(dgraph_type, list):
            dgraph_type = [dgraph_type] if dgraph_type else []
        
        # Comprehensive checks
        issues = []
        
        # Check 1: Is it typed as Import?
        if "Import" not in dgraph_type:
            issues.append(f"NOT_TYPED_AS_IMPORT (types: {dgraph_type})")
        
        # Check 2: Does Import.module key exist?
        if "Import.module" not in imp:
            issues.append("MODULE_KEY_MISSING")
        
        # Check 3: Is module None?
        elif module is None:
            issues.append("MODULE_VALUE_NONE")
        
        # Check 4: Is module empty string?
        elif isinstance(module, str):
            if module == "":
                issues.append("MODULE_EMPTY_STRING")
            elif not module.strip():
                issues.append("MODULE_WHITESPACE_ONLY")
            elif module.strip() == "<unknown>":
                issues.append("MODULE_UNKNOWN_PLACEHOLDER")
        
        # Check 5: Is module not a string?
        elif not isinstance(module, str):
            issues.append(f"MODULE_WRONG_TYPE ({type(module).__name__})")
        
        if issues:
            bad_nodes.append({
                "uid": uid,
                "index": i,
                "issues": issues,
                "dgraph_type": dgraph_type,
                "module": module,
                "text": imp.get("Import.text", "MISSING"),
                "file": imp.get("Import.file", "MISSING"),
                "line": imp.get("Import.line", "MISSING"),
                "imported_items": imp.get("Import.importedItems", []),
                "alias": imp.get("Import.alias", "MISSING")
            })
    
    print(f"Found {len(bad_nodes)} Import nodes with issues")
    
    # Write to problem_nodes.txt
    output_file = Path(__file__).parent.parent.parent.parent / "problem_nodes.txt"
    
    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("PROBLEMATIC IMPORT NODES - Comprehensive Analysis\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Summary:\n")
        f.write(f"  Total Import nodes: {len(imports)}\n")
        f.write(f"  Nodes with issues: {len(bad_nodes)}\n")
        if len(imports) > 0:
            f.write(f"  Percentage: {len(bad_nodes)/len(imports)*100:.2f}%\n")
        f.write("\n")
        
        if len(bad_nodes) == 0:
            f.write("NO PROBLEMATIC NODES FOUND via native Dgraph queries!\n")
            f.write("\nAll {len(imports)} Import nodes have valid module fields.\n")
            f.write("\nHowever, GraphQL is reporting {len(imports)} errors (one per Import node).\n")
            f.write("This suggests a GraphQL schema validation issue, not a data issue.\n")
            f.write("\nPossible causes:\n")
            f.write("  1. GraphQL schema cache is stale\n")
            f.write("  2. GraphQL validates differently than native queries\n")
            f.write("  3. Schema was updated but nodes weren't re-validated\n")
            f.write("  4. There's a mismatch between stored predicates and GraphQL schema\n")
        else:
            # Group by issue type
            by_issue = {}
            for node in bad_nodes:
                for issue in node["issues"]:
                    if issue not in by_issue:
                        by_issue[issue] = []
                    by_issue[issue].append(node)
            
            f.write(f"Breakdown by issue type:\n")
            for issue, nodes in sorted(by_issue.items()):
                f.write(f"  {issue}: {len(nodes)} node(s)\n")
            f.write("\n")
            
            # Group by file
            by_file = {}
            for node in bad_nodes:
                file_path = node.get("file", "UNKNOWN")
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(node)
            
            f.write(f"Breakdown by file:\n")
            for file_path, nodes in sorted(by_file.items()):
                f.write(f"  {file_path}: {len(nodes)} bad node(s)\n")
            f.write("\n" + "=" * 80 + "\n\n")
            
            # Write detailed information
            for i, node in enumerate(bad_nodes, 1):
                f.write(f"Bad Node #{i}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Index in query: {node['index']}\n")
                f.write(f"UID: {node['uid']}\n")
                f.write(f"Issues: {', '.join(node['issues'])}\n")
                f.write(f"Dgraph Type: {node['dgraph_type']}\n")
                f.write(f"File: {node['file']}\n")
                f.write(f"Line: {node['line']}\n")
                f.write(f"Module: {repr(node['module'])}\n")
                f.write(f"Text: {repr(node['text'])}\n")
                f.write(f"Imported Items: {node['imported_items']}\n")
                f.write(f"Alias: {node['alias']}\n")
                f.write("\n")
    
    print(f"\nDetailed information written to: {output_file}")
    
    if len(bad_nodes) > 0:
        print(f"\n" + "=" * 80)
        print(f"FOUND {len(bad_nodes)} PROBLEMATIC NODES!")
        print("=" * 80)
    else:
        print(f"\n" + "=" * 80)
        print("NO PROBLEMATIC NODES FOUND in native queries")
        print("But GraphQL reports errors - this is a GraphQL schema issue")
        print("=" * 80)
    
    return bad_nodes

if __name__ == "__main__":
    find_bad_imports_final()

