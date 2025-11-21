"""Data validation for graph nodes based on GraphQL schema.

This module provides dataclasses that enforce required fields from the schema
before insertion into Dgraph, preventing errors from missing or invalid data.
"""

import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class FileNode:
    """File node with required fields enforced."""
    path: str  # Required: String!
    
    # Optional fields
    functions_count: int = 0
    classes_count: int = 0
    structs_count: int = 0
    imports_count: int = 0
    macros_count: int = 0
    variables_count: int = 0
    typedefs_count: int = 0
    struct_field_accesses_count: int = 0
    ast_nodes: int = 0
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate required fields."""
        if not isinstance(self.path, str):
            return False, f"File.path must be a string, got {type(self.path).__name__}"
        if not self.path or not self.path.strip():
            return False, "File.path is required (String!) and cannot be empty"
        return True, None
    
    def to_dgraph_dict(self, uid: str) -> Dict[str, Any]:
        """Convert to Dgraph node dictionary."""
        return {
            "uid": f"_:{uid}",
            "dgraph.type": "File",
            "File.path": self.path,
            "File.functionsCount": self.functions_count,
            "File.classesCount": self.classes_count,
            "File.structsCount": self.structs_count,
            "File.importsCount": self.imports_count,
            "File.macrosCount": self.macros_count,
            "File.variablesCount": self.variables_count,
            "File.typedefsCount": self.typedefs_count,
            "File.structFieldAccessesCount": self.struct_field_accesses_count,
            "File.astNodes": self.ast_nodes,
        }


@dataclass
class FunctionNode:
    """Function node with required fields enforced."""
    name: str  # Required: String!
    file: str  # Required: String!
    
    # Optional fields
    line: int = 0
    column: int = 0
    signature: Optional[str] = None
    parameters: Optional[str] = None
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    embedding: Optional[List[float]] = None
    belongs_to_class: Optional[str] = None
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate required fields."""
        if not isinstance(self.name, str):
            return False, f"Function.name must be a string, got {type(self.name).__name__}"
        if not self.name or not self.name.strip():
            return False, "Function.name is required (String!) and cannot be empty"
        if not isinstance(self.file, str):
            return False, f"Function.file must be a string, got {type(self.file).__name__}"
        if not self.file or not self.file.strip():
            return False, "Function.file is required (String!) and cannot be empty"
        if self.line == 0:
            logger.warning(f"Function {self.name} in {self.file} has invalid line number (0), using 1")
            self.line = 1
        return True, None
    
    def to_dgraph_dict(self, uid: str) -> Dict[str, Any]:
        """Convert to Dgraph node dictionary."""
        node = {
            "uid": f"_:{uid}",
            "dgraph.type": "Function",
            "Function.name": self.name,
            "Function.file": self.file,
            "Function.line": self.line,
            "Function.column": self.column,
        }
        
        # Add optional fields
        if self.signature is not None:
            node["Function.signature"] = self.signature
        if self.parameters is not None:
            node["Function.parameters"] = self.parameters
        if self.return_type is not None:
            node["Function.returnType"] = self.return_type
        if self.docstring is not None:
            node["Function.docstring"] = self.docstring
        if self.embedding is not None:
            node["Function.embedding"] = self.embedding
        
        return node


