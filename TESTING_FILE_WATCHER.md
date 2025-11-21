# Testing the File Watcher Feature

This guide explains how to test the dynamic graph updates with file watching.

## Prerequisites

1. **Dgraph is running**:
   ```bash
   badger init_graph
   # or if already initialized:
   badger start_graph
   ```

2. **A test workspace is indexed**:
   ```bash
   cd /path/to/your/test/codebase
   badger index
   ```

   This will:
   - Index all source files
   - Build the graph
   - Save workspace path to `.badger-index/workspace.json`
   - Create hash cache at `.badger-index/node_hashes.json`

## Test 1: Basic File Watching

### Step 1: Start MCP Server with Watch Mode

```bash
cd /path/to/your/test/codebase
badger mcp-server --watch --verbose
```

You should see:
```
Starting MCP server...
Graph database: http://localhost:8080
Workspace: /path/to/your/test/codebase
File watching: enabled (10 second debounce)
Server will communicate via stdio
```

### Step 2: Modify a File

In another terminal, edit a source file (e.g., `test.py`):

```bash
# Add a new function or modify an existing one
echo "def new_function():\n    pass" >> test.py
```

### Step 3: Wait for Debounce (10 seconds)

The file watcher has a 10-second debounce, so wait at least 10 seconds after your last change.

### Step 4: Check Logs

In the MCP server terminal, you should see:
```
File changes detected: 1 files changed
Re-indexing workspace after file changes...
Graph built: X functions, Y classes
Successfully updated graph: Z files indexed
```

## Test 2: Verify Hash Cache is Working

### Step 1: Check Initial Cache Size

```bash
# Check how many nodes are cached
cat .badger-index/node_hashes.json | jq '.hashes | length'
```

### Step 2: Make a Small Change

Edit a file and add a comment (something that doesn't change the graph structure):

```python
# Add this comment
def existing_function():
    pass
```

### Step 3: Wait for Re-index

After 10 seconds, check the logs. You should see that only the changed file's nodes were processed.

### Step 4: Verify Only Changed Nodes Were Inserted

The hash cache should skip unchanged nodes. Check the logs for messages like:
```
Hash cache: X nodes cached
```

## Test 3: File Creation

### Step 1: Create a New File

```bash
cat > new_file.py << EOF
def new_function():
    """A new function"""
    return 42
EOF
```

### Step 2: Wait for Re-index

After 10 seconds, the new file should be indexed and added to the graph.

### Step 3: Verify

Check that the new function appears in the graph:
```bash
badger stats
```

## Test 4: File Deletion

### Step 1: Delete a File

```bash
rm test_file.py
```

### Step 2: Wait for Re-index

After 10 seconds, you should see:
```
Handling 1 deleted files
Deleted X nodes for file: /path/to/test_file.py
```

### Step 3: Verify Deletion

Check that nodes from the deleted file are removed:
```bash
badger stats
```

The counts should decrease.

## Test 5: Multiple Rapid Changes (Debouncing)

### Step 1: Make Multiple Changes Quickly

```bash
# Edit multiple files in quick succession
echo "# Change 1" >> file1.py
echo "# Change 2" >> file2.py
echo "# Change 3" >> file3.py
```

### Step 2: Verify Single Re-index

The debounce should batch all changes. After 10 seconds, you should see **one** re-index operation that processes all changed files.

## Test 6: Workspace Enforcement

### Step 1: Index Workspace A

```bash
cd /workspace/a
badger index
```

### Step 2: Try to Index Different Workspace

```bash
cd /workspace/b
badger index
```

You should see:
```
Warning: Different workspace already indexed: /workspace/a
Current workspace: /workspace/b
Clear graph and re-index with new workspace? [Y/n]:
```

### Step 3: Verify Workspace Path is Saved

```bash
cat .badger-index/workspace.json
```

Should show the indexed workspace path.

## Test 7: MCP Server Watches Correct Workspace

### Step 1: Index Workspace A

```bash
cd /workspace/a
badger index
```

### Step 2: Start MCP Server from Different Directory

```bash
cd /workspace/b
badger mcp-server --watch --workspace /workspace/a
```

The server should use the stored workspace path from `/workspace/a/.badger-index/workspace.json`, not the current directory.

## Debugging Tips

### Enable Verbose Logging

```bash
badger mcp-server --watch --verbose
```

This shows detailed logs including:
- File change events
- Re-indexing progress
- Hash cache statistics
- Node insertion counts

### Check Hash Cache

```bash
# View cached hashes
cat .badger-index/node_hashes.json | jq

# Count cached nodes
cat .badger-index/node_hashes.json | jq '.hashes | length'
```

### Check Workspace Metadata

```bash
# View stored workspace path
cat .badger-index/workspace.json | jq
```

### Monitor Graph Changes

```bash
# Before change
badger stats > before.txt

# Make change, wait for re-index

# After change
badger stats > after.txt

# Compare
diff before.txt after.txt
```

## Expected Behavior

1. **File modifications**: Re-index entire workspace, insert only changed nodes
2. **File creation**: New file indexed, all its nodes inserted
3. **File deletion**: Nodes from deleted file removed from graph
4. **Debouncing**: Multiple rapid changes batched into single re-index
5. **Hash cache**: Unchanged nodes skipped (no re-insertion, no embedding regeneration)
6. **Workspace scoping**: Watcher only monitors the indexed workspace

## Troubleshooting

### File Watcher Not Starting

- Check that workspace path is stored: `cat .badger-index/workspace.json`
- Verify you're in the correct directory or use `--workspace` flag
- Check logs for errors

### Changes Not Detected

- Ensure you're editing source files (.py, .c, .h, etc.)
- Wait at least 10 seconds after changes (debounce delay)
- Check that files are within the workspace directory
- Verify file watcher started: look for "File watcher started" in logs

### Too Many Re-indexes

- This is normal if you make changes frequently
- The 10-second debounce should batch rapid changes
- Consider making changes in batches

### Hash Cache Not Working

- Check that `.badger-index/node_hashes.json` exists
- Verify cache file is readable/writable
- Check logs for hash cache messages
- Try clearing and re-indexing: `rm .badger-index/node_hashes.json && badger index`

