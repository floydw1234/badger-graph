"""MCP tool implementations for querying code graph database."""

import json
import logging
import fnmatch
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

try:
    import numpy as np  # type: ignore
except ImportError:
    np = None  # numpy may not be available in all environments

from ..graph.dgraph import DgraphClient
from ..embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)


def _file_path_to_module(file_path: str, workspace_root: str = None) -> str:
    """Convert a file path to a Python module name.
    
    Args:
        file_path: Path to Python file (e.g., "cli/badger/mcp/server.py")
        workspace_root: Root directory of workspace (e.g., "cli" or ".")
    
    Returns:
        Module name (e.g., "badger.mcp.server")
    """
    # Normalize path
    path = Path(file_path)
    
    # Remove .py extension
    if path.suffix == ".py":
        path = path.with_suffix("")
    
    # Remove workspace root if provided
    if workspace_root:
        workspace_path = Path(workspace_root).resolve()
        try:
            path = path.resolve().relative_to(workspace_path)
        except ValueError:
            # Path is not relative to workspace, use as-is
            pass
    
    # Convert to module name
    parts = [p for p in path.parts if p and p != "__pycache__"]
    # Remove leading parts that aren't part of the module (e.g., "cli", "src")
    # Keep everything after common prefixes
    module_parts = []
    skip_prefixes = {"cli", "src", "lib", "python"}
    started = False
    for part in parts:
        if part in skip_prefixes and not started:
            continue
        started = True
        if part:
            module_parts.append(part)
    
    return ".".join(module_parts) if module_parts else path.stem


def extract_relative_path(path: str) -> str:
    """Extract relative path component from absolute path.
    
    Handles various path formats:
    - /path/to/src/packages/comm/gossipApi.h -> packages/comm/gossipApi.h
    - /path/to/src/comm/gossipApi.h -> comm/gossipApi.h
    - /path/to/gossipApi.h -> gossipApi.h
    
    Args:
        path: Absolute file path
    
    Returns:
        Relative path component (e.g., "packages/encryption/encryption.h")
    """
    parts = path.split("/")
    
    # Try to find common root markers
    for marker in ["packages", "src", "include", "lib"]:
        if marker in parts:
            idx = parts.index(marker)
            # For "src", skip it and take everything after
            # For others like "packages", include the marker
            if marker == "src":
                return "/".join(parts[idx+1:])
            else:
                return "/".join(parts[idx:])
    
    # If no marker found, try to find a reasonable starting point
    # Look for common directory patterns (comm, validation, sql, etc.)
    # and return from there
    common_dirs = {"comm", "validation", "sql", "encryption", "transactions", 
                   "initialization", "keystore", "signing", "utils", "tests"}
    for i, part in enumerate(parts):
        if part in common_dirs:
            return "/".join(parts[i:])
    
    # Fallback: return just the filename
    return parts[-1]