@dataclass
class ClassNode:
    """Class node with required fields enforced.
    
    Note: This represents both Python classes and C structs/unions/enums.
    - For Python: methods = method names, base_classes = parent classes
    - For C: methods = struct/union/enum field names, base_classes = empty/None
    """
    name: str  # Required: String!
    file: str  # Required: String!
    
    # Optional fields
    line: int = 0
    column: int = 0
    methods: Optional[List[str]] = None  # Method names (Python) or field names (C structs)
    base_classes: Optional[List[str]] = None  # Parent classes (Python) or empty (C)
    embedding: Optional[List[float]] = None
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate required fields."""
        if not isinstance(self.name, str):
            return False, f"Class.name must be a string, got {type(self.name).__name__}"
        if not self.name or not self.name.strip():
            return False, "Class.name is required (String!) and cannot be empty"
        if not isinstance(self.file, str):
            return False, f"Class.file must be a string, got {type(self.file).__name__}"
        if not self.file or not self.file.strip():
            return False, "Class.file is required (String!) and cannot be empty"
        return True, None
    
    def to_dgraph_dict(self, uid: str) -> Dict[str, Any]:
        """Convert to Dgraph node dictionary."""
        node = {
            "uid": f"_:{uid}",
            "dgraph.type": "Class",
            "Class.name": self.name,
            "Class.file": self.file,
            "Class.line": self.line,
            "Class.column": self.column,
        }
        
        # Add optional fields
        if self.methods is not None:
            node["Class.methods"] = self.methods
        if self.base_classes is not None:
            node["Class.baseClasses"] = self.base_classes
        if self.embedding is not None:
            node["Class.embedding"] = self.embedding
        
        return node


@dataclass
class StructNode:
    """Struct node with required fields enforced.
    
    Represents C structs/unions/enums.
    """
    name: str  # Required: String!
    file: str  # Required: String!
    
    # Optional fields
    line: int = 0
    column: int = 0
    fields: Optional[List[str]] = None  # Field names (not methods)
    embedding: Optional[List[float]] = None
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate required fields."""
        if not isinstance(self.name, str):
            return False, f"Struct.name must be a string, got {type(self.name).__name__}"
        if not self.name or not self.name.strip():
            return False, "Struct.name is required (String!) and cannot be empty"
        if not isinstance(self.file, str):
            return False, f"Struct.file must be a string, got {type(self.file).__name__}"
        if not self.file or not self.file.strip():
            return False, "Struct.file is required (String!) and cannot be empty"
        return True, None
    
    def to_dgraph_dict(self, uid: str) -> Dict[str, Any]:
        """Convert to Dgraph node dictionary."""
        node = {
            "uid": f"_:{uid}",
            "dgraph.type": "Struct",
            "Struct.name": self.name,
            "Struct.file": self.file,
            "Struct.line": self.line,
            "Struct.column": self.column,
        }
        
        # Add optional fields
        if self.fields is not None:
            node["Struct.fields"] = self.fields
        if self.embedding is not None:
            node["Struct.embedding"] = self.embedding
        
        return node


@dataclass
class ImportNode:
    """Import node with required fields enforced."""
    module: str  # Required: String!
    file: str  # Required: String!
    
    # Optional fields
    line: int = 0
    text: Optional[str] = None
    imported_items: Optional[List[str]] = None
    alias: Optional[str] = None
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate required fields."""
        if not isinstance(self.module, str):
            return False, f"Import.module must be a string, got {type(self.module).__name__}"
        if not self.module or not self.module.strip() or self.module == "<unknown>":
            return False, "Import.module is required (String!) and cannot be empty or '<unknown>'"
        if not isinstance(self.file, str):
            return False, f"Import.file must be a string, got {type(self.file).__name__}"
        if not self.file or not self.file.strip():
            return False, "Import.file is required (String!) and cannot be empty"
        return True, None
    
    def to_dgraph_dict(self, uid: str) -> Dict[str, Any]:
        """Convert to Dgraph node dictionary."""
        node = {
            "uid": f"_:{uid}",
            "dgraph.type": "Import",
            "Import.module": self.module,
            "Import.file": self.file,
            "Import.line": self.line,
        }
        
        # Add optional fields
        if self.text is not None:
            node["Import.text"] = self.text
        if self.imported_items is not None:
            node["Import.importedItems"] = self.imported_items
        if self.alias is not None:
            node["Import.alias"] = self.alias
        
        return node


@dataclass
class MacroNode:
    """Macro node with required fields enforced."""
    name: str  # Required: String!
    file: str  # Required: String!
    
    # Optional fields
    line: int = 0
    column: int = 0
    value: Optional[str] = None
    parameters: Optional[List[str]] = None
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate required fields."""
        if not isinstance(self.name, str):
            return False, f"Macro.name must be a string, got {type(self.name).__name__}"
        if not self.name or not self.name.strip():
            return False, "Macro.name is required (String!) and cannot be empty"
        if not isinstance(self.file, str):
            return False, f"Macro.file must be a string, got {type(self.file).__name__}"
        if not self.file or not self.file.strip():
            return False, "Macro.file is required (String!) and cannot be empty"
        if self.line == 0:
            logger.warning(f"Macro {self.name} in {self.file} has invalid line number (0), using 1")
            self.line = 1
        return True, None
    
    def to_dgraph_dict(self, uid: str) -> Dict[str, Any]:
        """Convert to Dgraph node dictionary."""
        node = {
            "uid": f"_:{uid}",
            "dgraph.type": "Macro",
            "Macro.name": self.name,
            "Macro.file": self.file,
            "Macro.line": self.line,
            "Macro.column": self.column,
        }
        
        # Add optional fields
        if self.value is not None:
            node["Macro.value"] = self.value
        if self.parameters is not None:
            node["Macro.parameters"] = self.parameters
        
        return node


