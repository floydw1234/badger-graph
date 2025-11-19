"""Tests for Python import extraction."""

import pytest
from pathlib import Path
from badger.parsers.python import PythonParser


class TestImportExtraction:
    """Test import extraction from Python files."""
    
    @pytest.fixture
    def parser(self):
        """Create a Python parser instance."""
        return PythonParser()
    
    def test_extract_simple_import(self, parser, tmp_path):
        """Test extracting a simple import statement."""
        test_file = tmp_path / "test_imports.py"
        test_file.write_text("import os\n")
        
        result = parser.parse_file(test_file)
        assert len(result.imports) == 1
        assert result.imports[0].module == "os"
        assert result.imports[0].imported_items == []
        assert result.imports[0].alias is None
    
    def test_extract_import_with_alias(self, parser, tmp_path):
        """Test extracting import with alias."""
        test_file = tmp_path / "test_imports.py"
        test_file.write_text("import json as json_module\n")
        
        result = parser.parse_file(test_file)
        assert len(result.imports) == 1
        assert result.imports[0].module == "json"
        assert result.imports[0].alias == "json_module"
    
    def test_extract_from_import(self, parser, tmp_path):
        """Test extracting from X import Y."""
        test_file = tmp_path / "test_imports.py"
        test_file.write_text("from typing import List\n")
        
        result = parser.parse_file(test_file)
        assert len(result.imports) == 1
        assert result.imports[0].module == "typing"
        assert "List" in result.imports[0].imported_items
    
    def test_extract_from_import_multiple(self, parser, tmp_path):
        """Test extracting from X import Y, Z."""
        test_file = tmp_path / "test_imports.py"
        test_file.write_text("from typing import List, Dict, Optional\n")
        
        result = parser.parse_file(test_file)
        assert len(result.imports) == 1
        assert result.imports[0].module == "typing"
        assert "List" in result.imports[0].imported_items
        assert "Dict" in result.imports[0].imported_items
        assert "Optional" in result.imports[0].imported_items
    
    def test_extract_from_import_with_alias(self, parser, tmp_path):
        """Test extracting from X import Y as Z."""
        test_file = tmp_path / "test_imports.py"
        test_file.write_text("from os import path as os_path\n")
        
        result = parser.parse_file(test_file)
        assert len(result.imports) == 1
        assert result.imports[0].module == "os"
        assert "path" in result.imports[0].imported_items
        assert result.imports[0].alias == "os_path"
    
    def test_extract_imports_from_sample_app(self, parser):
        """Test extracting imports from sample_app.py."""
        sample_file = Path(__file__).parent.parent / "test_code" / "python" / "sample_app.py"
        if not sample_file.exists():
            pytest.skip("sample_app.py not found")
        
        result = parser.parse_file(sample_file)
        assert len(result.imports) > 0
        
        # Check for specific imports
        import_modules = [imp.module for imp in result.imports if imp.module]
        assert "json" in import_modules or any("json" in str(imp.text) for imp in result.imports)
        assert "os" in import_modules or any("os" in str(imp.text) for imp in result.imports)
        
        # Check for from imports
        from_imports = [imp for imp in result.imports if imp.module and imp.imported_items]
        assert len(from_imports) > 0, "Should have at least one 'from X import Y' statement"
    
    def test_extract_imports_from_dynamic_imports(self, parser):
        """Test extracting imports from dynamic_imports.py."""
        dynamic_file = Path(__file__).parent.parent / "test_code" / "python" / "dynamic_imports.py"
        if not dynamic_file.exists():
            pytest.skip("dynamic_imports.py not found")
        
        result = parser.parse_file(dynamic_file)
        assert len(result.imports) > 0
        
        # Check for aliased imports
        aliased_imports = [imp for imp in result.imports if imp.alias]
        assert len(aliased_imports) > 0, "Should have aliased imports"