def _find_files_importing_module(
    dgraph_client: DgraphClient,
    module_name: str
) -> List[str]:
    """Find all files that import a given module.
    
    Args:
        dgraph_client: Dgraph client instance
        module_name: Module name to search for (e.g., "badger.mcp.server")
    
    Returns:
        List of file paths that import this module
    """
    # Query all files and their imports, then filter in Python
    # This is more reliable than using GraphQL filters which may not work correctly
    query = """
    query {
        files: queryFile(first: 10000) {
            id
            path
            containsImport {
                id
                module
                line
            }
        }
    }
    """
    result = dgraph_client.execute_graphql_query(query, {})
    
    importing_files = []
    if "files" in result:
        file_list = result["files"] if isinstance(result["files"], list) else [result["files"]]
        for file_node in file_list:
            imports = file_node.get("containsImport", [])
            if not isinstance(imports, list):
                imports = [imports] if imports else []
            
            # Check if any import matches the module
            # Try multiple matching strategies:
            # 1. Exact match
            # 2. Module is imported as parent (e.g., "badger.mcp" imports "badger.mcp.server")
            # 3. Parent module is imported (e.g., "badger.mcp.server" imports "badger.mcp")
            for imp in imports:
                imp_module = imp.get("module", "")
                if not imp_module:
                    continue
                
                # Normalize module names for comparison (handle relative imports)
                # Remove leading dots from relative imports for matching
                normalized_imp = imp_module.lstrip(".")
                normalized_target = module_name.lstrip(".")
                
                # Exact match
                if normalized_imp == normalized_target or imp_module == module_name:
                    importing_files.append(file_node.get("path", ""))
                    break
                # Module is a submodule of imported module (e.g., import badger.mcp, looking for badger.mcp.server)
                # Only match if the imported module is a meaningful parent (not just "badger" when looking for "badger.mcp.server")
                elif (normalized_target.startswith(normalized_imp + ".") and len(normalized_imp.split(".")) >= 2) or \
                     (module_name.startswith(imp_module + ".") and len(imp_module.split(".")) >= 2):
                    importing_files.append(file_node.get("path", ""))
                    break
                # Imported module is a submodule (e.g., import badger.mcp.server, looking for badger.mcp)
                elif normalized_imp.startswith(normalized_target + ".") or imp_module.startswith(module_name + "."):
                    importing_files.append(file_node.get("path", ""))
                    break
                # Handle relative imports: ".mcp.server" should match "badger.mcp.server"
                # Relative imports like ".mcp.server" from badger/ resolve to "badger.mcp.server"
                # So we check if the target ends with the normalized relative import
                elif imp_module.startswith(".") and normalized_imp:
                    # For ".mcp.server", check if "badger.mcp.server" ends with "mcp.server"
                    # or if they're equal after normalization
                    if normalized_target == normalized_imp or normalized_target.endswith("." + normalized_imp):
                        importing_files.append(file_node.get("path", ""))
                        break
                    # Also check if the last parts match (e.g., ".server" matches "badger.mcp.server")
                    target_parts = normalized_target.split(".")
                    imp_parts = normalized_imp.split(".")
                    if len(imp_parts) > 0 and len(target_parts) >= len(imp_parts):
                        # Check if the last N parts match
                        if target_parts[-len(imp_parts):] == imp_parts:
                            importing_files.append(file_node.get("path", ""))
                            break
    
    return importing_files


