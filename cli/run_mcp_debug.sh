#!/bin/bash
# Run MCP server with verbose logging to see all output

cd /home/william/Documents/codingProj/badger/cli

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run with verbose logging
python -m badger.mcp.server --graphdb-endpoint http://localhost:8080 --verbose
