"""Integration tests for Python parser."""

import pytest
from pathlib import Path
from badger.parsers.python import PythonParser


class TestPythonParserIntegration:
    """Integration tests for complete Python parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create a Python parser instance."""
        return PythonParser()
    
    def test_parse_sample_app_complete(self, parser):
        """Test complete parsing of sample_app.py."""
        sample_file = Path(__file__).parent.parent / "test_code" / "python" / "sample_app.py"
        if not sample_file.exists():
            pytest.skip("sample_app.py not found")
        
        result = parser.parse_file(sample_file)
        
        # Verify all components are extracted
        assert result.file_path == str(sample_file)
        assert len(result.functions) > 0
        assert len(result.classes) > 0
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
        
        # Verify class enhancements
        class_with_methods = None
        for cls in result.classes:
            if cls.methods:
                class_with_methods = cls
                break
        assert class_with_methods is not None, "Should have at least one class with methods"
        
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
            assert call.file_path == str(sample_file)
    
    def test_parse_complex_file(self, parser, tmp_path):
        """Test parsing a complex Python file with all features."""
        test_file = tmp_path / "complex.py"
        test_file.write_text("""
\"\"\"Complex test file.\"\"\"

import json
from typing import List, Dict, Optional

class BaseClass:
    def base_method(self):
        pass

class DerivedClass(BaseClass):
    def __init__(self, value: int):
        self.value = value
    
    def process(self, data: List[int]) -> int:
        \"\"\"Process data.\"\"\"
        result = sum(data)
        return result
    
    def helper(self):
        self.process([1, 2, 3])

def main():
    obj = DerivedClass(10)
    obj.process([1, 2, 3])
    obj.helper()

if __name__ == "__main__":
    main()
""")
        
        result = parser.parse_file(test_file)
        
        # Verify functions
        assert len(result.functions) >= 2  # main and process at least
        main_func = None
        for func in result.functions:
            if func.name == "main":
                main_func = func
                break
        assert main_func is not None
        
        # Verify classes
        assert len(result.classes) >= 2  # BaseClass and DerivedClass
        derived = None
        for cls in result.classes:
            if cls.name == "DerivedClass":
                derived = cls
                break
        assert derived is not None
        assert "BaseClass" in derived.base_classes
        assert len(derived.methods) > 0
        
        # Verify imports
        assert len(result.imports) >= 2
        
        # Verify function calls
        assert len(result.function_calls) > 0
        process_calls = [call for call in result.function_calls if "process" in call.callee_name]
        assert len(process_calls) > 0
    
    def test_backward_compatibility(self, parser, tmp_path):
        """Test that existing code still works with enhanced parser."""
        test_file = tmp_path / "simple.py"
        test_file.write_text("""
def simple_func():
    pass

class SimpleClass:
    pass

import os
""")
        
        result = parser.parse_file(test_file)
        
        # Should still extract basic information
        assert len(result.functions) == 1
        assert len(result.classes) == 1
        assert len(result.imports) == 1
        
        # New fields should have defaults
        func = result.functions[0]
        assert func.parameters == []
        assert func.signature is not None  # Should be built even if empty
        
        cls = result.classes[0]
        assert cls.methods == []
        assert cls.base_classes == []
        
        imp = result.imports[0]
        assert imp.module is not None or imp.text  # Should have at least text

