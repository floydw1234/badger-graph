# MCP Tools Test Report

## Test Results Summary

### ✅ Working Tools

1. **`find_symbol_usages`** - PARTIALLY WORKING
   - ✅ Finds function definitions correctly
   - ❌ Does NOT find function call sites (should show "call" type usages)
   - Test: `create_mcp_server` - Found definition only, no callers
   - Test: `index_directory` - Found definition only, no callers

2. **`semantic_code_search`** - ✅ WORKING
   - ✅ Returns relevant functions and classes
   - ✅ Similarity scores are reasonable
   - ✅ Finds functions by semantic meaning
   - Test queries worked well

### ❌ Not Working / Empty Results

3. **`get_function_callers`** - ❌ NOT WORKING
   - Returns empty results for all tested functions:
     - `create_mcp_server` → 0 callers (should have 1: line 301 in server.py)
     - `insert_graph` → 0 callers (should have 2: main.py line 174, indexer.py line 97)
     - `index_directory` → 0 callers (should have 2: main.py lines 314, 412)
   - **Issue**: Function call relationships not being stored or queried correctly

4. **`get_include_dependencies`** - ❌ NOT WORKING FOR PYTHON
   - Returns empty dependencies
   - **Note**: This tool is designed for C `#include` statements
   - Python uses `import` statements, which may not be tracked the same way
   - **Issue**: Python import dependencies not being tracked

5. **`check_affected_files`** - ❌ NOT WORKING
   - Returns empty affected files
   - Should find files that:
     - Import from changed files
     - Call functions from changed files
   - **Issue**: Dependency relationships not being stored or queried

6. **`find_struct_field_access`** - NOT TESTED
   - This is C-specific, not applicable to Python codebase

## Root Cause Analysis

### Function Call Relationships

The code shows that:
1. ✅ Function calls ARE extracted by parsers (PythonParser line 65, CParser line 80)
2. ✅ Function calls ARE added to relationships in `build_graph()` (builder.py lines 196-207)
3. ✅ Relationships ARE stored in `insert_graph()` (dgraph.py lines 594-616)

**However**, the queries are returning empty. Possible issues:
- Function call relationships might not be getting stored correctly
- The `calledByFunction` inverse relationship might not be working
- Function names in calls might not match function definitions exactly

### Import Dependencies

- Python imports are extracted but may not be stored as dependency relationships
- The `get_include_dependencies` tool queries for C-style includes, not Python imports
- Need to check if Python import relationships are stored

## Recommendations

1. **Verify function call storage**: Check if `Function.callsFunction` relationships are actually in Dgraph
2. **Check function name matching**: Ensure caller/callee names match exactly
3. **Add Python import tracking**: Extend `get_include_dependencies` to work with Python imports
4. **Fix `check_affected_files`**: Should query import relationships and function call relationships

## Next Steps

1. Query Dgraph directly to verify relationships exist:
   ```graphql
   query {
     func: queryFunction(filter: {name: {eq: "create_mcp_server"}}, first: 1) {
       id
       name
       calledByFunction {
         id
         name
         file
       }
     }
   }
   ```

2. Check if function calls are being extracted correctly during parsing
3. Verify relationship storage in `insert_graph()` method

