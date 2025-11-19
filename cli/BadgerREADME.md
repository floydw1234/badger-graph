# Badger CLI

Interactive coding agent for LLMs using tree-sitter and Dgraph.

## Installation

```bash
cd cli
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Usage

Simply run `badger` in any directory:

```bash
badger
```

Badger will:
1. **Prompt for graph database endpoint** (on first run, if not configured)
2. **Automatically index** all source files in the current directory
3. **Automatically update** the graph database with parsed code relationships
4. Start an interactive agent ready to help with your codebase

### First Run Setup

On first run, Badger will prompt you for your graph database endpoint:
```
Enter graph database endpoint [http://localhost:8080]:
```

The configuration is saved to `.badgerrc` in your project directory.

### Options

```bash
# Work in a specific directory
badger --dir /path/to/codebase

# Filter by language
badger --language python

# Enable verbose output
badger --verbose

# Override graph database endpoint
badger --graphdb-endpoint http://localhost:8080
```

### Interactive Commands

Once in the agent, you can:

- **Type natural language queries** - Ask about your codebase
- **`/read <file>`** - Read a file
- **`/index`** - Re-index the current directory
- **`/help`** - Show available commands
- **`exit` or `quit`** - Exit the agent

### Example Session

```
$ badger

Welcome
┌─────────────────────────────────────────┐
│ Badger - Interactive Coding Agent        │
│                                         │
│ Working directory: /home/user/project   │
└─────────────────────────────────────────┘

Indexing codebase...
Indexing Complete
Files indexed: 42
Functions found: 156
Classes found: 23
Imports found: 89

Badger Agent Ready
Type your requests. Type 'exit' or 'quit' to leave.

You: What does the getUserData function do?
[Agent queries graph and provides context...]

You: /read src/main.py
[Shows file contents...]

You: exit
Goodbye!
```

## Configuration

Configuration is automatically saved to `.badgerrc` in your project directory.

Configuration can be set via:

1. **Interactive prompt** (on first run) - Badger will ask for the graph database endpoint
2. **Command-line option** - `--graphdb-endpoint` to override
3. **Environment variables** (prefix with `BADGER_`):
   ```bash
   export BADGER_GRAPHDB_ENDPOINT=http://localhost:8080
   export BADGER_LANGUAGE=python
   export BADGER_VERBOSE=true
   ```
4. **Configuration file** (`.badgerrc` in project root):
   ```yaml
   graphdb_endpoint: http://localhost:8080
   language: python
   verbose: false
   ```

Command-line options override config file and environment variables.

## Output

Indexing creates a `.badger-index/` directory with:

- `index.json` - Summary of indexed files
- `relationships.json` - Extracted relationships
- `files/*.json` - Individual file parse results

## Supported Languages

- Python (`.py`)
- C (`.c`, `.h`)

More languages can be added by implementing the `BaseParser` interface.

## Future Features

The agent will integrate with:
- **vllm** for local LLM inference
- **qwen-3 coder 30b** for graph query generation
- **gpt-oss 120b** for code understanding and editing
- **MCP server** for GraphQL queries to Dgraph
- **Tool calls** for reading, editing, and querying files
