"""File discovery and reading utilities."""

from pathlib import Path
from typing import List, Optional


def detect_language(file_path: Path) -> Optional[str]:
    """Detect programming language from file extension."""
    extension = file_path.suffix.lower()
    
    language_map = {
        ".py": "python",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hxx": "cpp",
    }
    
    return language_map.get(extension)


def find_source_files(
    directory: Path,
    language: Optional[str] = None,
    exclude_patterns: Optional[List[str]] = None
) -> List[Path]:
    """Find source files in a directory.
    
    Args:
        directory: Root directory to search
        language: Language to filter by (e.g., "python", "c"). If None, finds all supported languages
        exclude_patterns: List of patterns to exclude (e.g., ["**/node_modules/**", "**/.git/**"])
    
    Returns:
        List of source file paths
    """
    if exclude_patterns is None:
        exclude_patterns = ["**/node_modules/**", "**/.git/**", "**/__pycache__/**", "**/.badger-index/**"]
    
    source_files = []
    
    # Language-specific extensions
    if language == "python":
        extensions = [".py"]
    elif language == "c":
        extensions = [".c", ".h"]
    elif language is None:
        # Find all supported languages
        extensions = [".py", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx"]
    else:
        # Unknown language, return empty
        return []
    
    for ext in extensions:
        pattern = f"**/*{ext}"
        for file_path in directory.rglob(pattern):
            # Check if file should be excluded
            should_exclude = False
            for pattern in exclude_patterns:
                if file_path.match(pattern):
                    should_exclude = True
                    break
            
            if not should_exclude and file_path.is_file():
                source_files.append(file_path)
    
    return sorted(source_files)


def read_file_content(file_path: Path) -> str:
    """Read file content as string."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        raise RuntimeError(f"Failed to read file {file_path}: {e}")

