"""Tests for base dataclasses."""

import pytest
from badger.parsers.base import (
    Position, Function, Class, Import, FunctionCall, ParseResult
)


class TestPosition:
    """Test Position dataclass."""
    
    def test_position_creation(self):
        """Test creating a Position."""
        pos = Position(row=10, column=5)
        assert pos.row == 10
        assert pos.column == 5


class TestFunction:
    """Test Function dataclass."""
    
    def test_function_creation_minimal(self):
        """Test creating a Function with minimal fields."""
        pos = Position(row=1, column=0)
        func = Function(
            name="test_func",
            start=pos,
            end=pos,
            file_path="test.py"
        )
        assert func.name == "test_func"
        assert func.signature is None
        assert func.parameters == []
        assert func.return_type is None
        assert func.docstring is None
    
    def test_function_creation_full(self):
        """Test creating a Function with all fields."""
        pos = Position(row=1, column=0)
        func = Function(
            name="test_func",
            start=pos,
            end=pos,
            file_path="test.py",
            signature="test_func(x: int, y: str) -> bool",
            parameters=["x", "y"],
            return_type="bool",
            docstring="Test function"
        )
        assert func.name == "test_func"
        assert func.signature == "test_func(x: int, y: str) -> bool"
        assert func.parameters == ["x", "y"]
        assert func.return_type == "bool"
        assert func.docstring == "Test function"
    
    def test_function_backward_compatibility(self):
        """Test that existing code still works with new fields."""
        pos = Position(row=1, column=0)
        func = Function(
            name="test_func",
            start=pos,
            end=pos,
            file_path="test.py"
        )
        # Should work without new fields
        assert func.name == "test_func"
        # New fields should have defaults
        assert func.parameters == []


class TestClass:
    """Test Class dataclass."""
    
    def test_class_creation_minimal(self):
        """Test creating a Class with minimal fields."""
        pos = Position(row=1, column=0)
        cls = Class(
            name="TestClass",
            start=pos,
            end=pos,
            file_path="test.py"
        )
        assert cls.name == "TestClass"
        assert cls.methods == []
        assert cls.base_classes == []
    
    def test_class_creation_full(self):
        """Test creating a Class with all fields."""
        pos = Position(row=1, column=0)
        cls = Class(
            name="TestClass",
            start=pos,
            end=pos,
            file_path="test.py",
            methods=["method1", "method2"],
            base_classes=["BaseClass"]
        )
        assert cls.name == "TestClass"
        assert cls.methods == ["method1", "method2"]
        assert cls.base_classes == ["BaseClass"]
    
    def test_class_backward_compatibility(self):
        """Test that existing code still works with new fields."""
        pos = Position(row=1, column=0)
        cls = Class(
            name="TestClass",
            start=pos,
            end=pos,
            file_path="test.py"
        )
        assert cls.name == "TestClass"
        assert cls.methods == []
        assert cls.base_classes == []


class TestImport:
    """Test Import dataclass."""
    
    def test_import_creation_minimal(self):
        """Test creating an Import with minimal fields."""
        pos = Position(row=1, column=0)
        imp = Import(
            text="import os",
            start=pos,
            end=pos,
            file_path="test.py"
        )
        assert imp.text == "import os"
        assert imp.module is None
        assert imp.imported_items == []
        assert imp.alias is None
    
    def test_import_creation_full(self):
        """Test creating an Import with all fields."""
        pos = Position(row=1, column=0)
        imp = Import(
            text="from typing import List, Dict",
            start=pos,
            end=pos,
            file_path="test.py",
            module="typing",
            imported_items=["List", "Dict"],
            alias=None
        )
        assert imp.text == "from typing import List, Dict"
        assert imp.module == "typing"
        assert imp.imported_items == ["List", "Dict"]
        assert imp.alias is None
    
    def test_import_backward_compatibility(self):
        """Test that existing code still works with new fields."""
        pos = Position(row=1, column=0)
        imp = Import(
            text="import os",
            start=pos,
            end=pos,
            file_path="test.py"
        )
        assert imp.text == "import os"
        assert imp.imported_items == []


class TestFunctionCall:
    """Test FunctionCall dataclass."""
    
    def test_function_call_creation(self):
        """Test creating a FunctionCall."""
        pos = Position(row=10, column=5)
        call = FunctionCall(
            caller_name="main",
            callee_name="test_func",
            is_method_call=False,
            start=pos,
            end=pos,
            file_path="test.py"
        )
        assert call.caller_name == "main"
        assert call.callee_name == "test_func"
        assert call.is_method_call is False
        assert call.start == pos
        assert call.end == pos
        assert call.file_path == "test.py"
    
    def test_method_call_creation(self):
        """Test creating a method call."""
        pos = Position(row=10, column=5)
        call = FunctionCall(
            caller_name="main",
            callee_name="obj.method",
            is_method_call=True,
            start=pos,
            end=pos,
            file_path="test.py"
        )
        assert call.is_method_call is True
        assert call.callee_name == "obj.method"


class TestParseResult:
    """Test ParseResult dataclass."""
    
    def test_parse_result_creation_minimal(self):
        """Test creating a ParseResult with minimal fields."""
        result = ParseResult(
            file_path="test.py",
            functions=[],
            classes=[],
            imports=[],
            total_nodes=100
        )
        assert result.file_path == "test.py"
        assert result.functions == []
        assert result.classes == []
        assert result.imports == []
        assert result.function_calls == []
        assert result.tree_string is None
    
    def test_parse_result_creation_full(self):
        """Test creating a ParseResult with all fields."""
        pos = Position(row=1, column=0)
        func = Function(
            name="test_func",
            start=pos,
            end=pos,
            file_path="test.py"
        )
        call = FunctionCall(
            caller_name="main",
            callee_name="test_func",
            is_method_call=False,
            start=pos,
            end=pos,
            file_path="test.py"
        )
        result = ParseResult(
            file_path="test.py",
            functions=[func],
            classes=[],
            imports=[],
            total_nodes=100,
            tree_string="def test_func(): pass",
            function_calls=[call]
        )
        assert len(result.functions) == 1
        assert len(result.function_calls) == 1
        assert result.tree_string == "def test_func(): pass"
    
    def test_parse_result_backward_compatibility(self):
        """Test that existing code still works with new fields."""
        result = ParseResult(
            file_path="test.py",
            functions=[],
            classes=[],
            imports=[],
            total_nodes=100
        )
        assert result.function_calls == []

