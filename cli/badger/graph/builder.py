"""Build graph from parsed results."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any
from ..parsers.base import ParseResult


@dataclass
class GraphData:
    """Graph data structure for code relationships."""
    
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    files: List[Dict[str, Any]] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    classes: List[Dict[str, Any]] = field(default_factory=list)
    structs: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[Dict[str, Any]] = field(default_factory=list)
    macros: List[Dict[str, Any]] = field(default_factory=list)
    variables: List[Dict[str, Any]] = field(default_factory=list)
    typedefs: List[Dict[str, Any]] = field(default_factory=list)
    struct_field_accesses: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)


def build_graph(parse_results: List[ParseResult]) -> GraphData:
    """Build graph from parse results.
    
    Extracts semantic relationships:
    - Function definitions
    - Class definitions
    - Import dependencies
    - Function calls (scaffolded for future implementation)
    - Class inheritance (scaffolded for future implementation)
    """
    graph = GraphData()
    
    for result in parse_results:
        # Add file information
        graph.files.append({
            "path": result.file_path,
            "functions_count": len(result.functions),
            "classes_count": len(result.classes),
            "structs_count": len(result.structs),
            "imports_count": len(result.imports),
            "macros_count": len(result.macros),
            "variables_count": len(result.variables),
            "typedefs_count": len(result.typedefs),
            "struct_field_accesses_count": len(result.struct_field_accesses),
            "ast_nodes": result.total_nodes
        })
        
        # Add classes first (we need them to determine which functions are methods)
        for cls in result.classes:
            cls_dict = {
                "name": cls.name,
                "file": cls.file_path,
                "line": cls.start.row + 1,
                "column": cls.start.column,
                "start_row": cls.start.row,
                "start_column": cls.start.column,
                "end_row": cls.end.row,
                "end_column": cls.end.column,
            }
            # Add enhanced fields if present
            if cls.methods:
                cls_dict["methods"] = cls.methods
            if cls.base_classes:
                cls_dict["base_classes"] = cls.base_classes
            graph.classes.append(cls_dict)
        
        # Add structs (C structs/unions/enums)
        for struct in result.structs:
            struct_dict = {
                "name": struct.name,
                "file": struct.file_path,
                "line": struct.start.row + 1,
                "column": struct.start.column,
                "start_row": struct.start.row,
                "start_column": struct.start.column,
                "end_row": struct.end.row,
                "end_column": struct.end.column,
            }
            # Add fields if present
            if struct.fields:
                struct_dict["fields"] = struct.fields
            graph.structs.append(struct_dict)
        
        # Add functions and determine which are methods
        for func in result.functions:
            func_dict = {
                "name": func.name,
                "file": func.file_path,
                "line": func.start.row + 1,
                "column": func.start.column,
                "start_row": func.start.row,
                "start_column": func.start.column,
                "end_row": func.end.row,
                "end_column": func.end.column,
            }
            # Add enhanced fields if present
            if func.signature:
                func_dict["signature"] = func.signature
            if func.parameters:
                func_dict["parameters"] = func.parameters
            if func.return_type:
                func_dict["return_type"] = func.return_type
            if func.docstring:
                func_dict["docstring"] = func.docstring
            
            # Check if this function is a method (inside a class)
            # Match by checking if function is within class line range and method name matches
            for cls in result.classes:
                if (cls.file_path == func.file_path and
                    cls.methods and func.name in cls.methods and
                    func.start.row >= cls.start.row and
                    func.start.row <= cls.end.row):
                    func_dict["belongs_to_class"] = cls.name
                    break
            
            graph.functions.append(func_dict)
        
        # Add synthetic module-level function node to anchor top-level calls
        # This allows module-level function calls to be stored correctly
        # Use line 1 (first line of file) to represent module scope
        module_func_dict = {
            "name": "<module>",
            "file": result.file_path,
            "line": 1,  # Use line 1 to represent module scope (avoids validation warning for line 0)
            "column": 0,
            "start_row": 0,
            "start_column": 0,
            "end_row": 0,
            "end_column": 0,
            "signature": f"<module> in {result.file_path}",
        }
        graph.functions.append(module_func_dict)
        
        # Add imports
        for imp in result.imports:
            imp_dict = {
                "text": imp.text.strip(),
                "file": imp.file_path,
                "line": imp.start.row + 1,
                "start_row": imp.start.row,
                "start_column": imp.start.column,
                "end_row": imp.end.row,
                "end_column": imp.end.column,
            }
            # Module is required by schema - ensure it's always set
            if imp.module:
                imp_dict["module"] = imp.module
            else:
                # Fallback: try to extract from text (shouldn't happen if parser is working correctly)
                match = re.search(r'#include\s+["<]([^">]+)[">]', imp.text)
                if match:
                    imp_dict["module"] = match.group(1)
                else:
                    # Last resort: use text itself
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Import in {imp.file_path}:{imp.start.row+1} has no module and couldn't extract from text: {imp.text}")
                    imp_dict["module"] = imp.text.strip()
            if imp.imported_items:
                imp_dict["imported_items"] = imp.imported_items
            if imp.alias:
                imp_dict["alias"] = imp.alias
            graph.imports.append(imp_dict)
        
        # Add macros
        for macro in result.macros:
            macro_dict = {
                "name": macro.name,
                "file": macro.file_path,
                "line": macro.start.row + 1,
                "column": macro.start.column,
                "start_row": macro.start.row,
                "start_column": macro.start.column,
                "end_row": macro.end.row,
                "end_column": macro.end.column,
            }
            if macro.value:
                macro_dict["value"] = macro.value
            if macro.parameters:
                macro_dict["parameters"] = macro.parameters
            graph.macros.append(macro_dict)
        
        # Add variables
        for var in result.variables:
            var_dict = {
                "name": var.name,
                "file": var.file_path,
                "line": var.start.row + 1,
                "column": var.start.column,
                "start_row": var.start.row,
                "start_column": var.start.column,
                "end_row": var.end.row,
                "end_column": var.end.column,
                "is_global": var.is_global,
            }
            if var.type:
                var_dict["type"] = var.type
            if var.storage_class:
                var_dict["storage_class"] = var.storage_class
            if var.containing_function:
                var_dict["containing_function"] = var.containing_function
            graph.variables.append(var_dict)
        
        # Add typedefs (as nodes)
        for tdef in result.typedefs:
            tdef_dict = {
                "name": tdef.name,
                "file": tdef.file_path,
                "line": tdef.start.row + 1,
                "column": tdef.start.column,
                "start_row": tdef.start.row,
                "start_column": tdef.start.column,
                "end_row": tdef.end.row,
                "end_column": tdef.end.column,
                "underlying_type": tdef.underlying_type,
            }
            graph.typedefs.append(tdef_dict)
        
        # Add struct field accesses
        for sfa in result.struct_field_accesses:
            sfa_dict = {
                "struct_name": sfa.struct_name,
                "field_name": sfa.field_name,
                "file": sfa.file_path,
                "line": sfa.start.row + 1,
                "column": sfa.start.column,
                "start_row": sfa.start.row,
                "start_column": sfa.start.column,
                "end_row": sfa.end.row,
                "end_column": sfa.end.column,
                "access_type": sfa.access_type,
            }
            graph.struct_field_accesses.append(sfa_dict)
    
    # Extract relationships
    # Add function call relationships
    for result in parse_results:
        for call in result.function_calls:
            graph.relationships.append({
                "type": "function_call",
                "caller": call.caller_name,
                "callee": call.callee_name,
                "is_method_call": call.is_method_call,
                "file": call.file_path,
                "line": call.start.row + 1,
                "start_row": call.start.row,
                "start_column": call.start.column,
            })
    
    # Add class inheritance relationships
    for result in parse_results:
        for cls in result.classes:
            for base_class in cls.base_classes:
                graph.relationships.append({
                    "type": "inheritance",
                    "derived": cls.name,
                    "base": base_class,
                    "file": cls.file_path,
                    "line": cls.start.row + 1,
                })
    
    # Add import dependency relationships
    for result in parse_results:
        for imp in result.imports:
            if imp.module:
                graph.relationships.append({
                    "type": "import",
                    "file": result.file_path,
                    "module": imp.module,
                    "is_system": "system" in (imp.imported_items or []),
                    "line": imp.start.row + 1,
                })
    
    # Add typedef relationships (for C) - keep for backward compatibility
    for result in parse_results:
        for tdef in result.typedefs:
            graph.relationships.append({
                "type": "typedef",
                "name": tdef.name,
                "underlying_type": tdef.underlying_type,
                "file": tdef.file_path,
                "line": tdef.start.row + 1,
            })
    
    # Build a map of struct names to Struct nodes for struct field access resolution
    struct_name_to_struct = {}
    for result in parse_results:
        for struct in result.structs:
            struct_name_to_struct[(struct.name, result.file_path)] = struct
    
    # Resolve struct field accesses to Struct nodes
    for result in parse_results:
        for sfa in result.struct_field_accesses:
            # Try to find matching struct
            resolved_struct = None
            
            # First try exact match by name and file
            key = (sfa.struct_name, result.file_path)
            if key in struct_name_to_struct:
                resolved_struct = struct_name_to_struct[key]
            else:
                # Try to find by name only (might be in different file)
                for (name, file_path), struct in struct_name_to_struct.items():
                    if name == sfa.struct_name:
                        resolved_struct = struct
                        break
                
                # If still not found, check typedef aliases
                if not resolved_struct:
                    for tdef in result.typedefs:
                        if tdef.name == sfa.struct_name:
                            # Check if underlying type is a struct
                            if "struct" in tdef.underlying_type.lower():
                                # Extract struct name from underlying type
                                # e.g., "struct MyStruct" -> "MyStruct"
                                parts = tdef.underlying_type.split()
                                if len(parts) > 1:
                                    struct_name = parts[-1]
                                    for (name, file_path), struct in struct_name_to_struct.items():
                                        if name == struct_name:
                                            resolved_struct = struct
                                            break
                            if resolved_struct:
                                break
            
            # Store resolved struct name if found
            if resolved_struct:
                # Find the sfa_dict we just created and add resolved_struct_name
                for sfa_dict in graph.struct_field_accesses:
                    if (sfa_dict["struct_name"] == sfa.struct_name and
                        sfa_dict["field_name"] == sfa.field_name and
                        sfa_dict["file"] == sfa.file_path and
                        sfa_dict["line"] == sfa.start.row + 1):
                        sfa_dict["resolved_struct_name"] = resolved_struct.name
                        sfa_dict["resolved_struct_file"] = resolved_struct.file_path
                        break
    
    # Add macro usage relationships
    for result in parse_results:
        # Group macro usages by macro name
        macro_usage_map = {}
        for mu in result.macro_usages:
            if mu.macro_name not in macro_usage_map:
                macro_usage_map[mu.macro_name] = []
            macro_usage_map[mu.macro_name].append(mu)
        
        # Create relationships for each macro usage
        for macro_name, usages in macro_usage_map.items():
            # Find macro definition(s) with this name
            matching_macros = [m for m in result.macros if m.name == macro_name]
            
            if matching_macros:
                # Create relationship for each usage
                for usage in usages:
                    graph.relationships.append({
                        "type": "macro_usage",
                        "macro": macro_name,
                        "file": usage.file_path,
                        "function": usage.function_context,
                        "line": usage.start.row + 1,
                    })
    
    # Add variable usage relationships
    for result in parse_results:
        # Group variable usages by variable name
        var_usage_map = {}
        for vu in result.variable_usages:
            if vu.variable_name not in var_usage_map:
                var_usage_map[vu.variable_name] = []
            var_usage_map[vu.variable_name].append(vu)
        
        # Create relationships for each variable usage
        for var_name, usages in var_usage_map.items():
            # Find variable definition(s) with this name
            matching_vars = [v for v in result.variables if v.name == var_name]
            
            if matching_vars:
                # For each usage, find the best matching variable (handle shadowing)
                for usage in usages:
                    # Prefer local variable in same function, then global
                    matching_var = None
                    for var in matching_vars:
                        if (not var.is_global and 
                            var.containing_function == usage.function_context):
                            matching_var = var
                            break
                    
                    if not matching_var:
                        # Fall back to global variable
                        for var in matching_vars:
                            if var.is_global:
                                matching_var = var
                                break
                    
                    if not matching_var and matching_vars:
                        matching_var = matching_vars[0]  # Use first match
                    
                    if matching_var:
                        graph.relationships.append({
                            "type": "variable_usage",
                            "variable": var_name,
                            "file": usage.file_path,
                            "function": usage.function_context,
                            "line": usage.start.row + 1,
                        })
    
    # Add typedef usage relationships
    for result in parse_results:
        # Group typedef usages by typedef name
        typedef_usage_map = {}
        for tu in result.typedef_usages:
            if tu.typedef_name not in typedef_usage_map:
                typedef_usage_map[tu.typedef_name] = []
            typedef_usage_map[tu.typedef_name].append(tu)
        
        # Create relationships for each typedef usage
        for typedef_name, usages in typedef_usage_map.items():
            # Find typedef definition(s) with this name
            matching_typedefs = [t for t in result.typedefs if t.name == typedef_name]
            
            if matching_typedefs:
                # Create relationship for each usage
                for usage in usages:
                    graph.relationships.append({
                        "type": "typedef_usage",
                        "typedef": typedef_name,
                        "file": usage.file_path,
                        "line": usage.start.row + 1,
                    })
    
    return graph

