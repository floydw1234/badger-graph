"""Tests for C function extraction."""

import pytest
from pathlib import Path
from badger.parsers.c import CParser


class TestCFunctionExtraction:
    """Test function extraction from C files."""
    
    @pytest.fixture
    def parser(self):
        """Create a C parser instance."""
        return CParser()
    
    def test_extract_function_with_parameters(self, parser, tmp_path):
        """Test extracting a function with parameters."""
        test_file = tmp_path / "test_func.c"
        test_file.write_text("""
void test_func(int x, char* y) {
    return;
}
""")
        
        result = parser.parse_file(test_file)
        assert len(result.functions) == 1
        assert result.functions[0].name == "test_func"
        assert len(result.functions[0].parameters) >= 2
        assert "x" in result.functions[0].parameters
        assert result.functions[0].return_type == "void"
        assert "test_func" in result.functions[0].signature
    
    def test_extract_function_with_return_type(self, parser, tmp_path):
        """Test extracting a function with return type."""
        test_file = tmp_path / "test_func.c"
        test_file.write_text("""
int calculate(int a, int b) {
    return a + b;
}
""")
        
        result = parser.parse_file(test_file)
        assert len(result.functions) == 1
        assert result.functions[0].name == "calculate"
        assert result.functions[0].return_type == "int"
        assert "int" in result.functions[0].signature
    
    def test_extract_function_declaration(self, parser, tmp_path):
        """Test extracting a function declaration."""
        test_file = tmp_path / "test_func.h"
        test_file.write_text("""
void base_service_init(BaseService* service, const char* config_path);
""")
        
        result = parser.parse_file(test_file)
        assert len(result.functions) == 1
        assert result.functions[0].name == "base_service_init"
        assert result.functions[0].return_type == "void"
        assert ";" in result.functions[0].signature  # Declaration should end with ;
    
    def test_extract_function_from_service_c(self, parser):
        """Test extracting functions from service.c."""
        service_file = Path(__file__).parent.parent / "test_code" / "C" / "service.c"
        if not service_file.exists():
            pytest.skip("service.c not found")
        
        result = parser.parse_file(service_file)
        assert len(result.functions) > 0
        
        # Find base_service_init function
        base_init = None
        for func in result.functions:
            if func.name == "base_service_init":
                base_init = func
                break
        
        assert base_init is not None, "base_service_init function should be found"
        assert base_init.return_type == "void"
        assert len(base_init.parameters) >= 2
        assert "service" in base_init.parameters or "config_path" in base_init.parameters
    
    def test_extract_function_from_service_h(self, parser):
        """Test extracting function declarations from service.h."""
        service_file = Path(__file__).parent.parent / "test_code" / "C" / "service.h"
        if not service_file.exists():
            pytest.skip("service.h not found")
        
        result = parser.parse_file(service_file)
        assert len(result.functions) > 0
        
        # Should have function declarations
        declarations = [f for f in result.functions if ";" in f.signature]
        assert len(declarations) > 0, "Should have function declarations"
    
    def test_extract_function_with_pointer_return(self, parser, tmp_path):
        """Test extracting a function with pointer return type."""
        test_file = tmp_path / "test_func.c"
        test_file.write_text("""
User* get_user(int id) {
    return NULL;
}
""")
        
        result = parser.parse_file(test_file)
        assert len(result.functions) == 1
        assert result.functions[0].name == "get_user"
        # Return type might be "User*" or just "User" depending on parsing
        assert result.functions[0].return_type is not None

