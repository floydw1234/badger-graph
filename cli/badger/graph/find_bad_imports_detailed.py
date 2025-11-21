#!/usr/bin/env python3
"""Find Import nodes by querying File nodes and their containsImport relationships."""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from badger.graph.dgraph import DgraphClient

def find_bad_imports_detailed():
    """Find bad imports by querying through File relationships."""
    client = DgraphClient()
    
    # Query File nodes and follow containsImport edges
    # This mimics what GraphQL does
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
                Import.line
            }
        }
    }
    """
    
    print("Querying File nodes and their containsImport relationships...")
    txn = client.client.txn(read_only=True)
    try:
        result = txn.query(query)
        data = json.loads(result.json)
    finally:
        txn.discard()
    
    files = data.get("files", [])
    print(f"Found {len(files)} File nodes")
    
    # Find imports with missing module
    bad_imports = []
    for file_node in files:
        file_path = file_node.get("File.path", "UNKNOWN")
        file_uid = file_node.get("uid", "UNKNOWN")
        imports_list = file_node.get("containsImport", [])
        if not isinstance(imports_list, list):
            imports_list = [imports_list] if imports_list else []
        
        for imp in imports_list:
            if not isinstance(imp, dict):
                continue
            
            uid = imp.get("uid", "UNKNOWN")
            module = imp.get("Import.module")
            
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
                bad_imports.append({
                    "file_path": file_path,
                    "file_uid": file_uid,
                    "import_uid": uid,
                    "reason": reason,
                    "module": module,
                    "text": imp.get("Import.text", "MISSING"),
                    "import_file": imp.get("Import.file", "MISSING"),
                    "import_line": imp.get("Import.line", "MISSING"),
                    "dgraph_type": imp.get("dgraph.type", "UNKNOWN")
                })
    
    print(f"Found {len(bad_imports)} Import nodes with missing/invalid module field")
    
    # Write to problem_nodes.txt
    output_file = Path(__file__).parent.parent.parent.parent / "problem_nodes.txt"
    
    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("PROBLEMATIC IMPORT NODES - Found via File.containsImport Relationships\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Summary:\n")
        f.write(f"  Total File nodes: {len(files)}\n")
        f.write(f"  Total Import nodes (via relationships): {sum(len(f.get('containsImport', [])) if isinstance(f.get('containsImport'), list) else (1 if f.get('containsImport') else 0) for f in files)}\n")
        f.write(f"  Import nodes with missing/invalid module: {len(bad_imports)}\n")
        f.write("\n")
        
        if len(bad_imports) == 0:
            f.write("No problematic nodes found!\n")
        else:
            # Group by reason
            by_reason = {}
            for imp in bad_imports:
                reason = imp["reason"]
                if reason not in by_reason:
                    by_reason[reason] = []
                by_reason[reason].append(imp)
            
            f.write(f"Breakdown by issue type:\n")
            for reason, nodes in sorted(by_reason.items()):
                f.write(f"  {reason}: {len(nodes)} node(s)\n")
            f.write("\n")
            
            # Group by file
            by_file = {}
            for imp in bad_imports:
                file_path = imp["file_path"]
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(imp)
            
            f.write(f"Breakdown by file:\n")
            for file_path, nodes in sorted(by_file.items()):
                f.write(f"  {file_path}: {len(nodes)} bad node(s)\n")
            f.write("\n" + "=" * 80 + "\n\n")
            
            # Write detailed information for each bad node
            for i, imp in enumerate(bad_imports, 1):
                f.write(f"Bad Node #{i}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Node Type: {imp['dgraph_type']}\n")
                f.write(f"Issue: {imp['reason']}\n")
                f.write(f"Import UID: {imp['import_uid']}\n")
                f.write(f"File (containing): {imp['file_path']}\n")
                f.write(f"File UID: {imp['file_uid']}\n")
                f.write(f"Import File: {imp['import_file']}\n")
                f.write(f"Import Line: {imp['import_line']}\n")
                f.write(f"Module: {repr(imp['module'])}\n")
                f.write(f"Text: {repr(imp['text'])}\n")
                f.write("\n")
    
    print(f"\nDetailed information written to: {output_file}")
    
    if len(bad_imports) > 0:
        print(f"\n" + "=" * 80)
        print(f"FOUND {len(bad_imports)} PROBLEMATIC NODES!")
        print("These are the nodes that GraphQL can't query.")
        print("=" * 80)
    
    return bad_imports

if __name__ == "__main__":
    find_bad_imports_detailed()

