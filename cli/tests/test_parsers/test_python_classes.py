"""Tests for Python class extraction."""

import pytest
from pathlib import Path
from badger.parsers.python import PythonParser


class TestClassExtraction:
    """Test class extraction from Python files."""
    
    @pytest.fixture
    def parser(self):
        """Create a Python parser instance."""
        return PythonParser()
    
    def test_extract_class_without_inheritance(self, parser, tmp_path):
        """Test extracting a class without inheritance."""
        test_file = tmp_path / "test_class.py"
        test_file.write_text("""
class SimpleClass:
    def method1(self):
        pass
""")
        
        result = parser.parse_file(test_file)
        assert len(result.classes) == 1
        assert result.classes[0].name == "SimpleClass"
        assert result.classes[0].base_classes == []
        assert "method1" in result.classes[0].methods
    
    def test_extract_class_with_inheritance(self, parser, tmp_path):
        """Test extracting a class with inheritance."""
        test_file = tmp_path / "test_class.py"
        test_file.write_text("""
class BaseClass:
    pass

class DerivedClass(BaseClass):
    def method1(self):
        pass
""")
        
        result = parser.parse_file(test_file)
        assert len(result.classes) == 2
        
        # Find DerivedClass
        derived = None
        for cls in result.classes:
            if cls.name == "DerivedClass":
                derived = cls
                break
        
        assert derived is not None
        assert "BaseClass" in derived.base_classes
        assert "method1" in derived.methods
    
    def test_extract_class_from_sample_app(self, parser):
        """Test extracting classes from sample_app.py."""
        sample_file = Path(__file__).parent.parent / "test_code" / "python" / "sample_app.py"
        if not sample_file.exists():
            pytest.skip("sample_app.py not found")
        
        result = parser.parse_file(sample_file)
        
        # Find UserService class
        user_service = None
        for cls in result.classes:
            if cls.name == "UserService":
                user_service = cls
                break
        
        assert user_service is not None, "UserService class should be found"
        assert "BaseService" in user_service.base_classes, f"Expected BaseService in base_classes, got {user_service.base_classes}"
        assert len(user_service.methods) > 0, "UserService should have methods"
        # Check for some expected methods
        method_names = [m for m in user_service.methods]
        assert "initialize" in method_names or "create_user" in method_names, f"Expected methods in UserService, got {method_names}"
    
    def test_extract_class_with_multiple_inheritance(self, parser, tmp_path):
        """Test extracting a class with multiple inheritance."""
        test_file = tmp_path / "test_class.py"
        test_file.write_text("""
class Base1:
    pass

class Base2:
    pass

class Derived(Base1, Base2):
    def method1(self):
        pass
""")
        
        result = parser.parse_file(test_file)
        derived = None
        for cls in result.classes:
            if cls.name == "Derived":
                derived = cls
                break
        
        assert derived is not None
        assert len(derived.base_classes) >= 1, "Should have at least one base class"
        assert "method1" in derived.methods

