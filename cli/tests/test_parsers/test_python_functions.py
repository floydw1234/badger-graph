"""Tests for Python function extraction."""

import pytest
from pathlib import Path
from badger.parsers.python import PythonParser


class TestFunctionExtraction:
    """Test function extraction from Python files."""
    
    @pytest.fixture
    def parser(self):
        """Create a Python parser instance."""
        return PythonParser()
    
    def test_extract_function_from_sample_app(self, parser):
        """Test extracting functions from sample_app.py."""
        sample_file = Path(__file__).parent.parent / "test_code" / "python" / "sample_app.py"
        if not sample_file.exists():
            pytest.skip("sample_app.py not found")
        
        result = parser.parse_file(sample_file)
        
        # Find validate_email function
        validate_func = None
        for func in result.functions:
            if func.name == "validate_email":
                validate_func = func
                break
        
        assert validate_func is not None, "validate_email function should be found"
        assert validate_func.parameters == ["email"], f"Expected ['email'], got {validate_func.parameters}"
        assert validate_func.return_type is not None, "Return type should be extracted"
        assert "bool" in validate_func.return_type, f"Expected bool in return type, got {validate_func.return_type}"
        assert validate_func.docstring is not None, "Docstring should be extracted"
        assert "email" in validate_func.docstring.lower(), f"Docstring should mention email: {validate_func.docstring}"
        assert validate_func.signature is not None, "Signature should be built"
        assert "validate_email" in validate_func.signature, "Signature should contain function name"
    
    def test_extract_function_with_parameters(self, parser, tmp_path):
        """Test extracting a function with parameters."""
        test_file = tmp_path / "test_func.py"
        test_file.write_text("""
def test_func(x, y):
    return x + y
""")
        
        result = parser.parse_file(test_file)
        assert len(result.functions) == 1
        assert result.functions[0].name == "test_func"
        assert result.functions[0].parameters == ["x", "y"]
        assert "test_func" in result.functions[0].signature
        assert "x" in result.functions[0].signature
        assert "y" in result.functions[0].signature
    
    def test_extract_function_with_type_hints(self, parser, tmp_path):
        """Test extracting a function with type hints."""
        test_file = tmp_path / "test_func.py"
        test_file.write_text("""
def validate_email(email: str) -> bool:
    return '@' in email and '.' in email
""")
        
        result = parser.parse_file(test_file)
        assert len(result.functions) == 1
        assert result.functions[0].name == "validate_email"
        assert result.functions[0].parameters == ["email"]
        assert result.functions[0].return_type is not None
        assert "bool" in result.functions[0].return_type
        assert "->" in result.functions[0].signature
    
    def test_extract_function_with_docstring(self, parser, tmp_path):
        """Test extracting a function with docstring."""
        test_file = tmp_path / "test_func.py"
        test_file.write_text('''
def test_func():
    """This is a docstring."""
    pass
''')
        
        result = parser.parse_file(test_file)
        assert len(result.functions) == 1
        assert result.functions[0].name == "test_func"
        assert result.functions[0].docstring is not None
        assert "docstring" in result.functions[0].docstring.lower()
    
    def test_extract_function_with_complex_signature(self, parser, tmp_path):
        """Test extracting a function with complex signature."""
        test_file = tmp_path / "test_func.py"
        test_file.write_text("""
def create_user(self, name: str, email: str) -> User:
    \"\"\"Create a new user.\"\"\"
    pass
""")
        
        result = parser.parse_file(test_file)
        assert len(result.functions) == 1
        assert result.functions[0].name == "create_user"
        assert "self" in result.functions[0].parameters
        assert "name" in result.functions[0].parameters
        assert "email" in result.functions[0].parameters
        assert result.functions[0].return_type is not None
        assert "User" in result.functions[0].return_type
        assert result.functions[0].docstring is not None
        assert "user" in result.functions[0].docstring.lower()

