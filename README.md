# Badger - Code Graph Database for MCP

Badger is a code graph database that indexes your codebase and provides powerful querying tools via the Model Context Protocol (MCP). It supports both C and Python codebases.

## Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd badger
```

### 2. Install Dependencies

```bash
cd cli
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### 3. Initialize the Graph Database

This command will:
- Check if Docker is installed and running
- Start a local Dgraph container (default: http://localhost:8080)
- Set up the GraphQL schema
- Save configuration to `.badgerrc`

```bash
badger init_graph
```

For a remote server, use:
```bash
badger init_graph --endpoint http://remote-server:8080
```

**Prerequisites:** Docker must be installed. Get it from https://docs.docker.com/get-docker/

**Note:** By default, Badger uses the local Dgraph endpoint. The endpoint is saved to `.badgerrc` and used by all commands automatically.

### 4. Index Your Codebase

```bash
badger index
```

This will:
- Parse all source files in the current directory
- Extract functions, classes, imports, relationships
- Store everything in the graph database

### 5. Set Up MCP in Cursor

```bash
badger mcp
```

This command will:
- Display step-by-step instructions
- Generate the JSON configuration for Cursor
- Save the config to `.badger-mcp-config.json` for easy copying

Then:
1. Open Cursor Settings (Cmd/Ctrl + ,)
2. Search for "MCP" or go to Extensions → MCP
3. Add the JSON configuration shown by `badger mcp`
4. Restart Cursor

## Commands

### `badger init_graph`

Initialize the graph database (Dgraph). By default, starts a local Dgraph container.

```bash
badger init_graph [--endpoint URL] [--port 8080] [--skip-docker]
```

Options:
- `--endpoint`: Dgraph endpoint URL (default: http://localhost:8080 for local Docker container)
- `--port`: HTTP port for Dgraph (default: 8080)
- `--grpc-port`: gRPC port for Dgraph (default: 9080)
- `--skip-docker`: Skip Docker setup, just configure endpoint

**Examples:**
- Local (default): `badger init_graph`
- Remote server: `badger init_graph --endpoint http://remote-server:8080`

**Data Persistence:**
- Data is automatically persisted to `.badger-data/dgraph/` in your project directory
- Data persists across container stops/restarts
- Use `badger stop_graph` to stop the container (data is preserved)
- Use `badger start_graph` to restart the container

### `badger index`

Index a codebase and store it in the graph database. Uses the local endpoint from `.badgerrc` by default.

```bash
badger index [directory] [--language python|c] [--endpoint URL] [--verbose]
```

Options:
- `directory`: Directory to index (default: current directory)
- `--language`: Language to parse (python, c). Auto-detect if not specified
- `--endpoint`: Override graph database endpoint (default: local from `.badgerrc` or http://localhost:8080)
- `--verbose`: Enable verbose output

**Examples:**
- Use local endpoint: `badger index`
- Use remote endpoint: `badger index --endpoint http://remote-server:8080`

### `badger mcp`

Show MCP setup instructions and configuration for Cursor.

```bash
badger mcp [--workspace PATH] [--endpoint URL]
```

Options:
- `--workspace`: Path to workspace (default: current directory)
- `--endpoint`: Dgraph endpoint URL

### `badger stats`

Show node counts in the graph database. Uses the local endpoint from `.badgerrc` by default.

```bash
badger stats [--endpoint URL]
```

### `badger clear`

Clear all data from the graph database. Uses the local endpoint from `.badgerrc` by default.

```bash
badger clear [--endpoint URL] [--yes]
```

**Warning:** This will delete ALL nodes and relationships!

### `badger stop_graph`

Stop the local Dgraph container. Data is preserved in `.badger-data/dgraph/`.

```bash
badger stop_graph [--container dgraph]
```

### `badger start_graph`

Start a previously stopped Dgraph container. All data is preserved.

```bash
badger start_graph [--container dgraph]
```

### `badger status_graph`

Show the status of the local Dgraph container.

```bash
badger status_graph [--container dgraph]
```

## Data Persistence

**How it works:**
- When you run `badger init_graph`, a Docker volume is created that maps `.badger-data/dgraph/` to `/dgraph` in the container
- All Dgraph data is stored in `.badger-data/dgraph/` in your project directory
- Data persists across:
  - Container stops/restarts
  - System reboots (container auto-restarts with `--restart unless-stopped`)
  - Container removal (as long as you don't delete `.badger-data/`)

**Lifecycle:**
1. `badger init_graph` - Creates container with persistent volume
2. `badger index` - Indexes codebase, data saved to `.badger-data/dgraph/`
3. `badger stop_graph` - Stops container, data remains in `.badger-data/dgraph/`
4. `badger start_graph` - Restarts container, loads data from `.badger-data/dgraph/`

**To completely remove data:**
```bash
badger stop_graph
rm -rf .badger-data/dgraph
```

## Features

- **Multi-language Support**: Python and C/C++
- **Rich Code Analysis**: Functions, classes, imports, macros, typedefs, struct field accesses
- **Relationship Tracking**: Function calls, inheritance, imports/includes
- **Semantic Search**: Vector embeddings for natural language queries
- **MCP Integration**: Works seamlessly with Cursor and other MCP-compatible tools

## Configuration

Configuration is stored in `.badgerrc` in your project directory:

```yaml
graphdb_endpoint: http://localhost:8080
language: python  # optional
verbose: false
```

You can also set environment variables with the `BADGER_` prefix:
- `BADGER_GRAPHDB_ENDPOINT`
- `BADGER_LANGUAGE`
- `BADGER_VERBOSE`

## MCP Tools

Badger provides the following MCP tools:

- `find_symbol_usages` - Find all usages of a symbol (function, macro, variable, struct, typedef)
- `get_function_callers` - Find all callers of a function
- `get_include_dependencies` - Get files that import/include a file
- `find_struct_field_access` - Find struct field accesses (C only)
- `check_affected_files` - Find files affected by changes
- `semantic_code_search` - Search code by semantic meaning

## Development

See [DEVELOPMENT.md](cli/DEVELOPMENT.md) for development setup and contributing guidelines.

## License

[Your License Here]
