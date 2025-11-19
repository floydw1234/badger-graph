"""Tests for C typedef extraction."""

import pytest
from pathlib import Path
from badger.parsers.c import CParser


class TestCTypedefExtraction:
    """Test typedef extraction from C files."""
    
    @pytest.fixture
    def parser(self):
        """Create a C parser instance."""
        return CParser()
    
    def test_extract_simple_typedef(self, parser, tmp_path):
        """Test extracting a simple typedef."""
        test_file = tmp_path / "test_typedef.c"
        test_file.write_text("""
typedef int MyInt;
""")
        
        result = parser.parse_file(test_file)
        assert len(result.typedefs) == 1
        assert result.typedefs[0].name == "MyInt"
        assert result.typedefs[0].underlying_type == "int"
    
    def test_extract_typedef_from_service_h(self, parser):
        """Test extracting typedefs from service.h."""
        service_file = Path(__file__).parent.parent / "test_code" / "C" / "service.h"
        if not service_file.exists():
            pytest.skip("service.h not found")
        
        result = parser.parse_file(service_file)
        # service.h has typedef structs, which are extracted as classes, not typedefs
        # So we might have 0 simple typedefs, but should have struct typedefs as classes
        assert len(result.classes) >= 2  # BaseService and UserService are typedef structs
    
    def test_typedef_struct_not_in_typedefs(self, parser, tmp_path):
        """Test that typedef structs are in classes, not typedefs list."""
        test_file = tmp_path / "test_typedef.h"
        test_file.write_text("""
typedef struct {
    int x;
} MyStruct;
""")
        
        result = parser.parse_file(test_file)
        # Typedef struct should be in classes
        assert len(result.classes) == 1
        assert result.classes[0].name == "MyStruct"
        # Should not be in typedefs (only simple typedefs go there)
        typedef_names = [t.name for t in result.typedefs]
        assert "MyStruct" not in typedef_names

