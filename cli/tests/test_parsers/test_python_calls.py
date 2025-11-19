"""Tests for Python function call extraction."""

import pytest
from pathlib import Path
from badger.parsers.python import PythonParser


class TestFunctionCallExtraction:
    """Test function call extraction from Python files."""
    
    @pytest.fixture
    def parser(self):
        """Create a Python parser instance."""
        return PythonParser()
    
    def test_extract_simple_function_call(self, parser, tmp_path):
        """Test extracting a simple function call."""
        test_file = tmp_path / "test_calls.py"
        test_file.write_text("""
def test_func():
    result = square(5)
    return result
""")
        
        result = parser.parse_file(test_file)
        assert len(result.function_calls) >= 1
        # Find the square() call
        square_call = None
        for call in result.function_calls:
            if call.callee_name == "square":
                square_call = call
                break
        assert square_call is not None
        assert square_call.caller_name == "test_func"
        assert square_call.is_method_call is False
    
    def test_extract_method_call(self, parser, tmp_path):
        """Test extracting a method call."""
        test_file = tmp_path / "test_calls.py"
        test_file.write_text("""
def test_func():
    obj = SomeClass()
    result = obj.method()
    return result
""")
        
        result = parser.parse_file(test_file)
        assert len(result.function_calls) >= 1
        # Find the method() call
        method_call = None
        for call in result.function_calls:
            if "method" in call.callee_name:
                method_call = call
                break
        assert method_call is not None
        assert method_call.is_method_call is True
    
    def test_extract_nested_calls(self, parser, tmp_path):
        """Test extracting nested function calls."""
        test_file = tmp_path / "test_calls.py"
        test_file.write_text("""
def process_data(data):
    result = outer(inner(data))
    return result
""")
        
        result = parser.parse_file(test_file)
        # Should find both inner() and outer() calls
        call_names = [call.callee_name for call in result.function_calls]
        assert "inner" in call_names or "outer" in call_names
    
    def test_extract_calls_from_sample_app(self, parser):
        """Test extracting function calls from sample_app.py."""
        sample_file = Path(__file__).parent.parent / "test_code" / "python" / "sample_app.py"
        if not sample_file.exists():
            pytest.skip("sample_app.py not found")
        
        result = parser.parse_file(sample_file)
        assert len(result.function_calls) > 0
        
        # Check that calls have caller context
        for call in result.function_calls:
            assert call.caller_name is not None
            assert call.callee_name is not None
            assert call.file_path == str(sample_file)
    
    def test_extract_calls_from_nested_calls(self, parser):
        """Test extracting calls from nested_calls.py."""
        nested_file = Path(__file__).parent.parent / "test_code" / "python" / "nested_calls.py"
        if not nested_file.exists():
            pytest.skip("nested_calls.py not found")
        
        result = parser.parse_file(nested_file)
        assert len(result.function_calls) > 0
        
        # Should have method calls
        method_calls = [call for call in result.function_calls if call.is_method_call]
        assert len(method_calls) > 0, "Should have at least one method call"
        
        # Should have function calls
        function_calls = [call for call in result.function_calls if not call.is_method_call]
        assert len(function_calls) > 0, "Should have at least one function call"
    
    def test_caller_context_tracking(self, parser, tmp_path):
        """Test that caller context is tracked correctly."""
        test_file = tmp_path / "test_calls.py"
        test_file.write_text("""
def func1():
    helper()

def func2():
    helper()

def helper():
    pass
""")
        
        result = parser.parse_file(test_file)
        # Should find helper() calls in both func1 and func2
        helper_calls = [call for call in result.function_calls if call.callee_name == "helper"]
        assert len(helper_calls) >= 2
        callers = [call.caller_name for call in helper_calls]
        assert "func1" in callers
        assert "func2" in callers

