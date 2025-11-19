# Badger Graph Viewer

A Flask web application for visualizing and searching your code graph stored in Dgraph using Cytoscape.js.

## Features

- **Interactive Graph Visualization**: View your code graph with nodes for files, functions, and classes
- **Text Search**: Search for nodes by function name, class name, or file path
- **Node Details**: Click on any node to see detailed information
- **Relationship Visualization**: See relationships between code elements (contains, calls, inherits)

## Installation

1. Install Flask:
```bash
pip install -r requirements.txt
```

2. Make sure your Dgraph instance is running (default: `http://localhost:8080`)

3. The app will automatically use your Badger configuration (`.badgerrc`) to connect to Dgraph, or you can set the `BADGER_GRAPHDB_ENDPOINT` environment variable.

## Usage

1. Start the Flask app:
```bash
cd /home/william/Documents/codingProj/badger/cli/graph-viewer
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000          # Cytoscape.js graph viewer
http://localhost:5000/voyager  # GraphQL Voyager schema viewer (schema structure only)
http://localhost:5000/explorer # GraphiQL explorer (query live data)
```

3. Use the interface:

**GraphiQL Explorer (`/explorer`):**
   - **Live Data Querying**: Write and execute GraphQL queries against your actual graph data
   - **Interactive Documentation**: Auto-complete and schema documentation
   - **Query Examples**: Pre-loaded example queries to get started
   - **Perfect for**: Exploring actual data in your graph, verifying parser/insertion logic with real queries

**GraphQL Voyager (`/voyager`):**
   - **Schema Visualization**: Interactive graph showing your GraphQL schema structure
   - **Type Exploration**: Click on any type to see its fields and relationships
   - **Relationship Mapping**: Visualize how types connect through fields
   - **Note**: Shows schema structure only, not actual data

**Cytoscape.js Viewer (`/`):**
   - **Load Full Graph**: Loads all nodes and relationships from Dgraph
   - **Search**: Type in the search box to find specific functions, classes, or files
   - **Click Nodes**: Click on any node to see detailed information in the side panel
   - **Reset View**: Resets the zoom and pan to fit all nodes

## Node Types

- **Blue Rectangles**: Files
- **Green Circles**: Functions
- **Orange Diamonds**: Classes

## Edge Types

- **Gray Arrows**: Contains relationships (file contains function/class)
- **Red Dashed Arrows**: Function calls
- **Purple Arrows**: Class inheritance

## API Endpoints

- `GET /` - Main Cytoscape.js visualization page
- `GET /voyager` - GraphQL Voyager schema visualization page (schema structure only)
- `GET /explorer` - GraphiQL explorer for querying live data
- `GET /api/graph` - Get full graph data
- `GET /api/search?q=<query>` - Search for nodes
- `GET /api/node/<node_id>` - Get detailed node information