async def find_symbol_usages(
    dgraph_client: DgraphClient,
    symbol: str,
    symbol_type: str
) -> Dict[str, Any]:
    """Find all usages of a symbol (function, macro, variable, struct, typedef).
    
    Args:
        dgraph_client: Dgraph client instance
        symbol: Symbol name
        symbol_type: Type of symbol ("function", "macro", "variable", "struct", "typedef")
    
    Returns:
        Dictionary with usages and count
    """
    try:
        if symbol_type not in ["function", "macro", "variable", "struct", "typedef"]:
            return {
                "error": f"Invalid symbol_type: {symbol_type}. Must be one of: function, macro, variable, struct, typedef",
                "type": "invalid_parameter"
            }
        
        usages = []
        
        if symbol_type == "function":
            # Simple query: get function and its callers via inverse relationship
            query = """
            query($funcName: String!) {
                func: queryFunction(filter: {name: {eq: $funcName}}, first: 100) {
                    id
                    name
                    file
                    line
                    signature
                    calledByFunction {
                        id
                        name
                        file
                        line
                        signature
                    }
                }
            }
            """
            result = dgraph_client.execute_graphql_query(query, {"funcName": symbol})
            
            func_list = result.get("func", [])
            if not isinstance(func_list, list):
                func_list = [func_list] if func_list else []
            
            for func in func_list:
                # Add the function definition itself
                usages.append({
                    "type": "definition",
                    "file": func.get("file", ""),
                    "line": func.get("line", 0),
                    "context": func.get("signature", "")
                })
                
                # Add callers (from inverse relationship)
                callers = func.get("calledByFunction", [])
                if not isinstance(callers, list):
                    callers = [callers] if callers else []
                
                for caller in callers:
                    if caller:  # Skip None/empty values
                        usages.append({
                            "type": "call",
                            "file": caller.get("file", ""),
                            "line": caller.get("line", 0),
                            "context": f"Called by {caller.get('name', 'unknown')}"
                        })
        
        elif symbol_type == "macro":
            # Query Macro nodes by name and find usages via usedInFile
            query = """
            query($macroName: String!) {
                macro: queryMacro(filter: {name: {eq: $macroName}}, first: 100) {
                    id
                    name
                    file
                    line
                    usedInFile {
                        id
                        path
                    }
                }
            }
            """
            result = dgraph_client.execute_graphql_query(query, {"macroName": symbol})
            
            if "macro" in result:
                macro_list = result["macro"] if isinstance(result["macro"], list) else [result["macro"]]
                for macro in macro_list:
                    # Add macro definition
                    usages.append({
                        "type": "definition",
                        "file": macro.get("file", ""),
                        "line": macro.get("line", 0),
                        "context": "Macro definition"
                    })
                    
                    # Add files that use this macro
                    used_in = macro.get("usedInFile", [])
                    if not isinstance(used_in, list):
                        used_in = [used_in] if used_in else []
                    
                    for file_node in used_in:
                        usages.append({
                            "type": "usage",
                            "file": file_node.get("path", ""),
                            "line": 0,  # File-level usage, no specific line
                            "context": "Used in file"
                        })
        
        elif symbol_type == "variable":
            # Query Variable nodes by name and find usages via usedInFunction
            query = """
            query($varName: String!) {
                variable: queryVariable(filter: {name: {eq: $varName}}, first: 100) {
                    id
                    name
                    file
                    line
                    type
                    usedInFunction {
                        id
                        name
                        file
                        line
                    }
                }
            }
            """
            result = dgraph_client.execute_graphql_query(query, {"varName": symbol})
            
            if "variable" in result:
                var_list = result["variable"] if isinstance(result["variable"], list) else [result["variable"]]
                for var in var_list:
                    # Add variable definition
                    usages.append({
                        "type": "definition",
                        "file": var.get("file", ""),
                        "line": var.get("line", 0),
                        "context": f"Variable definition: {var.get('type', 'unknown type')}"
                    })
                    
                    # Add functions that use this variable
                    used_in = var.get("usedInFunction", [])
                    if not isinstance(used_in, list):
                        used_in = [used_in] if used_in else []
                    
                    for func in used_in:
                        usages.append({
                            "type": "usage",
                            "file": func.get("file", ""),
                            "line": func.get("line", 0),
                            "context": f"Used in function {func.get('name', 'unknown')}"
                        })
        
        elif symbol_type == "struct":
            # Query Struct nodes by name
            query = """
            query($structName: String!) {
                struct: queryStruct(filter: {name: {eq: $structName}}, first: 100) {
                    id
                    name
                    file
                    line
                    fields
                    accessedByFieldAccess {
                        id
                        file
                        line
                        fieldName
                    }
                }
            }
            """
            result = dgraph_client.execute_graphql_query(query, {"structName": symbol})
            
            if "struct" in result:
                struct_list = result["struct"] if isinstance(result["struct"], list) else [result["struct"]]
                for struct in struct_list:
                    # Add struct definition
                    usages.append({
                        "type": "definition",
                        "file": struct.get("file", ""),
                        "line": struct.get("line", 0),
                        "context": "Struct definition"
                    })
                    
                    # Add field accesses
                    accesses = struct.get("accessedByFieldAccess", [])
                    if not isinstance(accesses, list):
                        accesses = [accesses] if accesses else []
                    
                    for access in accesses:
                        usages.append({
                            "type": "field_access",
                            "file": access.get("file", ""),
                            "line": access.get("line", 0),
                            "context": f"Field access: {access.get('fieldName', 'unknown')}"
                        })
        
        elif symbol_type == "typedef":
            # Query Typedef nodes by name and find usages via usedInFile
            query = """
            query($typedefName: String!) {
                typedef: queryTypedef(filter: {name: {eq: $typedefName}}, first: 100) {
                    id
                    name
                    file
                    line
                    underlyingType
                    usedInFile {
                        id
                        path
                    }
                }
            }
            """
            result = dgraph_client.execute_graphql_query(query, {"typedefName": symbol})
            
            if "typedef" in result:
                typedef_list = result["typedef"] if isinstance(result["typedef"], list) else [result["typedef"]]
                for typedef in typedef_list:
                    # Add typedef definition
                    usages.append({
                        "type": "definition",
                        "file": typedef.get("file", ""),
                        "line": typedef.get("line", 0),
                        "context": f"Typedef: {typedef.get('underlyingType', 'unknown type')}"
                    })
                    
                    # Add files that use this typedef
                    used_in = typedef.get("usedInFile", [])
                    if not isinstance(used_in, list):
                        used_in = [used_in] if used_in else []
                    
                    for file_node in used_in:
                        usages.append({
                            "type": "usage",
                            "file": file_node.get("path", ""),
                            "line": 0,  # File-level usage
                            "context": "Used in file"
                        })
        
        return {
            "usages": usages,
            "count": len(usages),
            "symbol": symbol,
            "symbol_type": symbol_type
        }
    
    except Exception as e:
        logger.error(f"Error in find_symbol_usages: {e}", exc_info=True)
        return {
            "error": str(e),
            "type": "query_error"
        }


