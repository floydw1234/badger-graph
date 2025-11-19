"""Tests for C include extraction."""

import pytest
from pathlib import Path
from badger.parsers.c import CParser


class TestCIncludeExtraction:
    """Test include extraction from C files."""
    
    @pytest.fixture
    def parser(self):
        """Create a C parser instance."""
        return CParser()
    
    def test_extract_system_include(self, parser, tmp_path):
        """Test extracting a system include."""
        test_file = tmp_path / "test_include.c"
        test_file.write_text('#include <stdio.h>\n')
        
        result = parser.parse_file(test_file)
        assert len(result.imports) == 1
        assert result.imports[0].module == "stdio.h"
        assert "system" in result.imports[0].imported_items
    
    def test_extract_local_include(self, parser, tmp_path):
        """Test extracting a local include."""
        test_file = tmp_path / "test_include.c"
        test_file.write_text('#include "service.h"\n')
        
        result = parser.parse_file(test_file)
        assert len(result.imports) == 1
        assert result.imports[0].module == "service.h"
        assert "local" in result.imports[0].imported_items
    
    def test_extract_multiple_includes(self, parser, tmp_path):
        """Test extracting multiple includes."""
        test_file = tmp_path / "test_include.c"
        test_file.write_text("""
#include <stdio.h>
#include <stdlib.h>
#include "service.h"
#include "user.h"
""")
        
        result = parser.parse_file(test_file)
        assert len(result.imports) == 4
        
        # Check system includes
        system_includes = [imp for imp in result.imports if "system" in imp.imported_items]
        assert len(system_includes) == 2
        
        # Check local includes
        local_includes = [imp for imp in result.imports if "local" in imp.imported_items]
        assert len(local_includes) == 2
    
    def test_extract_includes_from_service_c(self, parser):
        """Test extracting includes from service.c."""
        service_file = Path(__file__).parent.parent / "test_code" / "C" / "service.c"
        if not service_file.exists():
            pytest.skip("service.c not found")
        
        result = parser.parse_file(service_file)
        assert len(result.imports) > 0
        
        # Should have both system and local includes
        include_modules = [imp.module for imp in result.imports if imp.module]
        assert len(include_modules) > 0
        
        # Check for specific includes
        module_names = [imp.module for imp in result.imports]
        assert "service.h" in module_names or any("service.h" in str(imp.text) for imp in result.imports)
    
    def test_extract_includes_from_main_c(self, parser):
        """Test extracting includes from main.c."""
        main_file = Path(__file__).parent.parent / "test_code" / "C" / "main.c"
        if not main_file.exists():
            pytest.skip("main.c not found")
        
        result = parser.parse_file(main_file)
        assert len(result.imports) > 0
        
        # Should have local includes
        local_includes = [imp for imp in result.imports if "local" in imp.imported_items]
        assert len(local_includes) > 0

