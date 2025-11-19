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

All commands use the local Dgraph endpoint from `.badgerrc` by default. You can override this with the `--endpoint` option on most commands.

### `badger init_graph`

Initialize the graph database (Dgraph). By default, starts a local Dgraph container.

```bash
badger init_graph [--endpoint URL] [--compose-file PATH] [--skip-docker]
```

Options:
- `--endpoint`: Dgraph endpoint URL (default: http://localhost:8080 for local Docker container)
- `--compose-file`: Path to docker-compose.yml (default: `dgraph/docker-compose.yml`)
- `--skip-docker`: Skip Docker setup, just configure endpoint

**What it does:**
1. Checks if Docker is installed and running
2. Starts Dgraph using docker-compose (from `dgraph/docker-compose.yml`)
3. Sets up the GraphQL schema
4. Saves configuration to `.badgerrc`

**Examples:**
- Local (default): `badger init_graph`
- Remote server: `badger init_graph --endpoint http://remote-server:8080 --skip-docker`
- Custom compose file: `badger init_graph --compose-file /path/to/docker-compose.yml`

**Data Persistence:**
- Data is automatically persisted to `dgraph/dgraph-data/` in your project directory
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

This command:
- Displays step-by-step setup instructions
- Generates the JSON configuration for Cursor
- Saves the config to `.badger-mcp-config.json` for easy copying

### `badger mcp-server`

Start the MCP server manually (typically invoked automatically by Cursor).

```bash
badger mcp-server [--endpoint URL] [--workspace PATH] [--auto-index] [--verbose]
```

Options:
- `--endpoint`: Graph database endpoint URL (default: local from `.badgerrc` or http://localhost:8080)
- `--workspace`: Path to workspace/codebase root (default: current directory)
- `--auto-index`: Enable automatic indexing on startup
- `--verbose`: Enable verbose logging

**Note:** This command is typically invoked automatically by Cursor when configured. You can run it manually for testing.

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

Stop the local Dgraph container using docker-compose. Data is preserved.

```bash
badger stop_graph [--compose-file PATH]
```

Options:
- `--compose-file`: Path to docker-compose.yml (default: `dgraph/docker-compose.yml`)

**Note:** This stops the container but preserves all data. The data is stored in `dgraph/dgraph-data` and persists across stops/restarts.

### `badger start_graph`

Start a previously stopped Dgraph container using docker-compose. All data is preserved.

```bash
badger start_graph [--compose-file PATH]
```

Options:
- `--compose-file`: Path to docker-compose.yml (default: `dgraph/docker-compose.yml`)

**Note:** This starts a previously stopped container. All data is preserved from when the container was last running.

### `badger status_graph`

Show the status of the local Dgraph container.

```bash
badger status_graph [--compose-file PATH]
```

Options:
- `--compose-file`: Path to docker-compose.yml (default: `dgraph/docker-compose.yml`)

Shows whether the container is running, stopped, or exited.

## Data Persistence

**How it works:**
- When you run `badger init_graph`, Docker Compose creates a volume that maps `dgraph/dgraph-data/` to `/dgraph` in the container
- All Dgraph data is stored in `dgraph/dgraph-data/` in your project directory
- Data persists across:
  - Container stops/restarts
  - System reboots (container auto-restarts with `restart: unless-stopped`)
  - Container removal (as long as you don't delete `dgraph/dgraph-data/`)

**Lifecycle:**
1. `badger init_graph` - Creates container with persistent volume using docker-compose
2. `badger index` - Indexes codebase, data saved to `dgraph/dgraph-data/`
3. `badger stop_graph` - Stops container, data remains in `dgraph/dgraph-data/`
4. `badger start_graph` - Restarts container, loads data from `dgraph/dgraph-data/`
5. `badger status_graph` - Check if container is running

**To completely remove data:**
```bash
badger stop_graph
rm -rf dgraph/dgraph-data
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