async def get_include_dependencies(
    dgraph_client: DgraphClient,
    file_path: str
) -> Dict[str, Any]:
    """Find all files that include or import the target file (reverse dependencies).
    
    This function finds files that DEPEND ON the target file by including/importing it.
    It does NOT find files that the target file includes/imports.
    
    For C/C++ files:
    - If given a .c file (e.g., "gossipApi.c"), it searches for files that include
      the corresponding .h file (e.g., "gossipApi.h")
    - If given a .h file, it searches for files that include that header
    - Returns transitive dependencies: files that include files that include the target
    
    For Python files:
    - Finds files that import the module (e.g., "from badger.mcp import tools")
    - Returns transitive dependencies: files that import files that import the target
    
    Example:
        get_include_dependencies("gossipApi.c") returns:
        - Files that include "gossipApi.h" (e.g., main.c, gossipApi.c itself)
        - Files that include files that include "gossipApi.h" (transitive)
    
    Args:
        dgraph_client: Dgraph client instance
        file_path: Path to the file to find dependents for
    
    Returns:
        Dictionary with:
        - "file": The input file path
        - "dependencies": List of files that include/import this file, each with:
          - "file": Path to the dependent file
          - "module": The module/header that was matched
          - "depth": Depth in the dependency tree (1 = direct, 2+ = transitive)
          - "reason": Explanation of why this file is included
        - "count": Total number of dependent files found
        - "depth": Maximum depth of the dependency tree
    """
    try:
        # Determine if this is a Python file
        is_python = file_path.endswith(".py")
        
        if is_python:
            # Python: find files that import this module
            module_name = _file_path_to_module(file_path)
            
            # Simple recursive traversal
            async def find_importers(target_module: str, visited: Set[str], depth: int = 0) -> List[Dict[str, Any]]:
                """Find files that import the target module, recursively."""
                if target_module in visited or depth > 20:
                    return []
                
                visited.add(target_module)
                dependencies = []
                importing_files = _find_files_importing_module(dgraph_client, target_module)
                
                for importer_path in importing_files:
                    if importer_path == file_path:
                        continue
                    
                    dependencies.append({
                        "file": importer_path,
                        "module": target_module,
                        "depth": depth + 1,
                        "reason": f"Imports {target_module}"
                    })
                    
                    # Recursively find importers of this file
                    importer_module = _file_path_to_module(importer_path)
                    dependencies.extend(await find_importers(importer_module, visited, depth + 1))
                
                return dependencies
            
            dependencies = await find_importers(module_name, set())
        
        else:
            # C/C++: find files that include this header using native DQL
            # Extract relative path for matching
            target_modules = set()
            
            if file_path.endswith(".c"):
                h_path = file_path[:-2] + ".h"
                rel_path = extract_relative_path(h_path)
                target_modules.add(rel_path)
                target_modules.add(h_path.split("/")[-1])
                # Also try the .c path
                target_modules.add(extract_relative_path(file_path))
            else:
                rel_path = extract_relative_path(file_path)
                target_modules.add(rel_path)
                target_modules.add(file_path.split("/")[-1])
            
            logger.debug(f"get_include_dependencies: Searching for modules matching: {target_modules}")
            
            # Build lookup structures once (performance optimization)
            # Query all imports once and build module_to_files mapping
            all_imports_query = """
            {
                imports(func: has(Import.module)) {
                    uid
                    Import.module
                    Import.text
                    Import.file
                }
            }
            """
            
            txn = dgraph_client.client.txn(read_only=True)
            try:
                result = txn.query(all_imports_query)
                data = json.loads(result.json)
            finally:
                txn.discard()
            
            imports = data.get("imports", [])
            
            # Build module_to_files lookup: maps Import.module -> list of files that import it
            module_to_files: Dict[str, List[str]] = defaultdict(list)
            # Also build filename_to_modules for fuzzy matching
            filename_to_modules: Dict[str, Set[str]] = defaultdict(set)
            
            for imp in imports:
                if not isinstance(imp, dict):
                    continue
                module = imp.get("Import.module", "")
                importing_file = imp.get("Import.file", "")
                if not module or not importing_file:
                    continue
                
                module_to_files[module].append(importing_file)
                filename = module.split("/")[-1]
                filename_to_modules[filename].add(module)
            
            def _module_matches(module: str, target_modules_set: Set[str]) -> Tuple[bool, Optional[str]]:
                """Check if a module matches any target, returning (matches, matched_target)."""
                # Exact match
                if module in target_modules_set:
                    return True, module
                
                # Filename match
                module_filename = module.split("/")[-1]
                for target in target_modules_set:
                    target_filename = target.split("/")[-1]
                    if module_filename == target_filename:
                        # If target is just a filename, match any path with that filename
                        if "/" not in target:
                            return True, module
                        # If both have paths, check if they end the same way
                        if module.endswith("/" + target) or target.endswith("/" + module):
                            return True, module
                        # Also check if paths overlap (e.g., "comm/gossipApi.h" matches "packages/comm/gossipApi.h")
                        module_parts = module.split("/")
                        target_parts = target.split("/")
                        if len(module_parts) >= len(target_parts):
                            if module_parts[-len(target_parts):] == target_parts:
                                return True, module
                        if len(target_parts) >= len(module_parts):
                            if target_parts[-len(module_parts):] == module_parts:
                                return True, module
                
                return False, None
            
            def find_includers_dql(target_modules_set: Set[str], visited: Set[str], depth: int = 0) -> List[Dict[str, Any]]:
                """Find files that include any of the target modules using pre-built lookups."""
                if depth > 20:
                    return []
                
                dependencies = []
                matched_files = set()
                
                # Find all modules that match our targets
                matching_modules = set()
                for target_module in target_modules_set:
                    # Exact match
                    if target_module in module_to_files:
                        matching_modules.add(target_module)
                    
                    # Filename match
                    target_filename = target_module.split("/")[-1]
                    if target_filename in filename_to_modules:
                        for module in filename_to_modules[target_filename]:
                            matches, _ = _module_matches(module, target_modules_set)
                            if matches:
                                matching_modules.add(module)
                
                # Get all files that import matching modules
                for module in matching_modules:
                    files = module_to_files.get(module, [])
                    for file_path_check in files:
                        if file_path_check in visited or file_path_check in matched_files:
                            continue
                        
                        matches, matched_target = _module_matches(module, target_modules_set)
                        if matches:
                            visited.add(file_path_check)
                            matched_files.add(file_path_check)
                            dependencies.append({
                                "file": file_path_check,
                                "module": matched_target or module,
                                "depth": depth + 1,
                                "reason": f"Includes {matched_target or module}"
                            })
                            
                            # Recursively find includers of this file
                            new_target_modules = {extract_relative_path(file_path_check)}
                            if file_path_check.endswith(".c"):
                                h_path = file_path_check[:-2] + ".h"
                                new_target_modules.add(extract_relative_path(h_path))
                            dependencies.extend(find_includers_dql(new_target_modules, visited, depth + 1))
                
                return dependencies
            
            dependencies = find_includers_dql(target_modules, set())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_dependencies = []
        for dep in dependencies:
            dep_key = dep["file"]
            if dep_key not in seen:
                seen.add(dep_key)
                unique_dependencies.append(dep)
        
        max_depth = max([d.get("depth", 0) for d in unique_dependencies] + [0])
        
        return {
            "file": file_path,
            "dependencies": unique_dependencies,
            "count": len(unique_dependencies),  # Add count field
            "depth": max_depth
        }
    
    except Exception as e:
        logger.error(f"Error in get_include_dependencies: {e}", exc_info=True)
        return {
            "error": str(e),
            "type": "query_error"
        }


