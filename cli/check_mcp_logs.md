# How to Check MCP Server Logs

## Method 1: View Logs in Cursor

1. **Open Cursor Settings**
   - Press `Cmd/Ctrl + ,` to open settings
   - Or go to `File > Preferences > Settings`

2. **Find MCP Server Logs**
   - Search for "MCP" in settings
   - Look for "MCP Server Logs" or "Developer Tools"
   - Or check the Output panel: `View > Output` and select "MCP" from the dropdown

3. **Check Cursor's Developer Console**
   - Press `Cmd/Ctrl + Shift + P` to open command palette
   - Type "Developer: Toggle Developer Tools"
   - Look for MCP-related messages in the console

## Method 2: Run Server Manually (Best for Debugging)

Run the server directly in a terminal to see all logs:

```bash
cd /home/william/Documents/codingProj/badger/cli

# Activate your virtual environment first
source venv/bin/activate  # or whatever your venv path is

# Run the server with verbose logging
python -m badger.mcp.server --verbose
```

This will show you:
- Connection status
- Tool registration
- Any errors
- All log messages

## Method 3: Test Server Directly

Use the test script to verify tools are registered:

```bash
cd /home/william/Documents/codingProj/badger/cli
python test_mcp_connection.py
```

## Method 4: Check Cursor's MCP Configuration

The MCP server configuration is usually in:
- `~/.cursor/mcp.json` (Linux/Mac)
- Or in Cursor's settings JSON

Make sure it's configured correctly to point to your server.

