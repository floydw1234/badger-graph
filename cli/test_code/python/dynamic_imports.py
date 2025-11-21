"""
Test file demonstrating dynamic imports and conditional imports.
"""

import importlib
import sys
from typing import Any, Callable

# Conditional imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from requests import get, post
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    get = None
    post = None

# Import aliases yayay
import json as json_module
from os import path as os_path
from os.path import join as path_join, exists as path_exists

# Star import (testing edge case)
from typing import *

def dynamic_import_module(module_name: str) -> Any:
    """Dynamically import a module at runtime."""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None

def load_plugin(plugin_name: str) -> Callable:
    """Load a plugin module dynamically."""
    module = dynamic_import_module(f"plugins.{plugin_name}")
    if module and hasattr(module, 'execute'):
        return module.execute
    return lambda: None

def fetch_data(url: str) -> dict:
    """Fetch data using requests if available."""
    if HAS_REQUESTS and get:
        response = get(url)
        return response.json()
    return {}

def process_array(data: list) -> list:
    """Process array using numpy if available."""
    if HAS_NUMPY and np:
        arr = np.array(data)
        return arr.tolist()
    return data

def save_config(config: dict, filepath: str) -> None:
    """Save config using aliased imports."""
    if os_path.exists(os_path.dirname(filepath)):
        full_path = path_join(os_path.dirname(filepath), "config.json")
        with open(full_path, 'w') as f:
            json_module.dump(config, f)

def main():
    """Test various import patterns."""
    # Dynamic module loading
    math_module = dynamic_import_module('math')
    if math_module:
        result = math_module.sqrt(16)
        print(f"Square root: {result}")
    
    # Conditional function calls
    if HAS_REQUESTS:
        data = fetch_data("https://api.example.com/data")
        print(f"Fetched data: {data}")
    
    # Aliased imports
    config = {"key": "value"}
    save_config(config, "/tmp/test")
    
    # Nested function calls with aliases
    if path_exists("/tmp"):
        joined = path_join("/tmp", "test", "file.txt")
        print(f"Path: {joined}")

if __name__ == "__main__":
    main()