async def find_struct_field_access(
    dgraph_client: DgraphClient,
    struct_name: str,
    field_name: str
) -> Dict[str, Any]:
    """Find all places where a struct field is accessed.
    
    Args:
        dgraph_client: Dgraph client instance
        struct_name: Name of the struct
        field_name: Name of the field
    
    Returns:
        Dictionary with accesses and count
    """
    try:
        query = """
        query($structName: String!, $fieldName: String!) {
            accesses: queryStructFieldAccess(
                filter: {
                    structName: {eq: $structName},
                    fieldName: {eq: $fieldName}
                },
                first: 1000
            ) {
                id
                structName
                fieldName
                file
                line
                column
                accessType
            }
        }
        """
        result = dgraph_client.execute_graphql_query(query, {
            "structName": struct_name,
            "fieldName": field_name
        })
        
        accesses = []
        if "accesses" in result:
            access_list = result["accesses"] if isinstance(result["accesses"], list) else [result["accesses"]]
            for access in access_list:
                accesses.append({
                    "file": access.get("file", ""),
                    "line": access.get("line", 0),
                    "column": access.get("column", 0),
                    "access_type": access.get("accessType", "unknown")
                })
        
        return {
            "accesses": accesses,
            "count": len(accesses),
            "struct_name": struct_name,
            "field_name": field_name
        }
    
    except Exception as e:
        logger.error(f"Error in find_struct_field_access: {e}", exc_info=True)
        return {
            "error": str(e),
            "type": "query_error"
        }