@dataclass
class VariableNode:
    """Variable node with required fields enforced."""
    name: str  # Required: String!
    file: str  # Required: String!
    
    # Optional fields
    line: int = 0
    column: int = 0
    type: Optional[str] = None
    storage_class: Optional[str] = None
    is_global: bool = False
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate required fields."""
        if not isinstance(self.name, str):
            return False, f"Variable.name must be a string, got {type(self.name).__name__}"
        if not self.name or not self.name.strip():
            return False, "Variable.name is required (String!) and cannot be empty"
        if not isinstance(self.file, str):
            return False, f"Variable.file must be a string, got {type(self.file).__name__}"
        if not self.file or not self.file.strip():
            return False, "Variable.file is required (String!) and cannot be empty"
        if self.line == 0:
            logger.warning(f"Variable {self.name} in {self.file} has invalid line number (0), using 1")
            self.line = 1
        return True, None
    
    def to_dgraph_dict(self, uid: str) -> Dict[str, Any]:
        """Convert to Dgraph node dictionary."""
        node = {
            "uid": f"_:{uid}",
            "dgraph.type": "Variable",
            "Variable.name": self.name,
            "Variable.file": self.file,
            "Variable.line": self.line,
            "Variable.column": self.column,
            "Variable.isGlobal": self.is_global,
        }
        
        # Add optional fields
        if self.type is not None:
            node["Variable.type"] = self.type
        if self.storage_class is not None:
            node["Variable.storageClass"] = self.storage_class
        
        return node


@dataclass
class TypedefNode:
    """Typedef node with required fields enforced."""
    name: str  # Required: String!
    file: str  # Required: String!
    
    # Optional fields
    line: int = 0
    column: int = 0
    underlying_type: Optional[str] = None
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate required fields."""
        if not isinstance(self.name, str):
            return False, f"Typedef.name must be a string, got {type(self.name).__name__}"
        if not self.name or not self.name.strip():
            return False, "Typedef.name is required (String!) and cannot be empty"
        if not isinstance(self.file, str):
            return False, f"Typedef.file must be a string, got {type(self.file).__name__}"
        if not self.file or not self.file.strip():
            return False, "Typedef.file is required (String!) and cannot be empty"
        if self.line == 0:
            logger.warning(f"Typedef {self.name} in {self.file} has invalid line number (0), using 1")
            self.line = 1
        return True, None
    
    def to_dgraph_dict(self, uid: str) -> Dict[str, Any]:
        """Convert to Dgraph node dictionary."""
        node = {
            "uid": f"_:{uid}",
            "dgraph.type": "Typedef",
            "Typedef.name": self.name,
            "Typedef.file": self.file,
            "Typedef.line": self.line,
            "Typedef.column": self.column,
        }
        
        # Add optional fields
        if self.underlying_type is not None:
            node["Typedef.underlyingType"] = self.underlying_type
        
        return node


