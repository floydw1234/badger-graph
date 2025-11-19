"""Base parser interface for language parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Position:
    """Position in source code."""
    row: int
    column: int


@dataclass
class Function:
    """Function definition."""
    name: str
    start: Position
    end: Position
    file_path: str
    signature: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None


@dataclass
class Class:
    """Class definition."""
    name: str
    start: Position
    end: Position
    file_path: str
    methods: List[str] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)


@dataclass
class Import:
    """Import statement."""
    text: str
    start: Position
    end: Position
    file_path: str
    module: Optional[str] = None
    imported_items: List[str] = field(default_factory=list)
    alias: Optional[str] = None


@dataclass
class FunctionCall:
    """Function call site."""
    caller_name: str
    callee_name: str
    is_method_call: bool
    start: Position
    end: Position
    file_path: str


@dataclass
class Typedef:
    """Typedef definition."""
    name: str
    underlying_type: str
    start: Position
    end: Position
    file_path: str


@dataclass
class Macro:
    """Macro definition."""
    name: str
    start: Position
    end: Position
    file_path: str
    value: Optional[str] = None
    parameters: List[str] = field(default_factory=list)


@dataclass
class Variable:
    """Variable declaration."""
    name: str
    start: Position
    end: Position
    file_path: str
    type: Optional[str] = None
    storage_class: Optional[str] = None
    is_global: bool = False
    containing_function: Optional[str] = None


@dataclass
class StructFieldAccess:
    """Struct field access."""
    struct_name: str
    field_name: str
    access_type: str  # "direct" or "pointer"
    start: Position
    end: Position
    file_path: str


@dataclass
class MacroUsage:
    """Macro usage site."""
    macro_name: str
    start: Position
    end: Position
    file_path: str
    function_context: Optional[str] = None


@dataclass
class VariableUsage:
    """Variable usage site."""
    variable_name: str
    start: Position
    end: Position
    file_path: str
    function_context: str


@dataclass
class TypedefUsage:
    """Typedef usage site."""
    typedef_name: str
    start: Position
    end: Position
    file_path: str


@dataclass
class ParseResult:
    """Result of parsing a source file."""
    file_path: str
    functions: List[Function]
    classes: List[Class]
    imports: List[Import]
    total_nodes: int
    tree_string: Optional[str] = None
    function_calls: List[FunctionCall] = field(default_factory=list)
    typedefs: List[Typedef] = field(default_factory=list)
    macros: List[Macro] = field(default_factory=list)
    variables: List[Variable] = field(default_factory=list)
    struct_field_accesses: List[StructFieldAccess] = field(default_factory=list)
    macro_usages: List[MacroUsage] = field(default_factory=list)
    variable_usages: List[VariableUsage] = field(default_factory=list)
    typedef_usages: List[TypedefUsage] = field(default_factory=list)


class BaseParser(ABC):
    """Abstract base class for language parsers."""
    
    def __init__(self, language_name: str):
        self.language_name = language_name
        self.parser = None
        self.language = None
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the parser and language."""
        pass
    
    @abstractmethod
    def parse_file(self, file_path: Path) -> ParseResult:
        """Parse a source file and return parse results."""
        pass
    
    @abstractmethod
    def extract_functions(self, node) -> List[Function]:
        """Extract function definitions from AST node."""
        pass
    
    @abstractmethod
    def extract_classes(self, node) -> List[Class]:
        """Extract class definitions from AST node."""
        pass
    
    @abstractmethod
    def extract_imports(self, node) -> List[Import]:
        """Extract import statements from AST node."""
        pass
    
    def count_nodes(self, node) -> int:
        """Count total nodes in AST tree."""
        count = 1  # count this node
        for i in range(node.child_count):
            count += self.count_nodes(node.child(i))
        return count

