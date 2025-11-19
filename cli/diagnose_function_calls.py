#!/usr/bin/env python3
"""Diagnostic script to check function call relationships in Dgraph."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from badger.graph.dgraph import DgraphClient

def main():
    """Query Dgraph to diagnose function call relationships."""
    client = DgraphClient("http://localhost:8080")
    
    print("=" * 80)
    print("DIAGNOSTIC: Function Call Relationships")
    print("=" * 80)
    
    # Test 1: Check if create_mcp_server function exists
    print("\n1. Checking if 'create_mcp_server' function exists:")
    query1 = """
    query {
        func: queryFunction(filter: {name: {eq: "create_mcp_server"}}, first: 10) {
            id
            name
            file
            line
            signature
        }
    }
    """
    result1 = client.execute_graphql_query(query1, {})
    if result1.get("func"):
        funcs = result1["func"] if isinstance(result1["func"], list) else [result1["func"]]
        print(f"   Found {len(funcs)} function(s) named 'create_mcp_server':")
        for f in funcs:
            print(f"   - {f.get('file')}:{f.get('line')} - {f.get('signature', f.get('name'))}")
    else:
        print("   ❌ No function found with name 'create_mcp_server'")
    
    # Test 2: Check callsFunction relationships (outgoing)
    print("\n2. Checking 'callsFunction' relationships (outgoing):")
    query2 = """
    query {
        func: queryFunction(filter: {name: {eq: "create_mcp_server"}}, first: 10) {
            id
            name
            file
            callsFunction {
                id
                name
                file
                line
            }
        }
    }
    """
    result2 = client.execute_graphql_query(query2, {})
    if result2.get("func"):
        funcs = result2["func"] if isinstance(result2["func"], list) else [result2["func"]]
        for f in funcs:
            calls = f.get("callsFunction", [])
            if not isinstance(calls, list):
                calls = [calls] if calls else []
            print(f"   Function '{f.get('name')}' in {f.get('file')} calls {len(calls)} function(s):")
            for call in calls:
                print(f"     -> {call.get('name')} in {call.get('file')}:{call.get('line')}")
            if not calls:
                print("     (no outgoing calls found)")
    
    # Test 3: Check calledByFunction relationships (incoming)
    print("\n3. Checking 'calledByFunction' relationships (incoming):")
    query3 = """
    query {
        func: queryFunction(filter: {name: {eq: "create_mcp_server"}}, first: 10) {
            id
            name
            file
            calledByFunction {
                id
                name
                file
                line
                signature
            }
        }
    }
    """
    result3 = client.execute_graphql_query(query3, {})
    if result3.get("func"):
        funcs = result3["func"] if isinstance(result3["func"], list) else [result3["func"]]
        for f in funcs:
            callers = f.get("calledByFunction", [])
            if not isinstance(callers, list):
                callers = [callers] if callers else []
            print(f"   Function '{f.get('name')}' in {f.get('file')} is called by {len(callers)} function(s):")
            for caller in callers:
                print(f"     <- {caller.get('name')} in {caller.get('file')}:{caller.get('line')} - {caller.get('signature', '')}")
            if not callers:
                print("     ❌ (no callers found - this is the bug!)")
    
    # Test 4: Check run_mcp_server function and what it calls
    print("\n4. Checking 'run_mcp_server' function and its calls:")
    query4 = """
    query {
        func: queryFunction(filter: {name: {eq: "run_mcp_server"}}, first: 10) {
            id
            name
            file
            line
            callsFunction {
                id
                name
                file
                line
            }
        }
    }
    """
    result4 = client.execute_graphql_query(query4, {})
    if result4.get("func"):
        funcs = result4["func"] if isinstance(result4["func"], list) else [result4["func"]]
        for f in funcs:
            calls = f.get("callsFunction", [])
            if not isinstance(calls, list):
                calls = [calls] if calls else []
            print(f"   Function '{f.get('name')}' in {f.get('file')}:{f.get('line')} calls {len(calls)} function(s):")
            for call in calls:
                print(f"     -> {call.get('name')} in {call.get('file')}:{call.get('line')}")
            if not calls:
                print("     ❌ (no calls found - should call create_mcp_server)")
    
    # Test 5: Count total function call relationships
    print("\n5. Counting total function call relationships:")
    query5 = """
    query {
        funcs: queryFunction(first: 1000) {
            id
            name
            callsFunction {
                id
            }
        }
    }
    """
    result5 = client.execute_graphql_query(query5, {})
    if result5.get("funcs"):
        funcs = result5["funcs"] if isinstance(result5["funcs"], list) else [result5["funcs"]]
        total_calls = 0
        funcs_with_calls = 0
        for f in funcs:
            calls = f.get("callsFunction", [])
            if not isinstance(calls, list):
                calls = [calls] if calls else []
            if calls:
                funcs_with_calls += 1
                total_calls += len(calls)
        print(f"   Total functions: {len(funcs)}")
        print(f"   Functions with outgoing calls: {funcs_with_calls}")
        print(f"   Total call relationships: {total_calls}")
    
    print("\n" + "=" * 80)
    print("Diagnostic complete")
    print("=" * 80)

if __name__ == "__main__":
    main()

