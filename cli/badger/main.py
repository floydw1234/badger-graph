"""Main CLI entry point for Badger - Code graph database for MCP."""

import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from difflib import unified_diff

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax

from .config import load_config, save_config, BadgerConfig
from .parsers import PythonParser, CParser, BaseParser
from .utils import find_source_files, detect_language, read_file_content
from .graph import build_graph, DgraphClient, GraphData
from .query import parse_query
from .mcp.server import run_mcp_server

app = typer.Typer(help="Badger - Code graph database for MCP")
console = Console()


def get_parser(language: str) -> BaseParser:
    """Get parser for specified language."""
    if language == "python":
        return PythonParser()
    elif language == "c":
        return CParser()
    else:
        raise ValueError(f"Unsupported language: {language}")


def index_directory(
    directory: Path,
    config: BadgerConfig,
    language: Optional[str] = None,
    dgraph_client: Optional[DgraphClient] = None,
    strict_validation: bool = True
) -> tuple[list, GraphData]:
    """Index a directory and return parse results and graph data."""
    console.print(f"[dim]Indexing directory: {directory}[/dim]")
    
    # Find source files
    source_files = find_source_files(directory, language=language)
    
    if not source_files:
        console.print("[yellow]No source files found[/yellow]")
        return [], GraphData()
    
    # Parse files
    parse_results = []
    parsers: dict[str, BaseParser] = {}
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("Parsing files...", total=len(source_files))
        
        for file_path in source_files:
            # Detect or use specified language
            file_language = language or detect_language(file_path)
            
            if not file_language:
                progress.update(task, advance=1)
                continue
            
            # Get or create parser
            if file_language not in parsers:
                try:
                    parsers[file_language] = get_parser(file_language)
                except Exception as e:
                    if config.verbose:
                        console.print(f"[red]Failed to initialize {file_language} parser: {e}[/red]")
                    progress.update(task, advance=1)
                    continue
            
            parser = parsers[file_language]
            
            # Parse file
            try:
                result = parser.parse_file(file_path)
                parse_results.append(result)
            except Exception as e:
                if config.verbose:
                    console.print(f"[red]Failed to parse {file_path}: {e}[/red]")
            
            progress.update(task, advance=1)
    
    if not parse_results:
        return [], GraphData()
    
    # Build graph
    graph_data = build_graph(parse_results)
    
    # Save to .badger-index directory
    output_dir = directory / ".badger-index"
    output_dir.mkdir(exist_ok=True)
    
    files_dir = output_dir / "files"
    files_dir.mkdir(exist_ok=True)
    
    # Save individual file results
    for result in parse_results:
        file_name = Path(result.file_path).stem + ".json"
        file_output = files_dir / file_name
        with open(file_output, "w") as f:
            json.dump({
                "filePath": result.file_path,
                "functions": [
                    {
                        "name": func.name,
                        "start": {"row": func.start.row, "column": func.start.column},
                        "end": {"row": func.end.row, "column": func.end.column}
                    }
                    for func in result.functions
                ],
                "classes": [
                    {
                        "name": cls.name,
                        "start": {"row": cls.start.row, "column": cls.start.column},
                        "end": {"row": cls.end.row, "column": cls.end.column}
                    }
                    for cls in result.classes
                ],
                "imports": [
                    {
                        "text": imp.text,
                        "start": {"row": imp.start.row, "column": imp.start.column},
                        "end": {"row": imp.end.row, "column": imp.end.column}
                    }
                    for imp in result.imports
                ],
                "totalNodes": result.total_nodes
            }, f, indent=2)
    
    # Save summary index
    summary = {
        "generatedAt": graph_data.generated_at,
        "totalFiles": len(parse_results),
        "totalFunctions": len(graph_data.functions),
        "totalClasses": len(graph_data.classes),
        "totalImports": len(graph_data.imports),
        "files": graph_data.files
    }
    
    summary_file = output_dir / "index.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    # Save relationships
    relationships_file = output_dir / "relationships.json"
    with open(relationships_file, "w") as f:
        json.dump({
            "generatedAt": graph_data.generated_at,
            "functions": graph_data.functions,
            "classes": graph_data.classes,
            "imports": graph_data.imports,
            "calls": []
        }, f, indent=2)
    
    # Automatically save to graph database if client is available
    if dgraph_client:
        console.print("[dim]Updating graph database...[/dim]")
        try:
            # Initialize hash cache for incremental indexing
            from .graph.hash_cache import HashCache
            cache_file = output_dir / "node_hashes.json"
            hash_cache = HashCache(cache_file)
            
            if hash_cache.get_cache_size() > 0:
                console.print(f"[dim]Hash cache: {hash_cache.get_cache_size()} nodes cached[/dim]")
            
            if dgraph_client.insert_graph(graph_data, strict_validation=strict_validation, hash_cache=hash_cache):
                console.print("[green]✓ Graph database updated[/green]")
            else:
                console.print("[yellow]⚠ Graph database update not yet implemented[/yellow]")
        except ValueError as e:
            # Validation error in strict mode
            console.print(f"[red]Validation error: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error updating graph database: {e}[/red]")
            raise typer.Exit(1)
    
    return parse_results, graph_data


