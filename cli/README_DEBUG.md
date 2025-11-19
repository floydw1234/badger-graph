# Debugging MCP Server

## Current Setup

Your MCP server is configured to log to a file: `cli/mcp_server.log`

## How to View Logs

### Option 1: Watch the log file in real-time (Recommended)

In a terminal, run:
```bash
cd /home/william/Documents/codingProj/badger/cli
tail -f mcp_server.log
```

This will show all logs as they happen. Press `Ctrl+C` to stop.

### Option 2: View logs in Cursor

1. Open Output panel: `View > Output` (or `Ctrl+Shift+U`)
2. Select "MCP" or "Badger" from dropdown
3. You'll see all server logs there

### Option 3: Check the log file

```bash
cd /home/william/Documents/codingProj/badger/cli
cat mcp_server.log
# or
less mcp_server.log
```

## What to Look For

When the server starts successfully, you should see:
```
INFO - Creating MCP server
INFO - MCP server ready with 6 tools:
INFO -   - find_symbol_usages: Find all usages of a symbol...
INFO -   - get_include_dependencies: Get all files that transitively...
INFO -   - find_struct_field_access: Find all places where...
INFO -   - get_function_callers: Find all callers of a function...
INFO -   - semantic_code_search: Search for code by semantic...
INFO -   - check_affected_files: Given a list of changed files...
INFO - Starting MCP server with stdio transport
```

## Restarting the Server

After making changes to the code:
1. Restart Cursor (or reload the MCP server)
2. The server will restart automatically
3. Check the logs to verify it started correctly

## Testing Tools Manually

Run the test script:
```bash
cd /home/william/Documents/codingProj/badger/cli
python test_mcp_connection.py
```

This will verify that all 6 tools are registered correctly.

