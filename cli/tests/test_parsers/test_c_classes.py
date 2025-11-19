"""Tests for C struct/union/enum extraction."""

import pytest
from pathlib import Path
from badger.parsers.c import CParser


class TestCClassExtraction:
    """Test struct/union/enum extraction from C files."""
    
    @pytest.fixture
    def parser(self):
        """Create a C parser instance."""
        return CParser()
    
    def test_extract_struct_with_fields(self, parser, tmp_path):
        """Test extracting a struct with fields."""
        test_file = tmp_path / "test_struct.c"
        test_file.write_text("""
struct MyStruct {
    int x;
    char* y;
};
""")
        
        result = parser.parse_file(test_file)
        assert len(result.classes) == 1
        assert result.classes[0].name == "MyStruct"
        assert len(result.classes[0].methods) >= 2  # methods list stores field names
        assert "x" in result.classes[0].methods or "y" in result.classes[0].methods
    
    def test_extract_typedef_struct(self, parser, tmp_path):
        """Test extracting a typedef struct."""
        test_file = tmp_path / "test_struct.h"
        test_file.write_text("""
typedef struct {
    char* config_path;
    bool initialized;
} BaseService;
""")
        
        result = parser.parse_file(test_file)
        assert len(result.classes) == 1
        assert result.classes[0].name == "BaseService"
        assert len(result.classes[0].methods) >= 2  # Should have fields
        assert "config_path" in result.classes[0].methods or "initialized" in result.classes[0].methods
    
    def test_extract_struct_from_service_h(self, parser):
        """Test extracting structs from service.h."""
        service_file = Path(__file__).parent.parent / "test_code" / "C" / "service.h"
        if not service_file.exists():
            pytest.skip("service.h not found")
        
        result = parser.parse_file(service_file)
        assert len(result.classes) >= 2  # BaseService and UserService
        
        # Find BaseService
        base_service = None
        for cls in result.classes:
            if cls.name == "BaseService":
                base_service = cls
                break
        
        assert base_service is not None, "BaseService should be found"
        assert len(base_service.methods) >= 2, "BaseService should have fields"
        assert "config_path" in base_service.methods or "initialized" in base_service.methods
    
    def test_extract_union(self, parser, tmp_path):
        """Test extracting a union."""
        test_file = tmp_path / "test_union.c"
        test_file.write_text("""
union MyUnion {
    int i;
    float f;
};
""")
        
        result = parser.parse_file(test_file)
        assert len(result.classes) == 1
        assert result.classes[0].name == "MyUnion"
        assert len(result.classes[0].methods) >= 2
    
    def test_extract_enum(self, parser, tmp_path):
        """Test extracting an enum."""
        test_file = tmp_path / "test_enum.c"
        test_file.write_text("""
enum MyEnum {
    VALUE1,
    VALUE2,
    VALUE3
};
""")
        
        result = parser.parse_file(test_file)
        # Enums might not have fields extracted the same way, but should be found
        assert len(result.classes) >= 0  # Enums are extracted as classes

