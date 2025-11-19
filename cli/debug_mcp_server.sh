#!/bin/bash
# Debug script to run MCP server manually and see all logs
# This allows you to debug the server while Cursor can still connect to it

cd /home/william/Documents/codingProj/badger/cli

# Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set environment variables
export BADGER_GRAPHDB_ENDPOINT="http://localhost:8080"
export BADGER_WORKSPACE_PATH="/home/william/Documents/codingProj/tinyweb/CTinyWeb"

# Run server with verbose logging
# All logs go to stderr (which is allowed by MCP protocol)
# stdout is reserved for MCP protocol communication
python -m badger.mcp.server \
    --graphdb-endpoint "$BADGER_GRAPHDB_ENDPOINT" \
    --workspace "$BADGER_WORKSPACE_PATH" \
    --verbose 2>&1 | tee mcp_server.log

