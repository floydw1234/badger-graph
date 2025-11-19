"""Tests for C function call extraction."""

import pytest
from pathlib import Path
from badger.parsers.c import CParser


class TestCFunctionCallExtraction:
    """Test function call extraction from C files."""
    
    @pytest.fixture
    def parser(self):
        """Create a C parser instance."""
        return CParser()
    
    def test_extract_simple_function_call(self, parser, tmp_path):
        """Test extracting a simple function call."""
        test_file = tmp_path / "test_calls.c"
        test_file.write_text("""
void test_func() {
    helper();
}
""")
        
        result = parser.parse_file(test_file)
        assert len(result.function_calls) >= 1
        # Find the helper() call
        helper_call = None
        for call in result.function_calls:
            if call.callee_name == "helper":
                helper_call = call
                break
        assert helper_call is not None
        assert helper_call.caller_name == "test_func"
        assert helper_call.is_method_call is False
    
    def test_extract_method_call(self, parser, tmp_path):
        """Test extracting a method call (struct member access)."""
        test_file = tmp_path / "test_calls.c"
        test_file.write_text("""
void test_func() {
    obj->method();
}
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
    
    def test_extract_calls_from_main_c(self, parser):
        """Test extracting function calls from main.c."""
        main_file = Path(__file__).parent.parent / "test_code" / "C" / "main.c"
        if not main_file.exists():
            pytest.skip("main.c not found")
        
        result = parser.parse_file(main_file)
        assert len(result.function_calls) > 0
        
        # Check that calls have caller context
        for call in result.function_calls:
            assert call.caller_name is not None
            assert call.callee_name is not None
            assert call.file_path == str(main_file)
        
        # Should have calls to functions like user_service_init, printf, etc.
        call_names = [call.callee_name for call in result.function_calls]
        assert len(call_names) > 0
    
    def test_extract_calls_from_service_c(self, parser):
        """Test extracting function calls from service.c."""
        service_file = Path(__file__).parent.parent / "test_code" / "C" / "service.c"
        if not service_file.exists():
            pytest.skip("service.c not found")
        
        result = parser.parse_file(service_file)
        assert len(result.function_calls) > 0
        
        # Should have function calls
        call_names = [call.callee_name for call in result.function_calls]
        assert len(call_names) > 0
    
    def test_caller_context_tracking(self, parser, tmp_path):
        """Test that caller context is tracked correctly."""
        test_file = tmp_path / "test_calls.c"
        test_file.write_text("""
void func1() {
    helper();
}

void func2() {
    helper();
}

void helper() {
}
""")
        
        result = parser.parse_file(test_file)
        # Should find helper() calls in both func1 and func2
        helper_calls = [call for call in result.function_calls if call.callee_name == "helper"]
        assert len(helper_calls) >= 2
        callers = [call.caller_name for call in helper_calls]
        assert "func1" in callers
        assert "func2" in callers

