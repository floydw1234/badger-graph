#!/usr/bin/env python3
"""Test File.containsImport relationship structure."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.graph.dgraph import DgraphClient

async def test_file_contains_import():
    client = DgraphClient()
    
    # Try different query formats
    queries = [
        # Query 1: Using File.containsImport
        '''
        {
            files(func: type(File), first: 5) {
                uid
                File.path
                File.containsImport {
                    uid
                    Import.module
                    Import.text
                }
            }
        }
        ''',
        # Query 2: Using containsImport (without File. prefix)
        '''
        {
            files(func: type(File), first: 5) {
                uid
                File.path
                containsImport {
                    uid
                    Import.module
                    Import.text
                }
            }
        }
        ''',
        # Query 3: Using expand
        '''
        {
            files(func: type(File), first: 5) {
                uid
                File.path
                File.containsImport {
                    expand(_all_)
                }
            }
        }
        '''
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n{'='*80}")
        print(f"Query {i}:")
        print(f"{'='*80}")
        txn = client.client.txn(read_only=True)
        try:
            result = txn.query(query)
            data = json.loads(result.json)
        except Exception as e:
            print(f"ERROR: {e}")
            txn.discard()
            continue
        finally:
            txn.discard()
        
        files = data.get("files", [])
        print(f"Found {len(files)} files")
        
        for file_node in files[:2]:
            path = file_node.get("File.path", "N/A")
            imports = file_node.get("File.containsImport") or file_node.get("containsImport", [])
            if not isinstance(imports, list):
                imports = [imports] if imports else []
            print(f"\n  File: {path}")
            print(f"  Has {len(imports)} imports")
            for imp in imports[:2]:
                if isinstance(imp, dict):
                    print(f"    Import: {imp}")
                else:
                    print(f"    Import (not dict): {type(imp)} = {imp}")

if __name__ == "__main__":
    asyncio.run(test_file_contains_import())

