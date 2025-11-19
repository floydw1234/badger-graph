"""Integration tests for C parser."""

import pytest
from pathlib import Path
from badger.parsers.c import CParser


class TestCParserIntegration:
    """Integration tests for complete C parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create a C parser instance."""
        return CParser()
    
    def test_parse_service_c_complete(self, parser):
        """Test complete parsing of service.c."""
        service_file = Path(__file__).parent.parent / "test_code" / "C" / "service.c"
        if not service_file.exists():
            pytest.skip("service.c not found")
        
        result = parser.parse_file(service_file)
        
        # Verify all components are extracted
        assert result.file_path == str(service_file)
        assert len(result.functions) > 0
        assert len(result.imports) > 0
        assert len(result.function_calls) > 0
        assert result.total_nodes > 0
        
        # Verify function enhancements
        func_with_signature = None
        for func in result.functions:
            if func.signature:
                func_with_signature = func
                break
        assert func_with_signature is not None, "Should have at least one function with signature"
        
        # Verify import enhancements
        import_with_module = None
        for imp in result.imports:
            if imp.module:
                import_with_module = imp
                break
        assert import_with_module is not None, "Should have at least one import with module"
        
        # Verify function calls have proper structure
        for call in result.function_calls:
            assert call.caller_name is not None
            assert call.callee_name is not None
            assert call.file_path == str(service_file)
    
    def test_parse_service_h_complete(self, parser):
        """Test complete parsing of service.h."""
        service_file = Path(__file__).parent.parent / "test_code" / "C" / "service.h"
        if not service_file.exists():
            pytest.skip("service.h not found")
        
        result = parser.parse_file(service_file)
        
        # Verify all components
        assert len(result.functions) > 0  # Function declarations
        assert len(result.classes) >= 2  # BaseService and UserService
        assert len(result.imports) > 0
        
        # Verify struct fields
        base_service = None
        for cls in result.classes:
            if cls.name == "BaseService":
                base_service = cls
                break
        assert base_service is not None
        assert len(base_service.methods) >= 2  # Should have fields
    
    def test_parse_complex_c_file(self, parser, tmp_path):
        """Test parsing a complex C file with all features."""
        test_file = tmp_path / "complex.c"
        test_file.write_text("""
#include <stdio.h>
#include "header.h"

typedef int MyInt;

struct MyStruct {
    int x;
    char* y;
};

void process_data(int value) {
    helper(value);
    printf("Done\\n");
}

int helper(int x) {
    return x * 2;
}
""")
        
        result = parser.parse_file(test_file)
        
        # Verify functions
        assert len(result.functions) >= 2
        process_func = None
        for func in result.functions:
            if func.name == "process_data":
                process_func = func
                break
        assert process_func is not None
        
        # Verify struct
        assert len(result.classes) >= 1
        my_struct = None
        for cls in result.classes:
            if cls.name == "MyStruct":
                my_struct = cls
                break
        assert my_struct is not None
        assert len(my_struct.methods) >= 2  # Should have fields
        
        # Verify includes
        assert len(result.imports) >= 2
        
        # Verify function calls
        assert len(result.function_calls) > 0
        helper_calls = [call for call in result.function_calls if "helper" in call.callee_name]
        assert len(helper_calls) > 0
    
    def test_backward_compatibility(self, parser, tmp_path):
        """Test that existing code still works with enhanced parser."""
        test_file = tmp_path / "simple.c"
        test_file.write_text("""
void simple_func() {
}

struct SimpleStruct {
    int x;
};

#include <stdio.h>
""")
        
        result = parser.parse_file(test_file)
        
        # Should still extract basic information
        assert len(result.functions) == 1
        assert len(result.classes) == 1
        assert len(result.imports) == 1
        
        # New fields should have defaults or be populated
        func = result.functions[0]
        assert func.signature is not None  # Should be built even if empty
        
        cls = result.classes[0]
        assert cls.base_classes == []  # C doesn't have inheritance

