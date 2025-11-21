"""MCP tool implementations for querying code graph database."""

import json
import logging
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

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
    
    Args:
        path: Absolute file path
    
    Returns:
        Relative path component (e.g., "packages/encryption/encryption.h")
    """
    parts = path.split("/")
    if "packages" in parts:
        idx = parts.index("packages")
        return "/".join(parts[idx:])
    elif "src" in parts:
        idx = parts.index("src")
        return "/".join(parts[idx+1:])
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
    """Get all files that transitively import this file (Python) or include it (C).
    
    For Python files, finds files that import the module.
    For C files, finds files that include the header.
    
    Args:
        dgraph_client: Dgraph client instance
        file_path: Path to file
    
    Returns:
        Dictionary with dependency tree
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
            
            def find_includers_dql(target_modules_set: Set[str], visited: Set[str], depth: int = 0) -> List[Dict[str, Any]]:
                """Find files that include any of the target modules using native DQL."""
                if depth > 20:
                    return []
                
                dependencies = []
                
                # Step 1: Get all files with their Import UIDs
                files_query = """
                {
                    files(func: type(File)) {
                        uid
                        File.path
                        File.containsImport {
                            uid
                        }
                    }
                }
                """
                
                txn = dgraph_client.client.txn(read_only=True)
                try:
                    result = txn.query(files_query)
                    data = json.loads(result.json)
                finally:
                    txn.discard()
                
                files = data.get("files", [])
                
                # Step 2: Collect all Import UIDs and create a mapping
                import_uids = set()
                file_to_import_uids = {}
                
                for file_node in files:
                    file_path_check = file_node.get("File.path", "")
                    if not file_path_check:
                        continue
                    
                    imports_list = file_node.get("File.containsImport", [])
                    if not isinstance(imports_list, list):
                        imports_list = [imports_list] if imports_list else []
                    
                    file_import_uids = []
                    for imp in imports_list:
                        if isinstance(imp, dict):
                            imp_uid = imp.get("uid")
                            if imp_uid:
                                import_uids.add(imp_uid)
                                file_import_uids.append(imp_uid)
                    
                    if file_import_uids:
                        file_to_import_uids[file_path_check] = file_import_uids
                
                # Step 3: Query Import nodes directly by module instead of by UID
                # This avoids issues with expand(_all_) when querying by UID from relationships
                uid_to_import = {}
                
                # Query imports that match our target modules
                for target_module in target_modules_set:
                    escaped_module = target_module.replace('"', '\\"')
                    import_query = f"""
                    {{
                        imports(func: eq(Import.module, "{escaped_module}")) {{
                            uid
                            Import.module
                            Import.text
                            Import.file
                        }}
                    }}
                    """
                    
                    txn2 = dgraph_client.client.txn(read_only=True)
                    try:
                        result2 = txn2.query(import_query)
                        data2 = json.loads(result2.json)
                    finally:
                        txn2.discard()
                    
                    imports = data2.get("imports", [])
                    for imp in imports:
                        if isinstance(imp, dict):
                            uid = imp.get("uid")
                            if uid:
                                uid_to_import[uid] = imp
                
                # Also query by filename for cases where module is just "encryption.h"
                target_filenames = {t.split("/")[-1] for t in target_modules_set if "/" in t}
                for target_filename in target_filenames:
                    # Query all imports and filter by filename
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
                    
                    txn3 = dgraph_client.client.txn(read_only=True)
                    try:
                        result3 = txn3.query(all_imports_query)
                        data3 = json.loads(result3.json)
                    finally:
                        txn3.discard()
                    
                    imports3 = data3.get("imports", [])
                    for imp in imports3:
                        if not isinstance(imp, dict):
                            continue
                        module = imp.get("Import.module", "")
                        if not module or module.split("/")[-1] != target_filename:
                            continue
                        # Skip if already matched by exact query
                        if module in target_modules_set:
                            continue
                        uid = imp.get("uid")
                        if uid:
                            uid_to_import[uid] = imp
                
                # Step 4: Match Import nodes to target modules and get their files
                # Since we queried by module, all imports in uid_to_import already match
                for imp_uid, imp in uid_to_import.items():
                    module = imp.get("Import.module", "")
                    if not module:
                        continue
                    
                    # Get the file that contains this import
                    file_path_check = imp.get("Import.file", "")
                    if not file_path_check or file_path_check in visited:
                        continue
                    
                    # Check if module matches any target (it should, since we queried by target)
                    matches = False
                    matched_target = None
                    
                    # Exact match
                    if module in target_modules_set:
                        matches = True
                        matched_target = module
                    else:
                        # Try matching by filename
                        module_filename = module.split("/")[-1]
                        for target in target_modules_set:
                            target_filename = target.split("/")[-1]
                            if module_filename == target_filename:
                                # If target is just a filename, match any path with that filename
                                if "/" not in target:
                                    matches = True
                                    matched_target = module
                                    break
                                # If both have paths, check if they end the same way
                                if module.endswith("/" + target) or target.endswith("/" + module):
                                    matches = True
                                    matched_target = module
                                    break
                    
                    if matches:
                        visited.add(file_path_check)
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
    """Given a list of changed files, find all files that might be affected.
    
    Args:
        dgraph_client: Dgraph client instance
        changed_files: List of file paths
    
    Returns:
        Dictionary with affected files by type
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