def tool_read_file(file_path: Path) -> str:
    """Tool: Read a file and return its contents."""
    try:
        return read_file_content(file_path)
    except Exception as e:
        return f"Error reading file: {e}"


def tool_edit_file(file_path: Path, new_content: str, show_preview: bool = True) -> bool:
    """Tool: Edit a file with preview and approval."""
    if not file_path.exists():
        console.print(f"[red]Error: File {file_path} does not exist[/red]")
        return False
    
    try:
        old_content = read_file_content(file_path)
        
        if show_preview:
            # Show diff preview
            console.print(f"\n[cyan]Preview of changes to {file_path}:[/cyan]")
            
            diff = unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(file_path),
                tofile=str(file_path),
                lineterm=""
            )
            
            diff_text = "".join(diff)
            console.print(Syntax(diff_text, "diff", theme="monokai"))
            
            # Ask for approval
            if not Confirm.ask("\n[bold]Apply these changes?[/bold]", default=False):
                console.print("[yellow]Changes cancelled[/yellow]")
                return False
        
        # Write file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        console.print(f"[green]✓ File {file_path} updated[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]Error editing file: {e}[/red]")
        return False


def tool_query_graph(query_text: str, graph_data: GraphData, dgraph_client: Optional[DgraphClient] = None) -> Dict[str, Any]:
    """Tool: Query the code graph for context."""
    # Parse query to extract code elements
    query_elements = parse_query(query_text)
    
    # If Dgraph client is available, use it first
    if dgraph_client:
        dgraph_results = dgraph_client.query_context({
            "functions": query_elements.functions,
            "classes": query_elements.classes,
            "variables": query_elements.variables
        })
        if dgraph_results:
            return dgraph_results
    
    # Fallback: search in-memory graph data
    results = {
        "functions": [],
        "classes": [],
        "files": []
    }
    
    # Simple text matching for now
    query_lower = query_text.lower()
    
    for func in graph_data.functions:
        if query_lower in func["name"].lower():
            results["functions"].append(func)
    
    for cls in graph_data.classes:
        if query_lower in cls["name"].lower():
            results["classes"].append(cls)
    
    return results


