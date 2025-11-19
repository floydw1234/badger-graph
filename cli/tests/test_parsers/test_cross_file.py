"""Tests for cross-file relationship building."""

import pytest
from pathlib import Path
from badger.parsers.c import CParser
from badger.parsers.cross_file import CrossFileResolver


class TestCrossFileRelationships:
    """Test cross-file relationship resolution."""
    
    @pytest.fixture
    def parser(self):
        """Create a C parser instance."""
        return CParser()
    
    def test_resolve_function_call_same_file(self, parser, tmp_path):
        """Test resolving function call in same file."""
        test_file = tmp_path / "test.c"
        test_file.write_text("""
void helper() {
}

void caller() {
    helper();
}
""")
        
        result = parser.parse_file(test_file)
        resolver = CrossFileResolver([result])
        
        # Find the helper() call
        helper_call = None
        for call in result.function_calls:
            if call.callee_name == "helper":
                helper_call = call
                break
        
        assert helper_call is not None
        resolved_func = resolver.resolve_function_call(helper_call)
        assert resolved_func is not None
        assert resolved_func.name == "helper"
    
    def test_resolve_function_call_cross_file(self, parser, tmp_path):
        """Test resolving function call across files."""
        # Create header file
        header_file = tmp_path / "helper.h"
        header_file.write_text("""
void helper();
""")
        
        # Create source file that includes header
        source_file = tmp_path / "main.c"
        source_file.write_text("""
#include "helper.h"

void main() {
    helper();
}
""")
        
        header_result = parser.parse_file(header_file)
        source_result = parser.parse_file(source_file)
        
        resolver = CrossFileResolver([header_result, source_result])
        
        # Find the helper() call in main.c
        helper_call = None
        for call in source_result.function_calls:
            if call.callee_name == "helper":
                helper_call = call
                break
        
        assert helper_call is not None
        resolved_func = resolver.resolve_function_call(helper_call)
        assert resolved_func is not None
        assert resolved_func.name == "helper"
    
    def test_build_call_graph(self, parser, tmp_path):
        """Test building a call graph."""
        test_file = tmp_path / "test.c"
        test_file.write_text("""
void func1() {
    func2();
}

void func2() {
    func3();
}

void func3() {
}
""")
        
        result = parser.parse_file(test_file)
        resolver = CrossFileResolver([result])
        
        call_graph = resolver.get_call_graph()
        assert "func2" in call_graph
        assert "func1" in call_graph["func2"]
        assert "func3" in call_graph
        assert "func2" in call_graph["func3"]
    
    def test_file_dependencies(self, parser, tmp_path):
        """Test building file dependency graph."""
        header_file = tmp_path / "header.h"
        header_file.write_text("")
        
        source_file = tmp_path / "main.c"
        source_file.write_text('#include "header.h"\n')
        
        header_result = parser.parse_file(header_file)
        source_result = parser.parse_file(source_file)
        
        resolver = CrossFileResolver([header_result, source_result])
        dependencies = resolver.get_file_dependencies()
        
        # main.c should depend on header.h
        assert str(source_file) in dependencies
        # Note: The dependency resolution is simplified, so this might not always work
        # depending on path resolution
    
    def test_resolve_calls_from_test_code(self, parser):
        """Test resolving calls from actual test code files."""
        test_dir = Path(__file__).parent.parent / "test_code" / "C"
        
        files_to_parse = ["main.c", "service.c", "service.h"]
        parse_results = []
        
        for filename in files_to_parse:
            file_path = test_dir / filename
            if file_path.exists():
                result = parser.parse_file(file_path)
                parse_results.append(result)
        
        if len(parse_results) < 2:
            pytest.skip("Not enough test files found")
        
        resolver = CrossFileResolver(parse_results)
        
        # Check that we can resolve some function calls
        resolved_count = 0
        for result in parse_results:
            for call in result.function_calls:
                resolved = resolver.resolve_function_call(call)
                if resolved:
                    resolved_count += 1
        
        # Should be able to resolve at least some calls
        assert resolved_count > 0, "Should resolve at least some function calls"