@dataclass
class StructFieldAccessNode:
    """StructFieldAccess node with required fields enforced."""
    struct_name: str  # Required: String!
    field_name: str  # Required: String!
    file: str  # Required: String!
    
    # Optional fields
    line: int = 0
    column: int = 0
    access_type: Optional[str] = None
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate required fields."""
        if not isinstance(self.struct_name, str):
            return False, f"StructFieldAccess.structName must be a string, got {type(self.struct_name).__name__}"
        if not self.struct_name or not self.struct_name.strip():
            return False, "StructFieldAccess.structName is required (String!) and cannot be empty"
        if not isinstance(self.field_name, str):
            return False, f"StructFieldAccess.fieldName must be a string, got {type(self.field_name).__name__}"
        if not self.field_name or not self.field_name.strip():
            return False, "StructFieldAccess.fieldName is required (String!) and cannot be empty"
        if not isinstance(self.file, str):
            return False, f"StructFieldAccess.file must be a string, got {type(self.file).__name__}"
        if not self.file or not self.file.strip():
            return False, "StructFieldAccess.file is required (String!) and cannot be empty"
        if self.line == 0:
            logger.warning(f"StructFieldAccess {self.struct_name}.{self.field_name} in {self.file} has invalid line number (0), using 1")
            self.line = 1
        return True, None
    
    def to_dgraph_dict(self, uid: str) -> Dict[str, Any]:
        """Convert to Dgraph node dictionary."""
        node = {
            "uid": f"_:{uid}",
            "dgraph.type": "StructFieldAccess",
            "StructFieldAccess.structName": self.struct_name,
            "StructFieldAccess.fieldName": self.field_name,
            "StructFieldAccess.file": self.file,
            "StructFieldAccess.line": self.line,
            "StructFieldAccess.column": self.column,
        }
        
        # Add optional fields
        if self.access_type is not None:
            node["StructFieldAccess.accessType"] = self.access_type
        
        return node


def create_file_node(data: Dict[str, Any]) -> Optional[FileNode]:
    """Create and validate a FileNode from dictionary data."""
    try:
        # Strict validation: ensure required fields exist and are strings
        path = data.get("path")
        if path is None or not isinstance(path, str):
            logger.error(f"Invalid FileNode: path is missing or not a string")
            return None
        
        node = FileNode(
            path=path,
            functions_count=data.get("functions_count", 0),
            classes_count=data.get("classes_count", 0),
            structs_count=data.get("structs_count", 0),
            imports_count=data.get("imports_count", 0),
            macros_count=data.get("macros_count", 0),
            variables_count=data.get("variables_count", 0),
            typedefs_count=data.get("typedefs_count", 0),
            struct_field_accesses_count=data.get("struct_field_accesses_count", 0),
            ast_nodes=data.get("ast_nodes", 0),
        )
        is_valid, error = node.validate()
        if not is_valid:
            logger.error(f"Invalid FileNode: {error}")
            return None
        return node
    except Exception as e:
        logger.error(f"Error creating FileNode: {e}")
        return None


def create_function_node(data: Dict[str, Any]) -> Optional[FunctionNode]:
    """Create and validate a FunctionNode from dictionary data."""
    try:
        # Strict validation: ensure required fields exist and are strings
        name = data.get("name")
        file = data.get("file")
        
        if name is None or not isinstance(name, str):
            logger.warning(f"Invalid FunctionNode: name is missing or not a string - skipping")
            return None
        if file is None or not isinstance(file, str):
            logger.warning(f"Invalid FunctionNode: file is missing or not a string - skipping")
            return None
        
        node = FunctionNode(
            name=name,
            file=file,
            line=data.get("line", 0),
            column=data.get("column", 0),
            signature=data.get("signature"),
            parameters=json.dumps(data["parameters"]) if isinstance(data.get("parameters"), list) else data.get("parameters"),
            return_type=data.get("return_type"),
            docstring=data.get("docstring"),
            embedding=data.get("embedding"),
            belongs_to_class=data.get("belongs_to_class"),
        )
        is_valid, error = node.validate()
        if not is_valid:
            logger.warning(f"Invalid FunctionNode: {error} - skipping")
            return None
        return node
    except Exception as e:
        logger.error(f"Error creating FunctionNode: {e}")
        return None


def create_class_node(data: Dict[str, Any]) -> Optional[ClassNode]:
    """Create and validate a ClassNode from dictionary data."""
    try:
        # Strict validation: ensure required fields exist and are strings
        name = data.get("name")
        file = data.get("file")
        
        if name is None or not isinstance(name, str):
            logger.warning(f"Invalid ClassNode: name is missing or not a string - skipping")
            return None
        if file is None or not isinstance(file, str):
            logger.warning(f"Invalid ClassNode: file is missing or not a string - skipping")
            return None
        
        node = ClassNode(
            name=name,
            file=file,
            line=data.get("line", 0),
            column=data.get("column", 0),
            methods=data.get("methods"),
            base_classes=data.get("base_classes"),
            embedding=data.get("embedding"),
        )
        is_valid, error = node.validate()
        if not is_valid:
            logger.warning(f"Invalid ClassNode: {error} - skipping")
            return None
        return node
    except Exception as e:
        logger.error(f"Error creating ClassNode: {e}")
        return None


def create_struct_node(data: Dict[str, Any]) -> Optional[StructNode]:
    """Create and validate a StructNode from dictionary data."""
    try:
        # Strict validation: ensure required fields exist and are strings
        name = data.get("name")
        file = data.get("file")
        
        if name is None or not isinstance(name, str):
            logger.warning(f"Invalid StructNode: name is missing or not a string - skipping")
            return None
        if file is None or not isinstance(file, str):
            logger.warning(f"Invalid StructNode: file is missing or not a string - skipping")
            return None
        
        node = StructNode(
            name=name,
            file=file,
            line=data.get("line", 0),
            column=data.get("column", 0),
            fields=data.get("fields"),
            embedding=data.get("embedding"),
        )
        is_valid, error = node.validate()
        if not is_valid:
            logger.warning(f"Invalid StructNode: {error} - skipping")
            return None
        return node
    except Exception as e:
        logger.error(f"Error creating StructNode: {e}")
        return None


def create_import_node(data: Dict[str, Any]) -> Optional[ImportNode]:
    """Create and validate an ImportNode from dictionary data."""
    try:
        # Strict validation: ensure required fields exist and are strings
        module = data.get("module")
        file = data.get("file")
        
        # Use text as fallback if module is missing (for C includes that don't parse as modules)
        if module is None or (isinstance(module, str) and not module.strip()):
            if "text" in data and data["text"]:
                module = data["text"].strip()
            else:
                logger.warning(f"Invalid ImportNode: module is missing and no text fallback - skipping")
                return None
        
        if not isinstance(module, str):
            logger.warning(f"Invalid ImportNode: module is not a string - skipping")
            return None
        
        if file is None or not isinstance(file, str):
            logger.warning(f"Invalid ImportNode: file is missing or not a string - skipping")
            return None
        
        node = ImportNode(
            module=module,
            file=file,
            line=data.get("line", 0),
            text=data.get("text"),
            imported_items=data.get("imported_items"),
            alias=data.get("alias"),
        )
        is_valid, error = node.validate()
        if not is_valid:
            logger.warning(f"Invalid ImportNode: {error} - skipping")
            return None
        return node
    except Exception as e:
        logger.error(f"Error creating ImportNode: {e}")
        return None


def create_macro_node(data: Dict[str, Any]) -> Optional[MacroNode]:
    """Create and validate a MacroNode from dictionary data."""
    try:
        # Strict validation: ensure required fields exist and are strings
        name = data.get("name")
        file = data.get("file")
        
        if name is None or not isinstance(name, str):
            logger.warning(f"Invalid MacroNode: name is missing or not a string - skipping")
            return None
        if file is None or not isinstance(file, str):
            logger.warning(f"Invalid MacroNode: file is missing or not a string - skipping")
            return None
        
        node = MacroNode(
            name=name,
            file=file,
            line=data.get("line", 0),
            column=data.get("column", 0),
            value=data.get("value"),
            parameters=data.get("parameters"),
        )
        is_valid, error = node.validate()
        if not is_valid:
            logger.warning(f"Invalid MacroNode: {error} - skipping")
            return None
        return node
    except Exception as e:
        logger.error(f"Error creating MacroNode: {e}")
        return None


def create_variable_node(data: Dict[str, Any]) -> Optional[VariableNode]:
    """Create and validate a VariableNode from dictionary data."""
    try:
        # Strict validation: ensure required fields exist and are strings
        name = data.get("name")
        file = data.get("file")
        
        if name is None or not isinstance(name, str):
            logger.warning(f"Invalid VariableNode: name is missing or not a string - skipping")
            return None
        if file is None or not isinstance(file, str):
            logger.warning(f"Invalid VariableNode: file is missing or not a string - skipping")
            return None
        
        node = VariableNode(
            name=name,
            file=file,
            line=data.get("line", 0),
            column=data.get("column", 0),
            type=data.get("type"),
            storage_class=data.get("storage_class"),
            is_global=data.get("is_global", False),
        )
        is_valid, error = node.validate()
        if not is_valid:
            logger.warning(f"Invalid VariableNode: {error} - skipping")
            return None
        return node
    except Exception as e:
        logger.error(f"Error creating VariableNode: {e}")
        return None


def create_typedef_node(data: Dict[str, Any]) -> Optional[TypedefNode]:
    """Create and validate a TypedefNode from dictionary data."""
    try:
        # Strict validation: ensure required fields exist and are strings
        name = data.get("name")
        file = data.get("file")
        
        if name is None or not isinstance(name, str):
            logger.warning(f"Invalid TypedefNode: name is missing or not a string - skipping")
            return None
        if file is None or not isinstance(file, str):
            logger.warning(f"Invalid TypedefNode: file is missing or not a string - skipping")
            return None
        
        node = TypedefNode(
            name=name,
            file=file,
            line=data.get("line", 0),
            column=data.get("column", 0),
            underlying_type=data.get("underlying_type"),
        )
        is_valid, error = node.validate()
        if not is_valid:
            logger.warning(f"Invalid TypedefNode: {error} - skipping")
            return None
        return node
    except Exception as e:
        logger.error(f"Error creating TypedefNode: {e}")
        return None


def create_struct_field_access_node(data: Dict[str, Any]) -> Optional[StructFieldAccessNode]:
    """Create and validate a StructFieldAccessNode from dictionary data."""
    try:
        # Strict validation: ensure required fields exist and are strings
        struct_name = data.get("struct_name")
        field_name = data.get("field_name")
        file = data.get("file")
        
        if struct_name is None or not isinstance(struct_name, str):
            logger.warning(f"Invalid StructFieldAccessNode: struct_name is missing or not a string - skipping")
            return None
        if field_name is None or not isinstance(field_name, str):
            logger.warning(f"Invalid StructFieldAccessNode: field_name is missing or not a string - skipping")
            return None
        if file is None or not isinstance(file, str):
            logger.warning(f"Invalid StructFieldAccessNode: file is missing or not a string - skipping")
            return None
        
        node = StructFieldAccessNode(
            struct_name=struct_name,
            field_name=field_name,
            file=file,
            line=data.get("line", 0),
            column=data.get("column", 0),
            access_type=data.get("access_type"),
        )
        is_valid, error = node.validate()
        if not is_valid:
            logger.warning(f"Invalid StructFieldAccessNode: {error} - skipping")
            return None
        return node
    except Exception as e:
        logger.error(f"Error creating StructFieldAccessNode: {e}")
        return None

