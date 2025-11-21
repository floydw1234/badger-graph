"""Python parser using tree-sitter."""

from pathlib import Path
from tree_sitter import Language, Parser
from .base import BaseParser, ParseResult, Function, Class, Import, Position, FunctionCall

# Python standard library modules (top-level)
# This list covers common stdlib modules to filter out
_PYTHON_STDLIB_MODULES = {
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asyncio', 'atexit', 'audioop',
    'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins', 'bz2',
    'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs',
    'codeop', 'collections', 'colorsys', 'compileall', 'concurrent', 'configparser',
    'contextlib', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv', 'ctypes',
    'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib', 'dis',
    'distutils', 'doctest', 'dummy_threading', 'email', 'encodings', 'ensurepip',
    'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch',
    'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext',
    'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html',
    'http', 'idlelib', 'imaplib', 'imghdr', 'imp', 'importlib', 'inspect',
    'io', 'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3', 'linecache',
    'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 'marshal', 'math',
    'mimetypes', 'mmap', 'modulefinder', 'msilib', 'msvcrt', 'multiprocessing',
    'netrc', 'nis', 'nntplib', 'ntpath', 'nturl2path', 'numbers', 'operator',
    'optparse', 'os', 'ossaudiodev', 'pathlib', 'pdb', 'pickle', 'pickletools',
    'pipes', 'pkgutil', 'platform', 'plistlib', 'poplib', 'posix', 'posixpath',
    'pprint', 'profile', 'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr',
    'pydoc', 'queue', 'quopri', 'random', 're', 'readline', 'reprlib',
    'resource', 'rlcompleter', 'runpy', 'sched', 'secrets', 'select',
    'selectors', 'shelve', 'shlex', 'shutil', 'signal', 'site', 'smtplib',
    'sndhdr', 'socket', 'socketserver', 'spwd', 'sqlite3', 'sre_compile',
    'sre_constants', 'sre_parse', 'ssl', 'stat', 'statistics', 'string',
    'stringprep', 'struct', 'subprocess', 'sunau', 'symbol', 'symtable',
    'sys', 'sysconfig', 'syslog', 'tarfile', 'telnetlib', 'tempfile', 'termios',
    'test', 'textwrap', 'threading', 'time', 'timeit', 'tkinter', 'token',
    'tokenize', 'trace', 'traceback', 'tracemalloc', 'tty', 'turtle', 'types',
    'typing', 'unicodedata', 'unittest', 'urllib', 'uu', 'uuid', 'venv',
    'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'winsound',
    'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport',
    'zlib'
}


