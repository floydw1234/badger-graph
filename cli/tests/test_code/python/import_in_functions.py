"""
Test file demonstrating imports inside functions and late imports.
"""

def import_inside_function():
    """Import a module inside a function."""
    import random
    return random.randint(1, 100)

def conditional_import(use_advanced: bool):
    """Conditionally import based on parameter."""
    if use_advanced:
        import hashlib
        return hashlib.md5(b"test").hexdigest()
    else:
        import base64
        return base64.b64encode(b"test").decode()

def late_import_example():
    """Example of late import pattern."""
    # Import at point of use
    from collections import defaultdict, Counter
    from itertools import chain, combinations
    
    data = [1, 2, 2, 3, 3, 3]
    counter = Counter(data)
    return dict(counter)

def import_and_call():
    """Import and immediately call."""
    from datetime import datetime, timedelta
    now = datetime.now()
    future = now + timedelta(days=7)
    return future.isoformat()

def nested_import_scope():
    """Import in nested scope."""
    def inner_function():
        import sys
        return sys.version
    return inner_function()

def import_with_alias_in_function():
    """Import with alias inside function."""
    import json as json_lib
    import os.path as ospath
    
    data = {"test": "value"}
    json_str = json_lib.dumps(data)
    exists = ospath.exists("/tmp")
    return json_str, exists

def dynamic_import_choice(module_name: str):
    """Dynamically choose which module to import."""
    if module_name == "math":
        import math
        return math.sqrt(16)
    elif module_name == "random":
        import random
        return random.choice([1, 2, 3, 4])
    else:
        import string
        return string.ascii_letters

def import_from_package():
    """Import from a package inside function."""
    from typing import List, Dict, Optional
    from dataclasses import dataclass
    
    @dataclass
    class LocalData:
        items: List[str]
        metadata: Dict[str, Optional[str]]
    
    return LocalData(items=["a", "b"], metadata={"key": "value"})

def main():
    """Test various import-in-function patterns."""
    # Import inside function
    result1 = import_inside_function()
    print(f"Random: {result1}")
    
    # Conditional import
    result2 = conditional_import(True)
    print(f"Hash: {result2}")
    result3 = conditional_import(False)
    print(f"Base64: {result3}")
    
    # Late import
    result4 = late_import_example()
    print(f"Counter: {result4}")
    
    # Import and call
    result5 = import_and_call()
    print(f"Future date: {result5}")
    
    # Nested scope
    result6 = nested_import_scope()
    print(f"Python version: {result6}")
    
    # Alias in function
    result7, result8 = import_with_alias_in_function()
    print(f"JSON: {result7}, Path exists: {result8}")
    
    # Dynamic choice
    result9 = dynamic_import_choice("math")
    print(f"Math result: {result9}")
    result10 = dynamic_import_choice("random")
    print(f"Random result: {result10}")
    
    # Package import
    result11 = import_from_package()
    print(f"Local data: {result11}")

if __name__ == "__main__":
    main()

