#!/usr/bin/env python3
"""Find Import nodes in Dgraph that are missing the required module field."""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from badger.graph.dgraph import DgraphClient

def find_bad_imports():
    """Find all Import nodes missing the module field."""
    client = DgraphClient()
    
    # Use Dgraph's native query language (not GraphQL) to find all Import nodes
    # Query ALL fields to see what's actually stored
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
    
    print("Querying Dgraph for all Import nodes...")
    txn = client.client.txn(read_only=True)
    try:
        result = txn.query(query)
        data = json.loads(result.json)
    finally:
        txn.discard()
    
    imports = data.get("imports", [])
    print(f"Found {len(imports)} total Import nodes")
    
    # Find nodes with missing or invalid module field
    # Check multiple conditions:
    # 1. Key doesn't exist
    # 2. Value is None
    # 3. Value is empty string
    # 4. Value is only whitespace
    bad_nodes = []
    for imp in imports:
        module = imp.get("Import.module")
        uid = imp.get("uid", "UNKNOWN")
        
        # Check various failure conditions
        is_bad = False
        reason = ""
        
        if "Import.module" not in imp:
            is_bad = True
            reason = "KEY_MISSING"
        elif module is None:
            is_bad = True
            reason = "VALUE_NONE"
        elif isinstance(module, str):
            if not module.strip():
                is_bad = True
                reason = "EMPTY_STRING" if module == "" else "WHITESPACE_ONLY"
        else:
            # Module exists but is not a string (shouldn't happen)
            is_bad = True
            reason = f"WRONG_TYPE_{type(module).__name__}"
        
        if is_bad:
            bad_nodes.append({
                "uid": uid,
                "reason": reason,
                "node": imp
            })
    
    print(f"Found {len(bad_nodes)} Import nodes with missing or invalid module field")
    
    # Also try querying through File relationships to see if GraphQL sees different data
    print("\nChecking File nodes and their containsImport relationships...")
    file_query = """
    {
        files(func: type(File)) {
            uid
            File.path
            containsImport {
                uid
                Import.module
                Import.text
                Import.file
                Import.line
            }
        }
    }
    """
    
    txn2 = client.client.txn(read_only=True)
    try:
        result2 = txn2.query(file_query)
        data2 = json.loads(result2.json)
    finally:
        txn2.discard()
    
    files = data2.get("files", [])
    print(f"Found {len(files)} File nodes")
    
    # Check for imports in File nodes that don't have module
    file_bad_imports = []
    for file_node in files:
        file_path = file_node.get("File.path", "UNKNOWN")
        imports_list = file_node.get("containsImport", [])
        if not isinstance(imports_list, list):
            imports_list = [imports_list] if imports_list else []
        
        for imp in imports_list:
            if not isinstance(imp, dict):
                continue
            module = imp.get("Import.module")
            uid = imp.get("uid")
            
            # Check if module is missing/invalid
            is_bad = False
            reason = ""
            if "Import.module" not in imp:
                is_bad = True
                reason = "KEY_MISSING"
            elif module is None:
                is_bad = True
                reason = "VALUE_NONE"
            elif isinstance(module, str) and not module.strip():
                is_bad = True
                reason = "EMPTY_STRING" if module == "" else "WHITESPACE_ONLY"
            
            if is_bad:
                file_bad_imports.append({
                    "file": file_path,
                    "import_uid": uid,
                    "reason": reason,
                    "import_text": imp.get("Import.text", "MISSING"),
                    "import_module": imp.get("Import.module", "MISSING"),
                    "import_file": imp.get("Import.file", "MISSING"),
                    "import_line": imp.get("Import.line", "MISSING")
                })
    
    if file_bad_imports:
        print(f"Found {len(file_bad_imports)} imports in File nodes with missing module field")
        # Add to bad_nodes
        for item in file_bad_imports:
            bad_nodes.append({
                "uid": item["import_uid"],
                "reason": item["reason"],
                "source": "File.containsImport",
                "file": item["file"],
                "node": item
            })
    
    # Write to problem_nodes.txt
    output_file = Path(__file__).parent.parent.parent.parent / "problem_nodes.txt"
    
    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("PROBLEMATIC IMPORT NODES - Missing Module Field\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Summary:\n")
        f.write(f"  Total Import nodes (direct query): {len(imports)}\n")
        f.write(f"  Total File nodes: {len(files)}\n")
        f.write(f"  Nodes with missing/invalid module: {len(bad_nodes)}\n")
        if len(imports) > 0:
            f.write(f"  Percentage: {len(bad_nodes)/len(imports)*100:.2f}%\n")
        f.write("\n")
        
        # Group by reason
        by_reason = {}
        for node in bad_nodes:
            reason = node.get("reason", "UNKNOWN")
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(node)
        
        f.write(f"Breakdown by issue type:\n")
        for reason, nodes in sorted(by_reason.items()):
            f.write(f"  {reason}: {len(nodes)} node(s)\n")
        f.write("\n")
        
        if len(bad_nodes) == 0:
            f.write("No problematic nodes found in direct queries.\n")
            f.write("However, GraphQL may still fail due to:\n")
            f.write("  1. GraphQL being stricter than native queries\n")
            f.write("  2. Schema validation at query time\n")
            f.write("  3. Relationship traversal issues\n")
            f.write("\n")
        else:
            # Group by file for analysis
            by_file = {}
            for node in bad_nodes:
                if "source" in node:
                    file_path = node.get("file", "UNKNOWN")
                else:
                    file_path = node.get("node", {}).get("Import.file", "UNKNOWN")
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(node)
            
            f.write(f"Breakdown by file:\n")
            for file_path, nodes in sorted(by_file.items()):
                f.write(f"  {file_path}: {len(nodes)} bad node(s)\n")
            f.write("\n" + "=" * 80 + "\n\n")
            
            # Write detailed information for each bad node
            for i, node in enumerate(bad_nodes, 1):
                f.write(f"Bad Node #{i}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Issue: {node.get('reason', 'UNKNOWN')}\n")
                f.write(f"UID: {node.get('uid', 'UNKNOWN')}\n")
                
                if "source" in node:
                    f.write(f"Source: Found via File.containsImport relationship\n")
                    f.write(f"File: {node.get('file', 'UNKNOWN')}\n")
                    node_data = node.get("node", {})
                    f.write(f"Import UID: {node_data.get('import_uid', 'UNKNOWN')}\n")
                    f.write(f"Module: {repr(node_data.get('import_module', 'MISSING'))}\n")
                    f.write(f"Text: {repr(node_data.get('import_text', 'MISSING'))}\n")
                    f.write(f"Import File: {node_data.get('import_file', 'MISSING')}\n")
                    f.write(f"Import Line: {node_data.get('import_line', 'MISSING')}\n")
                else:
                    node_data = node.get("node", {})
                    f.write(f"Node Type: {node_data.get('dgraph.type', 'UNKNOWN')}\n")
                    f.write(f"File: {node_data.get('Import.file', 'MISSING')}\n")
                    f.write(f"Line: {node_data.get('Import.line', 'MISSING')}\n")
                    if "Import.module" in node_data:
                        f.write(f"Module: {repr(node_data.get('Import.module', 'MISSING'))}\n")
                    else:
                        f.write(f"Module: KEY MISSING (not in node dict)\n")
                    f.write(f"Text: {repr(node_data.get('Import.text', 'MISSING'))}\n")
                    f.write(f"Imported Items: {node_data.get('Import.importedItems', [])}\n")
                    f.write(f"Alias: {node_data.get('Import.alias', 'MISSING')}\n")
                f.write("\n")
    
    print(f"\nDetailed information written to: {output_file}")
    print(f"Found {len(bad_nodes)} problematic nodes")
    
    if len(bad_nodes) > 0:
        print("\n" + "=" * 80)
        print(f"FOUND {len(bad_nodes)} PROBLEMATIC NODES!")
        print("Check problem_nodes.txt for details")
        print("=" * 80)
    
    return bad_nodes

if __name__ == "__main__":
    find_bad_imports()