def interactive_agent(
    directory: Path,
    config: BadgerConfig,
    graph_data: GraphData,
    dgraph_client: Optional[DgraphClient] = None
):
    """Run interactive agent loop."""
    console.print("\n[bold green]Badger Agent Ready[/bold green]")
    console.print("[dim]Type your requests. Type 'exit' or 'quit' to leave.[/dim]\n")
    
    while True:
        try:
            # Get user input
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
            
            if not user_input.strip():
                continue
            
            # Handle exit commands
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("[yellow]Goodbye![/yellow]")
                break
            
            # Handle special commands
            if user_input.startswith("/"):
                if user_input == "/help":
                    console.print(Panel(
                        "[bold]Available commands:[/bold]\n\n"
                        "[cyan]/help[/cyan] - Show this help\n"
                        "[cyan]/read <file>[/cyan] - Read a file\n"
                        "[cyan]/index[/cyan] - Re-index the current directory\n"
                        "[cyan]/exit[/cyan] - Exit the agent",
                        title="Help"
                    ))
                    continue
                elif user_input.startswith("/read "):
                    file_path = Path(user_input[6:].strip())
                    if not file_path.is_absolute():
                        file_path = directory / file_path
                    content = tool_read_file(file_path)
                    console.print(Syntax(content, detect_language(file_path) or "text", theme="monokai"))
                    continue
                elif user_input == "/index":
                    console.print("[yellow]Re-indexing directory...[/yellow]")
                    dgraph_client = DgraphClient(config.graphdb_endpoint) if config.graphdb_endpoint else None
                    _, graph_data = index_directory(directory, config, dgraph_client=dgraph_client, strict_validation=True)
                    console.print("[green]Indexing complete[/green]\n")
                    continue
            
            # Process natural language query
            console.print("\n[dim]Processing query...[/dim]")
            
            # Query graph for context
            context = tool_query_graph(user_input, graph_data, dgraph_client)
            
            # Display context if found
            if context.get("functions") or context.get("classes"):
                console.print("\n[cyan]Relevant context found:[/cyan]")
                
                if context.get("functions"):
                    console.print("\n[bold]Functions:[/bold]")
                    for func in context["functions"][:5]:  # Show top 5
                        console.print(f"  • {func['name']} in {func['file']} (line {func['line']})")
                
                if context.get("classes"):
                    console.print("\n[bold]Classes:[/bold]")
                    for cls in context["classes"][:5]:  # Show top 5
                        console.print(f"  • {cls['name']} in {cls['file']} (line {cls['line']})")
            
            # TODO: Here you would:
            # 1. Send query to LLM (qwen-3 coder 30b) to create graph query
            # 2. Execute graph query to get context
            # 3. Send user input + context to LLM (gpt-oss 120b)
            # 4. LLM responds with tool calls (read_file, edit_file, query_graph)
            # 5. Execute tool calls with user approval
            # 6. Show previews before applying changes
            
            console.print("\n[yellow]Agent response (LLM integration not yet implemented)[/yellow]")
            console.print("[dim]In the future, the agent will:\n"
                         "  - Query the graph for relevant context\n"
                         "  - Use LLM to understand your request\n"
                         "  - Propose code changes with previews\n"
                         "  - Apply changes after your approval[/dim]\n")
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
        except EOFError:
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@app.command("init_graph")
def init_graph(
    endpoint: Optional[str] = typer.Option(None, "--endpoint", "-e", help="Dgraph endpoint URL (default: http://localhost:8080 for local Docker container)"),
    compose_file: Optional[Path] = typer.Option(None, "--compose-file", "-f", help="Path to docker-compose.yml (default: dgraph/docker-compose.yml)"),
    skip_docker: bool = typer.Option(False, "--skip-docker", help="Skip Docker setup, just configure endpoint"),
):
    """Initialize the graph database (Dgraph).
    
    This command:
    1. Checks if Docker is installed and running
    2. Starts Dgraph using docker-compose (from dgraph/docker-compose.yml)
    3. Sets up the GraphQL schema
    4. Saves configuration to .badgerrc
    
    Prerequisites:
    - Docker and docker-compose must be installed and running
    """
    import subprocess
    import time
    
    # Use endpoint from config if not provided, default to local
    work_dir = Path.cwd()
    config = load_config(directory=work_dir)
    if not endpoint:
        endpoint = config.graphdb_endpoint or "http://localhost:8080"
    
    # Check Docker
    if not skip_docker:
        console.print("[cyan]Checking Docker...[/cyan]")
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            console.print(f"[green]✓[/green] {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            console.print("[red]✗ Docker is not installed or not in PATH[/red]")
            console.print("[yellow]Please install Docker: https://docs.docker.com/get-docker/[/yellow]")
            raise typer.Exit(1)
        
        # Check for docker-compose
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                check=True
            )
            console.print(f"[green]✓[/green] Docker Compose available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            console.print("[red]✗ Docker Compose is not available[/red]")
            console.print("[yellow]Please ensure Docker Compose is installed (usually included with Docker Desktop)[/yellow]")
            raise typer.Exit(1)
        
        # Check if Docker daemon is running
        try:
            subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                check=True
            )
            console.print("[green]✓ Docker daemon is running[/green]")
        except subprocess.CalledProcessError:
            console.print("[red]✗ Docker daemon is not running[/red]")
            console.print("[yellow]Please start Docker Desktop or the Docker daemon[/yellow]")
            raise typer.Exit(1)
        
        # Find docker-compose.yml file
        if compose_file:
            compose_path = Path(compose_file).resolve()
        else:
            # Look for dgraph/docker-compose.yml relative to current directory
            compose_path = work_dir / "dgraph" / "docker-compose.yml"
            if not compose_path.exists():
                # Try looking in parent directories
                for parent in work_dir.parents:
                    candidate = parent / "dgraph" / "docker-compose.yml"
                    if candidate.exists():
                        compose_path = candidate
                        break
        
        if not compose_path.exists():
            console.print(f"[red]✗ docker-compose.yml not found[/red]")
            console.print(f"[yellow]Expected at: {compose_path}[/yellow]")
            console.print("[yellow]Use --compose-file to specify a different path[/yellow]")
            raise typer.Exit(1)
        
        compose_dir = compose_path.parent
        console.print(f"[dim]Using docker-compose.yml: {compose_path}[/dim]")
        
        # Check if Dgraph container is already running
        console.print("[cyan]Checking for existing Dgraph container...[/cyan]")
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "ps", "--format", "json"],
            cwd=compose_dir,
            capture_output=True,
            text=True
        )
        
        # Check if any service is running
        import json
        services_running = False
        if result.returncode == 0 and result.stdout.strip():
            try:
                services = json.loads(result.stdout)
                if isinstance(services, list) and len(services) > 0:
                    services_running = any(s.get("State") == "running" for s in services)
            except:
                # Fallback: check container name directly
                result2 = subprocess.run(
                    ["docker", "ps", "--filter", "name=badger-dgraph", "--format", "{{.Names}}"],
                    capture_output=True,
                    text=True
                )
                services_running = bool(result2.stdout.strip())
        
        if services_running:
            console.print(f"[green]✓ Dgraph container already running[/green]")
        else:
            # Start Dgraph using docker-compose
            console.print("[cyan]Starting Dgraph with docker-compose...[/cyan]")
            
            try:
                result = subprocess.run(
                    ["docker", "compose", "-f", str(compose_path), "up", "-d"],
                    cwd=compose_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                console.print(f"[green]✓ Started Dgraph container[/green]")
                
                # Wait for Dgraph to be ready
                console.print("[cyan]Waiting for Dgraph to be ready...[/cyan]")
                for i in range(30):  # Wait up to 30 seconds
                    try:
                        import requests
                        response = requests.get(f"{endpoint}/health", timeout=2)
                        if response.status_code == 200:
                            console.print("[green]✓ Dgraph is ready![/green]")
                            break
                    except:
                        time.sleep(1)
                        if i % 5 == 0:
                            console.print(f"[dim]Waiting... ({i+1}/30)[/dim]")
                else:
                    console.print("[yellow]⚠ Dgraph may not be fully ready yet. Continuing anyway...[/yellow]")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]✗ Failed to start Dgraph container[/red]")
                console.print(f"[red]{e.stderr}[/red]")
                raise typer.Exit(1)
    
    # Setup schema
    console.print("[cyan]Setting up GraphQL schema...[/cyan]")
    try:
        dgraph_client = DgraphClient(endpoint)
        if dgraph_client.setup_graphql_schema():
            console.print("[green]✓ GraphQL schema setup complete[/green]")
        else:
            console.print("[yellow]⚠ Schema setup may have failed. Continuing anyway...[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠ Could not setup schema: {e}[/yellow]")
        console.print("[yellow]You can run 'badger index' to setup the schema automatically[/yellow]")
    
    # Save configuration (endpoint already set above)
    config.graphdb_endpoint = endpoint
    save_config(config, work_dir)
    
    # Show data persistence info
    compose_path = compose_file if compose_file else (work_dir / "dgraph" / "docker-compose.yml")
    if not compose_path.exists():
        for parent in work_dir.parents:
            candidate = parent / "dgraph" / "docker-compose.yml"
            if candidate.exists():
                compose_path = candidate
                break
    
    data_dir = compose_path.parent / "dgraph-data" if compose_path.exists() else work_dir / ".badger-data" / "dgraph"
    persistence_info = ""
    if not skip_docker:
        persistence_info = f"\nData directory: [cyan]{data_dir}[/cyan]\n"
        persistence_info += "Data persists across container stops/restarts\n"
        persistence_info += "Use [cyan]badger stop_graph[/cyan] to stop the container\n"
        persistence_info += "Use [cyan]badger start_graph[/cyan] to restart it\n"
    
    console.print()
    console.print(Panel(
        f"[bold green]Graph database initialized![/bold green]\n\n"
        f"Endpoint: [cyan]{endpoint}[/cyan]\n"
        f"Config saved to: [cyan]{work_dir / '.badgerrc'}[/cyan]\n"
        f"{persistence_info}"
        f"\nNext steps:\n"
        f"  1. Run [cyan]badger index[/cyan] to index your codebase\n"
        f"  2. Run [cyan]badger mcp[/cyan] to get MCP setup instructions",
        title="Success"
    ))


