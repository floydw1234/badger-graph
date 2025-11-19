# Badger MCP Server Setup for Cursor

## Prerequisites

1. **Install dependencies:**
   ```bash
   cd cli
   pip install -r requirements.txt
   ```

2. **Ensure Dgraph is running** and accessible at your configured endpoint (default: `http://localhost:8080`)

3. **That's it!** The MCP server will automatically index your codebase on startup.
   
   **Optional:** If you want to index manually (or re-index), you can use:
   ```bash
   badger index /path/to/your/codebase --graphdb-endpoint http://localhost:8080
   ```

## Adding to Cursor

### Method 1: Via Cursor Settings UI

1. Open Cursor Settings:
   - Click the gear icon (⚙️) in the top right
   - Or go to `File` > `Settings` > `Features` > `MCP`

2. Click `+ Add New MCP Server`

3. Configure the server:
   - **Name**: `Badger Code Graph`
   - **Transport**: `command`
   - **Command**: 
     ```
     /home/william/Documents/codingProj/badger/cli/venv/bin/python -m badger.main mcp-server
     ```
     (Adjust the path to your Python executable)
   - **Environment Variables**:
     ```
     BADGER_GRAPHDB_ENDPOINT=http://localhost:8080
     BADGER_WORKSPACE_PATH=/path/to/your/codebase
     ```
     **Important**: Set `BADGER_WORKSPACE_PATH` to the root of your codebase. The MCP server will automatically index this directory on startup.

4. Save and enable the server

### Method 2: Via Settings JSON

1. Open Cursor Settings JSON:
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "Preferences: Open User Settings (JSON)"
   - Or manually edit: `~/.cursor/settings.json`

2. Add the MCP server configuration:

```json
{
  "mcpServers": {
    "badger": {
      "command": "/home/william/Documents/codingProj/badger/cli/venv/bin/python",
      "args": ["-m", "badger.main", "mcp-server"],
      "env": {
        "BADGER_GRAPHDB_ENDPOINT": "http://localhost:8080",
        "BADGER_WORKSPACE_PATH": "/path/to/your/codebase"
      }
    }
  }
}
```

**Important Notes:**
- The key is `mcpServers` (camelCase, no dot), **not** `mcp.servers`
- If you want to disable auto-indexing, add `"--no-auto-index"` to the args array:
  ```json
  "args": ["-m", "badger.main", "mcp-server", "--no-auto-index"]
  ```

**Important**: Set `BADGER_WORKSPACE_PATH` to the root of your codebase. The MCP server will automatically index this directory and use the calculated namespace.

**Note**: Replace the Python path with your actual path. You can find it with:
```bash
which python
# or
which python3
```

## Workflow

**Simple:** Just configure the MCP server in Cursor and it will automatically index your codebase!

1. **Configure MCP server in Cursor** (see below) - Set `BADGER_WORKSPACE_PATH` to your codebase root

2. **Cursor starts the server** - The server automatically indexes the workspace on startup

3. **Use MCP tools in Cursor** - The server queries the indexed graph database

**Automatic Indexing**: By default, the MCP server automatically indexes the workspace when it starts. This means:
- No need to run `badger index` separately
- The server stays up-to-date with your codebase
- Each time Cursor starts the server, it re-indexes (ensuring fresh data)

**Manual Indexing**: If you want to disable auto-indexing or index manually, use:
```bash
badger index /path/to/your/codebase --graphdb-endpoint http://localhost:8080
badger mcp-server --no-auto-index  # Disable auto-indexing
```

## Running the MCP Server Standalone

You can run the MCP server directly for testing (Cursor will auto-start it when configured):

### Method 1: Using the CLI command
```bash
badger mcp-server --graphdb-endpoint http://localhost:8080
```

With verbose logging:
```bash
badger mcp-server --graphdb-endpoint http://localhost:8080 --verbose
```

### Method 2: Direct Python module execution
```bash
python -m badger.mcp.server --graphdb-endpoint http://localhost:8080
```

Or with your virtual environment:
```bash
/home/william/Documents/codingProj/badger/cli/venv/bin/python -m badger.mcp.server --graphdb-endpoint http://localhost:8080
```

With verbose logging:
```bash
python -m badger.mcp.server --graphdb-endpoint http://localhost:8080 --verbose
```

**Alternative:** You can also use the `BADGER_GRAPHDB_ENDPOINT` environment variable:
```bash
export BADGER_GRAPHDB_ENDPOINT=http://localhost:8080
python -m badger.mcp.server
```

