# Debug Summary: check_affected_files and get_include_dependencies

## Issues Found

### 1. **Backwards Logic in `get_include_dependencies` for C files**

**Current behavior (WRONG):**
- Queries what the target file imports
- Finds files that import those same modules
- This finds files that share imports with the target, not files that import the target

**Expected behavior:**
- Find files where `containsImport.module` matches the target file path (or `.h` equivalent)
- For `encryption.c`, should find files that include `encryption.h`

**Location:** `cli/badger/mcp/tools.py` lines 476-536

### 2. **Path Format Mismatch**

The graph stores paths as:
- `/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/encryption/encryption.h`

But user may be testing with:
- `/home/william/Documents/tinyweb/CTinyweb/src/packages/encryption/encryption.h`

Note: `codingProj/tinyweb` vs `tinyweb`, and `CTinyWeb` vs `CTinyweb`

### 3. **Missing `module` Field in Some Import Nodes**

Some Import nodes don't have the `module` field set, causing GraphQL errors. This may be a data issue from indexing.

## What Should Work

Based on the graph data:
- Files that include `packages/encryption/encryption.h`:
  - `/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/packages/comm/envelope_dispatcher.c`
  - `/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/tests/envelope_test.c`
  - `/home/william/Documents/codingProj/tinyweb/CTinyWeb/src/tests/encryption_test.c`

- Function `encrypt_envelope_payload` is called by:
  - `tw_envelope_build_and_sign` in `envelope.c`
  - `encryption_test_main` in `encryption_test.c`

## Fix Needed

The `get_include_dependencies` function for C files should:

1. For a `.c` file, convert to `.h` file path
2. Query all files and find those where `containsImport.module` matches the target path
3. Handle path normalization (relative vs absolute, different base paths)

Example fix:
```python
# Instead of querying what target imports, query what imports target
target_module = file_path
if file_path.endswith(".c"):
    # Convert .c to .h
    target_module = file_path[:-2] + ".h"

# Find files where containsImport.module == target_module
```

