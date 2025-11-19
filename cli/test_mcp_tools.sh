#!/bin/bash
# Test MCP server tool registration

cd /home/william/Documents/codingProj/badger/cli

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run test script
python test_mcp_connection.py
