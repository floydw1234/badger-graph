"""Cross-file relationship resolution for C and Python parsers."""

from pathlib import Path
from typing import List, Dict, Set, Optional
from .base import ParseResult, Function, FunctionCall, Import


class CrossFileResolver:
    """Resolves relationships across multiple parsed files."""
    
    def __init__(self, parse_results: List[ParseResult]):
        """Initialize resolver with parse results from multiple files.
        
        Args:
            parse_results: List of ParseResult objects from parsed files
        """
        self.parse_results = parse_results
        self.file_index: Dict[str, ParseResult] = {
            result.file_path: result for result in parse_results
        }
        self.function_index: Dict[str, List[Function]] = {}
        self.include_map: Dict[str, Set[str]] = {}  # file -> set of included files
        
        self._build_indices()
    
    def _build_indices(self):
        """Build indices for fast lookup."""
        # Index functions by name
        for result in self.parse_results:
            for func in result.functions:
                if func.name not in self.function_index:
                    self.function_index[func.name] = []
                self.function_index[func.name].append(func)
        
        # Build include map (for C: track which files include which)
        for result in self.parse_results:
            file_path = result.file_path
            included_files = set()
            
            for imp in result.imports:
                if imp.module:
                    # For C includes, try to resolve the included file
                    # This is a simplified resolution - in practice, you'd need
                    # to handle include paths, relative paths, etc.
                    included_files.add(imp.module)
            
            self.include_map[file_path] = included_files
    
    def resolve_function_call(self, call: FunctionCall) -> Optional[Function]:
        """Resolve a function call to its definition/declaration.
        
        Args:
            call: FunctionCall object to resolve
            
        Returns:
            Function object if found, None otherwise
        """
        callee_name = call.callee_name
        
        # First, check if function is defined in the same file
        caller_file = self.file_index.get(call.file_path)
        if caller_file:
            for func in caller_file.functions:
                if func.name == callee_name:
                    return func
        
        # Check functions in included files (for C)
        if caller_file:
            for imp in caller_file.imports:
                if imp.module:
                    # Try to find the included file
                    included_file = self._find_included_file(call.file_path, imp.module)
                    if included_file:
                        included_result = self.file_index.get(included_file)
                        if included_result:
                            for func in included_result.functions:
                                if func.name == callee_name:
                                    return func
        
        # Fallback: search all files
        if callee_name in self.function_index:
            # Return the first definition (prefer definitions over declarations)
            functions = self.function_index[callee_name]
            for func in functions:
                # Prefer definitions (those with bodies) over declarations
                # For C, declarations end with ';' in signature
                if func.signature and not func.signature.endswith(';'):
                    return func
            # If no definition found, return first declaration
            if functions:
                return functions[0]
        
        return None
    
    def _find_included_file(self, from_file: str, include_name: str) -> Optional[str]:
        """Find the actual file path for an include.
        
        This is a simplified implementation. In practice, you'd need to:
        - Handle system includes vs local includes
        - Resolve relative paths
        - Check include paths
        
        Args:
            from_file: File that includes the module
            include_name: Name of the included file (e.g., "service.h")
            
        Returns:
            Full path to included file if found, None otherwise
        """
        from_path = Path(from_file)
        parent_dir = from_path.parent
        
        # Try relative path from including file
        candidate = parent_dir / include_name
        if candidate.exists():
            return str(candidate)
        
        # Try to find in parse results
        for result in self.parse_results:
            result_path = Path(result.file_path)
            if result_path.name == include_name:
                return result.file_path
        
        return None
    
    def get_call_graph(self) -> Dict[str, List[str]]:
        """Build a call graph mapping functions to their callers.
        
        Returns:
            Dictionary mapping function name to list of functions that call it
        """
        call_graph: Dict[str, Set[str]] = {}
        
        for result in self.parse_results:
            for call in result.function_calls:
                callee = call.callee_name
                caller = call.caller_name
                
                if callee not in call_graph:
                    call_graph[callee] = set()
                call_graph[callee].add(caller)
        
        # Convert sets to lists
        return {func: list(callers) for func, callers in call_graph.items()}
    
    def get_file_dependencies(self) -> Dict[str, Set[str]]:
        """Get file dependency graph based on includes/imports.
        
        Returns:
            Dictionary mapping file path to set of files it depends on
        """
        dependencies: Dict[str, Set[str]] = {}
        
        for result in self.parse_results:
            file_path = result.file_path
            deps = set()
            
            for imp in result.imports:
                if imp.module:
                    included_file = self._find_included_file(file_path, imp.module)
                    if included_file:
                        deps.add(included_file)
            
            dependencies[file_path] = deps
        
        return dependencies