@app.command()
def index(
    directory: Optional[Path] = typer.Argument(None, help="Directory to index (default: current directory)"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Language to parse (python, c). Auto-detect if not specified"),
    endpoint: Optional[str] = typer.Option(None, "--endpoint", "-e", help="Graph database endpoint URL (default: local from .badgerrc or http://localhost:8080)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Enable strict validation (default: True). If True, fail on validation errors. If False, skip invalid nodes with warnings."),
):
    """Index a codebase and store it in the graph database.
    
    This command parses all source files in the specified directory and stores
    the code graph in Dgraph. The indexed data is then available to the MCP server.
    
    By default, uses the local Dgraph endpoint configured by 'badger init_graph'.
    Use --endpoint to specify a remote server.
    """
    # Determine working directory
    if directory:
        work_dir = Path(directory).resolve()
    else:
        work_dir = Path.cwd()
    
    if not work_dir.exists() or not work_dir.is_dir():
        console.print(f"[red]Error: Directory {work_dir} does not exist or is not a directory[/red]")
        raise typer.Exit(1)
    
    # Load config (with directory to check for local config file)
    config = load_config(directory=work_dir)
    
    # Use endpoint from command line, config, or default to local
    if endpoint:
        config.graphdb_endpoint = endpoint
    elif not config.graphdb_endpoint:
        config.graphdb_endpoint = "http://localhost:8080"
    
    if verbose:
        config.verbose = verbose
    
    # Show indexing info
    console.print(Panel(
        f"[bold green]Badger[/bold green] - Code Graph Indexer\n\n"
        f"Directory: [cyan]{work_dir}[/cyan]\n"
        f"Graph database: [cyan]{config.graphdb_endpoint}[/cyan]",
        title="Indexing"
    ))
    
    # Initialize Dgraph client
    dgraph_client = DgraphClient(config.graphdb_endpoint)
    
    # Index directory (automatically updates graph database)
    console.print("\n[bold]Indexing codebase...[/bold]")
    if strict:
        console.print("[dim]Strict validation: enabled (will fail on validation errors)[/dim]")
    else:
        console.print("[dim]Strict validation: disabled (will skip invalid nodes)[/dim]")
    parse_results, graph_data = index_directory(work_dir, config, language, dgraph_client=dgraph_client, strict_validation=strict)
    
    if not parse_results:
        console.print("[yellow]No files to index.[/yellow]")
        raise typer.Exit(0)
    
    # Show summary
    table = Table(title="Indexing Complete", show_header=False, box=None)
    table.add_column(style="cyan")
    table.add_column(style="green")
    
    table.add_row("Files indexed", str(len(parse_results)))
    table.add_row("Functions found", str(len(graph_data.functions)))
    table.add_row("Classes found", str(len(graph_data.classes)))
    table.add_row("Imports found", str(len(graph_data.imports)))
    if hasattr(graph_data, 'macros') and graph_data.macros:
        table.add_row("Macros found", str(len(graph_data.macros)))
    if hasattr(graph_data, 'variables') and graph_data.variables:
        table.add_row("Variables found", str(len(graph_data.variables)))
    if hasattr(graph_data, 'typedefs') and graph_data.typedefs:
        table.add_row("Typedefs found", str(len(graph_data.typedefs)))
    
    console.print()
    console.print(table)
    console.print()
    console.print(f"[green]✓ Codebase indexed successfully[/green]")


@app.command("mcp")
def mcp(
    workspace_path: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Path to workspace (default: current directory)"),
    endpoint: Optional[str] = typer.Option(None, "--endpoint", "-e", help="Dgraph endpoint URL (default: local from .badgerrc or http://localhost:8080)"),
):
    """Show MCP setup instructions and configuration for Cursor.
    
    This command displays:
    1. Instructions for setting up Badger MCP in Cursor
    2. The JSON configuration to add to Cursor's MCP settings
    """
    # Determine workspace path
    if workspace_path:
        workspace = str(workspace_path.resolve())
    else:
        workspace = str(Path.cwd().resolve())
    
    # Get endpoint from command line, config, or default to local
    config = load_config(directory=Path(workspace))
    if not endpoint:
        endpoint = config.graphdb_endpoint or "http://localhost:8080"
    
    # Get Python path (use the venv if it exists, otherwise system python)
    venv_python = Path(workspace) / "cli" / "venv" / "bin" / "python"
    if venv_python.exists():
        python_path = str(venv_python)
    else:
        python_path = sys.executable
    
    # Get the MCP server script path
    # Use cli/mcp_server_with_logging.py (main entry point)
    repo_root = Path(__file__).parent.parent.parent
    mcp_script = repo_root / "cli" / "mcp_server_with_logging.py"
    
    # If script doesn't exist at that path, try relative to workspace
    if not mcp_script.exists():
        mcp_script = Path(workspace) / "cli" / "mcp_server_with_logging.py"
    
    if not mcp_script.exists():
        console.print("[red]Error: Could not find MCP server script[/red]")
        console.print(f"[yellow]Expected at: {mcp_script}[/yellow]")
        raise typer.Exit(1)
    
    mcp_script_path = str(mcp_script.resolve())
    
    # Generate MCP configuration JSON
    # Note: Cursor MCP config uses "mcpServers" at the top level
    # But we need to provide just the server config, not the wrapper
    mcp_config = {
        "command": python_path,
        "args": [
            mcp_script_path,
            "--endpoint", endpoint,
            "--workspace", workspace
        ]
    }
    
    # Also create the full config for reference
    full_mcp_config = {
        "mcpServers": {
            "badger": mcp_config
        }
    }
    
    # Display instructions
    console.print()
    console.print(Panel(
        "[bold cyan]Badger MCP Setup for Cursor[/bold cyan]\n\n"
        "Follow these steps to add Badger to Cursor:\n\n"
        "1. Open Cursor Settings\n"
        "   - Press [cyan]Cmd/Ctrl + ,[/cyan] to open settings\n"
        "   - Search for 'MCP' or navigate to Extensions → MCP\n\n"
        "2. Add Badger Server\n"
        "   - Click 'Add Server' or edit your MCP settings\n"
        "   - Copy the JSON configuration shown below\n\n"
        "3. Restart Cursor\n"
        "   - Close and reopen Cursor for changes to take effect\n\n"
        "4. Verify Installation\n"
        "   - Open Command Palette ([cyan]Cmd/Ctrl + Shift + P[/cyan])\n"
        "   - Search for 'MCP' to see available tools\n"
        "   - Badger tools should appear in the list",
        title="Instructions"
    ))
    
    console.print()
    console.print(Panel(
        "[bold]MCP Configuration JSON[/bold]\n\n"
        "Add this to your Cursor MCP settings:",
        title="Configuration"
    ))
    
    # Display JSON with syntax highlighting (show full config)
    json_str = json.dumps(full_mcp_config, indent=2)
    console.print(Syntax(json_str, "json", theme="monokai"))
    
    console.print()
    console.print(Panel(
        f"[bold]Configuration Details[/bold]\n\n"
        f"Python: [cyan]{python_path}[/cyan]\n"
        f"MCP Script: [cyan]{mcp_script_path}[/cyan]\n"
        f"Workspace: [cyan]{workspace}[/cyan]\n"
        f"Dgraph Endpoint: [cyan]{endpoint}[/cyan]",
        title="Details"
    ))
    
    # Save config to file for easy copying
    config_file = Path(workspace) / ".badger-mcp-config.json"
    with open(config_file, "w") as f:
        json.dump(full_mcp_config, f, indent=2)
    
    console.print()
    console.print(f"[green]✓ Configuration saved to: [cyan]{config_file}[/cyan][/green]")
    console.print("[dim]You can copy this file's contents into Cursor's MCP settings[/dim]")


@app.command("mcp-server")
def mcp_server(
    endpoint: Optional[str] = typer.Option(None, "--endpoint", "-e", help="Graph database endpoint URL (default: local from .badgerrc or http://localhost:8080)"),
    workspace_path: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Path to workspace/codebase root (default: current directory or BADGER_WORKSPACE_PATH env var)"),
    auto_index: bool = typer.Option(False, "--auto-index", help="Enable automatic indexing on startup"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """Start the MCP server for Model Context Protocol.
    
    The server runs on stdio and provides tools for querying the code graph database.
    This command is typically invoked automatically by Cursor when configured.
    You can also run it manually for testing.
    
    By default, the server does not automatically index the workspace. 
    Use --auto-index to enable automatic indexing on startup, or run 'badger index' separately.
    
    """
    import asyncio
    import logging
    
    # Set up logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Load config
    config = load_config()
    
    # Use endpoint from command line, config, or default to local
    if not endpoint:
        endpoint = config.graphdb_endpoint if config else "http://localhost:8080"
    
    # Determine workspace path
    workspace = str(workspace_path.resolve()) if workspace_path else None
    
    console.print(f"[green]Starting MCP server...[/green]")
    console.print(f"[dim]Graph database: {endpoint}[/dim]")
    if workspace:
        console.print(f"[dim]Workspace: {workspace}[/dim]")
    console.print("[dim]Server will communicate via stdio[/dim]\n")
    
    try:
        # Run MCP server
        asyncio.run(run_mcp_server(
            dgraph_endpoint=endpoint,
            workspace_path=workspace,
            auto_index=auto_index
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]Server shutdown requested[/yellow]")
    except Exception as e:
        console.print(f"[red]Server error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command()
def stats(
    endpoint: Optional[str] = typer.Option(None, "--endpoint", "-e", help="Graph database endpoint URL (default: local from .badgerrc or http://localhost:8080)"),
):
    """Show node counts in the graph database."""
    from .graph.dgraph import DgraphClient
    
    # Load config
    config = load_config()
    
    # Use endpoint from command line, config, or default to local
    if not endpoint:
        endpoint = config.graphdb_endpoint if config else "http://localhost:8080"
    
    console.print(f"[green]Querying Dgraph at {endpoint}...[/green]")
    
    client = DgraphClient(endpoint)
    try:
        # Query for full counts
        count_query = """
        {
            files: queryFile {
                id
            }
            functions: queryFunction {
                id
            }
            classes: queryClass {
                id
            }
            imports: queryImport {
                id
            }
            macros: queryMacro {
                id
            }
            variables: queryVariable {
                id
            }
            typedefs: queryTypedef {
                id
            }
            structFieldAccesses: queryStructFieldAccess {
                id
            }
        }
        """
        result = client.execute_graphql_query(count_query)
        
        # Count nodes
        counts = {
            "File": len(result.get("files", [])),
            "Function": len(result.get("functions", [])),
            "Class": len(result.get("classes", [])),
            "Import": len(result.get("imports", [])),
            "Macro": len(result.get("macros", [])),
            "Variable": len(result.get("variables", [])),
            "Typedef": len(result.get("typedefs", [])),
            "StructFieldAccess": len(result.get("structFieldAccesses", []))
        }
        
        total = sum(counts.values())
        
        # Display as single line
        console.print(f"\n[bold]Graph Statistics:[/bold]")
        console.print(f"Total: {total} | Files: {counts['File']} | Functions: {counts['Function']} | Classes: {counts['Class']} | Imports: {counts['Import']} | Macros: {counts['Macro']} | Variables: {counts['Variable']} | Typedefs: {counts['Typedef']} | Field Accesses: {counts['StructFieldAccess']}")
    finally:
        client.close()


@app.command("stop_graph")
def stop_graph(
    compose_file: Optional[Path] = typer.Option(None, "--compose-file", "-f", help="Path to docker-compose.yml (default: dgraph/docker-compose.yml)"),
):
    """Stop the local Dgraph container using docker-compose.
    
    This stops the container but preserves all data. The data is stored in
    dgraph/dgraph-data and persists across stops/restarts.
    
    To restart: Use 'badger start_graph'
    """
    import subprocess
    
    work_dir = Path.cwd()
    
    # Find docker-compose.yml file
    if compose_file:
        compose_path = Path(compose_file).resolve()
    else:
        compose_path = work_dir / "dgraph" / "docker-compose.yml"
        if not compose_path.exists():
            for parent in work_dir.parents:
                candidate = parent / "dgraph" / "docker-compose.yml"
                if candidate.exists():
                    compose_path = candidate
                    break
    
    if not compose_path.exists():
        console.print(f"[red]✗ docker-compose.yml not found[/red]")
        console.print(f"[yellow]Expected at: {compose_path}[/yellow]")
        raise typer.Exit(1)
    
    compose_dir = compose_path.parent
    console.print(f"[cyan]Stopping Dgraph container...[/cyan]")
    
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "stop"],
            cwd=compose_dir,
            capture_output=True,
            text=True,
            check=True
        )
        console.print(f"[green]✓ Dgraph container stopped[/green]")
        console.print("[dim]Data is preserved in dgraph/dgraph-data[/dim]")
        console.print("[dim]Use 'badger start_graph' to restart[/dim]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error stopping container: {e.stderr}[/red]")
        raise typer.Exit(1)


@app.command("start_graph")
def start_graph(
    compose_file: Optional[Path] = typer.Option(None, "--compose-file", "-f", help="Path to docker-compose.yml (default: dgraph/docker-compose.yml)"),
):
    """Start the local Dgraph container using docker-compose.
    
    This starts a previously stopped container. All data is preserved from
    when the container was last running.
    """
    import subprocess
    import time
    
    work_dir = Path.cwd()
    
    # Find docker-compose.yml file
    if compose_file:
        compose_path = Path(compose_file).resolve()
    else:
        compose_path = work_dir / "dgraph" / "docker-compose.yml"
        if not compose_path.exists():
            for parent in work_dir.parents:
                candidate = parent / "dgraph" / "docker-compose.yml"
                if candidate.exists():
                    compose_path = candidate
                    break
    
    if not compose_path.exists():
        console.print(f"[red]✗ docker-compose.yml not found[/red]")
        console.print(f"[yellow]Expected at: {compose_path}[/yellow]")
        raise typer.Exit(1)
    
    compose_dir = compose_path.parent
    console.print(f"[cyan]Starting Dgraph container...[/cyan]")
    
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "up", "-d"],
            cwd=compose_dir,
            capture_output=True,
            text=True,
            check=True
        )
        console.print(f"[green]✓ Dgraph container started[/green]")
        
        # Wait for Dgraph to be ready
        console.print("[cyan]Waiting for Dgraph to be ready...[/cyan]")
        endpoint = "http://localhost:8080"
        for i in range(30):  # Wait up to 30 seconds
            try:
                import requests
                response = requests.get(f"{endpoint}/health", timeout=2)
                if response.status_code == 200:
                    console.print("[green]✓ Dgraph is ready![/green]")
                    break
            except:
                time.sleep(1)
                if i % 5 == 0:
                    console.print(f"[dim]Waiting... ({i+1}/30)[/dim]")
        else:
            console.print("[yellow]⚠ Dgraph may not be fully ready yet. Continuing anyway...[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error starting container: {e.stderr}[/red]")
        console.print("[yellow]Run 'badger init_graph' to create the container first[/yellow]")
        raise typer.Exit(1)


@app.command("status_graph")
def status_graph(
    compose_file: Optional[Path] = typer.Option(None, "--compose-file", "-f", help="Path to docker-compose.yml (default: dgraph/docker-compose.yml)"),
):
    """Show the status of the local Dgraph container."""
    import subprocess
    import json
    
    work_dir = Path.cwd()
    
    # Find docker-compose.yml file
    if compose_file:
        compose_path = Path(compose_file).resolve()
    else:
        compose_path = work_dir / "dgraph" / "docker-compose.yml"
        if not compose_path.exists():
            # Try looking in parent directories
            for parent in work_dir.parents:
                candidate = parent / "dgraph" / "docker-compose.yml"
                if candidate.exists():
                    compose_path = candidate
                    break
            
            # Also try looking in the badger project root (where this code lives)
            if not compose_path.exists():
                # __file__ is cli/badger/main.py, so go up 3 levels to get project root
                badger_root = Path(__file__).parent.parent.parent
                candidate = badger_root / "dgraph" / "docker-compose.yml"
                if candidate.exists():
                    compose_path = candidate
                else:
                    # Also try one more level up in case we're in a different structure
                    badger_root_alt = badger_root.parent
                    candidate_alt = badger_root_alt / "dgraph" / "docker-compose.yml"
                    if candidate_alt.exists():
                        compose_path = candidate_alt
    
    if not compose_path.exists():
        console.print(f"[red]✗ docker-compose.yml not found[/red]")
        console.print(f"[yellow]Searched in:[/yellow]")
        console.print(f"  - {work_dir / 'dgraph' / 'docker-compose.yml'}")
        console.print(f"  - Parent directories of current working directory")
        console.print(f"[yellow]Use --compose-file to specify the path[/yellow]")
        raise typer.Exit(1)
    
    compose_dir = compose_path.parent
    
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "ps", "--format", "json"],
            cwd=compose_dir,
            capture_output=True,
            text=True,
            check=True
        )
        
        if result.stdout.strip():
            try:
                services = json.loads(result.stdout)
                if not isinstance(services, list):
                    services = [services]
                
                for service in services:
                    name = service.get("Name", "unknown")
                    state = service.get("State", "unknown")
                    status = service.get("Status", "")
                    
                    if state == "running":
                        console.print(f"[green]✓ Container '{name}' is running[/green]")
                        console.print(f"  Status: {status}")
                    else:
                        console.print(f"[yellow]Container '{name}' is {state}[/yellow]")
                        if state == "exited":
                            console.print(f"  Use 'badger start_graph' to start it")
            except json.JSONDecodeError:
                # Fallback to simple text parsing
                console.print(result.stdout)
        else:
            console.print("[yellow]No Dgraph containers found[/yellow]")
            console.print("[yellow]Run 'badger init_graph' to create the container[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error checking container status: {e.stderr}[/red]")
        raise typer.Exit(1)


