#!/usr/bin/env python3
"""Debug script for index_directory function.

Usage:
    python debug_index_directory.py <directory> [--language python|c] [--no-db] [--verbose]
"""

import sys
from pathlib import Path

# Add cli to path
sys.path.insert(0, str(Path(__file__).parent / "cli"))

from badger.main import index_directory
from badger.config import BadgerConfig
from badger.graph import DgraphClient

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Debug index_directory function")
    parser.add_argument("directory", type=Path, help="Directory to index")
    parser.add_argument("--language", "-l", choices=["python", "c"], help="Language filter")
    parser.add_argument("--no-db", action="store_true", help="Skip database insertion (just parse)")
    parser.add_argument("--endpoint", "-e", default="http://localhost:8080", help="Dgraph endpoint")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--strict", action="store_true", default=True, help="Enable strict validation")
    parser.add_argument("--no-strict", dest="strict", action="store_false", help="Disable strict validation")
    
    args = parser.parse_args()
    
    # Create config
    config = BadgerConfig()
    config.verbose = args.verbose
    
    # Create Dgraph client (or None if --no-db)
    dgraph_client = None
    if not args.no_db:
        try:
            dgraph_client = DgraphClient(args.endpoint)
            print(f"✓ Connected to Dgraph at {args.endpoint}")
        except Exception as e:
            print(f"⚠ Warning: Could not connect to Dgraph: {e}")
            print("  Continuing without database insertion...")
            dgraph_client = None
    
    # Call index_directory
    print(f"\n{'='*60}")
    print(f"Debugging index_directory")
    print(f"Directory: {args.directory}")
    print(f"Language: {args.language or 'auto-detect'}")
    print(f"Database: {'enabled' if dgraph_client else 'disabled (--no-db)'}")
    print(f"Strict validation: {args.strict}")
    print(f"{'='*60}\n")
    
    try:
        parse_results, graph_data = index_directory(
            directory=args.directory,
            config=config,
            language=args.language,
            dgraph_client=dgraph_client,
            strict_validation=args.strict
        )
        
        print(f"\n{'='*60}")
        print("Results:")
        print(f"  Files parsed: {len(parse_results)}")
        print(f"  Functions: {len(graph_data.functions)}")
        print(f"  Classes: {len(graph_data.classes)}")
        print(f"  Imports: {len(graph_data.imports)}")
        if hasattr(graph_data, 'macros'):
            print(f"  Macros: {len(graph_data.macros)}")
        if hasattr(graph_data, 'variables'):
            print(f"  Variables: {len(graph_data.variables)}")
        if hasattr(graph_data, 'typedefs'):
            print(f"  Typedefs: {len(graph_data.typedefs)}")
        print(f"{'='*60}\n")
        
        # Print first few parse results for inspection
        if parse_results and args.verbose:
            print("\nFirst parse result:")
            result = parse_results[0]
            print(f"  File: {result.file_path}")
            print(f"  Functions: {len(result.functions)}")
            for func in result.functions[:3]:
                print(f"    - {func.name} (line {func.start.row})")
            print(f"  Classes: {len(result.classes)}")
            for cls in result.classes[:3]:
                print(f"    - {cls.name} (line {cls.start.row})")
            print(f"  Imports: {len(result.imports)}")
            for imp in result.imports[:3]:
                print(f"    - {imp.text or imp.module} (line {imp.start.row})")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