async def get_function_callers(
    dgraph_client: DgraphClient,
    function_name: str,
    include_indirect: bool = True
) -> Dict[str, Any]:
    """Find all callers of a function, including function pointer assignments.
    
    Args:
        dgraph_client: Dgraph client instance
        function_name: Name of the function
        include_indirect: Include function pointer assignments
    
    Returns:
        Dictionary with callers and count
    """
    try:
        # Simple query: get function and its callers via inverse relationship
        query = """
        query($funcName: String!) {
            func: queryFunction(filter: {name: {eq: $funcName}}, first: 100) {
                id
                name
                file
                line
                signature
                calledByFunction {
                    id
                    name
                    file
                    line
                    signature
                }
            }
        }
        """
        result = dgraph_client.execute_graphql_query(query, {"funcName": function_name})
        
        func_list = result.get("func", [])
        if not isinstance(func_list, list):
            func_list = [func_list] if func_list else []
        
        callers = []
        indirect_callers = []
        
        for func in func_list:
            # Get direct callers from inverse relationship
            direct_callers = func.get("calledByFunction", [])
            if not isinstance(direct_callers, list):
                direct_callers = [direct_callers] if direct_callers else []
            
            for caller in direct_callers:
                if caller:  # Skip None/empty values
                    callers.append({
                        "type": "direct",
                        "caller": caller.get("name", ""),
                        "file": caller.get("file", ""),
                        "line": caller.get("line", 0),
                        "signature": caller.get("signature", "")
                    })
            
            # For indirect callers (function pointers), query variables
            if include_indirect:
                var_query = """
                query {
                    variables: queryVariable(first: 1000) {
                        id
                        name
                        type
                        file
                        line
                    }
                }
                """
                var_result = dgraph_client.execute_graphql_query(var_query, {})
                
                if "variables" in var_result:
                    var_list = var_result["variables"] if isinstance(var_result["variables"], list) else [var_result["variables"]]
                    for var in var_list:
                        if not var:  # Skip None/empty values
                            continue
                        var_type = var.get("type") or ""
                        var_name = var.get("name") or ""
                        # Simple heuristic for function pointers
                        if var_name and (function_name in var_name or "(*" in var_type or "function" in var_type.lower()):
                            indirect_callers.append({
                                "type": "indirect",
                                "variable": var_name,
                                "file": var.get("file", ""),
                                "line": var.get("line", 0),
                                "context": f"Possible function pointer: {var_type}"
                            })
        
        return {
            "callers": callers,
            "indirect": indirect_callers if include_indirect else [],
            "count": len(callers) + len(indirect_callers),
            "function_name": function_name
        }
    
    except Exception as e:
        logger.error(f"Error in get_function_callers: {e}", exc_info=True)
        return {
            "error": str(e),
            "type": "query_error"
        }