@app.command()
def clear(
    endpoint: Optional[str] = typer.Option(None, "--endpoint", "-e", help="Graph database endpoint URL (default: local from .badgerrc or http://localhost:8080)"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Clear all data from the graph database.
    
    WARNING: This will delete ALL nodes and relationships in the graph database.
    This action cannot be undone.
    """
    from .graph.dgraph import DgraphClient
    
    # Load config
    config = load_config()
    
    # Use endpoint from command line, config, or default to local
    if not endpoint:
        endpoint = config.graphdb_endpoint if config else "http://localhost:8080"
    
    if not confirm:
        console.print("[red]WARNING: This will delete ALL data from the graph database![/red]")
        response = typer.confirm("Are you sure you want to continue?")
        if not response:
            console.print("[yellow]Operation cancelled.[/yellow]")
            raise typer.Exit(0)
    
    console.print(f"[yellow]Clearing all data from Dgraph at {endpoint}...[/yellow]")
    
    client = DgraphClient(endpoint)
    try:
        # Use drop_all to clear everything (schema and data)
        # This is much faster and more robust than deleting nodes individually
        import pydgraph
        op = pydgraph.Operation(drop_all=True)
        client.client.alter(op)
        
        console.print(f"[green]✓ Successfully dropped all data and schema.[/green]")
        
        # Re-initialize schema since drop_all removes it
        console.print("[cyan]Re-initializing GraphQL schema...[/cyan]")
        if client.setup_graphql_schema():
            console.print("[green]✓ GraphQL schema setup complete[/green]")
        else:
            console.print("[yellow]⚠ Schema setup may have failed. Run 'badger init_graph' if needed.[/yellow]")
        
        # Clear hash cache (search in current directory and common locations)
        from .graph.hash_cache import HashCache
        work_dir = Path.cwd()
        cache_file = work_dir / ".badger-index" / "node_hashes.json"
        if cache_file.exists():
            hash_cache = HashCache(cache_file)
            hash_cache.clear_cache()
            console.print("[green]✓ Hash cache cleared[/green]")
        else:
            # Try to find cache files in subdirectories
            cache_files = list(work_dir.rglob(".badger-index/node_hashes.json"))
            if cache_files:
                for cache_file in cache_files:
                    hash_cache = HashCache(cache_file)
                    hash_cache.clear_cache()
                console.print(f"[green]✓ Cleared {len(cache_files)} hash cache file(s)[/green]")
            
    except Exception as e:
        console.print(f"[red]Error clearing graph: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("view")
def view(
    port: int = typer.Option(5000, "--port", "-p", help="Port to run the viewer on"),
    host: str = typer.Option("localhost", "--host", "-h", help="Host to run the viewer on"),
):
    """Start the graph viewer web interface.
    
    This command starts the Flask application that serves the graph visualization
    and automatically opens it in your default web browser.
    """
    import subprocess
    import webbrowser
    import time
    import sys
    
    # Find the viewer app.py
    # Current file is in cli/badger/main.py
    # Viewer is in cli/graph-viewer/app.py
    current_dir = Path(__file__).resolve().parent
    viewer_path = current_dir.parent.parent / "graph-viewer" / "app.py"
    
    # Check if we are in the installed package structure or source
    if not viewer_path.exists():
        # Try alternative location (source structure: cli/badger/main.py -> cli/graph-viewer/app.py)
        viewer_path = current_dir.parent / "graph-viewer" / "app.py"
    
    if not viewer_path.exists():
        console.print(f"[red]Error: Could not find viewer application[/red]")
        console.print(f"[yellow]Searched at: {viewer_path}[/yellow]")
        raise typer.Exit(1)
        
    console.print(f"[green]Starting graph viewer...[/green]")
    console.print(f"[dim]App path: {viewer_path}[/dim]")
    
    # Set environment variables for Flask
    env = os.environ.copy()
    env["FLASK_APP"] = str(viewer_path)
    env["PORT"] = str(port)
    
    # Note: app.py uses PORT env var if set
    
    cmd = [sys.executable, str(viewer_path)]
    
    try:
        # Start Flask app
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        console.print(f"[green]✓ Viewer started[/green]")
        console.print(f"Opening http://{host}:{port} in browser...")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        
        # Wait a moment for server to start then open browser
        # time.sleep(1.5)
        # webbrowser.open(f"http://{host}:{port}")
        
        # Stream output
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                # Print flask output nicely
                if " * Running on" in line:
                    console.print(f"[cyan]{line.strip()}[/cyan]")
                elif "GET /" in line or "POST /" in line:
                    console.print(f"[dim]{line.strip()}[/dim]")
                else:
                    print(line.strip())
                    
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping viewer...[/yellow]")
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        console.print("[green]✓ Viewer stopped[/green]")
    except Exception as e:
        console.print(f"[red]Error running viewer: {e}[/red]")
        if 'process' in locals() and process:
            process.terminate()
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
