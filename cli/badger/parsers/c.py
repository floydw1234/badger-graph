"""C parser using tree-sitter."""

import logging
import re
from pathlib import Path
from tree_sitter import Language, Parser
from .base import (
    BaseParser, ParseResult, Function, Class, Struct, Import, Position, FunctionCall, Typedef,
    Macro, Variable, StructFieldAccess, MacroUsage, VariableUsage, TypedefUsage
)


class CParser(BaseParser):
    """Parser for C source files."""
    
    def __init__(self):
        super().__init__("c")
        self.initialize()
    
    def initialize(self) -> None:
        """Initialize tree-sitter C parser."""
        try:
            from tree_sitter_c import language
            lang = Language(language())
            self.parser = Parser(lang)
        except ImportError:
            # Fallback: try compiled library approach
            try:
                C = Language("build/my-languages.so", "c")
                self.parser = Parser(C)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to initialize C parser. "
                    f"Make sure tree-sitter-c is installed: pip install tree-sitter-c. "
                    f"Error: {e}"
                )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize C parser: {e}")
    
    def parse_file(self, file_path: Path) -> ParseResult:
        """Parse a C file and return parse results."""
        if not self.parser:
            raise RuntimeError("Parser not initialized")
        
        try:
            with open(file_path, "rb") as f:
                source_code = f.read()
            
            tree = self.parser.parse(source_code)
            if not tree:
                raise RuntimeError("Failed to parse source code")
            
            root_node = tree.root_node
            
            # Extract information from AST
            functions = self.extract_functions(root_node, source_code)
            structs = self.extract_structs(root_node)
            imports = self.extract_imports(root_node)
            typedefs = self.extract_typedefs(root_node)
            macros = self.extract_macros(root_node)
            variables = self.extract_variables(root_node)
            struct_field_accesses = self.extract_struct_field_accesses(root_node)
            
            # Set file_path for all extracted items
            file_path_str = str(file_path)
            for func in functions:
                func.file_path = file_path_str
            for struct in structs:
                struct.file_path = file_path_str
            for imp in imports:
                imp.file_path = file_path_str
            for tdef in typedefs:
                tdef.file_path = file_path_str
            for macro in macros:
                macro.file_path = file_path_str
            for var in variables:
                var.file_path = file_path_str
            for sfa in struct_field_accesses:
                sfa.file_path = file_path_str
            
            # Extract function calls
            function_calls = self.extract_function_calls(root_node, source_code)
            for call in function_calls:
                call.file_path = file_path_str
            
            # Extract usages (need to be done after definitions are extracted)
            macro_usages = self.extract_macro_usages(root_node, macros)
            variable_usages = self.extract_variable_usages(root_node, variables)
            typedef_usages = self.extract_typedef_usages(root_node, typedefs)
            
            for mu in macro_usages:
                mu.file_path = file_path_str
            for vu in variable_usages:
                vu.file_path = file_path_str
            for tu in typedef_usages:
                tu.file_path = file_path_str
            
            return ParseResult(
                file_path=file_path_str,
                functions=functions,
                classes=[],  # C doesn't have classes, only structs
                structs=structs,
                imports=imports,
                total_nodes=self.count_nodes(root_node),
                tree_string=root_node.text.decode("utf-8") if hasattr(root_node, "text") else None,
                function_calls=function_calls,
                typedefs=typedefs,
                macros=macros,
                variables=variables,
                struct_field_accesses=struct_field_accesses,
                macro_usages=macro_usages,
                variable_usages=variable_usages,
                typedef_usages=typedef_usages
            )
        except Exception as e:
            raise RuntimeError(f"Error parsing C file {file_path}: {e}")
    
    def extract_functions(self, node, source_code: bytes = None) -> list[Function]:
        """Extract function definitions and declarations from AST node."""
        functions = []
        
        def get_function_name(declarator):
            """Extract function name from declarator."""
            if declarator.type == "function_declarator":
                # First child is usually the identifier (function name)
                for i in range(declarator.child_count):
                    child = declarator.child(i)
                    if child.type == "identifier":
                        return child.text.decode("utf-8")
            elif declarator.type == "identifier":
                return declarator.text.decode("utf-8")
            return None
        
        def extract_parameters(parameter_list):
            """Extract parameter names from parameter list."""
            param_names = []
            if not parameter_list:
                return param_names
            
            for i in range(parameter_list.child_count):
                child = parameter_list.child(i)
                if child.type == "parameter_declaration":
                    # Parameter name can be:
                    # 1. Direct identifier child
                    # 2. In a declarator field
                    # 3. In a pointer_declarator
                    param_name = None
                    
                    # Check for direct identifier
                    for j in range(child.child_count):
                        c = child.child(j)
                        if c.type == "identifier":
                            param_name = c.text.decode("utf-8")
                            break
                        elif c.type == "pointer_declarator":
                            # Pointer parameter: *name
                            # Find identifier in pointer_declarator
                            for k in range(c.child_count):
                                d = c.child(k)
                                if d.type == "identifier":
                                    param_name = d.text.decode("utf-8")
                                    break
                    
                    # Fallback: check declarator field
                    if not param_name:
                        declarator = child.child_by_field_name("declarator")
                        if declarator:
                            if declarator.type == "identifier":
                                param_name = declarator.text.decode("utf-8")
                            elif declarator.type == "pointer_declarator":
                                for k in range(declarator.child_count):
                                    d = declarator.child(k)
                                    if d.type == "identifier":
                                        param_name = d.text.decode("utf-8")
                                        break
                    
                    if param_name:
                        param_names.append(param_name)
                    # If no name found, might be unnamed parameter (just type) - skip
            return param_names
        
        def extract_return_type(func_node):
            """Extract return type from function node."""
            # Return type can be:
            # 1. First child if it's a type (primitive_type, type_identifier)
            # 2. For pointer types: type_identifier + pointer_declarator
            # 3. For complex types: might need to reconstruct
            
            if func_node.child_count == 0:
                return None
            
            first_child = func_node.child(0)
            
            # Simple case: primitive type or type identifier
            if first_child.type in ("primitive_type", "type_identifier", "sized_type_specifier"):
                return_type = first_child.text.decode("utf-8")
                
                # Check if next child is pointer_declarator (for pointer return types)
                if func_node.child_count > 1:
                    second_child = func_node.child(1)
                    if second_child.type == "pointer_declarator":
                        return_type += "*"
                
                return return_type
            
            # Handle pointer types where type comes before pointer_declarator
            # This happens when return type is like "User*"
            if first_child.type == "type_identifier" and func_node.child_count > 1:
                second_child = func_node.child(1)
                if second_child.type == "pointer_declarator":
                    return first_child.text.decode("utf-8") + "*"
            
            return None
        
        def build_signature(name, params, return_type, is_declaration=False):
            """Build function signature string."""
            sig = ""
            if return_type:
                sig += return_type + " "
            sig += name + "("
            if params:
                sig += ", ".join(params)
            sig += ")"
            if is_declaration:
                sig += ";"
            return sig
        
        def walk_tree(n):
            is_declaration = False
            if n.type == "function_definition":
                is_declaration = False
            elif n.type == "declaration":
                # Check if this is a function declaration
                declarator = n.child_by_field_name("declarator")
                if declarator and declarator.type == "function_declarator":
                    is_declaration = True
                else:
                    # Check if declarator is in a pointer_declarator
                    for i in range(n.child_count):
                        child = n.child(i)
                        if child.type == "pointer_declarator":
                            for j in range(child.child_count):
                                c = child.child(j)
                                if c.type == "function_declarator":
                                    is_declaration = True
                                    break
                            if is_declaration:
                                break
                
                if not is_declaration:
                    # Not a function declaration, skip
                    for i in range(n.child_count):
                        walk_tree(n.child(i))
                    return
            
            if n.type == "function_definition" or (n.type == "declaration" and is_declaration):
                declarator = n.child_by_field_name("declarator")
                if not declarator and n.type == "declaration":
                    # For declarations, declarator might be a direct child
                    for i in range(n.child_count):
                        child = n.child(i)
                        if child.type == "function_declarator":
                            declarator = child
                            break
                
                # If declarator is a pointer_declarator, find function_declarator inside it
                if declarator and declarator.type == "pointer_declarator":
                    for i in range(declarator.child_count):
                        child = declarator.child(i)
                        if child.type == "function_declarator":
                            declarator = child
                            break
                
                # If still no function_declarator, check children for pointer_declarator
                if not declarator or declarator.type != "function_declarator":
                    for i in range(n.child_count):
                        child = n.child(i)
                        if child.type == "pointer_declarator":
                            # Check if pointer_declarator contains function_declarator
                            for j in range(child.child_count):
                                c = child.child(j)
                                if c.type == "function_declarator":
                                    declarator = c
                                    break
                            if declarator and declarator.type == "function_declarator":
                                break
                
                if declarator and declarator.type == "function_declarator":
                    function_name = get_function_name(declarator)
                    if function_name:
                        # Extract return type
                        return_type = extract_return_type(n)
                        
                        # Extract parameters
                        parameter_list = declarator.child_by_field_name("parameters")
                        parameters = extract_parameters(parameter_list)
                        
                        # Build signature
                        signature = build_signature(function_name, parameters, return_type, is_declaration)
                        
                        functions.append(Function(
                            name=function_name,
                            start=Position(
                                row=n.start_point[0],
                                column=n.start_point[1]
                            ),
                            end=Position(
                                row=n.end_point[0],
                                column=n.end_point[1]
                            ),
                            file_path="",  # Will be set in parse_file
                            signature=signature,
                            parameters=parameters,
                            return_type=return_type,
                            docstring=None  # C doesn't have docstrings like Python
                        ))
            
            for i in range(n.child_count):
                walk_tree(n.child(i))
        
        walk_tree(node)
        return functions
    
    def extract_classes(self, node) -> list[Class]:
        """Extract class definitions from AST node.
        
        C doesn't have classes, only structs. This returns an empty list.
        Use extract_structs() for C structs/unions/enums.
        """
        return []
    
    def extract_structs(self, node) -> list[Struct]:
        """Extract struct, union, and enum definitions."""
        structs = []
        
        def extract_fields(specifier_node):
            """Extract field names from struct/union/enum."""
            fields = []
            field_list = specifier_node.child_by_field_name("body")
            if not field_list:
                # Try field_declaration_list
                for i in range(specifier_node.child_count):
                    child = specifier_node.child(i)
                    if child.type == "field_declaration_list":
                        field_list = child
                        break
            
            if field_list:
                for i in range(field_list.child_count):
                    child = field_list.child(i)
                    if child.type == "field_declaration":
                        # Field name can be:
                        # 1. field_identifier (direct child)
                        # 2. In a declarator
                        # 3. In a pointer_declarator
                        field_name = None
                        
                        # Check for field_identifier (most common)
                        for j in range(child.child_count):
                            c = child.child(j)
                            if c.type == "field_identifier":
                                field_name = c.text.decode("utf-8")
                                break
                            elif c.type == "identifier":
                                field_name = c.text.decode("utf-8")
                                break
                        
                        # Check declarator if not found
                        if not field_name:
                            declarator = child.child_by_field_name("declarator")
                            if declarator:
                                if declarator.type == "identifier" or declarator.type == "field_identifier":
                                    field_name = declarator.text.decode("utf-8")
                                elif declarator.type == "pointer_declarator":
                                    # Pointer field: *name
                                    for j in range(declarator.child_count):
                                        d = declarator.child(j)
                                        if d.type == "identifier" or d.type == "field_identifier":
                                            field_name = d.text.decode("utf-8")
                                            break
                                elif declarator.type == "array_declarator":
                                    # Array field: name[size]
                                    array_decl = declarator.child_by_field_name("declarator")
                                    if array_decl:
                                        if array_decl.type == "identifier" or array_decl.type == "field_identifier":
                                            field_name = array_decl.text.decode("utf-8")
                                        else:
                                            # Check children of array_declarator
                                            for k in range(array_decl.child_count):
                                                e = array_decl.child(k)
                                                if e.type == "identifier" or e.type == "field_identifier":
                                                    field_name = e.text.decode("utf-8")
                                                    break
                        
                        if field_name:
                            fields.append(field_name)
            return fields
        
        def walk_tree(n):
            # Handle typedef struct/union/enum
            if n.type == "type_definition":
                # Check if it's a typedef struct/union/enum
                specifier = None
                type_name = None
                
                for i in range(n.child_count):
                    child = n.child(i)
                    if child.type in ("struct_specifier", "union_specifier", "enum_specifier"):
                        specifier = child
                    elif child.type == "type_identifier":
                        type_name = child.text.decode("utf-8")
                
                if specifier and type_name:
                    # Extract fields
                    fields = extract_fields(specifier)
                    
                    structs.append(Struct(
                        name=type_name,
                        start=Position(
                            row=n.start_point[0],
                            column=n.start_point[1]
                        ),
                        end=Position(
                            row=n.end_point[0],
                            column=n.end_point[1]
                        ),
                        file_path="",  # Will be set in parse_file
                        fields=fields
                    ))
            
            # Handle regular struct/union/enum (not typedef)
            elif n.type in ("struct_specifier", "union_specifier", "enum_specifier"):
                name_node = n.child_by_field_name("name")
                if name_node:
                    struct_name = name_node.text.decode("utf-8")
                    # Extract fields
                    fields = extract_fields(n)
                    
                    structs.append(Struct(
                        name=struct_name,
                        start=Position(
                            row=n.start_point[0],
                            column=n.start_point[1]
                        ),
                        end=Position(
                            row=n.end_point[0],
                            column=n.end_point[1]
                        ),
                        file_path="",  # Will be set in parse_file
                        fields=fields
                    ))
            
            for i in range(n.child_count):
                walk_tree(n.child(i))
        
        walk_tree(node)
        return structs
    
    def extract_imports(self, node) -> list[Import]:
        """Extract include directives (as imports)."""
        imports = []
        
        def extract_include_info(include_node):
            """Extract information from preproc_include node."""
            import_text = include_node.text.decode("utf-8")
            module = None
            is_system_include = False
            
            # Find the included file name
            for i in range(include_node.child_count):
                child = include_node.child(i)
                if child.type == "system_lib_string":
                    # System include: #include <file.h>
                    module = child.text.decode("utf-8").strip("<>")
                    is_system_include = True
                    break
                elif child.type == "string_literal":
                    # Local include: #include "file.h"
                    module = child.text.decode("utf-8").strip('"')
                    is_system_include = False
                    break
            
            # Fallback: parse from text if tree-sitter didn't find it
            # This ensures module is always set, which is required by the schema
            if module is None:
                # Try to extract from #include "..." or #include <...>
                match = re.search(r'#include\s+["<]([^">]+)[">]', import_text)
                if match:
                    module = match.group(1)
                    is_system_include = '<' in import_text
                else:
                    # Last resort: use the text itself (shouldn't happen for valid includes)
                    # Log a warning but still set module to avoid schema violations
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Could not extract module from include: {import_text}")
                    module = import_text.strip()
            
            # Store module name, and use imported_items to indicate system vs local
            imported_items = []
            if is_system_include:
                imported_items.append("system")
            else:
                imported_items.append("local")
            
            return Import(
                text=import_text,
                start=Position(
                    row=include_node.start_point[0],
                    column=include_node.start_point[1]
                ),
                end=Position(
                    row=include_node.end_point[0],
                    column=include_node.end_point[1]
                ),
                file_path="",  # Will be set in parse_file
                module=module,
                imported_items=imported_items,
                alias=None
            )
        
        def walk_tree(n):
            # C preprocessor includes
            if n.type == "preproc_include":
                imp = extract_include_info(n)
                # Filter out system includes (standard library)
                if imp and "system" not in imp.imported_items:
                    imports.append(imp)
            
            for i in range(n.child_count):
                walk_tree(n.child(i))
        
        walk_tree(node)
        return imports
    
    def extract_typedefs(self, node) -> list[Typedef]:
        """Extract typedef definitions from AST node."""
        typedefs = []
        
        def extract_underlying_type(type_def_node):
            """Extract the underlying type from typedef."""
            # The underlying type is typically before the type_identifier
            for i in range(type_def_node.child_count):
                child = type_def_node.child(i)
                if child.type in ("primitive_type", "type_identifier", "sized_type_specifier"):
                    return child.text.decode("utf-8")
                elif child.type in ("struct_specifier", "union_specifier", "enum_specifier"):
                    # For typedef struct, return "struct" or the struct name
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        return f"struct {name_node.text.decode('utf-8')}"
                    return "struct"
            return None
        
        def walk_tree(n):
            if n.type == "type_definition":
                # Find the type name (type_identifier)
                type_name = None
                for i in range(n.child_count):
                    child = n.child(i)
                    if child.type == "type_identifier":
                        type_name = child.text.decode("utf-8")
                        break
                
                if type_name:
                    # Skip if it's a typedef struct/union/enum (already handled in extract_classes)
                    is_struct_typedef = False
                    for i in range(n.child_count):
                        child = n.child(i)
                        if child.type in ("struct_specifier", "union_specifier", "enum_specifier"):
                            is_struct_typedef = True
                            break
                    
                    # Only extract non-struct typedefs (simple type aliases)
                    if not is_struct_typedef:
                        underlying_type = extract_underlying_type(n)
                        typedefs.append(Typedef(
                            name=type_name,
                            underlying_type=underlying_type or "unknown",
                            start=Position(
                                row=n.start_point[0],
                                column=n.start_point[1]
                            ),
                            end=Position(
                                row=n.end_point[0],
                                column=n.end_point[1]
                            ),
                            file_path=""  # Will be set in parse_file
                        ))
            
            for i in range(n.child_count):
                walk_tree(n.child(i))
        
        walk_tree(node)
        return typedefs
    
    def extract_function_calls(self, node, source_code: bytes = None) -> list[FunctionCall]:
        """Extract function calls from AST node."""
        function_calls = []
        caller_stack = ["module"]  # Track current function context
        
        def get_callee_name(call_node):
            """Extract the name of the function being called."""
            # call_expression has function as first child
            if call_node.child_count == 0:
                return None
            
            function_expr = call_node.child(0)
            
            if function_expr.type == "identifier":
                # Direct function call: func()
                return function_expr.text.decode("utf-8")
            elif function_expr.type == "field_expression":
                # Method call: obj->method() or obj.method()
                # Find the field name (method name)
                field = function_expr.child_by_field_name("field")
                if field:
                    return field.text.decode("utf-8")
                # Fallback: last identifier in field_expression
                for i in range(function_expr.child_count - 1, -1, -1):
                    child = function_expr.child(i)
                    if child.type == "field_identifier" or child.type == "identifier":
                        return child.text.decode("utf-8")
            elif function_expr.type == "parenthesized_expression":
                # Function pointer call: (*func_ptr)()
                # Try to find identifier inside
                for i in range(function_expr.child_count):
                    child = function_expr.child(i)
                    if child.type == "identifier":
                        return child.text.decode("utf-8")
                    elif child.type == "pointer_expression":
                        # (*ptr)() - find identifier in pointer_expression
                        for j in range(child.child_count):
                            c = child.child(j)
                            if c.type == "identifier":
                                return c.text.decode("utf-8")
            elif function_expr.type == "pointer_expression":
                # Function pointer: func_ptr()
                for i in range(function_expr.child_count):
                    child = function_expr.child(i)
                    if child.type == "identifier":
                        return child.text.decode("utf-8")
            
            return None
        
        def is_method_call(call_node):
            """Determine if this is a method call (obj->method() or obj.method())."""
            if call_node.child_count == 0:
                return False
            function_expr = call_node.child(0)
            return function_expr.type == "field_expression"
        
        def walk_tree(n):
            # Track function definitions to know caller context
            if n.type == "function_definition":
                declarator = n.child_by_field_name("declarator")
                if not declarator:
                    # Check for pointer_declarator
                    for i in range(n.child_count):
                        child = n.child(i)
                        if child.type == "pointer_declarator":
                            for j in range(child.child_count):
                                c = child.child(j)
                                if c.type == "function_declarator":
                                    declarator = c
                                    break
                            if declarator:
                                break
                
                if declarator:
                    # Extract function name
                    for i in range(declarator.child_count):
                        child = declarator.child(i)
                        if child.type == "identifier":
                            caller_name = child.text.decode("utf-8")
                            caller_stack.append(caller_name)
                            break
            
            # Find call expressions
            if n.type == "call_expression":
                callee_name = get_callee_name(n)
                if callee_name:
                    is_method = is_method_call(n)
                    current_caller = caller_stack[-1] if caller_stack else "module"
                    
                    function_calls.append(FunctionCall(
                        caller_name=current_caller,
                        callee_name=callee_name,
                        is_method_call=is_method,
                        start=Position(
                            row=n.start_point[0],
                            column=n.start_point[1]
                        ),
                        end=Position(
                            row=n.end_point[0],
                            column=n.end_point[1]
                        ),
                        file_path=""  # Will be set in parse_file
                    ))
            
            # Recursively walk children
            for i in range(n.child_count):
                walk_tree(n.child(i))
            
            # Pop caller stack when leaving function definition
            if n.type == "function_definition":
                if len(caller_stack) > 1:
                    caller_stack.pop()
        
        walk_tree(node)
        return function_calls
    
    def extract_macros(self, node) -> list[Macro]:
        """Extract macro definitions from AST node.
        
        Handles both simple macros (#define FOO 42) and function-like macros
        (#define MAX(a,b) ((a)>(b)?(a):(b))).
        """
        macros = []
        
        def extract_macro_info(preproc_def_node):
            """Extract information from preproc_def node."""
            macro_name = None
            macro_value = None
            parameters = []
            
            # Find the macro name (first identifier after #define)
            for i in range(preproc_def_node.child_count):
                child = preproc_def_node.child(i)
                if child.type == "identifier":
                    macro_name = child.text.decode("utf-8")
                    break
            
            if not macro_name:
                return None
            
            # Check if it's a function-like macro (has preproc_params)
            preproc_params = preproc_def_node.child_by_field_name("preproc_params")
            if preproc_params:
                # Function-like macro: extract parameters
                for j in range(preproc_params.child_count):
                    param_child = preproc_params.child(j)
                    if param_child.type == "identifier":
                        parameters.append(param_child.text.decode("utf-8"))
            else:
                # Simple macro: extract value (everything after the name)
                # The value is typically in a preproc_arg or as remaining children
                preproc_arg = preproc_def_node.child_by_field_name("preproc_arg")
                if preproc_arg:
                    macro_value = preproc_arg.text.decode("utf-8").strip()
                else:
                    # Try to find value in remaining children
                    found_name = False
                    value_parts = []
                    for j in range(preproc_def_node.child_count):
                        child = preproc_def_node.child(j)
                        if found_name and child.type != "identifier":
                            value_parts.append(child.text.decode("utf-8"))
                        elif child.type == "identifier" and child.text.decode("utf-8") == macro_name:
                            found_name = True
                    if value_parts:
                        macro_value = " ".join(value_parts).strip()
            
            return Macro(
                name=macro_name,
                value=macro_value,
                parameters=parameters,
                start=Position(
                    row=preproc_def_node.start_point[0],
                    column=preproc_def_node.start_point[1]
                ),
                end=Position(
                    row=preproc_def_node.end_point[0],
                    column=preproc_def_node.end_point[1]
                ),
                file_path=""  # Will be set in parse_file
            )
        
        def walk_tree(n):
            if n.type == "preproc_def":
                macro = extract_macro_info(n)
                if macro:
                    macros.append(macro)
            
            for i in range(n.child_count):
                walk_tree(n.child(i))
        
        walk_tree(node)
        return macros
    
    def extract_variables(self, node) -> list[Variable]:
        """Extract variable declarations from AST node.
        
        Tracks global vs local variables and their containing function context.
        """
        variables = []
        function_stack = []  # Track current function context
        
        def extract_variable_info(decl_node):
            """Extract variable information from declaration node."""
            # Skip if this is a function declaration
            declarator = decl_node.child_by_field_name("declarator")
            if declarator and declarator.type == "function_declarator":
                return None
            
            var_name = None
            var_type = None
            storage_class = None
            
            # Extract storage class (static, extern, etc.)
            for i in range(decl_node.child_count):
                child = decl_node.child(i)
                if child.type == "storage_class_specifier":
                    storage_class = child.text.decode("utf-8")
                    break
            
            # Extract type
            type_parts = []
            for i in range(decl_node.child_count):
                child = decl_node.child(i)
                if child.type in ("primitive_type", "type_identifier", "sized_type_specifier"):
                    type_parts.append(child.text.decode("utf-8"))
                elif child.type == "pointer_declarator":
                    type_parts.append("*")
                    # Check if there's a type before the pointer
                    break
            
            if type_parts:
                var_type = " ".join(type_parts)
            
            # Extract variable name from declarator
            if declarator:
                # Variable name can be in different places depending on declaration type
                if declarator.type == "identifier":
                    var_name = declarator.text.decode("utf-8")
                elif declarator.type == "pointer_declarator":
                    # Find identifier in pointer_declarator
                    for j in range(declarator.child_count):
                        d_child = declarator.child(j)
                        if d_child.type == "identifier":
                            var_name = d_child.text.decode("utf-8")
                            break
                elif declarator.type == "array_declarator":
                    # Find identifier in array_declarator
                    array_decl = declarator.child_by_field_name("declarator")
                    if array_decl:
                        if array_decl.type == "identifier":
                            var_name = array_decl.text.decode("utf-8")
                        else:
                            for k in range(array_decl.child_count):
                                e = array_decl.child(k)
                                if e.type == "identifier":
                                    var_name = e.text.decode("utf-8")
                                    break
            
            if not var_name:
                return None
            
            # Determine if global or local
            is_global = len(function_stack) == 0
            containing_function = function_stack[-1] if function_stack else None
            
            return Variable(
                name=var_name,
                type=var_type,
                storage_class=storage_class,
                is_global=is_global,
                containing_function=containing_function,
                start=Position(
                    row=decl_node.start_point[0],
                    column=decl_node.start_point[1]
                ),
                end=Position(
                    row=decl_node.end_point[0],
                    column=decl_node.end_point[1]
                ),
                file_path=""  # Will be set in parse_file
            )
        
        def walk_tree(n):
            # Track function definitions
            if n.type == "function_definition":
                declarator = n.child_by_field_name("declarator")
                if declarator:
                    # Extract function name
                    for i in range(declarator.child_count):
                        child = declarator.child(i)
                        if child.type == "identifier":
                            func_name = child.text.decode("utf-8")
                            function_stack.append(func_name)
                            break
            
            # Extract variable declarations
            if n.type == "declaration":
                var = extract_variable_info(n)
                if var:
                    variables.append(var)
            
            # Recursively walk children
            for i in range(n.child_count):
                walk_tree(n.child(i))
            
            # Pop function stack when leaving function definition
            if n.type == "function_definition":
                if function_stack:
                    function_stack.pop()
        
        walk_tree(node)
        return variables
    
    def extract_struct_field_accesses(self, node) -> list[StructFieldAccess]:
        """Extract struct field accesses from AST node.
        
        Handles both direct access (struct.field) and pointer access (struct->field).
        Also handles casts: ((MyStruct*)ptr)->field
        
        Note: For variable-based accesses (e.g., user->name), we store the variable name.
        Type resolution to struct names happens in the graph builder.
        """
        field_accesses = []
        
        # Build a map of variable names to their types from function parameters and declarations
        # This helps resolve variable names to struct types
        variable_types = {}
        
        def extract_type_from_declaration(decl_node):
            """Extract type name from a declaration node."""
            # Look for type_identifier in the declaration
            # Handle cases like: const User* user, User* user, User user
            type_identifier = None
            for i in range(decl_node.child_count):
                child = decl_node.child(i)
                if child.type == "type_identifier":
                    type_identifier = child.text.decode("utf-8")
                    # Found type identifier, return it
                    return type_identifier
                elif child.type == "primitive_type":
                    # Skip primitive types (int, char, etc.)
                    continue
                elif child.type in ("init_declarator", "declarator", "pointer_declarator"):
                    # Don't recurse into declarator - the type is before it
                    continue
                elif child.type in ("const", "volatile", "restrict", "static", "extern"):
                    # Skip qualifiers
                    continue
            
            # If we didn't find a type_identifier directly, check if there's a struct/union/enum specifier
            for i in range(decl_node.child_count):
                child = decl_node.child(i)
                if child.type in ("struct_specifier", "union_specifier", "enum_specifier"):
                    # Extract the name from the specifier
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        return name_node.text.decode("utf-8")
            
            return None
        
        def collect_variable_types(n):
            """Collect variable names and their types from declarations."""
            # Function parameters
            if n.type == "parameter_declaration":
                type_name = extract_type_from_declaration(n)
                declarator = n.child_by_field_name("declarator")
                if declarator and type_name:
                    # Find the identifier (variable name)
                    for i in range(declarator.child_count):
                        child = declarator.child(i)
                        if child.type == "identifier":
                            var_name = child.text.decode("utf-8")
                            variable_types[var_name] = type_name
                            break
            
            # Variable declarations
            elif n.type == "declaration":
                type_name = extract_type_from_declaration(n)
                if type_name:
                    # Find all declarators in this declaration
                    for i in range(n.child_count):
                        child = n.child(i)
                        if child.type == "init_declarator":
                            declarator = child.child_by_field_name("declarator")
                            if declarator:
                                for j in range(declarator.child_count):
                                    subchild = declarator.child(j)
                                    if subchild.type == "identifier":
                                        var_name = subchild.text.decode("utf-8")
                                        variable_types[var_name] = type_name
                                        break
        
        # First pass: collect variable types
        def walk_collect(n):
            collect_variable_types(n)
            for i in range(n.child_count):
                walk_collect(n.child(i))
        
        walk_collect(node)
        
        def extract_struct_name_from_expression(expr_node):
            """Extract struct name from an expression node."""
            # Handle different expression types
            if expr_node.type == "identifier":
                var_name = expr_node.text.decode("utf-8")
                # Try to resolve variable name to its type
                if var_name in variable_types:
                    return variable_types[var_name]
                # Fallback: return the identifier (might be a struct name directly)
                return var_name
            elif expr_node.type == "pointer_expression":
                # For -> access, the left side might be a cast or identifier
                operand = expr_node.child_by_field_name("operand")
                if operand:
                    return extract_struct_name_from_expression(operand)
            elif expr_node.type == "cast_expression":
                # Extract type from cast: (MyStruct*)ptr
                type_node = expr_node.child_by_field_name("type")
                if type_node:
                    # Look for type_identifier in the type
                    for i in range(type_node.child_count):
                        child = type_node.child(i)
                        if child.type == "type_identifier":
                            return child.text.decode("utf-8")
                        elif child.type == "pointer_declarator":
                            # Check for type_identifier before pointer
                            for j in range(i):
                                prev_child = type_node.child(j)
                                if prev_child.type == "type_identifier":
                                    return prev_child.text.decode("utf-8")
            elif expr_node.type == "parenthesized_expression":
                # Unwrap parentheses
                for i in range(expr_node.child_count):
                    child = expr_node.child(i)
                    if child.type not in ("(", ")"):
                        result = extract_struct_name_from_expression(child)
                        if result:
                            return result
            return None
        
        def walk_tree(n):
            # Handle field_expression: struct.field or struct->field
            # In tree-sitter C, both . and -> are represented as field_expression
            # Structure: field_expression has children: [operand, operator, field]
            # The operator (-> or .) is a child node
            if n.type == "field_expression":
                # field_expression doesn't use named fields, children are in order:
                # [operand (identifier), operator (-> or .), field (field_identifier)]
                field_node = n.child_by_field_name("field")
                # If field_name doesn't work, try getting field_identifier from children
                if not field_node:
                    for child in n.children:
                        if child.type == "field_identifier":
                            field_node = child
                            break
                
                # Operand is typically the first child (identifier)
                operand_node = None
                for child in n.children:
                    if child.type == "identifier":
                        operand_node = child
                        break
                    elif child.type in ("pointer_expression", "cast_expression", "parenthesized_expression"):
                        operand_node = child
                        break
                
                if field_node and operand_node:
                    field_name = field_node.text.decode("utf-8")
                    struct_name = extract_struct_name_from_expression(operand_node)
                    
                    # Determine access type by checking for -> operator
                    access_type = "direct"  # Default to direct access (.)
                    for i in range(n.child_count):
                        child = n.child(i)
                        # Check if this is the -> operator
                        if child.type == "->":
                            access_type = "pointer"
                            break
                    
                    if struct_name and field_name:
                        field_accesses.append(StructFieldAccess(
                            struct_name=struct_name,
                            field_name=field_name,
                            access_type=access_type,
                            start=Position(
                                row=n.start_point[0],
                                column=n.start_point[1]
                            ),
                            end=Position(
                                row=n.end_point[0],
                                column=n.end_point[1]
                            ),
                            file_path=""  # Will be set in parse_file
                        ))
            
            # Recursively walk children
            for i in range(n.child_count):
                walk_tree(n.child(i))
        
        walk_tree(node)
        return field_accesses
    
    def extract_macro_usages(self, node, macros: list[Macro]) -> list[MacroUsage]:
        """Extract macro usage sites from AST node.
        
        Finds identifier nodes that match macro names (excluding macro definitions).
        """
        macro_usages = []
        macro_names = {macro.name for macro in macros}
        function_stack = ["module"]  # Track current function context
        
        # Build a set of macro definition positions to exclude
        macro_def_positions = set()
        for macro in macros:
            macro_def_positions.add((macro.start.row, macro.start.column))
        
        def walk_tree(n, parent_stack=None):
            if parent_stack is None:
                parent_stack = []
            
            # Track function definitions
            if n.type == "function_definition":
                declarator = n.child_by_field_name("declarator")
                if declarator:
                    for i in range(declarator.child_count):
                        child = declarator.child(i)
                        if child.type == "identifier":
                            func_name = child.text.decode("utf-8")
                            function_stack.append(func_name)
                            break
            
            # Find identifier nodes that match macro names
            if n.type == "identifier":
                identifier_name = n.text.decode("utf-8")
                if identifier_name in macro_names:
                    # Check if this is not part of a macro definition
                    pos = (n.start_point[0], n.start_point[1])
                    if pos not in macro_def_positions:
                        # Check if any parent in stack is preproc_def (skip if so)
                        is_in_macro_def = any(p.type == "preproc_def" for p in parent_stack)
                        
                        if not is_in_macro_def:
                            current_function = function_stack[-1] if function_stack else "module"
                            macro_usages.append(MacroUsage(
                                macro_name=identifier_name,
                                function_context=current_function if current_function != "module" else None,
                                start=Position(
                                    row=n.start_point[0],
                                    column=n.start_point[1]
                                ),
                                end=Position(
                                    row=n.end_point[0],
                                    column=n.end_point[1]
                                ),
                                file_path=""  # Will be set in parse_file
                            ))
            
            # Recursively walk children
            new_parent_stack = parent_stack + [n]
            for i in range(n.child_count):
                walk_tree(n.child(i), new_parent_stack)
            
            # Pop function stack when leaving function definition
            if n.type == "function_definition":
                if len(function_stack) > 1:
                    function_stack.pop()
        
        walk_tree(node)
        return macro_usages
    
    def extract_variable_usages(self, node, variables: list[Variable]) -> list[VariableUsage]:
        """Extract variable usage sites from AST node.
        
        Finds identifier nodes that match variable names (excluding variable declarations).
        Handles variable shadowing (prefers local over global).
        """
        variable_usages = []
        function_stack = ["module"]  # Track current function context
        
        # Build variable registry: name -> list of variables with that name
        variable_registry = {}
        for var in variables:
            if var.name not in variable_registry:
                variable_registry[var.name] = []
            variable_registry[var.name].append(var)
        
        # Build a set of variable declaration positions to exclude
        var_def_positions = set()
        for var in variables:
            var_def_positions.add((var.start.row, var.start.column))
        
        def find_matching_variable(var_name, current_function):
            """Find the best matching variable for a usage (handle shadowing)."""
            if var_name not in variable_registry:
                return None
            
            candidates = variable_registry[var_name]
            
            # If we're in a function, prefer local variables
            if current_function != "module":
                # First try to find a local variable in the current function
                for var in candidates:
                    if not var.is_global and var.containing_function == current_function:
                        return var
                # Then try global variables
                for var in candidates:
                    if var.is_global:
                        return var
            else:
                # In module scope, prefer global variables
                for var in candidates:
                    if var.is_global:
                        return var
            
            # Return first match if no better match found
            return candidates[0] if candidates else None
        
        def walk_tree(n, parent_stack=None):
            if parent_stack is None:
                parent_stack = []
            
            # Track function definitions
            if n.type == "function_definition":
                declarator = n.child_by_field_name("declarator")
                if declarator:
                    for i in range(declarator.child_count):
                        child = declarator.child(i)
                        if child.type == "identifier":
                            func_name = child.text.decode("utf-8")
                            function_stack.append(func_name)
                            break
            
            # Find identifier nodes that match variable names
            if n.type == "identifier":
                identifier_name = n.text.decode("utf-8")
                if identifier_name in variable_registry:
                    # Check if this is not part of a variable declaration
                    pos = (n.start_point[0], n.start_point[1])
                    if pos not in var_def_positions:
                        # Check if any parent in stack is declaration (skip if so)
                        is_in_decl = any(p.type == "declaration" for p in parent_stack)
                        
                        if not is_in_decl:
                            current_function = function_stack[-1] if function_stack else "module"
                            matching_var = find_matching_variable(identifier_name, current_function)
                            
                            if matching_var:
                                variable_usages.append(VariableUsage(
                                    variable_name=identifier_name,
                                    function_context=current_function,
                                    start=Position(
                                        row=n.start_point[0],
                                        column=n.start_point[1]
                                    ),
                                    end=Position(
                                        row=n.end_point[0],
                                        column=n.end_point[1]
                                    ),
                                    file_path=""  # Will be set in parse_file
                                ))
            
            # Recursively walk children
            new_parent_stack = parent_stack + [n]
            for i in range(n.child_count):
                walk_tree(n.child(i), new_parent_stack)
            
            # Pop function stack when leaving function definition
            if n.type == "function_definition":
                if len(function_stack) > 1:
                    function_stack.pop()
        
        walk_tree(node)
        return variable_usages
    
    def extract_typedef_usages(self, node, typedefs: list[Typedef]) -> list[TypedefUsage]:
        """Extract typedef usage sites from AST node.
        
        Finds type_identifier nodes that match typedef names (excluding typedef definitions).
        """
        typedef_usages = []
        typedef_names = {tdef.name for tdef in typedefs}
        
        # Build a set of typedef definition positions to exclude
        typedef_def_positions = set()
        for tdef in typedefs:
            typedef_def_positions.add((tdef.start.row, tdef.start.column))
        
        def walk_tree(n, parent_stack=None):
            if parent_stack is None:
                parent_stack = []
            
            # Find type_identifier nodes that match typedef names
            if n.type == "type_identifier":
                type_name = n.text.decode("utf-8")
                if type_name in typedef_names:
                    # Check if this is not part of a typedef definition
                    pos = (n.start_point[0], n.start_point[1])
                    if pos not in typedef_def_positions:
                        # Check if any parent in stack is type_definition (skip if so)
                        is_in_typedef_def = any(p.type == "type_definition" for p in parent_stack)
                        
                        if not is_in_typedef_def:
                            typedef_usages.append(TypedefUsage(
                                typedef_name=type_name,
                                start=Position(
                                    row=n.start_point[0],
                                    column=n.start_point[1]
                                ),
                                end=Position(
                                    row=n.end_point[0],
                                    column=n.end_point[1]
                                ),
                                file_path=""  # Will be set in parse_file
                            ))
            
            # Recursively walk children
            new_parent_stack = parent_stack + [n]
            for i in range(n.child_count):
                walk_tree(n.child(i), new_parent_stack)
        
        walk_tree(node)
        return typedef_usages