async def semantic_code_search(
    dgraph_client: DgraphClient,
    embedding_service: EmbeddingService,
    query: str,
    file_pattern: str = "*",
    limit: int = 10
) -> Dict[str, Any]:
    """Search for code by semantic meaning using embeddings.
    
    Args:
        dgraph_client: Dgraph client instance
        embedding_service: Embedding service instance
        query: Natural language query
        file_pattern: Glob pattern to filter files
        limit: Maximum number of results
    
    Returns:
        Dictionary with matching functions/classes and scores
    """
    try:
        if not query or not query.strip():
            return {
                "error": "Query cannot be empty",
                "type": "invalid_parameter"
            }
        
        # Generate query embedding
        query_embedding = embedding_service.generate_query_embedding(query)
        
        # Convert to list if numpy array
        if np is not None and isinstance(query_embedding, np.ndarray):
            query_embedding = query_embedding.tolist()
        
        # Perform vector search
        vector_results = dgraph_client.vector_search_similar(
            query_embedding=query_embedding,
            top_k=limit * 2,  # Get more results to filter by pattern
            search_type="both"
        )
        
        # Filter by file pattern
        functions = []
        classes = []
        
        for func in vector_results.get("functions", []):
            file_path = func.get("file", "")
            if fnmatch.fnmatch(file_path, file_pattern) or fnmatch.fnmatch(file_path.split("/")[-1], file_pattern):
                functions.append({
                    "name": func.get("name", ""),
                    "file": file_path,
                    "line": func.get("line", 0),
                    "signature": func.get("signature", ""),
                    "docstring": func.get("docstring", ""),
                    "similarity_score": 1.0 - func.get("vector_distance", 1.0)  # Convert distance to similarity
                })
        
        for cls in vector_results.get("classes", []):
            file_path = cls.get("file", "")
            if fnmatch.fnmatch(file_path, file_pattern) or fnmatch.fnmatch(file_path.split("/")[-1], file_pattern):
                classes.append({
                    "name": cls.get("name", ""),
                    "file": file_path,
                    "line": cls.get("line", 0),
                    "methods": cls.get("methods", []),
                    "similarity_score": 1.0 - cls.get("vector_distance", 1.0)
                })
        
        # Sort by similarity and limit
        functions.sort(key=lambda x: x["similarity_score"], reverse=True)
        classes.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        functions = functions[:limit]
        classes = classes[:limit]
        
        return {
            "functions": functions,
            "classes": classes,
            "count": len(functions) + len(classes),
            "query": query
        }
    
    except Exception as e:
        logger.error(f"Error in semantic_code_search: {e}", exc_info=True)
        return {
            "error": str(e),
            "type": "query_error"
        }