class PythonParser(BaseParser):
    """Parser for Python source files."""
    
    def __init__(self):
        super().__init__("python")
        self.initialize()
    
    def initialize(self) -> None:
        """Initialize tree-sitter Python parser."""
        try:
            from tree_sitter_python import language
            lang = Language(language())
            self.parser = Parser(lang)
        except ImportError:
            # Fallback: try compiled library approach
            try:
                Python = Language("build/my-languages.so", "python")
                self.parser = Parser(Python)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to initialize Python parser. "
                    f"Make sure tree-sitter-python is installed: pip install tree-sitter-python. "
                    f"Error: {e}"
                )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Python parser: {e}")
    
    def parse_file(self, file_path: Path) -> ParseResult:
        """Parse a Python file and return parse results."""
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
            classes = self.extract_classes(root_node)
            imports = self.extract_imports(root_node)
            
            # Set file_path for all extracted items
            file_path_str = str(file_path)
            for func in functions:
                func.file_path = file_path_str
            for cls in classes:
                cls.file_path = file_path_str
            for imp in imports:
                imp.file_path = file_path_str
            
            # Extract function calls
            function_calls = self.extract_function_calls(root_node, source_code)
            for call in function_calls:
                call.file_path = file_path_str
            
            return ParseResult(
                file_path=file_path_str,
                functions=functions,
                classes=classes,
                imports=imports,
                total_nodes=self.count_nodes(root_node),
                tree_string=root_node.text.decode("utf-8") if hasattr(root_node, "text") else None,
                function_calls=function_calls
            )
        except Exception as e:
            raise RuntimeError(f"Error parsing Python file {file_path}: {e}")
    
    def extract_functions(self, node, source_code: bytes = None) -> list[Function]:
        """Extract function definitions from AST node."""
        functions = []
        
        def extract_parameters(params_node):
            """Extract parameter names from parameters node."""
            param_names = []
            if not params_node:
                return param_names
            
            for i in range(params_node.child_count):
                child = params_node.child(i)
                # Skip parentheses and commas
                if child.type in ("(", ")", ","):
                    continue
                elif child.type == "identifier":
                    param_names.append(child.text.decode("utf-8"))
                elif child.type == "typed_parameter":
                    # Handle typed parameters like "x: int"
                    # The first child is the identifier (parameter name)
                    if child.child_count > 0:
                        name_node = child.child(0)
                        if name_node.type == "identifier":
                            param_names.append(name_node.text.decode("utf-8"))
                elif child.type == "default_parameter":
                    # Handle default parameters like "x: int = 0"
                    # The first child is the identifier (parameter name)
                    if child.child_count > 0:
                        name_node = child.child(0)
                        if name_node.type == "identifier":
                            param_names.append(name_node.text.decode("utf-8"))
                elif child.type == "keyword_argument":
                    # Handle keyword arguments (skip for now)
                    pass
            return param_names
        
        def extract_return_type(func_node):
            """Extract return type annotation from function node."""
            return_type_node = func_node.child_by_field_name("return_type")
            if return_type_node:
                return return_type_node.text.decode("utf-8")
            return None
        
        def extract_docstring(func_node, source_code: bytes):
            """Extract docstring from function body."""
            if not source_code:
                return None
            
            body_node = func_node.child_by_field_name("body")
            if not body_node:
                return None
            
            # Look for first string literal in body (docstring)
            for i in range(body_node.child_count):
                child = body_node.child(i)
                if child.type == "expression_statement":
                    expr = child.child(0) if child.child_count > 0 else None
                    if expr and expr.type == "string":
                        # Extract docstring
                        docstring_text = source_code[expr.start_byte:expr.end_byte].decode("utf-8")
                        # Remove quotes (simple approach - handles triple quotes)
                        docstring_text = docstring_text.strip('"\'')
                        if docstring_text.startswith('"""') or docstring_text.startswith("'''"):
                            docstring_text = docstring_text[3:-3]
                        return docstring_text.strip()
            return None
        
        def build_signature(name, params, return_type):
            """Build function signature string."""
            sig = name + "("
            if params:
                sig += ", ".join(params)
            sig += ")"
            if return_type:
                sig += " -> " + return_type
            return sig
        
        def walk_tree(n):
            if n.type == "function_definition":
                name_node = n.child_by_field_name("name")
                if name_node:
                    function_name = name_node.text.decode("utf-8")
                    
                    # Extract parameters
                    params_node = n.child_by_field_name("parameters")
                    parameters = extract_parameters(params_node)
                    
                    # Extract return type
                    return_type = extract_return_type(n)
                    
                    # Extract docstring
                    docstring = extract_docstring(n, source_code) if source_code else None
                    
                    # Build signature
                    signature = build_signature(function_name, parameters, return_type)
                    
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
                        docstring=docstring
                    ))
            
            for i in range(n.child_count):
                walk_tree(n.child(i))
        
        walk_tree(node)
        return functions
    
    def extract_classes(self, node) -> list[Class]:
        """Extract class definitions from AST node."""
        classes = []
        
        def extract_base_classes(class_node):
            """Extract base classes from class definition."""
            base_classes = []
            superclasses_node = class_node.child_by_field_name("superclasses")
            if superclasses_node:
                # superclasses node contains argument_list with base class names
                for i in range(superclasses_node.child_count):
                    child = superclasses_node.child(i)
                    if child.type == "identifier":
                        base_classes.append(child.text.decode("utf-8"))
                    elif child.type == "attribute":
                        # Handle dotted names like "module.Class"
                        # Extract the full attribute name
                        base_classes.append(child.text.decode("utf-8"))
            return base_classes
        
        def extract_methods(class_node):
            """Extract method names from class body."""
            methods = []
            body_node = class_node.child_by_field_name("body")
            if not body_node:
                return methods
            
            def walk_body(n):
                if n.type == "function_definition":
                    name_node = n.child_by_field_name("name")
                    if name_node:
                        methods.append(name_node.text.decode("utf-8"))
                for i in range(n.child_count):
                    walk_body(n.child(i))
            
            walk_body(body_node)
            return methods
        
        def walk_tree(n):
            if n.type == "class_definition":
                name_node = n.child_by_field_name("name")
                if name_node:
                    class_name = name_node.text.decode("utf-8")
                    
                    # Extract base classes
                    base_classes = extract_base_classes(n)
                    
                    # Extract methods
                    methods = extract_methods(n)
                    
                    classes.append(Class(
                        name=class_name,
                        start=Position(
                            row=n.start_point[0],
                            column=n.start_point[1]
                        ),
                        end=Position(
                            row=n.end_point[0],
                            column=n.end_point[1]
                        ),
                        file_path="",  # Will be set in parse_file
                        methods=methods,
                        base_classes=base_classes
                    ))
            
            for i in range(n.child_count):
                walk_tree(n.child(i))
        
        walk_tree(node)
        return classes
    
    def extract_imports(self, node) -> list[Import]:
        """Extract import statements from AST node."""
        imports = []
        
        def extract_import_statement(import_node):
            """Extract information from import_statement node."""
            # import X
            # import X as Y
            # import X, Y
            import_text = import_node.text.decode("utf-8")
            module = None
            imported_items = []
            alias = None
            
            # Skip "import" keyword, then process children
            for i in range(import_node.child_count):
                child = import_node.child(i)
                if child.type == "import":
                    continue
                elif child.type == "dotted_name" or child.type == "identifier":
                    if module is None:
                        module = child.text.decode("utf-8")
                elif child.type == "dotted_as_name":
                    # Handle "import X as Y"
                    dotted = child.child_by_field_name("name")
                    if dotted:
                        module = dotted.text.decode("utf-8")
                    alias_node = child.child_by_field_name("alias")
                    if alias_node:
                        alias = alias_node.text.decode("utf-8")
                elif child.type == "aliased_import":
                    # Handle "import X as Y" - aliased_import contains name and alias
                    name_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")
                    if name_node:
                        if module is None:
                            module = name_node.text.decode("utf-8")
                        else:
                            imported_items.append(name_node.text.decode("utf-8"))
                    if alias_node:
                        alias = alias_node.text.decode("utf-8")
                # Skip commas
            
            return Import(
                text=import_text,
                start=Position(
                    row=import_node.start_point[0],
                    column=import_node.start_point[1]
                ),
                end=Position(
                    row=import_node.end_point[0],
                    column=import_node.end_point[1]
                ),
                file_path="",
                module=module,
                imported_items=imported_items,
                alias=alias
            )
        
        def extract_import_from_statement(import_node):
            """Extract information from import_from_statement node."""
            # from X import Y
            # from X import Y, Z
            # from X import Y as Z
            import_text = import_node.text.decode("utf-8")
            module = None
            imported_items = []
            alias = None
            
            # Extract module name (from X ...)
            module_name_node = import_node.child_by_field_name("module_name")
            if module_name_node:
                module = module_name_node.text.decode("utf-8")
            
            # Extract imported items - they are direct children after "import" keyword
            # Skip "from", module_name, "import" keywords
            found_import_keyword = False
            for i in range(import_node.child_count):
                child = import_node.child(i)
                if child.type == "import":
                    found_import_keyword = True
                    continue
                if found_import_keyword:
                    # After "import" keyword, collect imported items
                    if child.type == "identifier":
                        imported_items.append(child.text.decode("utf-8"))
                    elif child.type == "dotted_name":
                        imported_items.append(child.text.decode("utf-8"))
                    elif child.type == "aliased_import":
                        # Handle "Y as Z"
                        name_node = child.child_by_field_name("name")
                        alias_node = child.child_by_field_name("alias")
                        if name_node:
                            imported_items.append(name_node.text.decode("utf-8"))
                        if alias_node:
                            # For now, store the last alias (could be improved to map items to aliases)
                            alias = alias_node.text.decode("utf-8")
                    # Skip commas
            
            return Import(
                text=import_text,
                start=Position(
                    row=import_node.start_point[0],
                    column=import_node.start_point[1]
                ),
                end=Position(
                    row=import_node.end_point[0],
                    column=import_node.end_point[1]
                ),
                file_path="",
                module=module,
                imported_items=imported_items,
                alias=alias
            )
        
        def is_stdlib_module(module: str) -> bool:
            """Check if a module is part of Python standard library."""
            if not module:
                return False
            # Get the top-level module name (first part of dotted name)
            top_level = module.split('.')[0]
            return top_level in _PYTHON_STDLIB_MODULES
        
        def walk_tree(n):
            if n.type == "import_statement":
                imp = extract_import_statement(n)
                # Filter out standard library imports
                if imp and imp.module and not is_stdlib_module(imp.module):
                    imports.append(imp)
            elif n.type == "import_from_statement":
                imp = extract_import_from_statement(n)
                # Filter out standard library imports
                if imp and imp.module and not is_stdlib_module(imp.module):
                    imports.append(imp)
            
            for i in range(n.child_count):
                walk_tree(n.child(i))
        
        walk_tree(node)
        return imports
    
    def extract_function_calls(self, node, source_code: bytes = None) -> list[FunctionCall]:
        """Extract function calls from AST node."""
        function_calls = []
        caller_stack = ["module"]  # Track current function/method context
        
        def get_callee_name(call_node):
            """Extract the name of the function being called.
            
            For method calls like obj.method() or self.method(), returns only
            the method name (e.g., 'method') to match function definitions.
            """
            function_node = call_node.child_by_field_name("function")
            if not function_node:
                return None
            
            if function_node.type == "identifier":
                return function_node.text.decode("utf-8")
            elif function_node.type == "attribute":
                # Method call: obj.method() or self.method()
                # Extract ONLY the method name (last part), not the full path
                # This allows matching against function definitions which are stored
                # with just the function name, not the full attribute path
                attr_node = function_node.child_by_field_name("attribute")
                if attr_node and attr_node.type == "identifier":
                    return attr_node.text.decode("utf-8")
                # Handle nested attributes like obj.sub.method() - get the last attribute
                current = function_node
                while current:
                    if current.type == "attribute":
                        attr_node = current.child_by_field_name("attribute")
                        if attr_node and attr_node.type == "identifier":
                            # This is the method name we want
                            return attr_node.text.decode("utf-8")
                        current = current.child_by_field_name("object")
                    else:
                        break
                return None
            return None
        
        def is_method_call(call_node):
            """Determine if this is a method call (obj.method()) vs function call."""
            function_node = call_node.child_by_field_name("function")
            if not function_node:
                return False
            return function_node.type == "attribute"
        
        def walk_tree(n):
            # Track function definitions to know caller context
            if n.type == "function_definition":
                name_node = n.child_by_field_name("name")
                if name_node:
                    caller_name = name_node.text.decode("utf-8")
                    caller_stack.append(caller_name)
            
            # Find call nodes
            if n.type == "call":
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