## Testing the MCP Server

1. **Open Cursor AI Chat:**
   - Press `Cmd+L` (Mac) or `Ctrl+L` (Windows/Linux)

2. **Try these queries:**
   - "Find all usages of the function `main`"
   - "What files include `stdio.h`?"
   - "Find all places where struct `MyStruct` field `value` is accessed"
   - "Who calls the function `process_data`?"
   - "Search for code related to buffer allocation"
   - "What files would be affected if I change `utils.c`?"

3. **Check server logs:**
   - If the server doesn't work, check the Cursor output panel
   - Or run the server manually to see errors:
     ```bash
     badger mcp-server --graphdb-endpoint http://localhost:8080 --verbose
     ```

## Available Tools

The MCP server provides these tools:

1. **find_symbol_usages** - Find all usages of functions, macros, variables, structs, or typedefs
   - ✅ Works for **Python** (functions, variables, classes)
   - ✅ Works for **C** (functions, macros, variables, structs, typedefs)
   
2. **get_include_dependencies** - Get transitive include dependencies for header files
   - ✅ Works for **Python** (import statements)
   - ✅ Works for **C** (include directives)
   
3. **find_struct_field_access** - Find all places where a struct field is accessed
   - ❌ **C-specific only** (Python uses classes, not structs)
   
4. **get_function_callers** - Find all callers of a function (direct and indirect)
   - ✅ Works for **Python** (function calls)
   - ✅ Works for **C** (function calls)
   
5. **semantic_code_search** - Search code by semantic meaning using embeddings
   - ✅ Works for **Python** (searches functions and classes)
   - ✅ Works for **C** (searches functions and structs/classes)
   
6. **check_affected_files** - Find files affected by changes (transitive dependencies + call graph)
   - ✅ Works for **Python** (imports + function calls)
   - ✅ Works for **C** (includes + function calls)

## Language Support

**Python Support:**
- ✅ Functions, classes, variables, imports
- ✅ Function callers, semantic search, affected files
- ❌ Macros, structs, typedefs (C-only features)

**C Support:**
- ✅ All features: functions, macros, variables, structs, typedefs
- ✅ Struct field access tracking
- ✅ Include dependency traversal

**Note:** The tools query the graph database which contains data from both Python and C parsers. As long as your codebase has been indexed with both parsers, the tools will work for both languages automatically.

## Troubleshooting

### Server won't start:
- Check that the Python path is correct
- Verify Dgraph is running: `curl http://localhost:8080/health`
- Check environment variables are set correctly
- Run the server manually with `--verbose` to see errors:
  ```bash
  badger mcp-server --graphdb-endpoint http://localhost:8080 --verbose
  ```

### Tools not being called by Cursor:
1. **Check Cursor MCP status:**
   - Go to Settings > Features > MCP
   - Verify the server is listed and enabled
   - Check if there are any error messages

2. **Check Cursor logs:**
   - Open Developer Tools: Help > Toggle Developer Tools
   - Check the Console tab for MCP-related errors

3. **Verify server is running:**
   - The server should start automatically when Cursor opens
   - Check if the process is running: `ps aux | grep badger`

4. **Test server manually:**
   - Run with verbose logging to see if tools are registered:
     ```bash
     badger mcp-server --graphdb-endpoint http://localhost:8080 --verbose
     ```
   - You should see: "MCP server ready with 6 tools"

5. **Check workspace path:**
   - Ensure `BADGER_WORKSPACE_PATH` matches the actual workspace
   - The server logs will show: "Using workspace: /path/to/workspace"

6. **Try explicit tool invocation:**
   - In Cursor AI Chat, try: "Use the find_symbol_usages tool to find all usages of struct MyStruct"
   - Or: "Call find_struct_field_access for struct User and field name"

### Tools return no results:
- The server auto-indexes on startup - check logs for indexing errors
- Verify the graph database contains data by querying directly
- Ensure the namespace matches (check server logs for namespace ID)

### Import errors:**
- Make sure `mcp>=1.0.0` is installed: `pip install mcp>=1.0.0`
- Check all dependencies: `pip install -r requirements.txt`

### Debugging Tips:
- Enable verbose logging: Add `--verbose` flag or set log level to DEBUG
- Check server logs in Cursor's output panel
- Test tools manually by running the server standalone
- Verify Dgraph connection: The server validates connection on startup