async def check_affected_files(
    dgraph_client: DgraphClient,
    changed_files: List[str]
) -> Dict[str, Any]:
    """Find all files that would be affected if the given files are changed.
    
    This function identifies files that need to be recompiled, retested, or reviewed
    when the specified files are modified. It finds:
    
    1. Direct includes: Files that directly include/import the changed files
       (e.g., if "gossipApi.c" changes, files that include "gossipApi.h" are affected)
    
    2. Transitive includes: Files that include files that include the changed files
       (e.g., if A includes B, and B includes C, then changing C affects both A and B)
    
    3. Function calls: Files that call functions defined in the changed files
       (e.g., if "gossipApi.c" defines a function, files that call it are affected)
    
    This is useful for:
    - Determining test scope when a file changes
    - Identifying files that need recompilation
    - Understanding the impact of code changes
    
    Args:
        dgraph_client: Dgraph client instance
        changed_files: List of file paths that have been modified
    
    Returns:
        Dictionary with:
        - "affected_files": Sorted list of all unique affected file paths
        - "by_type": Dictionary categorizing affected files:
          - "direct_include": Files that directly include/import changed files
          - "transitive_include": Files that transitively include changed files
          - "function_call": Files that call functions from changed files
        - "count": Total number of unique affected files
        - "changed_files": The input list of changed files
    """
    try:
        affected_files = set()
        by_type = {
            "direct_include": [],
            "transitive_include": [],
            "function_call": []
        }
        
        for changed_file in changed_files:
            # Use DQL to find the file and its functions (avoiding GraphQL issues)
            escaped_path = changed_file.replace('"', '\\"')
            file_query = f"""
            {{
                files(func: eq(File.path, "{escaped_path}"), first: 1) {{
                    uid
                    File.path
                    File.containsFunction {{
                        uid
                        Function.name
                    }}
                }}
            }}
            """
            
            txn = dgraph_client.client.txn(read_only=True)
            try:
                result = txn.query(file_query)
                data = json.loads(result.json)
            finally:
                txn.discard()
            
            files = data.get("files", [])
            if not files:
                # File not found, but still try to check dependencies
                file_path = changed_file
                deps_result = await get_include_dependencies(dgraph_client, file_path)
                for dep in deps_result.get("dependencies", []):
                    dep_file = dep.get("file", "")
                    if dep_file and dep_file != file_path:
                        affected_files.add(dep_file)
                        by_type["direct_include"].append({
                            "file": dep_file,
                            "reason": dep.get("reason", "Imports/includes file"),
                            "changed_file": changed_file
                        })
                continue
            
            file_node = files[0]
            file_path = file_node.get("File.path", changed_file)
            
            # Find files that import/include this file (using get_include_dependencies)
            deps_result = await get_include_dependencies(dgraph_client, file_path)
            for dep in deps_result.get("dependencies", []):
                dep_file = dep.get("file", "")
                if dep_file and dep_file != file_path:
                    affected_files.add(dep_file)
                    by_type["direct_include"].append({
                        "file": dep_file,
                        "reason": dep.get("reason", "Imports/includes file"),
                        "changed_file": changed_file
                    })
            
            # Find functions in changed file and their callers
            functions_list = file_node.get("File.containsFunction", [])
            if not isinstance(functions_list, list):
                functions_list = [functions_list] if functions_list else []
            
            # Get function names from UIDs
            function_uids = [f.get("uid") for f in functions_list if isinstance(f, dict) and f.get("uid")]
            functions = []
            if function_uids:
                # Query functions by UID to get their names
                func_uid_list = ", ".join(function_uids)
                func_query = f"""
                {{
                    functions(func: uid({func_uid_list})) {{
                        uid
                        Function.name
                    }}
                }}
                """
                
                txn2 = dgraph_client.client.txn(read_only=True)
                try:
                    result2 = txn2.query(func_query)
                    data2 = json.loads(result2.json)
                finally:
                    txn2.discard()
                
                functions_data = data2.get("functions", [])
                functions = [{"name": f.get("Function.name", "")} for f in functions_data if isinstance(f, dict)]
            
            for func in functions:
                func_name = func.get("name", "")
                if not func_name or func_name == "<module>":
                    continue
                
                # Use simplified get_function_callers
                callers_result = await get_function_callers(dgraph_client, func_name, include_indirect=False)
                
                for caller in callers_result.get("callers", []):
                    caller_file = caller.get("file", "")
                    if caller_file and caller_file != file_path:
                            affected_files.add(caller_file)
                            by_type["function_call"].append({
                                "file": caller_file,
                                "reason": f"Calls function {func_name}",
                                "changed_file": changed_file,
                                "function": func_name
                            })
        
        return {
            "affected_files": sorted(list(affected_files)),
            "by_type": by_type,
            "count": len(affected_files),
            "changed_files": changed_files
        }
    
    except Exception as e:
        logger.error(f"Error in check_affected_files: {e}", exc_info=True)
        return {
            "error": str(e),
            "type": "query_error"
        }

